import requests
import json
import logging
from flask import current_app

from app.extensions import db
from app.models import PendingSubmission, EssayAssignment, StudentProfile, User, Enrollment
from app.llm.provider import get_llm_provider, LLMConnectionError

logger = logging.getLogger(__name__)

# Define a reasonable chunk size to avoid oversized API requests
PROMPT_CHUNK_SIZE = 20

class AiMatcherError(Exception):
    """Custom exception for AI Matcher related errors."""
    pass

def _get_student_roster(assignment_id):
    """
    Fetches the student roster for a given assignment.
    Returns a list of strings, e.g., ["张三 (学号: 202301)", "李四 (学号: 202302)"].
    """
    assignment = db.session.get(EssayAssignment, assignment_id)
    if not assignment:
        raise AiMatcherError(f"Assignment with id {assignment_id} not found.")

    roster = []
    # An assignment can be linked to classrooms or individual students
    # 1. Get students from classrooms
    for classroom in assignment.classrooms:
        for enrollment in classroom.enrollments:
            student_user = enrollment.student.user
            student_name = student_user.full_name
            student_number = enrollment.student_number or '无学号'
            roster.append(f"{student_name} (学号: {student_number})")

    # Get students assigned individually
    for student_profile in assignment.students:
        student_name = student_profile.user.full_name
        # Since we don't have an enrollment context here, we cannot get a student number.
        # We will just use the name for matching.
        roster_entry = f"{student_name}"
        if roster_entry not in roster:
            roster.append(roster_entry)

    if not roster:
        raise AiMatcherError("Could not generate a student roster for the assignment.")

    return list(set(roster)) # Return unique list

def _build_prompt(roster, submissions_data):
    """
    Builds the structured prompt for the LLM.
    """
    # Using f-string for multiline strings is cleaner
    return f"""
# 角色
你是一名经验丰富的教师助手，你的任务是根据图片中识别出的文字，将其与学生名单进行匹配。

# 上下文
- **学生名单**: {json.dumps(roster, ensure_ascii=False)}
- **待匹配内容**: 
  {json.dumps(submissions_data, ensure_ascii=False, indent=2)}

# 任务指令
1.  请仔细分析每个“识别文本”，找出其中可能存在的学生姓名或学号。
2.  “识别文本”可能存在OCR识别错误，请进行模糊匹配。例如，“张こ”应匹配到“张三”，“学号: 2o23o1”应匹配到学号“202301”。
3.  对于每个“文件名”，在“学生名单”中找到最匹配的一项。
4.  如果某段文本无法找到任何可匹配的姓名或学号，请将该文件的匹配结果设为 `null`。
5.  最终，请只返回一个JSON对象，key为“文件名”，value为匹配到的学生姓名（只需姓名，不要包含学号）。不要包含任何额外的解释或Markdown标记。

# 输出格式示例
{{
  "image1.jpg": "张三",
  "image2.png": "李四",
  "image3.jpeg": null
}}
"""

def _call_llm_api(prompt):
    """
    Calls the DeepSeek API and returns the parsed JSON response.
    """
    # Use LLMProvider for automatic retry logic
    system_prompt = "You are a helpful assistant that returns JSON."
    combined_prompt = system_prompt + "\n\n" + prompt
    
    try:
        logger.debug(f"Calling AI matcher with retry logic")
        
        provider = get_llm_provider()
        result = provider.call_llm(
            prompt=combined_prompt,
            max_retries=2,      # Allow 2 retries for network issues
            timeout=60,         # 60 second timeout per attempt
            require_json=True,  # Matcher needs JSON format
            temperature=0.1
        )
        
        return result

    except LLMConnectionError as e:
        logger.error(f"LLM API request failed due to network issue: {e}")
        raise AiMatcherError(f"Could not connect to the LLM service: {e}")
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to parse LLM response: {e}")
        raise AiMatcherError("Invalid JSON response from the LLM service.")


def _process_chunk(chunk, roster, user_map):
    """Processes a single chunk of submissions."""
    try:
        submissions_data = [
            {"文件名": sub.original_filename, "识别文本": sub.ocr_text}
            for sub in chunk
        ]
        prompt = _build_prompt(roster, submissions_data)
        matched_results = _call_llm_api(prompt)

        for sub in chunk:
            student_name = matched_results.get(sub.original_filename)
            if student_name:
                student_profile = user_map.get(student_name)
                if student_profile:
                    sub.matched_student_id = student_profile.id
                    sub.status = 'match_completed'
                else:
                    sub.status = 'failed'
                    sub.error_message = f"LLM matched to '{student_name}', but this student was not found in the roster map."
            else:
                sub.status = 'match_completed'
        db.session.commit()
    except AiMatcherError as e:
        logger.error(f"Failed to process a chunk for matching: {e}")
        for sub in chunk:
            sub.status = 'failed'
            sub.error_message = f"AI Matching failed for this batch: {e}"
        db.session.commit()

def match_students_for_assignment(assignment_id):
    """
    Main entry point for the AI matcher service.
    Processes all 'ocr_completed' submissions for an assignment in chunks.
    """
    app = current_app._get_current_object()
    with app.app_context():
        submissions = PendingSubmission.query.filter_by(
            assignment_id=assignment_id,
            status='ocr_completed'
        ).all()

        if not submissions:
            logger.info(f"No submissions with 'ocr_completed' status for assignment {assignment_id}.")
            return

        logger.info(f"Found {len(submissions)} raw submissions with 'ocr_completed' status for assignment {assignment_id}.")

        # --- Pre-filter submissions with invalid OCR text ---
        MIN_OCR_TEXT_LENGTH = 2
        valid_submissions = []
        for sub in submissions:
            if sub.ocr_text and len(sub.ocr_text.strip()) >= MIN_OCR_TEXT_LENGTH:
                valid_submissions.append(sub)
            else:
                logger.warning(f"Submission {sub.id} (file: {sub.original_filename}) has insufficient OCR text. Marking as failed.")
                sub.status = 'failed'
                sub.error_message = "OCR text is empty or too short for matching."
        db.session.commit()
        # ----------------------------------------------------

        if not valid_submissions:
            logger.info(f"No submissions with valid OCR text to match for assignment {assignment_id}.")
            return
            
        logger.info(f"Found {len(valid_submissions)} submissions with valid OCR text to process for assignment {assignment_id}.")

        try:
            roster = _get_student_roster(assignment_id)
            if not roster:
                raise AiMatcherError("Could not generate a student roster for the assignment.")

            # Create a name-to-profile map for quick lookups
            all_users = User.query.filter(User.student_profile != None).all()
            user_map = {user.full_name: user.student_profile for user in all_users}

            # Process submissions in chunks, now using the filtered list
            for i in range(0, len(valid_submissions), PROMPT_CHUNK_SIZE):
                chunk = valid_submissions[i:i + PROMPT_CHUNK_SIZE]
                logger.info(f"Processing chunk {i // PROMPT_CHUNK_SIZE + 1} with {len(chunk)} submissions.")
                _process_chunk(chunk, roster, user_map)
            
            logger.info(f"Successfully finished matching all chunks for assignment {assignment_id}.")

        except AiMatcherError as e:
            logger.error(f"AI Matcher Error for assignment {assignment_id}: {e}")
            # Mark all remaining (un-chunked) submissions as failed
            for sub in submissions:
                if sub.status == 'ocr_completed': # Only fail those that haven't been touched
                    sub.status = 'failed'
                    sub.error_message = str(e)
            db.session.commit()
        except Exception as e:
            logger.error(f"Unexpected Error during matching for assignment {assignment_id}: {e}", exc_info=True)
            for sub in submissions:
                if sub.status == 'ocr_completed':
                    sub.status = 'failed'
                    sub.error_message = "An unexpected server error occurred during matching."
            db.session.commit() 
import json
import requests
from flask import current_app
from app.extensions import db
from app.models import Essay, PromptStyleTemplate, GradeLevel

def _format_grading_standard_for_prompt(standard):
    """Formats the grading standard from DB objects into a string for the AI prompt."""
    if not standard:
        return "没有提供评分标准。"
    
    # Using a list and join for better performance and readability
    prompt_lines = [
        f"作文题目: {standard.title}",
        f"总分: {standard.total_score}\n"
    ]

    for dim in sorted(standard.dimensions, key=lambda d: d.id):
        prompt_lines.append(f"--- 维度: {dim.name} (满分: {dim.max_score}) ---")
        # Sort rubrics by score to maintain a consistent order (A, B, C...)
        for rubric in sorted(dim.rubrics, key=lambda r: r.max_score, reverse=True):
            prompt_lines.append(f"  - {rubric.level_name} ({rubric.min_score}~{rubric.max_score}分): {rubric.description}")
        prompt_lines.append("") # Add a blank line for spacing

    return "\n".join(prompt_lines)


def _build_prompt(essay_text, grading_standard_text, style_instructions, is_from_ocr=False):
    """Builds the full prompt for the AI model."""
    
    ocr_warning = ""
    if is_from_ocr:
        ocr_warning = """
---
**【重要指导：请优先理解，宽容错误】**
你正在分析的这篇学生作文是通过OCR（光学字符识别）技术从图片转换而来，这在处理中文时尤其容易出错。请在评分时展现你的高度智能，并遵循以下原则：

1.  **忽略典型的OCR错误**：
    *   **形近字混淆**：不要因为常见的识别错误而扣分，例如把“己”识别成“已”或“巳”；“日”识别成“曰”；“天”识别成“夫”；“末”识别成“未”。
    *   **标点符号错误**：中文逗号句号（，。）被识别成英文逗号句号（,.）是常态，请完全忽略这类问题。
    *   **格式和粘连**：文本中可能出现不自然的换行、多余的空格，或者文字粘连（如“我和你”变成“我禾口你”），甚至文字拆分（如“好”变成“女子”）。请尝试根据上下文理解原文。
    *   **少字漏字**：部分词句可能因识别不全出现缺字、漏字等现象，只要结合上下文能合理推断原意，请不要因此扣分。

2.  **聚焦核心素养**：
    *   你的评分重点应该是文章的**思想内容、结构安排、语言表达和创意特色**。
    *   请主动推断原文意图。如果一个词或句子看起来不通顺，但结合上下文可以明显看出是OCR识别错误，请基于你推断出的正确含义进行评价，不要揪住错字不放。

3.  **智能判断**：
    *   如果一句话由于识别错误实在无法理解，可以在评价中指出“某处内容因识别问题无法完全理解”，但不要因此作出负面评价，除非这影响了对整个段落或篇章的理解。

你的核心任务是作为一名富有经验和同理心的语文老师，洞察学生真实的表达水平，而不是测试OCR软件的准确率。
---
"""

    # This is the JSON structure we want the AI to return.
    # Providing it as a clear example is crucial for reliable JSON output.
    json_format_example = """
{
  "total_score": "<number: 根据各维度得分计算出的总分>",
  "overall_comment": "<string: (使用Markdown) 对作文的综合评价和鼓励语>",
  "strengths": [
    "<string: 从全文角度看，提炼出的一个核心优点>",
    "<string: 从全文角度看，提炼出的另一个核心优点>"
  ],
  "improvements": [
    "<string: 从全文角度看，给出的一个主要改进建议>",
    "<string: 从全文角度看，给出的另一个主要改进建议>"
  ],
  "dimensions": [
    {
      "dimension_name": "<string: 第一个维度的名称>",
      "score": "<number: 该维度的最终得分>",
      "selected_rubric_level": "<string: 根据得分和标准，判定该维度所属的等级，例如'A'或'B'>",
      "feedback": "<string: (使用Markdown) 针对该维度的详细评价，解释为什么得到这个分数，并结合原文进行分析>",
      "example_good_sentence": "<string: 从原文中摘录一句能体现该维度优点的话，如果没有则返回空字符串>",
      "example_improvement_suggestion": {
        "original": "<string: 从原文中摘录一句该维度下有待改进的话>",
        "suggested": "<string: 针对上面那句话给出具体的优化范例>"
      }
    }
  ]
}
"""
    
    prompt = f"""
{style_instructions}

你的任务是根据下面提供的【评分标准详情】，对这篇【学生作文】进行打分和评价。

**【你的输出要求】**
你的回答**必须且只能**是一个完整的、符合下面【JSON输出格式】定义的JSON对象。
绝对不要在JSON代码块之外添加任何导语、解释、注释、总结或其他任何文字。返回的内容必须能直接被Python的`json.loads()`方法解析。
{ocr_warning}
---
**【学生作文】**

{essay_text}

---
**【评分标准详情】**

{grading_standard_text}

---
**【JSON输出格式】**

请严格按照以下JSON结构和字段名返回你的分析结果：
```json
{json_format_example.strip()}
```
"""
    return prompt.strip()


def grade_essay_with_ai(essay_id: int) -> None:
    """
    Grades a given Essay by its ID using an AI model and populates its fields.
    
    This function handles its own database session and commits the transaction.
    It is safe for concurrent execution.

    Args:
        essay_id: The ID of the Essay to be graded.

    Returns:
        None. The function updates the database directly.
    """
    essay = db.session.get(Essay, essay_id)
    if not essay:
        current_app.logger.error(f"AI grading failed: Essay with ID {essay_id} not found.")
        return

    try:
        # Ensure we have text to grade and a standard to grade against
        if not essay.content:
            essay.status = 'error_no_text'
            current_app.logger.warning(f"AI grading failed: Essay ID {essay.id} has no text content.")
            db.session.commit()
            return
            
        grading_standard = essay.assignment.grading_standard if essay.assignment else essay.grading_standard
        if not grading_standard:
            essay.status = 'error_no_standard'
            current_app.logger.warning(f"AI grading failed: Essay ID {essay.id} is not associated with a grading standard.")
            db.session.commit()
            return
        
        # --- NEW: Dynamically fetch prompt style with new priority ---
        style_instructions = ""
        
        # 1. Check for a style specifically set on the assignment by the teacher
        if essay.assignment and essay.assignment.prompt_style_template:
            style_instructions = essay.assignment.prompt_style_template.style_instructions
        
        # 2. If not set, find the default style for the student's grade level
        else:
            grade_level = grading_standard.grade_level
            if grade_level:
                assoc = grade_level.prompt_style_associations.filter_by(is_default=True).first()
                if assoc:
                    style_instructions = assoc.prompt_style_template.style_instructions

        # 3. Fallback to a generic instruction if no specific or default template is found
        if not style_instructions:
            style_instructions = "请你扮演一位专业、细致、严格的语文老师。"
        # --- END NEW ---

        # Set status to 'grading' just before the API call
        essay.status = 'grading'
        db.session.commit() # Commit status change immediately so other processes can see it
        current_app.logger.debug(f"Status for Essay ID {essay.id} set to 'grading'.")

        # 1. Format the standard and build the prompt
        grading_standard_text = _format_grading_standard_for_prompt(grading_standard)
        prompt = _build_prompt(essay.content, grading_standard_text, style_instructions, essay.is_from_ocr)

        # 2. Call the AI API
        api_key = current_app.config['DEEPSEEK_API_KEY']
        api_url = current_app.config['DEEPSEEK_API_URL']

        payload = {
            "model": current_app.config.get('DEEPSEEK_MODEL_CHAT'),
            # "model": current_app.config.get('DEEPSEEK_MODEL_REASONER'),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5,
            "response_format": {"type": "json_object"}
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(api_url, headers=headers, data=json.dumps(payload), timeout=180)
        response.raise_for_status()

        # 3. Parse and populate the result
        ai_result_json = response.json()
        
        if "choices" in ai_result_json and ai_result_json["choices"]:
            content_str = ai_result_json["choices"][0]["message"]["content"]
            parsed_content = json.loads(content_str)
            essay.ai_score = parsed_content
            essay.status = 'graded'
            current_app.logger.info(f"Essay ID {essay.id} successfully graded by AI.")
            db.session.commit()
        else:
            raise ValueError("AI response JSON is empty or malformed.")

    except requests.RequestException as e:
        db.session.rollback()
        essay_to_update = db.session.get(Essay, essay_id)
        if essay_to_update:
            essay_to_update.status = 'error_api'
            essay_to_update.error_message = f"AI评分服务API请求失败: {str(e)[:500]}"
            current_app.logger.error(f"AI grading API request failed for Essay ID {essay_id}: {e}")
            db.session.commit()
    except (json.JSONDecodeError, ValueError) as e:
        db.session.rollback()
        essay_to_update = db.session.get(Essay, essay_id)
        if essay_to_update:
            essay_to_update.status = 'error_parsing'
            essay_to_update.error_message = f"解析AI评分服务返回结果失败: {str(e)[:500]}"
            current_app.logger.error(f"Failed to parse AI response for Essay ID {essay_id}: {e}")
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        essay_to_update = db.session.get(Essay, essay_id)
        if essay_to_update:
            essay_to_update.status = 'error_unknown'
            essay_to_update.error_message = f"AI评分时发生未知错误: {str(e)[:500]}"
            current_app.logger.error(f"An unknown error occurred during AI grading for Essay ID {essay_id}: {e}", exc_info=True)
            db.session.commit() 
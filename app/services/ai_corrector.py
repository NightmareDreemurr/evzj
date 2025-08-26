import requests
import json
from flask import current_app
from app.extensions import db
from app.models import Essay
from app.llm.provider import get_llm_provider, LLMConnectionError

class AIConnectionError(Exception):
    """Custom exception for AI service connection errors."""
    pass

def correct_text_with_ai(raw_text: str) -> str:
    """
    Uses a large language model to correct OCR-generated text, following the pattern in ai_grader.
    Args:
        raw_text: The raw text string from the OCR service.
    Returns:
        A corrected version of the text.
    Raises:
        AIConnectionError: If there's an issue with the AI service API call.
    """
    if not raw_text or not raw_text.strip():
        return ""

    try:
        api_key = current_app.config.get('DEEPSEEK_API_KEY')
        api_url = current_app.config.get('DEEPSEEK_API_URL')

        if not api_key or not api_url:
            raise AIConnectionError("DeepSeek API key or URL is not configured.")

        system_prompt = (
            "你是一位逻辑严谨、细致入微的中文校对专家和文本结构分析师。你的任务是分步处理OCR识别的学生作文文本，准确还原其原始内容和结构。\n\n"
            "### 核心处理流程\n\n"
            "**第一步：结构分析 (Analyze First)**\n"
            "你的首要任务是分析全文的结构。仔细检查文本是否存在一个持续的、交错的模式，这通常是双栏或跨页文本被错误识别的标志（例如：`左边第一行`\\n`右边第一行`\\n`左边第二行`\\n`右边第二行`...）。\n"
            "*   **判断条件**：**当且仅当**你高度确信整个文本主体都遵循这种清晰、规律的交错模式时，你才进入第二步进行结构重组。\n"
            "*   **例外情况**：如果文本只是局部混乱，或者没有明显的、贯穿全文的交错模式，**请跳过第二步**，直接进入第三步。这样做是为了避免错误地“修正”学生原文中本就存在的、非结构性的语言问题。\n\n"
            "**第二步：结构重组 (Reorganize Conditionally)**\n"
            "*此步骤仅在第一步分析结果为“是”时执行。*\n"
            "1.  **识别并分离**：将交错的文本分离成两个逻辑列（左列和右列）。\n"
            "2.  **重新拼接**：先完整拼接左列的所有内容，然后在其后拼接右列的所有内容，形成一篇结构连贯的草稿。\n\n"
            "**第三步：清理与内容校对 (Always Proofread)**\n"
            "*无论前两步发生了什么，此步骤都必须执行。*\n"
            "1.  **清理文首**：检查并**删除**位于文章最开头的任何疑似学生姓名（如“王予昊”、“李明”等）。最终输出必须以标题或正文第一句话开始。\n"
            "2.  **精细校对**：在（可能已经过重组的）文本上进行全面的内容校对。\n"
            "    *   **基础修正**：修正所有明显的错别字、标点错误等。\n"
            "    *   **上下文修正**：结合上下文修正形近字、音近字、专有名词等错误。\n"
            "    *   **保证文意通顺**，但必须忠于学生原文的核心思想。\n\n"
            "### 核心原则与限制\n"
            "*   **绝对忠于原文**：你的修改**必须**严格忠实于学生的原始意图和核心内容。绝不允许进行任何形式的创意性改写、内容增删或风格美化。你是在“校对”，不是在“重写”或“润色”。\n"
            "*   **保留学生风格**：尽量保留学生原文的语气和独特的个人表达方式。\n\n"
            "### 输出要求\n"
            "*   **纯文本输出**：你的返回内容**必须且只能**是修正后的纯净文本。\n"
            "*   **严禁任何额外内容**：不要包含任何解释、评论、前言或总结。\n\n"
            "### 综合修正示例 (适用于触发了结构重组的场景)\n"
            "# 输入 (OCR原始文本，模拟了姓名+双栏串行+错别字):\n"
            "王小明\\n"
            "俄昨天看3一本书，\\n"
            "他很勇敢。\\n"
            "书名叫<小日记>，\\n"
            "每当我读完这个故事，\\n"
            "里面有个小日月，\\n"
            "他就像一盏明灯。\\n\\n"
            "# 输出 (你应返回的文本):\n"
            "我昨天看了一本书，书名叫《小日记》，里面有个小明，他很勇敢。每当我读完这个故事，他就像一盏明灯。"
        )

        # Use LLMProvider for automatic retry logic
        prompt = f"请校对以下OCR识别的文本：\n\n{raw_text}"
        combined_prompt = system_prompt + "\n\n" + prompt
        
        current_app.logger.debug(f"Calling AI corrector with retry logic")
        
        provider = get_llm_provider()
        result = provider.call_llm(
            prompt=combined_prompt,
            max_retries=2,      # Allow 2 retries for network issues
            timeout=120,        # 120 second timeout per attempt
            require_json=False, # Text correction doesn't need JSON format
            temperature=0.2
        )
        
        # Extract the corrected text from the result
        if isinstance(result, dict) and 'content' in result:
            corrected_text = result['content'].strip()
        else:
            corrected_text = str(result).strip()
            
        return corrected_text

    except LLMConnectionError as e:
        current_app.logger.error(f"AI corrector service API request failed: {e}")
        raise AIConnectionError(f"AI校对服务API请求失败: {e}")
    except (json.JSONDecodeError, ValueError) as e:
        current_app.logger.error(f"Failed to parse AI corrector service response: {e}")
        raise AIConnectionError(f"解析AI校对服务返回结果失败: {e}")
    except Exception as e:
        current_app.logger.error(f"AI corrector service failed with an unknown error: {e}")
        raise AIConnectionError(f"AI校对服务发生未知错误: {e}") 


def correct_essay_with_ai(essay_id: int) -> None:
    """
    Fetches an essay by ID, corrects its OCR text using an AI model,
    and updates the content in the database.

    This function handles its own database session and commits the transaction.

    Args:
        essay_id: The ID of the Essay to be corrected.
    """
    essay = db.session.get(Essay, essay_id)
    if not essay:
        current_app.logger.error(f"AI correction failed: Essay with ID {essay_id} not found.")
        return

    if not essay.original_ocr_text or not essay.original_ocr_text.strip():
        current_app.logger.warning(f"Skipping AI correction for Essay {essay_id}: no original OCR text found.")
        essay.content = essay.original_ocr_text or ""
        # We can just set the content and commit, no need for AI.
        db.session.commit()
        return

    try:
        current_app.logger.debug(f"Starting AI correction for essay {essay_id}.")
        corrected_text = correct_text_with_ai(essay.original_ocr_text)
        essay.content = corrected_text
        current_app.logger.info(f"AI correction successful for essay {essay_id}.")
        db.session.commit()

    except AIConnectionError as e:
        db.session.rollback()
        # Re-fetch the essay after rollback
        essay_to_update = db.session.get(Essay, essay_id)
        if essay_to_update:
            essay_to_update.status = 'error_correction'
            essay_to_update.error_message = f"AI校对连接失败: {str(e)[:500]}"
            essay_to_update.content = essay.original_ocr_text # Revert content to original
            db.session.commit()
        current_app.logger.error(f"AI correction failed for essay {essay_id}: {e}")
    except Exception as e:
        db.session.rollback()
        essay_to_update = db.session.get(Essay, essay_id)
        if essay_to_update:
            essay_to_update.status = 'error_correction'
            essay_to_update.error_message = f"AI校对时发生未知错误: {str(e)[:500]}"
            essay_to_update.content = essay.original_ocr_text # Revert content to original
            db.session.commit()
        current_app.logger.error(f"An unknown error occurred during AI correction for essay {essay_id}: {e}", exc_info=True) 
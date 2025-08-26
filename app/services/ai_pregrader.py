"""
AI Pre-grader service for generating enhanced essay analysis data.
Provides outline, diagnostics, exercises, summary and diagnosis information.
"""
import requests
import json
import logging
from flask import current_app
from typing import Dict, Any, Optional
from app.services.grading_utils import format_grading_standard_for_prompt
from app.llm.provider import get_llm_provider, LLMConnectionError

logger = logging.getLogger(__name__)


class AIPregraderError(Exception):
    """Custom exception for AI Pre-grader related errors."""
    pass


def generate_preanalysis(essay_text: str, cleaned_text: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Generate pre-analysis data including outline, diagnostics, exercises, summary and diagnosis.
    
    Args:
        essay_text: Original essay text
        cleaned_text: AI-corrected text (optional)
        context: Additional context like topic, grade, etc. (optional)
        
    Returns:
        Dictionary with analysis, diagnostics, exercises, summary, diagnosis
        
    Raises:
        AIPregraderError: If there's an issue with the AI service API call
    """
    if not essay_text or not essay_text.strip():
        return _get_empty_preanalysis()
    
    try:
        # Use cleaned text if available, otherwise use original
        text_to_analyze = cleaned_text if cleaned_text and cleaned_text.strip() else essay_text
        
        # Build prompt for comprehensive analysis with system instruction
        prompt = _build_analysis_prompt(text_to_analyze, context or {})
        system_prompt = "你是一位经验丰富的中文作文教师，擅长分析学生作文并提供有针对性的指导建议。请严格按照JSON格式返回分析结果。\n\n" + prompt
        
        logger.debug(f"Sending pre-analysis request to LLM API with retry logic")
        
        # Use LLMProvider for automatic retry logic
        provider = get_llm_provider()
        analysis_data = provider.call_llm(
            prompt=system_prompt,
            max_retries=2,  # Allow 2 retries for network issues
            timeout=60,     # 60 second timeout per attempt
            require_json=True,
            temperature=0.3
        )
        
        # Validate and sanitize the response
        validated_data = _validate_and_sanitize_response(analysis_data)
        logger.info(f"Successfully generated pre-analysis data")
        
        return validated_data
        
    except LLMConnectionError as e:
        logger.error(f"Pre-grader API request failed due to network issue: {e}")
        return _get_empty_preanalysis()
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to parse pre-grader response: {e}")
        return _get_empty_preanalysis()
    except Exception as e:
        logger.error(f"Unexpected error in pre-grader: {e}", exc_info=True)
        return _get_empty_preanalysis()


def _build_analysis_prompt(text: str, context: Dict[str, Any]) -> str:
    """Build the comprehensive analysis prompt for the LLM."""
    
    topic = context.get('topic', '未知题目')
    grade = context.get('grade', '未知年级')
    
    # Get grading standard information if available
    grading_standard_text = ""
    has_grading_standard = False
    if 'grading_standard' in context and context['grading_standard']:
        grading_standard_text = format_grading_standard_for_prompt(context['grading_standard'])
        has_grading_standard = grading_standard_text != "没有提供评分标准。"
    
    # Build the grading standard section
    grading_standard_section = ""
    if has_grading_standard:
        grading_standard_section = f"""
## 评分标准
请在分析过程中参考以下评分标准，确保你的诊断和建议与实际评分标准保持一致：

{grading_standard_text}

"""
    
    # Adjust diagnostic and exercise instructions based on whether we have grading standards
    diagnostic_instruction = ""
    exercise_instruction = ""
    summary_instruction = ""
    diagnosis_instruction = ""
    
    if has_grading_standard:
        diagnostic_instruction = "- 重要：请结合上述评分标准中的维度和评分要求进行分析"
        exercise_instruction = "- 重要：练习应该针对评分标准中的具体维度进行设计"
        summary_instruction = "- 重要：评价应该基于评分标准的各个维度"
        diagnosis_instruction = "- 重要：问题诊断和改进建议应该与评分标准相对应"
    
    prompt = f"""
请对以下学生作文进行全面分析，并严格按照JSON格式返回结果。

## 作文信息
- 题目：{topic}
- 年级：{grade}
{grading_standard_section}
## 作文内容
{text}

## 分析要求
请从以下四个维度进行分析，并返回严格的JSON格式结果：

### 1. 段落结构分析 (analysis.outline)
- 将作文按自然段落进行分析
- 为每个段落标注写作意图和作用
- 格式：[{{"para": 段落编号, "intent": "该段落的写作意图"}}]

### 2. 问题诊断 (diagnostics)  
- 识别作文中的具体问题
- 提供问题证据和改进建议
{diagnostic_instruction}
- 格式：[{{"para": 段落编号或null, "issue": "问题类型", "evidence": "问题证据", "advice": ["改进建议1", "改进建议2"]}}]

### 3. 个性化练习 (exercises)
- 根据发现的问题设计针对性练习
- 提供练习要点和示例
{exercise_instruction}
- 格式：[{{"type": "练习类型", "prompt": "练习要求", "hint": ["要点1", "要点2"], "sample": "示例内容"}}]

### 4. 综合评价 (summary)
- 面向家长和教师的作文总体评价
- 简明扼要，突出优点和改进方向
{summary_instruction}
- 格式：字符串

### 5. 诊断反馈 (diagnosis)
- before: 主要问题描述
- comment: 具体改进建议  
- after: 改进后的预期效果
{diagnosis_instruction}
- 格式：{{"before": "问题描述", "comment": "改进建议", "after": "预期效果"}}

## 返回格式
请严格按照以下JSON格式返回，不要包含任何额外的文本或Markdown标记：

{{
  "analysis": {{
    "outline": [
      {{"para": 1, "intent": "开篇点题，介绍主题"}},
      {{"para": 2, "intent": "具体描述，展开论述"}}
    ]
  }},
  "diagnostics": [
    {{"para": 2, "issue": "描写不够具体", "evidence": "缺乏细节描写", "advice": ["增加感官描写", "补充具体事例"]}}
  ],
  "exercises": [
    {{"type": "细节描写训练", "prompt": "请围绕某个场景写150字细节描写", "hint": ["运用五感", "使用比喻"], "sample": "示例内容"}}
  ],
  "summary": "整体结构清晰，内容真实感人，建议在细节描写和语言表达上进一步提升。",
  "diagnosis": {{
    "before": "作文结构基本合理，但细节描写不够生动",
    "comment": "建议多运用感官描写，让文章更加生动具体",
    "after": "通过增加细节描写，文章将更加生动感人"
  }}
}}
"""
    
    return prompt


def _validate_and_sanitize_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and sanitize the LLM response to ensure it has the expected structure."""
    
    result = {
        "analysis": {"outline": []},
        "diagnostics": [],
        "exercises": [],
        "summary": "",
        "diagnosis": {}
    }
    
    if not isinstance(data, dict):
        return result
    
    # Validate analysis.outline
    analysis = data.get("analysis", {})
    if isinstance(analysis, dict) and "outline" in analysis:
        outline = analysis["outline"]
        if isinstance(outline, list):
            validated_outline = []
            for item in outline:
                if isinstance(item, dict) and "para" in item and "intent" in item:
                    try:
                        validated_outline.append({
                            "para": int(item["para"]),
                            "intent": str(item["intent"])[:200]  # Limit length
                        })
                    except (ValueError, TypeError):
                        continue
            result["analysis"]["outline"] = validated_outline
    
    # Validate diagnostics
    diagnostics = data.get("diagnostics", [])
    if isinstance(diagnostics, list):
        validated_diagnostics = []
        for item in diagnostics:
            if isinstance(item, dict) and all(k in item for k in ["issue", "evidence", "advice"]):
                para = item.get("para")
                if para is not None:
                    try:
                        para = int(para)
                    except (ValueError, TypeError):
                        para = None
                
                advice = item.get("advice", [])
                if not isinstance(advice, list):
                    advice = [str(advice)] if advice else []
                
                validated_diagnostics.append({
                    "para": para,
                    "issue": str(item["issue"])[:100],
                    "evidence": str(item["evidence"])[:200],
                    "advice": [str(a)[:100] for a in advice[:5]]  # Limit to 5 items
                })
        result["diagnostics"] = validated_diagnostics
    
    # Validate exercises
    exercises = data.get("exercises", [])
    if isinstance(exercises, list):
        validated_exercises = []
        for item in exercises:
            if isinstance(item, dict) and all(k in item for k in ["type", "prompt"]):
                hint = item.get("hint", [])
                if not isinstance(hint, list):
                    hint = [str(hint)] if hint else []
                
                validated_exercises.append({
                    "type": str(item["type"])[:50],
                    "prompt": str(item["prompt"])[:300],
                    "hint": [str(h)[:100] for h in hint[:5]],
                    "sample": str(item.get("sample", ""))[:500]
                })
        result["exercises"] = validated_exercises
    
    # Validate summary
    summary = data.get("summary", "")
    if isinstance(summary, str):
        result["summary"] = summary[:500]  # Limit length
    
    # Validate diagnosis
    diagnosis = data.get("diagnosis", {})
    if isinstance(diagnosis, dict):
        validated_diagnosis = {}
        for key in ["before", "comment", "after"]:
            if key in diagnosis:
                validated_diagnosis[key] = str(diagnosis[key])[:300]
        result["diagnosis"] = validated_diagnosis
    
    return result


def _get_empty_preanalysis() -> Dict[str, Any]:
    """Return empty pre-analysis structure for fallback scenarios."""
    return {
        "analysis": {"outline": []},
        "diagnostics": [],
        "exercises": [],
        "summary": "",
        "diagnosis": {}
    }
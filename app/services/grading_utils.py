"""
Shared utilities for grading standards formatting.
"""


def format_grading_standard_for_prompt(standard):
    """
    Formats the grading standard from DB objects into a string for AI prompts.
    
    This function can be used by both ai_grader and ai_pregrader to ensure
    consistent formatting of grading standards in prompts.
    
    Args:
        standard: GradingStandard database object
        
    Returns:
        str: Formatted grading standard text for prompt
    """
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
        prompt_lines.append("")  # Add a blank line for spacing

    return "\n".join(prompt_lines)
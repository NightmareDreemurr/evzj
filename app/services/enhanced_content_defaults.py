"""
Enhanced content fallback data generator.
Provides default enhanced evaluation content when the AI-generated content is not available.
"""

from app.schemas.evaluation import (
    EvaluationResult, Analysis, OutlineItem, DiagnosticItem, ExerciseItem, 
    Diagnosis, Meta, TextBlock, Scores
)

def create_default_enhanced_content(essay_content: str = "", student_name: str = "学生") -> EvaluationResult:
    """
    Create default enhanced evaluation content with sample data.
    This provides a structure that teachers can edit to create meaningful feedback.
    """
    
    # Analyze content to create basic outline
    paragraphs = [p.strip() for p in essay_content.split('\n') if p.strip()] if essay_content else []
    paragraph_count = len(paragraphs)
    
    # Create default outline based on paragraph count
    outline_items = []
    if paragraph_count > 0:
        outline_templates = [
            "开篇点题，简要介绍书籍背景和主要内容",
            "具体描述感兴趣的情节，并分析其意义", 
            "联系个人生活经历，分享心得体会",
            "总结全书道理，并强调实际应用",
            "深入思考与感悟，升华主题"
        ]
        
        for i in range(min(paragraph_count, 5)):
            outline_items.append(OutlineItem(
                para=i + 1,
                intent=outline_templates[i] if i < len(outline_templates) else f"第{i+1}段的写作意图"
            ))
    
    # Create default diagnostic items
    default_diagnostics = [
        DiagnosticItem(
            para=1,
            issue="内容概述不够详细",
            evidence="仅简要提及主要内容，未深入描述感兴趣部分",
            advice=[
                "扩展对书籍主要情节的描述，突出更多细节",
                "增加对感兴趣部分的详细情节叙述"
            ]
        ),
        DiagnosticItem(
            para=3,
            issue="生活经历匹配度低", 
            evidence="生活经历与书中内容关联较弱，解释简单",
            advice=[
                "选择更相关的生活经历，确保与书中主题紧密匹配",
                "详细描述经历，增强说服力和情感深度"
            ]
        ),
        DiagnosticItem(
            para=None,
            issue="语言表达口语化",
            evidence="使用口语如'一口气看完'，缺乏学术规范",
            advice=[
                "使用更客观的语言，避免口语表达",
                "增加学术术语如'象征'或'冲突'来提升严谨性"
            ]
        ),
        DiagnosticItem(
            para=None,
            issue="字数不足",
            evidence="作文总字数约300字，低于400字要求",
            advice=[
                "扩展内容，增加对书籍和心得的详细描述",
                "确保字数达到或超过400字"
            ]
        )
    ]
    
    # Create default exercise items
    default_exercises = [
        ExerciseItem(
            type="书籍内容概述练习",
            prompt="选择一本书，概述其主要内容并详细描述一个感兴趣的情节，字数不少于200字",
            hint=[
                "抓住关键情节，使用具体细节",
                "避免空泛描述，如'很好看'"
            ],
            sample="在《哈利·波特》中，哈利与伏地魔的最终对决展示了勇气与牺牲的主题。哈利举起魔杖，念出'除你武器'，象征正义战胜邪恶。"
        ),
        ExerciseItem(
            type="心得体会联系练习",
            prompt="阅读一个故事后，写一段文字联系自己的实际生活经历，确保经历与书中内容匹配，字数不少于150字",
            hint=[
                "选择相关经历，详细描述过程",
                "强调情感和教训"
            ],
            sample="读《小王子》后，我想到自己曾忽视朋友的感受，就像小王子离开玫瑰一样。我道歉并修复了友谊，学会了珍惜。"
        ),
        ExerciseItem(
            type="语言规范练习",
            prompt="改写一段口语化文字，使其更客观严谨，使用至少两个学术术语",
            hint=[
                "避免'我觉得'等主观词",
                "使用术语如'象征'或'矛盾'"
            ],
            sample="将'我觉得这本书很好看'改为'该作品通过象征手法展现了人性的复杂矛盾，具有深刻的教育意义'。"
        )
    ]
    
    # Create default diagnosis
    default_diagnosis = Diagnosis(
        before="作文基本结构完整，能够表达个人阅读感受，但在细节描述、语言规范和内容深度方面还有提升空间",
        comment="建议加强对书籍内容的详细分析，选择更贴切的生活经历进行对比，使用更规范的书面语言表达",
        after="通过有针对性的练习和指导，预期能够在作文质量上取得明显提升，特别是在内容深度和语言表达方面"
    )
    
    # Create the evaluation result
    evaluation_data = EvaluationResult(
        meta=Meta(student=student_name),
        text=TextBlock(original=essay_content, cleaned=essay_content),
        scores=Scores(total=0.0, rubrics=[]),
        highlights=[],
        diagnosis=default_diagnosis,
        analysis=Analysis(outline=outline_items, issues=[]),
        diagnostics=default_diagnostics,
        exercises=default_exercises,
        summary="本次作文分析基于基础模板生成，请教师根据实际情况调整和完善评价内容，以提供更准确的指导建议。"
    )
    
    return evaluation_data
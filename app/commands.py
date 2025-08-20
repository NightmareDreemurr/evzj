import click
import re
from .extensions import db
from app.models import GradeLevel, User, School, AdminProfile, TeacherProfile, StudentProfile, GradingStandard, Dimension, Rubric, Tag, Classroom, Enrollment, EssayAssignment, Essay, PromptStyleTemplate, PromptStyleGradeLevelDefault, PendingSubmission
from werkzeug.security import generate_password_hash
from datetime import datetime

def seed_standards():
    """Seeds grading standards from a hardcoded data structure."""
    click.echo("开始从硬编码数据植入评分标准...")

    # Define all standards in a structured Python format
    standards_data = [
        {
            "grade_key": "二上", "title": "看图写话(单图):小老鼠在干什么(语文地七)", "tags": ["观察", "叙述", "想象"], "total_score": 10, "creator_email": None,
            "dimensions": [
                {"name": "观察与叙述", "max_score": 4, "rubrics": [
                    {"level": "A", "desc": "观察仔细，****准确描述****图中老鼠的主要动作、神态、所处环境（至少2个关键细节）。叙述****完整清晰****（谁+在哪儿+做什么）。", "min": 4, "max": 4},
                    {"level": "B", "desc": "观察较仔细，能描述图中老鼠的动作和环境（至少1个关键细节）。叙述****基本完整****。", "min": 3, "max": 3},
                    {"level": "C", "desc": "观察不仔细，描述模糊或错误。叙述****不完整****（只写一两句话）。", "min": 1, "max": 2},
                ]},
                {"name": "想象与表达", "max_score": 4, "rubrics": [
                    {"level": "A", "desc": "基于图片进行****合理且有趣****的想象（如心理、原因、结果），想象部分有****1-2处具体细节****。语句****通顺连贯****，用词****准确****。", "min": 4, "max": 4},
                    {"level": "B", "desc": "有合理想象，但****不够具体或略显简单****。语句****基本通顺连贯****，用词****基本准确****。", "min": 3, "max": 3},
                    {"level": "C", "desc": "想象****不合理或完全脱离图片****。语句****不够通顺****（有1-2处小问题），或用词****不够恰当****。", "min": 2, "max": 2},
                    {"level": "D", "desc": "几乎没有想象或想象混乱。语句****不通顺、语意不清****，词不达意。", "min": 0, "max": 1},
                ]},
                {"name": "书写规范", "max_score": 2, "rubrics": [
                    {"level": "A", "desc": "字迹****较端正****，书面****整洁****。标点符号（句号、逗号）使用****基本正确****。", "min": 2, "max": 2},
                    {"level": "B", "desc": "字迹****潦草，但尚能看清****。标点符号****错误较多****或****缺失严重****。", "min": 1, "max": 1},
                ]}
            ]
        },
        {
            "grade_key": "三上", "title": "那次玩得真高兴", "tags": ["自叙", "分享类"], "total_score": 30, "creator_email": "kcalb_mengwang@kcalbmengwang.com",
            "dimensions": [
                {"name": "事件叙述清晰度", "max_score": 9, "rubrics": [
                    {"level": "A", "desc": "完整交代时间、地点、人物、活动（4要素齐全），****经过描述具体****（如玩了什么、怎么玩的）。", "min": 8, "max": 9},
                    {"level": "B", "desc": "缺1个要素（如未写时间），经过描述****较具体但缺少细节****。", "min": 6, "max": 7},
                    {"level": "C", "desc": "缺2个要素或事件模糊（如只写“我和朋友玩”），经过描述****简略、空洞****。", "min": 3, "max": 5},
                    {"level": "D", "desc": "事件叙述****混乱不清或离题****。", "min": 0, "max": 2}
                ]},
                {"name": "情感分享具体度", "max_score": 9, "rubrics": [
                    {"level": "A", "desc": "****通过2处以上具体事例/细节****（如动作“笑得前仰后合”、语言“太好玩啦！”、神态“眼睛眯成一条缝”）****生动表现“高兴”****，情感真挚。", "min": 8, "max": 9},
                    {"level": "B", "desc": "有1处具体事例/细节表现“高兴”，情感****较真实****。", "min": 6, "max": 7},
                    {"level": "C", "desc": "****空泛表达情感****（如“我很高兴”“开心极了”），****缺乏具体事例支撑****。", "min": 3, "max": 5},
                    {"level": "D", "desc": "****未表达情感****或情感与事件****矛盾****。", "min": 0, "max": 2}
                ]},
                {"name": "语言表达流畅度", "max_score": 9, "rubrics": [
                    {"level": "A", "desc": "语句****通顺流畅****，****尝试运用3个及以上积累的好词佳句****（如“兴高采烈”、“欢声笑语”）。连接词使用恰当（然后、突然、最后）。", "min": 8, "max": 9},
                    {"level": "B", "desc": "语句****较通顺****，****用词准确但平淡****（能用1-2个好词）。有简单连接词。", "min": 6, "max": 7},
                    {"level": "C", "desc": "语句****基本通顺但有2-3处小问题****（如重复、啰嗦）。词汇****较单一****。", "min": 3, "max": 5},
                    {"level": "D", "desc": "语句****不通顺、语意不清****（病句≥4处），词不达意。", "min": 0, "max": 2}
                ]},
                {"name": "规范与基本功", "max_score": 3, "rubrics": [
                    {"level": "A", "desc": "标点符号（，。！？）****使用完全正确****。字数≥250字。错别字≤2个。", "min": 3, "max": 3},
                    {"level": "B", "desc": "标点****错误≤3处****。字数220-250字。错别字3-5个。", "min": 2, "max": 2},
                    {"level": "C", "desc": "标点****错误≥4处****或****严重缺失****。字数180-220字。错别字≥6个。", "min": 1, "max": 1},
                    {"level": "D", "desc": "****几乎无标点****或****完全乱用****。字数<180字。错别字极多。", "min": 0, "max": 0}
                ]}
            ]
        },
        {
            "grade_key": "四上", "title": "推荐一个好地方", "tags": ["介绍", "说服类"], "total_score": 35, "creator_email": "kcalb_mengwang@kcalbmengwang.com",
            "dimensions": [
                {"name": "推荐理由充分性", "max_score": 15, "rubrics": [
                    {"level": "A", "desc": "推荐地明确，提供****≥3条具体理由****（景色/活动/美食/文化等），****每条理由均有细节支撑****（如“湖水清澈见底，可见鱼群穿梭”）", "min": 13, "max": 15},
                    {"level": "B", "desc": "推荐地明确，提供****2条具体理由****，其中****1-2条有细节支撑****", "min": 11, "max": 12.9},
                    {"level": "C", "desc": "推荐地明确，提供****1-2条理由但较空泛****（如“很好玩”），****无细节支撑****", "min": 9, "max": 10.9},
                    {"level": "D", "desc": "未明确推荐地或****理由与地点无关****", "min": 0, "max": 8.9}
                ]},
                {"name": "说服策略有效性", "max_score": 10, "rubrics": [
                    {"level": "A", "desc": "****成功运用≥2种说服技巧****：对比（比XX更美）、数据（占地500亩）、感官描写（花香扑鼻）、邀请性语句（“你一定不能错过”）", "min": 8, "max": 10},
                    {"level": "B", "desc": "****运用1种说服技巧****，语言具有****基本吸引力****", "min": 7, "max": 7.9},
                    {"level": "C", "desc": "****平铺直叙介绍****，无说服技巧", "min": 6, "max": 6.9},
                    {"level": "D", "desc": "语言枯燥或****劝退读者****（如“其实也没什么好看”）", "min": 0, "max": 5.9}
                ]},
                {"name": "语言与结构", "max_score": 10, "rubrics": [
                    {"level": "A", "desc": "结构清晰：****开头总起+分段理由+结尾强化****；语言流畅；****用词精准生动****（如“美不胜收”“流连忘返”）", "min": 8, "max": 10},
                    {"level": "B", "desc": "结构完整但****分段模糊****；语言通顺；用词****准确但平淡****", "min": 7, "max": 7.9},
                    {"level": "C", "desc": "结构松散（如理由混杂）；语句****基本通顺但有2-3处啰嗦****；词汇单一", "min": 6, "max": 6.9},
                    {"level": "D", "desc": "****结构混乱****；语句****不通顺或词不达意****", "min": 0, "max": 5.9}
                ]}
            ]
        },
        # Add other standards here if needed...
        {
            "grade_key": "五下", "title": "写读后感--实用-学术类设计", "tags": ["读后感", "实用类", "学术类"], "total_score": 40, "creator_email": "kcalb_mengwang@kcalbmengwang.com",
            "dimensions": [
                {
                    "name": "书籍内容概述提炼", "max_score": 20, "rubrics": [
                        {"level": "A", "desc": "能够概述这本书的主要内容，抓住自己感兴趣地方进行情节描述", "min": 16, "max": 20},
                        {"level": "B", "desc": "能大概明白这本书讲了什么内容，但是没有聚焦自己感兴趣的部分详细介绍", "min": 14, "max": 15},
                        {"level": "C", "desc": "没有讲清楚这本书的具体内容，只是停留在空泛的描述（如“这本书很好看”）", "min": 12, "max": 13},
                        {"level": "D", "desc": "未结合或完全离题", "min": 0, "max": 11}
                    ]
                },
                {
                    "name": "心得体会交流分享", "max_score": 10, "rubrics": [
                        {"level": "A", "desc": "能结合自己的实际生活经历，谈一谈阅读后的体会与感受：\\n1. 能把自己的体会和感受说清楚\\n2. 所选的经历和书中的内容相匹配\\n3. 能联系自己的实际生活经历交流，把经历说清楚", "min": 8, "max": 10},
                        {"level": "B", "desc": "有一定体会和感受，但是表述较简单；与书本内容匹配度较低；没有把自己的生活经历说清楚", "min": 7, "max": 7.5},
                        {"level": "C", "desc": "结构缺失环节（如无引用或无联系），所结合的经历空洞（“生活中也有很多这样的事”）", "min": 6, "max": 6.5},
                        {"level": "D", "desc": "无心得体会", "min": 0, "max": 5.5}
                    ]
                },
                {
                    "name": "语言表达学术规范", "max_score": 10, "rubrics": [
                        {"level": "A", "desc": "语言客观严谨（避免“我觉得”），术语准确（如“象征”“矛盾冲突”）；标点规范（书名号、引号）；字数≥400字；错字≤3个", "min": 8, "max": 10},
                        {"level": "B", "desc": "语言基本客观但偶带口语（“超好看”）；标点错误≤3处；字数350-400字；错字4-6个", "min": 7, "max": 7.5},
                        {"level": "C", "desc": "语言使用不规范，术语误用；标点错误4-5处；字数300-350字；错字7-9个", "min": 6, "max": 6.5},
                        {"level": "D", "desc": "语言完全口语化；标点混乱；字数<300字；错字≥10个", "min": 0, "max": 5.5}
                    ]
                }
            ]
        }
    ]

    grade_map = {
        '二上': '二年级上学期', '三上': '三年级上学期', '四上': '四年级上学期',
        '五下': '五年级下学期',
    }
    
    # Clean up existing standards before seeding
    # This must be done in an order that respects foreign key constraints.
    db.session.execute(db.text('DELETE FROM grading_standard_tags'))
    Rubric.query.delete()
    Dimension.query.delete()
    GradingStandard.query.delete()
    Tag.query.delete() # Deleting tags after standards and links
    db.session.commit()
    click.echo("已清除旧的评分标准、维度、等级和标签关联。")

    teacher_user = User.query.filter_by(email="kcalb_mengwang@kcalbmengwang.com").first()

    for std_data in standards_data:
        grade_name = grade_map.get(std_data["grade_key"])
        if not grade_name:
            click.echo(f"警告: 未知的年级key '{std_data['grade_key']}'", err=True)
            continue
        
        grade_level = GradeLevel.query.filter_by(name=grade_name).first()
        if not grade_level:
            click.echo(f"警告: 未在数据库中找到年级 '{grade_name}'", err=True)
            continue
            
        creator_id = teacher_user.id if std_data["creator_email"] and teacher_user else None
        
        new_standard = GradingStandard(
            title=std_data["title"],
            grade_level_id=grade_level.id,
            total_score=std_data["total_score"],
            creator_id=creator_id,
            is_active=True
        )

        for tag_name in std_data["tags"]:
            tag = Tag.query.filter_by(name=tag_name).first()
            if not tag:
                tag = Tag(name=tag_name, description="")
            new_standard.tags.append(tag)

        db.session.add(new_standard)
        db.session.flush()

        for dim_data in std_data["dimensions"]:
            new_dimension = Dimension(
                name=dim_data["name"],
                max_score=dim_data["max_score"],
                standard_id=new_standard.id
            )
            db.session.add(new_dimension)
            db.session.flush()
            
            for rubric_data in dim_data["rubrics"]:
                new_rubric = Rubric(
                    dimension_id=new_dimension.id,
                    level_name=rubric_data["level"],
                    description=rubric_data["desc"],
                    min_score=rubric_data["min"],
                    max_score=rubric_data["max"]
                )
                db.session.add(new_rubric)
    
    db.session.commit()
    click.echo(f"成功从硬编码数据植入 {len(standards_data)} 个评分标准。")


def seed_prompt_styles():
    """Seeds a universal default prompt style and several specific, non-default styles."""
    click.echo("开始植入评语风格模板...")

    # Clean up old templates first, respecting foreign key constraints
    PromptStyleGradeLevelDefault.query.delete()
    PromptStyleTemplate.query.delete()
    db.session.commit()
    click.echo("已清除旧的评语风格模板和关联。")

    all_grades = GradeLevel.query.all()
    if not all_grades:
        click.echo("警告：数据库中没有任何年级数据，无法植入评语模板。", err=True)
        return

    # --- 1. Seed the Universal, Adaptive, DEFAULT Template ---
    adaptive_style_instructions = """
你是一位专业的、适应性极强的全能型语文老师。你的核心任务是根据学生的年级，用最适合他们年龄和认知水平的语言风格，对他们的作文进行评价和指导。

**核心指令：动态调整评语风格**
这是最重要的部分！你的评语风格**必须**根据我接下来在【学生信息】中提供的具体年级，进行动态调整。

*   **对于小学低年级（一至三年级）**:
    *   **语气**: 必须像一位亲切、有耐心的大哥哥/大姐姐，充满鼓励和童趣。多用表扬和积极的词汇（例如“真棒”、“了不起”、“老师发现了一个闪光点”），少用生硬的批评。
    *   **语言**: 必须是口语化的、简单易懂的，多用孩子能理解的比喻和生活中的具体例子。
    *   **目标**: 激发写作兴趣，建立自信心，让他们觉得写作是一件快乐的事。

*   **对于小学高年级（四至六年级）**:
    *   **语气**: 必须像一位循循善诱的老师，既要肯定学生的优点，也要开始明确指出可以改进的问题。
    *   **语言**: 可以开始引入一些基础的书面语和简单的写作术语（例如“文章结构”、“细节描写”、“开头结尾”）。
    *   **目标**: 培养基本的写作规范、逻辑顺序和使用细节描写来丰富内容的能力。

*   **对于初中生**:
    *   **语气**: 必须像一位平等的探讨者和引路人，尊重学生的个人想法，引导他们进行更深度的思考。
    *   **语言**: 必须使用标准的书面语和常见的文学评论术语（例如“文章主旨”、“论点与论据”、“修辞手法”、“承上启下”）。
    *   **目标**: 锻炼学生的逻辑思辨能力、论证能力以及使文章有深度和见解。

*   **对于高中生**:
    *   **语气**: 必须像一位严谨的学术导师，评语需要精准、客观、富有启发性，能够引导学生进行批判性思考。
    *   **语言**: 必须是专业的、精炼的，能够从文学鉴赏或学术写作的角度提出有价值的见解。
    *   **目标**: 培养学生的批判性思维、独立见解和形成自己成熟的写作风格。

**所有评语都需遵循的通用原则**:
1.  **优点优先**: 无论哪个年级，评语都必须先从原文中找到一个具体的优点进行表扬。
2.  **结合原文**: 所有的评价和建议都必须有原文的词句作为依据，不能空泛地评论。
3.  **启发式提问**: 多使用开放式问题来让学生自己思考，而不是直接给出“标准答案”。
"""
    universal_template = PromptStyleTemplate(
        name="通用自适应风格",
        style_instructions=adaptive_style_instructions.strip(),
        creator_id=None
    )
    db.session.add(universal_template)
    for grade in all_grades:
        assoc = PromptStyleGradeLevelDefault(
            prompt_style_template=universal_template, 
            grade_level=grade, 
            is_default=True
        )
        db.session.add(assoc)
    click.echo("成功植入1个通用自适应模板，并将其设为所有年级的默认模板。")

    # --- 2. Seed Specific, NON-DEFAULT Templates ---
    specific_styles_data = [
        {
            "name": "小学低年级·鼓励式", 
            "grade_keys": ["一上", "一下", "二上", "二下", "三上", "三下"],
            "instructions": """你是一位非常有童心、善于鼓励的小学低年级语文老师。
你的核心任务是保护和激发学生的写作兴趣，引导他们从说到写。
- **评语重点**:
  1.  **看图写话引导**: 针对看图写话，要引导学生“仔细看图，说说图上有什么，他们在做什么，想什么？”
  2.  **句子完整性**: 表扬能写出完整句子的努力（“谁+在哪+做什么”）。如果句子不完整，要温和地提醒，例如：“如果加上‘谁’在做什么，句子就更清楚啦！”
  3.  **鼓励想象**: 对任何合理的想象都要给予大力表扬，例如：“你能想到小鸟的心情，真是一个有爱心的孩子！”
  4.  **用词表扬**: 对任何新学的、用得不错的词语都要圈出来表扬。
- **语气与语言**:
  - 必须使用儿童化的、充满鼓励和赞美的语言。
  - 多用拟人、比喻等手法，让评语本身也充满童趣。
  - 例子: “你的这个句子像一颗亮晶晶的星星，照亮了整个故事！”“老师仿佛看到了你笔下那个活泼的小兔子在纸上跳舞呢！”
"""
        },
        {
            "name": "小学高年级·引导式", 
            "grade_keys": ["四上", "四下", "五上", "五下", "六上", "六下"],
            "instructions": """你是一位循循善诱、注重方法的小学高年级语文老师。
你的核心任务是引导学生从“写清楚”到“写生动”，并建立初步的篇章结构概念。
- **评语重点**:
  1.  **叙事要素**: 引导学生关注记叙文六要素（时间、地点、人物、起因、经过、结果），检查文章是否把事情交代清楚。
  2.  **细节描写**: 引导学生运用五感（视觉、听觉、嗅觉、味觉、触觉）和动静结合等方法，把场景和过程写具体。例如：“你写了‘公园很美’，如果能写写你看到了什么颜色的花，听到了什么声音，会让读者也感觉到美哦。”
  3.  **真情实感**: 鼓励学生表达真实感受，并引导他们思考如何通过具体事件来表现情感，而不是空喊口号。
  4.  **结构意识**: 引导学生注意文章的开头和结尾，以及段落之间的划分。
- **语气与语言**:
  - 语气温和而坚定，以商量和提问的方式给出建议。
  - 开始使用“细节描写”、“结构”、“过渡”等基本术语，但需用简单的语言解释。
  - 例子: “文章的主体部分很精彩，如果结尾能总结一下自己的感受，首尾呼应，会不会更棒呢？”
"""
        },
        {
            "name": "初中·思辨式", 
            "grade_keys": ["初一上", "初一下", "初二上", "初二下", "初三上", "初三下"],
            "instructions": """你是一位注重逻辑思辨和表达深度的初中语文老师。
你的核心任务是引导学生从“记事”走向“表达思想”，并熟练运用多种表达方式。
- **评语重点**:
  1.  **中心思想**: 明确指出文章的主旨是否清晰、深刻，并引导学生思考如何通过材料来凸显中心。
  2.  **结构与逻辑**: 分析文章的篇章结构（如总分总、并列、递进），段落之间的逻辑关系是否严谨，过渡是否自然。
  3.  **论证方法**: 对于议论文，要重点分析论点是否明确，论据是否典型有力，论证过程是否合理（事实论据、道理论据的运用）。
  4.  **语言锤炼**: 引导学生关注语言的准确性和表现力，例如分析关键句子的表达效果，建议替换更精炼的词语。
- **语气与语言**:
  - 语气平等、理性，像一位与学生共同探讨问题的学长或研究者。
  - 熟练使用“主旨”、“论点”、“论据”、“结构层次”、“表达方式”等议论文和记叙文的专业术语。
  - 例子: “你的观点很有新意。为了让说服力更强，可以考虑补充一个反面论证，通过对比让观点更突出。”
"""
        },
        {
            "name": "高中·学术式", 
            "grade_keys": ["高一上", "高一下", "高二上", "高二下", "高三上", "高三下"],
            "instructions": """你是一位严谨深刻、具有学术视野和思想高度的高中语文老师/学者。
你的核心任务是引导学生形成独立的思想和成熟的写作风格，追求表达的深度和思想的锐度。
- **评语重点**:
  1.  **思想深度**: 重点评析文章的思想内涵、人文关怀和批判性思考的深度。让学生思考现象背后的本质。
  2.  **结构艺术**: 分析文章的谋篇布局之妙，如叙事视角（全知、限制）、线索设置、伏笔照应等手法的运用效果。
  3.  **风格与语言**: 鉴赏作者的语言风格（豪放、婉约、平实、犀利），分析其如何通过句式、词汇、修辞等形成独特风格。
  4.  **审美价值**: 从文学审美或哲学思辨的高度，探讨文章的价值和启发意义，提出可供深入研究的开放性问题。
- **语气与语言**:
  - 语气是专业的、精准的、富有启发性的，有时甚至是带有挑战性的，旨在激发学生的思辨热情。
  - 语言精炼、典雅，能娴熟运用文学、哲学、美学等领域的术语进行跨学科分析。
  - 例子: “本文对‘个人与时代’关系的探讨具有相当的深度。但叙述主体‘我’的形象略显单薄，若能将其置于更具体的矛盾冲突中，其内心的挣扎或许更能彰显主题的张力。你认为呢？”
"""
        }
    ]

    grade_map = {
        '一上': '一年级上学期', '一下': '一年级下学期', '二上': '二年级上学期', '二下': '二年级下学期',
        '三上': '三年级上学期', '三下': '三年级下学期', '四上': '四年级上学期', '四下': '四年级下学期',
        '五上': '五年级上学期', '五下': '五年级下学期', '六上': '六年级上学期', '六下': '六年级下学期',
        '初一上': '初一上学期', '初一下': '初一下学期', '初二上': '初二上学期', '初二下': '初二下学期',
        '初三上': '初三上学期', '初三下': '初三下学期', '高一上': '高一上学期', '高一下': '高一下学期',
        '高二上': '高二上学期', '高二下': '高二下学期', '高三上': '高三上学期', '高三下': '高三下学期'
    }

    for style_data in specific_styles_data:
        template = PromptStyleTemplate(
            name=style_data["name"],
            style_instructions=style_data["instructions"],
            creator_id=None
        )
        db.session.add(template)
        
        grade_levels_for_style = []
        for key in style_data["grade_keys"]:
            grade_name = grade_map.get(key)
            if grade_name:
                grade = GradeLevel.query.filter_by(name=grade_name).first()
                if grade:
                    grade_levels_for_style.append(grade)
        
        if not grade_levels_for_style:
            click.echo(f"警告: 模板 '{style_data['name']}' 未找到任何匹配的年级，已跳过关联。", err=True)
            continue

        for grade in grade_levels_for_style:
            assoc = PromptStyleGradeLevelDefault(
                prompt_style_template=template,
                grade_level=grade,
                is_default=False  # These are specific, non-default options
            )
            db.session.add(assoc)
            
    db.session.commit()
    click.echo(f"成功植入 {len(specific_styles_data)} 个特定的、非默认的评语模板。")


def seed_assignments():
    """Seeds a specific default assignment for demonstration purposes."""
    click.echo("开始植入默认作业...")

    # --- Configuration ---
    DEFAULT_ASSIGNMENT_TITLE = "写读后感--实用-学术类设计"
    TARGET_GRADE_NAME = "五年级下学期"
    TEACHER_EMAIL = "kcalb_mengwang@kcalbmengwang.com"

    # --- Deletion Step ---
    # To prevent duplicates, delete any existing assignment with the same title first.
    existing_assignment = EssayAssignment.query.filter_by(title=DEFAULT_ASSIGNMENT_TITLE).first()
    if existing_assignment:
        # 在删除旧作业之前，必须清理所有依赖，避免外键约束阻塞：
        # 1) 删除 AssignmentReport（1:1，assignment_id 唯一且非空）
        # 2) 清空作业与班级、作业与学生的多对多关联表
        # 3) 将该作业下所有 Essay 的 assignment_id 置为 NULL（保留作文数据）
        # 4) 删除 PendingSubmission（该表 assignment_id 非空，无法置 NULL）
        try:
            from app.models import Essay, PendingSubmission, AssignmentReport  # 局部导入，减少全局改动
            from sqlalchemy.orm.collections import InstrumentedList

            # 1) 删除 AssignmentReport（如果存在）
            report = getattr(existing_assignment, 'report', None)
            if report:
                try:
                    if isinstance(report, InstrumentedList):
                        deleted_count = 0
                        for r in list(report):
                            db.session.delete(r)
                            deleted_count += 1
                        click.echo(f"已删除旧作业的 {deleted_count} 条 AssignmentReport 记录。")
                    else:
                        db.session.delete(report)
                        click.echo("已删除旧作业的 AssignmentReport。")
                except Exception as de:
                    click.echo(f"删除旧作业报告时发生错误：{de}", err=True)
                    raise
            # 2) 清空多对多关联
            if existing_assignment.classrooms:
                existing_assignment.classrooms.clear()
                click.echo("已清空作业与班级的关联。")
            if existing_assignment.students:
                existing_assignment.students.clear()
                click.echo("已清空作业与学生的直接关联。")

            # 3) 将 Essay.assignment_id 置为 NULL（不删除作文，避免数据丢失）
            updated_essays = Essay.query.filter_by(assignment_id=existing_assignment.id).update({Essay.assignment_id: None}, synchronize_session=False)
            if updated_essays:
                click.echo(f"已将 {updated_essays} 篇作文从该作业中解除关联（assignment_id 置 NULL）。")

            # 4) 删除该作业的 PendingSubmission 记录
            deleted_pending = PendingSubmission.query.filter_by(assignment_id=existing_assignment.id).delete(synchronize_session=False)
            if deleted_pending:
                click.echo(f"已删除 {deleted_pending} 条待处理提交记录（PendingSubmission）。")

            # 先 flush 以确保上述更改落库，避免后续 delete 受约束影响
            db.session.flush()

            # 最后删除旧作业本身
            db.session.delete(existing_assignment)
            db.session.commit()
            click.echo(f"已删除旧的默认作业 '{DEFAULT_ASSIGNMENT_TITLE}'。")
        except Exception as e:
            db.session.rollback()
            click.echo(f"删除旧作业时发生错误，已回滚：{e}", err=True)
            return

    # --- Prerequisite Lookup ---
    # Find the grading standard
    grading_standard = GradingStandard.query.filter_by(title=DEFAULT_ASSIGNMENT_TITLE).first()
    if not grading_standard:
        click.echo(f"错误: 未找到标题为 '{DEFAULT_ASSIGNMENT_TITLE}' 的评分标准。跳过创建。", err=True)
        return

    # Find the teacher
    teacher_user = User.query.filter_by(email=TEACHER_EMAIL).first()
    if not teacher_user or not teacher_user.teacher_profile:
        click.echo(f"错误: 未找到教师 '{TEACHER_EMAIL}' 或其资料不完整。跳过创建。", err=True)
        return

    # Find the target classroom based on grade name
    target_grade = GradeLevel.query.filter_by(name=TARGET_GRADE_NAME).first()
    if not target_grade:
        click.echo(f"错误: 未找到年级 '{TARGET_GRADE_NAME}'。跳过创建。", err=True)
        return
        
    # Find the first classroom associated with that grade
    # Note: This logic assumes a Classroom's name contains the GradeLevel's name, e.g., "五年级(1)班"
    target_classroom = Classroom.query.filter(Classroom.class_name.like(f"%{target_grade.name.split('学期')[0]}%")).first()

    # --- Creation Step ---
    new_assignment = EssayAssignment(
        title=DEFAULT_ASSIGNMENT_TITLE,
        description="这是一个默认的示例作业，请选择一本书阅读，并撰写一篇读后感，分享你的见解与感受。",
        teacher_profile_id=teacher_user.teacher_profile.id,
        grading_standard_id=grading_standard.id,
        due_date=datetime(2099, 12, 31) # A far-future due date
    )

    if target_classroom:
        new_assignment.classrooms.append(target_classroom)
        click.echo(f"作业将被分配给班级: '{target_classroom.class_name}'。")
    else:
        click.echo(f"警告: 未找到与年级 '{TARGET_GRADE_NAME}' 关联的班级。将不会把作业分配给任何班级。", err=True)


    db.session.add(new_assignment)
    db.session.commit()
    
    click.echo(f"成功植入新的默认作业: '{DEFAULT_ASSIGNMENT_TITLE}'。")


def seed_real_students():
    """Seeds a classroom with a list of real student names."""
    click.echo("开始植入班级学生名单...")

    student_names = [
        "蔡昕达", "陈果", "陈佳怡", "邓昕来", "丁思月", "樊宇一", "费辰予", "高梓萌",
        "韩芮同", "权康雪", "金昕宇", "李承宇", "马杨焱", "马伊诺", "倪瑞辰", "浦景瑶",
        "钱雅馨", "沈乐", "沈李昕翊", "沈芷亦", "盛悦武", "石沁羽", "石翔予", "史瑞",
        "孙家宸", "王予昊", "王梓懿", "吴可昕", "徐歆玥", "徐萱涵", "徐予梵", "徐语辰",
        "徐梓薇", "严俊杰", "严书涵", "姚梓萱", "翟旖沺", "张茗彧", "张翊轩", "郑易辰",
        "周末", "周佑安", "朱昕懿", "左子恒", "吴彦霖"
    ]

    # Find the default classroom
    default_classroom_name = "默认班级"
    classroom = Classroom.query.filter_by(class_name=default_classroom_name).first()

    if not classroom:
        click.echo(f"错误: 未找到 '{default_classroom_name}'。请先运行 'flask seed' 命令创建默认班级。", err=True)
        return

    # Find the last student number to continue from there
    last_enrollment = Enrollment.query.order_by(Enrollment.student_number.desc()).first()
    start_student_number = 1
    if last_enrollment and last_enrollment.student_number and last_enrollment.student_number.isdigit():
        start_student_number = int(last_enrollment.student_number) + 1

    # Find last user to continue numbering
    last_student_user = User.query.filter(User.username.like('student%')).order_by(User.id.desc()).first()
    start_user_index = 1
    if last_student_user:
        match = re.search(r'student(\d+)', last_student_user.username)
        if match:
            start_user_index = int(match.group(1)) + 1

    count = 0
    for i, name in enumerate(student_names, start=start_user_index):
        user_index = i
        email = f"student{user_index}@example.com"
        
        if User.query.filter_by(email=email).first():
            click.echo(f"学生 {name} (邮箱: {email}) 已存在，跳过。")
            continue

        username = f"student{user_index}"
        password = "kcalb1060568661" # Default password

        user = User(
            email=email,
            username=username,
            full_name=name,
            role='student',
            password_hash=generate_password_hash(password)
        )
        user.student_profile = StudentProfile()

        student_number_str = str(2023000 + start_student_number + count)
        enrollment = Enrollment(classroom=classroom, student_number=student_number_str)
        user.student_profile.enrollments.append(enrollment)
        
        db.session.add(user)
        count += 1
    
    if count > 0:
        db.session.commit()
        click.echo(f"成功植入 {count} 名新学生到 '{default_classroom_name}'。")
    else:
        click.echo("没有新的学生需要植入。")


def register_commands(app):
    @app.cli.command("seed")
    def seed_db():
        """初始化数据库数据，包括年级、默认用户、标准和作业。"""
        # --- Seed Grade Levels, School, Classroom, Users (as before) ---
        if GradeLevel.query.first():
            click.echo("检测到已有年级数据，正在删除原有年级...")
            GradeLevel.query.delete()
            db.session.commit()
            click.echo("原有年级已删除。")

        grades = [
            '一年级上学期', '一年级下学期', '二年级上学期', '二年级下学期',
            '三年级上学期', '三年级下学期', '四年级上学期', '四年级下学期',
            '五年级上学期', '五年级下学期', '六年级上学期', '六年级下学期',
            '初一上学期', '初一下学期', '初二上学期', '初二下学期',
            '初三上学期', '初三下学期', '高一上学期', '高一下学期',
            '高二上学期', '高二下学期', '高三上学期', '高三下学期'
        ]
        for grade_name in grades:
            grade = GradeLevel(name=grade_name)
            db.session.add(grade)
        db.session.commit()
        click.echo(f"成功植入 {len(grades)} 个年级。")
        
        default_school_name = "默认学校"
        school = School.query.filter_by(name=default_school_name).first()
        if not school:
            school = School(name=default_school_name, sort_name=default_school_name)
            db.session.add(school)
            db.session.commit()
            click.echo(f"创建了默认学校: '{default_school_name}'。")

        default_classroom_name = "默认班级"
        classroom = Classroom.query.filter_by(class_name=default_classroom_name, school_id=school.id).first()
        if not classroom:
            classroom = Classroom(
                school_id=school.id, entry_year=2023, graduate_year=2029,
                class_number=1, class_name=default_classroom_name
            )
            db.session.add(classroom)
            db.session.commit()
            click.echo(f"创建了默认班级: '{default_classroom_name}'。")
        
        users_to_seed = [
            {"email": "ris@7sref.com", "username": "admin", "full_name": "リス", "role": "admin", "password": "kcalb1060568661"},
            {"email": "kcalb_mengwang@kcalbmengwang.com", "username": "teacher", "full_name": "沈鑫", "role": "teacher", "password": "kcalb1060568661"},
            {"email": "1060568661@qq.com", "username": "student", "full_name": "沈鑫", "role": "student", "password": "kcalb1060568661"}
        ]
        
        # We need to delete old users to avoid conflicts if we re-seed
        # Also delete profiles to avoid UNIQUE constraint errors
        AdminProfile.query.delete()
        TeacherProfile.query.delete()
        StudentProfile.query.delete()
        Enrollment.query.delete()
        # Explicitly clear the many-to-many association table
        db.session.execute(db.text('DELETE FROM teachers_classrooms'))
        User.query.delete()
        db.session.commit()
        click.echo("已清除旧的用户、资料和注册信息。")

        for user_data in users_to_seed:
            user = User(
                email=user_data["email"], username=user_data["username"], full_name=user_data["full_name"],
                role=user_data["role"], password_hash=generate_password_hash(user_data["password"])
            )
            if user.role == 'admin':
                user.admin_profile = AdminProfile()
            elif user.role == 'teacher':
                user.teacher_profile = TeacherProfile(school_id=school.id)
                user.teacher_profile.classrooms.append(classroom)
            elif user.role == 'student':
                user.student_profile = StudentProfile()
                enrollment = Enrollment(classroom=classroom, student_number="2023001")
                user.student_profile.enrollments.append(enrollment)
            db.session.add(user)
        db.session.commit()
        click.echo("默认用户植入完成。")

        # --- Seed Standards from Hardcoded data ---
        seed_standards()
        
        # --- Seed Prompt Styles ---
        seed_prompt_styles()
        
        # --- Seed Default Assignment ---
        seed_assignments() 

    @app.cli.command("seed-class")
    def seed_class_command():
        """Seeds the database with a class of real students."""
        seed_real_students() 

    @app.cli.command("dump-pending")
    @click.option('--assignment-id', type=int, help='Optional: Filter by a specific assignment ID.')
    def dump_pending(assignment_id):
        """Dumps the content of the PendingSubmission table to the console."""
        click.echo("Dumping content of PendingSubmission table...")
        
        query = PendingSubmission.query
        if assignment_id:
            query = query.filter_by(assignment_id=assignment_id)
            click.echo(f"Filtering for assignment_id = {assignment_id}")
        
        submissions = query.all()

        if not submissions:
            click.echo("No records found in PendingSubmission table (with the given filter).")
            return

        click.echo("=" * 40)
        for sub in submissions:
            click.echo(f"  ID: {sub.id}")
            click.echo(f"  Assignment ID: {sub.assignment_id}")
            click.echo(f"  Status: {sub.status}")
            click.echo(f"  Original Filename: {sub.original_filename}")
            click.echo(f"  File Path: {sub.file_path}")
            click.echo(f"  Matched Student ID: {sub.matched_student_id}")
            ocr_text_preview = (sub.ocr_text[:150] + '...') if sub.ocr_text and len(sub.ocr_text) > 150 else sub.ocr_text
            click.echo(f"  OCR Text: {ocr_text_preview}")
            click.echo(f"  Error Message: {sub.error_message}")
            click.echo("-" * 40)
        
        click.echo(f"\nTotal records found: {len(submissions)}")
        click.echo("=" * 40) 

    @app.cli.command("clean-pending")
    @click.option('--assignment-id', type=int, required=True, help='The assignment ID for which to delete pending submissions.')
    def clean_pending(assignment_id):
        """Deletes all PendingSubmission records for a specific assignment."""
        click.echo(f"Attempting to delete all PendingSubmission records for assignment_id = {assignment_id}...")
        
        try:
            num_deleted = PendingSubmission.query.filter_by(assignment_id=assignment_id).delete()
            db.session.commit()
            click.echo(f"Successfully deleted {num_deleted} records.")
        except Exception as e:
            db.session.rollback()
            click.echo(f"An error occurred: {e}", err=True) 

    @app.cli.command("clean-essays")
    @click.option('--assignment-id', type=int, required=True, help='The assignment ID for which to delete all confirmed essays.')
    def clean_essays(assignment_id):
        """Deletes all confirmed essays for a specific assignment."""
        essays_to_delete = Essay.query.filter_by(assignment_id=assignment_id).all()
        if not essays_to_delete:
            click.echo(f"No essays found for assignment ID {assignment_id}.")
            return

        count = len(essays_to_delete)
        # Use a raw delete for efficiency
        Essay.query.filter_by(assignment_id=assignment_id).delete(synchronize_session=False)
        db.session.commit()
        click.echo(f"Successfully deleted {count} essays for assignment ID {assignment_id}.")

    @app.cli.command("dump-essays")
    @click.argument('assignment_id', type=int)
    def dump_essays(assignment_id):
        """Dumps key information for all essays in a specific assignment."""
        import json

        essays = Essay.query.filter_by(assignment_id=assignment_id).order_by(Essay.id).all()

        if not essays:
            click.echo(f"No essays found for assignment ID: {assignment_id}")
            return

        click.echo(f"--- Dumping Essays for Assignment ID: {assignment_id} ---")
        
        for essay in essays:
            click.echo(f"\n- Essay ID: {essay.id}")
            click.echo(f"  - Status: {essay.status}")
            
            # Safely print ai_score
            ai_score_content = "Not available or empty."
            if essay.ai_score:
                try:
                    # Pretty print the JSON content
                    ai_score_content = json.dumps(essay.ai_score, ensure_ascii=False, indent=2)
                except (TypeError, json.JSONDecodeError):
                    ai_score_content = f"Invalid JSON in database: {essay.ai_score}"
            
            click.echo(f"  - AI Score Content:\n{ai_score_content}")
            click.echo("-" * 20)
"""
Test fixtures for evaluation pipeline tests.
"""

SAMPLE_ESSAY = """我的妈妈

我的妈妈是一个很好的人。她每天都很辛苦地工作，照顾我们全家。

妈妈早上很早就起床给我做早饭。她做的饭很好吃，有我爱吃的鸡蛋和面包。妈妈还要送我上学，在路上总是叮嘱我要认真听课。

妈妈下班后还要做家务。她洗衣服、打扫房间、做晚饭，很累但是从不抱怨。有时候我想帮忙，妈妈总是说让我好好学习就行了。

我觉得妈妈很伟大。她为了我们付出了很多，我看在眼里记在心里。

我爱我的妈妈。我长大后要好好孝顺她，让她过上好日子。"""

SAMPLE_META = {
    'student_id': 'test_student_123',
    'grade': '五年级',
    'topic': '我的妈妈',
    'words': len(SAMPLE_ESSAY),
    'genre': 'narrative'
}

MOCK_ANALYSIS_RESULT = {
    "outline": [
        {"para": 1, "intent": "开头点题，介绍妈妈"},
        {"para": 2, "intent": "描述妈妈早上的辛苦"},
        {"para": 3, "intent": "描述妈妈下班后的家务"},
        {"para": 4, "intent": "表达对妈妈的感激"},
        {"para": 5, "intent": "表达对妈妈的爱"}
    ],
    "issues": ["缺乏具体细节描写", "情感表达可以更深入"]
}

MOCK_SCORES_RESULT = {
    "content": 22.5,
    "structure": 16.0,
    "language": 18.0,
    "aesthetics": 10.5,
    "norms": 8.5,
    "total": 75.5,
    "rationale": "内容充实表达真挚，结构清晰层次分明，语言流畅自然，有一定文采，书写规范。"
}
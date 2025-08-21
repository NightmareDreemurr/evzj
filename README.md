# e文智教 - 重构版 (evzj_refactored)

欢迎来到 e文智教项目的重构版本！本项目旨在将原有的原型应用升级为一个健壮、可扩展、可维护的现代化 Web 应用。

---

## 核心架构升级

与原版相比，本项目的核心架构进行了以下关键升级：

1.  **数据持久化与多租户支持**:
    - 废弃了原有的内存字典 `classroom_students`。
    - 引入 **Flask-SQLAlchemy**，使用关系型数据库 (初始为 SQLite) 对所有数据进行持久化存储。
    - 新增 `School` 模型，实现了对多学校（多租户）的支持，为未来横向扩展打下基础。

2.  **动态评分标准**:
    - 将原来硬编码在 `utils/ai_utils.py` 中的 `grading_criteria` 字典彻底移除。
    - 设计了全新的 `GradingStandard`, `Dimension`, `Rubric` 数据模型，使得评分标准可以动态地在数据库中进行管理和配置，极大提高了灵活性。

3.  **现代化的应用结构**:
    - 采用 **应用工厂 (Application Factory)** 模式来创建和配置 Flask 应用。
    - 规划使用 **Flask Blueprints** 对不同功能的路由进行模块化管理。
    - 规划引入 **Celery** 作为专业的分布式任务队列，将耗时的 OCR 和 AI 任务与主应用完全解耦（待实施）。

---

## 数据库模型概览

新的数据模型结构如下：

-   `School`: 学校，顶层租户。
    -   `Classroom`: 班级，从属于一个学校。
        -   `Student`: 学生，从属于一个班级，新增了 `student_number` (学号) 字段。
            -   `Essay`: 作文，核心实体，记录了所有与单篇作文相关的信息。
                -   `ManualReview`: 人工复核记录，与 `Essay` 是一对一关系。

-   `GradingStandard`: 一套完整的评分标准。
    -   `Dimension`: 评分标准下的具体维度。
        -   `Rubric`: 维度下的具体评分等级和细则。

---

## 本地开发指南

请遵循以下步骤来启动和运行本应用：

1.  **创建并激活虚拟环境**:
    *(建议在 `evzj_refactored` 根目录下执行)*
    ```bash
    # 创建虚拟环境
    python -m venv .venv

    # 激活虚拟环境 (Windows PowerShell)
    .\.venv\Scripts\Activate.ps1
    # (macOS/Linux)
    # source .venv/bin/activate
    ```

2.  **安装依赖**:
    确保虚拟环境已激活，然后安装所有必要的 Python 包。
    ```bash
    pip install -r requirements.txt
    ```

3.  **配置 API 密钥**:
    打开 `config.py` 文件，填入你的 `DEEPSEEK_API_KEY`, `BAIDU_OCR_API_KEY` 和 `BAIDU_OCR_SECRET_KEY`。

4.  **启动应用**:
    一切就绪后，运行以下命令即可启动开发服务器。
    ```bash
    python run.py
    ```
    应用默认将运行在 `http://127.0.0.1:5001`。

---

**下一步**:
- 实施新的业务逻辑来替换旧的字典操作。
- 将 `utils` 中的函数适配新的数据库模型。
- 搭建 Celery 任务队列。
- 使用蓝图重构路由。
- 更新前端模板以适配新的数据结构。

---

## 新增功能：结构化LLM评估流水线

本项目已集成了新的结构化LLM评估流水线，替代了原有的一次性评分方式。

### 流水线架构

新的评估流水线采用以下结构化步骤：

1. **结构化解析 (analyze)**: 分析作文段落意图和问题清单
2. **动态评分标准加载 (load_standard)**: 从数据库或YAML文件加载评分标准
3. **多维度评分 (score)**: 基于标准和分析结果进行评分
4. **内容合规审核 (moderate)**: 内容安全和合规检查
5. **结果装配 (assemble)**: 组装统一的JSON输出格式

### JSON输出格式

评估结果采用统一的JSON格式：

```json
{
  "meta": {
    "student_id": "学生ID",
    "grade": "五年级", 
    "topic": "作文题目",
    "words": 字数统计
  },
  "analysis": {
    "outline": [
      {"para": 1, "intent": "段落意图描述"}
    ],
    "issues": ["问题清单"]
  },
  "scores": {
    "content": 内容分,
    "structure": 结构分,
    "language": 语言分,
    "aesthetics": 文采分,
    "norms": 规范分,
    "total": 总分,
    "rationale": "评分理由"
  },
  "diagnostics": [
    {
      "para": 段落号,
      "issue": "问题类型",
      "evidence": "问题证据", 
      "advice": ["改进建议"]
    }
  ],
  "exercises": [
    {
      "type": "练习类型",
      "prompt": "练习提示",
      "hint": ["练习要点"],
      "sample": "示例"
    }
  ],
  "summary": "给家长的总结"
}
```

### 开发命令

项目提供了便捷的开发命令：

```bash
# 安装依赖
make install

# 启动开发服务器
make dev

# 运行测试
make test

# 初始化数据库
make seed

# 清理临时文件
make clean
```

### 报告生成

支持从新的JSON格式生成Word/DOCX和文本报告：

```bash
# 生成作文评估报告（DOCX格式，默认）
python regenerate_report.py --essay-id <essay_id> --format docx --output <output_path>

# 生成作文评估报告（文本格式）
python regenerate_report.py --essay-id <essay_id> --format txt --output <output_path>

# 生成作业整体报告（向后兼容）
python regenerate_report.py --assignment <assignment_id>
```

**新特性说明：**
- **DOCX默认格式**: 使用`python-docx`生成格式化的Word文档，包含标题、分段、加粗等样式
- **CLI增强**: 支持`--essay-id`、`--format`和`--output`参数
- **向后兼容**: 保持原有`--assignment`参数的支持

### 智能元数据解析

系统现在自动从数据库解析作文元数据，无需硬编码：

**元数据来源：**
- **年级**: 从作业的评分标准→年级等级表获取
- **文体**: 从评分标准标题智能识别（记叙文、说明文、议论文）
- **题目**: 从作业标题获取
- **字数**: 使用智能中文字数统计

**中文字数统计特性：**
- 准确识别CJK字符（中日韩字符）
- 混合中英文本的词数统计  
- 自动处理标点符号和空白字符

### LLM提供器优化

评估流水线针对不同步骤进行了专门优化：

- **分析步骤**: 温度0.2，超时20秒，1次重试
- **评分步骤**: 温度0.1，超时30秒，2次重试
- **JSON验证**: 严格的JSON格式验证和错误重试

### 评分标准管理

评分标准支持数据库动态加载和YAML文件回退：

- 数据库优先：从`GradingStandard`、`Dimension`、`Rubric`表加载
- YAML回退：从`data/standards/`目录加载（如`grade5_narrative.yaml`）

### 测试覆盖

项目包含完整的测试套件（30个测试用例）：

- **评估流水线测试**: 分析、评分、组装等核心组件测试
- **元数据解析测试**: 数据库驱动的年级/文体解析测试  
- **文本统计测试**: 中文字数统计和综合文本分析测试
- **JSON存储测试**: ai_score字段的序列化/反序列化一致性测试
- **报告生成测试**: DOCX和文本格式报告生成测试
- **标准数据访问测试**: 评分标准的数据库和YAML回退测试
- **端到端集成测试**: 完整评估流程测试
- **DOCX导出测试**: 网页端DOCX报告下载功能测试

---

## DOCX 导出功能

本项目支持将作文评估报告导出为 DOCX 格式文档，方便教师下载和分享评估结果。

### 功能特性

- **单篇作文导出**: 为每篇作文生成包含详细评估信息的 DOCX 文档
- **作业汇总导出**: 为整个作业生成汇总报告（当前版本导出代表作文）
- **模板自动生成**: 首次使用时自动创建最小报告模板
- **兼容性处理**: 自动处理历史评分数据格式差异
- **文件名优化**: 自动处理特殊字符，确保文件名合法性

### 依赖安装

确保已安装必要的依赖包：

```bash
pip install python-docx==1.1.2 docxtpl==0.16.7
```

### 使用方法

#### 网页端下载

1. **作业报告页面**: 
   - 访问作业报告页面
   - 点击"下载 DOCX 报告"按钮获取作业汇总报告

2. **单篇作文导出**:
   - 在作业报告页面的作文示例中
   - 点击每篇作文旁的下载按钮获取单篇作文报告

#### API 接口

```python
# 下载单篇作文报告
GET /assignments/essays/<essay_id>/report/download

# 下载作业汇总报告  
GET /assignments/<assignment_id>/report/download
```

### 报告内容

生成的 DOCX 报告包含以下内容：

1. **基本信息**
   - 学生姓名、班级、教师、日期
   - 作文题目和字数统计

2. **评分结果**
   - 总分和各维度评分详情
   - 评分理由和权重信息

3. **文本内容**
   - 作文原文
   - 清洗后文本（如有AI校对）

4. **高亮摘要**
   - 按类型（语法、拼写、风格等）分组的问题统计
   - 严重程度分类和示例展示

5. **诊断建议**
   - 问题诊断和改进建议
   - 针对性的写作指导

### 模板自定义

#### 自动生成模板

首次运行时，系统会在 `templates/word/ReportTemplate.docx` 自动生成最小模板。

#### 自定义模板

1. 编辑 `templates/word/ReportTemplate.docx` 文件
2. 使用以下模板变量：

```jinja2
{{ meta.student }}          # 学生姓名
{{ meta.class_ }}           # 班级名称  
{{ meta.teacher }}          # 教师姓名
{{ meta.topic }}            # 作文题目
{{ meta.date }}             # 评估日期
{{ scores.total }}          # 总分
{{ text.original }}         # 原文内容
{{ text.cleaned }}          # 清洗后文本
{% for r in scores.rubrics %}{{ r.name }}: {{ r.score }}/{{ r.max }}{% endfor %}
```

#### 高级模板功能（需要 docxtpl）

如果安装了 `docxtpl==0.16.7`，可以使用更强大的模板功能：

```jinja2
# 循环显示评分维度
{% for rubric in scores.rubrics %}
{{ rubric.name }}: {{ rubric.score }}/{{ rubric.max }} (权重{{ rubric.weight }})
理由：{{ rubric.reason }}
{% endfor %}

# 高亮摘要统计
{% for type, data in highlight_summary.items %}
{{ type }}问题: 低{{ data.low }}个, 中{{ data.medium }}个, 高{{ data.high }}个
示例: {{ data.examples|join(', ') }}
{% endfor %}
```

### 故障排除

#### 常见问题

1. **模板文件丢失**: 系统会自动重新生成最小模板
2. **历史数据兼容**: DAO层自动处理不同格式的评分数据
3. **字体问题**: Linux环境建议安装中文字体（如思源黑体）

#### 错误处理

- 评估数据缺失时会提供友好的错误提示
- 文件生成失败时会回退到安全的默认处理
- 网络或权限问题会显示具体的错误信息

#### 调试建议

```bash
# 检查DOCX生成功能
python -c "from app.reporting.docx_renderer import render_essay_docx; print('DOCX功能可用')"

# 运行DOCX相关测试
pytest tests/test_docx_renderer.py -v

# 检查模板生成
python -c "from app.reporting.docx_renderer import ensure_template_exists; print(ensure_template_exists())"
```

运行 `make test` 查看完整测试结果。 
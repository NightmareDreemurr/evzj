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

支持从新的JSON格式生成Word报告：

```bash
# 生成作文评估报告
python regenerate_report.py --essay <essay_id> --output <output_path>

# 生成作业整体报告（向后兼容）
python regenerate_report.py --assignment <assignment_id>
```

### 评分标准管理

评分标准支持数据库动态加载和YAML文件回退：

- 数据库优先：从`GradingStandard`、`Dimension`、`Rubric`表加载
- YAML回退：从`data/standards/`目录加载（如`grade5_narrative.yaml`）

### 测试覆盖

项目包含完整的测试套件（13个测试用例）：

- 标准数据访问测试
- 评估流水线组件测试  
- 端到端集成测试
- 报告生成测试

运行 `make test` 查看完整测试结果。 
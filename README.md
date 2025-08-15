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
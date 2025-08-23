from .extensions import db
from datetime import datetime
from flask_login import UserMixin
from sqlalchemy.ext.associationproxy import association_proxy
from werkzeug.security import generate_password_hash, check_password_hash

# --- 核心认证与身份模型 ---

class User(UserMixin, db.Model):
    """统一用户模型，系统的唯一认证入口。"""
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, comment="登录邮箱")
    username = db.Column(db.String(100), unique=True, nullable=False, comment="用户名")
    phone = db.Column(db.String(100), unique=True, nullable=True, comment="手机号")
    password_hash = db.Column(db.String(255), nullable=False, comment="哈希密码")
    role = db.Column(db.String(20), nullable=False, comment="角色: 'admin', 'teacher', 'student'")
    full_name = db.Column(db.String(100), nullable=False)
    nickname = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关系: 记录用户创建的评分标准
    created_standards = db.relationship('GradingStandard', back_populates='creator', lazy='dynamic')

    # 与各个 Profile 表的一对一关系
    admin_profile = db.relationship('AdminProfile', back_populates='user', uselist=False, cascade="all, delete-orphan")
    teacher_profile = db.relationship('TeacherProfile', back_populates='user', uselist=False, cascade="all, delete-orphan")
    student_profile = db.relationship('StudentProfile', back_populates='user', uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<User {self.email}>'

class AdminProfile(db.Model):
    """管理员资料"""
    __tablename__ = 'admin_profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    user = db.relationship('User', back_populates='admin_profile')

class TeacherProfile(db.Model):
    """教师资料"""
    __tablename__ = 'teacher_profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    
    # 教师与学校是多对一
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    school = db.relationship('School', back_populates='teachers')

    # 教师可教授多个班级 (多对多)
    classrooms = db.relationship('Classroom', secondary='teachers_classrooms', back_populates='teachers')
    # 教师可使用多套评分标准 (多对多)
    available_standards = db.relationship('GradingStandard', secondary='teachers_grading_standards', back_populates='usable_by_teachers')
    # 教师可进行多次人工复核 (一对多)
    reviews_by = db.relationship('ManualReview', back_populates='teacher', lazy='dynamic')
    user = db.relationship('User', back_populates='teacher_profile')
    # 教师可创建多个作文作业 (一对多)
    assignments = db.relationship('EssayAssignment', back_populates='teacher')

class StudentProfile(db.Model):
    """
    学生资料模型
    - **设计目的**: 代表一个独立于任何学校的“人”。学生通过“入学”行为与学校/班级产生关联。
    """
    __tablename__ = 'student_profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    
    user = db.relationship('User', back_populates='student_profile')
    # 关系: 一个学生可以有多次“入学”记录，对应不同学校/班级
    enrollments = db.relationship('Enrollment', back_populates='student', cascade="all, delete-orphan")
    # 关系: 学生可被布置多个作业 (多对多)
    essay_assignments = db.relationship('EssayAssignment', secondary='assignment_student_profiles', back_populates='students')

    def __repr__(self):
        # 通过 self.user.full_name 获取姓名，保持数据来源唯一
        return f'<StudentProfile for User "{self.user.full_name if self.user else "N/A"}">'


# --- 组织、教学与关系模型 ---

class School(db.Model):
    """学校/机构模型"""
    __tablename__ = 'schools'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    sort_name = db.Column(db.String(150), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    classrooms = db.relationship('Classroom', back_populates='school', lazy='dynamic', cascade="all, delete-orphan")
    teachers = db.relationship('TeacherProfile', back_populates='school', lazy='dynamic', cascade="all, delete-orphan")

teachers_classrooms_association = db.Table('teachers_classrooms',
    db.Column('teacher_profile_id', db.Integer, db.ForeignKey('teacher_profiles.id'), primary_key=True),
    db.Column('classroom_id', db.Integer, db.ForeignKey('classrooms.id'), primary_key=True)
)

# 新增：作业与班级的多对多关联表
assignment_classrooms_association = db.Table('assignment_classrooms',
    db.Column('assignment_id', db.Integer, db.ForeignKey('essay_assignments.id'), primary_key=True),
    db.Column('classroom_id', db.Integer, db.ForeignKey('classrooms.id'), primary_key=True)
)

# 新增：作业与单个学生的多对多关联表
assignment_student_profiles_association = db.Table('assignment_student_profiles',
    db.Column('assignment_id', db.Integer, db.ForeignKey('essay_assignments.id'), primary_key=True),
    db.Column('student_profile_id', db.Integer, db.ForeignKey('student_profiles.id'), primary_key=True)
)

class Classroom(db.Model):
    """班级模型"""
    __tablename__ = 'classrooms'
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    entry_year = db.Column(db.Integer, nullable=False)
    graduate_year = db.Column(db.Integer, nullable=False)
    class_number = db.Column(db.Integer, nullable=False)
    class_name = db.Column(db.String(100), nullable=False)
    
    school = db.relationship('School', back_populates='classrooms')
    # 关系: 一个班级可以有多条“入学”记录
    enrollments = db.relationship('Enrollment', back_populates='classroom', cascade="all, delete-orphan")
    teachers = db.relationship('TeacherProfile', secondary=teachers_classrooms_association, back_populates='classrooms')
    # 关系: 一个班级可以被布置多个作业
    assignments = db.relationship('EssayAssignment', secondary=assignment_classrooms_association, back_populates='classrooms')

    def __repr__(self):
        return f'<Classroom {self.class_name}>'

class Enrollment(db.Model):
    """
    入学/注册模型 (新增)
    - **设计目的**: 作为学生和班级之间的核心连接，解决了学生归属多个机构的问题。
    """
    __tablename__ = 'enrollments'
    id = db.Column(db.Integer, primary_key=True)
    student_profile_id = db.Column(db.Integer, db.ForeignKey('student_profiles.id'), nullable=False)
    classroom_id = db.Column(db.Integer, db.ForeignKey('classrooms.id'), nullable=False)
    student_number = db.Column(db.String(50), nullable=True, comment="该学生在该班的学号")
    status = db.Column(db.String(50), default='active', nullable=False, comment="在读状态: active, graduated, withdrawn")
    enrollment_date = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship('StudentProfile', back_populates='enrollments')
    classroom = db.relationship('Classroom', back_populates='enrollments')
    # 关系: 一次入学可以产生多篇作文
    essays = db.relationship('Essay', back_populates='enrollment', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Enrollment student_id={self.student_profile_id} in classroom_id={self.classroom_id}>'


# --- 作文与评分模型 ---

class EssayAssignment(db.Model):
    """
    作文作业模型 (新增)
    - **设计目的**: 让教师可以创建、发布和管理作文作业。
    """
    __tablename__ = 'essay_assignments'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, comment="作业标题")
    description = db.Column(db.Text, nullable=True, comment="作业描述或要求")
    
    teacher_profile_id = db.Column(db.Integer, db.ForeignKey('teacher_profiles.id'), nullable=False, comment="出题教师ID")
    grading_standard_id = db.Column(db.Integer, db.ForeignKey('grading_standards.id'), nullable=False, comment="关联的评分标准ID")
    prompt_style_template_id = db.Column(db.Integer, db.ForeignKey('prompt_style_templates.id'), nullable=True, comment="教师指定的评语风格ID (可选)")

    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment="发布时间")
    due_date = db.Column(db.DateTime, nullable=True, comment="截止日期")

    # 关系
    teacher = db.relationship('TeacherProfile', back_populates='assignments')
    grading_standard = db.relationship('GradingStandard')
    prompt_style_template = db.relationship('PromptStyleTemplate')
    # 作业与班级的多对多关系
    classrooms = db.relationship('Classroom', secondary=assignment_classrooms_association, back_populates='assignments')
    # 新增: 作业与单个学生的直接多对多关系
    students = db.relationship('StudentProfile', secondary=assignment_student_profiles_association, back_populates='essay_assignments')
    # 作业与学生提交的作文的一对多关系
    essays = db.relationship('Essay', back_populates='assignment')

    def __repr__(self):
        return f'<EssayAssignment "{self.title}">'


class PendingSubmission(db.Model):
    """
    待处理的提交模型。
    用于临时存储上传的作业图片，跟踪其处理状态，直到教师确认为止。
    """
    __tablename__ = 'pending_submissions'
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('essay_assignments.id'), nullable=False, comment="关联的作业ID")
    uploader_id = db.Column(db.Integer, db.ForeignKey('teacher_profiles.id'), nullable=False, comment="上传者（教师）ID")

    original_filename = db.Column(db.String(255), nullable=False, comment="原始文件名")
    file_path = db.Column(db.String(255), nullable=False, unique=True, comment="文件存储路径")
    
    # 状态机，跟踪处理进度
    status = db.Column(
        db.Enum('uploaded', 'preprocessing', 'ocr_processing', 'ocr_completed', 'matching', 'match_completed', 'failed', name='submission_status_enum'),
        default='uploaded', 
        nullable=False,
        comment="处理状态"
    )
    
    ocr_text = db.Column(db.Text, nullable=True, comment="OCR识别出的文本")
    error_message = db.Column(db.Text, nullable=True, comment="处理失败时的错误信息")
    
    # AI匹配结果
    matched_student_id = db.Column(db.Integer, db.ForeignKey('student_profiles.id'), nullable=True, comment="AI匹配到的学生ID")
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关系
    assignment = db.relationship('EssayAssignment')
    uploader = db.relationship('TeacherProfile')
    matched_student = db.relationship('StudentProfile')

    def __repr__(self):
        return f'<PendingSubmission id={self.id} for Assignment id={self.assignment_id}>'


class Essay(db.Model):
    """作文模型"""
    __tablename__ = 'essays'
    id = db.Column(db.Integer, primary_key=True)
    # 核心改动：作文不再直接关联学生，而是关联到一次“入学”记录
    enrollment_id = db.Column(db.Integer, db.ForeignKey('enrollments.id'), nullable=False)
    # 新增：关联到作文作业，可以为空（代表自主练习）
    assignment_id = db.Column(db.Integer, db.ForeignKey('essay_assignments.id'), nullable=True, comment="关联的作业ID")
    # 注意：此评分标准ID仅用于“自主练习”的作文。
    # 如果作文档属于某个作业(assignment_id不为空)，则应以作业的评分标准为准(essay.assignment.grading_standard)。
    grading_standard_id = db.Column(db.Integer, db.ForeignKey('grading_standards.id'), nullable=True, comment="自主练习时使用的评分标准ID")
    
    content = db.Column(db.Text, nullable=True, comment="最终用于评分的文本（可能经过AI校对）")
    teacher_corrected_text = db.Column(db.Text, nullable=True, comment="教师手动校对后的文本")
    original_ocr_text = db.Column(db.Text, nullable=True, comment="来自OCR的原始识别文本")
    is_from_ocr = db.Column(db.Boolean, default=False, nullable=False, comment="内容是否来自OCR识别")
    original_image_path = db.Column(db.String(255), nullable=True, comment="如果来自OCR，原始图片的存储路径")
    annotated_overlay_path = db.Column(db.String(255), nullable=True, comment="圈画叠加层图片路径")

    # Scoring
    ai_score = db.Column(db.JSON, nullable=True, comment="AI原始评分和评语")
    ai_evaluation = db.Column(db.JSON, nullable=True, comment="AI增强评估结果（包含段落分析、诊断、练习等）")
    teacher_score = db.Column(db.JSON, nullable=True, comment="教师手动调整后的各维度分数")
    teacher_feedback_overrides = db.Column(db.JSON, nullable=True, comment="教师对AI评语的覆写（修改/删除）")
    final_score = db.Column(db.Float, nullable=True)

    # Status and Error tracking
    status = db.Column(db.String(50), default='pending', index=True) # e.g., pending, ocr_failed, correcting, grading, graded, error
    task_id = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    error_message = db.Column(db.Text, nullable=True)
    
    enrollment = db.relationship('Enrollment', back_populates='essays')
    assignment = db.relationship('EssayAssignment', back_populates='essays') # 新增关系
    grading_standard = db.relationship('GradingStandard')
    manual_review = db.relationship('ManualReview', back_populates='essay', uselist=False, cascade="all, delete-orphan")

    # Association proxy to easily get the student (User) from the essay
    student = association_proxy('enrollment', 'student.user')

    def __repr__(self):
        return f'<Essay id={self.id} for Enrollment id={self.enrollment_id}>'

class ManualReview(db.Model):
    """人工复核模型"""
    __tablename__ = 'manual_reviews'
    id = db.Column(db.Integer, primary_key=True)
    essay_id = db.Column(db.Integer, db.ForeignKey('essays.id'), unique=True, nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher_profiles.id'), nullable=False)
    
    manual_score = db.Column(db.JSON, nullable=True)
    manual_comment = db.Column(db.Text, nullable=True)
    annotated_image_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    essay = db.relationship('Essay', back_populates='manual_review')
    teacher = db.relationship('TeacherProfile', back_populates='reviews_by')

    def __repr__(self):
        return f'<ManualReview for Essay id={self.essay_id} by Teacher id={self.teacher_id}>'


# --- 动态评分标准模型 ---

class GradeLevel(db.Model):
    __tablename__ = 'grade_levels'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    is_enabled = db.Column(db.Boolean, default=False, nullable=False, comment="是否启用该年级")
    standards = db.relationship('GradingStandard', back_populates='grade_level', lazy='dynamic')
    # The M2M relationship is now handled by the PromptStyleGradeLevelDefault association object
    prompt_style_associations = db.relationship('PromptStyleGradeLevelDefault', back_populates='grade_level', cascade="all, delete-orphan", lazy='dynamic')

    def __repr__(self):
        return f'<GradeLevel {self.name}>'

# This association table is replaced by the model below to include the 'is_default' flag.
# prompt_style_grade_levels_association = db.Table('prompt_style_grade_levels',
#     db.Column('prompt_style_template_id', db.Integer, db.ForeignKey('prompt_style_templates.id'), primary_key=True),
#     db.Column('grade_level_id', db.Integer, db.ForeignKey('grade_levels.id'), primary_key=True)
# )

class PromptStyleGradeLevelDefault(db.Model):
    """Association object between PromptStyleTemplate and GradeLevel."""
    __tablename__ = 'prompt_style_grade_level_defaults'
    prompt_style_template_id = db.Column(db.Integer, db.ForeignKey('prompt_style_templates.id'), primary_key=True)
    grade_level_id = db.Column(db.Integer, db.ForeignKey('grade_levels.id'), primary_key=True)
    is_default = db.Column(db.Boolean, default=False, nullable=False, comment="Is this template the default for this grade level?")

    prompt_style_template = db.relationship('PromptStyleTemplate', back_populates='grade_level_associations')
    grade_level = db.relationship('GradeLevel', back_populates='prompt_style_associations')


class PromptStyleTemplate(db.Model):
    __tablename__ = 'prompt_style_templates'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, comment="模板名称, e.g., '小学低年级-鼓励式'")
    style_instructions = db.Column(db.Text, nullable=False, comment="核心的Prompt风格指令")
    # is_default is now stored in the PromptStyleGradeLevelDefault association object.
    # is_default = db.Column(db.Boolean, default=False, nullable=False, comment="是否为该年级的默认模板")
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, comment="创建者ID, null表示系统预设")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to the association object
    grade_level_associations = db.relationship('PromptStyleGradeLevelDefault', back_populates='prompt_style_template', cascade="all, delete-orphan")
    creator = db.relationship('User')

    def __repr__(self):
        return f'<PromptStyleTemplate "{self.name}">'


grading_standard_tags_association = db.Table('grading_standard_tags',
    db.Column('grading_standard_id', db.Integer, db.ForeignKey('grading_standards.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True)
)

teachers_grading_standards_association = db.Table('teachers_grading_standards',
    db.Column('teacher_profile_id', db.Integer, db.ForeignKey('teacher_profiles.id'), primary_key=True),
    db.Column('grading_standard_id', db.Integer, db.ForeignKey('grading_standards.id'), primary_key=True)
)

class Tag(db.Model):
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    grading_standards = db.relationship('GradingStandard', secondary=grading_standard_tags_association, back_populates='tags')

    def __repr__(self):
        return f'<Tag {self.name}>'

class GradingStandard(db.Model):
    __tablename__ = 'grading_standards'
    id = db.Column(db.Integer, primary_key=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, comment="创建者ID, null表示系统标准")
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    grade_level_id = db.Column(db.Integer, db.ForeignKey('grade_levels.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    total_score = db.Column(db.Integer, nullable=False)
    
    creator = db.relationship('User', back_populates='created_standards')
    grade_level = db.relationship('GradeLevel', back_populates='standards')
    dimensions = db.relationship('Dimension', back_populates='standard', cascade="all, delete-orphan")
    usable_by_teachers = db.relationship('TeacherProfile', secondary=teachers_grading_standards_association, back_populates='available_standards')
    tags = db.relationship('Tag', secondary=grading_standard_tags_association, back_populates='grading_standards')

    def __repr__(self):
        grade_name = self.grade_level.name if self.grade_level else "N/A"
        return f'<GradingStandard "{self.title}" for {grade_name}>'

class Dimension(db.Model):
    __tablename__ = 'dimensions'
    id = db.Column(db.Integer, primary_key=True)
    standard_id = db.Column(db.Integer, db.ForeignKey('grading_standards.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    max_score = db.Column(db.Integer, nullable=False)
    standard = db.relationship('GradingStandard', back_populates='dimensions')
    rubrics = db.relationship('Rubric', back_populates='dimension', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Dimension "{self.name}">'

class Rubric(db.Model):
    __tablename__ = 'rubrics'
    id = db.Column(db.Integer, primary_key=True)
    dimension_id = db.Column(db.Integer, db.ForeignKey('dimensions.id'), nullable=False)
    level_name = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text, nullable=False)
    min_score = db.Column(db.Float, nullable=False)
    max_score = db.Column(db.Float, nullable=False)
    dimension = db.relationship('Dimension', back_populates='rubrics')

    def __repr__(self):
        return f'<Rubric {self.level_name}>'

class AssignmentReport(db.Model):
    """作业报告模型，存储AI分析的作业整体情况"""
    __tablename__ = 'assignment_reports'
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('essay_assignments.id'), nullable=False, unique=True)
    report_data = db.Column(db.Text, nullable=False, comment="AI分析的JSON数据")
    generated_at = db.Column(db.DateTime, default=datetime.utcnow, comment="报告生成时间")
    generated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, comment="报告生成者")
    
    # 关系
    assignment = db.relationship('EssayAssignment', backref=db.backref('report', uselist=False))
    generator = db.relationship('User')
    
    def __repr__(self):
        return f'<AssignmentReport for Assignment {self.assignment_id}>'
    
    def get_report_data(self):
        """获取解析后的报告数据"""
        try:
            import json
            return json.loads(self.report_data)
        except json.JSONDecodeError:
            return {}

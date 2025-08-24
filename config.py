import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """基础配置类"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-hard-to-guess-string'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 从环境变量加载 API Keys
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL")
    DEEPSEEK_MODEL_CHAT = os.getenv("DEEPSEEK_MODEL_CHAT")
    DEEPSEEK_MODEL_REASONER = os.getenv("DEEPSEEK_MODEL_REASONER")
    BAIDU_OCR_API_KEY = os.getenv("BAIDU_OCR_API_KEY")
    BAIDU_OCR_SECRET_KEY = os.getenv("BAIDU_OCR_SECRET_KEY")
    BAIDU_OCR_TOKEN_URL = os.getenv("BAIDU_OCR_TOKEN_URL")
    BAIDU_OCR_GENERAL_URL = os.getenv("BAIDU_OCR_GENERAL_URL")

    # File Uploads
    UPLOAD_FOLDER = os.getenv('UPLOADS_DIR') or os.path.join(os.path.abspath(os.path.dirname(__file__)), 'uploads')

    # 并行处理配置
    OCR_MAX_CONCURRENCY = int(os.getenv("OCR_MAX_CONCURRENCY", 5))
    
    # Enhanced evaluation feature flags
    EVAL_PREBUILD_ENABLED = os.getenv("EVAL_PREBUILD_ENABLED", "true").lower() == "true"
    EVAL_REQUIRE_REVIEW_BEFORE_EXPORT = os.getenv("EVAL_REQUIRE_REVIEW_BEFORE_EXPORT", "false").lower() == "true"


    @staticmethod
    def init_app(app):
        pass

class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'app.db')

class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or 'sqlite://'

class ProductionConfig(Config):
    """生产环境配置"""
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'app.db')

# 注册配置名称
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
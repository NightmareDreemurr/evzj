from flask import Flask, request
from config import config
from .extensions import db, login_manager, bootstrap, moment, mail, migrate
from .models import User, GradingStandard, EssayAssignment, PromptStyleTemplate
from .decorators import admin_required
from .commands import register_commands
import os
import requests

def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv('FLASK_CONFIG', 'default')
        
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    bootstrap.init_app(app)
    moment.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)

    # Set up the login manager
    from .models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    login_manager.login_view = 'auth.login'
    login_manager.login_message = '请先登录以访问此页面。'
    login_manager.login_message_category = 'info'

    @app.before_request
    def log_request_info():
        ip = request.remote_addr
        # try:
        #     geo_response = requests.get(f"https://ipapi.co/{ip}/json/").json()
        #     country = geo_response.get('country_name', 'Unknown')
        #     city = geo_response.get('city', 'Unknown')
        #     region = f"{country} - {city}"
        # except Exception as e:
        #     region = "Unknown"
        # app.logger.info(f"Request from {ip} ({region}): {request.method} {request.url}")
        app.logger.info(f"Request from {ip} : {request.method} {request.url}")


    # Register blueprints
    from .blueprints.main import main_bp
    app.register_blueprint(main_bp)

    from .blueprints.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from .blueprints.admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    from .blueprints.standards import standards_bp
    app.register_blueprint(standards_bp, url_prefix='/standards')

    from .blueprints.assignments import assignments_bp
    app.register_blueprint(assignments_bp, url_prefix='/assignments')

    from .blueprints.students import students_bp
    app.register_blueprint(students_bp, url_prefix='/students')

    # Register CLI commands
    register_commands(app)

    # Custom template filters
    @app.template_filter('basename')
    def basename_filter(s):
        return os.path.basename(s)
    
    @app.template_filter('from_json')
    def from_json_filter(json_str):
        """将JSON字符串转换为Python对象"""
        import json
        try:
            return json.loads(json_str) if json_str else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    return app

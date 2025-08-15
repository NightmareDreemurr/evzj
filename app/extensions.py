"""
This file initializes extensions for the Flask app.
This is to prevent circular imports.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bootstrap import Bootstrap
from flask_moment import Moment
from flask_mail import Mail
from flask_migrate import Migrate

db = SQLAlchemy()
login_manager = LoginManager()
bootstrap = Bootstrap()
moment = Moment()
mail = Mail()
migrate = Migrate() 
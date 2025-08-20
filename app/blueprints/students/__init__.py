from flask import Blueprint

students_bp = Blueprint('students', __name__)

from . import routes
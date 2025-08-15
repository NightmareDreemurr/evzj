from flask import Blueprint

assignments_bp = Blueprint('assignments', __name__, url_prefix='/assignments')

from . import assignment_routes, submission_routes, api_routes

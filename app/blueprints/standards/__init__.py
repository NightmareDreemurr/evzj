from flask import Blueprint

standards_bp = Blueprint('standards', __name__, url_prefix='/standards')

from . import routes 
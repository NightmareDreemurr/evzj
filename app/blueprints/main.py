from flask import Blueprint, render_template, send_from_directory, current_app
from flask_login import login_required
import os

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@main_bp.route('/index')
@login_required
def index():
    return render_template('base.html')

@main_bp.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Safely serves files from the upload folder."""
    upload_folder = current_app.config['UPLOAD_FOLDER']
    return send_from_directory(upload_folder, filename) 
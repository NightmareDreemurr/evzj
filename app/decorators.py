from functools import wraps
from flask import abort
from flask_login import current_user

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function

def teacher_required(f):
    """
    Ensures the current user is authenticated, has the 'teacher' role,
    and has a complete teacher profile.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(403)
        if current_user.role != 'teacher':
            abort(403)
        if not hasattr(current_user, 'teacher_profile') or not current_user.teacher_profile:
            abort(403) # Or a more specific error page
        return f(*args, **kwargs)
    return decorated_function 
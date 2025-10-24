from flask import Blueprint, render_template


camera_bp = Blueprint('camera', __name__)

@camera_bp.route('/camera')
def camera_page():
    """Dedicated camera view page"""
    return render_template('camera.html')

from flask import Blueprint, render_template


logs_bp = Blueprint('logs', __name__)

@logs_bp.route('/logs')
def logs():
    return render_template('logs.html')

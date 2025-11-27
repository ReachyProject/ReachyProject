from flask import Blueprint, render_template

macro_recorder_bp = Blueprint('macro_recorader', __name__)

@macro_recorder_bp.route('/live-recorder')
def movement_recorder():
    return render_template('macro_recorder.html')

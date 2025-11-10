from flask import Blueprint, render_template

macro_recorder_bp = Blueprint('macro_recorader', __name__)

@macro_recorder_bp.route('/macro-recorder')
def movement_recorder():
    return render_template('macro_recorder.html')

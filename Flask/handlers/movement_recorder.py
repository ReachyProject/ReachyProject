from flask import Blueprint, render_template

movement_recorder_bp = Blueprint('movement_recorder', __name__)

@movement_recorder_bp.route('/snapshot-recorder')
def movement_recorder():
    return render_template('movement_recorder.html')

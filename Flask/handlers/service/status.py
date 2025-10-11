
from flask import Blueprint, jsonify
from global_variables import running_process

status_bp = Blueprint('status', __name__)

@status_bp.route('/service/status', methods=['GET'])
def service_status():
    global running_process
    if running_process and running_process.poll() is None:
        return jsonify({'running': True})
    return jsonify({'running': False})

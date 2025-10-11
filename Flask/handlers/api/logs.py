from flask import Blueprint, jsonify
from global_variables import log_lines


api_logs_bp = Blueprint('api_logs', __name__)

@api_logs_bp.route('/api/logs')
def get_logs():
    """Return the current logs"""
    return jsonify({'logs': list(log_lines)})
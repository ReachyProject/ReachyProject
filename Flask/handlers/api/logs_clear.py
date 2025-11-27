from flask import Blueprint, jsonify
from Flask.global_variables import log_lines

logs_clear_bp = Blueprint('logs_clear', __name__)

@logs_clear_bp.route('/api/logs/clear', methods=['POST'])
def clear_logs():
    """Clear all logs"""
    global log_lines
    log_lines.clear()
    return jsonify({'success': True, 'message': 'Logs cleared'})
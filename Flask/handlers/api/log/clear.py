from flask import jsonify
from global_variables import log_lines

def clear_logs():
    """Clear all logs"""
    global log_lines
    log_lines.clear()
    return jsonify({'success': True, 'message': 'Logs cleared'})

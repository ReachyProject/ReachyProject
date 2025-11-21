from flask import Blueprint, jsonify
from global_variables import log_lines


def get_logs():
    """Return the current logs"""
    return jsonify({'logs': list(log_lines)})

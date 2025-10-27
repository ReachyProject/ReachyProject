from flask import jsonify
from global_variables import tracking_process

def tracking_status():
    """Get the current status of the face tracking system"""
    if tracking_process is not None and tracking_process.poll() is None:
        return jsonify({'running': True})
    return jsonify({'running': False})

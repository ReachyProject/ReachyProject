from flask import Blueprint, Response, jsonify
from Flask.camera import CAMERA_AVAILABLE, CameraFrameProvider


camera_status_bp = Blueprint('camera_status', __name__)

@camera_status_bp.route('/api/camera/status')
def camera_status():
    """Check if camera feed is available"""
    if not CAMERA_AVAILABLE:
        return jsonify({
            'status': 'unavailable',
            'available': False,
            'message': 'Camera module not loaded'
        }), 503
    
    is_available = CameraFrameProvider.is_available()
    
    if is_available:
        _, metadata = CameraFrameProvider.get_latest_frame()
        return jsonify({
            'status': 'online',
            'available': True,
            'metadata': metadata
        })
    else:
        return jsonify({
            'status': 'offline',
            'available': False,
            'message': 'Face tracking service not running'
        }), 503

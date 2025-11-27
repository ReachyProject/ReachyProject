import platform
from flask import Blueprint, jsonify
from handlers.camera import CAMERA_AVAILABLE
from FaceTracking.Controllers.frame_publisher import CameraFrameProvider


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

        # Get platform-specific temp directory info
        temp_dir = CameraFrameProvider.get_temp_directory()

        return jsonify({
            'status': 'online',
            'available': True,
            'metadata': metadata,
            'platform': platform.system(),
            'temp_directory': str(temp_dir)
        })
    else:
        return jsonify({
            'status': 'offline',
            'available': False,
            'message': 'Face tracking service not running',
            'platform': platform.system()
        }), 503

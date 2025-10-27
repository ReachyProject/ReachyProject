import platform
from flask import jsonify
from camera import CAMERA_AVAILABLE, CameraFrameProvider

def camera_info():
    """Get information about camera frame storage location"""
    if not CAMERA_AVAILABLE:
        return jsonify({
            'available': False,
            'message': 'Camera module not loaded'
        }), 503

    temp_dir = CameraFrameProvider.get_temp_directory()
    frame_path = CameraFrameProvider.FRAME_PATH

    return jsonify({
        'platform': platform.system(),
        'temp_directory': str(temp_dir),
        'frame_path': str(frame_path),
        'frame_exists': frame_path.exists(),
        'is_available': CameraFrameProvider.is_available()
    })

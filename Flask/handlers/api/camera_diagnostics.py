from flask import Blueprint, jsonify
import time
import platform
from handlers.camera import CAMERA_AVAILABLE

try:
    from FaceTracking.Controllers.frame_publisher import CameraFrameProvider
    CAMERA_AVAILABLE = True
except ImportError:
    CameraFrameProvider = None
    CAMERA_AVAILABLE = False

camera_diagnostics_bp = Blueprint('camera_diagnostics', __name__)

@camera_diagnostics_bp.route('/api/camera/diagnostics')
def camera_diagnostics():
    """Detailed diagnostics for the camera system"""
    if not CAMERA_AVAILABLE:
        return jsonify({
            'available': False,
            'message': 'Camera module not loaded'
        })

    temp_dir = CameraFrameProvider.get_temp_directory()
    frame_path = CameraFrameProvider.FRAME_PATH
    metadata_path = CameraFrameProvider.METADATA_PATH

    diagnostics = {
        'platform': platform.system(),
        'temp_directory': str(temp_dir),
        'temp_dir_exists': temp_dir.exists(),
        'frame': {
            'path': str(frame_path),
            'exists': frame_path.exists(),
            'size_bytes': frame_path.stat().st_size if frame_path.exists() else 0,
            'last_modified': frame_path.stat().st_mtime if frame_path.exists() else None
        },
        'metadata': {
            'path': str(metadata_path),
            'exists': metadata_path.exists()
        },
        'is_available': CameraFrameProvider.is_available()
    }

    # Add frame age if available
    if frame_path.exists():
        age = time.time() - frame_path.stat().st_mtime
        diagnostics['frame']['age_seconds'] = round(age, 2)
        diagnostics['frame']['is_recent'] = age < 2.0

    return jsonify(diagnostics)
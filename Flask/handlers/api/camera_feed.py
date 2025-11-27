from flask import Blueprint, Response
import cv2 as cv
import time
from Flask.camera import CAMERA_AVAILABLE, generate_camera_frames
from Flask.global_variables import log_lines


camera_feed_bp = Blueprint('camera_feed', __name__)

@camera_feed_bp.route('/api/camera/feed')
def camera_feed():
    print(CAMERA_AVAILABLE)
    """Live MJPEG camera stream"""
    try:
        return Response(
            generate_camera_frames(),
            mimetype='multipart/x-mixed-replace; boundary=frame',
            headers={
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0',
                'Connection': 'close'
            }
        )
    except Exception as e:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Camera feed error: {str(e)}[/red]")
        return Response("Camera feed error", status=500)
    
import time
from flask import Response

from camera import generate_camera_frames
from global_variables import log_lines


def camera_feed():
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

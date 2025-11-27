from flask import Blueprint, render_template
import time
import cv2 as cv
from global_variables import log_lines


# Camera frame provider import
try:
    from FaceTracking.Controllers.frame_publisher import CameraFrameProvider
    CAMERA_AVAILABLE = True
except ImportError:
    CameraFrameProvider = None
    CAMERA_AVAILABLE = False


camera_bp = Blueprint('camera', __name__)

@camera_bp.route('/camera')
def camera_page():
    """Dedicated camera view page"""
    return render_template('camera.html')

def generate_camera_frames():
    """Generator for camera video stream with error recovery"""
    consecutive_errors = 0
    max_errors = 10
    
    while True:
        if not CAMERA_AVAILABLE:
            continue
        
        try:
            frame, _ = CameraFrameProvider.get_latest_frame()
            
            if frame is None:
                consecutive_errors += 1
                if consecutive_errors > max_errors:
                    log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Too many failed frame reads[/red]")
                    break
                continue
            
            # Reset error counter on success
            consecutive_errors = 0
            
            # Encode frame
            ret, jpeg = cv.imencode('.jpg', frame, [cv.IMWRITE_JPEG_QUALITY, 85])
            
            if not ret:
                continue
            
            frame_data = jpeg.tobytes()
            
            # Yield with proper MJPEG boundary
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n'
                   b'Content-Length: ' + str(len(frame_data)).encode() + b'\r\n'
                   b'\r\n' + frame_data + b'\r\n')
            
        except GeneratorExit:
            # Client disconnected
            break
        except Exception as e:
            consecutive_errors += 1
            if consecutive_errors > max_errors:
                log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Stream error: {str(e)}[/red]")
                break

from flask import Blueprint, Response
import cv2 as cv
import time
from camera import CAMERA_AVAILABLE, CameraFrameProvider
from global_variables import log_lines


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
    
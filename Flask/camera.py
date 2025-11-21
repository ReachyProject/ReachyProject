import time
import platform
import cv2 as cv
from pathlib import Path
import tempfile
from global_variables import log_lines


# Camera frame provider import
try:
    from FaceTracking.reachy_face_tracking import CameraFrameProvider
    CAMERA_AVAILABLE = True
except ImportError:
    CameraFrameProvider = None
    CAMERA_AVAILABLE = False


def get_camera_frame_path():
    """Get the platform-appropriate camera frame path"""
    if platform.system() == 'Windows':
        temp_dir = Path(tempfile.gettempdir()) / "reachy_frames"
    else:
        temp_dir = Path("/tmp/reachy_frames")

    return temp_dir / "reachy_camera_frame.jpg"


def generate_camera_frames():
    """Generator for camera video stream with error recovery"""
    consecutive_errors = 0
    max_errors = 10
    error_logged = False  # Add this flag

    while True:
        if not CAMERA_AVAILABLE:
            time.sleep(0.1)  # Add small delay
            continue

        try:
            frame, _ = CameraFrameProvider.get_latest_frame()

            if frame is None:
                consecutive_errors += 1

                # Only log the first error to avoid spam
                if not error_logged and consecutive_errors == 1:
                    log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]Waiting for camera frames...[/yellow]")
                    error_logged = True

                if consecutive_errors > max_errors:
                    log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Camera frame timeout[/red]")
                    break

                time.sleep(0.1)  # Wait before retrying
                continue

            # Reset error counter and flag on success
            if error_logged and consecutive_errors > 0:
                log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [green]Camera frames available[/green]")
                error_logged = False

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
            time.sleep(0.1)  # Wait before retrying

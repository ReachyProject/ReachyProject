
# Camera frame provider import
try:
    from FaceTracking.reachy_face_tracking import CameraFrameProvider
    CAMERA_AVAILABLE = True
except ImportError:
    CameraFrameProvider = None
    CAMERA_AVAILABLE = False
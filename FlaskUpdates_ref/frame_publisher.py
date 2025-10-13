"""
Frame Publisher - Publishes camera frames for external consumption
Can be used by Flask webapp or other services
"""

import cv2
import threading
import time
import json
from pathlib import Path


class CameraFrameProvider:
    """
    Shared frame provider that can be accessed by external applications.
    Uses atomic writes to prevent partial frame reads.
    """
    FRAME_PATH = Path("/tmp/reachy_camera_frame.jpg")
    FRAME_TEMP_PATH = Path("/tmp/reachy_camera_frame_temp.jpg")
    METADATA_PATH = Path("/tmp/reachy_camera_metadata.json")
    
    _frame_lock = threading.Lock()
    
    @classmethod
    def publish_frame(cls, frame, metadata=None):
        """
        Publish a frame for external consumption with atomic write
        
        Args:
            frame: OpenCV frame (BGR format)
            metadata: Optional dict with metadata about the frame
        """
        try:
            with cls._frame_lock:
                # Write to temporary file first
                success = cv2.imwrite(
                    str(cls.FRAME_TEMP_PATH), 
                    frame,
                    [cv2.IMWRITE_JPEG_QUALITY, 85]
                )
                
                if not success:
                    print("Warning: Failed to write frame")
                    return
                
                # Atomic rename (prevents reading partial files)
                cls.FRAME_TEMP_PATH.rename(cls.FRAME_PATH)
                
                # Save metadata
                if metadata is not None:
                    try:
                        # Ensure all values are JSON serializable
                        serializable_metadata = {}
                        for key, value in metadata.items():
                            if value is None:
                                serializable_metadata[key] = None
                            elif isinstance(value, (bool, int, float, str)):
                                serializable_metadata[key] = value
                            elif isinstance(value, dict):
                                # Handle nested dicts (like face_position, head_position)
                                serializable_metadata[key] = {
                                    k: float(v) if v is not None and isinstance(v, (int, float)) else v
                                    for k, v in value.items()
                                }
                            else:
                                serializable_metadata[key] = str(value)
                        
                        # Ensure required keys exist with defaults
                        serializable_metadata.setdefault('wave_detected', False)
                        serializable_metadata.setdefault('face_detected', False)
                        serializable_metadata.setdefault('tracking_state', 'unknown')
                        serializable_metadata.setdefault('antenna_mode', 'idle')
                        
                        with open(cls.METADATA_PATH, 'w') as f:
                            json.dump(serializable_metadata, f, indent=2)
                    except (TypeError, ValueError) as e:
                        print(f"Warning: Failed to serialize metadata: {e}")
                        # Try to save a minimal version
                        minimal_metadata = {
                            'timestamp': time.time(),
                            'error': 'Metadata serialization failed'
                        }
                        with open(cls.METADATA_PATH, 'w') as f:
                            json.dump(minimal_metadata, f)
                        
        except Exception as e:
            print(f"Error publishing frame: {e}")
    
    @classmethod
    def get_latest_frame(cls):
        """
        Get the latest published frame (call this from your webapp)
        
        Returns:
            (frame, metadata) tuple or (None, None) if no frame available
        """
        try:
            with cls._frame_lock:
                if not cls.FRAME_PATH.exists():
                    return None, None
                
                # Read frame
                frame = cv2.imread(str(cls.FRAME_PATH))
                
                if frame is None:
                    return None, None
                
                # Read metadata if exists
                metadata = None
                if cls.METADATA_PATH.exists():
                    with open(cls.METADATA_PATH, 'r') as f:
                        metadata = json.load(f)
                
                return frame.copy(), metadata
        except Exception as e:
            print(f"Error reading frame: {e}")
            return None, None
    
    @classmethod
    def is_available(cls):
        """
        Check if frames are being published
        
        Returns:
            bool: True if frames are available and recent
        """
        if not cls.FRAME_PATH.exists():
            return False
        
        # Check if file was modified recently (within last 2 seconds)
        try:
            mtime = cls.FRAME_PATH.stat().st_mtime
            return (time.time() - mtime) < 2.0
        except:
            return False
    
    @classmethod
    def cleanup(cls):
        """Clean up published frame files"""
        try:
            if cls.FRAME_PATH.exists():
                cls.FRAME_PATH.unlink()
            if cls.FRAME_TEMP_PATH.exists():
                cls.FRAME_TEMP_PATH.unlink()
            if cls.METADATA_PATH.exists():
                cls.METADATA_PATH.unlink()
        except Exception as e:
            print(f"Error cleaning up frames: {e}")
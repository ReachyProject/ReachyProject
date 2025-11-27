"""
Frame Publisher - Publishes camera frames for external consumption
Can be used by Flask webapp or other services
Cross-platform support for Linux and Windows
"""

import cv2
import threading
import time
import json
import tempfile
import platform
from pathlib import Path
import os

# Suppress OpenCV warnings about missing files
os.environ['OPENCV_LOG_LEVEL'] = 'ERROR'
cv2.setLogLevel(0)


class CameraFrameProvider:
    """
    Shared frame provider that can be accessed by external applications.
    Uses atomic writes to prevent partial frame reads.
    Cross-platform support for Linux and Windows.
    """

    # Use platform-appropriate temp directory
    _TEMP_DIR = Path(tempfile.gettempdir()) / "reachy_frames"

    FRAME_PATH = _TEMP_DIR / "reachy_camera_frame.jpg"
    FRAME_TEMP_PATH = _TEMP_DIR / "reachy_camera_frame_temp.jpg"
    METADATA_PATH = _TEMP_DIR / "reachy_camera_metadata.json"

    _frame_lock = threading.Lock()
    _initialized = False

    @classmethod
    def _ensure_temp_dir(cls):
        """Ensure the temp directory exists"""
        if not cls._initialized:
            try:
                cls._TEMP_DIR.mkdir(parents=True, exist_ok=True)
                cls._initialized = True
            except Exception as e:
                print(f"Warning: Failed to create temp directory: {e}")

    @classmethod
    def publish_frame(cls, frame, metadata=None):
        """
        Publish a frame for external consumption with atomic write

        Args:
            frame: OpenCV frame (BGR format)
            metadata: Optional dict with metadata about the frame
        """
        cls._ensure_temp_dir()

        try:
            with cls._frame_lock:
                # Write to a temporary file first
                success = cv2.imwrite(
                    str(cls.FRAME_TEMP_PATH),
                    frame,
                    [cv2.IMWRITE_JPEG_QUALITY, 85]
                )

                if not success:
                    print("Warning: Failed to write frame")
                    return

                # Windows-specific: Retry logic for file operations
                max_retries = 3
                retry_delay = 0.01  # 10ms

                for attempt in range(max_retries):
                    try:
                        # On Windows, delete the target first if it exists
                        if platform.system() == 'Windows' and cls.FRAME_PATH.exists():
                            try:
                                cls.FRAME_PATH.unlink()
                            except PermissionError:
                                # File is locked, wait and retry
                                if attempt < max_retries - 1:
                                    time.sleep(retry_delay)
                                    continue
                                else:
                                    # Last attempt failed, skip this frame
                                    return

                        # Atomic rename
                        cls.FRAME_TEMP_PATH.rename(cls.FRAME_PATH)
                        break  # Success!

                    except (PermissionError, OSError) as e:
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            continue
                        else:
                            # Failed after all retries, skip this frame silently
                            return

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

                        with open(cls.METADATA_PATH, 'w', encoding='utf-8') as f:
                            json.dump(serializable_metadata, f, indent=2)
                    except (TypeError, ValueError, OSError) as e:
                        # Silently ignore metadata errors
                        pass

        except Exception as e:
            # Silently ignore frame publish errors to avoid spam
            pass

    @classmethod
    def get_latest_frame(cls):
        """
        Get the latest published frame (call this from your webapp)

        Returns:
            (frame, metadata) tuple or (None, None) if no frame available
        """
        cls._ensure_temp_dir()

        try:
            with cls._frame_lock:
                if not cls.FRAME_PATH.exists():
                    return None, None

                # Read frame with error suppression and retry logic
                max_retries = 3
                retry_delay = 0.01  # 10ms
                frame = None

                # Temporarily disable OpenCV error output
                old_log_level = cv2.getLogLevel()
                cv2.setLogLevel(0)

                try:
                    for attempt in range(max_retries):
                        try:
                            frame = cv2.imread(str(cls.FRAME_PATH))
                            if frame is not None:
                                break
                        except Exception:
                            if attempt < max_retries - 1:
                                time.sleep(retry_delay)
                            continue
                finally:
                    cv2.setLogLevel(old_log_level)

                if frame is None:
                    return None, None

                # Read metadata if exists
                metadata = None
                if cls.METADATA_PATH.exists():
                    try:
                        with open(cls.METADATA_PATH, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                    except (json.JSONDecodeError, IOError, PermissionError):
                        metadata = None

                return frame.copy(), metadata
        except Exception:
            return None, None

    @classmethod
    def is_available(cls):
        """
        Check if frames are being published

        Returns:
            bool: True if frames are available and recent
        """
        cls._ensure_temp_dir()

        if not cls.FRAME_PATH.exists():
            return False

        # Check if the file was modified recently (within the last 2 seconds)
        try:
            mtime = cls.FRAME_PATH.stat().st_mtime
            return (time.time() - mtime) < 2.0
        except Exception:
            return False

    @classmethod
    def cleanup(cls):
        """Clean up published frame files"""
        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                if cls.FRAME_PATH.exists():
                    cls.FRAME_PATH.unlink()
                if cls.FRAME_TEMP_PATH.exists():
                    cls.FRAME_TEMP_PATH.unlink()
                if cls.METADATA_PATH.exists():
                    cls.METADATA_PATH.unlink()

                # Try to remove the temp directory if empty
                try:
                    if cls._TEMP_DIR.exists() and not any(cls._TEMP_DIR.iterdir()):
                        cls._TEMP_DIR.rmdir()
                except Exception:
                    pass

                break  # Success

            except (PermissionError, OSError):
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    # Failed cleanup, but don't crash
                    pass

    @classmethod
    def get_temp_directory(cls):
        """
        Get the temporary directory being used for frame storage

        Returns:
            Path: The temporary directory path
        """
        return cls._TEMP_DIR

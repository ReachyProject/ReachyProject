"""
Reachy Face Tracking Module - Standalone Service

This module runs as an independent service and publishes camera frames
that can be consumed by external applications (like your Flask webapp).

Usage:
1. Run as standalone service: python reachy_face_tracking.py
2. Import and access frames: from reachy_face_tracking import CameraFrameProvider

Your webapp can then access frames via CameraFrameProvider.get_latest_frame()
"""

import random
import cv2 as cv
import mediapipe as mp
from reachy_sdk import ReachySDK
from reachy_sdk.trajectory import goto
from reachy_sdk.trajectory.interpolation import InterpolationMode
import time
import threading
import numpy as np
from pathlib import Path
import json

# Initialize MediaPipe Face Detection
mp_face_detection = mp.solutions.face_detection
mp_drawing = mp.solutions.drawing_utils


class CameraFrameProvider:
    """
    Shared frame provider that can be accessed by external applications.
    Uses file-based sharing for simplicity and cross-process compatibility.
    """
    FRAME_PATH = Path("/tmp/reachy_camera_frame.jpg")
    METADATA_PATH = Path("/tmp/reachy_camera_metadata.json")
    
    @classmethod
    def publish_frame(cls, frame, metadata=None):
        """Publish a frame for external consumption"""
        try:
            # Save frame as JPEG
            cv.imwrite(str(cls.FRAME_PATH), frame)
            
            # Save metadata
            if metadata is not None:
                with open(cls.METADATA_PATH, 'w') as f:
                    json.dump(metadata, f)
        except Exception as e:
            print(f"Error publishing frame: {e}")
    
    @classmethod
    def get_latest_frame(cls):
        """Get the latest published frame (call this from your webapp)"""
        try:
            if not cls.FRAME_PATH.exists():
                return None, None
            
            # Read frame
            frame = cv.imread(str(cls.FRAME_PATH))
            
            # Read metadata if exists
            metadata = None
            if cls.METADATA_PATH.exists():
                with open(cls.METADATA_PATH, 'r') as f:
                    metadata = json.load(f)
            
            return frame, metadata
        except Exception as e:
            print(f"Error reading frame: {e}")
            return None, None
    
    @classmethod
    def is_available(cls):
        """Check if frames are being published"""
        if not cls.FRAME_PATH.exists():
            return False
        
        # Check if file was modified recently (within last 2 seconds)
        mtime = cls.FRAME_PATH.stat().st_mtime
        return (time.time() - mtime) < 2.0


class FaceTrackingController:
    """ROI-based tracking controller to minimize jitter and unnecessary movements"""
    def __init__(self, frame_width, frame_height):
        # Frame parameters
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.frame_center_x = frame_width / 2
        self.frame_center_y = frame_height / 2
        
        # ROI parameters (configurable)
        self.roi_width_ratio = 0.40
        self.roi_height_ratio = 0.40
        
        # Movement control
        self.last_movement_time = 0
        self.movement_interval = 0.1
        self.min_movement_threshold = 1.0
        
        # Smoothing
        self.smoothing_factor = 0.7
        self.smoothed_error_x = 0
        self.smoothed_error_y = 0
        
    def get_roi_bounds(self):
        """Calculate ROI boundaries around frame center"""
        roi_w = int(self.frame_width * self.roi_width_ratio)
        roi_h = int(self.frame_height * self.roi_height_ratio)
        
        x1 = int(self.frame_center_x - roi_w / 2)
        y1 = int(self.frame_center_y - roi_h / 2)
        x2 = int(self.frame_center_x + roi_w / 2)
        y2 = int(self.frame_center_y + roi_h / 2)
        
        return (x1, y1, x2, y2)
    
    def is_in_roi(self, face_x, face_y):
        """Check if face is within the ROI dead zone"""
        x1, y1, x2, y2 = self.get_roi_bounds()
        return x1 <= face_x <= x2 and y1 <= face_y <= y2
    
    def calculate_movement(self, face_x, face_y, current_time, movement_gain=50):
        """Calculate if movement is needed based on ROI and timing"""
        if current_time - self.last_movement_time < self.movement_interval:
            return None
        
        if self.is_in_roi(face_x, face_y):
            return None
        
        error_x = (face_x - self.frame_center_x) / self.frame_width
        error_y = (face_y - self.frame_center_y) / self.frame_height
        
        alpha = 1 - self.smoothing_factor
        self.smoothed_error_x = alpha * error_x + self.smoothing_factor * self.smoothed_error_x
        self.smoothed_error_y = alpha * error_y + self.smoothing_factor * self.smoothed_error_y
        
        pan_adjustment = -self.smoothed_error_x * movement_gain
        roll_adjustment = -self.smoothed_error_y * movement_gain
        
        movement_magnitude = np.sqrt(pan_adjustment**2 + roll_adjustment**2)
        if movement_magnitude < self.min_movement_threshold:
            return None
        
        self.last_movement_time = current_time
        
        return (pan_adjustment, roll_adjustment)
    
    def draw_debug_overlay(self, frame, face_x=None, face_y=None):
        """Draw ROI and tracking info for debugging"""
        x1, y1, x2, y2 = self.get_roi_bounds()
        cv.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        cx, cy = int(self.frame_center_x), int(self.frame_center_y)
        cv.line(frame, (cx - 20, cy), (cx + 20, cy), (255, 0, 0), 2)
        cv.line(frame, (cx, cy - 20), (cx, cy + 20), (255, 0, 0), 2)
        
        if face_x is not None and face_y is not None:
            in_roi = self.is_in_roi(face_x, face_y)
            color = (0, 255, 0) if in_roi else (0, 0, 255)
            cv.circle(frame, (int(face_x), int(face_y)), 10, color, -1)
            cv.line(frame, (cx, cy), (int(face_x), int(face_y)), color, 2)
            
            status = "IN ROI - STABLE" if in_roi else "OUT OF ROI"
            cv.putText(frame, status, (10, 30), cv.FONT_HERSHEY_SIMPLEX, 
                      0.7, color, 2)
        
        return frame


class ReachyFaceTracker:
    """Main face tracking system that runs independently"""
    
    def __init__(self, reachy_host='localhost', show_overlay=True, enable_antenna=True):
        """
        Initialize face tracker
        
        Args:
            reachy_host: Reachy SDK host address
            show_overlay: Whether to draw debug overlay on camera feed
            enable_antenna: Whether to enable antenna animations
        """
        self.reachy = ReachySDK(reachy_host)
        self.show_overlay = show_overlay
        self.enable_antenna = enable_antenna
        
        # Camera parameters
        test_img = self.reachy.left_camera.last_frame
        self.frame_height, self.frame_width = test_img.shape[:2]
        
        # Initialize tracking controller
        self.tracker = FaceTrackingController(self.frame_width, self.frame_height)
        
        # Position tracking
        self.target_pan = 0
        self.target_roll = 0
        self.target_pitch = 0
        self.current_pan = 0
        self.current_roll = 0
        self.current_pitch = 0
        self.INTERPOLATION_RATE = 0.3
        
        # Face tracking state
        self.frame_count = 0
        self.no_face_count = 0
        self.PANLEFT = True
        
        # Scanning state
        self.scanning_state = "idle"
        self.scan_count = 0
        self.MAX_SCANS = 1
        self.state_start_time = 0
        
        # Antenna control
        self.current_antenna_mode = "idle"
        if self.enable_antenna:
            self.antenna_thread_running = True
            self.antenna_thread = threading.Thread(target=self._antenna_controller, daemon=True)
            self.antenna_thread.start()
        
        # Face detection
        self.face_detection = mp_face_detection.FaceDetection(
            model_selection=1, 
            min_detection_confidence=0.9
        )
        
        # Tracking thread
        self.tracking_thread_running = False
        self.tracking_thread = None
    
    def _antenna_controller(self):
        """Background thread to control antenna movements"""
        while self.antenna_thread_running:
            try:
                if self.current_antenna_mode == "sad":
                    self.reachy.head.l_antenna.goal_position = -125
                    self.reachy.head.r_antenna.goal_position = 125
                    time.sleep(0.3)
                    self.reachy.head.l_antenna.goal_position = -120
                    self.reachy.head.r_antenna.goal_position = 120
                    
                elif self.current_antenna_mode == "tracking":
                    base_left = -15
                    base_right = 15
                    wiggle = random.uniform(-15, 15)
                    
                    self.reachy.head.l_antenna.goal_position = base_left + wiggle
                    self.reachy.head.r_antenna.goal_position = base_right - wiggle
                    time.sleep(random.uniform(0.3, 0.8))
                    
                elif self.current_antenna_mode == "idle":
                    self.reachy.head.l_antenna.goal_position = 0
                    self.reachy.head.r_antenna.goal_position = 0
                    time.sleep(0.5)
                    
                elif self.current_antenna_mode == "scanning":
                    for _ in range(2):
                        if not self.antenna_thread_running or self.current_antenna_mode != "scanning":
                            break
                        self.reachy.head.l_antenna.goal_position = -125
                        self.reachy.head.r_antenna.goal_position = 125
                        time.sleep(0.3)
                        self.reachy.head.l_antenna.goal_position = -100
                        self.reachy.head.r_antenna.goal_position = 100
                        time.sleep(0.3)
                        
                elif self.current_antenna_mode == "giving_up":
                    for pos in range(0, -21, -2):
                        if not self.antenna_thread_running or self.current_antenna_mode != "giving_up":
                            break
                        self.reachy.head.l_antenna.goal_position = -pos
                        self.reachy.head.r_antenna.goal_position = pos
                        time.sleep(0.1)
                        
            except Exception as e:
                print(f"Antenna error: {e}")
                time.sleep(0.5)
    
    def _tracking_loop(self):
        """Main tracking loop with ROI-based movement control"""
        self.current_pan = self.reachy.head.neck_yaw.present_position
        self.current_roll = self.reachy.head.neck_roll.present_position
        self.current_pitch = self.reachy.head.neck_pitch.present_position
        self.target_pan = self.current_pan
        self.target_roll = self.current_roll
        self.target_pitch = self.current_pitch
        
        while self.tracking_thread_running:
            try:
                self.frame_count += 1
                current_time = time.time()
                
                image = self.reachy.left_camera.last_frame
                if image is None:
                    continue

                image.flags.writeable = False
                image_rgb = cv.cvtColor(image, cv.COLOR_BGR2RGB)
                results = self.face_detection.process(image_rgb)
                
                face_x, face_y = None, None
                face_detected = False
                
                if results.detections:
                    # FACE DETECTED
                    face_detected = True
                    self.no_face_count = 0
                    self.scan_count = 0
                    self.scanning_state = "idle"
                    
                    if self.enable_antenna:
                        self.current_antenna_mode = "tracking"
                    
                    detection = results.detections[0]
                    bbox = detection.location_data.relative_bounding_box
                    
                    face_x = (bbox.xmin + bbox.width / 2) * self.frame_width
                    face_y = (bbox.ymin + bbox.height / 2) * self.frame_height
                    
                    movement = self.tracker.calculate_movement(
                        face_x, face_y, current_time, movement_gain=50
                    )
                    
                    if movement is not None:
                        pan_adjustment, roll_adjustment = movement
                        
                        actual_pan = self.reachy.head.neck_yaw.present_position
                        actual_roll = self.reachy.head.neck_roll.present_position
                        
                        self.target_pan = actual_pan + pan_adjustment
                        self.target_roll = actual_roll + roll_adjustment
                        self.target_pitch = 0
                    
                else:
                    # NO FACE - scanning behavior
                    self.no_face_count += 1
                    
                    if self.scanning_state == "idle":
                        if self.no_face_count >= 60:
                            self.scanning_state = "scanning"
                            self.scan_count = 0
                            self.state_start_time = current_time
                            if self.enable_antenna:
                                self.current_antenna_mode = "scanning"
                        else:
                            if self.enable_antenna:
                                self.current_antenna_mode = "idle"
                            
                    elif self.scanning_state == "scanning":
                        if self.enable_antenna:
                            self.current_antenna_mode = "scanning"
                        
                        if self.frame_count % 90 == 0:
                            self.scan_count += 1
                            
                            if self.scan_count > self.MAX_SCANS:
                                self.scanning_state = "giving_up"
                                self.state_start_time = current_time
                                if self.enable_antenna:
                                    self.current_antenna_mode = "giving_up"
                            else:
                                random_pan_magnitude = random.uniform(30, 75)
                                random_roll = random.uniform(-5, 5)
                                
                                if self.PANLEFT:
                                    random_pan = -random_pan_magnitude
                                else:
                                    random_pan = random_pan_magnitude
                                
                                self.PANLEFT = not self.PANLEFT
                                
                                self.target_pan = random_pan
                                self.target_roll = random_roll
                                self.target_pitch = 0
                                
                    elif self.scanning_state == "giving_up":
                        if current_time - self.state_start_time > 1.5:
                            self.scanning_state = "sad"
                            self.state_start_time = current_time
                            if self.enable_antenna:
                                self.current_antenna_mode = "sad"
                            
                    elif self.scanning_state == "sad":
                        if self.enable_antenna:
                            self.current_antenna_mode = "sad"
                        
                        if current_time - self.state_start_time > 2.0:
                            self.scanning_state = "looking_down"
                            self.state_start_time = current_time
                            goto(
                                goal_positions={
                                    self.reachy.head.neck_yaw: 0,
                                    self.reachy.head.neck_roll: -30,
                                    self.reachy.head.neck_pitch: 0
                                },
                                duration=0.4,
                                interpolation_mode=InterpolationMode.MINIMUM_JERK
                            )
                            
                    elif self.scanning_state == "looking_down":
                        if self.enable_antenna:
                            self.current_antenna_mode = "sad"
                        
                        if current_time - self.state_start_time > 3.0:
                            self.scanning_state = "waiting"
                            self.state_start_time = current_time
                            
                    elif self.scanning_state == "waiting":
                        if self.enable_antenna:
                            self.current_antenna_mode = "sad"
                        
                        if current_time - self.state_start_time > 2.0:
                            self.scanning_state = "scanning"
                            self.scan_count = 0
                            self.state_start_time = current_time
                            if self.enable_antenna:
                                self.current_antenna_mode = "scanning"
                            self.target_pitch = 0
                
                # Smooth interpolation
                self.current_pan += (self.target_pan - self.current_pan) * self.INTERPOLATION_RATE
                self.current_roll += (self.target_roll - self.current_roll) * self.INTERPOLATION_RATE
                
                # Send positions
                self.reachy.head.neck_yaw.goal_position = self.current_pan
                self.reachy.head.neck_roll.goal_position = self.current_roll
                self.reachy.head.neck_pitch.goal_position = self.current_pitch
                
                # Prepare frame for publishing
                display_frame = image.copy()
                if self.show_overlay:
                    display_frame = self.tracker.draw_debug_overlay(display_frame, face_x, face_y)
                
                # Publish frame with metadata
                metadata = {
                    'timestamp': current_time,
                    'face_detected': face_detected,
                    'face_position': {'x': float(face_x), 'y': float(face_y)} if face_x else None,
                    'head_position': {
                        'pan': float(self.current_pan),
                        'roll': float(self.current_roll),
                        'pitch': float(self.current_pitch)
                    },
                    'tracking_state': self.scanning_state,
                    'antenna_mode': self.current_antenna_mode
                }
                
                CameraFrameProvider.publish_frame(display_frame, metadata)
                
            except Exception as e:
                print(f"Tracking error: {e}")
                time.sleep(0.1)
    
    def start_tracking(self):
        """Start the face tracking system"""
        if self.tracking_thread is None or not self.tracking_thread.is_alive():
            # Turn on head
            print("Turning on Reachy's head...")
            self.reachy.turn_on('head')
            time.sleep(1)
            
            # Start tracking thread
            self.tracking_thread_running = True
            self.tracking_thread = threading.Thread(target=self._tracking_loop, daemon=True)
            self.tracking_thread.start()
            print("Face tracking started")
            print("Publishing frames to CameraFrameProvider")
    
    def stop_tracking(self):
        """Stop the face tracking system"""
        print("\nStopping tracking...")
        self.tracking_thread_running = False
        
        if self.tracking_thread is not None:
            self.tracking_thread.join(timeout=2)
        
        if self.enable_antenna:
            self.antenna_thread_running = False
            self.antenna_thread.join(timeout=2)
        
        self.face_detection.close()
        
        # Return to neutral
        goto(
            goal_positions={
                self.reachy.head.neck_yaw: 0,
                self.reachy.head.neck_roll: 0,
                self.reachy.head.neck_pitch: 0,
                self.reachy.head.l_antenna: 0,
                self.reachy.head.r_antenna: 0
            },
            duration=1.0,
            interpolation_mode=InterpolationMode.MINIMUM_JERK
        )
        time.sleep(1)
        
        self.reachy.turn_off_smoothly('head')
        print("Tracking stopped")


def main():
    """Run as standalone application"""
    print("="*60)
    print("Reachy Face Tracking Service")
    print("="*60)
    print("\nThis service runs independently and publishes camera frames")
    print("that can be consumed by your Flask webapp.\n")
    
    # Create tracker
    tracker = ReachyFaceTracker(
        reachy_host='localhost',
        show_overlay=True,
        enable_antenna=True
    )
    
    # Start tracking
    tracker.start_tracking()
    
    print("\nService running!")
    print("Frames available via CameraFrameProvider.get_latest_frame()")
    print("\nPress Ctrl+C to stop\n")
    
    try:
        # Keep running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        tracker.stop_tracking()
        print("Done!")


if __name__ == "__main__":
    main()

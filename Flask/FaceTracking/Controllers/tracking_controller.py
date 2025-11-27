"""
Tracking Controller - Handles camera input and face detection
Can work with webcam or Reachy camera
"""

import random
from collections import deque

import cv2 as cv
import mediapipe as mp
import numpy as np

# Initialize MediaPipe
mp_face_detection = mp.solutions.face_detection
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils


def _smooth_positions(positions, window=3):
    """Apply moving average smoothing"""
    smoothed = []
    for i in range(len(positions)):
        start = max(0, i - window // 2)
        end = min(len(positions), i + window // 2 + 1)
        avg_x = sum(p[0] for p in positions[start:end]) / (end - start)
        avg_y = sum(p[1] for p in positions[start:end]) / (end - start)
        smoothed.append((avg_x, avg_y))
    return smoothed


class WaveDetector:
    """Hand wave detection using MediaPipe Hands"""

    def __init__(self, buffer_size=30):
        self.hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5
        )

        # Track wrist positions over time
        self.wrist_positions = deque(maxlen=buffer_size)

        # Movement thresholds (relaxed for better detection)
        self.wave_threshold = 0.06
        self.vertical_threshold = 0.4
        self.min_waves = 2
        self.movement_threshold = 0.003
        self.min_wave_speed = 0.004

        # Temporal constraints (relaxed)
        self.max_wave_duration = 35
        self.min_wave_duration = 10

        # Smoothing
        self.smoothing_window = 3

    def detect_wave(self, image_rgb):
        """
        Detect waving motion in frame
        
        Args:
            image_rgb: RGB image from MediaPipe processing
            
        Returns:
            (wave_detected, hand_landmarks_list)
        """
        results = self.hands.process(image_rgb)
        wave_detected = False
        hand_landmarks_list = []

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                hand_landmarks_list.append(hand_landmarks)

                # Get wrist position (landmark 0)
                wrist = hand_landmarks.landmark[0]
                self.wrist_positions.append((wrist.x, wrist.y))

                # Check for waving motion
                if len(self.wrist_positions) >= self.min_wave_duration:
                    wave_detected = self._analyze_wave_motion()
        else:
            # Clear buffer if no hand detected
            self.wrist_positions.clear()

        return wave_detected, hand_landmarks_list

    def _analyze_wave_motion(self):
        """Analyze if the wrist movement pattern represents a wave"""
        if len(self.wrist_positions) < self.min_wave_duration:
            return False

        # Check temporal constraint
        if len(self.wrist_positions) > self.max_wave_duration:
            return False

        positions = list(self.wrist_positions)

        # Apply smoothing to reduce noise
        smoothed_positions = _smooth_positions(positions, self.smoothing_window)
        x_coords = [p[0] for p in smoothed_positions]
        y_coords = [p[1] for p in smoothed_positions]

        # Check vertical movement (should be minimal for horizontal wave)
        y_range = max(y_coords) - min(y_coords)
        if y_range > self.vertical_threshold:
            return False

        # Calculate velocities
        velocities = [abs(x_coords[i + 1] - x_coords[i]) for i in range(len(x_coords) - 1)]
        avg_velocity = sum(velocities) / len(velocities) if velocities else 0

        # Require minimum speed for wave motion
        if avg_velocity < self.min_wave_speed:
            return False

        # Detect direction changes in horizontal movement with a threshold
        direction_changes = 0
        for i in range(1, len(x_coords) - 1):
            prev_delta = x_coords[i] - x_coords[i - 1]
            next_delta = x_coords[i + 1] - x_coords[i]

            # Only count significant movements
            if abs(prev_delta) > self.movement_threshold and abs(next_delta) > self.movement_threshold:
                if prev_delta * next_delta < 0:  # Sign change
                    direction_changes += 1

        # Check total horizontal movement range
        x_range = max(x_coords) - min(x_coords)

        # Wave detected if enough horizontal movement and direction changes
        return x_range > self.wave_threshold and direction_changes >= self.min_waves

    def cleanup(self):
        """Clean up resources"""
        self.hands.close()


class ROIController:
    """ROI-based tracking controller to minimize jitter"""

    def __init__(self, frame_width, frame_height):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.frame_center_x = frame_width / 2
        self.frame_center_y = frame_height / 2

        # ROI parameters - SMALLER for quicker response
        self.roi_width_ratio = 0.40  # Reduced from 0.60
        self.roi_height_ratio = 0.35  # Reduced from 0.50

        # Movement control - FASTER response
        self.last_movement_time = 0
        self.movement_interval = 0.05  # Reduced from 0.1 for faster updates
        self.min_movement_threshold = 0.5  # Reduced from 1.0 for more sensitive

        # Smoothing - LESS smoothing for quicker response
        self.smoothing_factor = 0.5  # Reduced from 0.7
        self.smoothed_error_x = 0
        self.smoothed_error_y = 0

    def get_roi_bounds(self):
        """Calculate ROI boundaries around the frame center"""
        roi_w = int(self.frame_width * self.roi_width_ratio)
        roi_h = int(self.frame_height * self.roi_height_ratio)

        x1 = int(self.frame_center_x - roi_w / 2)
        y1 = int(self.frame_center_y - roi_h / 2)
        x2 = int(self.frame_center_x + roi_w / 2)
        y2 = int(self.frame_center_y + roi_h / 2)

        return x1, y1, x2, y2

    def is_in_roi(self, face_x, face_y):
        """Check if face is within the ROI dead zone"""
        x1, y1, x2, y2 = self.get_roi_bounds()
        return x1 <= face_x <= x2 and y1 <= face_y <= y2

    def calculate_movement(self, face_x, face_y, current_time, movement_gain=75):  # Increased from 50
        """Calculate if movement is necessary based on ROI and timing"""
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

        movement_magnitude = np.sqrt(pan_adjustment ** 2 + roll_adjustment ** 2)
        if movement_magnitude < self.min_movement_threshold:
            return None

        self.last_movement_time = current_time

        return pan_adjustment, roll_adjustment

    def draw_debug_overlay(self, frame, face_x=None, face_y=None, hand_landmarks_list=None, wave_detected=False):
        """Draw ROI, tracking info, and hand landmarks for debugging"""
        # Draw ROI
        x1, y1, x2, y2 = self.get_roi_bounds()
        cv.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # Draw center crosshair
        cx, cy = int(self.frame_center_x), int(self.frame_center_y)
        cv.line(frame, (cx - 20, cy), (cx + 20, cy), (255, 0, 0), 2)
        cv.line(frame, (cx, cy - 20), (cx, cy + 20), (255, 0, 0), 2)

        # Draw face tracking
        if face_x is not None and face_y is not None:
            in_roi = self.is_in_roi(face_x, face_y)
            color = (0, 255, 0) if in_roi else (0, 0, 255)
            cv.circle(frame, (int(face_x), int(face_y)), 10, color, -1)
            cv.line(frame, (cx, cy), (int(face_x), int(face_y)), color, 2)

            status = "IN ROI - STABLE" if in_roi else "OUT OF ROI"
            cv.putText(frame, status, (10, 30), cv.FONT_HERSHEY_SIMPLEX,
                       0.7, color, 2)

        # Draw hand landmarks
        if hand_landmarks_list:
            for hand_landmarks in hand_landmarks_list:
                mp_drawing.draw_landmarks(
                    frame,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS
                )

        # Draw wave status
        if wave_detected:
            cv.putText(frame, "WAVING!", (10, 70),
                       cv.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)

        return frame


class TrackingController:
    """Handles camera input and face detection logic"""

    def __init__(self, camera_source, show_overlay=True):
        """
        Initialize tracking controller
        
        Args:
            camera_source: Either cv2.VideoCapture object or 'reachy'
            show_overlay: Whether to draw debug overlay
        """
        self.reachy = None
        self.camera_source = camera_source
        self.show_overlay = show_overlay
        self.is_reachy_camera = (camera_source == 'reachy')

        # Get frame dimensions
        if self.is_reachy_camera:
            # Will be set later when the reachy object is provided
            self.frame_width = None
            self.frame_height = None
            self.roi_controller = None
        else:
            # Get from webcam
            test_frame = self._get_frame()
            if test_frame is not None:
                self.frame_height, self.frame_width = test_frame.shape[:2]
                self.roi_controller = ROIController(self.frame_width, self.frame_height)

        # Face detection
        self.face_detection = mp_face_detection.FaceDetection(
            model_selection=1,
            min_detection_confidence=0.9
        )

        # Hand wave detection
        self.wave_detector = WaveDetector(buffer_size=30)

        # Tracking state
        self.frame_count = 0
        self.no_face_count = 0
        self.PANLEFT = True

        # Scanning state machine
        self.scanning_state = "idle"
        self.scan_count = 0
        self.MAX_SCANS = 5
        self.state_start_time = 0

    def set_reachy_camera(self, reachy):
        """Set up Reachy camera after initialization"""
        self.reachy = reachy
        test_img = reachy.left_camera.last_frame
        self.frame_height, self.frame_width = test_img.shape[:2]
        self.roi_controller = ROIController(self.frame_width, self.frame_height)

    def _get_frame(self):
        """Get frame from the camera source"""
        if self.is_reachy_camera:
            return self.reachy.left_camera.last_frame
        else:
            ret, frame = self.camera_source.read()
            if ret:
                return frame
            return None

    def process_frame(self, current_time):
        """
        Process one frame and return tracking data
        
        Returns:
            dict with keys: frame, face_detected, face_position, wave_detected,
                           movement_command, scanning_state, antenna_mode
        """
        self.frame_count += 1

        image = self._get_frame()
        if image is None:
            return None

        # Process for face and hand detection
        image.flags.writeable = False
        image_rgb = cv.cvtColor(image, cv.COLOR_BGR2RGB)

        # Face detection
        face_results = self.face_detection.process(image_rgb)

        # Hand wave detection
        wave_detected, hand_landmarks_list = self.wave_detector.detect_wave(image_rgb)

        face_x, face_y = None, None
        face_detected = False
        movement_command = None

        if face_results.detections:
            # FACE DETECTED
            face_detected = True
            self.no_face_count = 0
            self.scan_count = 0
            self.scanning_state = "idle"
            antenna_mode = "tracking"

            detection = face_results.detections[0]
            bbox = detection.location_data.relative_bounding_box

            face_x = (bbox.xmin + bbox.width / 2) * self.frame_width
            face_y = (bbox.ymin + bbox.height / 2) * self.frame_height

            # Calculate movement if needed
            movement = self.roi_controller.calculate_movement(
                face_x, face_y, current_time, movement_gain=50
            )

            if movement is not None:
                movement_command = {
                    'type': 'adjust',
                    'pan_adjustment': movement[0],
                    'roll_adjustment': movement[1],
                    'pitch': 0
                }
        else:
            # NO FACE - scanning behavior
            self.no_face_count += 1
            movement_command, antenna_mode = self._handle_no_face(current_time)

        # Prepare display frame
        display_frame = image.copy()
        if self.show_overlay:
            display_frame = self.roi_controller.draw_debug_overlay(
                display_frame, face_x, face_y, hand_landmarks_list, wave_detected
            )

        # Return complete tracking data with all required keys
        return {
            'frame': display_frame,
            'face_detected': face_detected,
            'face_position': {'x': float(face_x) if face_x is not None else None,
                              'y': float(face_y) if face_y is not None else None},
            'wave_detected': wave_detected,
            'wave_command': 'wave_back' if wave_detected else None,  # NEW: Command to wave back
            'movement_command': movement_command,
            'scanning_state': self.scanning_state,
            'antenna_mode': antenna_mode
        }

    def _handle_no_face(self, current_time):
        """Handle scanning behavior when no face is detected"""
        movement_command = None
        antenna_mode = "idle"

        if self.scanning_state == "idle":
            if self.no_face_count >= 60:
                self.scanning_state = "scanning"
                self.scan_count = 0
                self.state_start_time = current_time
                antenna_mode = "scanning"
            else:
                antenna_mode = "idle"

        elif self.scanning_state == "scanning":
            antenna_mode = "scanning"

            if self.frame_count % 90 == 0:
                self.scan_count += 1

                if self.scan_count > self.MAX_SCANS:
                    self.scanning_state = "giving_up"
                    self.state_start_time = current_time
                    antenna_mode = "giving_up"
                else:
                    random_pan_magnitude = random.uniform(30, 75)
                    random_roll = random.uniform(-5, 5)

                    if self.PANLEFT:
                        random_pan = -random_pan_magnitude
                    else:
                        random_pan = random_pan_magnitude

                    self.PANLEFT = not self.PANLEFT

                    movement_command = {
                        'type': 'absolute',
                        'pan': random_pan,
                        'roll': random_roll,
                        'pitch': 0
                    }

        elif self.scanning_state == "giving_up":
            if current_time - self.state_start_time > 1.5:
                self.scanning_state = "sad"
                self.state_start_time = current_time
                antenna_mode = "sad"

        elif self.scanning_state == "sad":
            antenna_mode = "sad"

            if current_time - self.state_start_time > 2.0:
                self.scanning_state = "looking_down"
                self.state_start_time = current_time
                movement_command = {
                    'type': 'absolute',
                    'pan': 0,
                    'roll': -30,
                    'pitch': 0
                }

        elif self.scanning_state == "looking_down":
            antenna_mode = "sad"

            if current_time - self.state_start_time > 3.0:
                self.scanning_state = "waiting"
                self.state_start_time = current_time

        elif self.scanning_state == "waiting":
            antenna_mode = "sad"

            if current_time - self.state_start_time > 2.0:
                self.scanning_state = "scanning"
                self.scan_count = 0
                self.state_start_time = current_time
                antenna_mode = "scanning"

        return movement_command, antenna_mode

    def cleanup(self):
        """Clean up resources"""
        self.face_detection.close()
        self.wave_detector.cleanup()
        if not self.is_reachy_camera:
            self.camera_source.release()

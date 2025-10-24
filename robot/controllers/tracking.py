import time
import random
import threading

import cv2 as cv
import mediapipe as mp
from reachy_sdk.trajectory import goto
from reachy_sdk.trajectory.interpolation import InterpolationMode
from rich import print

# Initialize MediaPipe Face Detection
mp_face_detection = mp.solutions.face_detection
mp_drawing = mp.solutions.drawing_utils

class TrackingController:
    def __init__(self, parent: "RobotController"):
        self.parent = parent
        self.reachy = parent.reachy
        self.running = False
        self.thread = None
        # Position tracking
        self.target_pan = 0
        self.target_roll = 0
        self.target_pitch = 0
        self.current_pan = 0
        self.current_roll = 0
        self.current_pitch = 0
        self.INTERPOLATION_RATE = 0.3
        self.MIN_MOVEMENT_THRESHOLD = 2.0

        # Face tracking state
        self.smoothed_error_x = 0
        self.smoothed_error_y = 0
        self.frame_count = 0
        self.no_face_count = 0
        self.PANLEFT = True

             # Face detection
        self.face_detection = mp_face_detection.FaceDetection(
            model_selection=1, 
            min_detection_confidence=0.9
        )

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
            print("✅ Tracking started")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
            print("🛑 Tracking stopped")

    def pause(self):
        self.running = False

    def _loop(self):
        """Main tracking loop that runs continuously"""
        self.current_pan = self.reachy.head.neck_yaw.present_position
        self.current_roll = self.reachy.head.neck_roll.present_position
        self.current_pitch = self.reachy.head.neck_pitch.present_position
        self.target_pan = self.current_pan
        self.target_roll = self.current_roll
        self.target_pitch = self.current_pitch

        while True:
            if self.running:
                #print("loop da loop, " + str(self.running) + ", ")
                try:
                    self.frame_count += 1
                    current_time = time.time()

                    image = self.reachy.left_camera.last_frame
                    if image is None:
                        continue

                    # Process image
                    image.flags.writeable = False
                    image_rgb = cv.cvtColor(image, cv.COLOR_BGR2RGB)
                    results = self.face_detection.process(image_rgb)

                    if results.detections:
                        # FACE DETECTED
                        self.no_face_count = 0
                        self.scan_count = 0
                        self.parent.scanning_state = "idle"

                        # Set antenna mode based on conversation state
                        if not self.parent.conversation_active:
                            self.parent.antenna_controller.current_antenna_mode = "tracking"

                        detection = results.detections[0]
                        bbox = detection.location_data.relative_bounding_box

                        face_center_x = (bbox.xmin + bbox.width / 2) * self.parent.frame_width
                        face_center_y = (bbox.ymin + bbox.height / 2) * self.parent.frame_height

                        error_x = (face_center_x - self.parent.frame_center_x) / self.parent.frame_width
                        error_y = (face_center_y - self.parent.frame_center_y) / self.parent.frame_height

                        self.smoothed_error_x = self.parent.SMOOTHING_ALPHA * error_x + (
                                1 - self.parent.SMOOTHING_ALPHA) * self.smoothed_error_x
                        self.smoothed_error_y = self.parent.SMOOTHING_ALPHA * error_y + (
                                1 - self.parent.SMOOTHING_ALPHA) * self.smoothed_error_y

                        if abs(self.smoothed_error_x) > self.parent.DEADBAND or abs(self.smoothed_error_y) > self.parent.DEADBAND:
                            actual_pan = self.reachy.head.neck_yaw.present_position
                            actual_roll = self.reachy.head.neck_roll.present_position

                            pan_movement = -self.smoothed_error_x * self.parent.MOVEMENT_GAIN
                            roll_movement = -self.smoothed_error_y * self.parent.MOVEMENT_GAIN

                            new_target_pan = actual_pan + pan_movement
                            new_target_roll = actual_roll + roll_movement

                            if abs(new_target_pan - self.target_pan) > self.MIN_MOVEMENT_THRESHOLD or \
                                    abs(new_target_roll - self.target_roll) > self.MIN_MOVEMENT_THRESHOLD:
                                self.target_pan = new_target_pan
                                self.target_roll = new_target_roll

                        self.target_pitch = 0

                    else:
                        # NO FACE - scanning state machine (only if not in conversation)
                        if not self.parent.conversation_active:
                            self.no_face_count += 1

                            if self.parent.scanning_state == "idle":
                                if self.no_face_count >= 60:
                                    self.scanning_state = "scanning"
                                    self.scan_count = 0
                                    self.state_start_time = current_time
                                    self.parent.antenna_controller.current_antenna_mode = "scanning"
                                else:
                                    self.parent.antenna_controller.current_antenna_mode = "idle"

                            elif self.parent.scanning_state == "scanning":
                                self.parent.antenna_controller.current_antenna_mode = "scanning"

                                if self.frame_count % 90 == 0:
                                    self.scan_count += 1

                                    if self.scan_count > self.parent.MAX_SCANS:
                                        self.parent.scanning_state = "giving_up"
                                        self.state_start_time = current_time
                                        self.parent.antenna_controller.current_antenna_mode = "giving_up"
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

                            elif self.parent.scanning_state == "giving_up":
                                if current_time - self.state_start_time > 1.5:
                                    self.parent.scanning_state = "sad"
                                    self.state_start_time = current_time
                                    self.parent.antenna_controller.current_antenna_mode = "sad"

                            elif self.parent.scanning_state == "sad":
                                self.parent.antenna_controller.current_antenna_mode = "sad"

                                if current_time - self.state_start_time > 2.0:
                                    self.parent.scanning_state = "looking_down"
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

                            elif self.parent.scanning_state == "looking_down":
                                self.parent.antenna_controller.current_antenna_mode = "sad"

                                if current_time - self.state_start_time > 3.0:
                                    self.parent.scanning_state = "waiting"
                                    self.state_start_time = current_time

                            elif self.parent.scanning_state == "waiting":
                                self.parent.antenna_controller.current_antenna_mode = "sad"

                                if current_time - self.state_start_time > 2.0:
                                    self.parent.scanning_state = "scanning"
                                    self.scan_count = 0
                                    self.state_start_time = current_time
                                    self.parent.antenna_controller.current_antenna_mode = "scanning"
                                    self.target_pitch = 0

                    # Interpolate toward target
                    self.current_pan += (self.target_pan - self.current_pan) * self.INTERPOLATION_RATE
                    self.current_roll += (self.target_roll - self.current_roll) * self.INTERPOLATION_RATE

                    # Send positions
                    self.reachy.head.neck_yaw.goal_position = self.current_pan
                    self.reachy.head.neck_roll.goal_position = self.current_roll
                    self.reachy.head.neck_pitch.goal_position = self.current_pitch
                    cv.imshow('Reachy Face Tracking', image)
                    
                    time.sleep(0.03)  # ~30 FPS

                except Exception as e:
                    print(f"Tracking error: {e}")
                    time.sleep(0.1)
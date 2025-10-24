"""
Movement Controller - Handles robot head movements
Abstracted to work with or without actual Reachy hardware
"""

import time
import random
import threading
from abc import ABC, abstractmethod


class MovementController(ABC):
    """Abstract base class for movement control"""

    @abstractmethod
    def move_head(self, pan, roll, pitch):
        """Move head to specified position"""
        pass

    @abstractmethod
    def get_current_position(self):
        """Get current head position (pan, roll, pitch)"""
        pass

    @abstractmethod
    def set_antenna_mode(self, mode):
        """Set antenna animation mode"""
        pass

    @abstractmethod
    def turn_on(self):
        """Turn on the robot"""
        pass

    @abstractmethod
    def turn_off(self):
        """Turn off the robot"""
        pass


class ReachyMovementController(MovementController):
    """Movement controller for actual Reachy robot"""

    def __init__(self, reachy_host='128.39.142.134', enable_antenna=True):
        from reachy_sdk import ReachySDK
        from reachy_sdk.trajectory import goto
        from reachy_sdk.trajectory.interpolation import InterpolationMode

        self.reachy = ReachySDK(reachy_host)
        self.goto = goto
        self.InterpolationMode = InterpolationMode
        self.enable_antenna = enable_antenna

        # Current positions
        self.current_pan = 0
        self.current_roll = 0
        self.current_pitch = 0

        # Antenna control
        self.current_antenna_mode = "idle"
        if self.enable_antenna:
            self.antenna_thread_running = True
            self.antenna_thread = threading.Thread(target=self._antenna_controller, daemon=True)
            self.antenna_thread.start()

    def move_head(self, pan, roll, pitch):
        """Move Reachy's head to specified position"""
        self.current_pan = pan
        self.current_roll = roll
        self.current_pitch = pitch

        self.reachy.head.neck_yaw.goal_position = pan
        self.reachy.head.neck_roll.goal_position = roll
        self.reachy.head.neck_pitch.goal_position = pitch

    def get_current_position(self):
        """Get current head position from Reachy"""
        return (
            self.reachy.head.neck_yaw.present_position,
            self.reachy.head.neck_roll.present_position,
            self.reachy.head.neck_pitch.present_position
        )

    def set_antenna_mode(self, mode):
        """Set antenna animation mode"""
        if self.enable_antenna:
            self.current_antenna_mode = mode

    def turn_on(self):
        """Turn on Reachy's head"""
        print("Turning on Reachy's head...")
        self.reachy.turn_on('head')
        time.sleep(1)

        # Get initial positions
        self.current_pan, self.current_roll, self.current_pitch = self.get_current_position()

    def turn_off(self):
        """Turn off Reachy's head smoothly"""
        print("Turning off Reachy...")

        # Stop antenna thread
        if self.enable_antenna:
            self.antenna_thread_running = False
            self.antenna_thread.join(timeout=2)

        # Return to neutral position
        self.goto(
            goal_positions={
                self.reachy.head.neck_yaw: 0,
                self.reachy.head.neck_roll: 0,
                self.reachy.head.neck_pitch: 0,
                self.reachy.head.l_antenna: 0,
                self.reachy.head.r_antenna: 0
            },
            duration=1.0,
            interpolation_mode=self.InterpolationMode.MINIMUM_JERK
        )
        time.sleep(1)

        self.reachy.turn_off_smoothly('head')

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


class SimulatedMovementController(MovementController):
    """Simulated movement controller for testing without hardware"""

    def __init__(self, enable_antenna=True):
        self.enable_antenna = enable_antenna
        self.current_pan = 0
        self.current_roll = 0
        self.current_pitch = 0
        self.current_antenna_mode = "idle"

        print("Using SIMULATED movement controller (no hardware)")

    def move_head(self, pan, roll, pitch):
        """Simulate head movement"""
        self.current_pan = pan
        self.current_roll = roll
        self.current_pitch = pitch
        # Print occasional updates (not every frame)
        if random.random() < 0.05:  # 5% of frames
            print(f"[SIM] Head: pan={pan:.1f}, roll={roll:.1f}, pitch={pitch:.1f}")

    def get_current_position(self):
        """Get simulated current position"""
        return self.current_pan, self.current_roll, self.current_pitch

    def set_antenna_mode(self, mode):
        """Simulate antenna mode change"""
        if self.enable_antenna and self.current_antenna_mode != mode:
            self.current_antenna_mode = mode
            print(f"[SIM] Antenna mode: {mode}")

    def turn_on(self):
        """Simulate turning on"""
        print("[SIM] Robot turned on")
        self.current_pan = 0
        self.current_roll = 0
        self.current_pitch = 0

    def turn_off(self):
        """Simulate turning off"""
        print("[SIM] Returning to neutral position...")
        self.current_pan = 0
        self.current_roll = 0
        self.current_pitch = 0
        self.current_antenna_mode = "idle"
        print("[SIM] Robot turned off")

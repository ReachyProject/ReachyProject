import math
import math
import time

from constants import REACHY_JOINTS
from reachy import get_reachy, get_joint_by_name
from reachy_sdk.trajectory import goto
from reachy_sdk.trajectory.interpolation import InterpolationMode


class MovementSequence:
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.running = False
        self.positions = []

    def end(self):
        self.running = False

    def execute_movement_sequence(self, max_duration, max_degrees_per_second=60):
        movement_start = time.time()
        previous_timestamp = None
        previous_joints = None

        for timestamp, joints in self.positions:
            if time.time() - max_duration > movement_start:
                return # exit early

            if previous_timestamp is None:
                previous_joints = get_joints()
                continue

            delay = timestamp - previous_timestamp

            max_change = get_max_angle_change(previous_joints, joints, delay)

            if max_change > max_degrees_per_second:
                delay *= max_change / max_degrees_per_second

            goto(joints, duration=delay, interpolation_mode=InterpolationMode.MINIMUM_JERK)

            previous_timestamp = timestamp
        return

    def record_movement_sequence(self, callback, movement_interval=0.1):
        try:
            while self.running:
                self.positions.append(self.get_current_position())
                time.sleep(movement_interval)
            callback()
        except Exception:
            print("")


    def get_current_position(self) -> tuple[float, dict[object, float]]:
        return time.time(), get_joints()

    def start_sequence(self):
        self.start_time = time.time()
        self.record_movement_sequence(self.end_sequence)

    def end_sequence(self):
        self.running = False
        self.end_time = time.time()

def get_joints() -> dict[object, float]:
    reachy = get_reachy()
    if reachy is None:
        return {}

    positions = {}
    nan_count = 0

    for joint_name in REACHY_JOINTS:
        joint = get_joint_by_name(reachy, joint_name)
        if joint:
            try:
                pos = joint.present_position

                if pos is None or math.isnan(pos):
                    positions[joint] = 0.0
                    nan_count += 1
                else:
                    positions[joint] = round(float(pos), 2)

            except Exception:
                positions[joint] = 0.0
                nan_count += 1

    return positions

#returns maximum movement speed in degrees/second
def get_max_angle_change(prev_joints: dict, curr_joints: dict, delta_t: float) -> float:
    if delta_t <= 0:
        return 0.0

    max_speed = 0.0
    for joint, curr_angle in curr_joints.items():
        if joint in prev_joints:
            prev_angle = prev_joints[joint]
            delta_angle = abs(curr_angle - prev_angle)
            speed = delta_angle / delta_t
            if speed > max_speed:
                max_speed = speed

    return max_speed

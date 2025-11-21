import time
from global_variables import log_lines, reachy_connection


# Reachy SDK imports
try:
    from reachy_sdk import ReachySDK
    from reachy_sdk.trajectory import goto
    from reachy_sdk.trajectory.interpolation import InterpolationMode
    REACHY_SDK_AVAILABLE = True
except ImportError:
    ReachySDK = None
    goto = None
    InterpolationMode = None
    REACHY_SDK_AVAILABLE = False


def get_reachy():
    """Get or create Reachy connection"""
    global reachy_connection
    if not REACHY_SDK_AVAILABLE:
        return None

    if reachy_connection is None:
        try:
            reachy_connection = ReachySDK(host='128.39.142.134')
            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [green]Connected to Reachy[/green]")
        except Exception as e:
            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Failed to connect to Reachy: {e}[/red]")
            return None
    return reachy_connection


def get_joint_by_name(robot, joint):
    """Get a joint object from Reachy by name"""
    try:
        # Handle arm joints
        if joint.startswith('r_') and joint != 'r_antenna':
            return getattr(robot.r_arm, joint, None)
        elif joint.startswith('l_') and joint != 'l_antenna':
            return getattr(robot.l_arm, joint, None)
        # Handle antenna joints
        elif joint == 'l_antenna':
            return getattr(robot.head, 'l_antenna', None)
        elif joint == 'r_antenna':
            return getattr(robot.head, 'r_antenna', None)
        # Handle neck joints
        elif joint == 'neck_yaw':
            return robot.head.neck_yaw
        elif joint == 'neck_roll':
            return robot.head.neck_roll
        elif joint == 'neck_pitch':
            return robot.head.neck_pitch
        else:
            return None
    except Exception as e:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error getting joint {joint}: {e}")
        return None
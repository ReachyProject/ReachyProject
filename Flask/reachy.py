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
            reachy_connection = ReachySDK(host='localhost')
            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [green]Connected to Reachy[/green]")
        except Exception as e:
            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Failed to connect to Reachy: {e}[/red]")
            return None
    return reachy_connection

def get_joint_by_name(reachy, joint_name):
    """Get joint object from Reachy by name"""
    try:
        # Handle arm joints
        if joint_name.startswith('r_') and joint_name != 'r_antenna':
            return getattr(reachy.r_arm, joint_name, None)
        elif joint_name.startswith('l_') and joint_name != 'l_antenna':
            return getattr(reachy.l_arm, joint_name, None)
        # Handle antenna joints
        elif joint_name == 'l_antenna':
            return getattr(reachy.head, 'l_antenna', None)
        elif joint_name == 'r_antenna':
            return getattr(reachy.head, 'r_antenna', None)
        # Handle neck joints
        elif joint_name == 'neck_yaw':
            return reachy.head.neck_yaw
        elif joint_name == 'neck_roll':
            return reachy.head.neck_roll
        elif joint_name == 'neck_pitch':
            return reachy.head.neck_pitch
        else:
            return None
    except Exception as e:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error getting joint {joint_name}: {e}")
        return None
    
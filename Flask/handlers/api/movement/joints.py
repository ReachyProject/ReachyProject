import time

from flask import jsonify
from reachy import get_reachy, get_joint_by_name
from constants import REACHY_JOINTS

from global_variables import log_lines


def get_joints():
    """Return list of available joints with their current state"""
    try:
        robot = get_reachy()
        joint_info = []

        if robot:
            # Get actual joints from the robot
            try:
                for joint_name in REACHY_JOINTS:
                    joint = get_joint_by_name(robot, joint_name)
                    if joint:
                        joint_info.append({
                            'name': joint_name,
                            'compliant': joint.compliant if hasattr(joint, 'compliant') else False
                        })
            except (AttributeError, ValueError, RuntimeError) as e:
                # If we can't get state, just return names
                log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error getting joint state: {e}")
                joint_info = [{'name': j, 'compliant': False} for j in REACHY_JOINTS]
        else:
            # Robot not connected, return default list
            joint_info = [{'name': j, 'compliant': False} for j in REACHY_JOINTS]

        return jsonify({'success': True, 'joints': [j['name'] for j in joint_info]})
    except OSError as e:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Connection error: {e}")
        return jsonify({'success': True, 'joints': REACHY_JOINTS})  # Fallback to a static list
    
from flask import jsonify
import time
import math
from global_variables import compliant_mode_active, initial_positions, log_lines
from reachy import get_reachy, get_joint_by_name, REACHY_SDK_AVAILABLE
from constants import REACHY_JOINTS


def start_compliant_mode():
    """Start compliant mode - keep all joints stiff until the user unlocks them"""
    global compliant_mode_active, initial_positions

    if not REACHY_SDK_AVAILABLE:
        return jsonify({'success': False, 'message': 'Reachy SDK not available'})

    try:
        robot = get_reachy()
        if robot is None:
            return jsonify({'success': False, 'message': 'Cannot connect to Reachy'})

        # Turn on the robot (all joints stiff)
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [cyan]Turning on robot...[/cyan]")
        robot.turn_on('r_arm')
        robot.turn_on('l_arm')
        robot.turn_on('head')

        time.sleep(1.5)  # Wait for joints to stabilize

        # CAPTURE INITIAL POSITIONS
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [cyan]Reading initial positions...[/cyan]")
        initial_positions = {}
        nan_joints = []

        for joint in REACHY_JOINTS:
            joint = get_joint_by_name(robot, joint)
            if joint:
                try:
                    pos = joint.present_position

                    if pos is None or math.isnan(pos):
                        log_lines.append(
                            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]{joint}: NaN - will use 0.0[/yellow]")
                        initial_positions[joint] = 0.0
                        nan_joints.append(joint)
                    else:
                        initial_positions[joint] = round(float(pos), 2)
                        log_lines.append(
                            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {joint}: {initial_positions[joint]}°")

                except Exception as e:
                    log_lines.append(
                        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]{joint}: Error - {str(e)}[/red]")
                    initial_positions[joint] = 0.0
                    nan_joints.append(joint)

        if nan_joints:
            log_lines.append(
                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]Joints with NaN: {', '.join(nan_joints)}[/yellow]")

        compliant_mode_active = True
        log_lines.append(
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [green]Ready! All joints are stiff and locked.[/green]")
        log_lines.append(
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]Use 'Unlock' buttons to make joints compliant for "
            f"positioning[/yellow]")

        return jsonify({
            'success': True,
            'message': 'Ready for positioning. Unlock joints to move them.',
            'initial_positions': initial_positions
        })

    except Exception as e:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Error: {str(e)}[/red]")
        return jsonify({'success': False, 'message': str(e)})
    
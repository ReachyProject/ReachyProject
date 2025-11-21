import time
from flask import request, jsonify

from reachy import get_reachy, get_joint_by_name
from global_variables import log_lines


def toggle_joint():
    """Toggle a specific joint between compliant and stiff"""
    joint = None

    try:
        data = request.json
        joint = data.get('joint')
        locked = data.get('locked')

        robot = get_reachy()
        if robot is None:
            return jsonify({'success': False, 'message': 'Cannot connect to Reachy'})

        joint = get_joint_by_name(robot, joint)
        if joint is None:
            return jsonify({'success': False, 'message': f'Joint {joint} not found'})

        # Set compliant state
        joint.compliant = not locked

        # Verify the change took effect
        actual_state = joint.compliant
        state = "locked (stiff)" if not actual_state else "unlocked (compliant)"

        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {joint} set to {state}")

        return jsonify({'success': True, 'message': f'{joint} {state}'})

    except Exception as e:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Error toggling {joint}: {str(e)}[/red]")
        return jsonify({'success': False, 'message': str(e)})    

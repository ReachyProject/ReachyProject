from flask import Blueprint, request, jsonify
import time
from reachy import get_reachy, get_joint_by_name
from global_variables import log_lines


toggle_joint_bp = Blueprint('toggle_joint', __name__)

toggle_joint_bp.route('/api/movement/toggle-joint', methods=['POST'])
def toggle_joint():
    """Toggle a specific joint between compliant and stiff"""
    try:
        data = request.json
        joint_name = data.get('joint')
        locked = data.get('locked')
        
        reachy = get_reachy()
        if reachy is None:
            return jsonify({'success': False, 'message': 'Cannot connect to Reachy'})
        
        joint = get_joint_by_name(reachy, joint_name)
        if joint is None:
            return jsonify({'success': False, 'message': f'Joint {joint_name} not found'})
        
        # Set compliant state
        joint.compliant = not locked
        
        # Verify the change took effect
        actual_state = joint.compliant
        state = "locked (stiff)" if not actual_state else "unlocked (compliant)"
        
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {joint_name} set to {state}")
        
        return jsonify({'success': True, 'message': f'{joint_name} {state}'})
        
    except Exception as e:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Error toggling {joint_name}: {str(e)}[/red]")
        return jsonify({'success': False, 'message': str(e)})
    
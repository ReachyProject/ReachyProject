from flask import Blueprint, jsonify
import time
import math
from Flask.reachy import get_reachy, get_joint_by_name
from Flask.constants import REACHY_JOINTS
from Flask.global_variables import log_lines


positions_bp = Blueprint('positions', __name__)

@positions_bp.route('/api/movement/positions', methods=['GET'])
def get_positions():
    """Get current positions of all joints with NaN handling"""
    try:
        reachy = get_reachy()
        if reachy is None:
            return jsonify({'success': False, 'message': 'Cannot connect to Reachy'})
        
        positions = {}
        nan_count = 0
        
        for joint_name in REACHY_JOINTS:
            joint = get_joint_by_name(reachy, joint_name)
            if joint:
                try:
                    pos = joint.present_position
                    
                    # Proper NaN check
                    if pos is None or math.isnan(pos):
                        positions[joint_name] = 0.0
                        nan_count += 1
                    else:
                        positions[joint_name] = round(float(pos), 2)
                        
                except (AttributeError, TypeError, ValueError) as e:
                    positions[joint_name] = 0.0
            else:
                positions[joint_name] = 0.0
        
        # Only log if we have NaN issues (and not too frequently)
        if nan_count > 0 and nan_count == len(REACHY_JOINTS):
            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Warning: All joints returning NaN values[/red]")
        
        return jsonify({'success': True, 'positions': positions})
        
    except Exception as e:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Error getting positions: {str(e)}[/red]")
        return jsonify({'success': False, 'message': str(e)})
    
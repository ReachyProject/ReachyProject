from flask import Blueprint, jsonify
import time
import math
from Flask.reachy import get_reachy, get_joint_by_name
from Flask.constants import REACHY_JOINTS
from Flask.global_variables import log_lines


capture_bp = Blueprint('capture', __name__)

@capture_bp.route('/api/movement/capture', methods=['GET'])
def capture_position():
    """Capture current position of all joints"""
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
                    
                    if pos is None or math.isnan(pos):
                        positions[joint_name] = 0.0
                        nan_count += 1
                    else:
                        positions[joint_name] = round(float(pos), 2)
                        
                except Exception:
                    positions[joint_name] = 0.0
                    nan_count += 1
        
        if nan_count > 0:
            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]Position captured ({nan_count} NaN values replaced with 0.0)[/yellow]")
        else:
            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [cyan]Position captured successfully[/cyan]")
        
        return jsonify({'success': True, 'positions': positions})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

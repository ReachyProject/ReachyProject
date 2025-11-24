from flask import Blueprint, jsonify
from Flask.reachy import get_reachy, get_joint_by_name
from Flask.constants import REACHY_JOINTS
from Flask.global_variables import log_lines, compliant_mode_active
import time


stop_compliant_bp = Blueprint('stop_compliant', __name__)

@stop_compliant_bp.route('/api/movement/stop-compliant', methods=['POST'])
def stop_compliant_mode():
    """Stop compliant mode - lock all joints in place (stiffen)"""
    global compliant_mode_active
    
    try:
        reachy = get_reachy()
        if reachy is None:
            return jsonify({'success': False, 'message': 'Cannot connect to Reachy'})
        
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]Stiffening all joints...[/yellow]")
        
        # Stiffen all joints by setting them non-compliant
        stiffened_joints = []
        for joint_name in REACHY_JOINTS:
            joint = get_joint_by_name(reachy, joint_name)
            if joint:
                try:
                    joint.compliant = False
                    stiffened_joints.append(joint_name)
                    log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Stiffened {joint_name}")
                except Exception as e:
                    log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Error stiffening {joint_name}: {e}[/red]")
        
        compliant_mode_active = False
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [green]All joints locked in current position[/green]")
        
        return jsonify({
            'success': True, 
            'message': 'All joints stiffened and locked',
            'stiffened_joints': stiffened_joints
        })
        
    except Exception as e:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Error in stop_compliant: {str(e)}[/red]")
        return jsonify({'success': False, 'message': str(e)})
    
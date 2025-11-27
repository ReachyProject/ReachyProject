from flask import Blueprint, jsonify
import time
from Flask.reachy import get_reachy, get_joint_by_name, goto, InterpolationMode
from Flask.constants import REACHY_JOINTS
from Flask.global_variables import compliant_mode_active, initial_positions, log_lines


emergency_stop_bp = Blueprint('emergency_stop', __name__)

@emergency_stop_bp.route('/api/movement/emergency-stop', methods=['POST'])
def emergency_stop():
    """EMERGENCY: Stiffen all joints, return to initial position, then smoothly power down"""
    global compliant_mode_active, initial_positions
    
    try:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red bold]EMERGENCY STOP INITIATED[/red bold]")
        
        reachy = get_reachy()
        if reachy is None:
            return jsonify({'success': False, 'message': 'Cannot connect to Reachy'})
        
        # Step 1: Immediately stiffen all joints
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]Step 1: Stiffening all joints...[/yellow]")
        stiffened_joints = []
        for joint_name in REACHY_JOINTS:
            joint = get_joint_by_name(reachy, joint_name)
            if joint:
                try:
                    joint.compliant = False
                    stiffened_joints.append(joint_name)
                except Exception as e:
                    log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Error stiffening {joint_name}: {e}[/red]")
        
        time.sleep(0.5)
        
        # Step 2: Return to INITIAL positions (where we started)
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]Step 2: Returning to initial position...[/yellow]")
        
        if initial_positions:
            # Build goal_positions dict from initial positions
            goal_positions = {}
            
            # Right arm
            if 'r_shoulder_pitch' in initial_positions:
                goal_positions[reachy.r_arm.r_shoulder_pitch] = initial_positions['r_shoulder_pitch']
            if 'r_shoulder_roll' in initial_positions:
                goal_positions[reachy.r_arm.r_shoulder_roll] = initial_positions['r_shoulder_roll']
            if 'r_arm_yaw' in initial_positions:
                goal_positions[reachy.r_arm.r_arm_yaw] = initial_positions['r_arm_yaw']
            if 'r_elbow_pitch' in initial_positions:
                goal_positions[reachy.r_arm.r_elbow_pitch] = initial_positions['r_elbow_pitch']
            if 'r_forearm_yaw' in initial_positions:
                goal_positions[reachy.r_arm.r_forearm_yaw] = initial_positions['r_forearm_yaw']
            if 'r_wrist_pitch' in initial_positions:
                goal_positions[reachy.r_arm.r_wrist_pitch] = initial_positions['r_wrist_pitch']
            if 'r_wrist_roll' in initial_positions:
                goal_positions[reachy.r_arm.r_wrist_roll] = initial_positions['r_wrist_roll']
            
            # Left arm
            if 'l_shoulder_pitch' in initial_positions:
                goal_positions[reachy.l_arm.l_shoulder_pitch] = initial_positions['l_shoulder_pitch']
            if 'l_shoulder_roll' in initial_positions:
                goal_positions[reachy.l_arm.l_shoulder_roll] = initial_positions['l_shoulder_roll']
            if 'l_arm_yaw' in initial_positions:
                goal_positions[reachy.l_arm.l_arm_yaw] = initial_positions['l_arm_yaw']
            if 'l_elbow_pitch' in initial_positions:
                goal_positions[reachy.l_arm.l_elbow_pitch] = initial_positions['l_elbow_pitch']
            if 'l_forearm_yaw' in initial_positions:
                goal_positions[reachy.l_arm.l_forearm_yaw] = initial_positions['l_forearm_yaw']
            if 'l_wrist_pitch' in initial_positions:
                goal_positions[reachy.l_arm.l_wrist_pitch] = initial_positions['l_wrist_pitch']
            if 'l_wrist_roll' in initial_positions:
                goal_positions[reachy.l_arm.l_wrist_roll] = initial_positions['l_wrist_roll']
            
            # Neck joints
            if 'neck_yaw' in initial_positions:
                goal_positions[reachy.head.neck_yaw] = initial_positions['neck_yaw']
            if 'neck_roll' in initial_positions:
                goal_positions[reachy.head.neck_roll] = initial_positions['neck_roll']
            if 'neck_pitch' in initial_positions:
                goal_positions[reachy.head.neck_pitch] = initial_positions['neck_pitch']
            
            if goal_positions:
                goto(
                    goal_positions=goal_positions,
                    duration=2.0,
                    interpolation_mode=InterpolationMode.MINIMUM_JERK
                )
                log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [cyan]Returned to initial positions[/cyan]")
        else:
            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]No initial positions stored, staying in place[/yellow]")
        
        time.sleep(2.5)
        
        # Step 3: Smoothly power down
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]Step 3: Powering down safely...[/yellow]")
        reachy.turn_off_smoothly('r_arm')
        reachy.turn_off_smoothly('l_arm')
        reachy.turn_off_smoothly('head')
        
        compliant_mode_active = False
        initial_positions = {}  # Clear stored positions
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [green]EMERGENCY STOP COMPLETE - Robot safely powered down[/green]")
        
        return jsonify({
            'success': True, 
            'message': 'Emergency stop complete - robot powered down',
            'stiffened_joints': stiffened_joints
        })
        
    except Exception as e:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Emergency stop error: {str(e)}[/red]")
        try:
            if reachy:
                reachy.turn_off_smoothly('r_arm')
                reachy.turn_off_smoothly('l_arm')
                reachy.turn_off_smoothly('head')
        except:
            pass
        return jsonify({'success': False, 'message': str(e)})
    
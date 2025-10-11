from flask import Flask, render_template, request, jsonify, Response
import os
import sys
import subprocess
from pathlib import Path
from collections import deque
import threading
import time
import cv2 as cv
from dotenv import set_key
import math

from reachy import REACHY_SDK_AVAILABLE, ReachySDK, goto, InterpolationMode
from camera import CAMERA_AVAILABLE, CameraFrameProvider
from constants import ELEVENLABS_VOICES, REACHY_JOINTS
from global_variables import running_process, log_lines, reachy_connection, compliant_mode_active, initial_positions

from handlers.index import index_bp 
from handlers.save_config import save_config_bp
from handlers.camera_feed import camera_feed_bp
from handlers.camera_status import camera_status_bp
from handlers.camera import camera_bp


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Reachy SDK imports
if not REACHY_SDK_AVAILABLE:
    print("Warning: reachy_sdk not available. Movement recorder will not function.")

# Camera frame provider import
if not CAMERA_AVAILABLE:
    print("Camera frame provider not available")
    

app = Flask(__name__)

def read_process_output(process):
    """Read output from process and store in log_lines"""
    global log_lines
    try:
        while True:
            line = process.stdout.readline()
            if not line:
                break
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            log_lines.append(f"[{timestamp}] {line.strip()}")
    except Exception as e:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error reading output: {str(e)}")

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

# ==================== CAMERA ROUTES ====================

app.register_blueprint(camera_feed_bp)
app.register_blueprint(camera_status_bp)
app.register_blueprint(camera_bp)

# ==================== ORIGINAL ROUTES ====================

app.register_blueprint(index_bp)

@app.route('/update_voice', methods=['POST'])
def update_voice():
    data = request.get_json()
    voice_id = data.get('VOICE_ID')
    
    if not voice_id:
        return jsonify({'success': False, 'message': 'No voice ID provided'}), 400

    set_key('.env', 'VOICE_ID', voice_id)
    return jsonify({'success': True, 'message': f'Voice ID updated to {voice_id}'})


@app.route('/logs')
def logs():
    return render_template('logs.html')

@app.route('/api/logs')
def get_logs():
    """Return the current logs"""
    return jsonify({'logs': list(log_lines)})

@app.route('/api/logs/clear', methods=['POST'])
def clear_logs():
    """Clear all logs"""
    global log_lines
    log_lines.clear()
    return jsonify({'success': True, 'message': 'Logs cleared'})


app.register_blueprint(save_config_bp)


@app.route('/service/<action>', methods=['POST'])
def service_control(action):
    global running_process
    
    try:
        if action == 'start':
            if running_process and running_process.poll() is None:
                return jsonify({'success': False, 'message': 'Service is already running'})
            
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'

            from dotenv import load_dotenv
            load_dotenv()
            VOICE_ID = os.getenv("VOICE_ID", "Unknown")
            
            running_process = subprocess.Popen(
                [sys.executable, '-u', 'main.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace',
                env=env
            )
            
            thread = threading.Thread(target=read_process_output, args=(running_process,))
            thread.daemon = True
            thread.start()
            
            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [green]✓ Service started[/green]")
            return jsonify({'success': True, 'message': 'Reachy service started'})
        
        elif action == 'stop':
            if not running_process or running_process.poll() is not None:
                return jsonify({'success': False, 'message': 'Service is not running'})
            
            running_process.terminate()
            try:
                running_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                running_process.kill()
                running_process.wait()
            
            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]■ Service stopped[/red]")
            return jsonify({'success': True, 'message': 'Reachy service stopped'})
        
        elif action == 'restart':
            if running_process and running_process.poll() is None:
                running_process.terminate()
                try:
                    running_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    running_process.kill()
                    running_process.wait()
                log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]↻ Service stopped for restart[/yellow]")
            
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            
            running_process = subprocess.Popen(
                [sys.executable, '-u', 'main.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace',
                env=env
            )
            
            thread = threading.Thread(target=read_process_output, args=(running_process,))
            thread.daemon = True
            thread.start()
            
            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [green]✓ Service restarted[/green]")
            return jsonify({'success': True, 'message': 'Reachy service restarted'})
        
        else:
            return jsonify({'success': False, 'message': 'Invalid action'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/service/status', methods=['GET'])
def service_status():
    global running_process
    if running_process and running_process.poll() is None:
        return jsonify({'running': True})
    return jsonify({'running': False})

# ==================== MOVEMENT RECORDER ROUTES ====================

@app.route('/movement-recorder')
def movement_recorder():
    return render_template('movement_recorder.html')

@app.route('/api/movement/joints', methods=['GET'])
def get_joints():
    """Return list of available joints with their current state"""
    try:
        reachy = get_reachy()
        joint_info = []
        
        if reachy:
            # Get actual joints from the robot
            try:
                for joint_name in REACHY_JOINTS:
                    joint = get_joint_by_name(reachy, joint_name)
                    if joint:
                        joint_info.append({
                            'name': joint_name,
                            'compliant': joint.compliant if hasattr(joint, 'compliant') else False
                        })
            except:
                # If we can't get state, just return names
                joint_info = [{'name': j, 'compliant': False} for j in REACHY_JOINTS]
        else:
            # Robot not connected, return default list
            joint_info = [{'name': j, 'compliant': False} for j in REACHY_JOINTS]
        
        return jsonify({'success': True, 'joints': [j['name'] for j in joint_info]})
    except Exception as e:
        return jsonify({'success': True, 'joints': REACHY_JOINTS})  # Fallback to static list

@app.route('/api/movement/start-compliant', methods=['POST'])
def start_compliant_mode():
    """Start compliant mode - keep all joints stiff until user unlocks them"""
    global compliant_mode_active, initial_positions
    
    if not REACHY_SDK_AVAILABLE:
        return jsonify({'success': False, 'message': 'Reachy SDK not available'})
    
    try:
        reachy = get_reachy()
        if reachy is None:
            return jsonify({'success': False, 'message': 'Cannot connect to Reachy'})
        
        # Turn on the robot (all joints stiff)
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [cyan]Turning on robot...[/cyan]")
        reachy.turn_on('r_arm')
        reachy.turn_on('l_arm')
        reachy.turn_on('head')
        
        time.sleep(1.5)  # Wait for joints to stabilize
        
        # CAPTURE INITIAL POSITIONS
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [cyan]Reading initial positions...[/cyan]")
        initial_positions = {}
        nan_joints = []
        
        for joint_name in REACHY_JOINTS:
            joint = get_joint_by_name(reachy, joint_name)
            if joint:
                try:
                    pos = joint.present_position
                    
                    if pos is None or math.isnan(pos):
                        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]{joint_name}: NaN - will use 0.0[/yellow]")
                        initial_positions[joint_name] = 0.0
                        nan_joints.append(joint_name)
                    else:
                        initial_positions[joint_name] = round(float(pos), 2)
                        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {joint_name}: {initial_positions[joint_name]}°")
                        
                except Exception as e:
                    log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]{joint_name}: Error - {str(e)}[/red]")
                    initial_positions[joint_name] = 0.0
                    nan_joints.append(joint_name)
        
        if nan_joints:
            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]Joints with NaN: {', '.join(nan_joints)}[/yellow]")
        
        compliant_mode_active = True
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [green]Ready! All joints are stiff and locked.[/green]")
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]Use 'Unlock' buttons to make joints compliant for positioning[/yellow]")
        
        return jsonify({
            'success': True, 
            'message': 'Ready for positioning. Unlock joints to move them.',
            'initial_positions': initial_positions
        })
        
    except Exception as e:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Error: {str(e)}[/red]")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/movement/stop-compliant', methods=['POST'])
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

@app.route('/api/movement/emergency-stop', methods=['POST'])
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

@app.route('/api/movement/toggle-joint', methods=['POST'])
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

@app.route('/api/movement/positions', methods=['GET'])
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

@app.route('/api/movement/capture', methods=['GET'])
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

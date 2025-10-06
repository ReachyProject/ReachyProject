from flask import Flask, render_template, request, jsonify
import os
import sys
import subprocess
from pathlib import Path
from collections import deque
import threading
import time

# Reachy SDK imports
try:
    from reachy_sdk import ReachySDK
    from reachy_sdk.trajectory import goto
    from reachy_sdk.trajectory.interpolation import InterpolationMode
    REACHY_SDK_AVAILABLE = True
except ImportError:
    REACHY_SDK_AVAILABLE = False
    print("Warning: reachy_sdk not available. Movement recorder will not function.")

app = Flask(__name__)

# Store the process ID of the running main.py
running_process = None
log_lines = deque(maxlen=500)  # Store last 500 log lines

# Global variables for Reachy connection
reachy_connection = None
compliant_mode_active = False

PERSONAS = ["Old Man", "Young Man", "Old Woman", "Young Woman", "Child"]
AGE_RANGES = {
    "Old Man": ["60-70", "70-80", "80+"],
    "Young Man": ["18-25", "26-35", "36-45"],
    "Old Woman": ["60-70", "70-80", "80+"],
    "Young Woman": ["18-25", "26-35", "36-45"],
    "Child": ["5-8", "9-12", "13-17"]
}
MOODS = ["Happy", "Sad", "Angry", "Neutral", "Excited", "Tired", "Anxious"]
LLM_PROVIDERS = ["OpenAI", "Anthropic", "Hugging Face", "Cohere", "Google"]
LLM_MODELS = {
    "OpenAI": ["gpt-4", "gpt-3.5-turbo", "gpt-4-turbo"],
    "Anthropic": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
    "Hugging Face": ["mistral-7b", "llama-2-70b", "falcon-40b"],
    "Cohere": ["command", "command-light", "command-nightly"],
    "Google": ["gemini-pro", "gemini-ultra", "palm-2"]
}

# Define which joints to control - adjust based on your Reachy configuration
REACHY_JOINTS = [
    'r_shoulder_pitch', 'r_shoulder_roll', 'r_arm_yaw', 'r_elbow_pitch',
    'r_forearm_yaw', 'r_wrist_pitch', 'r_wrist_roll', 'r_gripper',
    'l_shoulder_pitch', 'l_shoulder_roll', 'l_arm_yaw', 'l_elbow_pitch',
    'l_forearm_yaw', 'l_wrist_pitch', 'l_wrist_roll', 'l_gripper',
    'l_antenna', 'r_antenna'  # Head joints - neck uses look_at() separately
]

def write_to_env(persona, age_range, mood, llm_provider, llm_model):
    """Write configuration to .env file"""
    env_path = Path('.env')
    env_content = f"""PERSONA={persona}
AGE_RANGE={age_range}
MOOD={mood}
LLM_PROVIDER={llm_provider}
LLM_MODEL={llm_model}
"""
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(env_content)
    return True

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
        # Joint names in Reachy SDK already include the prefix
        if joint_name.startswith('r_'):
            return getattr(reachy.r_arm, joint_name, None)
        elif joint_name.startswith('l_') and joint_name != 'l_antenna':
            return getattr(reachy.l_arm, joint_name, None)
        elif joint_name in ['l_antenna', 'r_antenna']:
            return getattr(reachy.head, joint_name, None)
        else:
            return None
    except Exception as e:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error getting joint {joint_name}: {e}")
        return None

# Original routes
@app.route('/')
def index():
    return render_template('index.html', 
                         personas=PERSONAS,
                         age_ranges=AGE_RANGES,
                         moods=MOODS,
                         llm_providers=LLM_PROVIDERS,
                         llm_models=LLM_MODELS)

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

@app.route('/save_config', methods=['POST'])
def save_config():
    try:
        data = request.json
        persona = data.get('persona')
        age_range = data.get('age_range')
        mood = data.get('mood')
        llm_provider = data.get('llm_provider')
        llm_model = data.get('llm_model')
        
        write_to_env(persona, age_range, mood, llm_provider, llm_model)
        return jsonify({'success': True, 'message': 'Configuration saved'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/service/<action>', methods=['POST'])
def service_control(action):
    global running_process
    
    try:
        if action == 'start':
            if running_process and running_process.poll() is None:
                return jsonify({'success': False, 'message': 'Service is already running'})
            
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

# Movement Recorder routes
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
    """Start compliant mode - SAFELY activate with gravity compensation"""
    global compliant_mode_active
    
    if not REACHY_SDK_AVAILABLE:
        return jsonify({'success': False, 'message': 'Reachy SDK not available'})
    
    try:
        reachy = get_reachy()
        if reachy is None:
            return jsonify({'success': False, 'message': 'Cannot connect to Reachy'})
        
        # Turn on the robot arms and head (makes them stiff)
        reachy.turn_on('r_arm')
        reachy.turn_on('l_arm')
        reachy.turn_on('head')
        
        time.sleep(0.5)
        
        # Move to safe starting position - arms slightly raised to prevent falling
        safe_positions = {
            reachy.r_arm.r_shoulder_pitch: 0,
            reachy.r_arm.r_shoulder_roll: -20,
            reachy.r_arm.r_elbow_pitch: -90,
            reachy.l_arm.l_shoulder_pitch: 0,
            reachy.l_arm.l_shoulder_roll: 20,
            reachy.l_arm.l_elbow_pitch: -90,
        }
        
        # Use goto for smooth movement to safe position
        from reachy_sdk.trajectory import goto
        from reachy_sdk.trajectory.interpolation import InterpolationMode
        
        goto(
            goal_positions=safe_positions,
            duration=2.0,
            interpolation_mode=InterpolationMode.MINIMUM_JERK
        )
        
        # Center the head
        reachy.head.look_at(x=0.5, y=0, z=0, duration=1.5)
        
        time.sleep(2.5)  # Wait for movements to complete
        
        compliant_mode_active = True
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [green]Compliant mode ready - all joints locked[/green]")
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]Unlock specific joints to begin positioning[/yellow]")
        
        return jsonify({'success': True, 'message': 'Ready for positioning. Unlock joints to move.'})
        
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
        for joint_name in REACHY_JOINTS:
            joint = get_joint_by_name(reachy, joint_name)
            if joint:
                try:
                    joint.compliant = False
                    log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Stiffened {joint_name}")
                except Exception as e:
                    log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Error stiffening {joint_name}: {e}[/red]")
        
        compliant_mode_active = False
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [green]All joints locked in current position[/green]")
        
        return jsonify({'success': True, 'message': 'All joints stiffened and locked'})
        
    except Exception as e:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Error in stop_compliant: {str(e)}[/red]")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/movement/emergency-stop', methods=['POST'])
def emergency_stop():
    """EMERGENCY: Stiffen all joints, return to safe position, then smoothly power down"""
    global compliant_mode_active
    
    try:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red bold]EMERGENCY STOP INITIATED[/red bold]")
        
        reachy = get_reachy()
        if reachy is None:
            return jsonify({'success': False, 'message': 'Cannot connect to Reachy'})
        
        # Step 1: Immediately stiffen all joints
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]Step 1: Stiffening all joints...[/yellow]")
        for joint_name in REACHY_JOINTS:
            joint = get_joint_by_name(reachy, joint_name)
            if joint:
                try:
                    joint.compliant = False
                except Exception as e:
                    log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Error stiffening {joint_name}: {e}[/red]")
        
        time.sleep(0.5)  # Brief pause to ensure joints are stiff
        
        # Step 2: Return to safe starting position
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]Step 2: Returning to safe position...[/yellow]")
        safe_positions = {
            reachy.r_arm.r_shoulder_pitch: 0,
            reachy.r_arm.r_shoulder_roll: -20,
            reachy.r_arm.r_elbow_pitch: -90,
            reachy.l_arm.l_shoulder_pitch: 0,
            reachy.l_arm.l_shoulder_roll: 20,
            reachy.l_arm.l_elbow_pitch: -90,
        }
        
        goto(
            goal_positions=safe_positions,
            duration=2.0,
            interpolation_mode=InterpolationMode.MINIMUM_JERK
        )
        
        # Center the head
        reachy.head.look_at(x=0.5, y=0, z=0, duration=1.5)
        
        time.sleep(2.5)  # Wait for movements to complete
        
        # Step 3: Smoothly power down
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]Step 3: Powering down safely...[/yellow]")
        reachy.turn_off_smoothly('r_arm')
        reachy.turn_off_smoothly('l_arm')
        reachy.turn_off('head')
        
        compliant_mode_active = False
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [green]EMERGENCY STOP COMPLETE - Robot safely powered down[/green]")
        
        return jsonify({'success': True, 'message': 'Emergency stop complete - robot powered down'})
        
    except Exception as e:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Emergency stop error: {str(e)}[/red]")
        # Still try to power down even if there was an error
        try:
            if reachy:
                reachy.turn_off_smoothly('r_arm')
                reachy.turn_off_smoothly('l_arm')
                reachy.turn_off('head')
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
        
        joint.compliant = not locked
        
        state = "locked" if locked else "unlocked"
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {joint_name} {state}")
        
        return jsonify({'success': True, 'message': f'{joint_name} {state}'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/movement/positions', methods=['GET'])
def get_positions():
    """Get current positions of all joints with detailed logging"""
    try:
        reachy = get_reachy()
        if reachy is None:
            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Failed to get positions - no Reachy connection[/red]")
            return jsonify({'success': False, 'message': 'Cannot connect to Reachy'})
        
        positions = {}
        failed_joints = []
        
        for joint_name in REACHY_JOINTS:
            joint = get_joint_by_name(reachy, joint_name)
            if joint:
                try:
                    pos = joint.present_position
                    positions[joint_name] = round(pos, 2)
                    # Log every 10th position update to avoid spam
                    if hash(joint_name) % 10 == 0:
                        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [dim]{joint_name}: {positions[joint_name]}°[/dim]")
                except Exception as e:
                    positions[joint_name] = 0.0
                    failed_joints.append(joint_name)
                    log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Failed to read {joint_name}: {e}[/red]")
            else:
                positions[joint_name] = 0.0
                failed_joints.append(joint_name)
                log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Joint not found: {joint_name}[/red]")
        
        if failed_joints:
            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]Failed joints: {', '.join(failed_joints)}[/yellow]")
        
        return jsonify({'success': True, 'positions': positions})
        
    except Exception as e:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Error getting positions: {str(e)}[/red]")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/movement/capture', methods=['POST'])
def capture_position():
    """Capture current position of all joints including head orientation"""
    try:
        reachy = get_reachy()
        if reachy is None:
            return jsonify({'success': False, 'message': 'Cannot connect to Reachy'})
        
        positions = {}
        
        # Capture arm joints
        for joint_name in REACHY_JOINTS:
            joint = get_joint_by_name(reachy, joint_name)
            if joint:
                try:
                    positions[joint_name] = round(joint.present_position, 2)
                except:
                    positions[joint_name] = 0.0
        
        # Capture head orientation (get neck joint positions for reference)
        try:
            positions['neck_roll'] = round(reachy.head.neck.neck_roll.present_position, 2)
            positions['neck_pitch'] = round(reachy.head.neck.neck_pitch.present_position, 2)
            positions['neck_yaw'] = round(reachy.head.neck.neck_yaw.present_position, 2)
        except:
            pass  # Head might not be available
        
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [cyan]Position captured[/cyan]")
        
        return jsonify({'success': True, 'positions': positions})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
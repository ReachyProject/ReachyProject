import math
import os
import platform
import subprocess
import sys
from reachy import REACHY_SDK_AVAILABLE
from camera import CAMERA_AVAILABLE

# Handlers
from handlers.index import index_bp 
from handlers.camera import camera_bp
from handlers.api.camera_feed import camera_feed_bp
from handlers.api.camera_status import camera_status_bp
from handlers.api.logs import api_logs_bp
from handlers.logs import logs_bp
from handlers.save_config import save_config_bp
from handlers.update_voice import update_voice_bp
from handlers.api.logs_clear import logs_clear_bp
from handlers.service.action import action_bp
from handlers.service.status import status_bp
from handlers.movement_recorder import movement_recorder_bp
from handlers.api.movement.capture import capture_bp
from handlers.api.movement.joints import joints_bp
from handlers.api.movement.positions import positions_bp
from handlers.api.movement.start_compliant import start_compliant_bp
from handlers.api.movement.stop_compliant import stop_compliant_bp
from handlers.api.movement.emergency_stop import emergency_stop_bp
from handlers.api.movement.toggle_joint import toggle_joint_bp
from handlers.persona_config import persona_config_bp

import cv2 as cv
from dotenv import set_key
from flask import Flask, render_template, request, jsonify, Response

# Reachy SDK imports
try:
    from reachy_sdk import ReachySDK
    from reachy_sdk.trajectory import goto
    from reachy_sdk.trajectory.interpolation import InterpolationMode

    REACHY_SDK_AVAILABLE = True
except ImportError:
    REACHY_SDK_AVAILABLE = False
    ReachySDK = None
    goto = None
    InterpolationMode = None
    print("Warning: reachy_sdk not available. Movement recorder will not function.")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Camera frame provider import
try:
    from FaceTracking.Controllers.frame_publisher import CameraFrameProvider

    CAMERA_AVAILABLE = True
except ImportError:
    CAMERA_AVAILABLE = False
    CameraFrameProvider = None  # type: Optional[any]
    print("Warning: Camera frame provider not available")

app = Flask(__name__)

# Store the process ID of the running tracking system
tracking_process = None  # type: Optional[subprocess.Popen]
running_process = None  # type: Optional[subprocess.Popen]
log_lines = deque(maxlen=500)

# Global variables for Reachy connection
reachy_connection = None
compliant_mode_active = False
initial_positions = {}

PERSONAS = ["Old Man", "Young Man", "Old Woman", "Young Woman", "Child"]
AGE_RANGES = {
    "Old Man": ["60-70", "70-80", "80+"],
    "Young Man": ["18-25", "26-35", "36-45"],
    "Old Woman": ["60-70", "70-80", "80+"],
    "Young Woman": ["18-25", "26-35", "36-45"],
    "Child": ["5-8", "9-12", "13-17"]
}

# ElevenLabs voice IDs per persona
ELEVENLABS_VOICES = {
    "Old Man": "BBfN7Spa3cqLPH1xAS22",
    "Young Man": "zNsotODqUhvbJ5wMG7Ei",
    "Old Woman": "vFLqXa8bgbofGarf6fZh",
    "Young Woman": "GP1bgf0sjoFuuHkyrg8E",
    "Child": "GP1bgf0sjoFuuHkyrg8E"  # fallback to "Young Woman" voice ID
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

REACHY_JOINTS = [
    'r_shoulder_pitch', 'r_shoulder_roll', 'r_arm_yaw', 'r_elbow_pitch',
    'r_forearm_yaw', 'r_wrist_pitch', 'r_wrist_roll', 'r_gripper',
    'l_shoulder_pitch', 'l_shoulder_roll', 'l_arm_yaw', 'l_elbow_pitch',
    'l_forearm_yaw', 'l_wrist_pitch', 'l_wrist_roll', 'l_gripper',
    'l_antenna', 'r_antenna',
    'neck_yaw', 'neck_roll', 'neck_pitch'
]


def write_to_env(persona, age_range, mood, llm_provider, llm_model):
    """Write configuration to .env file"""
    env_path = Path('.env')

    voice_id = ELEVENLABS_VOICES.get(persona, "")

    env_content = f"""PERSONA={persona}
    AGE_RANGE={age_range}
    MOOD={mood}
    LLM_PROVIDER={llm_provider}
    LLM_MODEL={llm_model}
    VOICE_ID={voice_id}
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
            reachy_connection = ReachySDK(host='128.39.142.134')
            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [green]Connected to Reachy[/green]")
        except Exception as e:
            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Failed to connect to Reachy: {e}[/red]")
            return None
    return reachy_connection


def get_joint_by_name(robot, joint):
    """Get a joint object from Reachy by name"""
    try:
        # Handle arm joints
        if joint.startswith('r_') and joint != 'r_antenna':
            return getattr(robot.r_arm, joint, None)
        elif joint.startswith('l_') and joint != 'l_antenna':
            return getattr(robot.l_arm, joint, None)
        # Handle antenna joints
        elif joint == 'l_antenna':
            return getattr(robot.head, 'l_antenna', None)
        elif joint == 'r_antenna':
            return getattr(robot.head, 'r_antenna', None)
        # Handle neck joints
        elif joint == 'neck_yaw':
            return robot.head.neck_yaw
        elif joint == 'neck_roll':
            return robot.head.neck_roll
        elif joint == 'neck_pitch':
            return robot.head.neck_pitch
        else:
            return None
    except Exception as e:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error getting joint {joint}: {e}")
        return None


# ==================== CAMERA ROUTES ====================

def get_camera_frame_path():
    """Get the platform-appropriate camera frame path"""
    if platform.system() == 'Windows':
        temp_dir = Path(tempfile.gettempdir()) / "reachy_frames"
    else:
        temp_dir = Path("/tmp/reachy_frames")

    return temp_dir / "reachy_camera_frame.jpg"


def generate_camera_frames():
    """Generator for camera video stream with error recovery"""
    consecutive_errors = 0
    max_errors = 10
    error_logged = False  # Add this flag

    while True:
        if not CAMERA_AVAILABLE:
            time.sleep(0.1)  # Add small delay
            continue

        try:
            frame, _ = CameraFrameProvider.get_latest_frame()

            if frame is None:
                consecutive_errors += 1

                # Only log the first error to avoid spam
                if not error_logged and consecutive_errors == 1:
                    log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]Waiting for camera frames...[/yellow]")
                    error_logged = True

                if consecutive_errors > max_errors:
                    log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Camera frame timeout[/red]")
                    break

                time.sleep(0.1)  # Wait before retrying
                continue

            # Reset error counter and flag on success
            if error_logged and consecutive_errors > 0:
                log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [green]Camera frames available[/green]")
                error_logged = False

            consecutive_errors = 0

            # Encode frame
            ret, jpeg = cv.imencode('.jpg', frame, [cv.IMWRITE_JPEG_QUALITY, 85])

            if not ret:
                continue

            frame_data = jpeg.tobytes()

            # Yield with proper MJPEG boundary
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n'
                   b'Content-Length: ' + str(len(frame_data)).encode() + b'\r\n'
                                                                         b'\r\n' + frame_data + b'\r\n')

        except GeneratorExit:
            # Client disconnected
            break
        except Exception as e:
            consecutive_errors += 1
            if consecutive_errors > max_errors:
                log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Stream error: {str(e)}[/red]")
                break
            time.sleep(0.1)  # Wait before retrying


@app.route('/api/camera/feed')
def camera_feed():
    """Live MJPEG camera stream"""
    try:
        return Response(
            generate_camera_frames(),
            mimetype='multipart/x-mixed-replace; boundary=frame',
            headers={
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0',
                'Connection': 'close'
            }
        )
    except Exception as e:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Camera feed error: {str(e)}[/red]")
        return Response("Camera feed error", status=500)


@app.route('/api/camera/status')
def camera_status():
    """Check if camera feed is available"""
    if not CAMERA_AVAILABLE:
        return jsonify({
            'status': 'unavailable',
            'available': False,
            'message': 'Camera module not loaded'
        }), 503

    is_available = CameraFrameProvider.is_available()

    if is_available:
        _, metadata = CameraFrameProvider.get_latest_frame()

        # Get platform-specific temp directory info
        temp_dir = CameraFrameProvider.get_temp_directory()

        return jsonify({
            'status': 'online',
            'available': True,
            'metadata': metadata,
            'platform': platform.system(),
            'temp_directory': str(temp_dir)
        })
    else:
        return jsonify({
            'status': 'offline',
            'available': False,
            'message': 'Face tracking service not running',
            'platform': platform.system()
        }), 503


@app.route('/camera')
def camera_page():
    """Dedicated camera view page"""
    return render_template('camera.html')


@app.route('/api/camera/info')
def camera_info():
    """Get information about camera frame storage location"""
    if not CAMERA_AVAILABLE:
        return jsonify({
            'available': False,
            'message': 'Camera module not loaded'
        }), 503

    temp_dir = CameraFrameProvider.get_temp_directory()
    frame_path = CameraFrameProvider.FRAME_PATH

    return jsonify({
        'platform': platform.system(),
        'temp_directory': str(temp_dir),
        'frame_path': str(frame_path),
        'frame_exists': frame_path.exists(),
        'is_available': CameraFrameProvider.is_available()
    })


@app.route('/api/camera/diagnostics')
def camera_diagnostics():
    """Detailed diagnostics for the camera system"""
    if not CAMERA_AVAILABLE:
        return jsonify({
            'available': False,
            'message': 'Camera module not loaded'
        })

    temp_dir = CameraFrameProvider.get_temp_directory()
    frame_path = CameraFrameProvider.FRAME_PATH
    metadata_path = CameraFrameProvider.METADATA_PATH

    diagnostics = {
        'platform': platform.system(),
        'temp_directory': str(temp_dir),
        'temp_dir_exists': temp_dir.exists(),
        'frame': {
            'path': str(frame_path),
            'exists': frame_path.exists(),
            'size_bytes': frame_path.stat().st_size if frame_path.exists() else 0,
            'last_modified': frame_path.stat().st_mtime if frame_path.exists() else None
        },
        'metadata': {
            'path': str(metadata_path),
            'exists': metadata_path.exists()
        },
        'is_available': CameraFrameProvider.is_available()
    }

    # Add frame age if available
    if frame_path.exists():
        age = time.time() - frame_path.stat().st_mtime
        diagnostics['frame']['age_seconds'] = round(age, 2)
        diagnostics['frame']['is_recent'] = age < 2.0

    return jsonify(diagnostics)


# ==================== TRACKING CONTROL ROUTES ====================
@app.route('/api/tracking/control/<action>', methods=['POST'])
def tracking_control(action):
    """Control the face tracking system (start/stop/restart)"""
    global tracking_process

    try:
        if action == 'start':
            if tracking_process is not None and tracking_process.poll() is None:
                return jsonify({'success': False, 'message': 'Tracking is already running'})

            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'

            tracking_process = subprocess.Popen(
                [sys.executable, '-u', 'main.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace',
                env=env
            )

            thread = threading.Thread(target=read_process_output, args=(tracking_process,))
            thread.daemon = True
            thread.start()

            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [green]Face tracking started[/green]")
            return jsonify({'success': True, 'message': 'Face tracking started'})

        elif action == 'stop':
            if tracking_process is None or tracking_process.poll() is not None:
                return jsonify({'success': False, 'message': 'Tracking is not running'})

            tracking_process.terminate()
            try:
                tracking_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                tracking_process.kill()
                tracking_process.wait()

            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Face tracking stopped[/red]")
            return jsonify({'success': True, 'message': 'Face tracking stopped'})

        elif action == 'restart':
            # Stop if running
            if tracking_process is not None and tracking_process.poll() is None:
                tracking_process.terminate()
                try:
                    tracking_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    tracking_process.kill()
                    tracking_process.wait()
                log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]"
                                 f" [yellow]Tracking stopped for restart[/yellow]")

            # Start again
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'

            tracking_process = subprocess.Popen(
                [sys.executable, '-u', 'main.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace',
                env=env
            )

            thread = threading.Thread(target=read_process_output, args=(tracking_process,))
            thread.daemon = True
            thread.start()

            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [green]Face tracking restarted[/green]")
            return jsonify({'success': True, 'message': 'Face tracking restarted'})

        else:
            return jsonify({'success': False, 'message': 'Invalid action'})

    except Exception as e:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Tracking control error: {str(e)}[/red]")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/tracking/status', methods=['GET'])
def tracking_status():
    """Get the current status of the face tracking system"""
    if tracking_process is not None and tracking_process.poll() is None:
        return jsonify({'running': True})
    return jsonify({'running': False})


# ==================== ORIGINAL ROUTES ====================
@app.route('/')
def index():
    voice_mappings = {
        "Old Man": "BBfN7Spa3cqLPH1xAS22",
        "Young Man": "zNsotODqUhvbJ5wMG7Ei",
        "Old Woman": "vFLqXa8bgbofGarf6fZh",
        "Young Woman": "GP1bgf0sjoFuuHkyrg8E",
        "Child": None  # No child voice available
    }

    return render_template('index.html',
                           personas=list(voice_mappings.keys()),
                           voice_mappings=voice_mappings,
                           age_ranges=AGE_RANGES,
                           moods=MOODS,
                           llm_providers=LLM_PROVIDERS,
                           llm_models=LLM_MODELS)


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


@app.route('/save_config', methods=['POST'])
def save_config():
    try:
        data = request.json
        persona = data.get('persona')
        age_range = data.get('age_range')
        mood = data.get('mood')
        llm_provider = data.get('llm_provider')
        llm_model = data.get('llm_model')

        # Save config and get the voice ID
        voice_id = ELEVENLABS_VOICES.get(persona, "")
        write_to_env(persona, age_range, mood, llm_provider, llm_model)

        return jsonify({
            'success': True,
            'message': 'Configuration saved',
            'voice_id': voice_id
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/service/<action>', methods=['POST'])
def service_control(action):
    global running_process

    try:
        if action == 'start':
            if running_process is not None and running_process.poll() is None:
                return jsonify({'success': False, 'message': 'Service is already running'})

            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'

            from dotenv import load_dotenv
            load_dotenv()

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
            if running_process is None or running_process.poll() is not None:
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
            if running_process is not None and running_process.poll() is None:
                running_process.terminate()
                try:
                    running_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    running_process.kill()
                    running_process.wait()
                log_lines.append(
                    f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]↻ Service stopped for restart[/yellow]")

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
    if running_process is not None and running_process.poll() is None:
        return jsonify({'running': True})
    return jsonify({'running': False})

app.register_blueprint(index_bp)
app.register_blueprint(update_voice_bp)
app.register_blueprint(logs_bp)
app.register_blueprint(api_logs_bp)
app.register_blueprint(logs_clear_bp)
app.register_blueprint(save_config_bp)
app.register_blueprint(action_bp)
app.register_blueprint(status_bp)
app.register_blueprint(persona_config_bp)

# ==================== MOVEMENT RECORDER ROUTES ====================

@app.route('/movement-recorder')
def movement_recorder():
    return render_template('movement_recorder.html')


@app.route('/api/movement/joints', methods=['GET'])
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


@app.route('/api/movement/start-compliant', methods=['POST'])
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


@app.route('/api/movement/stop-compliant', methods=['POST'])
def stop_compliant_mode():
    """Stop compliant mode - lock all joints in place (stiffen)"""
    global compliant_mode_active

    try:
        robot = get_reachy()
        if robot is None:
            return jsonify({'success': False, 'message': 'Cannot connect to Reachy'})

        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]Stiffening all joints...[/yellow]")

        # Stiffen all joints by setting them non-compliant
        stiffened_joints = []
        for joint in REACHY_JOINTS:
            joint = get_joint_by_name(robot, joint)
            if joint:
                try:
                    joint.compliant = False
                    stiffened_joints.append(joint)
                    log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Stiffened {joint}")
                except Exception as e:
                    log_lines.append(
                        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Error stiffening {joint}: {e}[/red]")

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

    robot = None

    try:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red bold]EMERGENCY STOP INITIATED[/red bold]")

        robot = get_reachy()
        if robot is None:
            return jsonify({'success': False, 'message': 'Cannot connect to Reachy'})

        # Step 1: Immediately stiffen all joints
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]Step 1: Stiffening all joints...[/yellow]")
        stiffened_joints = []
        for joint_name in REACHY_JOINTS:
            joint = get_joint_by_name(robot, joint_name)
            if joint:
                try:
                    joint.compliant = False
                    stiffened_joints.append(joint_name)
                except (AttributeError, RuntimeError) as e:
                    log_lines.append(
                        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Error stiffening {joint_name}: {e}[/red]")

        time.sleep(0.5)

        # Step 2: Return to INITIAL positions (where we started)
        log_lines.append(
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]Step 2: Returning to initial position...[/yellow]")

        if initial_positions:
            # Build goal_positions dict from initial positions
            goal_positions = {}

            # Right arm
            if 'r_shoulder_pitch' in initial_positions:
                goal_positions[robot.r_arm.r_shoulder_pitch] = initial_positions['r_shoulder_pitch']
            if 'r_shoulder_roll' in initial_positions:
                goal_positions[robot.r_arm.r_shoulder_roll] = initial_positions['r_shoulder_roll']
            if 'r_arm_yaw' in initial_positions:
                goal_positions[robot.r_arm.r_arm_yaw] = initial_positions['r_arm_yaw']
            if 'r_elbow_pitch' in initial_positions:
                goal_positions[robot.r_arm.r_elbow_pitch] = initial_positions['r_elbow_pitch']
            if 'r_forearm_yaw' in initial_positions:
                goal_positions[robot.r_arm.r_forearm_yaw] = initial_positions['r_forearm_yaw']
            if 'r_wrist_pitch' in initial_positions:
                goal_positions[robot.r_arm.r_wrist_pitch] = initial_positions['r_wrist_pitch']
            if 'r_wrist_roll' in initial_positions:
                goal_positions[robot.r_arm.r_wrist_roll] = initial_positions['r_wrist_roll']

            # Left arm
            if 'l_shoulder_pitch' in initial_positions:
                goal_positions[robot.l_arm.l_shoulder_pitch] = initial_positions['l_shoulder_pitch']
            if 'l_shoulder_roll' in initial_positions:
                goal_positions[robot.l_arm.l_shoulder_roll] = initial_positions['l_shoulder_roll']
            if 'l_arm_yaw' in initial_positions:
                goal_positions[robot.l_arm.l_arm_yaw] = initial_positions['l_arm_yaw']
            if 'l_elbow_pitch' in initial_positions:
                goal_positions[robot.l_arm.l_elbow_pitch] = initial_positions['l_elbow_pitch']
            if 'l_forearm_yaw' in initial_positions:
                goal_positions[robot.l_arm.l_forearm_yaw] = initial_positions['l_forearm_yaw']
            if 'l_wrist_pitch' in initial_positions:
                goal_positions[robot.l_arm.l_wrist_pitch] = initial_positions['l_wrist_pitch']
            if 'l_wrist_roll' in initial_positions:
                goal_positions[robot.l_arm.l_wrist_roll] = initial_positions['l_wrist_roll']

            # Neck joints
            if 'neck_yaw' in initial_positions:
                goal_positions[robot.head.neck_yaw] = initial_positions['neck_yaw']
            if 'neck_roll' in initial_positions:
                goal_positions[robot.head.neck_roll] = initial_positions['neck_roll']
            if 'neck_pitch' in initial_positions:
                goal_positions[robot.head.neck_pitch] = initial_positions['neck_pitch']

            if goal_positions:
                goto(
                    goal_positions=goal_positions,
                    duration=2.0,
                    interpolation_mode=InterpolationMode.MINIMUM_JERK
                )
                log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [cyan]Returned to initial positions[/cyan]")
        else:
            log_lines.append(
                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                f"[yellow]No initial positions stored, staying in place[/yellow]")

        time.sleep(2.5)

        # Step 3: Smoothly power down
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]Step 3: Powering down safely...[/yellow]")
        robot.turn_off_smoothly('r_arm')
        robot.turn_off_smoothly('l_arm')
        robot.turn_off_smoothly('head')

        compliant_mode_active = False
        initial_positions = {}  # Clear stored positions
        log_lines.append(
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]"
            f" [green]EMERGENCY STOP COMPLETE - Robot safely powered down[/green]")

        return jsonify({
            'success': True,
            'message': 'Emergency stop complete - robot powered down',
            'stiffened_joints': stiffened_joints
        })

    except (OSError, AttributeError, RuntimeError) as e:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Emergency stop error: {str(e)}[/red]")
        try:
            if robot is not None:
                robot.turn_off_smoothly('r_arm')
                robot.turn_off_smoothly('l_arm')
                robot.turn_off_smoothly('head')
        except (AttributeError, RuntimeError):
            pass
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/movement/toggle-joint', methods=['POST'])
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


@app.route('/api/movement/positions', methods=['GET'])
def get_positions():
    """Get current positions of all joints with NaN handling"""
    try:
        robot = get_reachy()
        if robot is None:
            return jsonify({'success': False, 'message': 'Cannot connect to Reachy'})

        positions = {}
        nan_count = 0

        for joint in REACHY_JOINTS:
            joint = get_joint_by_name(robot, joint)
            if joint:
                try:
                    pos = joint.present_position

                    # Proper NaN check
                    if pos is None or math.isnan(pos):
                        positions[joint] = 0.0
                        nan_count += 1
                    else:
                        positions[joint] = round(float(pos), 2)

                except (AttributeError, TypeError, ValueError):
                    positions[joint] = 0.0
            else:
                positions[joint] = 0.0

        # Only log if we have NaN issues (and not too frequently)
        if nan_count > 0 and nan_count == len(REACHY_JOINTS):
            log_lines.append(
                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Warning: All joints returning NaN values[/red]")

        return jsonify({'success': True, 'positions': positions})

    except Exception as e:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Error getting positions: {str(e)}[/red]")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/movement/capture', methods=['GET'])
def capture_position():
    """Capture current position of all joints"""
    try:
        robot = get_reachy()
        if robot is None:
            return jsonify({'success': False, 'message': 'Cannot connect to Reachy'})

        positions = {}
        nan_count = 0

        for joint_name in REACHY_JOINTS:
            joint = get_joint_by_name(robot, joint_name)
            if joint:
                try:
                    pos = joint.present_position

                    if pos is None or math.isnan(pos):
                        positions[joint_name] = 0.0
                        nan_count += 1
                    else:
                        positions[joint_name] = round(float(pos), 2)

                except (AttributeError, ValueError, TypeError):
                    positions[joint_name] = 0.0
                    nan_count += 1

        if nan_count > 0:
            log_lines.append(
                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]"
                f" [yellow]Position captured ({nan_count} NaN values replaced with 0.0)[/yellow]")
        else:
            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [cyan]Position captured successfully[/cyan]")

        return jsonify({'success': True, 'positions': positions})

    except OSError as e:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Capture error: {str(e)}[/red]")
        return jsonify({'success': False, 'message': str(e)})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

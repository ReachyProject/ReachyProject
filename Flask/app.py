from collections import deque
from flask import Flask, render_template, request, jsonify, Response
import os
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


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Camera frame provider import
try:
    from FaceTracking.Controllers.frame_publisher import CameraFrameProvider
    CAMERA_AVAILABLE = True
except ImportError:
    CAMERA_AVAILABLE = False
    print("Warning: Camera frame provider not available")
if not REACHY_SDK_AVAILABLE:
    print("Warning: reachy_sdk not available. Movement recorder will not function.")

if not CAMERA_AVAILABLE:
    print("Camera frame provider not available")
    

app = Flask(__name__)

# Store the process ID of the running tracking system
tracking_process = None
running_process = None
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
    "Child": "GP1bgf0sjoFuuHkyrg8E" # fallback to "Young Woman" voice ID
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

def generate_camera_frames():
    """Generator for camera video stream with error recovery"""
    consecutive_errors = 0
    max_errors = 10
    
    while True:
        if not CAMERA_AVAILABLE:
            continue
        
        try:
            frame, metadata = CameraFrameProvider.get_latest_frame()
            
            if frame is None:
                consecutive_errors += 1
                if consecutive_errors > max_errors:
                    log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Too many failed frame reads[/red]")
                    break
                continue
            
            # Reset error counter on success
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
        return jsonify({
            'status': 'online',
            'available': True,
            'metadata': metadata
        })
    else:
        return jsonify({
            'status': 'offline',
            'available': False,
            'message': 'Face tracking service not running'
        }), 503

@app.route('/camera')
def camera_page():
    """Dedicated camera view page"""
    return render_template('camera.html')


# ==================== CAMERA ROUTES ====================

app.register_blueprint(camera_feed_bp)
app.register_blueprint(camera_status_bp)
app.register_blueprint(camera_bp)

# ==================== ORIGINAL ROUTES ====================

app.register_blueprint(index_bp)
app.register_blueprint(update_voice_bp)
app.register_blueprint(logs_bp)
app.register_blueprint(api_logs_bp)
app.register_blueprint(logs_clear_bp)
app.register_blueprint(save_config_bp)
app.register_blueprint(action_bp)
app.register_blueprint(status_bp)

# ==================== MOVEMENT RECORDER ROUTES ====================

app.register_blueprint(movement_recorder_bp)
app.register_blueprint(joints_bp)
app.register_blueprint(start_compliant_bp)
app.register_blueprint(stop_compliant_bp)
app.register_blueprint(emergency_stop_bp)
app.register_blueprint(toggle_joint_bp)
app.register_blueprint(positions_bp)
app.register_blueprint(capture_bp)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
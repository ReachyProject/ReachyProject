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
from handlers.persona_config import persona_config_bp


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

if not REACHY_SDK_AVAILABLE:
    print("Warning: reachy_sdk not available. Movement recorder will not function.")

if not CAMERA_AVAILABLE:
    print("Camera frame provider not available")
    

app = Flask(__name__)


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
app.register_blueprint(persona_config_bp)

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

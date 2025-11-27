from flask import Flask, render_template, request, jsonify, Response
import os
import sys

from Flask.handlers.macro_recorder import macro_recorder_bp
from Flask.reachy import REACHY_SDK_AVAILABLE
from Flask.camera import CAMERA_AVAILABLE

# Handlers
from Flask.handlers.macro_recorder import macro_recorder_bp
from Flask.handlers.index import index_bp
from Flask.handlers.camera import camera_bp
from Flask.handlers.api.camera_feed import camera_feed_bp
from Flask.handlers.api.camera_status import camera_status_bp
from Flask.handlers.api.logs import api_logs_bp
from Flask.handlers.logs import logs_bp
from Flask.handlers.save_config import save_config_bp
from Flask.handlers.api.logs_clear import logs_clear_bp
from Flask.handlers.service.action import action_bp
from Flask.handlers.service.status import status_bp
from Flask.handlers.movement_recorder import movement_recorder_bp
from Flask.handlers.api.movement.capture import capture_bp
from Flask.handlers.api.movement.joints import joints_bp
from Flask.handlers.api.movement.positions import positions_bp
from Flask.handlers.api.movement.start_compliant import start_compliant_bp
from Flask.handlers.api.movement.stop_compliant import stop_compliant_bp
from Flask.handlers.api.movement.emergency_stop import emergency_stop_bp
from Flask.handlers.api.movement.toggle_joint import toggle_joint_bp
from Flask.handlers.persona_config import persona_config_bp

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
app.register_blueprint(logs_bp)
app.register_blueprint(api_logs_bp)
app.register_blueprint(logs_clear_bp)
app.register_blueprint(save_config_bp)
app.register_blueprint(action_bp)
app.register_blueprint(status_bp)
app.register_blueprint(persona_config_bp)

# ==================== MOVEMENT RECORDER ROUTES ====================

app.register_blueprint(movement_recorder_bp)
app.register_blueprint(macro_recorder_bp)
app.register_blueprint(joints_bp)
app.register_blueprint(start_compliant_bp)
app.register_blueprint(stop_compliant_bp)
app.register_blueprint(emergency_stop_bp)
app.register_blueprint(toggle_joint_bp)
app.register_blueprint(positions_bp)
app.register_blueprint(capture_bp)

@app.context_processor
def inject_active_page():
    return dict(active_page=request.path)

def run():
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)

if __name__ == '__main__':
    run()

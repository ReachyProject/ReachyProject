import os
import sys
from flask import Flask

from reachy import REACHY_SDK_AVAILABLE
from camera import CAMERA_AVAILABLE

from blueprints.original_routes import original_routes_bp
from blueprints.camera_routes import camera_routes_bp
from blueprints.movement_recorder_routes_bp import movement_recorder_routes_bp
from blueprints.tracking_control_routes import tracking_control_routes_bp

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


if not REACHY_SDK_AVAILABLE:
    print("Warning: reachy_sdk not available. Movement recorder will not function.")

if not CAMERA_AVAILABLE:
    print("Warning: Camera frame provider not available")


app = Flask(__name__)

# Register Blueprints
app.register_blueprint(original_routes_bp)
app.register_blueprint(camera_routes_bp)
app.register_blueprint(movement_recorder_routes_bp)
app.register_blueprint(tracking_control_routes_bp)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

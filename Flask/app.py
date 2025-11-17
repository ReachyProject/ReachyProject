import os
import sys
from flask import Flask

from reachy import REACHY_SDK_AVAILABLE
from camera import CAMERA_AVAILABLE

from handlers.macro_recorder import macro_recorder_bp
from blueprints.original_routes import original_routes_bp
from blueprints.camera_routes import camera_routes_bp
from blueprints.movement_recorder_routes_bp import movement_recorder_routes_bp
from blueprints.tracking_control_routes import tracking_control_routes_bp


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
app.register_blueprint(macro_recorder_bp)


@app.context_processor
def inject_active_page():
    return dict(active_page=request.path)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

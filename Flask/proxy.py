from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit
from flask_cors import CORS, cross_origin
import time
import os

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app, resources={r"/state": {"origins": "http://localhost:5000"}})

app.config['SECRET_KEY'] = 'reachy-proxy-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# In-memory joint state
JOINT_STATE = {}
LAST_UPDATED = time.time()

@app.route('/')
def index():
    # serve a simple page (proxy.html must be placed in templates/)
    return send_from_directory('templates', 'proxy.html')

@app.route('/status')
def status():
    return jsonify({
        'success': True,
        'proxy': True,
        'timestamp': time.time(),
        'clients': len(socketio.server.manager.get_participants('/', '/')) if hasattr(socketio.server, 'manager') else 0
    })

@app.route('/state')
@cross_origin()
def get_state():
    return jsonify({
        'success': True,
        'positions': JOINT_STATE,
        'timestamp': LAST_UPDATED
    })

# Serve static files for client JS/CSS if needed
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

# Socket.IO events
@socketio.on('connect')
def handle_connect():
    sid = request.sid if request else 'unknown'
    print(f"[proxy] client connected: {sid}")
    # send current state to newly connected client
    emit('robot_state', {
        'positions': JOINT_STATE,
        'timestamp': LAST_UPDATED
    })

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid if request else 'unknown'
    print(f"[proxy] client disconnected: {sid}")

@socketio.on('joint_update')
def handle_joint_update(data):
    """
    Expect data: { joint: 'l_wrist', angle: 12.3, origin: 'proxy' (optional) }
    Broadcast to all clients except sender.
    """
    joint = data.get('joint')
    angle = data.get('angle')
    origin = data.get('origin', 'unknown')
    if joint is None or angle is None:
        emit('error', {'message': 'Missing joint or angle'})
        return
    JOINT_STATE[joint] = float(angle)
    global LAST_UPDATED
    LAST_UPDATED = time.time()
    # Broadcast update
    emit('mirror_update', {'joint': joint, 'angle': JOINT_STATE[joint], 'origin': origin, 'timestamp': LAST_UPDATED}, broadcast=True, include_self=False)

@socketio.on('set_multiple_joints')
def handle_set_multiple_joints(data):
    positions = data.get('positions', {})
    if not isinstance(positions, dict):
        emit('error', {'message': 'positions must be object'})
        return
    for j, a in positions.items():
        JOINT_STATE[j] = float(a)
    global LAST_UPDATED
    LAST_UPDATED = time.time()
    emit('multiple_mirror_update', {'positions': positions, 'origin': data.get('origin','unknown'), 'timestamp': LAST_UPDATED}, broadcast=True, include_self=False)

@socketio.on('request_state')
def handle_request_state():
    emit('robot_state', {'positions': JOINT_STATE, 'timestamp': LAST_UPDATED})

if __name__ == '__main__':
    # ensure templates/static directories exist
    if not os.path.exists('templates'):
        os.makedirs('templates')
    if not os.path.exists('static'):
        os.makedirs('static')
    print("Starting proxy server on http://0.0.0.0:5001")
    socketio.run(app, host='0.0.0.0', port=5001, debug=True, allow_unsafe_werkzeug=True)
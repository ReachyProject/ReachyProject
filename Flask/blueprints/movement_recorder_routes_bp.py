from flask import Blueprint

from handlers.movement_recorder import movement_recorder
from handlers.api.movement.joints import get_joints
from handlers.api.movement.toggle_joint import toggle_joint
from handlers.api.movement.positions import get_positions
from handlers.api.movement.capture import capture_position
from handlers.api.movement.start_compliant import start_compliant_mode
from handlers.api.movement.stop_compliant import stop_compliant_mode

movement_recorder_routes_bp = Blueprint('movement_recorder_routes', __name__)

movement_recorder_routes_bp.route('/movement-recorder')(movement_recorder)
movement_recorder_routes_bp.route('/api/movement/joints', methods=['GET'])(get_joints)
movement_recorder_routes_bp.route('/api/movement/toggle-joint', methods=['POST'])(toggle_joint) 
movement_recorder_routes_bp.route('/api/movement/positions', methods=['GET'])(get_positions)
movement_recorder_routes_bp.route('/api/movement/capture', methods=['GET'])(capture_position)
movement_recorder_routes_bp.route('/api/movement/start_compliant', 
                                  methods=['POST'])(start_compliant_mode)
movement_recorder_routes_bp.route('/api/movement/stop_compliant', 
                                  methods=['POST'])(stop_compliant_mode)

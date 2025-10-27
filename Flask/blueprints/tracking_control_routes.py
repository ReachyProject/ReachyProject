from flask import Blueprint

from handlers.api.tracking.control.action import tracking_control
from handlers.api.tracking.status import tracking_status

tracking_control_routes_bp = Blueprint('tracking_control_routes', __name__)

tracking_control_routes_bp.route('/api/tracking/control/<action>', methods=['POST'])(tracking_control)
tracking_control_routes_bp.route('/api/tracking/status', methods=['GET'])(tracking_status)

from flask import Blueprint

from handlers.camera import camera_page
from handlers.api.camera.diagnostics import camera_diagnostics
from handlers.api.camera.status import camera_status
from handlers.api.camera.info import camera_info
from handlers.api.camera.feed import camera_feed


camera_routes_bp = Blueprint('camera_routes', __name__)

camera_routes_bp.route('/camera')(camera_page)
camera_routes_bp.route('/api/camera/diagnostics')(camera_diagnostics)
camera_routes_bp.route('/api/camera/status')(camera_status)
camera_routes_bp.route('/api/camera/info')(camera_info)
camera_routes_bp.route('/api/camera/feed')(camera_feed)

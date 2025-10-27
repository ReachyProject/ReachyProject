from flask import Blueprint

from handlers.index import index
from handlers.update_voice import update_voice
from handlers.logs import logs
from handlers.api.logs import get_logs
from handlers.api.log.clear import clear_logs
from handlers.save_config import save_config
from handlers.service.action import service_control
from handlers.service.status import service_status

original_routes_bp = Blueprint('original_routes', __name__)

original_routes_bp.route('/')(index)
original_routes_bp.route('/update_voice', methods=['POST'])(update_voice)
original_routes_bp.route('/logs')(logs)
original_routes_bp.route('/api/logs')(get_logs)
original_routes_bp.route('/api/logs/clear', methods=['POST'])(clear_logs)
original_routes_bp.route('/save_config', methods=['POST'])(save_config)
original_routes_bp.route('/service/<action>', methods=['POST'])(service_control)
original_routes_bp.route('/service/status', methods=['GET'])(service_status)



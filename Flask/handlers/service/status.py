
from flask import jsonify
from global_variables import running_process


def service_status():
    if running_process is not None and running_process.poll() is None:
        return jsonify({'running': True})
    return jsonify({'running': False})


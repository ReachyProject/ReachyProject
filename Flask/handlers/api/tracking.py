
import os
import subprocess
import sys
import threading
import time
from flask import Blueprint, jsonify
from handlers.service.action import read_process_output
from global_variables import log_lines, tracking_process


tracking_bp = Blueprint('tracking', __name__)

@tracking_bp.route('/api/tracking/control/<action>', methods=['POST'])
def tracking_control(action):
    """Control the face tracking system (start/stop/restart)"""
    global tracking_process

    try:
        if action == 'start':
            if tracking_process is not None and tracking_process.poll() is None:
                return jsonify({'success': False, 'message': 'Tracking is already running'})

            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'

            tracking_process = subprocess.Popen(
                [sys.executable, '-u', 'Flask/FaceTracking/main.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace',
                env=env
            )

            thread = threading.Thread(target=read_process_output, args=(tracking_process,))
            thread.daemon = True
            thread.start()

            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [green]Face tracking started[/green]")
            return jsonify({'success': True, 'message': 'Face tracking started'})

        elif action == 'stop':
            if tracking_process is None or tracking_process.poll() is not None:
                return jsonify({'success': False, 'message': 'Tracking is not running'})

            tracking_process.terminate()
            try:
                tracking_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                tracking_process.kill()
                tracking_process.wait()

            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Face tracking stopped[/red]")
            return jsonify({'success': True, 'message': 'Face tracking stopped'})

        elif action == 'restart':
            # Stop if running
            if tracking_process is not None and tracking_process.poll() is None:
                tracking_process.terminate()
                try:
                    tracking_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    tracking_process.kill()
                    tracking_process.wait()
                log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]"
                                 f" [yellow]Tracking stopped for restart[/yellow]")

            # Start again
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'

            tracking_process = subprocess.Popen(
                [sys.executable, '-u', 'main.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace',
                env=env
            )

            thread = threading.Thread(target=read_process_output, args=(tracking_process,))
            thread.daemon = True
            thread.start()

            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [green]Face tracking restarted[/green]")
            return jsonify({'success': True, 'message': 'Face tracking restarted'})

        else:
            return jsonify({'success': False, 'message': 'Invalid action'})

    except Exception as e:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]Tracking control error: {str(e)}[/red]")
        return jsonify({'success': False, 'message': str(e)})
    
@tracking_bp.route('/api/tracking/status', methods=['GET'])
def service_status():
    global tracking_process
    if tracking_process is not None and tracking_process.poll() is None:
        return jsonify({'running': True})
    return jsonify({'running': False})
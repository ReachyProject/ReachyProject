from flask import jsonify
import subprocess
import sys
import threading
import os
import time
from process_output import read_process_output
from global_variables import log_lines, running_process


def service_control(action):
    global running_process

    try:
        if action == 'start':
            if running_process is not None and running_process.poll() is None:
                return jsonify({'success': False, 'message': 'Service is already running'})

            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'

            from dotenv import load_dotenv
            load_dotenv()

            running_process = subprocess.Popen(
                [sys.executable, '-u', 'main.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace',
                env=env
            )

            thread = threading.Thread(target=read_process_output, args=(running_process,))
            thread.daemon = True
            thread.start()

            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [green]✓ Service started[/green]")
            return jsonify({'success': True, 'message': 'Reachy service started'})

        elif action == 'stop':
            if running_process is None or running_process.poll() is not None:
                return jsonify({'success': False, 'message': 'Service is not running'})

            running_process.terminate()
            try:
                running_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                running_process.kill()
                running_process.wait()

            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [red]■ Service stopped[/red]")
            return jsonify({'success': True, 'message': 'Reachy service stopped'})

        elif action == 'restart':
            if running_process is not None and running_process.poll() is None:
                running_process.terminate()
                try:
                    running_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    running_process.kill()
                    running_process.wait()
                log_lines.append(
                    f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]↻ Service stopped for restart[/yellow]")

            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'

            running_process = subprocess.Popen(
                [sys.executable, '-u', 'main.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace',
                env=env
            )

            thread = threading.Thread(target=read_process_output, args=(running_process,))
            thread.daemon = True
            thread.start()

            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [green]✓ Service restarted[/green]")
            return jsonify({'success': True, 'message': 'Reachy service restarted'})

        else:
            return jsonify({'success': False, 'message': 'Invalid action'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    
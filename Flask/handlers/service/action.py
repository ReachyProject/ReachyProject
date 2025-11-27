from flask import Blueprint, request, jsonify
import subprocess
import sys
import threading
import os
import time
from Flask.global_variables import log_lines, running_process


def read_process_output(process):
    """Read output from process and store in log_lines"""
    global log_lines
    try:
        while True:
            line = process.stdout.readline()
            if not line:
                break
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            log_lines.append(f"[{timestamp}] {line.strip()}")
    except Exception as e:
        log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error reading output: {str(e)}")


action_bp = Blueprint('action', __name__)

@action_bp.route('/service/<action>', methods=['POST'])
def service_control(action):
    global running_process
    
    try:
        if action == 'start':
            if running_process and running_process.poll() is None:
                return jsonify({'success': False, 'message': 'Service is already running'})
            
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'

            from dotenv import load_dotenv
            load_dotenv()
            VOICE_ID = os.getenv("VOICE_ID", "Unknown")
            
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
            if not running_process or running_process.poll() is not None:
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
            if running_process and running_process.poll() is None:
                running_process.terminate()
                try:
                    running_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    running_process.kill()
                    running_process.wait()
                log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [yellow]↻ Service stopped for restart[/yellow]")
            
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
    
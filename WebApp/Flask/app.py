from flask import Flask, render_template, request, jsonify
import os
import sys
import subprocess
from pathlib import Path
from collections import deque
import threading
import time

app = Flask(__name__)

# Store the process ID of the running main.py
running_process = None
log_lines = deque(maxlen=500)  # Store last 500 log lines

PERSONAS = ["Old Man", "Young Man", "Old Woman", "Young Woman", "Child"]
AGE_RANGES = {
    "Old Man": ["60-70", "70-80", "80+"],
    "Young Man": ["18-25", "26-35", "36-45"],
    "Old Woman": ["60-70", "70-80", "80+"],
    "Young Woman": ["18-25", "26-35", "36-45"],
    "Child": ["5-8", "9-12", "13-17"]
}
MOODS = ["Happy", "Sad", "Angry", "Neutral", "Excited", "Tired", "Anxious"]
LLM_PROVIDERS = ["OpenAI", "Anthropic", "Hugging Face", "Cohere", "Google"]
LLM_MODELS = {
    "OpenAI": ["gpt-4", "gpt-3.5-turbo", "gpt-4-turbo"],
    "Anthropic": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
    "Hugging Face": ["mistral-7b", "llama-2-70b", "falcon-40b"],
    "Cohere": ["command", "command-light", "command-nightly"],
    "Google": ["gemini-pro", "gemini-ultra", "palm-2"]
}

def write_to_env(persona, age_range, mood, llm_provider, llm_model):
    """Write configuration to .env file"""
    env_path = Path('.env')
    env_content = f"""PERSONA={persona}
AGE_RANGE={age_range}
MOOD={mood}
LLM_PROVIDER={llm_provider}
LLM_MODEL={llm_model}
"""
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(env_content)
    return True

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

@app.route('/')
def index():
    return render_template('index.html', 
                         personas=PERSONAS,
                         age_ranges=AGE_RANGES,
                         moods=MOODS,
                         llm_providers=LLM_PROVIDERS,
                         llm_models=LLM_MODELS)

@app.route('/logs')
def logs():
    return render_template('logs.html')

@app.route('/api/logs')
def get_logs():
    """Return the current logs"""
    return jsonify({'logs': list(log_lines)})

@app.route('/api/logs/clear', methods=['POST'])
def clear_logs():
    """Clear all logs"""
    global log_lines
    log_lines.clear()
    return jsonify({'success': True, 'message': 'Logs cleared'})

@app.route('/save_config', methods=['POST'])
def save_config():
    try:
        data = request.json
        persona = data.get('persona')
        age_range = data.get('age_range')
        mood = data.get('mood')
        llm_provider = data.get('llm_provider')
        llm_model = data.get('llm_model')
        
        write_to_env(persona, age_range, mood, llm_provider, llm_model)
        return jsonify({'success': True, 'message': 'Configuration saved'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/service/<action>', methods=['POST'])
def service_control(action):
    global running_process
    
    try:
        if action == 'start':
            if running_process and running_process.poll() is None:
                return jsonify({'success': False, 'message': 'Service is already running'})
            
            # Set environment variable to force UTF-8 on Windows
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            
            running_process = subprocess.Popen(
                [sys.executable, '-u', 'main.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace',  # Replace characters that can't be encoded
                env=env
            )
            
            # Start thread to read output
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
            
            # Set environment variable to force UTF-8 on Windows
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            
            running_process = subprocess.Popen(
                [sys.executable, '-u', 'main.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace',  # Replace characters that can't be encoded
                env=env
            )
            
            # Start thread to read output
            thread = threading.Thread(target=read_process_output, args=(running_process,))
            thread.daemon = True
            thread.start()
            
            log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [green]✓ Service restarted[/green]")
            return jsonify({'success': True, 'message': 'Reachy service restarted'})
        
        else:
            return jsonify({'success': False, 'message': 'Invalid action'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/service/status', methods=['GET'])
def service_status():
    global running_process
    if running_process and running_process.poll() is None:
        return jsonify({'running': True})
    return jsonify({'running': False})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
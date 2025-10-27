import time
from global_variables import log_lines


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

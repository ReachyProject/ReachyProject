from collections import deque

# Store the process ID of the running main.py
# Store the process ID of the running tracking system
tracking_process = None  # type: Optional[subprocess.Popen]
running_process = None  # type: Optional[subprocess.Popen]
log_lines = deque(maxlen=500)  # Store last 500 log lines

# Global variables for Reachy connection
reachy_connection = None
compliant_mode_active = False
initial_positions = {}

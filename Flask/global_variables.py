from collections import deque

# Store the process ID of the running main.py
running_process = None
tracking_process = None
log_lines = deque(maxlen=500)  # Store last 500 log lines

# Global variables for Reachy connection
reachy_connection = None
compliant_mode_active = False
initial_positions = {}  # Store starting positions

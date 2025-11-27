"""
Proxy Client - Sends robot positions to the web proxy for visualization
Integrates with the face tracking system
"""

import socketio
import threading
import time
from collections import deque


# Joint limits - clamp all positions before sending to proxy
JOINT_LIMITS = {
    'r_shoulder_pitch': (-150, 90),
    'r_shoulder_roll': (-180, 10),
    'r_arm_yaw': (-90, 90),
    'r_elbow_pitch': (-125, 0),
    'r_forearm_yaw': (-100, 100),
    'r_wrist_pitch': (-45, 45),
    'r_wrist_roll': (-55, 35),
    'r_gripper': (-50, 25),
    'l_shoulder_pitch': (-150, 90),
    'l_shoulder_roll': (-10, 180),
    'l_arm_yaw': (-90, 90),
    'l_elbow_pitch': (-125, 0),
    'l_forearm_yaw': (-100, 100),
    'l_wrist_pitch': (-45, 45),
    'l_wrist_roll': (-35, 55),
    'l_gripper': (-25, 50),
    'l_antenna': (-30, 30),
    'r_antenna': (-30, 30),
    'neck_yaw': (-45, 45),
    'neck_pitch': (-25, 25),
    'neck_roll': (-20, 20)
}


def clamp_joint_angle(joint_name, angle):
    """
    Clamp a joint angle to its limits
    
    Args:
        joint_name: Name of the joint
        angle: Angle in degrees
        
    Returns:
        Clamped angle in degrees
    """
    if joint_name not in JOINT_LIMITS:
        return angle
    
    min_angle, max_angle = JOINT_LIMITS[joint_name]
    return max(min_angle, min(max_angle, angle))


class ProxyClient:
    """
    Client that connects to the proxy server and sends robot positions
    """

    def __init__(self, proxy_url='http://10.24.13.51:5001', enable_sync=True):
        """
        Initialize proxy client
        
        Args:
            proxy_url: URL of the proxy server
            enable_sync: Whether to enable position synchronization
        """
        self.proxy_url = proxy_url
        self.enable_sync = enable_sync
        self.connected = False
        
        # Socket.IO client
        self.sio = socketio.Client(reconnection=True, reconnection_delay=1)
        
        # Position tracking
        self.last_sent_positions = {}
        self.position_threshold = 0.5  # Only send if changed by > 0.5 degrees
        
        # Rate limiting
        self.last_send_time = 0
        self.min_send_interval = 0.05  # Max 20 updates/second
        
        # Position queue for smooth updates
        self.position_queue = deque(maxlen=100)
        self.queue_thread = None
        self.queue_running = False
        
        # Setup event handlers
        self._setup_handlers()
        
    def _setup_handlers(self):
        """Setup Socket.IO event handlers"""
        
        @self.sio.on('connect')
        def on_connect():
            self.connected = True
            print(f"[ProxyClient] Connected to proxy at {self.proxy_url}")
            
        @self.sio.on('disconnect')
        def on_disconnect():
            self.connected = False
            print("[ProxyClient] Disconnected from proxy")
            
        @self.sio.on('error')
        def on_error(data):
            print(f"[ProxyClient] Error: {data}")
    
    def connect(self):
        """Connect to the proxy server"""
        if not self.enable_sync:
            print("[ProxyClient] Sync disabled, not connecting")
            return
            
        try:
            print(f"[ProxyClient] Connecting to {self.proxy_url}...")
            self.sio.connect(self.proxy_url)
            
            # Start queue processing thread
            self.queue_running = True
            self.queue_thread = threading.Thread(target=self._process_queue, daemon=True)
            self.queue_thread.start()
            
            return True
        except Exception as e:
            print(f"[ProxyClient] Failed to connect: {e}")
            self.enable_sync = False
            return False
    
    def disconnect(self):
        """Disconnect from proxy server"""
        if self.sio.connected:
            print("[ProxyClient] Disconnecting...")
            self.queue_running = False
            if self.queue_thread:
                self.queue_thread.join(timeout=1.0)
            self.sio.disconnect()
    
    def send_position(self, pan=None, pitch=None, roll=None, force=False):
        """
        Send a single joint position update
        
        Args:
            pan: Neck yaw angle (degrees)
            pitch: Neck pitch angle (degrees)
            roll: Neck roll angle (degrees)
            force: Force send even if below threshold
        """
        if not self.enable_sync or not self.connected:
            return
        
        current_time = time.time()
        
        # Rate limiting
        if not force and (current_time - self.last_send_time) < self.min_send_interval:
            return
        
        # Build position dict with clamped values
        positions = {}
        
        if pan is not None:
            clamped_pan = clamp_joint_angle('neck_yaw', pan)
            if force or self._should_send('neck_yaw', clamped_pan):
                positions['neck_yaw'] = float(clamped_pan)
                self.last_sent_positions['neck_yaw'] = clamped_pan
        
        if pitch is not None:
            clamped_pitch = clamp_joint_angle('neck_pitch', pitch)
            if force or self._should_send('neck_pitch', clamped_pitch):
                positions['neck_pitch'] = float(clamped_pitch)
                self.last_sent_positions['neck_pitch'] = clamped_pitch
        
        if roll is not None:
            clamped_roll = clamp_joint_angle('neck_roll', roll)
            if force or self._should_send('neck_roll', clamped_roll):
                positions['neck_roll'] = float(clamped_roll)
                self.last_sent_positions['neck_roll'] = clamped_roll
        
        # Send if we have any updates
        if positions:
            try:
                self.sio.emit('set_multiple_joints', {
                    'positions': positions,
                    'origin': 'face_tracker'
                })
                self.last_send_time = current_time
            except Exception as e:
                print(f"[ProxyClient] Send error: {e}")
    
    def send_positions_batch(self, positions_dict, force=False):
        """
        Send multiple joint positions at once
        
        Args:
            positions_dict: Dict with keys like 'neck_yaw', 'neck_pitch', 'neck_roll'
            force: Force send even if below threshold
        """
        if not self.enable_sync or not self.connected:
            return
        
        current_time = time.time()
        
        # Rate limiting
        if not force and (current_time - self.last_send_time) < self.min_send_interval:
            return
        
        # Clamp and filter positions by threshold
        to_send = {}
        for joint, angle in positions_dict.items():
            # Clamp to joint limits first
            clamped_angle = clamp_joint_angle(joint, angle)
            
            if force or self._should_send(joint, clamped_angle):
                to_send[joint] = float(clamped_angle)
                self.last_sent_positions[joint] = clamped_angle
        
        # Send if we have updates
        if to_send:
            try:
                self.sio.emit('set_multiple_joints', {
                    'positions': to_send,
                    'origin': 'face_tracker'
                })
                self.last_send_time = current_time
            except Exception as e:
                print(f"[ProxyClient] Send error: {e}")
    
    def queue_position_update(self, pan=None, pitch=None, roll=None):
        """
        Queue a position update for smooth batched sending
        
        Args:
            pan: Neck yaw angle
            pitch: Neck pitch angle
            roll: Neck roll angle
        """
        if not self.enable_sync:
            return
        
        positions = {}
        if pan is not None:
            positions['neck_yaw'] = float(clamp_joint_angle('neck_yaw', pan))
        if pitch is not None:
            positions['neck_pitch'] = float(clamp_joint_angle('neck_pitch', pitch))
        if roll is not None:
            positions['neck_roll'] = float(clamp_joint_angle('neck_roll', roll))
        
        if positions:
            self.position_queue.append((time.time(), positions))
    
    def _process_queue(self):
        """Background thread to process queued position updates"""
        while self.queue_running:
            try:
                if self.position_queue and self.connected:
                    # Get latest position from queue
                    _, positions = self.position_queue[-1]
                    self.position_queue.clear()  # Clear queue after getting latest
                    
                    # Send the position
                    self.send_positions_batch(positions)
                
                time.sleep(self.min_send_interval)
            except Exception as e:
                print(f"[ProxyClient] Queue processing error: {e}")
                time.sleep(0.1)
    
    def _should_send(self, joint_name, new_value):
        """Check if position change exceeds threshold"""
        if joint_name not in self.last_sent_positions:
            return True
        
        delta = abs(new_value - self.last_sent_positions[joint_name])
        return delta >= self.position_threshold
    
    def reset_to_neutral(self):
        """Send command to reset robot to neutral position"""
        if not self.enable_sync or not self.connected:
            return
        
        try:
            # Neutral position (all zeros are within limits)
            neutral_positions = {
                'neck_yaw': 0.0,
                'neck_pitch': 0.0,
                'neck_roll': 0.0
            }
            
            self.sio.emit('set_multiple_joints', {
                'positions': neutral_positions,
                'origin': 'face_tracker'
            })
            self.last_sent_positions = neutral_positions.copy()
            print("[ProxyClient] Reset to neutral position")
        except Exception as e:
            print(f"[ProxyClient] Reset error: {e}")
    
    def is_connected(self):
        """Check if connected to proxy"""
        return self.connected


# Convenience functions for easy integration
_default_client = None

def init_proxy_client(proxy_url='http://10.24.13.51:5001', enable_sync=True):
    """Initialize the default proxy client"""
    global _default_client
    _default_client = ProxyClient(proxy_url, enable_sync)
    return _default_client.connect()

def get_proxy_client():
    """Get the default proxy client"""
    global _default_client
    if _default_client is None:
        init_proxy_client()
    return _default_client

def send_head_position(pan, pitch, roll):
    """Convenience function to send head position using default client"""
    client = get_proxy_client()
    if client:
        # Clamp before queueing
        clamped_pan = clamp_joint_angle('neck_yaw', pan)
        clamped_pitch = clamp_joint_angle('neck_pitch', pitch)
        clamped_roll = clamp_joint_angle('neck_roll', roll)
        client.queue_position_update(pan=clamped_pan, pitch=clamped_pitch, roll=clamped_roll)

def disconnect_proxy():
    """Disconnect the default proxy client"""
    global _default_client
    if _default_client:
        _default_client.disconnect()
        _default_client = None
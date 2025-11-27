"""
Main Face Tracking Application with Proxy Integration
Supports both webcam testing and Reachy robot control
Sends positions to web proxy for visualization
"""

import cv2
import time
from Controllers.tracking_controller import TrackingController
from Controllers.movement_controller import SimulatedMovementController, ReachyMovementController
from Controllers.frame_publisher import CameraFrameProvider
from Controllers.proxy_client import ProxyClient


class FaceTrackingSystem:
    """Main system that coordinates tracking and movement"""

    def __init__(self, use_reachy=False, camera_id=1, show_window=True, 
                 publish_frames=False, use_proxy=True, proxy_url='http://10.24.13.51:5001'):
        """
        Initialize the face tracking system
        
        Args:
            use_reachy: If True, use Reachy robot. If False, use simulated controller
            camera_id: Camera ID for webcam (ignored if you use_reachy=True)
            show_window: Whether to show the camera window
            publish_frames: Whether to publish frames for external consumption
            use_proxy: Whether to send positions to web proxy
            proxy_url: URL of the proxy server
        """
        self.use_reachy = use_reachy
        self.show_window = show_window
        self.publish_frames = publish_frames
        self.use_proxy = use_proxy

        # Initialize proxy client if enabled
        self.proxy_client = None
        if use_proxy:
            print(f"Initializing proxy client ({proxy_url})...")
            self.proxy_client = ProxyClient(proxy_url, enable_sync=True)

        # Initialize camera and tracking
        if use_reachy:
            print("Initializing Reachy mode...")
            self.movement_controller = ReachyMovementController(
                reachy_host='128.39.142.134',
                enable_antenna=True
            )
            self.tracking_controller = TrackingController('reachy', show_overlay=True)
            # Set up Reachy camera reference
            self.tracking_controller.set_reachy_camera(self.movement_controller.reachy)
        else:
            print(f"Initializing webcam mode (camera {camera_id})...")
            cap = cv2.VideoCapture(camera_id)
            if not cap.isOpened():
                raise RuntimeError(f"Could not open camera {camera_id}")

            self.movement_controller = SimulatedMovementController(enable_antenna=True)
            self.tracking_controller = TrackingController(cap, show_overlay=True)

        # Position tracking with smooth interpolation - FASTER for quicker response
        self.target_pan = 0
        self.target_roll = 0
        self.target_pitch = 0
        self.current_pan = 0
        self.current_roll = 0
        self.current_pitch = 0
        self.INTERPOLATION_RATE = 0.5  # Increased from 0.3 for faster response

        # State
        self.running = False

    def start(self):
        """Start the tracking system"""
        print("\n" + "=" * 60)
        print("Face Tracking System Starting")
        print("=" * 60)

        # Connect to proxy if enabled
        if self.proxy_client:
            if self.proxy_client.connect():
                print("✓ Connected to proxy visualization")
            else:
                print("✗ Failed to connect to proxy (continuing without it)")

        # Turn on movement controller
        self.movement_controller.turn_on()

        # Get initial positions
        self.current_pan, self.current_roll, self.current_pitch = \
            self.movement_controller.get_current_position()
        self.target_pan = self.current_pan
        self.target_roll = self.current_roll
        self.target_pitch = self.current_pitch

        # Send initial position to proxy
        if self.proxy_client:
            self.proxy_client.send_positions_batch({
                'neck_yaw': self.current_pan,
                'neck_pitch': self.current_pitch,
                'neck_roll': self.current_roll
            }, force=True)

        print("\nSystem ready!")
        print("- Face tracking active")
        print("- Hand wave detection active")
        if self.publish_frames:
            temp_dir = CameraFrameProvider.get_temp_directory()
            print(f"- Publishing frames to {temp_dir / 'reachy_camera_frame.jpg'}")
        if self.proxy_client and self.proxy_client.is_connected():
            print(f"- Web visualization at http://10.24.13.51:5001")
        print("- Press 'q' to quit")
        if self.show_window:
            print("- Press 'o' to toggle overlay")
        print()

        self.running = True
        self._main_loop()

    def _main_loop(self):
        """Main processing loop"""
        show_overlay = True
        frame_count = 0

        try:
            while self.running:
                current_time = time.time()
                frame_count += 1

                # Get tracking data
                tracking_data = self.tracking_controller.process_frame(current_time)

                if tracking_data is None:
                    time.sleep(0.01)
                    continue

                # Handle movement commands
                if tracking_data['movement_command']:
                    cmd = tracking_data['movement_command']

                    if cmd['type'] == 'adjust':
                        # Relative adjustment
                        actual_pan, actual_roll, _ = self.movement_controller.get_current_position()
                        self.target_pan = actual_pan + cmd['pan_adjustment']
                        self.target_roll = actual_roll + cmd['roll_adjustment']
                        self.target_pitch = cmd['pitch']

                    elif cmd['type'] == 'absolute':
                        # Absolute positioning
                        self.target_pan = cmd['pan']
                        self.target_roll = cmd['roll']
                        self.target_pitch = cmd['pitch']

                # Handle wave detection
                if tracking_data.get('wave_command') == 'wave_back':
                    # TODO: Trigger wave animation
                    # For now, just log it
                    if not hasattr(self, '_last_wave_time') or (current_time - self._last_wave_time) > 3.0:
                        print("[WAVE] Wave detected! Triggering wave response...")
                        self._last_wave_time = current_time
                        # self.movement_controller.wave_back()  # To be implemented

                # Update antenna mode
                self.movement_controller.set_antenna_mode(tracking_data['antenna_mode'])

                # Smooth interpolation
                self.current_pan += (self.target_pan - self.current_pan) * self.INTERPOLATION_RATE
                self.current_roll += (self.target_roll - self.current_roll) * self.INTERPOLATION_RATE
                self.current_pitch += (self.target_pitch - self.current_pitch) * self.INTERPOLATION_RATE

                # Send positions to movement controller
                self.movement_controller.move_head(
                    self.current_pan,
                    self.current_roll,
                    self.current_pitch
                )

                # Send positions to proxy for visualization
                if self.proxy_client and self.proxy_client.is_connected():
                    # Build complete position dict including antennas
                    positions_to_send = {
                        'neck_yaw': self.current_pan,
                        'neck_pitch': self.current_pitch,
                        'neck_roll': self.current_roll
                    }
                    
                    # Add antenna positions based on mode
                    antenna_mode = tracking_data['antenna_mode']
                    if antenna_mode == 'sad':
                        positions_to_send['l_antenna'] = -125
                        positions_to_send['r_antenna'] = 125
                    elif antenna_mode == 'tracking':
                        # Slight wiggle
                        import random
                        wiggle = random.uniform(-15, 15)
                        positions_to_send['l_antenna'] = -15 + wiggle
                        positions_to_send['r_antenna'] = 15 - wiggle
                    elif antenna_mode == 'scanning':
                        # Scanning motion
                        positions_to_send['l_antenna'] = -125
                        positions_to_send['r_antenna'] = 125
                    elif antenna_mode == 'giving_up':
                        # Droop motion
                        positions_to_send['l_antenna'] = -20
                        positions_to_send['r_antenna'] = 20
                    else:  # idle
                        positions_to_send['l_antenna'] = 0
                        positions_to_send['r_antenna'] = 0
                    
                    self.proxy_client.send_positions_batch(positions_to_send)

                # Publish frame if enabled
                if self.publish_frames:
                    metadata = {
                        'timestamp': current_time,
                        'face_detected': tracking_data['face_detected'],
                        'face_position': tracking_data['face_position'],
                        'wave_detected': tracking_data['wave_detected'],
                        'head_position': {
                            'pan': float(self.current_pan),
                            'roll': float(self.current_roll),
                            'pitch': float(self.current_pitch)
                        },
                        'tracking_state': tracking_data['scanning_state'],
                        'antenna_mode': tracking_data['antenna_mode']
                    }
                    CameraFrameProvider.publish_frame(tracking_data['frame'], metadata)

                # Display the window if enabled
                if self.show_window:
                    frame = tracking_data['frame']

                    # Add status text
                    status_text = f"State: {tracking_data['scanning_state']}"
                    if tracking_data['face_detected']:
                        status_text += " | Face: DETECTED"
                    else:
                        status_text += " | Face: NOT FOUND"

                    if tracking_data['wave_detected']:
                        status_text += " | WAVING"

                    # Add proxy connection status
                    if self.proxy_client:
                        if self.proxy_client.is_connected():
                            status_text += " | Proxy: ✓"
                        else:
                            status_text += " | Proxy: ✗"

                    cv2.putText(frame, status_text, (10, frame.shape[0] - 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                    cv2.imshow('Face Tracking', frame)

                    # Handle keyboard
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        print("\nQuitting...")
                        self.running = False
                    elif key == ord('o'):
                        show_overlay = not show_overlay
                        self.tracking_controller.show_overlay = show_overlay
                        print(f"Overlay: {'ON' if show_overlay else 'OFF'}")
                    elif key == ord('r'):
                        # Reset to neutral position
                        print("Resetting to neutral...")
                        self.target_pan = 0
                        self.target_roll = 0
                        self.target_pitch = 0
                        if self.proxy_client:
                            self.proxy_client.reset_to_neutral()

                # Print FPS occasionally
                if frame_count % 100 == 0:
                    print(f"[INFO] Processed {frame_count} frames | "
                          f"Position: pan={self.current_pan:.1f}° pitch={self.current_pitch:.1f}° roll={self.current_roll:.1f}°")

        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
        finally:
            self.stop()

    def stop(self):
        """Stop the tracking system"""
        print("\nStopping tracking system...")
        self.running = False

        # Disconnect from proxy
        if self.proxy_client:
            self.proxy_client.disconnect()

        # Cleanup
        self.tracking_controller.cleanup()
        self.movement_controller.turn_off()

        if self.publish_frames:
            CameraFrameProvider.cleanup()

        if self.show_window:
            cv2.destroyAllWindows()

        print("System stopped.")


def main():
    """
    Main entry point
    
    Configuration options:
    - use_reachy: True to use real Reachy robot, False for webcam simulation
    - camera_id: Which camera to use (0 = default, 1 = external, etc.)
    - show_window: Show the camera feed window
    - publish_frames: Publish frames to temp directory for web apps
    - use_proxy: Enable web proxy visualization
    - proxy_url: URL of the proxy server
    """
    try:
        system = FaceTrackingSystem(
            use_reachy=False,        # Set to True when using actual Reachy
            camera_id=0,             # 0 = default camera, 1 = external
            show_window=True,        # Show OpenCV window
            publish_frames=True,     # Publish for web consumption
            use_proxy=True,          # Enable proxy visualization
            proxy_url='http://10.24.13.51:5001'
        )
        system.start()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
"""
Main Face Tracking Application
Supports both webcam testing and Reachy robot control
"""

import cv2
import time
import argparse
from tracking_controller import TrackingController
from movement_controller import SimulatedMovementController, ReachyMovementController
from frame_publisher import CameraFrameProvider


class FaceTrackingSystem:
    """Main system that coordinates tracking and movement"""
    
    def __init__(self, use_reachy=False, camera_id=1, show_window=True, publish_frames=False):
        """
        Initialize face tracking system
        
        Args:
            use_reachy: If True, use Reachy robot. If False, use simulated controller
            camera_id: Camera ID for webcam (ignored if use_reachy=True)
            show_window: Whether to show the camera window
            publish_frames: Whether to publish frames for external consumption
        """
        self.use_reachy = use_reachy
        self.show_window = show_window
        self.publish_frames = publish_frames
        
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
        print("\n" + "="*60)
        print("Face Tracking System Starting")
        print("="*60)
        
        # Turn on movement controller
        self.movement_controller.turn_on()
        
        # Get initial positions
        self.current_pan, self.current_roll, self.current_pitch = \
            self.movement_controller.get_current_position()
        self.target_pan = self.current_pan
        self.target_roll = self.current_roll
        self.target_pitch = self.current_pitch
        
        print("\nSystem ready!")
        print("- Face tracking active")
        print("- Hand wave detection active")
        if self.publish_frames:
            print("- Publishing frames to /tmp/reachy_camera_frame.jpg")
        print("- Press 'q' to quit")
        if self.show_window:
            print("- Press 'o' to toggle overlay")
        print()
        
        self.running = True
        self._main_loop()
    
    def _main_loop(self):
        """Main processing loop"""
        show_overlay = True
        
        try:
            while self.running:
                current_time = time.time()
                
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
                        print(f"[WAVE] Wave detected! Triggering wave response...")
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
                
                # Display window if enabled
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
                
        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the tracking system"""
        print("\nStopping tracking system...")
        self.running = False
        
        # Cleanup
        self.tracking_controller.cleanup()
        self.movement_controller.turn_off()
        
        if self.publish_frames:
            CameraFrameProvider.cleanup()
        
        if self.show_window:
            cv2.destroyAllWindows()
        
        print("System stopped.")


def main():
    parser = argparse.ArgumentParser(description='Face Tracking System')
    parser.add_argument('--reachy', action='store_true',
                       help='Use Reachy robot (default: use webcam simulation)')
    parser.add_argument('--camera', type=int, default=1,
                       help='Camera ID for webcam mode (default: 1)')
    parser.add_argument('--no-window', action='store_true',
                       help='Run without display window')
    parser.add_argument('--publish', action='store_true',
                       help='Publish frames to /tmp for external access')
    
    args = parser.parse_args()
    
    try:
        system = FaceTrackingSystem(
            use_reachy=args.reachy,
            camera_id=args.camera,
            show_window=not args.no_window,
            publish_frames=args.publish
        )
        system.start()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
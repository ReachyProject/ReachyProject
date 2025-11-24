
from robot.controllers.robot import RobotController
from reachy_sdk import ReachySDK
import time
from rich import print
import os
from dotenv import load_dotenv
from pathlib import Path
from  Flask.constants import AGE_RANGES

#dotenv_path = Path(__file__).parent.parent / '.env'
#load_dotenv(dotenv_path=dotenv_path)
#ip = os.getenv("REACHY_IP_ADDRESS")
#reachy = ReachySDK(ip)


#ip = '128.39.142.134' # external ip Address
ip = "192.168.0.177" # Local ip address

def main():
    testing = False

    print("Robot bootstrap, AGE_RANGES from Flask: ", str(AGE_RANGES)) # Cross-platform import test

    if testing:
        main_controller =  RobotController(None)
        main_controller.speech_controller.speech_loop("hello reachy", 30)
        return

    # Connect to Reachy
    print("Connecting to Reachy at:", ip)
    reachy = ReachySDK(ip)
    
    print("Turning on head...")
    reachy.turn_on('head')
    time.sleep(1)

    # Create robot controller
    robot_controller = RobotController(reachy)
    
    # Start passive tracking
    #robot_controller.tracking_controller.start()
    
    try:
        print("\n" + "="*60)
        print("🤖 Reachy is now tracking faces and listening")
        print("Say 'Hey Reachy' to start a robot_controller")
        print("Once in robot_controller, just keep talking naturally")
        print("Conversation ends after 30s of silence")
        print("Press Ctrl+C to quit")
        print("="*60 + "\n")


        # Start robot_controller loop with 15 second timeout
        robot_controller.interaction_loop(wake_word="reachy", conversation_timeout=15)
                
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    finally:
        robot_controller.cleanup()
        reachy.turn_off_smoothly('head')
        print("✅ Done!")


if __name__ == "__main__":
    main()

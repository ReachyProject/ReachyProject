from .controllers.robot import *


import random
from collections import deque

import cv2 as cv
import mediapipe as mp
from reachy_sdk import ReachySDK
from reachy_sdk.trajectory import goto
from reachy_sdk.trajectory.interpolation import InterpolationMode
import time
import threading
from io import BytesIO
import os
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from groq import Groq
from elevenlabs.play import play
import pyaudio
import wave
import struct
import math
import queue
from rich import print

from difflib import SequenceMatcher
import webrtcvad

def main():
    testing = False
 
    if testing:
        main_controller =  RobotController(None)
        main_controller.speech_controller.speech_loop("hello reachy", 30)
        return

    # Connect to Reachy
    print("Connecting to Reachy...")
    reachy = ReachySDK('128.39.142.134')
    
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

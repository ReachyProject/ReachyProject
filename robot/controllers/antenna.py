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

class AntennaController:
    def __init__(self, parent: "RobotController"):
        self.parent = parent
        self.reachy = parent.reachy
        self.current_antenna_mode = "idle"
        self.start()

    def _set(self, left, right):
        self.reachy.head.l_antenna.goal_position = left
        self.reachy.head.r_antenna.goal_position = right

    def _wiggle(self, base_left, base_right, wiggle_range, sleep_range):
        wiggle = random.uniform(*wiggle_range)
        self._set(base_left + wiggle, base_right - wiggle)
        time.sleep(random.uniform(*sleep_range))

    def _execute(self, moves: list[tuple[int, int]], interval):
        for left, right in moves:
            self._set(left, right)
            time.sleep(interval)

    def _loop(self):
        while self.running:
            #print("antenna mode: " + str(self.current_antenna_mode) + ", running: " + str(self.running))
            try:
                match self.current_antenna_mode:
                    case "sad":
                        self._execute([(-125, 125), (-120, 120)], 0.3)
                    case "tracking":
                        self._wiggle(-15, 15, (-15, 15), (0.3, 0.8))
                    case "scanning":
                        self._execute([(-125, 125), (-100, 100)], 0.3)
                    case "talking":
                        self._wiggle(-15, 15, (-25, 25), (0.2, 0.4))
                    case "idle":
                        self._set(0, 0)
                    case _:
                        time.sleep(0.5)
            except Exception as e:
                print(f"Antenna error: {e}")
                time.sleep(0.5)

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        self.running = False
        self.thread.join(timeout=2)
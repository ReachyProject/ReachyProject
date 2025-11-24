import time

from elevenlabs.play import play
from reachy_sdk import ReachySDK
from reachy_sdk.trajectory import goto
from reachy_sdk.trajectory.interpolation import InterpolationMode
from rich import print

from Flask.handlers.persona_config import build_system_prompt
from robot.controllers.speech import SpeechController
from robot.controllers.antenna import AntennaController
from robot.controllers.tracking import TrackingController



class RobotController:
    def __init__(self, reachy: ReachySDK = None):
        self.reachy = reachy

        self.speech_controller = SpeechController(self, voice_id=None)
        print(f"🎙️ Using voice ID: {self.speech_controller.voice_id}")
        self.prompt = None

        self.antenna_controller = AntennaController(self)
        self.tracking_controller = TrackingController(self)

        # Camera parameters
        test_img = reachy.left_camera.last_frame
        self.frame_height, self.frame_width = test_img.shape[:2]
        self.frame_center_x = self.frame_width / 2
        self.frame_center_y = self.frame_height / 2
        
        # Smoothing parameters
        self.DEADBAND = 0.04
        self.MOVEMENT_GAIN = 50
        self.SMOOTHING_ALPHA = 0.5

        # Scanning state
        self.scanning_state = "idle"
        self.scan_count = 0
        self.MAX_SCANS = 1
        self.state_start_time = 0

        # Conversation state
        self.conversation_active = False

    def interaction_loop(self, wake_word="reachy", conversation_timeout=15):
        """
        Continuous interaction loop:
          - Robot idles until wake word is detected.
          - Then enters active listening mode.
          - Returns to idle after 'conversation_timeout' seconds of silence.
        """
        last_speech_time = 0

        print(f"Entering speech loop. Waiting for wake word '{wake_word}'...")

        while True:
            try:
                print("-1")
                if not self.conversation_active:
                    self.current_antenna_mode = "idle"
                    print("pre")
                    if True: #self.speech_controller.detect_wake_word(wake_word=wake_word, timeout=30):
                        print("if")
                        print("🟢 Activated by wake word!")
                        self.start()
                        self.conversation_active = True
                        self.antenna_controller.current_antenna_mode = "talking"
                        last_speech_time = time.time()
                    else:
                        print("Waiting for wake word...")
                        continue
                print("0")
                speech, wav_buffer = self.speech_controller.audio_controller.record_until_silence(
                    max_duration=10,
                    silence_duration=1,
                )
                print("1")

                if speech == False:
                    if time.time() - last_speech_time > conversation_timeout:
                        print("Timeout, returning to idle.")
                        self.stop()
                        self.conversation_active = False
                        continue
                    else:
                        continue  #
                print("2")
                
                # --- Process Speech ---
                transcription = self.speech_controller.elevenlabs.speech_to_text.convert(
                    file=wav_buffer,
                    model_id="scribe_v1",
                    tag_audio_events=False,
                    language_code="eng",
                    diarize=False,
                )
                print("3")

                text = transcription.text.strip()
                if text:
                    print(f"👤 User: {text}")
                    last_speech_time = time.time()

                    # Example: Generate AI response
                    response = self.speech_controller.generate_ai_response(text, self.prompt)
                    print(f"🤖 Reachy: {response}")
                    play(self.speech_controller.text_to_speech(response))
                    print("4")

            except KeyboardInterrupt:
                print("Speech loop interrupted by user.")
                break
            except Exception as e:
                print(f"interaction loop Error: {e}")
                time.sleep(1)


    def start(self):
        self.antenna_controller.start()
        self.tracking_controller.start()

    def stop(self):
        self.tracking_controller.pause()
        self.antenna_controller.stop()
         # Return to neutral
        goto(
            goal_positions={
                self.reachy.head.neck_yaw: 0,
                self.reachy.head.neck_roll: 0,
                self.reachy.head.neck_pitch: 0,
                self.reachy.head.l_antenna: 0,
                self.reachy.head.r_antenna: 0
            },
            duration=1.0,
            interpolation_mode=InterpolationMode.MINIMUM_JERK
        )
        time.sleep(1)

    def cleanup(self):
        """Clean up all threads and return to neutral"""
        print("\n🧹 Cleaning up...")
        
        self.tracking_controller.stop()
        self.antenna_controller.stop()
        self.face_detection.close()
        
        # Return to neutral
        goto(
            goal_positions={
                self.reachy.head.neck_yaw: 0,
                self.reachy.head.neck_roll: 0,
                self.reachy.head.neck_pitch: 0,
                self.reachy.head.l_antenna: 0,
                self.reachy.head.r_antenna: 0
            },
            duration=1.0,
            interpolation_mode=InterpolationMode.MINIMUM_JERK
        )
        time.sleep(1)
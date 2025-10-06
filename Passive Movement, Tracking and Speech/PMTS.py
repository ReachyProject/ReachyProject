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

load_dotenv()
VOICE_ID = os.getenv("VOICE_ID")

# Initialize MediaPipe Face Detection
mp_face_detection = mp.solutions.face_detection
mp_drawing = mp.solutions.drawing_utils

class AudioController:
    def __init__(self, parent: "RobotController",  rate=16000, chunk=1024, vad_level=3):
        self.rate = rate
        self.parent = parent
        self.chunk = chunk
        self.format = pyaudio.paInt16
        self.channels = 1
        self.audio = pyaudio.PyAudio()
        self.vad = webrtcvad.Vad(vad_level)

    def record(self, duration: float) -> bytes:
        with self.audio.open(format=self.format, channels=self.channels,
                             rate=self.rate, input=True,
                             frames_per_buffer=self.chunk, input_device_index=0) as stream:
            frames = [stream.read(self.chunk) for _ in range(int(self.rate / self.chunk * duration))]
        return b"".join(frames)

    def record_until_silence(self, max_duration=15.0, silence_duration=1.0) -> tuple[bool, BytesIO]:
        """
        Records audio until a period of silence is detected (VAD-based).
        Returns the captured audio as an in-memory WAV (BytesIO).
        """

        rate, fmt, channels = self.rate, self.format, self.channels
        chunk_ms = 30
        chunk = int(rate * chunk_ms / 1000)
        silence_frames = int(silence_duration * 1000 / chunk_ms)

        stream = self.audio.open(
            format=fmt, channels=channels, rate=rate,
            input=True, frames_per_buffer=chunk, input_device_index=0
        )
        print("🎤 Listening (record until silence)...")

        vad = self.vad
        pre_buffer = deque(maxlen=10)
        voiced_frames = []
        silence_count = 0
        speech_started = False
        start_time = time.time()

        timeout = False

        try:
            while True:
                frame = stream.read(chunk, exception_on_overflow=False)
                is_speech = vad.is_speech(frame, rate)
                
                if not speech_started:
                    pre_buffer.append(frame)
                    if is_speech:
                        speech_started = True
                        voiced_frames.extend(pre_buffer)
                        pre_buffer.clear()
                        print("🗣️ Speech detected — recording...")
                else:
                    voiced_frames.append(frame)
                    if is_speech:
                        silence_count = 0
                    else:
                        silence_count += 1
                        if silence_count > silence_frames:
                            print("✅ Silence detected — stopping.")
                            break

                if time.time() - start_time > max_duration:
                    print("⏰ Timeout reached — stopping.")
                    timeout = True
                    break

        finally:
            stream.stop_stream()
            stream.close()

        if timeout:
            print("Timeout, silence.")
            return (False, BytesIO())

        if not voiced_frames:
            print("⚠️ No speech detected.")
            return (False, BytesIO())

        wav_buffer = BytesIO()
        with wave.open(wav_buffer, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(self.audio.get_sample_size(fmt))
            wf.setframerate(rate)
            wf.writeframes(b"".join(voiced_frames))
        wav_buffer.seek(0)
        wav_buffer.name = "speech.wav"

        return (True, wav_buffer)
    

    def _get_rms(self, data):
        """Calculate RMS (Root Mean Square) for volume detection"""
        count = len(data) / 2
        format_str = "%dh" % count
        shorts = struct.unpack(format_str, data)
        sum_squares = sum((sample ** 2 for sample in shorts))
        rms = math.sqrt(sum_squares / count)
        return rms


    def detect_first_word(self, pre_buffer_ms=200, capture_after_ms=600, timeout=8.0) -> str:
        """
        Waits for speech using VAD, records a short snippet (first word/phrase),
        and returns its transcribed text.
        """

        rate, fmt, channels = self.rate, self.format, self.channels
        chunk_ms = 30  # WebRTC VAD works with 10/20/30 ms frames
        chunk = int(rate * chunk_ms / 1000)
        pre_frames = int(pre_buffer_ms / chunk_ms)
        capture_frames = int(capture_after_ms / chunk_ms)

        stream = self.audio.open(
            format=fmt, channels=channels, rate=rate,
            input=True, frames_per_buffer=chunk, input_device_index=0
        )
        print("👂 Waiting for first speech...")

        buffer = deque(maxlen=pre_frames)
        start_time = time.time()

        try:
            # --- Wait for first voice frame ---
            while time.time() - start_time < timeout:
                frame = stream.read(chunk, exception_on_overflow=False)
                buffer.append(frame)
                if self.vad.is_speech(frame, rate):
                    print("🗣️ Speech detected! Capturing first word...")
                    frames = list(buffer)

                    # --- Capture short window after detection ---
                    for _ in range(capture_frames):
                        frames.append(stream.read(chunk, exception_on_overflow=False))

                    # --- Stop and transcribe ---
                    stream.stop_stream()
                    stream.close()

                    wav = BytesIO()
                    with wave.open(wav, "wb") as wf:
                        wf.setnchannels(channels)
                        wf.setsampwidth(self.audio.get_sample_size(fmt))
                        wf.setframerate(rate)
                        wf.writeframes(b"".join(frames))
                    wav.seek(0)
                    wav.name = "first_word.wav"

                    transcription = self.parent.speech_controller.elevenlabs.speech_to_text.convert(
                        file=wav,
                        model_id="scribe_v1",
                        language_code="eng",
                        tag_audio_events=False,
                        diarize=False,
                    )
                    text = transcription.text.strip().split(" ")[0]
                    print("🧠 First word:", text)
                    return text

            print("⏰ Timeout — no speech detected.")
            stream.stop_stream()
            stream.close()
            return ""
        except Exception as e:
            print(f"Error: {e}")
            try:
                stream.stop_stream();
                stream.close()
            except:
                pass
            return ""

    def similar(self, a: str, b: str):
        return SequenceMatcher(None, a, b).ratio()

class SpeechController:
    def __init__(self, parent: "RobotController" = None,voice_id=VOICE_ID, model_id="eleven_multilingual_v2"):
        self.voice_id = voice_id
        self.model_id = model_id
        self.parent = parent
        self.elevenlabs = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
        self.llm = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.audio_controller = AudioController(parent)

    def speech_loop(self, wake_word="hey reachy", conversation_timeout=15):
        """
        Continuous speech loop:
          - Robot idles until wake word is detected.
          - Then enters active listening mode.
          - Returns to idle after 'conversation_timeout' seconds of silence.
        """
        active = False
        last_speech_time = 0

        print(f"Entering speech loop. Waiting for wake word '{wake_word}'...")

        while True:
            try:
                if not active:
                    self.parent.current_antenna_mode = "idle"
                    print("pre")
                    if self.detect_wake_word(wake_word=wake_word, timeout=30):
                        print("🟢 Activated by wake word!")
                        self.parent.tracking_controller.start()
                        active = True
                        self.parent.current_antenna_mode = "talking"
                        last_speech_time = time.time()
                    else:
                        print("Waiting for wake word...")
                        continue


                print("gubb")
                speech, wav_buffer = self.audio_controller.record_until_silence(
                    max_duration=10,
                    silence_duration=1.5,
                )
                print("post")

                if speech == False:
                    if time.time() - last_speech_time > conversation_timeout:
                        print("Timeout, returning to idle.")
                        self.parent.tracking_controller.stop()
                        active = False
                        continue
                    else:
                        continue  #

                # --- Process Speech ---
                transcription = self.elevenlabs.speech_to_text.convert(
                    file=wav_buffer,
                    model_id="scribe_v1",
                    tag_audio_events=False,
                    language_code="eng",
                    diarize=False,
                )

                text = transcription.text.strip()
                if text:
                    print(f"👤 User: {text}")
                    last_speech_time = time.time()

                    # Example: Generate AI response
                    response = self.generate_ai_response(text,
                                              "You are a child, act stupid. Limit response length to 2-3 sentences. Responses should be possible to be played through elevenlabs. Add punctuation to the text; high prosody")

                    print(f"🤖 Reachy: {response}")
                    play(self.text_to_speech(response))

            except KeyboardInterrupt:
                print("Speech loop interrupted by user.")
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(1)


    def text_to_speech(self, input_text) -> bytes:
        audio = self.elevenlabs.text_to_speech.convert(
            text=input_text,
            voice_id=self.voice_id,
            model_id=self.model_id,
            output_format="mp3_44100_128",
            voice_settings={
                "stability": 0.05,
                "similarity_boost": 0.35,
                "style": 0.99,
                "use_speaker_boost": True
            }
        )
        return audio

    def speech_to_text_with_vad(self, wake_word, timeout, max_duration=10, silence_threshold=500, silence_duration=2.0) -> str:
        """Record audio until silence is detected or max duration is reached"""
        print("vad-pre")
        while True:
            speech = self.detect_wake_word(wake_word, timeout)
            if speech: break
        print("vad-post")

        speech, wav_buffer = self.audio_controller.record_until_silence(max_duration, silence_duration)

        transcription = self.elevenlabs.speech_to_text.convert(
            file=wav_buffer,
            model_id="scribe_v1",
            tag_audio_events=False,
            language_code="eng",
            diarize=False,
        )
        return transcription.text

    def _check_wake_word(self, transcribed_text, wake_word):
        """Check if wake word matches with fuzzy logic for common misheard words"""
        text_lower = transcribed_text.lower()
        wake_lower = wake_word.lower()
        
        # Direct match
        if wake_lower in text_lower:
            return True
        
        # Common mishearings of "Reachy"
        reachy_variants = [
            "hey reachy", "hey reach", "heyreach", "hey ricci", 
            "hey richie", "hey peachy", "hey teacher", "a reachy",
            "hey reachi", "hey rechy", "heyreachy"
        ]
        
        return any(variant in text_lower for variant in reachy_variants)

    def detect_wake_word(self, wake_word="hey reachy", timeout=15) -> bool:
        """
        Uses VAD to capture short phrases until wake word is detected.
        Avoids short false triggers by capturing full short utterances.
        """
        print(f"👂 Listening for wake word '{wake_word}'...")
        start_time = time.time()
        debounce_delay = 1.0  # wait this long after each attempt

        while time.time() - start_time < timeout:
            print("wake pre")
            speech, wav_buffer = self.audio_controller.record_until_silence(
                max_duration=5,
                silence_duration=1.5
            )
            print("wake post")

            if not wav_buffer.getbuffer().nbytes:
                continue  # nothing captured, keep waiting

            try:
                transcription = self.elevenlabs.speech_to_text.convert(
                    file=wav_buffer,
                    model_id="scribe_v1",
                    language_code="eng",
                    tag_audio_events=False,
                    diarize=False,
                )

                text = transcription.text.lower().strip()
                if not text:
                    continue

                print(f"🔍 Heard: '{text}'")

                if self._check_wake_word(text, wake_word):
                    print("🎉 Wake word detected!")
                    return True
                else:
                    similarity = self.audio_controller.similar(text, wake_word)
                    print("Similarity score: " + str(similarity))

                    if similarity > 0.4:
                        print(f"🤔 Close Wake Word match: " + wake_word)
                        return True

            except Exception as e:
                print(f"⚠️ Wake word processing error: {e}")

            # Debounce – wait a moment before listening again
            time.sleep(debounce_delay)

        print("⏰ Wake word timeout.")
        return False

    def generate_ai_response(self, prompt, system_prompt, llm_model="llama-3.3-70b-versatile") -> str:
        response = self.llm.chat.completions.create(
            model=llm_model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        return response.choices[0].message.content


class RobotController:
    def __init__(self, reachy: ReachySDK = None):
        self.reachy = reachy

        self.speech_controller = SpeechController(self, voice_id="6XVxc5pFxXre3breYJhP")
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

        # Face detection
        self.face_detection = mp_face_detection.FaceDetection(
            model_selection=1, 
            min_detection_confidence=0.9
        )
        

        # Conversation state
        self.conversation_active = False

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

class TrackingController:
    def __init__(self, parent: "RobotController"):
        self.parent = parent
        self.reachy = parent.reachy
        self.running = False
        self.thread = None
        # Position tracking
        self.target_pan = 0
        self.target_roll = 0
        self.target_pitch = 0
        self.current_pan = 0
        self.current_roll = 0
        self.current_pitch = 0
        self.INTERPOLATION_RATE = 0.3
        self.MIN_MOVEMENT_THRESHOLD = 2.0

        # Face tracking state
        self.smoothed_error_x = 0
        self.smoothed_error_y = 0
        self.frame_count = 0
        self.no_face_count = 0
        self.PANLEFT = True

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
            print("✅ Tracking started")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
            print("🛑 Tracking stopped")

    def _loop(self):
        """Main tracking loop that runs continuously"""
        self.current_pan = self.reachy.head.neck_yaw.present_position
        self.current_roll = self.reachy.head.neck_roll.present_position
        self.current_pitch = self.reachy.head.neck_pitch.present_position
        self.target_pan = self.current_pan
        self.target_roll = self.current_roll
        self.target_pitch = self.current_pitch

        while self.running:
            try:
                self.frame_count += 1
                current_time = time.time()

                image = self.reachy.left_camera.last_frame
                if image is None:
                    continue

                # Process image
                image.flags.writeable = False
                image_rgb = cv.cvtColor(image, cv.COLOR_BGR2RGB)
                results = self.parent.face_detection.process(image_rgb)

                if results.detections:
                    # FACE DETECTED
                    self.no_face_count = 0
                    self.scan_count = 0
                    self.parent.scanning_state = "idle"

                    # Set antenna mode based on conversation state
                    if not self.parent.conversation_active:
                        self.parent.antenna_controller.current_antenna_mode = "tracking"

                    detection = results.detections[0]
                    bbox = detection.location_data.relative_bounding_box

                    face_center_x = (bbox.xmin + bbox.width / 2) * self.parent.frame_width
                    face_center_y = (bbox.ymin + bbox.height / 2) * self.parent.frame_height

                    error_x = (face_center_x - self.parent.frame_center_x) / self.parent.frame_width
                    error_y = (face_center_y - self.parent.frame_center_y) / self.parent.frame_height

                    self.smoothed_error_x = self.parent.SMOOTHING_ALPHA * error_x + (
                            1 - self.parent.SMOOTHING_ALPHA) * self.smoothed_error_x
                    self.smoothed_error_y = self.parent.SMOOTHING_ALPHA * error_y + (
                            1 - self.parent.SMOOTHING_ALPHA) * self.smoothed_error_y

                    if abs(self.smoothed_error_x) > self.parent.DEADBAND or abs(self.smoothed_error_y) > self.parent.DEADBAND:
                        actual_pan = self.reachy.head.neck_yaw.present_position
                        actual_roll = self.reachy.head.neck_roll.present_position

                        pan_movement = -self.smoothed_error_x * self.parent.MOVEMENT_GAIN
                        roll_movement = -self.smoothed_error_y * self.parent.MOVEMENT_GAIN

                        new_target_pan = actual_pan + pan_movement
                        new_target_roll = actual_roll + roll_movement

                        if abs(new_target_pan - self.target_pan) > self.MIN_MOVEMENT_THRESHOLD or \
                                abs(new_target_roll - self.target_roll) > self.MIN_MOVEMENT_THRESHOLD:
                            self.target_pan = new_target_pan
                            self.target_roll = new_target_roll

                    self.target_pitch = 0

                else:
                    # NO FACE - scanning state machine (only if not in conversation)
                    if not self.parent.conversation_active:
                        self.no_face_count += 1

                        if self.parent.scanning_state == "idle":
                            if self.no_face_count >= 60:
                                self.scanning_state = "scanning"
                                self.scan_count = 0
                                self.state_start_time = current_time
                                self.parent.antenna_controller.current_antenna_mode = "scanning"
                            else:
                                self.parent.antenna_controller.current_antenna_mode = "idle"

                        elif self.parent.scanning_state == "scanning":
                            self.parent.antenna_controller.current_antenna_mode = "scanning"

                            if self.frame_count % 90 == 0:
                                self.scan_count += 1

                                if self.scan_count > self.parent.MAX_SCANS:
                                    self.parent.scanning_state = "giving_up"
                                    self.state_start_time = current_time
                                    self.parent.antenna_controller.current_antenna_mode = "giving_up"
                                else:
                                    random_pan_magnitude = random.uniform(30, 75)
                                    random_roll = random.uniform(-5, 5)

                                    if self.PANLEFT:
                                        random_pan = -random_pan_magnitude
                                    else:
                                        random_pan = random_pan_magnitude

                                    self.PANLEFT = not self.PANLEFT

                                    self.target_pan = random_pan
                                    self.target_roll = random_roll
                                    self.target_pitch = 0

                        elif self.parent.scanning_state == "giving_up":
                            if current_time - self.state_start_time > 1.5:
                                self.parent.scanning_state = "sad"
                                self.state_start_time = current_time
                                self.parent.antenna_controller.current_antenna_mode = "sad"

                        elif self.parent.scanning_state == "sad":
                            self.parent.antenna_controller.current_antenna_mode = "sad"

                            if current_time - self.state_start_time > 2.0:
                                self.parent.scanning_state = "looking_down"
                                self.state_start_time = current_time
                                goto(
                                    goal_positions={
                                        self.reachy.head.neck_yaw: 0,
                                        self.reachy.head.neck_roll: -30,
                                        self.reachy.head.neck_pitch: 0
                                    },
                                    duration=0.4,
                                    interpolation_mode=InterpolationMode.MINIMUM_JERK
                                )

                        elif self.parent.scanning_state == "looking_down":
                            self.parent.antenna_controller.current_antenna_mode = "sad"

                            if current_time - self.state_start_time > 3.0:
                                self.parent.scanning_state = "waiting"
                                self.state_start_time = current_time

                        elif self.parent.scanning_state == "waiting":
                            self.parent.antenna_controller.current_antenna_mode = "sad"

                            if current_time - self.state_start_time > 2.0:
                                self.parent.scanning_state = "scanning"
                                self.scan_count = 0
                                self.state_start_time = current_time
                                self.parent.antenna_controller.current_antenna_mode = "scanning"
                                self.target_pitch = 0

                # Interpolate toward target
                self.current_pan += (self.target_pan - self.current_pan) * self.INTERPOLATION_RATE
                self.current_roll += (self.target_roll - self.current_roll) * self.INTERPOLATION_RATE

                # Send positions
                self.reachy.head.neck_yaw.goal_position = self.current_pan
                self.reachy.head.neck_roll.goal_position = self.current_roll
                self.reachy.head.neck_pitch.goal_position = self.current_pitch
                cv.imshow('Reachy Face Tracking', image)
                
                time.sleep(0.03)  # ~30 FPS

            except Exception as e:
                print(f"Tracking error: {e}")
                time.sleep(0.1)


class AntennaController:
    def __init__(self, parent: "RobotController"):
        self.parent = parent
        self.reachy = parent.reachy
        self.current_antenna_mode = "idle"
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

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
            mode = self.current_antenna_mode
            try:
                match mode:
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

    def stop(self):
        self.running = False
        self.thread.join(timeout=2)


def main():
    testing = False

    if testing:
        main_controller = RobotController(None)
        main_controller.speech_controller.speech_loop("hello reachy", 30)
        return

    # Connect to Reachy
    print("Connecting to Reachy...")
    reachy = ReachySDK('localhost')
    
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
        robot_controller.speech_controller.speech_loop(wake_word="hey reachy", conversation_timeout=15)
                
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    finally:
        robot_controller.cleanup()
        reachy.turn_off_smoothly('head')
        print("✅ Done!")


if __name__ == "__main__":
    main()

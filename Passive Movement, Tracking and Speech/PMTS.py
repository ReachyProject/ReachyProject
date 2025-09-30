import random
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

load_dotenv()

# Initialize MediaPipe Face Detection
mp_face_detection = mp.solutions.face_detection
mp_drawing = mp.solutions.drawing_utils


class SpeechAPI:
    def __init__(self, voice_id="ljo9gAlSqKOvF6D8sOsX", model_id="eleven_multilingual_v2"):
        self.voice_id = voice_id
        self.model_id = model_id
        self.elevenlabs = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
        self.llm = Groq(api_key=os.getenv("GROQ_API_KEY"))

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

    def speech_to_text_with_vad(self, max_duration=10, silence_threshold=500, silence_duration=2.0) -> str:
        """Record audio until silence is detected or max duration is reached"""
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000
        CHUNK = 1024

        audio = pyaudio.PyAudio()
        stream = None

        try:
            stream = audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
                input_device_index=0
            )

            print("🎤 Listening...")
            frames = []
            silent_chunks = 0
            silence_chunks_needed = int(silence_duration * RATE / CHUNK)
            max_chunks = int(max_duration * RATE / CHUNK)
            
            recording_started = False
            
            for i in range(max_chunks):
                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    frames.append(data)
                    
                    # Calculate volume (RMS)
                    rms = self._get_rms(data)
                    
                    # Check if speaking
                    if rms > silence_threshold:
                        recording_started = True
                        silent_chunks = 0
                    else:
                        if recording_started:
                            silent_chunks += 1
                    
                    # Stop if we've had enough silence after speech started
                    if recording_started and silent_chunks > silence_chunks_needed:
                        print("✅ Silence detected, processing...")
                        break
                        
                    # Visual feedback
                    if i % 10 == 0:
                        if recording_started:
                            print(f"🔊 Recording... (volume: {rms:.0f})")
                        else:
                            print(f"👂 Waiting for speech... (volume: {rms:.0f})")
                except Exception as e:
                    print(f"Audio read error: {e}")
                    break

            if stream:
                stream.stop_stream()
                stream.close()

        finally:
            if stream:
                try:
                    stream.close()
                except:
                    pass
            audio.terminate()

        # Convert to WAV in memory
        wav_buffer = BytesIO()
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(audio.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))

        wav_buffer.seek(0)
        wav_buffer.name = "recording.wav"

        # Transcribe
        transcription = self.elevenlabs.speech_to_text.convert(
            file=wav_buffer,
            model_id="scribe_v1",
            tag_audio_events=False,
            language_code="eng",
            diarize=False,
        )

        return transcription.text

    def _get_rms(self, data):
        """Calculate RMS (Root Mean Square) for volume detection"""
        count = len(data) / 2
        format_str = "%dh" % count
        shorts = struct.unpack(format_str, data)
        sum_squares = sum((sample ** 2 for sample in shorts))
        rms = math.sqrt(sum_squares / count)
        return rms

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

    def detect_wake_word(self, wake_word="hey alex", timeout=30):
        """Listen for wake word with timeout"""
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000
        CHUNK = 1024
        RECORD_SECONDS = 3  # Listen in 3-second chunks

        audio = pyaudio.PyAudio()
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            frames = []
            stream = None
            
            try:
                stream = audio.open(
                    format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK,
                    input_device_index=0
                )

                for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    frames.append(data)

                stream.stop_stream()
                stream.close()
                stream = None

                # Convert to WAV
                wav_buffer = BytesIO()
                with wave.open(wav_buffer, 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(audio.get_sample_size(FORMAT))
                    wf.setframerate(RATE)
                    wf.writeframes(b''.join(frames))

                wav_buffer.seek(0)
                wav_buffer.name = "wake_word.wav"

                # Transcribe
                transcription = self.elevenlabs.speech_to_text.convert(
                    file=wav_buffer,
                    model_id="scribe_v1",
                    tag_audio_events=False,
                    language_code="eng",
                    diarize=False,
                )

                text = transcription.text.lower().strip()
                print(f"🔍 Heard: '{text}'")
                
                # Check if wake word is in the transcription (with fuzzy matching)
                if self._check_wake_word(text, wake_word):
                    audio.terminate()
                    return True
                    
            except Exception as e:
                print(f"Wake word detection error: {e}")
                if stream is not None:
                    try:
                        stream.stop_stream()
                        stream.close()
                    except:
                        pass
                time.sleep(0.5)
        
        audio.terminate()
        return False

    def generate_ai_response(self, prompt, llm_model="llama-3.3-70b-versatile") -> str:
        response = self.llm.chat.completions.create(
            model=llm_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a child, act stupid. Limit response length to 2-3 sentences. Responses should be possible to be played through elevenlabs. Add punctuation to the text; high prosody"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        return response.choices[0].message.content


class RoboticConversation:
    def __init__(self, reachy: ReachySDK, speech_api: SpeechAPI):
        self.reachy = reachy
        self.speech_api = speech_api
        
        # Camera parameters
        test_img = reachy.left_camera.last_frame
        self.frame_height, self.frame_width = test_img.shape[:2]
        self.frame_center_x = self.frame_width / 2
        self.frame_center_y = self.frame_height / 2
        
        # Smoothing parameters
        self.DEADBAND = 0.04
        self.MOVEMENT_GAIN = 50
        self.SMOOTHING_ALPHA = 0.5
        
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
        
        # Scanning state
        self.scanning_state = "idle"
        self.scan_count = 0
        self.MAX_SCANS = 1
        self.state_start_time = 0
        
        # Antenna control
        self.antenna_thread_running = True
        self.current_antenna_mode = "idle"
        self.antenna_thread = threading.Thread(target=self._antenna_controller, daemon=True)
        self.antenna_thread.start()
        
        # Face detection
        self.face_detection = mp_face_detection.FaceDetection(
            model_selection=1, 
            min_detection_confidence=0.9
        )
        
        # Tracking thread
        self.tracking_thread_running = False
        self.tracking_thread = None
        
        # Conversation state
        self.conversation_active = False

    def _antenna_controller(self):
        """Background thread to control antenna movements"""
        while self.antenna_thread_running:
            try:
                if self.current_antenna_mode == "sad":
                    self.reachy.head.l_antenna.goal_position = -125
                    self.reachy.head.r_antenna.goal_position = 125
                    time.sleep(0.3)
                    self.reachy.head.l_antenna.goal_position = -120
                    self.reachy.head.r_antenna.goal_position = 120
                    
                elif self.current_antenna_mode == "tracking":
                    base_left = -15
                    base_right = 15
                    wiggle = random.uniform(-15, 15)
                    
                    self.reachy.head.l_antenna.goal_position = base_left + wiggle
                    self.reachy.head.r_antenna.goal_position = base_right - wiggle
                    time.sleep(random.uniform(0.3, 0.8))
                    
                elif self.current_antenna_mode == "idle":
                    self.reachy.head.l_antenna.goal_position = 0
                    self.reachy.head.r_antenna.goal_position = 0
                    time.sleep(0.5)
                    
                elif self.current_antenna_mode == "scanning":
                    for _ in range(2):
                        if not self.antenna_thread_running or self.current_antenna_mode != "scanning":
                            break
                        self.reachy.head.l_antenna.goal_position = -125
                        self.reachy.head.r_antenna.goal_position = 125
                        time.sleep(0.3)
                        self.reachy.head.l_antenna.goal_position = -100
                        self.reachy.head.r_antenna.goal_position = 100
                        time.sleep(0.3)
                        
                elif self.current_antenna_mode == "giving_up":
                    for pos in range(0, -21, -2):
                        if not self.antenna_thread_running or self.current_antenna_mode != "giving_up":
                            break
                        self.reachy.head.l_antenna.goal_position = -pos
                        self.reachy.head.r_antenna.goal_position = pos
                        time.sleep(0.1)
                        
                elif self.current_antenna_mode == "talking":
                    # Excited antenna movement while talking
                    base_left = -15
                    base_right = 15
                    wiggle = random.uniform(-25, 25)
                    
                    self.reachy.head.l_antenna.goal_position = base_left + wiggle
                    self.reachy.head.r_antenna.goal_position = base_right - wiggle
                    time.sleep(random.uniform(0.2, 0.4))
                        
            except Exception as e:
                print(f"Antenna error: {e}")
                time.sleep(0.5)

    def _tracking_loop(self):
        """Main tracking loop that runs continuously"""
        self.current_pan = self.reachy.head.neck_yaw.present_position
        self.current_roll = self.reachy.head.neck_roll.present_position
        self.current_pitch = self.reachy.head.neck_pitch.present_position
        self.target_pan = self.current_pan
        self.target_roll = self.current_roll
        self.target_pitch = self.current_pitch
        
        while self.tracking_thread_running:
            try:
                self.frame_count += 1
                current_time = time.time()
                
                image = self.reachy.left_camera.last_frame
                if image is None:
                    continue

                # Process image
                image.flags.writeable = False
                image_rgb = cv.cvtColor(image, cv.COLOR_BGR2RGB)
                results = self.face_detection.process(image_rgb)
                
                if results.detections:
                    # FACE DETECTED
                    self.no_face_count = 0
                    self.scan_count = 0
                    self.scanning_state = "idle"
                    
                    # Set antenna mode based on conversation state
                    if not self.conversation_active:
                        self.current_antenna_mode = "tracking"
                    
                    detection = results.detections[0]
                    bbox = detection.location_data.relative_bounding_box
                    
                    face_center_x = (bbox.xmin + bbox.width / 2) * self.frame_width
                    face_center_y = (bbox.ymin + bbox.height / 2) * self.frame_height
                    
                    error_x = (face_center_x - self.frame_center_x) / self.frame_width
                    error_y = (face_center_y - self.frame_center_y) / self.frame_height
                    
                    self.smoothed_error_x = self.SMOOTHING_ALPHA * error_x + (1 - self.SMOOTHING_ALPHA) * self.smoothed_error_x
                    self.smoothed_error_y = self.SMOOTHING_ALPHA * error_y + (1 - self.SMOOTHING_ALPHA) * self.smoothed_error_y
                    
                    if abs(self.smoothed_error_x) > self.DEADBAND or abs(self.smoothed_error_y) > self.DEADBAND:
                        actual_pan = self.reachy.head.neck_yaw.present_position
                        actual_roll = self.reachy.head.neck_roll.present_position
                        
                        pan_movement = -self.smoothed_error_x * self.MOVEMENT_GAIN
                        roll_movement = -self.smoothed_error_y * self.MOVEMENT_GAIN
                        
                        new_target_pan = actual_pan + pan_movement
                        new_target_roll = actual_roll + roll_movement
                        
                        if abs(new_target_pan - self.target_pan) > self.MIN_MOVEMENT_THRESHOLD or \
                           abs(new_target_roll - self.target_roll) > self.MIN_MOVEMENT_THRESHOLD:
                            self.target_pan = new_target_pan
                            self.target_roll = new_target_roll
                    
                    self.target_pitch = 0
                    
                else:
                    # NO FACE - scanning state machine (only if not in conversation)
                    if not self.conversation_active:
                        self.no_face_count += 1
                        
                        if self.scanning_state == "idle":
                            if self.no_face_count >= 60:
                                self.scanning_state = "scanning"
                                self.scan_count = 0
                                self.state_start_time = current_time
                                self.current_antenna_mode = "scanning"
                            else:
                                self.current_antenna_mode = "idle"
                                
                        elif self.scanning_state == "scanning":
                            self.current_antenna_mode = "scanning"
                            
                            if self.frame_count % 90 == 0:
                                self.scan_count += 1
                                
                                if self.scan_count > self.MAX_SCANS:
                                    self.scanning_state = "giving_up"
                                    self.state_start_time = current_time
                                    self.current_antenna_mode = "giving_up"
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
                                    
                        elif self.scanning_state == "giving_up":
                            if current_time - self.state_start_time > 1.5:
                                self.scanning_state = "sad"
                                self.state_start_time = current_time
                                self.current_antenna_mode = "sad"
                                
                        elif self.scanning_state == "sad":
                            self.current_antenna_mode = "sad"
                            
                            if current_time - self.state_start_time > 2.0:
                                self.scanning_state = "looking_down"
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
                                
                        elif self.scanning_state == "looking_down":
                            self.current_antenna_mode = "sad"
                            
                            if current_time - self.state_start_time > 3.0:
                                self.scanning_state = "waiting"
                                self.state_start_time = current_time
                                
                        elif self.scanning_state == "waiting":
                            self.current_antenna_mode = "sad"
                            
                            if current_time - self.state_start_time > 2.0:
                                self.scanning_state = "scanning"
                                self.scan_count = 0
                                self.state_start_time = current_time
                                self.current_antenna_mode = "scanning"
                                self.target_pitch = 0
                
                # Interpolate toward target
                self.current_pan += (self.target_pan - self.current_pan) * self.INTERPOLATION_RATE
                self.current_roll += (self.target_roll - self.current_roll) * self.INTERPOLATION_RATE
                
                # Send positions
                self.reachy.head.neck_yaw.goal_position = self.current_pan
                self.reachy.head.neck_roll.goal_position = self.current_roll
                self.reachy.head.neck_pitch.goal_position = self.current_pitch
                
                time.sleep(0.03)  # ~30 FPS
                
            except Exception as e:
                print(f"Tracking error: {e}")
                time.sleep(0.1)

    def start_tracking(self):
        """Start the background tracking thread"""
        if self.tracking_thread is None or not self.tracking_thread.is_alive():
            self.tracking_thread_running = True
            self.tracking_thread = threading.Thread(target=self._tracking_loop, daemon=True)
            self.tracking_thread.start()
            print("✅ Tracking started")

    def stop_tracking(self):
        """Stop the background tracking thread"""
        self.tracking_thread_running = False
        if self.tracking_thread is not None:
            self.tracking_thread.join(timeout=2)
        print("🛑 Tracking stopped")

    def conversation_loop(self, wake_word="hey reachy", conversation_timeout=15):
        """Active conversation loop with wake word detection and continuous conversation mode"""
        print(f"\n👂 Listening for wake word: '{wake_word}'...")
        
        in_conversation = False
        last_interaction_time = 0
        
        while True:
            current_time = time.time()
            
            # Check if we should exit conversation mode due to timeout
            if in_conversation and (current_time - last_interaction_time > conversation_timeout):
                print(f"\n💤 Conversation timeout after {conversation_timeout}s of silence")
                in_conversation = False
                self.conversation_active = False
                self.current_antenna_mode = "tracking"
                print(f"👂 Listening for wake word: '{wake_word}'...")
            
            # If not in conversation, wait for wake word
            if not in_conversation:
                if self.speech_api.detect_wake_word(wake_word=wake_word, timeout=30):
                    print(f"\n🎉 Wake word detected!")
                    in_conversation = True
                    self.conversation_active = True
                    self.current_antenna_mode = "talking"
                    last_interaction_time = current_time
                else:
                    print("⏰ Wake word timeout, continuing to listen...")
                    continue
            
            # In conversation mode - just listen for speech
            if in_conversation:
                try:
                    user_speech = self.speech_api.speech_to_text_with_vad(
                        max_duration=10,
                        silence_threshold=500,
                        silence_duration=2.0
                    )
                    
                    # Update last interaction time
                    last_interaction_time = time.time()
                    
                    print(f"👤 User: {user_speech}")
                    
                    if user_speech.strip():
                        # Generate response
                        print("🤔 Thinking...")
                        ai_response = self.speech_api.generate_ai_response(user_speech)
                        print(f"🤖 Reachy: {ai_response}")
                        
                        # Speak response (tracking continues in background)
                        audio_bytes = self.speech_api.text_to_speech(ai_response)
                        play(audio_bytes)
                        
                        # Update time again after response
                        last_interaction_time = time.time()
                        
                        print("👂 Continue speaking or pause to end conversation...")
                    else:
                        print("🤷 No speech detected, listening...")
                        
                except Exception as e:
                    print(f"Conversation error: {e}")
                    time.sleep(1)

    def cleanup(self):
        """Clean up all threads and return to neutral"""
        print("\n🧹 Cleaning up...")
        
        self.stop_tracking()
        
        self.antenna_thread_running = False
        self.antenna_thread.join(timeout=2)
        
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


def main():
    # Connect to Reachy
    print("Connecting to Reachy...")
    reachy = ReachySDK('localhost')
    
    print("Turning on head...")
    reachy.turn_on('head')
    time.sleep(1)
    
    # Initialize speech API
    speech_api = SpeechAPI(voice_id="6XVxc5pFxXre3breYJhP")
    
    # Create conversation manager
    conversation = RoboticConversation(reachy, speech_api)
    
    # Start passive tracking
    conversation.start_tracking()
    
    try:
        print("\n" + "="*60)
        print("🤖 Reachy is now tracking faces and listening")
        print("Say 'Hey Reachy' to start a conversation")
        print("Once in conversation, just keep talking naturally")
        print("Conversation ends after 30s of silence")
        print("Press Ctrl+C to quit")
        print("="*60 + "\n")
        
        # Start conversation loop with 15 second timeout
        conversation.conversation_loop(wake_word="hey reachy", conversation_timeout=30)
                
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    finally:
        conversation.cleanup()
        reachy.turn_off_smoothly('head')
        print("✅ Done!")


if __name__ == "__main__":
    main()
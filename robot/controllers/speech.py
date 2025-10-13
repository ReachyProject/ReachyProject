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

from .audio import AudioController


class SpeechController:
    def __init__(self, parent: "RobotController" = None,voice_id=None, model_id="eleven_multilingual_v2"):
        load_dotenv()
        self.voice_id = os.getenv("VOICE_ID")
        self.model_id = model_id
        self.parent = parent
        self.elevenlabs = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
        self.llm = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.audio_controller = AudioController(parent)

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

    def detect_wake_word(self, wake_word, timeout=15) -> bool:
        print("wake")
        """
        Uses VAD to capture short phrases until wake word is detected.
        Avoids short false triggers by capturing full short utterances.
        """
        try:

            print(f"👂 Listening for wake word '{wake_word}'...")
            start_time = time.time()

            while time.time() - start_time < timeout:
                print("a")
                speech, wav_buffer = self.audio_controller.record_until_silence(
                    max_duration=5,
                    silence_duration=1.5
                )
                print("ab")
                if speech == False:
                    print("no speech")
                    continue
                if not wav_buffer.getbuffer().nbytes:
                    continue  # nothing captured, keep waiting
                print("b")
                try:
                    print("found some speech")
                    transcription = self.elevenlabs.speech_to_text.convert(
                        file=wav_buffer,
                        model_id="scribe_v1",
                        language_code="eng",
                        tag_audio_events=False,
                        diarize=False,
                    )

                    text = transcription.text.lower().strip()
                    print("text: ", text)

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


            print("⏰ Wake word timeout.")
            return False
        except Exception as e:
            print(f"bruhge: {e}")

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

import os
import time
from io import BytesIO
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.play import play
from groq import Groq
from rich import print
import typing
from robot.controllers.audio import AudioController
import Flask.handlers.save_config as save_config
import json

class SpeechController:
    def __init__(self, parent: "RobotController" = None, model_id="eleven_multilingual_v2"):
        save_config.get_env_config()
        load_dotenv()
        self.model_id = model_id
        self.parent = parent
        self.elevenlabs = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
        self.llm = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.audio_controller = AudioController(parent)
        self.conversation_path = ""
        self.conversation_history = []
    
    def load_conversation(self, file_path):
        if file_path == "":
            file_path = self.conversation_path

        if not os.path.exists(file_path):
            print(f"💬 No existing conversation file found at '{file_path}'. Starting new conversation.")
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list) and all(isinstance(msg, dict) and "role" in msg and "content" in msg for msg in data):
                self.conversation_history = data
                print(f"✅ Loaded {len(self.conversation_history)} messages from {file_path}")
            else:
                print("⚠️ Invalid conversation format, starting new conversation.")
        except Exception as e:
            print(f"⚠️ Error loading conversation: {e}")

        return

    async def save_conversation(self, path: str = None):
        """Save the current conversation history to disk."""
        file_path = path or self.conversation_path
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.conversation_history, f, indent=2, ensure_ascii=False)
            print(f"💾 Conversation saved to {file_path}")
        except Exception as e:
            print(f"⚠️ Failed to save conversation: {e}")

    def reset_conversation(self):
        """Clear chat history (e.g., when wake word is triggered again)."""
        self.conversation_history = []

    def text_to_speech(self, input_text) -> typing.Iterator[bytes]:
        from Flask.handlers.save_config import CURRENT_VOICE_ID

        audio = self.elevenlabs.text_to_speech.convert(
            text=input_text,
            voice_id=CURRENT_VOICE_ID,
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
        if not self.conversation_history:
            self.conversation_history.append({
                "role": "system",
                "content": system_prompt
            })
        else:
            self.conversation_history[0] = {
                "role": "system",
                "content": system_prompt
            }

        self.conversation_history.append({
             "role": "user",
             "content": prompt
        })
        response = self.llm.chat.completions.create(
            model=llm_model,
            messages=self.conversation_history
        )
        assistant_reply = response.choices[0].message.content

        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_reply
        })
        return assistant_reply

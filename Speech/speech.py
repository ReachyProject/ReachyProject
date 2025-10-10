from io import BytesIO
import os

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from groq import Groq
from elevenlabs.play import play
import pyaudio
import wave
from pydub import AudioSegment
from pydub.playback import play as pyplay


load_dotenv()

class SpeechAPI:
    def __init__(self, voice_id="ljo9gAlSqKOvF6D8sOsX", model_id="eleven_multilingual_v2"):
        self.voice_id = voice_id
        self.model_id = model_id

        self.elevenlabs = ElevenLabs(
            api_key=os.getenv("ELEVENLABS_API_KEY"),
        )
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
    
    
    def list_audio_devices(self):
        audio = pyaudio.PyAudio()
        print("\n=== Available Audio Devices ===")
        for i in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(i)
            print(f"Device {i}: {info['name']}")
            print(f"  Input channels: {info['maxInputChannels']}")
            print(f"  Output channels: {info['maxOutputChannels']}")
            print(f"  Default sample rate: {info['defaultSampleRate']}")
        audio.terminate()
        

    def speech_to_text(self) -> str:
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 44100
        CHUNK = 1024
        RECORD_SECONDS = 5

        audio = pyaudio.PyAudio()

        # RECORDING
        stream = audio.open(format=FORMAT, channels=CHANNELS,
                            rate=RATE, input=True,
                            frames_per_buffer=CHUNK)
        print("Recording...")
        frames = []
        for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
            data = stream.read(CHUNK)
            frames.append(data)

        stream.stop_stream()
        stream.close()

        audio_bytes = b''.join(frames)

        # Convert to WAV in memory
        wav_buffer = BytesIO()
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(audio.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(audio_bytes)

        wav_buffer.seek(0)
        wav_buffer.name = "recording.wav"

        # ✅ Terminate after all streams are closed
        audio.terminate()

        audio_segment = AudioSegment.from_wav(wav_buffer)
        pyplay(audio_segment)

        print("Playback finished.")

        # TRANSCRIBE
        transcription = self.elevenlabs.speech_to_text.convert(
            file=wav_buffer,
            model_id="scribe_v1",
            tag_audio_events=False,
            language_code="eng",
            diarize=False,
        )

        return transcription



    def generate_ai_response(self, prompt, llm_model="llama-3.3-70b-versatile") -> str:
        response = self.llm.chat.completions.create(
            model=llm_model,
            messages=[ # type: ignore
                {
                    "role": "system",
                    "content": "You are a child. Act playful and curious, using simple, childlike responses. Limit response length to 2-3 sentences. Responses should be possible to be played through elevenlabs. Add punctuation to the text; high prosody"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        return response.choices[0].message.content


def main():
    api = SpeechAPI(voice_id="6XVxc5pFxXre3breYJhP")
    print(api.speech_to_text())
    
    response = api.generate_ai_response(input("Input: "))
    print(response)
    llm_response =  api.text_to_speech(response)
    play(llm_response)

if __name__ == "__main__":
    main()
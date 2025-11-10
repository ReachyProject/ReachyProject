import time
import math
import wave
import queue
import struct
import threading
from io import BytesIO
from collections import deque
from difflib import SequenceMatcher

import pyaudio
import webrtcvad
from rich import print



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
        print("test")
        rate, fmt, channels = self.rate, self.format, self.channels
        chunk_ms = 30
        chunk = int(rate * chunk_ms / 1000)
        silence_frames = int(silence_duration * 1000 / chunk_ms)
        print("open")
        stream = self.audio.open(
            format=fmt, channels=channels, rate=rate,
            input=True, frames_per_buffer=chunk, input_device_index=2
        )
        print("🎤 Listening (record until silence)...")

        vad = self.vad
        pre_buffer = deque(maxlen=10)
        voiced_frames = []
        silence_count = 0
        speech_started = False
        start_time = time.time()
        recording_time = 0.0
        timeout = False
        print("a")
        try:
            while True:
                frame = stream.read(chunk, exception_on_overflow=False)
                is_speech = vad.is_speech(frame, rate)
                print("b")
                if not speech_started:
                    pre_buffer.append(frame)
                    if is_speech:
                        speech_started = True
                        recording_time = time.time()
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
                if speech_started and time.time() - recording_time > max_duration:
                    print("Recording time used; stopping.")
                    timeout = True
                    break
                elif time.time() - start_time > max_duration and speech_started == False:
                    timeout = True
                    print("Timeout reached; stopping.")
                    break

        finally:
            stream.stop_stream()
            stream.close()

        if timeout:
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

    def similar(self, a: str, b: str) -> float:
        words_a = a.lower().split()
        words_b = b.lower().split()
        
        best_score = 0.0

        for word_a in words_a:
            for word_b in words_b:
                score = SequenceMatcher(None, word_a, word_b).ratio()
                if score > best_score:
                    best_score = score

        return best_score
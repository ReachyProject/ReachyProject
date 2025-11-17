"""
Standalone test for SpeechController:
- Records your voice until silence
- Transcribes it using ElevenLabs STT
- Sends it to Groq LLM for a response
- Speaks the reply aloud via ElevenLabs TTS
"""

from robot.controllers.speech import SpeechController
from elevenlabs.play import play


def main():
    # Initialize SpeechController (loads .env, Groq, ElevenLabs, mic)
    print("🎙 Initializing speech system...")
    speech = SpeechController()

    print("\n🎤 Say something after the beep (recording stops after silence)...\n")

    # Record until silence
    detected, wav_buffer = speech.audio_controller.record_until_silence(max_duration=10, silence_duration=1)
    if not detected:
        print("⚠️ No speech detected. Try again.")
        return

    # Convert to text using ElevenLabs STT
    print("🧠 Transcribing...")
    transcription = speech.elevenlabs.speech_to_text.convert(
        file=wav_buffer,
        model_id="scribe_v1",
        tag_audio_events=False,
        language_code="eng",
        diarize=False,
    )

    text = transcription.text.strip()
    print(f"👤 You said: {text}")

    # Send to Groq LLM for response
    print("🤖 Generating AI response...")
    system_prompt = (
        "You are Reachy the robot, a curious child-like AI. "
        "Reply in a friendly, simple way. Keep answers short (1–3 sentences)."
    )
    response = speech.generate_ai_response(text, system_prompt)
    print(f"Reachy: {response}")

    # Convert to speech and play
    print("🗣 Speaking response...")
    audio_bytes = speech.text_to_speech(response)
    print(audio_bytes)
    play(audio=audio_bytes)

    print("\n✅ Conversation complete!")


if __name__ == "__main__":
    main()

from flask import Blueprint, request, jsonify
from pathlib import Path
from Flask.constants import ELEVENLABS_VOICES, AGE_RANGES, MOODS, ASSISTANT_TYPES, PERSONAS
import os
from dotenv import load_dotenv
from pathlib import Path

CURRENT_AGE = None
CURRENT_MOOD = None
CURRENT_ASSISTANT = None
CURRENT_PERSONA = None
CURRENT_VOICE_ID = None

def get_env_config():
    """
    Loads persona config from .env with safety and fallbacks.
    Returns a dict with persona, age_range, mood, assistant_type,
    llm_provider, llm_model, and voice_id.
    """
    global CURRENT_PERSONA, CURRENT_AGE, CURRENT_MOOD, CURRENT_ASSISTANT, CURRENT_VOICE_ID

    env_path = Path('.env')
    load_dotenv(env_path)  # Load .env into environment

    persona = os.getenv("PERSONA")
    age_range = os.getenv("AGE_RANGE")
    mood = os.getenv("MOOD")
    llm_provider = os.getenv("LLM_PROVIDER")
    llm_model = os.getenv("LLM_MODEL")
    voice_id = os.getenv("VOICE_ID")
    assistant = os.getenv("ASSISTANT_TYPE")


    # ----- DEFAULTS -----
    default_persona = PERSONAS[0]
    default_age = "Old Man"
    default_mood = "Happy"
    default_assistant = "Educational"

    # If persona missing, fallback
    CURRENT_PERSONA = persona or default_persona
    CURRENT_AGE = age_range or default_age
    CURRENT_MOOD = mood or default_mood
    CURRENT_ASSISTANT = assistant or default_assistant
    CURRENT_VOICE_ID = voice_id or ELEVENLABS_VOICES.get(persona, "")

    print("voice in config  file")
    print(CURRENT_VOICE_ID)


def write_to_env(persona=None, age_range=None, mood=None, llm_provider=None, llm_model=None, voice_id=None, assistant_type=None):
    """Update specific configuration values in a .env file without overwriting everything"""
    env_path = Path('.env')
    env_vars = {}

    # Read existing env variables if the file exists
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value

    # Update only the values provided
    if persona is not None:
        env_vars['PERSONA'] = persona
    if age_range is not None:
        env_vars['AGE_RANGE'] = age_range
    if mood is not None:
        env_vars['MOOD'] = mood
    if llm_provider is not None:
        env_vars['LLM_PROVIDER'] = llm_provider
    if llm_model is not None:
        env_vars['LLM_MODEL'] = llm_model
    if voice_id is not None:
        env_vars['VOICE_ID'] = voice_id
    if assistant_type is not None:
        env_vars['ASSISTANT_TYPE'] = assistant_type

    # Write back all variables to the file
    with open(env_path, 'w', encoding='utf-8') as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")

    return True


save_config_bp = Blueprint('save_config', __name__)

@save_config_bp.route('/save_config', methods=['POST'])
def save_config():
    try:
        data = request.json
        persona = data.get('persona')
        age_range = data.get('age_range')
        mood = data.get('mood')
        llm_provider = data.get('llm_provider')
        llm_model = data.get('llm_model')
        assistant_type = data.get('assistant_type')

        persona_index = PERSONAS.index(persona)

        # Save config and get the voice ID
        voice_id = ELEVENLABS_VOICES.get(persona, "")
        print("voice added:")
        print(voice_id)
        write_to_env(
            persona_index, 
            age_range, mood, 
            llm_provider, 
            llm_model, 
            voice_id, 
            assistant_type
        )
        global CURRENT_PERSONA, CURRENT_AGE, CURRENT_MOOD, CURRENT_ASSISTANT, CURRENT_VOICE_ID

        CURRENT_AGE = age_range
        CURRENT_MOOD = mood
        CURRENT_VOICE_ID = voice_id
        CURRENT_PERSONA = persona_index
        CURRENT_ASSISTANT = assistant_type

        return jsonify({
            'success': True,
            'message': 'Configuration saved',
            'voice_id': voice_id
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

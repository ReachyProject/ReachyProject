from flask import request, jsonify
from pathlib import Path
from constants import ELEVENLABS_VOICES


def write_to_env(persona, age_range, mood, llm_provider, llm_model):
    """Write configuration to .env file"""
    env_path = Path('.env')

    voice_id = ELEVENLABS_VOICES.get(persona, "")

    env_content = f"""PERSONA={persona}
    AGE_RANGE={age_range}
    MOOD={mood}
    LLM_PROVIDER={llm_provider}
    LLM_MODEL={llm_model}
    VOICE_ID={voice_id}
    """
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(env_content)
    return True


def save_config():
    try:
        data = request.json
        persona = data.get('persona')
        age_range = data.get('age_range')
        mood = data.get('mood')
        llm_provider = data.get('llm_provider')
        llm_model = data.get('llm_model')

        # Save config and get the voice ID
        voice_id = ELEVENLABS_VOICES.get(persona, "")
        write_to_env(persona, age_range, mood, llm_provider, llm_model)

        return jsonify({
            'success': True,
            'message': 'Configuration saved',
            'voice_id': voice_id
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

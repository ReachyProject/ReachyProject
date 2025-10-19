from constants import (
    PERSONAS, AGE_RANGES, ELEVENLABS_VOICES,
    MOODS, ASSISTANT_TYPES, LLM_PROVIDERS, LLM_MODELS
)
from flask import Blueprint, request, jsonify


persona_config_bp = Blueprint('persona_config', __name__)

@persona_config_bp.route('/api/personas/options', methods=['GET'])
def get_persona_options():
#Return all persona-related configuration options.
    return jsonify({
        "personas": PERSONAS,
        "age_ranges": AGE_RANGES,
        "voice_mappings": ELEVENLABS_VOICES,
        "moods": list(MOODS.keys()),
        "assistant_types": list(ASSISTANT_TYPES.keys()),
        "llm_providers": LLM_PROVIDERS,
        "llm_models": LLM_MODELS
    })


@persona_config_bp.route('/api/personas/build_prompt', methods=['POST'])
def build_persona_prompt():
    #Builds a system prompt based on user input.
    data = request.json

    persona = data.get("persona")
    age_range = data.get("age_range")
    mood = data.get("mood")
    assistant_type = data.get("assistant_type")

    if not all([persona, mood, assistant_type]):
        return jsonify({"error": "Missing required fields"}), 400

    prompt = build_system_prompt(persona, age_range, mood, assistant_type)

    return jsonify({"prompt": prompt})

def get_persona_profile(persona, mood, assistant_type, llm_provider=None, llm_model=None, age_range=None):
    if not llm_provider:
        llm_provider = LLM_PROVIDERS[0]  # default to first provider
    if not llm_model:
        llm_model = LLM_MODELS.get(llm_provider, [None])[0]
        
    return {
        "persona": persona,
        "age_range": age_range or (AGE_RANGES.get(persona, [])[0] if AGE_RANGES.get(persona) else None),
        "voice_id": ELEVENLABS_VOICES.get(persona),
        "mood": {
            "name": mood,
            "description": MOODS.get(mood, "")
        },
        "assistant_type": {
            "name": assistant_type,
            "description": ASSISTANT_TYPES.get(assistant_type, "")
        },
        "llm": {
            "provider": llm_provider,
            "model": llm_model
        }
    }


def build_system_prompt(persona, age_range, mood, assistant_type):

    mood_desc = MOODS.get(mood, "")
    assistant_desc = ASSISTANT_TYPES.get(assistant_type, "")

    # Persona descriptor
    persona_part = f"You are a {mood.lower()} {persona.lower()}"
    if age_range:
        persona_part += f" aged around {age_range}"
    persona_part += "."

    # Combine everything
    prompt = (
        f"{persona_part} "
        f"{mood_desc} "
        f"{assistant_desc} "
        f"Adjust your responses to reflect both your personality and emotional tone."
    )

    return prompt.strip()

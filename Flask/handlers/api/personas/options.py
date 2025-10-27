from flask import jsonify
from constants import (
    PERSONAS, AGE_RANGES, ELEVENLABS_VOICES, MOODS, 
    ASSISTANT_TYPES, LLM_PROVIDERS, LLM_MODELS
)


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

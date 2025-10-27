from flask import render_template
from constants import (
    AGE_RANGES, MOODS, LLM_PROVIDERS, LLM_MODELS,
    ELEVENLABS_VOICES, ASSISTANT_TYPES
)

def index():
    return render_template(
        'index.html', 
        personas=list(ELEVENLABS_VOICES.keys()),
        voice_mappings=ELEVENLABS_VOICES,
        age_ranges=AGE_RANGES,
        moods=MOODS,
        llm_providers=LLM_PROVIDERS,
        llm_models=LLM_MODELS,
        assistant_types=ASSISTANT_TYPES
    )

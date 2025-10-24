from flask import Blueprint, render_template, request, jsonify
from constants import (
    AGE_RANGES, MOODS, LLM_PROVIDERS, LLM_MODELS,
    ELEVENLABS_VOICES, ASSISTANT_TYPES
)

index_bp = Blueprint('index', __name__)

@index_bp.route('/')
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


@index_bp.route('/build_prompt', methods=['POST'])
def build_prompt():
    data = request.json
    persona = data.get("persona")
    age_range = data.get("age_range")
    mood = data.get("mood")
    assistant_type = data.get("assistant_type")
    provider = data.get("llm_provider")
    model = data.get("llm_model")

    # Basic validation
    if not all([persona, age_range, mood, assistant_type, provider, model]):
        return jsonify({"success": False, "message": "Missing one or more fields."}), 400

    # Build the system prompt
    prompt = (
        f"You are a {persona} ({age_range}) AI persona. "
        f"{MOODS[mood]} "
        f"{ASSISTANT_TYPES[assistant_type]} "
        f"You are powered by {provider} using the {model} model."
    )

    # Select voice ID (fallback if needed)
    voice_id = ELEVENLABS_VOICES.get(persona, "default")

    return jsonify({
        "success": True,
        "message": "Prompt generated successfully.",
        "prompt": prompt,
        "voice_id": voice_id
    })

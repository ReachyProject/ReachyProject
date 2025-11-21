from personas import build_system_prompt
from flask import request, jsonify


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


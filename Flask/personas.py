from constants import (
    ELEVENLABS_VOICES, MOODS, ASSISTANT_TYPES, 
    LLM_PROVIDERS, LLM_MODELS, AGE_RANGES
)

def build_system_prompt(persona, age_range, mood, assistant_type):
    """Build a system prompt"""
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


def get_persona_profile(persona, mood, assistant_type, llm_provider=None, llm_model=None, age_range=None):
    """Get the profile of a persona"""
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


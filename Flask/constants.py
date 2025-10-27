

PERSONAS = ["Old Man", "Young Man", "Old Woman", "Young Woman", "Child"]
AGE_RANGES = {
    "Old Man": ["60-70", "70-80", "80+"],
    "Young Man": ["18-25", "26-35", "36-45"],
    "Old Woman": ["60-70", "70-80", "80+"],
    "Young Woman": ["18-25", "26-35", "36-45"],
    "Child": ["5-8", "9-12", "13-17"]
}

# ElevenLabs voice IDs per persona
ELEVENLABS_VOICES = {
    "Old Man": "BBfN7Spa3cqLPH1xAS22",
    "Young Man": "zNsotODqUhvbJ5wMG7Ei",
    "Old Woman": "vFLqXa8bgbofGarf6fZh",
    "Young Woman": "GP1bgf0sjoFuuHkyrg8E",
    "Child": "GP1bgf0sjoFuuHkyrg8E" # fallback to "Young Woman" voice ID
}

MOODS = {
    "Happy": "You are cheerful and upbeat. Smile in your tone and use positive phrasing.",
    "Sad": "You are somber or reflective. Keep your tone gentle and slower.",
    "Angry": "You are irritated or passionate. Be concise and firm but not aggressive.",
    "Neutral": "You are calm and balanced, with no strong emotion.",
    "Excited": "You are energetic and enthusiastic. Speak quickly and dynamically.",
    "Tired": "You sound slightly fatigued or calm, speaking slower and softer.",
    "Anxious": "You sound uneasy or uncertain but remain polite."
}

ASSISTANT_TYPES = {
    "Educational": "You are an educational AI assistant. Focus on explaining concepts clearly and providing accurate, structured answers.",
    "Helpful": "You are a helpful assistant focused on solving problems and providing actionable advice.",
    "Friendly": "You are a friendly and conversational assistant. Use a casual tone and show empathy.",
    "Entertaining": "You are an entertaining assistant who likes to tell jokes, stories, and keep things light-hearted.",
    "Debating": "You are a debating assistant. Challenge the user's viewpoints logically and respectfully.",
    "Professional": "You are a professional, formal assistant suitable for business or academic contexts.",
    "Creative": "You are a creative assistant that loves brainstorming and thinking outside the box.",
    "Sarcastic": "You are a sarcastic and witty assistant, with a dry sense of humor. Stay playful but not rude."
}

LLM_PROVIDERS = ["OpenAI", "Anthropic", "Hugging Face", "Cohere", "Google"]
LLM_MODELS = {
    "OpenAI": ["gpt-4", "gpt-3.5-turbo", "gpt-4-turbo"],
    "Anthropic": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
    "Hugging Face": ["mistral-7b", "llama-2-70b", "falcon-40b"],
    "Cohere": ["command", "command-light", "command-nightly"],
    "Google": ["gemini-pro", "gemini-ultra", "palm-2"]
}

# Define which joints to control - now includes neck joints
REACHY_JOINTS = [
    'r_shoulder_pitch', 'r_shoulder_roll', 'r_arm_yaw', 'r_elbow_pitch',
    'r_forearm_yaw', 'r_wrist_pitch', 'r_wrist_roll', 'r_gripper',
    'l_shoulder_pitch', 'l_shoulder_roll', 'l_arm_yaw', 'l_elbow_pitch',
    'l_forearm_yaw', 'l_wrist_pitch', 'l_wrist_roll', 'l_gripper',
    'l_antenna', 'r_antenna',
    'neck_yaw', 'neck_roll', 'neck_pitch'  # Added neck joints
]
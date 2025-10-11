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

MOODS = ["Happy", "Sad", "Angry", "Neutral", "Excited", "Tired", "Anxious"]
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
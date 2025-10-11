from flask import Blueprint, render_template
from constants import AGE_RANGES, MOODS, LLM_PROVIDERS, LLM_MODELS

index_bp = Blueprint('index', __name__)

@index_bp.route('/')
def index():
    voice_mappings = {
       "Old Man": "BBfN7Spa3cqLPH1xAS22",
        "Young Man": "zNsotODqUhvbJ5wMG7Ei",
        "Old Woman": "vFLqXa8bgbofGarf6fZh",
        "Young Woman": "GP1bgf0sjoFuuHkyrg8E",
        "Child": None  # No child voice available
    }

    return render_template('index.html', 
                    personas=list(voice_mappings.keys()),
                    voice_mappings=voice_mappings,
                    age_ranges=AGE_RANGES,
                    moods=MOODS,
                    llm_providers=LLM_PROVIDERS,
                    llm_models=LLM_MODELS)
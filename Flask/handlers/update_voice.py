from flask import Blueprint, request, jsonify
from dotenv import set_key


update_voice_bp = Blueprint('update_voice', __name__)

@update_voice_bp.route('/update_voice', methods=['POST'])
def update_voice():
    data = request.get_json()
    voice_id = data.get('VOICE_ID')
    
    if not voice_id:
        return jsonify({'success': False, 'message': 'No voice ID provided'}), 400

    set_key('.env', 'VOICE_ID', voice_id)
    return jsonify({'success': True, 'message': f'Voice ID updated to {voice_id}'})
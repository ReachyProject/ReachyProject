from flask import request, jsonify
from dotenv import set_key


def update_voice():
    data = request.get_json()
    voice_id = data.get('VOICE_ID')

    if not voice_id:
        return jsonify({'success': False, 'message': 'No voice ID provided'}), 400

    set_key('.env', 'VOICE_ID', voice_id)
    return jsonify({'success': True, 'message': f'Voice ID updated to {voice_id}'})

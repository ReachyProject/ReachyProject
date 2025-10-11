from flask import Blueprint, jsonify
from reachy import get_reachy, get_joint_by_name
from constants import REACHY_JOINTS

joints_bp = Blueprint('joints', __name__)

@joints_bp.route('/api/movement/joints', methods=['GET'])
def get_joints():
    """Return list of available joints with their current state"""
    try:
        reachy = get_reachy()
        joint_info = []
        
        if reachy:
            # Get actual joints from the robot
            try:
                for joint_name in REACHY_JOINTS:
                    joint = get_joint_by_name(reachy, joint_name)
                    if joint:
                        joint_info.append({
                            'name': joint_name,
                            'compliant': joint.compliant if hasattr(joint, 'compliant') else False
                        })
            except:
                # If we can't get state, just return names
                joint_info = [{'name': j, 'compliant': False} for j in REACHY_JOINTS]
        else:
            # Robot not connected, return default list
            joint_info = [{'name': j, 'compliant': False} for j in REACHY_JOINTS]
        
        return jsonify({'success': True, 'joints': [j['name'] for j in joint_info]})
    except Exception as e:
        return jsonify({'success': True, 'joints': REACHY_JOINTS})  # Fallback to static list
    
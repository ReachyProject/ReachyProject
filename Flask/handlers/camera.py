from flask import Blueprint, render_template


def camera_page():
    """Dedicated camera view page"""
    return render_template('camera.html')

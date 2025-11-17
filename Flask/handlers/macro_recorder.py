from flask import Blueprint, render_template

def macro_recorder():
    return render_template('macro_recorder.html')

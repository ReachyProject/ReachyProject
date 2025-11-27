import threading

from robot.bootstrap import main as robot_main
from Flask.app import run as flask_main

if __name__ == "__main__":
    flask_thread = threading.Thread(target=flask_main, daemon=True)
    flask_thread.start()

    robot_main()
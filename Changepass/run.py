"""
run.py — Entry point (Changepass)
"""

import sys
import os
import threading
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication

import core
import gui


def main():
    core._gui = None

    threading.Thread(target=core.start_asyncio_loop, daemon=True).start()

    def _wait_ready():
        while core._loop is None:
            time.sleep(0.05)
        time.sleep(0.3)
        core.bridge.log_signal.emit(
            f"[{datetime.now().strftime('%H:%M:%S')}] [WS] Server san sang: ws://127.0.0.1:8000"
        )
        if core._gui:
            core._gui.on_server_ready()

    threading.Thread(target=_wait_ready, daemon=True).start()

    app = QApplication(sys.argv)
    app.setStyleSheet(gui.STYLE)

    win = gui.MainWindow()
    core._gui = win
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

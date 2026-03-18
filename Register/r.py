"""
r.py — Entry point
"""

import sys
import threading
import time
from datetime import datetime

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
            f"[{datetime.now().strftime('%H:%M:%S')}] [WS] Server san sang"
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
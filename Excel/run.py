"""
run.py — Entry point cho Excel Export Tool (Luxshare)
"""

import sys
import threading
from datetime import datetime
from PyQt6.QtWidgets import QApplication

import core
import gui


def _wait_ready():
    """Chờ WS server sẵn sàng rồi báo GUI."""
    import time
    while not core._loop:
        time.sleep(0.05)
    time.sleep(0.3)
    core.bridge.log_signal.emit(
        f"[{datetime.now().strftime('%H:%M:%S')}] [WS] Server san sang: ws://127.0.0.1:8000"
    )
    if core._gui:
        core._gui.on_server_ready()


if __name__ == "__main__":
    # Khởi asyncio loop (WebSocket server) trên thread nền
    t = threading.Thread(target=core.start_asyncio_loop, daemon=True)
    t.start()

    # Chờ server rồi thông báo GUI
    tw = threading.Thread(target=_wait_ready, daemon=True)
    tw.start()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(gui.STYLE)

    window = gui.MainWindow()
    core._gui = window
    window.show()

    sys.exit(app.exec())
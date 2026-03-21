"""
run.py — Entry point cho Tool-RIOT (Login + Change Password + Register)
"""

import sys
import threading

from PyQt6.QtWidgets import QApplication

import gui

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Tool-RIOT")
    app.setStyleSheet(gui.STYLE)

    window = gui.MainWindow()
    gui._main_window = window
    window.show()

    # Khởi chạy asyncio loop (WebSocket server + toàn bộ automation) trong thread riêng
    t = threading.Thread(target=gui.start_asyncio_loop, daemon=True)
    t.start()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()

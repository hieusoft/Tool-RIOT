"""
gui.py — PyQt6 MainWindow và stylesheet (Login)
"""

import time
import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QListWidget, QListWidgetItem, QTextEdit,
    QHeaderView, QAbstractItemView, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QBrush

import core

# ── Stylesheet ────────────────────────────────────────────────────────────────
STYLE = """
QMainWindow, QWidget#root {
    background: #0c0f14;
}
QWidget {
    background: transparent;
    color: #eef2f6;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}
QWidget#toolbar {
    background: #0f131b;
    border-bottom: 2px solid #262d38;
}
QWidget#left_panel {
    background: #0e121a;
    border-right: 1px solid #262d38;
}
QWidget#left_header {
    background: #121a24;
    border-bottom: 2px solid #263040;
}
QListWidget {
    background: #0e121a;
    border: none;
    outline: none;
}
QListWidget::item {
    border-bottom: 1px solid #202734;
    padding: 10px 12px;
    color: #d0defa;
}
QListWidget::item:selected {
    background: #182337;
    border-left: 3px solid #2eb8c8;
    color: #ffffff;
}
QListWidget::item:hover { background: #17202d; }
QTableWidget {
    background: #0f131b;
    alternate-background-color: #111620;
    gridline-color: #1f2630;
    border: none;
    outline: none;
}
QTableWidget::item {
    padding: 6px 10px;
    color: #d0defa;
    border: none;
}
QTableWidget::item:selected { background: #1a2848; color: #ffffff; }
QHeaderView::section {
    background: #10161f;
    color: #d3e2ff;
    font-weight: bold;
    padding: 10px;
    border: none;
    border-bottom: 2px solid #263040;
    border-right: 1px solid #232b36;
}
QPushButton#btn_start {
    background: #0e4d6b;
    color: white;
    border: 1px solid #1a88b8;
    padding: 7px 20px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton#btn_start:hover    { background: #126090; }
QPushButton#btn_start:disabled { background: #1a2a3a; color: #556; }
QPushButton#btn_stop {
    background: #8b2a2a;
    color: white;
    border: 1px solid #c23b3b;
    padding: 7px 20px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton#btn_stop:hover    { background: #a33; }
QPushButton#btn_stop:disabled { background: #2a1a1a; color: #556; }
QPushButton#btn_clear {
    background: #1b2331;
    color: #8da2cc;
    border: 1px solid #2f3c51;
    padding: 4px 12px;
    font-size: 11px;
}
QPushButton#btn_clear:hover { background: #232e42; }
QPushButton#btn_export {
    background: #1a3050;
    color: #7ab0ff;
    border: 1px solid #2f5080;
    padding: 7px 16px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton#btn_export:hover { background: #1f3d66; }
QTextEdit#log_box {
    background: #090d12;
    color: #7a9cc0;
    border: none;
    font-family: "Consolas", monospace;
    font-size: 11px;
}
QScrollBar:vertical {
    background: #0b0f15;
    width: 6px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #2f405b;
    border-radius: 3px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QLabel#status_bar {
    background: #080b0f;
    color: #4a6080;
    padding: 4px 14px;
    font-size: 11px;
    border-top: 1px solid #1a2030;
}
QLabel#count_badge {
    background: #1e2a3a;
    color: #bdd2ff;
    font-size: 11px;
    font-weight: bold;
    padding: 2px 10px;
    border: 1px solid #3d506e;
}
"""

# ── Main window ────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Riot  —  Login")
        self.setMinimumSize(1100, 680)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        root_v = QVBoxLayout(root)
        root_v.setContentsMargins(0, 0, 0, 0)
        root_v.setSpacing(0)

        self._build_toolbar(root_v)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self._build_left(body)
        self._build_right(body)
        root_v.addLayout(body, 1)

        self._build_statusbar(root_v)

        core.bridge.log_signal.connect(self._on_log)
        core.bridge.refresh_signal.connect(self._on_refresh)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    # ── Toolbar ───────────────────────────────────────────────────────────────
    def _build_toolbar(self, parent_layout):
        tb = QWidget()
        tb.setObjectName("toolbar")
        tb.setFixedHeight(56)
        h = QHBoxLayout(tb)
        h.setContentsMargins(18, 0, 18, 0)
        h.setSpacing(0)

        logo_box = QWidget()
        logo_box.setFixedSize(92, 36)
        logo_box.setStyleSheet("background:#1a88b8; border:1px solid #2eb8d8;")
        logo_inner = QHBoxLayout(logo_box)
        logo_inner.setContentsMargins(0, 0, 0, 0)
        logo_lbl = QLabel("HieuSoft")
        logo_lbl.setStyleSheet("color:white; font-size:13px; font-weight:bold; background:transparent;")
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_inner.addWidget(logo_lbl)
        h.addWidget(logo_box)

        title = QLabel("  Login")
        title.setStyleSheet("color:white; font-size:15px; font-weight:bold; background:transparent;")
        h.addWidget(title)

        h.addStretch()

        self.btn_stop = QPushButton("■  STOP")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setFixedHeight(34)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(core.trigger_stop)

        self.btn_start = QPushButton("▶  BAT DAU")
        self.btn_start.setObjectName("btn_start")
        self.btn_start.setFixedHeight(34)
        self.btn_start.clicked.connect(self._on_start)

        self.btn_export = QPushButton("XUAT TXT")
        self.btn_export.setObjectName("btn_export")
        self.btn_export.setFixedHeight(34)
        self.btn_export.clicked.connect(self._export_txt)

        h.addWidget(self.btn_stop)
        h.addSpacing(8)
        h.addWidget(self.btn_export)
        h.addSpacing(8)
        h.addWidget(self.btn_start)

        parent_layout.addWidget(tb)

    # ── Left panel ────────────────────────────────────────────────────────────
    def _build_left(self, parent_layout):
        left = QWidget()
        left.setObjectName("left_panel")
        left.setFixedWidth(250)
        left_v = QVBoxLayout(left)
        left_v.setContentsMargins(0, 0, 0, 0)
        left_v.setSpacing(0)

        lhdr = QWidget()
        lhdr.setObjectName("left_header")
        lhdr.setFixedHeight(52)
        lhdr_h = QHBoxLayout(lhdr)
        lhdr_h.setContentsMargins(14, 0, 14, 0)
        sess_title = QLabel("Session ID")
        sess_title.setStyleSheet("color:white; font-size:13px; font-weight:bold; background:transparent;")
        lhdr_h.addWidget(sess_title)
        lhdr_h.addStretch()
        self.count_badge = QLabel("0 ket noi")
        self.count_badge.setObjectName("count_badge")
        lhdr_h.addWidget(self.count_badge)
        left_v.addWidget(lhdr)

        self.sess_list = QListWidget()
        self.sess_list.setAlternatingRowColors(False)
        left_v.addWidget(self.sess_list, 1)

        parent_layout.addWidget(left)

    # ── Right panel ───────────────────────────────────────────────────────────
    def _build_right(self, parent_layout):
        right_w = QWidget()
        right_v = QVBoxLayout(right_w)
        right_v.setContentsMargins(0, 0, 0, 0)
        right_v.setSpacing(0)

        # Stat cards
        cards_w = QWidget()
        cards_w.setStyleSheet("background:#0b0e14; border-bottom:1px solid #262d38;")
        cards_h = QHBoxLayout(cards_w)
        cards_h.setContentsMargins(0, 0, 0, 0)
        cards_h.setSpacing(0)
        self.stat_conn    = self._stat_card(cards_h, "KET NOI",      "0", "#4282ff", last=False)
        self.stat_running = self._stat_card(cards_h, "DANG CHAY",    "0", "#fdb45a", last=False)
        self.stat_done    = self._stat_card(cards_h, "HOAN THANH",   "0", "#4ae98c", last=False)
        self.stat_mfa     = self._stat_card(cards_h, "CAN 2FA",      "0", "#e8a030", last=False)
        self.stat_error   = self._stat_card(cards_h, "LOI",          "0", "#ff7070", last=True)
        cards_w.setFixedHeight(90)
        right_v.addWidget(cards_w)

        # Table title
        sec_title_w = QWidget()
        sec_title_w.setStyleSheet("background:#121a24; border-bottom:1px solid #263040;")
        sec_title_w.setFixedHeight(36)
        stl = QHBoxLayout(sec_title_w)
        stl.setContentsMargins(18, 0, 14, 0)
        t = QLabel("Ket qua dang nhap")
        t.setStyleSheet("color:#8da2cc; font-size:12px; background:transparent;")
        stl.addWidget(t)
        right_v.addWidget(sec_title_w)

        # Account table — 6 cot
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Username", "Password", "Session ID", "Status", "Ghi chu", "Cookie"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 150)
        self.table.setColumnWidth(3, 110)
        self.table.setColumnWidth(4, 100)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        right_v.addWidget(self.table, 1)

        # Log strip
        log_hdr = QWidget()
        log_hdr.setStyleSheet("background:#0f131b; border-top:1px solid #1a2030; border-bottom:1px solid #1a2030;")
        log_hdr.setFixedHeight(32)
        lh = QHBoxLayout(log_hdr)
        lh.setContentsMargins(14, 0, 14, 0)
        log_title = QLabel("LOG")
        log_title.setStyleSheet("color:#5a7090; font-size:10px; font-weight:bold; background:transparent;")
        lh.addWidget(log_title)
        lh.addStretch()
        clear_btn = QPushButton("Xoa")
        clear_btn.setObjectName("btn_clear")
        clear_btn.setFixedHeight(22)
        clear_btn.clicked.connect(self._clear_log)
        lh.addWidget(clear_btn)
        right_v.addWidget(log_hdr)

        self.log_box = QTextEdit()
        self.log_box.setObjectName("log_box")
        self.log_box.setReadOnly(True)
        self.log_box.setFixedHeight(110)
        right_v.addWidget(self.log_box)

        parent_layout.addWidget(right_w, 1)

    def _stat_card(self, parent_layout, label, value, color, last=False):
        card = QWidget()
        card.setObjectName("stat_card")
        border = "border-right:1px solid #262d38;" if not last else ""
        card.setStyleSheet(f"QWidget#stat_card {{ background:#0f131b; {border} }}")
        v = QVBoxLayout(card)
        v.setContentsMargins(20, 14, 20, 14)
        lbl = QLabel(label)
        lbl.setStyleSheet("color:#7a9abf; font-size:10px; font-weight:bold; background:transparent;")
        v.addWidget(lbl)
        num = QLabel(value)
        num.setStyleSheet(f"color:{color}; font-size:26px; font-weight:bold; background:transparent;")
        v.addWidget(num)
        parent_layout.addWidget(card)
        return num

    def _build_statusbar(self, parent_layout):
        self.status_bar = QLabel("San sang")
        self.status_bar.setObjectName("status_bar")
        self.status_bar.setFixedHeight(26)
        parent_layout.addWidget(self.status_bar)

    # ── Slots ─────────────────────────────────────────────────────────────────
    def _on_start(self):
        if core._running:
            return
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.status_bar.setText("Dang dang nhap...")
        core.trigger_run()

    def _on_log(self, msg):
        self.log_box.append(msg)

    def _on_refresh(self):
        self._refresh_sessions()
        self._refresh_table()
        self._refresh_stats()
        if not core._running:
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.status_bar.setText("San sang")

    def _clear_log(self):
        self.log_box.clear()

    def _export_txt(self):
        if not core.acct_log:
            QMessageBox.information(self, "Thong bao", "Chua co du lieu de xuat!")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Luu file", "login_results.txt", "Text Files (*.txt)"
        )
        if not path:
            return
        lines = []
        for e in core.acct_log:
            status  = e.get("status", "?")
            note    = e.get("note", "")
            cookies = e.get("cookies", "")
            lines.append(f"{e['username']}|{e['password']}|{status}|{note}|{cookies}")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        QMessageBox.information(self, "Thanh cong", f"Da xuat {len(lines)} dong ra:\n{path}")

    def _tick(self):
        self._refresh_sessions()

    def _refresh_sessions(self):
        self.sess_list.clear()
        for sid, info in core.sessions.items():
            elapsed = int(time.time() - info.get("connected_at", time.time()))
            m, s    = divmod(elapsed, 60)
            short   = str(sid)[:22] + "..."
            status  = info.get("status", "-")
            item    = QListWidgetItem(f"{short}\n{status}  —  {m:02d}:{s:02d}")
            self.sess_list.addItem(item)
        self.count_badge.setText(f"{len(core.sessions)} ket noi")

    def _refresh_table(self):
        self.table.setRowCount(len(core.acct_log))
        STATUS_COLORS = {
            "Hoan thanh":   ("#112a1c", "#4ae98c"),
            "Co cookie":    ("#0a2010", "#30ff80"),
            "Khong co cookie": ("#1a2a1a", "#80c080"),
            "Lay cookie...": ("#0e1a2a", "#7ab0ff"),
            "Loi":          ("#2a1111", "#ff7070"),
            "Da dung":      ("#1a1a1a", "#888888"),
            "Dang chay":    ("#0e1a2a", "#7ab0ff"),
            "Can 2FA":      ("#2a1e0a", "#e8a030"),
            "Can kiem tra": ("#1a1a2a", "#a090d0"),
        }
        for row, e in enumerate(core.acct_log):
            status = e.get("status", "Cho...")
            bg_hex, fg_hex = STATUS_COLORS.get(status, ("#0f131b", "#8da0c0"))
            bg = QColor(bg_hex)
            fg = QColor(fg_hex)

            def cell(text, align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter):
                it = QTableWidgetItem(str(text))
                it.setBackground(QBrush(bg))
                it.setForeground(QBrush(fg))
                it.setTextAlignment(align)
                return it

            center = Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            self.table.setItem(row, 0, cell(e.get("username", "")))
            self.table.setItem(row, 1, cell(e.get("password", "")))
            self.table.setItem(row, 2, cell(str(e["session_id"])[:22] + "..."))
            self.table.setItem(row, 3, cell(status, center))
            self.table.setItem(row, 4, cell(e.get("note", ""), center))
            # Cookie: hien thi 60 ky tu dau
            raw_cookie = e.get("cookies", "")
            short_cookie = (raw_cookie[:60] + "...") if len(raw_cookie) > 60 else raw_cookie
            self.table.setItem(row, 5, cell(short_cookie))

    def _refresh_stats(self):
        self.stat_conn.setText(str(len(core.sessions)))
        self.stat_running.setText(str(sum(1 for e in core.acct_log if "chay" in e.get("status", "").lower())))
        self.stat_done.setText(str(sum(1 for e in core.acct_log if "Hoan" in e.get("status", ""))))
        self.stat_mfa.setText(str(sum(1 for e in core.acct_log if "2FA" in e.get("status", ""))))
        self.stat_error.setText(str(sum(1 for e in core.acct_log if "Loi" in e.get("status", ""))))

    def on_server_ready(self):
        self.status_bar.setText("Server san sang: ws://127.0.0.1:8000  ✓")

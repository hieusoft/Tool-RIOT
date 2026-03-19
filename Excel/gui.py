"""
gui.py — PyQt6 MainWindow (Excel Import Tool — Luxshare CCCD)
Import file Excel → hien thi vao bang → bam BAT DAU de tu dong xu ly.
"""

import time
import os
from datetime import datetime
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QListWidget, QListWidgetItem, QTextEdit,
    QHeaderView, QAbstractItemView, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QBrush

import core

STYLE = """
QMainWindow, QWidget#root { background: #0c0f14; }
QWidget {
    background: transparent;
    color: #eef2f6;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}
QWidget#toolbar { background: #0f131b; border-bottom: 2px solid #262d38; }
QWidget#left_panel { background: #0e121a; border-right: 1px solid #262d38; }
QWidget#left_header { background: #121a24; border-bottom: 2px solid #263040; }
QListWidget { background: #0e121a; border: none; outline: none; }
QListWidget::item { border-bottom: 1px solid #202734; padding: 10px 12px; color: #d0defa; }
QListWidget::item:selected { background: #182337; border-left: 3px solid #1e8a3c; color: #fff; }
QListWidget::item:hover { background: #17202d; }
QTableWidget {
    background: #0f131b;
    alternate-background-color: #111620;
    gridline-color: #1f2630;
    border: none; outline: none;
}
QTableWidget::item { padding: 6px 10px; color: #d0defa; border: none; }
QTableWidget::item:selected { background: #1a2848; color: #fff; }
QHeaderView::section {
    background: #10161f; color: #d3e2ff; font-weight: bold;
    padding: 8px; border: none;
    border-bottom: 2px solid #263040; border-right: 1px solid #232b36;
}
QPushButton#btn_start {
    background: #0e6b2a; color: white; border: 1px solid #1ab84a;
    padding: 7px 20px; font-weight: bold; font-size: 13px;
}
QPushButton#btn_start:hover    { background: #129038; }
QPushButton#btn_start:disabled { background: #1a2a1a; color: #556; }
QPushButton#btn_stop {
    background: #8b2a2a; color: white; border: 1px solid #c23b3b;
    padding: 7px 20px; font-weight: bold; font-size: 13px;
}
QPushButton#btn_stop:hover    { background: #a33; }
QPushButton#btn_stop:disabled { background: #2a1a1a; color: #556; }
QPushButton#btn_import {
    background: #1a3050; color: #7ab0ff; border: 1px solid #2f5080;
    padding: 7px 16px; font-weight: bold; font-size: 13px;
}
QPushButton#btn_import:hover { background: #1f3d66; }
QPushButton#btn_clear {
    background: #1b2331; color: #8da2cc; border: 1px solid #2f3c51;
    padding: 4px 12px; font-size: 11px;
}
QPushButton#btn_clear:hover { background: #232e42; }
QTextEdit#log_box {
    background: #090d12; color: #7a9cc0; border: none;
    font-family: "Consolas", monospace; font-size: 11px;
}
QScrollBar:vertical { background: #0b0f15; width: 6px; border: none; }
QScrollBar::handle:vertical { background: #2f405b; border-radius: 3px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QLabel#status_bar {
    background: #080b0f; color: #4a6080; padding: 4px 14px;
    font-size: 11px; border-top: 1px solid #1a2030;
}
QLabel#count_badge {
    background: #1e2a3a; color: #bdd2ff; font-size: 11px;
    font-weight: bold; padding: 2px 10px; border: 1px solid #3d506e;
}
QLabel#import_badge {
    background: #0e3020; color: #50e080; font-size: 11px;
    font-weight: bold; padding: 2px 10px; border: 1px solid #20603a;
}
"""

# Columns: (header, key in acct_log/imported_data, width_mode)
TABLE_COLS = [
    ("#",          None,          "fixed",   40),
    ("Ho ten",     "full_name",   "stretch", 0),
    ("CCCD",       "cccd",        "fixed",   130),
    ("Gioi tinh",  "gender",      "fixed",   76),
    ("Ngay sinh",  "birthday",    "fixed",   90),
    ("Dia chi",    "address",     "stretch", 0),
    ("Ngay cap",   "issue_date",  "fixed",   90),
    ("Han",        "expiry_date", "fixed",   90),
    ("Status",     "status",      "fixed",   100),
]

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HieuSoft  —  Excel Import (Luxshare CCCD)")
        self.setMinimumSize(1180, 700)

        root = QWidget(); root.setObjectName("root")
        self.setCentralWidget(root)
        rv = QVBoxLayout(root); rv.setContentsMargins(0,0,0,0); rv.setSpacing(0)

        self._build_toolbar(rv)

        body = QHBoxLayout(); body.setContentsMargins(0,0,0,0); body.setSpacing(0)
        self._build_left(body)
        self._build_right(body)
        rv.addLayout(body, 1)

        self._build_statusbar(rv)

        core.bridge.log_signal.connect(self._on_log)
        core.bridge.refresh_signal.connect(self._on_refresh)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_sessions)
        self._timer.start(1000)

    # ── Toolbar ───────────────────────────────────────────────────────────────
    def _build_toolbar(self, parent):
        tb = QWidget(); tb.setObjectName("toolbar"); tb.setFixedHeight(56)
        h = QHBoxLayout(tb); h.setContentsMargins(18,0,18,0); h.setSpacing(0)

        logo = QWidget(); logo.setFixedSize(92, 36)
        logo.setStyleSheet("background:#1e8a3c; border:1px solid #2eb85c;")
        li = QHBoxLayout(logo); li.setContentsMargins(0,0,0,0)
        ll = QLabel("HieuSoft"); ll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ll.setStyleSheet("color:white; font-size:13px; font-weight:bold; background:transparent;")
        li.addWidget(ll); h.addWidget(logo)

        h.addWidget(self._lbl("  Excel Import CCCD", "color:white; font-size:15px; font-weight:bold;"))
        h.addStretch()

        self.import_badge = QLabel("0 dong")
        self.import_badge.setObjectName("import_badge")
        h.addWidget(self.import_badge)
        h.addSpacing(12)

        self.btn_stop = QPushButton("■  STOP")
        self.btn_stop.setObjectName("btn_stop"); self.btn_stop.setFixedHeight(34)
        self.btn_stop.setEnabled(False); self.btn_stop.clicked.connect(core.trigger_stop)

        self.btn_import = QPushButton("📂  IMPORT EXCEL")
        self.btn_import.setObjectName("btn_import"); self.btn_import.setFixedHeight(34)
        self.btn_import.clicked.connect(self._import_excel)

        self.btn_start = QPushButton("▶  BAT DAU")
        self.btn_start.setObjectName("btn_start"); self.btn_start.setFixedHeight(34)
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self._on_start)

        for w in [self.btn_stop, self.btn_import, self.btn_start]:
            h.addSpacing(8); h.addWidget(w)

        parent.addWidget(tb)

    # ── Left panel ────────────────────────────────────────────────────────────
    def _build_left(self, parent):
        left = QWidget(); left.setObjectName("left_panel"); left.setFixedWidth(230)
        lv = QVBoxLayout(left); lv.setContentsMargins(0,0,0,0); lv.setSpacing(0)

        lhdr = QWidget(); lhdr.setObjectName("left_header"); lhdr.setFixedHeight(52)
        lh = QHBoxLayout(lhdr); lh.setContentsMargins(14,0,14,0)
        lh.addWidget(self._lbl("Session ID", "color:white; font-size:13px; font-weight:bold;"))
        lh.addStretch()
        self.count_badge = QLabel("0 ket noi"); self.count_badge.setObjectName("count_badge")
        lh.addWidget(self.count_badge)
        lv.addWidget(lhdr)

        self.sess_list = QListWidget()
        lv.addWidget(self.sess_list, 1)
        parent.addWidget(left)

    # ── Right panel ───────────────────────────────────────────────────────────
    def _build_right(self, parent):
        rw = QWidget(); rv = QVBoxLayout(rw); rv.setContentsMargins(0,0,0,0); rv.setSpacing(0)

        # Stat cards
        cw = QWidget()
        cw.setStyleSheet("background:#0b0e14; border-bottom:1px solid #262d38;")
        ch = QHBoxLayout(cw); ch.setContentsMargins(0,0,0,0); ch.setSpacing(0)
        self.stat_conn    = self._stat_card(ch, "KET NOI",      "0", "#4282ff", False)
        self.stat_import  = self._stat_card(ch, "DA IMPORT",    "0", "#7ab0ff", False)
        self.stat_running = self._stat_card(ch, "DANG CHAY",    "0", "#fdb45a", False)
        self.stat_done    = self._stat_card(ch, "HOAN THANH",   "0", "#4ae98c", False)
        self.stat_error   = self._stat_card(ch, "LOI",          "0", "#ff7070", True)
        cw.setFixedHeight(90); rv.addWidget(cw)

        # Section title
        sw = QWidget()
        sw.setStyleSheet("background:#121a24; border-bottom:1px solid #263040;")
        sw.setFixedHeight(36); sl = QHBoxLayout(sw); sl.setContentsMargins(18,0,14,0)
        sl.addWidget(self._lbl("Du lieu CCCD (tu file Excel)", "color:#8da2cc; font-size:12px;"))
        rv.addWidget(sw)

        # Table
        n_cols = len(TABLE_COLS)
        self.table = QTableWidget(0, n_cols)
        self.table.setHorizontalHeaderLabels([c[0] for c in TABLE_COLS])
        hdr = self.table.horizontalHeader()
        for i, (_, _, mode, w) in enumerate(TABLE_COLS):
            if mode == "stretch":
                hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                self.table.setColumnWidth(i, w)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        rv.addWidget(self.table, 1)

        # Log strip
        lhdr = QWidget()
        lhdr.setStyleSheet("background:#0f131b; border-top:1px solid #1a2030; border-bottom:1px solid #1a2030;")
        lhdr.setFixedHeight(32); lh = QHBoxLayout(lhdr); lh.setContentsMargins(14,0,14,0)
        lh.addWidget(self._lbl("LOG", "color:#5a7090; font-size:10px; font-weight:bold;"))
        lh.addStretch()
        clr = QPushButton("Xoa"); clr.setObjectName("btn_clear")
        clr.setFixedHeight(22); clr.clicked.connect(lambda: self.log_box.clear())
        lh.addWidget(clr); rv.addWidget(lhdr)

        self.log_box = QTextEdit(); self.log_box.setObjectName("log_box")
        self.log_box.setReadOnly(True); self.log_box.setFixedHeight(110)
        rv.addWidget(self.log_box)

        parent.addWidget(rw, 1)

    def _stat_card(self, parent, label, val, color, last):
        card = QWidget(); card.setObjectName("stat_card")
        br = "" if last else "border-right:1px solid #262d38;"
        card.setStyleSheet(f"QWidget#stat_card {{ background:#0f131b; {br} }}")
        v = QVBoxLayout(card); v.setContentsMargins(20,14,20,14)
        v.addWidget(self._lbl(label, "color:#7a9abf; font-size:10px; font-weight:bold;"))
        num = QLabel(val)
        num.setStyleSheet(f"color:{color}; font-size:26px; font-weight:bold; background:transparent;")
        v.addWidget(num); parent.addWidget(card)
        return num

    def _lbl(self, text, style=""):
        l = QLabel(text)
        l.setStyleSheet((style + "; background:transparent;").lstrip("; "))
        return l

    def _build_statusbar(self, parent):
        self.status_bar = QLabel("San sang — Bam 'Import Excel' de tai du lieu")
        self.status_bar.setObjectName("status_bar"); self.status_bar.setFixedHeight(26)
        parent.addWidget(self.status_bar)

    # ── Slots ─────────────────────────────────────────────────────────────────
    def _import_excel(self):
        """Mo dialog chon file Excel, doc vao imported_data, hien thi bang."""
        default_dir = os.path.dirname(os.path.abspath(core.ACCOUNT_FILE))
        path, _ = QFileDialog.getOpenFileName(
            self, "Chon file Excel CCCD", default_dir, "Excel Files (*.xlsx *.xls)"
        )
        if not path:
            return
        count = core.load_excel_file(path)
        if count == 0:
            QMessageBox.warning(self, "Loi", "Khong doc duoc du lieu tu file Excel!\n"
                                "Kiem tra lai header: Ho ten | CCCD | Gioi tinh | Ngay sinh | Dia chi | Ngay cap | Han")
            return
        self.import_badge.setText(f"{count} dong")
        self.stat_import.setText(str(count))
        self.btn_start.setEnabled(True)
        self.status_bar.setText(f"Da import {count} dong tu: {os.path.basename(path)}")
        self._refresh_import_table()
        QMessageBox.information(self, "Thanh cong", f"Da import {count} dong tu file Excel.")

    def _refresh_import_table(self):
        """Hien thi imported_data len bang (khi chua chay, dung acct_log se trong)."""
        data = core.acct_log if core.acct_log else core.imported_data
        STATUS_COLORS = {
            "Hoan thanh": ("#112a1c", "#4ae98c"),
            "Loi":        ("#2a1111", "#ff7070"),
            "Dang chay":  ("#0e1a2a", "#7ab0ff"),
            "Cho...":     ("#1a1a1a", "#888"),
        }
        self.table.setRowCount(len(data))
        for row, e in enumerate(data):
            status  = e.get("status", "")
            bg_hex, fg_hex = STATUS_COLORS.get(status, ("#0f131b", "#8da0c0"))
            bg, fg = QColor(bg_hex), QColor(fg_hex)

            def cell(text, align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter):
                it = QTableWidgetItem(str(text))
                it.setBackground(QBrush(bg)); it.setForeground(QBrush(fg))
                it.setTextAlignment(align); return it

            ctr = Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            for col, (_, key, _, _) in enumerate(TABLE_COLS):
                if key is None:
                    self.table.setItem(row, col, cell(row + 1, ctr))
                elif key == "status":
                    self.table.setItem(row, col, cell(e.get(key, ""), ctr))
                elif key in ("birthday", "issue_date", "expiry_date", "gender", "cccd"):
                    self.table.setItem(row, col, cell(e.get(key, ""), ctr))
                else:
                    self.table.setItem(row, col, cell(e.get(key, "")))

    def _on_start(self):
        if core._running: return
        self.btn_start.setEnabled(False); self.btn_stop.setEnabled(True)
        self.status_bar.setText("Dang chay...")
        core.acct_log.clear()
        core.trigger_run()

    def _on_log(self, msg):
        self.log_box.append(msg)

    def _on_refresh(self):
        self._refresh_sessions()
        self._refresh_import_table()
        self._refresh_stats()
        if not core._running:
            self.btn_start.setEnabled(bool(core.imported_data))
            self.btn_stop.setEnabled(False)
            self.status_bar.setText("San sang")

    def _refresh_sessions(self):
        self.sess_list.clear()
        for sid, info in core.sessions.items():
            elapsed = int(time.time() - info.get("connected_at", time.time()))
            m, s = divmod(elapsed, 60)
            item = QListWidgetItem(f"{str(sid)[:22]}...\n{info.get('status','-')}  —  {m:02d}:{s:02d}")
            self.sess_list.addItem(item)
        self.count_badge.setText(f"{len(core.sessions)} ket noi")

    def _refresh_stats(self):
        self.stat_conn.setText(str(len(core.sessions)))
        self.stat_import.setText(str(len(core.imported_data)))
        self.stat_running.setText(str(sum(1 for e in core.acct_log if "chay" in e.get("status","").lower())))
        self.stat_done.setText(str(sum(1 for e in core.acct_log if "Hoan" in e.get("status",""))))
        self.stat_error.setText(str(sum(1 for e in core.acct_log if "Loi" in e.get("status",""))))

    def on_server_ready(self):
        self.status_bar.setText("Server san sang: ws://127.0.0.1:8000  ✓  —  Bam 'Import Excel' de tai du lieu")

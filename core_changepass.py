"""
core_changepass.py — Business logic cho chức năng Đổi mật khẩu (không có WS server)
WS server được quản lý tập trung bởi gui.py
"""

import asyncio
import json
import random
import time
import sys
import os
from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ── Shared state ──────────────────────────────────────────────────────────────
sessions   = {}   # {sessionId: {ws, pending, status, connected_at}}
acct_log   = []   # [{session_id, username, old_password, new_password, status}]

_req_id    = 0
_loop      = None
_running   = False
_stop_flag = False

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
ACCOUNT_FILE = os.path.join(BASE_DIR, "account_changepass.txt")

# ── Signal bridge (asyncio → Qt) ──────────────────────────────────────────────
class Bridge(QObject):
    log_signal     = pyqtSignal(str)
    refresh_signal = pyqtSignal()

bridge = Bridge()

# ── Helpers ───────────────────────────────────────────────────────────────────
def next_id():
    global _req_id
    _req_id += 1
    return str(_req_id)

def log(msg, _tag="info"):
    now  = datetime.now().strftime("%H:%M:%S")
    line = f"[{now}] {msg}"
    print(line)
    bridge.log_signal.emit(line)

async def human_delay(a=0.4, b=1.2):
    await asyncio.sleep(random.uniform(a, b))

# ── WebSocket communication ───────────────────────────────────────────────────
async def send_and_wait(session_id, action, data, timeout=30):
    s = sessions.get(session_id)
    if not s:
        return None
    req_id = next_id()
    fut    = asyncio.get_event_loop().create_future()
    s["pending"][req_id] = fut
    await s["ws"].send(json.dumps({"requestId": req_id, "action": action, "data": data}))
    log(f"[{str(session_id)[:8]}] >> {action}")
    try:
        return await asyncio.wait_for(asyncio.shield(fut), timeout=timeout)
    except asyncio.TimeoutError:
        log(f"[{str(session_id)[:8]}] !! Timeout: {action}")
        return None
    finally:
        s["pending"].pop(req_id, None)

async def wait_for_selector(session_id, sel, tab_id=None, max_wait=20, interval=0.5):
    data = {"selector": sel}
    if tab_id:
        data["tabId"] = tab_id
    elapsed = 0
    while elapsed < max_wait:
        if _stop_flag:
            return False
        res = await send_and_wait(session_id, "check_element", data, timeout=6)
        if res and (res.get("result") or {}).get("found"):
            return True
        await asyncio.sleep(interval)
        elapsed += interval
    log(f"[{str(session_id)[:8]}] !! Not found: {sel}")
    return False

def set_status(session_id, status):
    if session_id in sessions:
        sessions[session_id]["status"] = status
    for e in reversed(acct_log):
        if e["session_id"] == session_id:
            e["status"] = status
            break
    bridge.refresh_signal.emit()

# ── Load accounts ─────────────────────────────────────────────────────────────
def load_accounts():
    """
    Đọc file account_changepass.txt, mỗi dòng: username|old_password|new_password
    """
    accounts = []
    if not os.path.exists(ACCOUNT_FILE):
        log(f"!! Khong tim thay file: {ACCOUNT_FILE}")
        return accounts
    with open(ACCOUNT_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) >= 3:
                accounts.append({
                    "username":     parts[0].strip(),
                    "old_password": parts[1].strip(),
                    "new_password": parts[2].strip(),
                })
            elif len(parts) == 2:
                log(f"!! Dong thieu mat khau moi: {line} — bo qua")
    log(f">> Doc duoc {len(accounts)} tai khoan tu account_changepass.txt")
    return accounts

# ── Automation ────────────────────────────────────────────────────────────────
CHANGE_PASS_URL = "https://account.riotgames.com"

async def run_changepass(session_id, username, old_password, new_password):
    sid = str(session_id)[:8]
    log(f"[{sid}] Bat dau doi mat khau: {username}")
    set_status(session_id, "Dang chay")

    sw  = lambda a, d, **kw: send_and_wait(session_id, a, d, **kw)
    wfs = lambda s, t=None, **kw: wait_for_selector(session_id, s, t, **kw)

    try:
        # ── 1. Mo trang login Riot ──
        res    = await sw("open_url", {"url": "https://auth.riotgames.com/login#access_token", "newTab": True})
        tab_id = (res or {}).get("result", {}).get("tabId")

        def tab(x={}):
            d = dict(x)
            if tab_id:
                d["tabId"] = tab_id
            return d

        # ── 2. Nhap username ──
        if await wfs('[data-testid="username"]', tab_id, max_wait=25):
            await human_delay(0.5, 1.0)
            await sw("type_text", tab({"selector": '[data-testid="username"]', "value": username}))
        else:
            log(f"[{sid}] !! Khong thay o username")
            set_status(session_id, "Loi")
            return

        await human_delay(0.5, 1.0)

        # ── 3. Nhap password ──
        if await wfs('[data-testid="password"]', tab_id, max_wait=10):
            await human_delay(0.3, 0.7)
            await sw("type_text", tab({"selector": '[data-testid="password"]', "value": old_password}))

        await human_delay(0.6, 1.2)

        # ── 4. Bam Login ──
        await sw("click", tab({"selector": '[data-testid="btn-signin-submit"]'}))
        log(f"[{sid}] Da bam Login, cho trang tai...")

        await asyncio.sleep(4)

        # Chuyen den trang Security
        await sw("open_url", tab({"url": CHANGE_PASS_URL}))
        log(f"[{sid}] Mo trang Security...")

        # ── 6. Cho nut "Change Password" hien ra ──
        change_btn_sel = 'button[data-testid="btn-change-password"], button.password-change-btn, [aria-label*="Change password"], [data-testid="change-password-button"]'
        found_change = await wfs(change_btn_sel, tab_id, max_wait=20)

        if not found_change:
            found_change = await wfs('button', tab_id, max_wait=5)

        if found_change:
            await human_delay(0.5, 1.0)
            for sel in [
                '[data-testid="change-password-button"]',
                '[data-testid="btn-change-password"]',
                'button[class*="password"]',
            ]:
                res2 = await send_and_wait(session_id, "check_element", tab({"selector": sel}), timeout=4)
                if (res2 or {}).get("result", {}).get("found"):
                    await sw("click", tab({"selector": sel}))
                    break

        # ── 7. Dien Current Password ──
        cur_pass_sel_list = [
            '[data-testid="current-password"]',
            'input[name="currentPassword"]',
            'input[placeholder*="current"]',
            'input[autocomplete="current-password"]',
        ]
        found_cur = False
        for sel in cur_pass_sel_list:
            if await wfs(sel, tab_id, max_wait=8):
                await human_delay(0.3, 0.7)
                await sw("type_text", tab({"selector": sel, "value": old_password}))
                found_cur = True
                break

        if not found_cur:
            log(f"[{sid}] !! Khong thay truong 'Current Password'")
            set_status(session_id, "Loi")
            return

        # ── 8. Dien New Password ──
        new_pass_sel_list = [
            '[data-testid="new-password"]',
            'input[name="newPassword"]',
            'input[placeholder*="new"]',
            'input[autocomplete="new-password"]',
        ]
        found_new = False
        for sel in new_pass_sel_list:
            if await wfs(sel, tab_id, max_wait=8):
                await human_delay(0.3, 0.6)
                await sw("type_text", tab({"selector": sel, "value": new_password}))
                found_new = True
                break

        if not found_new:
            log(f"[{sid}] !! Khong thay truong 'New Password'")
            set_status(session_id, "Loi")
            return

        # ── 9. Confirm New Password ──
        confirm_sel_list = [
            '[data-testid="confirm-password"]',
            'input[name="confirmPassword"]',
            'input[placeholder*="confirm"]',
        ]
        for sel in confirm_sel_list:
            if await wfs(sel, tab_id, max_wait=8):
                await human_delay(0.3, 0.6)
                await sw("type_text", tab({"selector": sel, "value": new_password}))
                break

        await human_delay(0.7, 1.4)

        # ── 10. Bam Save / Submit ──
        submit_sel_list = [
            '[data-testid="btn-save-password"]',
            '[data-testid="submit-button"]',
            'button[type="submit"]',
        ]
        for sel in submit_sel_list:
            res3 = await send_and_wait(session_id, "check_element", tab({"selector": sel}), timeout=4)
            if (res3 or {}).get("result", {}).get("found"):
                await human_delay(0.4, 0.8)
                await sw("click", tab({"selector": sel}))
                break

        await asyncio.sleep(3)
        log(f"[{sid}] Doi mat khau hoan tat: {username}")

        for e in reversed(acct_log):
            if e["session_id"] == session_id:
                e["new_password"] = new_password
                break
        set_status(session_id, "Hoan thanh")

    except Exception as e:
        set_status(session_id, "Loi")
        log(f"[{sid}] Error: {e}")


async def run_all_sessions():
    global _running, _stop_flag
    _stop_flag = False

    accounts = load_accounts()
    if not accounts:
        log("!! Khong co tai khoan nao trong account_changepass.txt (dinh dang: username|old_pass|new_pass)")
        _running = False
        bridge.refresh_signal.emit()
        return

    session_ids = list(sessions.keys())
    if not session_ids:
        log("!! Chua co session nao ket noi!")
        _running = False
        bridge.refresh_signal.emit()
        return

    log(f">> Bat dau {len(session_ids)} session(s) voi {len(accounts)} tai khoan...")

    tasks = []
    for i, (sid, acct) in enumerate(zip(session_ids, accounts)):
        entry = {
            "session_id":   sid,
            "username":     acct["username"],
            "old_password": acct["old_password"],
            "new_password": acct["new_password"],
            "status":       "Cho...",
        }
        acct_log.append(entry)
        log(f"  >> [{str(sid)[:8]}] {acct['username']}")
        tasks.append(asyncio.create_task(
            run_changepass(sid, acct["username"], acct["old_password"], acct["new_password"])
        ))

    bridge.refresh_signal.emit()
    await asyncio.gather(*tasks, return_exceptions=True)
    log(">> Tat ca sessions hoan thanh!")
    _running = False
    bridge.refresh_signal.emit()

# ── Public triggers (called from GUI) ─────────────────────────────────────────
def trigger_run(loop):
    global _running
    if _running:
        return
    _running = True
    asyncio.run_coroutine_threadsafe(run_all_sessions(), loop)

def trigger_stop():
    global _stop_flag, _running
    _stop_flag = True
    _running   = False
    log("!! Dung — cac session se ket thuc sau buoc hien tai")
    bridge.refresh_signal.emit()

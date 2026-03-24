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
    Đọc file account_changepass.txt
    Format 2 trường: username|new_password (old_password = empty)
    Format 3 trường: username|old_password|new_password
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
                # Format: username|new_password (login bằng new_password)
                accounts.append({
                    "username":     parts[0].strip(),
                    "old_password": parts[1].strip(),  # dùng chính password này để login
                    "new_password": parts[1].strip(),  # và đổi thành password mới
                })
            else:
                log(f"!! Dong sai dinh dang: {line} — bo qua")
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
        res    = await sw("open_url", {"url": "https://account.riotgames.com", "newTab": True})
        tab_id = (res or {}).get("result", {}).get("tabId")

        def tab(x={}):
            d = dict(x)
            if tab_id:
                d["tabId"] = tab_id
            return d

        # ── 2. Nhap username ──
        if await wfs('[data-testid="input-username"]', tab_id, max_wait=25):
            await human_delay(0.5, 1.0)
            await sw("type_text", tab({"selector": '[data-testid="input-username"]', "value": username}))
        else:
            log(f"[{sid}] !! Khong thay o username")
            set_status(session_id, "Loi")
            return

        await human_delay(0.5, 1.0)

        # ── 3. Nhap password ──
        if await wfs('[data-testid="input-password"]', tab_id, max_wait=10):
            await human_delay(0.3, 0.7)
            await sw("type_text", tab({"selector": '[data-testid="input-password"]', "value": old_password}))

        await human_delay(0.6, 1.2)

        # ── 4. Bam Login ──
        await sw("click", tab({"selector": '[data-testid="btn-signin-submit"]'}))
        log(f"[{sid}] Da bam Login, cho trang tai...")
        log(f"[{sid}] Kiem tra hCaptcha...")
        captcha_elapsed = 0
        while captcha_elapsed < 60:
            res_cap = await send_and_wait(session_id, "check_element",
                                          tab({"selector": 'iframe[src*="hcaptcha.com"][src*="frame=checkbox"]:not([src*="invisible"])'}), timeout=5)
            found_cap = (res_cap or {}).get("result", {})
            if isinstance(found_cap, dict):
                found_cap = found_cap.get("found", False)
            else:
                found_cap = bool(found_cap)
            if not found_cap:
                break
            log(f"[{sid}] hCaptcha visible dang hien — cho 5s...")
            await asyncio.sleep(5)
            captcha_elapsed += 5
        if captcha_elapsed >= 60:
            log(f"[{sid}] Captcha timeout 60s, tiep tuc...")
        else:
            log(f"[{sid}] Khong co captcha visible, tiep tuc...")
        # ── 4b. Kiem tra error message sau submit ──
        await asyncio.sleep(2)
        err_res = await send_and_wait(session_id, "check_element",
                                      tab({"selector": '[data-testid="error-message"]'}), timeout=5)
        if (err_res or {}).get("result", {}).get("found"):
            log(f"[{sid}] !! Login that bai — sai username/password hoac tai khoan bi khoa")
            set_status(session_id, "Login loi")
            return

        # Chờ trang account load sau khi login (tự redirect về account.riotgames.com)
        await asyncio.sleep(6)
        log(f"[{sid}] Mo trang Security...")

        # ── 6. Scroll đến form đổi mật khẩu và điền ──
        cur_pass_sel = '[data-testid="password-card__currentPassword"]'
        if not await wfs(cur_pass_sel, tab_id, max_wait=20):
            log(f"[{sid}] !! Khong thay truong 'Current Password'")
            set_status(session_id, "Loi")
            return

        # Scroll đến element trước khi nhập
        await send_and_wait(session_id, "execute_script",
                            tab({"script": f"document.querySelector('{cur_pass_sel}')?.scrollIntoView({{behavior:'smooth',block:'center'}})"}),
                            timeout=5)
        await human_delay(0.5, 1.0)

        # ── 7. Dien Current Password ──
        await sw("type_text", tab({"selector": cur_pass_sel, "value": old_password}))

        # ── 8. Dien New Password ──
        new_pass_sel = '[data-testid="password-card__newPassword"]'
        if await wfs(new_pass_sel, tab_id, max_wait=8):
            await human_delay(0.3, 0.6)
            await sw("type_text", tab({"selector": new_pass_sel, "value": new_password}))
        else:
            log(f"[{sid}] !! Khong thay truong 'New Password'")
            set_status(session_id, "Loi")
            return

        # ── 9. Confirm New Password ──
        confirm_sel = '[data-testid="password-card__confirmNewPassword"]'
        if await wfs(confirm_sel, tab_id, max_wait=8):
            await human_delay(0.3, 0.6)
            await sw("type_text", tab({"selector": confirm_sel, "value": new_password}))


        await human_delay(0.7, 1.4)

        # ── 10. Bam Save / Submit ──
        submit_sel         = '[data-testid="password-card__submit-btn"]'
        submit_enabled_sel = '[data-testid="password-card__submit-btn"]:not([disabled])'
        log(f"[{sid}] Cho nut Save duoc active...")
        # Chờ button bỏ disabled (tối đa 8s)
        if await wfs(submit_enabled_sel, tab_id, max_wait=8):
            await human_delay(0.4, 0.8)
            await sw("click", tab({"selector": submit_sel}))
            log(f"[{sid}] Da bam Save Changes!")
        else:
            log(f"[{sid}] !! Nut Save van disabled — co the mat khau khong hop le")
            set_status(session_id, "Loi")
            return


        await asyncio.sleep(3)
        log(f"[{sid}] Doi mat khau hoan tat: {username}")

        for e in reversed(acct_log):
            if e["session_id"] == session_id:
                e["new_password"] = new_password
                break
        set_status(session_id, "Hoan thanh")

        # ── Logout + dọn dẹp tab ──
        LOGOUT_URL = "https://login.riotgames.com/end-session-redirect?redirect_uri=https%3A%2F%2Fauth.riotgames.com%2Flogout"
        log(f"[{sid}] Logout va don dep tab...")
        await sw("open_url", tab({"url": LOGOUT_URL}))
        await sw("clear_cookies", {})
        await asyncio.sleep(2)

        # Đóng tất cả tab trừ tab đầu tiên (giữ browser khỏi đóng)
        all_tabs_res = await send_and_wait(session_id, "list_tabs", {}, timeout=5)
        all_tabs = ((all_tabs_res or {}).get("result", [])) or []
        for t in all_tabs[1:]:
            tid = t.get("id") if isinstance(t, dict) else None
            if tid:
                await send_and_wait(session_id, "close_tab", {"tabId": tid}, timeout=5)
        await asyncio.sleep(1)
        log(f"[{sid}] San sang cho account tiep theo...")

    except Exception as e:
        set_status(session_id, "Loi")
        log(f"[{sid}] Error: {e}")

    finally:
        # Luôn logout + dọn tab dù thành công hay lỗi
        try:
            LOGOUT_URL = "https://login.riotgames.com/end-session-redirect?redirect_uri=https%3A%2F%2Fauth.riotgames.com%2Flogout"
            log(f"[{sid}] [finally] Logout va dong tab...")
            await send_and_wait(session_id, "open_url",
                                {"url": LOGOUT_URL, "newTab": False}, timeout=10)
            await send_and_wait(session_id, "clear_cookies", {}, timeout=5)
            await asyncio.sleep(2)
            # Đóng tất cả tab trừ tab[0]
            tabs_r = await send_and_wait(session_id, "list_tabs", {}, timeout=5)
            tabs   = ((tabs_r or {}).get("result", [])) or []
            for t in tabs[1:]:
                tid = t.get("id") if isinstance(t, dict) else None
                if tid:
                    await send_and_wait(session_id, "close_tab", {"tabId": tid}, timeout=5)
            log(f"[{sid}] [finally] Tab sach — san sang account tiep theo")
        except Exception as fe:
            log(f"[{sid}] [finally] Loi don dep: {fe}")



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

    # Đưa tất cả account vào queue — mỗi session worker tự pick
    queue: asyncio.Queue = asyncio.Queue()
    for acct in accounts:
        await queue.put(acct)

    async def session_worker(sid):
        """Mỗi session lấy account từ queue cho đến khi hết."""
        while not _stop_flag:
            try:
                acct = queue.get_nowait()
            except asyncio.QueueEmpty:
                break  # Hết account
            entry = {
                "session_id":   sid,
                "username":     acct["username"],
                "old_password": acct["old_password"],
                "new_password": acct["new_password"],
                "status":       "Cho...",
            }
            acct_log.append(entry)
            bridge.refresh_signal.emit()
            log(f"  >> [{str(sid)[:8]}] {acct['username']}")
            await run_changepass(sid, acct["username"], acct["old_password"], acct["new_password"])
            queue.task_done()

    tasks = [asyncio.create_task(session_worker(sid)) for sid in session_ids]
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

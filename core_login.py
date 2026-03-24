"""
core_login.py — Business logic cho chức năng Login (không có WS server)
WS server được quản lý tập trung bởi gui.py
"""

import asyncio
import json
import random
import time
import sys
import os
import urllib.parse
import requests
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
acct_log   = []   # [{session_id, username, password, status, note}]

_req_id    = 0
_loop      = None
_running   = False
_stop_flag = False

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
ACCOUNT_FILE = os.path.join(BASE_DIR, "account_login.txt")

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

def set_status(session_id, status, note=""):
    if session_id in sessions:
        sessions[session_id]["status"] = status
    for e in reversed(acct_log):
        if e["session_id"] == session_id:
            e["status"] = status
            if note:
                e["note"] = note
            break
    bridge.refresh_signal.emit()

# ── Load accounts ─────────────────────────────────────────────────────────────
def load_accounts():
    """
    Đọc file account_login.txt, mỗi dòng: username|password
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
            if len(parts) >= 2:
                accounts.append({"username": parts[0].strip(), "password": parts[1].strip()})
    log(f">> Doc duoc {len(accounts)} tai khoan tu account_login.txt")
    return accounts

# ── Automation ────────────────────────────────────────────────────────────────
LOGIN_URL = "https://auth.riotgames.com/authorize?redirect_uri=http://localhost/redirect&client_id=riot-client&response_type=token%20id_token&nonce=1&scope=openid%20link%20ban%20lol_region%20account"

async def run_login(session_id, username, password):
    sid = str(session_id)[:8]
    log(f"[{sid}] Bat dau login: {username}")
    set_status(session_id, "Dang chay")

    sw  = lambda a, d, **kw: send_and_wait(session_id, a, d, **kw)
    wfs = lambda s, t=None, **kw: wait_for_selector(session_id, s, t, **kw)

    try:
        # ── 1. Mo tab moi trang dang nhap Riot ──
        res    = await sw("open_url", {"url": LOGIN_URL, "newTab": True})
        tab_id = (res or {}).get("result", {}).get("tabId")

        def tab(x={}):
            d = dict(x)
            if tab_id:
                d["tabId"] = tab_id
            return d

        # ── 3. Cho o Username hien ra ──
        username_sel = '[data-testid="input-username"]'
        if not await wfs(username_sel, tab_id, max_wait=25):
            log(f"[{sid}] !! Khong thay o username — trang chua tai xong")
            set_status(session_id, "Loi", "Timeout username")
            return

        await human_delay(0.5, 1.0)
        await sw("type_text", tab({"selector": username_sel, "value": username}))

        # ── 4. Nhap Password ──
        password_sel = '[data-testid="input-password"]'
        if await wfs(password_sel, tab_id, max_wait=10):
            await human_delay(0.3, 0.8)
            await sw("type_text", tab({"selector": password_sel, "value": password}))

        await human_delay(0.6, 1.3)

        # ── 5. Bam Login ──
        submit_sel = '[data-testid="btn-signin-submit"]'
        await sw("click", tab({"selector": submit_sel}))
        log(f"[{sid}] Da bam Login, cho phan hoi...")

        # ── 6. Cho hCaptcha neu xuat hien ──
        # Chi check captcha VISIBLE (checkbox frame), bo qua invisible captcha (tu solve)
        # Frame checkbox co src chua "frame=checkbox" va KHONG phai checkbox-invisible
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

        # ── 7. Kiem tra ket qua ──
        await asyncio.sleep(7)

        error_sels = [
            '[data-testid="error-message"]',
        ]
        for err_sel in error_sels:
            res_err = await send_and_wait(session_id, "check_element",
                                          tab({"selector": err_sel}), timeout=4)
            if (res_err or {}).get("result", {}).get("found"):
                log(f"[{sid}] !! Co thong bao loi hien thi — co the sai mat khau")
                set_status(session_id, "Loi", "Sai mat khau")
                return

        # mfa_sels = [
        #     '[data-testid="mfa-code-input"]',
        #     'input[placeholder*="code"]',
        #     '[data-testid="multifactor"]',
        # ]
        # for mfa_sel in mfa_sels:
        #     res_mfa = await send_and_wait(session_id, "check_element",
        #                                    tab({"selector": mfa_sel}), timeout=4)
        #     if (res_mfa or {}).get("result", {}).get("found"):
        #         log(f"[{sid}] -- Tai khoan co bat 2FA (yeu cau nhap ma)")
        #         set_status(session_id, "Can 2FA", "Bat 2FA")
        #         return

        logged_in = True

        await asyncio.sleep(5)
        if logged_in:
            log(f"[{sid}] ++ Dang nhap thanh cong: {username}")
            set_status(session_id, "Lay token...", "Dang nhap OK")
            access_token = ""
            token_tab_id = None
            for i in range(40):   # toi da ~20s
                await asyncio.sleep(0.5)
                if _stop_flag:
                    break
                tabs_res = await send_and_wait(session_id, "list_tabs", {}, timeout=5)
                tabs = []
                if tabs_res:
                    r = tabs_res.get("result", [])
                    tabs = r if isinstance(r, list) else []
                if i % 6 == 0:
                    log(f"[{sid}] [DBG] so tab={len(tabs)}")
                for t in tabs:
                    url = t.get("url", "") if isinstance(t, dict) else ""
                    if "access_token=" in url:
                        # Token co the nam trong fragment (#) hoac query string (?)
                        frag   = url.split("#", 1)[-1] if "#" in url else url.split("?", 1)[-1]
                        params = dict(urllib.parse.parse_qsl(frag))
                        tok    = params.get("access_token", "")
                        if tok:
                            access_token = tok
                            token_tab_id = t.get("id") or t.get("tabId")
                            break
                if access_token:
                    break

            # Dong tab chua token (localhost/redirect) sau khi lay xong
            if token_tab_id:
                await send_and_wait(session_id, "close_tab", {"tabId": token_tab_id}, timeout=5)

            if access_token:
                log(f"[{sid}] ++ Token: {access_token[:50]}...")
                for e in reversed(acct_log):
                    if e["session_id"] == session_id:
                        e["token"] = access_token
                        break
                token_file = os.path.join(BASE_DIR, "token.txt")
                with open(token_file, "a", encoding="utf-8") as f:
                    f.write(f"{username}|{password}|{access_token}\n")
                log(f"[{sid}] Da ghi token vao token.txt")

                # ── Lay thong tin user tu /userinfo bang requests Python ──
                log(f"[{sid}] Dang lay userinfo (requests)...")

                def _fetch_userinfo():
                    try:
                        r = requests.post(
                            "https://auth.riotgames.com/userinfo",
                            headers={
                                "Authorization": f"Bearer {access_token}",
                                "Content-Type": "application/json",
                            },
                            timeout=10,
                        )
                        return r.status_code, r.text
                    except Exception as ex:
                        return -1, str(ex)

                loop = asyncio.get_event_loop()
                ui_status, ui_body = await loop.run_in_executor(None, _fetch_userinfo)
                log(f"[{sid}] Userinfo HTTP {ui_status}: {ui_body[:300]}")

                ui_data = {}
                try:
                    if ui_status == 200:
                        ui_data = json.loads(ui_body)
                except Exception:
                    pass

                for e in reversed(acct_log):
                    if e["session_id"] == session_id:
                        e["userinfo"]     = ui_data
                        e["userinfo_raw"] = ui_body
                        break

                userinfo_file = os.path.join(BASE_DIR, "userinfo.txt")
                with open(userinfo_file, "a", encoding="utf-8") as f:
                    f.write(f"{username}|{password}|{access_token}|{ui_body}\n")
                log(f"[{sid}] Da ghi userinfo vao userinfo.txt")

                bridge.refresh_signal.emit()
                set_status(session_id, "Hoan thanh", "Co token")
            else:
                log(f"[{sid}] ?? Khong lay duoc token")
                for e in reversed(acct_log):
                    if e["session_id"] == session_id:
                        e["token"] = ""
                        break
                set_status(session_id, "Hoan thanh", "Khong co token")
        else:
            log(f"[{sid}] ?? Khong ro ket qua — kiem tra thu cong: {username}")
            set_status(session_id, "Can kiem tra", "")

    except Exception as e:
        set_status(session_id, "Loi", str(e))
        log(f"[{sid}] Error: {e}")


async def _logout_session(session_id):
    """Navigate đến Riot logout URL để hủy session, rồi đóng tab thừa."""
    sid = str(session_id)[:8]
    sw = lambda a, d, **kw: send_and_wait(session_id, a, d, **kw)
    try:
        # Đóng hết tab thừa (trừ tab đầu tiên)
        tabs_res = await sw("list_tabs", {}, timeout=5)
        tabs = []
        if tabs_res:
            r = tabs_res.get("result", [])
            tabs = r if isinstance(r, list) else []
        for t in tabs[1:]:
            tid = t.get("id") or t.get("tabId")
            if tid:
                await sw("close_tab", {"tabId": tid}, timeout=4)
        # Navigate đến trang logout chính thức của Riot
        log(f"[{sid}] Dang logout Riot...")
        await sw("open_url", {"url": "https://auth.riotgames.com/logout"}, timeout=10)
        await asyncio.sleep(3)   # chờ server hủy session + redirect xong
        log(f"[{sid}] Logout xong, san sang account tiep theo")
    except Exception as ex:
        log(f"[{sid}] Warning logout: {ex}")


async def _session_worker(session_id, queue):
    """Mỗi session lấy account từ queue → login → logout → lặp lại."""
    sid = str(session_id)[:8]
    first = True
    while not _stop_flag:
        try:
            acct = queue.get_nowait()
        except asyncio.QueueEmpty:
            break

        if not first:
            # Logout browser sau account trước
            await _logout_session(session_id)
            await asyncio.sleep(1)
        first = False

        log(f"[{sid}] Bat dau account: {acct['username']}")
        entry = {
            "session_id": session_id,
            "username":   acct["username"],
            "password":   acct["password"],
            "status":     "Cho...",
        }
        acct_log.append(entry)
        bridge.refresh_signal.emit()

        await run_login(session_id, acct["username"], acct["password"])
        queue.task_done()

    log(f"[{sid}] Worker ket thuc")


async def run_all_sessions():
    global _running, _stop_flag
    _stop_flag = False

    accounts = load_accounts()
    if not accounts:
        log("!! Khong co tai khoan nao (dinh dang: username|password)")
        _running = False
        bridge.refresh_signal.emit()
        return

    session_ids = list(sessions.keys())
    if not session_ids:
        log("!! Chua co session nao ket noi!")
        _running = False
        bridge.refresh_signal.emit()
        return

    # Nạp hết accounts vào queue dùng chung
    queue = asyncio.Queue()
    for acct in accounts:
        await queue.put(acct)

    log(f">> {len(session_ids)} session(s) | {len(accounts)} accounts | Queue mode")
    bridge.refresh_signal.emit()

    # Mỗi session chạy worker vòng lặp lấy từ queue
    tasks = [asyncio.create_task(_session_worker(sid, queue)) for sid in session_ids]
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

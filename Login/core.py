"""
core.py — Business logic, WebSocket server, shared state (Login)
"""

import asyncio
import threading
import websockets
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
acct_log   = []   # [{session_id, username, password, status, note}]

_req_id    = 0
_loop      = None
_gui       = None
_running   = False
_stop_flag = False

ACCOUNT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "account.txt")

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
    Đọc file account.txt, mỗi dòng: username|password
    Trả về list [{"username": ..., "password": ...}]
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
    log(f">> Doc duoc {len(accounts)} tai khoan tu account.txt")
    return accounts

# ── Automation ────────────────────────────────────────────────────────────────
LOGIN_URL = "https://support.riotgames.com/hc/en-us"

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

        # ── 2. Bam nut "Sign in" tren trang Support ──
        signin_btn_sel = '[data-telemetry-label="masthead-login-button"]'
        if await wfs(signin_btn_sel, tab_id, max_wait=20):
            await human_delay(0.5, 1.0)
            await sw("click", tab({"selector": signin_btn_sel}))
            log(f"[{sid}] Da bam Sign in, cho form login hien ra...")
        else:
            log(f"[{sid}] !! Khong thay nut Sign in")
            set_status(session_id, "Loi", "Khong thay nut Sign in")
            return

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

        # ── 5. Cho hCaptcha neu xuat hien, lap moi 5s cho den khi bien mat ──
        captcha_sel = 'iframe[src*="hcaptcha.com"]'
        log(f"[{sid}] Kiem tra hCaptcha...")
        while True:
            res_cap = await send_and_wait(session_id, "check_element",
                                          tab({"selector": captcha_sel}), timeout=5)
            found_cap = (res_cap or {}).get("result", {}).get("found", False)
            if not found_cap:
                break
            log(f"[{sid}] hCaptcha dang hien — cho 5s...")
            await asyncio.sleep(5)
        log(f"[{sid}] hCaptcha da bien mat, tiep tuc...")

        # ── 6. Kiem tra ket qua: thanh cong / sai mat khau / 2FA ──
        await asyncio.sleep(3)

        # Kiem tra loi "sai mat khau"
        error_sels = [
            '[data-testid="error-message"]',
            '[class*="error"]',
            '[aria-live="polite"]',
        ]
        for err_sel in error_sels:
            res_err = await send_and_wait(session_id, "check_element",
                                          tab({"selector": err_sel}), timeout=4)
            if (res_err or {}).get("result", {}).get("found"):
                # Doc noi dung loi
                log(f"[{sid}] !! Co thong bao loi hien thi — co the sai mat khau")
                set_status(session_id, "Loi", "Sai mat khau")
                return

        # Kiem tra 2FA (MFA)
        mfa_sels = [
            '[data-testid="mfa-code-input"]',
            'input[placeholder*="code"]',
            '[data-testid="multifactor"]',
        ]
        for mfa_sel in mfa_sels:
            res_mfa = await send_and_wait(session_id, "check_element",
                                           tab({"selector": mfa_sel}), timeout=4)
            if (res_mfa or {}).get("result", {}).get("found"):
                log(f"[{sid}] -- Tai khoan co bat 2FA (yeu cau nhap ma)")
                set_status(session_id, "Can 2FA", "Bat 2FA")
                return

        # Kiem tra da dang nhap thanh cong: URL chuyen sang trang account
        # hoac nut logout hien ra
        success_sels = [
            '[data-testid="username-display"]',
            'a[href*="logout"]',
            '[data-testid="account-alias"]',
        ]
        logged_in = False
        for succ_sel in success_sels:
            res_ok = await send_and_wait(session_id, "check_element",
                                          tab({"selector": succ_sel}), timeout=5)
            if (res_ok or {}).get("result", {}).get("found"):
                logged_in = True
                break
        await asyncio.sleep(5)        
        if logged_in:
            log(f"[{sid}] ++ Dang nhap thanh cong: {username}")
            set_status(session_id, "Lay cookie...", "Dang nhap OK")

            # ── Vao trang geo_info de lay cookie ──
            GEO_URL = "https://sspd.playersupport.riotgames.com/geo_info/ip"
            log(f"[{sid}] Mo trang lay cookie: {GEO_URL}")
            await sw("open_url", tab({"url": GEO_URL}))
            await asyncio.sleep(2)

            # Lay toan bo cookie cua tab hien tai
            res_cookie = await send_and_wait(session_id, "get_cookies", tab({}), timeout=10)
            cookies = (res_cookie or {}).get("result", {}).get("cookies", [])

            if cookies:
                # Dinh dang thanh chuoi key=value
                cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
                log(f"[{sid}] Cookie ({len(cookies)} muc): {cookie_str[:120]}...")
                # Luu vao acct_log
                for e in reversed(acct_log):
                    if e["session_id"] == session_id:
                        e["cookies"] = cookie_str
                        break
                # Ghi ra file cookies.txt
                cookie_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")
                with open(cookie_file, "a", encoding="utf-8") as f:
                    f.write(f"{username}|{password}|{cookie_str}\n")
                log(f"[{sid}] Da ghi cookie vao cookies.txt")

                # ── Goi POST API start_workflow ──
                WORKFLOW_URL = "https://sspd.playersupport.riotgames.com/arbiter/edge/start_workflow"
                WORKFLOW_BODY = json.dumps({
                    "locale":  "en_US",
                    "host":    "https://sspd.playersupport.riotgames.com",
                    "name":    "cu2_hub_pb.m3",
                    "channel": "WEB"
                })
                log(f"[{sid}] Goi POST {WORKFLOW_URL}...")

                # Dung execute_script de chay fetch trong browser (cookie da co san)
                js_code = f"""
(async () => {{
  try {{
    const res = await fetch("{WORKFLOW_URL}", {{
      method: "POST",
      headers: {{
        "Content-Type": "application/json",
        "Accept": "application/json"
      }},
      body: {repr(WORKFLOW_BODY)},
      credentials: "include"
    }});
    const text = await res.text();
    return {{ status: res.status, body: text.substring(0, 500) }};
  }} catch(err) {{
    return {{ status: -1, body: err.toString() }};
  }}
}})()
"""
                res_wf = await send_and_wait(session_id, "execute_script",
                                              tab({"script": js_code}), timeout=20)
                wf_result = (res_wf or {}).get("result", {})
                wf_status  = wf_result.get("status", "?")
                wf_body    = wf_result.get("body", "")
                log(f"[{sid}] Workflow response HTTP {wf_status}: {wf_body[:200]}")

                # Luu ket qua vao acct_log va file
                for e in reversed(acct_log):
                    if e["session_id"] == session_id:
                        e["workflow_status"] = wf_status
                        e["workflow_body"]   = wf_body
                        break
                wf_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workflow_results.txt")
                with open(wf_file, "a", encoding="utf-8") as f:
                    f.write(f"{username}|{password}|HTTP{wf_status}|{wf_body}\n")
                log(f"[{sid}] Da ghi ket qua workflow vao workflow_results.txt")

                set_status(session_id, "Hoan thanh", "Co cookie")
            else:
                log(f"[{sid}] ?? Khong lay duoc cookie")
                set_status(session_id, "Hoan thanh", "Khong co cookie")


        else:
            # Van co the thanh cong nhung khong tim thay selector — ghi nhan
            log(f"[{sid}] ?? Khong ro ket qua — kiem tra thu cong: {username}")
            set_status(session_id, "Can kiem tra", "")

    except Exception as e:
        set_status(session_id, "Loi", str(e))
        log(f"[{sid}] Error: {e}")


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

    log(f">> Bat dau {len(session_ids)} session(s) voi {len(accounts)} tai khoan...")

    tasks = []
    for sid, acct in zip(session_ids, accounts):
        entry = {
            "session_id": sid,
            "username":   acct["username"],
            "password":   acct["password"],
            "status":     "Cho...",
            "note":       "",
        }
        acct_log.append(entry)
        log(f"  >> [{str(sid)[:8]}] {acct['username']}")
        tasks.append(asyncio.create_task(
            run_login(sid, acct["username"], acct["password"])
        ))

    bridge.refresh_signal.emit()
    await asyncio.gather(*tasks, return_exceptions=True)
    log(">> Tat ca sessions hoan thanh!")
    _running = False
    bridge.refresh_signal.emit()


# ── WebSocket server ───────────────────────────────────────────────────────────
async def ws_handler(websocket):
    session_id = None
    try:
        async for raw in websocket:
            try:
                msg = json.loads(raw)
            except Exception as e:
                log(f"Parse error: {e}")
                continue
            t = msg.get("type")
            if t == "register":
                session_id = msg.get("sessionId")
                if not session_id:
                    continue
                sessions[session_id] = {
                    "ws": websocket, "info": msg,
                    "pending": {}, "status": "Ket noi",
                    "connected_at": time.time()
                }
                log(f"++ Session: {str(session_id)[:8]}... ({len(sessions)} total)")
                bridge.refresh_signal.emit()
            elif t == "result":
                sid = msg.get("sessionId") or session_id
                if sid and sid in sessions:
                    rid = msg.get("requestId")
                    p   = sessions[sid]["pending"]
                    if rid and rid in p and not p[rid].done():
                        p[rid].set_result(msg)
    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        log(f"Handler error: {e}")
    finally:
        if session_id and session_id in sessions:
            sessions.pop(session_id, None)
            log(f"-- Session ngat: {str(session_id)[:8]}... ({len(sessions)} con)")
            bridge.refresh_signal.emit()

async def _ws_server():
    await websockets.serve(ws_handler, "127.0.0.1", 8000)
    log("[WS] Server san sang: ws://127.0.0.1:8000")
    await asyncio.Future()

def start_asyncio_loop():
    global _loop
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    _loop.run_until_complete(_ws_server())

# ── Public triggers (called from GUI) ─────────────────────────────────────────
def trigger_run():
    global _running
    if _running:
        return
    _running = True
    asyncio.run_coroutine_threadsafe(run_all_sessions(), _loop)

def trigger_stop():
    global _stop_flag, _running
    _stop_flag = True
    _running   = False
    log("!! Dung — cac session se ket thuc sau buoc hien tai")
    bridge.refresh_signal.emit()

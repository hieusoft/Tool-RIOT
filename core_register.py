"""
core_register.py — Business logic cho chức năng Đăng ký tài khoản (không có WS server)
WS server được quản lý tập trung bởi gui.py
"""

import asyncio
import json
import random
import time
import sys
import re
from datetime import datetime
from faker import Faker

from PyQt6.QtCore import QObject, pyqtSignal

fake = Faker()

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ── Shared state ──────────────────────────────────────────────────────────────
sessions   = {}   # {sessionId: {ws, pending, status, connected_at}}
acct_log   = []   # [{session_id, username, email, password, status}]

_req_id    = 0
_loop      = None
_running   = False
_stop_flag = False

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

async def wait_for_selector(session_id, sel, tab_id=None, max_wait=20, interval=0.4):
    data = {"selector": sel}
    if tab_id:
        data["tabId"] = tab_id
    elapsed = 0
    while elapsed < max_wait:
        if _stop_flag:
            return False
        res = await send_and_wait(session_id, "check_element", data, timeout=5)
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

# ── Automation ────────────────────────────────────────────────────────────────
async def run_signup(session_id, email, username, password):
    sid = str(session_id)[:8]

    while True:
        if _stop_flag:
            set_status(session_id, "Da dung")
            return
        log(f"[{sid}] Start: {email} / {username}")
        set_status(session_id, "Dang chay")

        sw  = lambda a, d, **kw: send_and_wait(session_id, a, d, **kw)
        wfs = lambda s, t=None, **kw: wait_for_selector(session_id, s, t, **kw)

        try:
            res    = await sw("open_url", {"url": "https://signup.leagueoflegends.com/en-us/signup/index#/", "newTab": True})
            tab_id = (res or {}).get("result", {}).get("tabId")

            def tab(x={}):
                d = dict(x)
                if tab_id: d["tabId"] = tab_id
                return d

            if await wfs('[data-testid="riot-signup-email"]', tab_id):
                await human_delay(0.5, 1.0)
                await sw("type_text", tab({"selector": '[data-testid="riot-signup-email"]', "value": email}), timeout=30)

            await human_delay(0.6, 1.4)
            await sw("click", tab({"selector": "#newsletter"}))
            await human_delay(0.3, 0.8)
            await sw("click", tab({"selector": "#thirdpartycomms"}))
            await human_delay(0.8, 1.8)
            await sw("click", tab({"selector": '[data-testid="btn-signup-submit"]'}))

            if await wfs('[data-testid="riot-signup-username"]', tab_id):
                await human_delay()
                await sw("type_text", tab({"selector": '[data-testid="riot-signup-username"]', "value": username}), timeout=20)

            await human_delay(0.7, 1.5)
            await sw("click", tab({"selector": '[data-testid="btn-signup-submit"]'}))

            if await wfs('[data-testid="input-password"]', tab_id):
                await human_delay()
                await sw("type_text", tab({"selector": '[data-testid="input-password"]', "value": password}), timeout=20)

            if await wfs('[data-testid="password-confirm"]', tab_id):
                await human_delay(0.4, 0.9)
                await sw("type_text", tab({"selector": '[data-testid="password-confirm"]', "value": password}), timeout=20)

            await human_delay(0.7, 1.5)
            await sw("click", tab({"selector": '[data-testid="btn-signup-submit"]'}))

            if await wfs('#tos-scrollable-area', tab_id, max_wait=20):
                await human_delay()
                for pos in [500, 1500, 3000, 999999]:
                    await sw("scroll_element", tab({"selector": "#tos-scrollable-area", "top": pos}))
                    await human_delay(0.4, 0.9)
                if await wfs('#tos-checkbox:not([disabled])', tab_id, max_wait=10):
                    await human_delay(0.3, 0.7)
                    await sw("click", tab({"selector": "#tos-checkbox"}))
                    await human_delay(0.4, 0.8)
                    if await wfs('[data-testid="btn-accept-tos"]:not([disabled])', tab_id, max_wait=10):
                        await human_delay(0.5, 1.0)
                        await sw("click", tab({"selector": '[data-testid="btn-accept-tos"]'}))

                        captcha_sel = 'iframe[src*="hcaptcha.com"]'
                        log(f"[{sid}] Kiem tra hCaptcha...")
                        while True:
                            res = await send_and_wait(session_id, "check_element",
                                                      tab({"selector": captcha_sel}), timeout=5)
                            found = (res or {}).get("result", {}).get("found", False)
                            if not found:
                                break
                            log(f"[{sid}] hCaptcha dang hien — cho 5s...")
                            await asyncio.sleep(5)
                        log(f"[{sid}] hCaptcha da bien mat, tiep tuc...")

            set_status(session_id, "Hoan thanh")
            log(f"[{sid}] Done! Xoa cookie va tao account moi...")

            LOGOUT_URL = "https://login.riotgames.com/end-session-redirect?redirect_uri=https%3A%2F%2Fauth.riotgames.com%2Flogout"
            await sw("open_url", tab({"url": LOGOUT_URL}))
            await sw("clear_cookies", tab({}))
            await asyncio.sleep(3)

            if _stop_flag:
                set_status(session_id, "Da dung")
                return

            base     = re.sub(r'[^a-zA-Z0-9_]', '', fake.user_name())[:13] or "user"
            username = base + fake.numerify("##")
            email    = fake.email()
            password = "Auto@" + fake.numerify("######")
            acct_log.append({"session_id": session_id, "username": username,
                             "email": email, "password": password, "status": "Dang chay"})
            bridge.refresh_signal.emit()
            log(f"[{sid}] Vong moi: {email} / {username}")

        except Exception as e:
            set_status(session_id, "Loi")
            log(f"[{sid}] Error: {e}")
            await asyncio.sleep(3)


async def run_all_sessions():
    global _running, _stop_flag
    _stop_flag = False
    if not sessions:
        log("!! Chua co session nao!")
        _running = False
        bridge.refresh_signal.emit()
        return

    log(f">> Bat dau {len(sessions)} session(s)...")
    tasks = []
    for sid in list(sessions.keys()):
        base     = re.sub(r'[^a-zA-Z0-9_]', '', fake.user_name())[:13] or "user"
        username = base + fake.numerify("##")
        email    = fake.email()
        password = "Auto@" + fake.numerify("######")
        acct_log.append({"session_id": sid, "username": username,
                          "email": email, "password": password, "status": "Cho..."})
        log(f"  >> {email} / {username}")
        tasks.append(asyncio.create_task(run_signup(sid, email, username, password)))

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

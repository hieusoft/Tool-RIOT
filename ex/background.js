const WS_URL = "ws://127.0.0.1:8000/ws";

let SESSION_ID  = null;
let ws          = null;
let wsConnected = false;
let registered  = false;   // true sau khi user bấm "Sẵn sàng"
let reconnectTimer = null;

function log(...args) {
  console.log("[WS-EXT]", ...args);
}

// ── Khởi tạo sessionId (persistent) ─────────────────────────────────────────
async function initSession() {
  const stored = await chrome.storage.local.get("sessionId");
  if (stored.sessionId) {
    SESSION_ID = stored.sessionId;
    log("Reusing sessionId:", SESSION_ID);
  } else {
    SESSION_ID = crypto.randomUUID();
    await chrome.storage.local.set({ sessionId: SESSION_ID });
    log("New sessionId:", SESSION_ID);
  }
  // Kết nối WS nhưng CHƯA register – chờ user bấm "Sẵn sàng"
  connectWebSocket();
}

// ── Kết nối WebSocket ─────────────────────────────────────────────────────────
function connectWebSocket() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return;
  }

  log("Connecting WS:", WS_URL);
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    wsConnected = true;
    log("WS connected. Chờ user bấm Sẵn sàng...");
    // KHÔNG tự gửi register ở đây
  };

  ws.onmessage = async (event) => {
    let message;
    try {
      message = JSON.parse(event.data);
      log("Nhận lệnh:", message);
      const result = await handleCommand(message);
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: "result",
          sessionId: SESSION_ID,
          requestId: message.requestId || null,
          ok: true,
          result
        }));
      }
    } catch (error) {
      console.error("[WS-EXT] Lỗi:", error);
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: "result",
          sessionId: SESSION_ID,
          requestId: message?.requestId || null,
          ok: false,
          error: String(error)
        }));
      }
    }
  };

  ws.onclose = () => {
    wsConnected = false;
    registered = false;
    log("WS disconnected, reconnect sau 3s...");
    scheduleReconnect();
  };

  ws.onerror = (err) => {
    console.error("[WS-EXT] WS error:", err);
    try { ws.close(); } catch (_) {}
  };
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connectWebSocket();
  }, 3000);
}

// ── Gửi register lên server ────────────────────────────────────────────────── 
function sendRegister(mode) {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    return false;
  }
  const m = mode || "login";
  ws.send(JSON.stringify({
    type: "register",
    sessionId: SESSION_ID,
    mode: m,
    source: "chrome-extension",
    userAgent: navigator.userAgent,
    time: new Date().toISOString()
  }));
  registered = true;
  log("Registered! sessionId:", SESSION_ID, "mode:", m);
  return true;
}

// ── Lắng nghe message từ popup ────────────────────────────────────────────────
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "get_state") {
    sendResponse({
      sessionId: SESSION_ID,
      wsConnected,
      registered
    });
    return true;
  }

  if (msg.type === "unregister") {
    registered = false;
    // Tạo session ID mới và reconnect — server drop session cũ khi WS đóng
    SESSION_ID = crypto.randomUUID();
    chrome.storage.local.set({ sessionId: SESSION_ID });
    log("New sessionId:", SESSION_ID);
    if (ws) { try { ws.close(); } catch (_) {} ws = null; }
    connectWebSocket();
    sendResponse({ ok: true });
    return true;
  }

  if (msg.type === "register_now") {
    if (!wsConnected) {
      sendResponse({ ok: false, error: "WS chua ket noi" });
      return true;
    }
    if (registered) {
      sendResponse({ ok: true, already: true });
      return true;
    }
    const ok = sendRegister(msg.mode || "login");
    sendResponse({ ok, sessionId: SESSION_ID });
    return true;
  }
});

// ── Command handler (từ server) ───────────────────────────────────────────────
async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  return tabs[0] || null;
}

async function handleCommand(message) {
  const { action, data = {} } = message;
  switch (action) {
    case "ping":          return { pong: true, sessionId: SESSION_ID, time: new Date().toISOString() };
    case "open_url":      return await openUrl(data);
    case "reload_tab":    return await reloadTab(data);
    case "close_tab":     return await closeTab(data);
    case "activate_tab":  return await activateTab(data);
    case "list_tabs":     return await listTabs();
    case "execute_script": return await executeScriptInTab(data);
    case "fill_field":      return await fillFieldInTab(data);
    case "click":           return await sendToContentScript("click", data);
    case "fill":            return await sendToContentScript("fill", data);
    case "type_text":       return await sendToContentScript("type_text", data);
    case "get_title":       return await getTitle(data);
    case "get_url":         return await getUrl(data);
    case "get_cookies":     return await getCookies(data);
    case "check_element":   return await checkElement(data);
    case "scroll_element":  return await scrollElement(data);
    default: throw new Error(`Action không hỗ trợ: ${action}`);
  }
}

// Cho tab load xong (status = "complete"), polling moi 300ms, toi da 30s
async function waitForTabLoad(tabId, maxMs = 30000) {
  const start = Date.now();
  while (Date.now() - start < maxMs) {
    const tab = await chrome.tabs.get(tabId);
    if (tab.status === "complete") return tab;
    await new Promise(r => setTimeout(r, 300));
  }
  // Tra ve trang thai hien tai du chua complete
  return await chrome.tabs.get(tabId);
}

async function openUrl(data) {
  const url    = data.url;
  const newTab = data.newTab !== false;
  if (!url) throw new Error("Thiếu data.url");
  if (newTab) {
    const tab     = await chrome.tabs.create({ url, active: true });
    const loaded  = await waitForTabLoad(tab.id);
    return { tabId: loaded.id, url: loaded.url, status: loaded.status };
  } else {
    const tab = data.tabId
      ? await chrome.tabs.get(data.tabId)
      : await getActiveTab();
    if (!tab?.id) throw new Error("Không tìm thấy active tab");
    await chrome.tabs.update(tab.id, { url, active: true });
    const loaded = await waitForTabLoad(tab.id);
    return { tabId: loaded.id, url: loaded.url, status: loaded.status };
  }
}
async function reloadTab(data) {
  const tabId = data.tabId || (await getActiveTab())?.id;
  if (!tabId) throw new Error("Không tìm thấy tab để reload");
  await chrome.tabs.reload(tabId);
  return { tabId, reloaded: true };
}
async function closeTab(data) {
  const tabId = data.tabId || (await getActiveTab())?.id;
  if (!tabId) throw new Error("Không tìm thấy tab để đóng");
  await chrome.tabs.remove(tabId);
  return { tabId, closed: true };
}
async function activateTab(data) {
  if (!data.tabId) throw new Error("Thiếu data.tabId");
  await chrome.tabs.update(data.tabId, { active: true });
  return { tabId: data.tabId, activated: true };
}
async function listTabs() {
  const tabs = await chrome.tabs.query({});
  return tabs.map(t => ({ id: t.id, title: t.title, url: t.url, active: t.active }));
}
async function getTitle(data) {
  const tabId = data.tabId || (await getActiveTab())?.id;
  if (!tabId) throw new Error("Không tìm thấy tab");
  const tab = await chrome.tabs.get(tabId);
  return { tabId, title: tab.title, url: tab.url };
}
async function getUrl(data) {
  const tabId = data.tabId || (await getActiveTab())?.id;
  if (!tabId) throw new Error("Không tìm thấy tab");
  const tab = await chrome.tabs.get(tabId);
  return { tabId, url: tab.url };
}
async function executeScriptInTab(data) {
  const tabId = data.tabId || (await getActiveTab())?.id;
  if (!tabId) throw new Error("Không tìm thấy tab");
  const code = data.script || data.code;
  if (!code) throw new Error("Thiếu data.script");
  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: (c) => { try { return { ok: true, result: eval(c) }; } catch(e) { return { ok: false, error: String(e) }; } },
    args: [code]
  });
  return results?.[0]?.result || null;
}

// fill_field native — allFrames de tim trong iframe
async function fillFieldInTab(data) {
  const tabId = data.tabId || (await getActiveTab())?.id;
  if (!tabId) throw new Error("Không tìm thấy tab");
  if (!data.selector) throw new Error("Thiếu data.selector");
  const results = await chrome.scripting.executeScript({
    target: { tabId, allFrames: true },
    func: (sel, val) => {
      var el = document.querySelector(sel);
      if (!el) return null; // null = khong co trong frame nay
      el.focus();
      try {
        var desc = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
        if (desc && desc.set) desc.set.call(el, val);
        else el.value = val;
      } catch(e) { el.value = val; }
      ['input','change','blur'].forEach(function(t) {
        try { el.dispatchEvent(new Event(t, {bubbles:true,cancelable:true})); } catch(_){}
      });
      return { ok: true, value: el.value, frame: location.href };
    },
    args: [data.selector, String(data.value ?? "")]
  });
  // Tim frame nao tra ve ket qua thuc su (khong null)
  const hit = (results || []).find(r => r?.result !== null && r?.result !== undefined);
  if (hit) return hit.result;
  return { ok: false, error: 'not found in any frame: ' + data.selector };
}


async function getCookies(data) {
  const tabId = data.tabId || (await getActiveTab())?.id;
  if (!tabId) throw new Error("Không tìm thấy tab");
  const tab = await chrome.tabs.get(tabId);
  const url = tab.url;
  const cookies = await chrome.cookies.getAll({ url });
  return { cookies: cookies.map(c => ({ name: c.name, value: c.value, domain: c.domain })) };
}
async function checkElement(data) {
  const tabId = data.tabId || (await getActiveTab())?.id;
  if (!tabId) throw new Error("Không tìm thấy tab");
  if (!data.selector) throw new Error("Thiếu data.selector");
  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: (sel) => !!document.querySelector(sel),
    args: [data.selector]
  });
  return { found: !!(results?.[0]?.result) };
}
async function scrollElement(data) {
  const tabId = data.tabId || (await getActiveTab())?.id;
  if (!tabId) throw new Error("Không tìm thấy tab");
  if (!data.selector) throw new Error("Thiếu data.selector");
  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: (sel, top) => {
      const el = document.querySelector(sel);
      if (!el) return { ok: false, error: `Không tìm thấy: ${sel}` };
      el.scrollTop = top;
      return { ok: true, scrollTop: el.scrollTop, scrollHeight: el.scrollHeight };
    },
    args: [data.selector, data.top ?? 999999]
  });
  return results?.[0]?.result || null;
}
async function sendToContentScript(type, data) {
  const tabId = data.tabId || (await getActiveTab())?.id;
  if (!tabId) throw new Error("Không tìm thấy active tab");
  const response = await chrome.tabs.sendMessage(tabId, { type, data });
  return { tabId, response };
}

// ── Khởi động ─────────────────────────────────────────────────────────────────
chrome.runtime.onInstalled.addListener(() => { log("Installed"); initSession(); });
chrome.runtime.onStartup.addListener(() => { log("Startup"); initSession(); });
initSession();
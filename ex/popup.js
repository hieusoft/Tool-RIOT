const logEl     = document.getElementById("log");
const sessionEl = document.getElementById("session-id");
const statusEl  = document.getElementById("status-badge");
const wsDot     = document.getElementById("ws-dot");

function addLog(msg, cls = "") {
  const line = document.createElement("div");
  line.className = cls;
  line.textContent = new Date().toLocaleTimeString("vi-VN") + " " + msg;
  logEl.appendChild(line);
  logEl.scrollTop = logEl.scrollHeight;
}

function setStatus(label, cls) {
  statusEl.textContent = label;
  statusEl.className = "badge " + cls;
}

// Lấy trạng thái hiện tại từ background
chrome.runtime.sendMessage({ type: "get_state" }, (res) => {
  if (chrome.runtime.lastError) {
    addLog("Loi ket noi background", "err");
    return;
  }
  const { sessionId, wsConnected, registered } = res || {};

  sessionEl.textContent = sessionId ? sessionId.substring(0, 24) + "…" : "Chua khoi tao";

  if (wsConnected) {
    wsDot.className = "dot online";
    addLog("WS dang ket noi", "info");
  } else {
    wsDot.className = "dot offline";
    addLog("WS chua ket noi", "err");
  }

  if (registered) {
    setStatus("Da ket noi", "ready");
    addLog("Da tu dong ket noi voi server", "ok");
  } else if (wsConnected) {
    setStatus("Dang ket noi...", "running");
  } else {
    setStatus("Cho ket noi", "idle");
  }
});

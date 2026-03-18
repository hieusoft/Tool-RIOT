const logEl    = document.getElementById("log");
const btnReady  = document.getElementById("btn-ready");
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
    addLog("Lỗi kết nối background", "err");
    return;
  }
  const { sessionId, wsConnected, registered } = res || {};

  sessionEl.textContent = sessionId ? sessionId.substring(0, 20) + "…" : "Chưa khởi tạo";

  if (wsConnected) {
    wsDot.className = "dot";
    addLog("WS đang kết nối", "info");
  } else {
    wsDot.className = "dot offline";
    addLog("WS chưa kết nối", "err");
  }

  if (registered) {
    setStatus("Đã đăng ký ✓", "ready");
    btnReady.disabled = true;
    btnReady.textContent = "✅ Đã sẵn sàng";
    addLog("Đã đăng ký với server", "ok");
  } else {
    setStatus("Chờ", "idle");
  }
});

// Nút Sẵn sàng
btnReady.addEventListener("click", () => {
  btnReady.disabled = true;
  btnReady.textContent = "⏳ Đang đăng ký...";
  setStatus("Đang kết nối...", "running");
  addLog("Gửi lệnh sẵn sàng...", "info");

  chrome.runtime.sendMessage({ type: "register_now" }, (res) => {
    if (chrome.runtime.lastError || !res?.ok) {
      addLog("Thất bại: " + (res?.error || chrome.runtime.lastError?.message), "err");
      setStatus("Lỗi", "error");
      btnReady.disabled = false;
      btnReady.textContent = "⚡ Sẵn sàng";
      return;
    }
    setStatus("Đã đăng ký ✓", "ready");
    btnReady.textContent = "✅ Đã sẵn sàng";
    addLog("Đăng ký thành công!", "ok");
  });
});

const logEl     = document.getElementById("log");
const btnReady  = document.getElementById("btn-ready");
const sessionEl = document.getElementById("session-id");
const statusEl  = document.getElementById("status-badge");
const wsDot     = document.getElementById("ws-dot");
const modeEl    = document.getElementById("mode-select");

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

// Khôi phục mode đã chọn từ storage
chrome.storage.local.get(["selectedMode"], (res) => {
  if (res.selectedMode) modeEl.value = res.selectedMode;
});

modeEl.addEventListener("change", () => {
  const newMode = modeEl.value;
  chrome.storage.local.set({ selectedMode: newMode });

  // Reset UI về trạng thái chờ để đăng ký lại với mode mới
  setStatus("Cho", "idle");
  btnReady.disabled = false;
  btnReady.textContent = "San sang";
  btnReady.classList.remove("active");

  // Thông báo background huỷ đăng ký cũ
  chrome.runtime.sendMessage({ type: "unregister" });
});

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
    setStatus("Da dang ky", "ready");
    btnReady.disabled = true;
    btnReady.textContent = "Da san sang";
    btnReady.classList.add("active");
    addLog("Da dang ky voi server", "ok");
  } else {
    setStatus("Cho", "idle");
  }
});

// Nút Sẵn sàng
btnReady.addEventListener("click", () => {
  const mode = modeEl.value;
  btnReady.disabled = true;
  btnReady.textContent = "Dang dang ky...";
  setStatus("Dang ket noi...", "running");
  addLog("Gui lenh san sang (mode=" + mode + ")...", "info");

  chrome.runtime.sendMessage({ type: "register_now", mode }, (res) => {
    if (chrome.runtime.lastError || !res?.ok) {
      addLog("That bai: " + (res?.error || chrome.runtime.lastError?.message), "err");
      setStatus("Loi", "error");
      btnReady.disabled = false;
      btnReady.textContent = "San sang";
      btnReady.classList.remove("active");
      return;
    }
    setStatus("Da dang ky", "ready");
    btnReady.textContent = "Da san sang";
    btnReady.classList.add("active");
    addLog("Dang ky thanh cong! mode=" + mode, "ok");
  });
});

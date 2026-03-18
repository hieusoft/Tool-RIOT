function qs(selector) {
  return document.querySelector(selector);
}

// Helper: delay ngẫu nhiên
function randomDelay(min, max) {
  return new Promise(r => setTimeout(r, Math.random() * (max - min) + min));
}

// Gõ từng ký tự mô phỏng người thật
async function typeText(el, text) {
  el.focus();
  el.click();
  await randomDelay(80, 200); // dừng chút sau khi click vào field

  for (const char of text) {
    const opts = { key: char, char, bubbles: true, cancelable: true };

    el.dispatchEvent(new KeyboardEvent("keydown",  opts));
    el.dispatchEvent(new KeyboardEvent("keypress", opts));

    // Thêm ký tự vào value
    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype, "value"
    )?.set;
    if (nativeInputValueSetter) {
      nativeInputValueSetter.call(el, el.value + char);
    } else {
      el.value += char;
    }

    el.dispatchEvent(new Event("input",  { bubbles: true }));
    el.dispatchEvent(new KeyboardEvent("keyup", opts));

    // Delay ngẫu nhiên giữa mỗi lần gõ: 40–130ms, thỉnh thoảng dừng dài hơn
    const pause = Math.random() < 0.1
      ? Math.random() * 300 + 200  // 10% chance: dừng dài 200–500ms
      : Math.random() * 90  + 40;  // 90% chance: bình thường 40–130ms
    await randomDelay(pause, pause + 10);
  }

  el.dispatchEvent(new Event("change", { bubbles: true }));
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const { type, data } = message || {};

  // Xử lý bất đồng bộ
  (async () => {
    try {
      if (type === "click") {
        const el = qs(data.selector);
        if (!el) {
          sendResponse({ ok: false, error: `Không tìm thấy element: ${data.selector}` });
          return;
        }
        await randomDelay(60, 180); // dừng chút trước khi click
        el.click();
        sendResponse({ ok: true, clicked: data.selector });
        return;
      }

      if (type === "fill") {
        const el = qs(data.selector);
        if (!el) {
          sendResponse({ ok: false, error: `Không tìm thấy element: ${data.selector}` });
          return;
        }
        el.focus();
        el.value = data.value ?? "";
        el.dispatchEvent(new Event("input",  { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
        sendResponse({ ok: true, filled: data.selector, value: data.value ?? "" });
        return;
      }

      if (type === "type_text") {
        const el = qs(data.selector);
        if (!el) {
          sendResponse({ ok: false, error: `Không tìm thấy element: ${data.selector}` });
          return;
        }
        await typeText(el, data.value ?? "");
        sendResponse({ ok: true, typed: data.selector, value: data.value ?? "" });
        return;
      }

      sendResponse({ ok: false, error: "Message type không hỗ trợ" });
    } catch (error) {
      sendResponse({ ok: false, error: String(error) });
    }
  })();

  return true; // giữ sendResponse alive cho async
});
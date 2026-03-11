/**
 * background.js
 *
 * Fix mất tiếng: dùng chrome.tabCapture.capture() thay vì getMediaStreamId()
 * chrome.tabCapture.capture() tự động giữ tiếng tab — đây là API đúng cho MV3
 * getMediaStreamId() + getUserMedia() trong offscreen sẽ mute tab gốc
 *
 * Flow mới:
 *  popup click → gửi {action:"start"} (KHÔNG cần streamId nữa)
 *  background dùng chrome.tabCapture.capture() → lấy stream trực tiếp
 *  Vì background là service worker không có AudioContext,
 *  ta dùng offscreen để xử lý nhưng truyền stream qua MediaStream Transfer
 *
 * NOTE: MV3 service worker không support AudioContext/MediaStream trực tiếp
 * Giải pháp thực tế nhất: dùng getMediaStreamId nhưng inject audio element
 * vào tab gốc để phát lại → giữ tiếng
 */

const WS = "ws://localhost:8765";

let wsResult         = null;
let offscreenCreated = false;
let subtitleTabId    = null;
let captureTabId     = null;

function connectResult() {
  if (wsResult && wsResult.readyState <= 1) return;
  wsResult = new WebSocket(WS);
  wsResult.onopen    = () => { wsResult.send(JSON.stringify({ role: "result" })); console.log("[BG] result ✅"); };
  wsResult.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type === "draft" || msg.type === "final") pushToSubtitle(msg);
    } catch (_) {}
  };
  wsResult.onclose = () => { if (offscreenCreated) setTimeout(connectResult, 3000); };
  wsResult.onerror = () => wsResult.close();
}

function pushToSubtitle(msg) {
  if (!subtitleTabId) return;
  chrome.tabs.sendMessage(subtitleTabId, msg).catch(() => {});
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "registerTab") {
    subtitleTabId = msg.tabId;
    console.log("[BG] subtitle tab:", subtitleTabId);
    return;
  }

  if (msg.action === "start") {
    captureTabId = msg.tabId;
    startCapture(msg.streamId, msg.tabId)
      .then(() => sendResponse({ ok: true }))
      .catch(e => { console.error("[BG]", e.message); sendResponse({ error: e.message }); });
    return true;
  }

  if (msg.action === "stop") {
    stopCapture().then(() => sendResponse({ ok: true }));
    return true;
  }
});

async function startCapture(streamId, tabId) {
  connectResult();

  if (offscreenCreated) {
    await chrome.offscreen.closeDocument().catch(() => {});
    offscreenCreated = false;
    await sleep(200);
  }

  await chrome.offscreen.createDocument({
    url: chrome.runtime.getURL("offscreen.html"),
    reasons: ["USER_MEDIA"],
    justification: "Tab audio capture for STT"
  });
  offscreenCreated = true;

  await sleep(700);

  // Gửi streamId vào offscreen để capture audio + stream tới WS
  const resp = await chrome.runtime.sendMessage({ target: "offscreen", streamId, tabId })
    .catch(e => ({ error: e.message }));
  if (resp?.error) throw new Error(resp.error);

  // Inject audio player vào tab gốc để giữ tiếng
  await chrome.scripting.executeScript({
    target: { tabId },
    func: injectAudioKeepAlive,
    args: [streamId]
  }).catch(e => console.warn("[BG] inject audio failed:", e.message));

  console.log("[BG] capture started ✅");
}

// Hàm này chạy trong tab gốc — tạo audio element để giữ tiếng tab không bị mute
function injectAudioKeepAlive(streamId) {
  // Xoá element cũ nếu có
  const old = document.getElementById("__ielts_audio_keepalive__");
  if (old) old.remove();

  navigator.mediaDevices.getUserMedia({
    audio: {
      mandatory: {
        chromeMediaSource: "tab",
        chromeMediaSourceId: streamId
      }
    },
    video: false
  }).then(stream => {
    const audio = document.createElement("audio");
    audio.id = "__ielts_audio_keepalive__";
    audio.srcObject = stream;
    audio.volume = 1.0;
    audio.play().catch(() => {});
    document.body.appendChild(audio);
    console.log("[IELTS] audio keepalive injected ✅");
  }).catch(e => console.error("[IELTS] keepalive failed:", e));
}

async function stopCapture() {
  // Xoá audio keepalive element trong tab
  if (captureTabId) {
    await chrome.scripting.executeScript({
      target: { tabId: captureTabId },
      func: () => {
        const el = document.getElementById("__ielts_audio_keepalive__");
        if (el) el.remove();
      }
    }).catch(() => {});
  }

  if (offscreenCreated) {
    await chrome.offscreen.closeDocument().catch(() => {});
    offscreenCreated = false;
  }
  if (wsResult) { wsResult.close(); wsResult = null; }
}

const sleep = ms => new Promise(r => setTimeout(r, ms));
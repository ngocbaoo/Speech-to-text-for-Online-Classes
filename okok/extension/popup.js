const btnWindow  = document.getElementById("btnWindow");
const btnStart   = document.getElementById("btnStart");
const btnStop    = document.getElementById("btnStop");
const statusDot  = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");

function setStatus(s) {
  statusDot.className  = "status-dot"  + (s === "active" ? " active" : s === "error" ? " error" : "");
  statusText.className = "status-text" + (s === "active" ? " active" : s === "error" ? " error" : "");
  statusText.textContent = { idle:"IDLE", active:"CAPTURING", error:"ERROR" }[s] || "IDLE";
}

btnWindow.onclick = () => {
  chrome.windows.create({
    url: chrome.runtime.getURL("subtitle.html"),
    type: "popup", width: 700, height: 220
  });
};

btnStart.onclick = async () => {
  btnStart.disabled = true;
  setStatus("active");
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) throw new Error("Không tìm thấy tab");

    // getMediaStreamId PHẢI gọi trong click handler
    const streamId = await new Promise((resolve, reject) => {
      chrome.tabCapture.getMediaStreamId({ targetTabId: tab.id }, id => {
        chrome.runtime.lastError
          ? reject(new Error(chrome.runtime.lastError.message))
          : resolve(id);
      });
    });

    // Gửi cả streamId lẫn tabId để background inject keepalive
    chrome.runtime.sendMessage({ action: "start", streamId, tabId: tab.id }, resp => {
      if (chrome.runtime.lastError || resp?.error) {
        console.error("[Popup]", resp?.error || chrome.runtime.lastError?.message);
        setStatus("error"); btnStart.disabled = false; btnStop.disabled = true;
      } else {
        btnStop.disabled = false;
      }
    });
  } catch (e) {
    console.error("[Popup]", e.message);
    setStatus("error"); btnStart.disabled = false;
  }
};

btnStop.onclick = () => {
  btnStop.disabled = true; btnStart.disabled = false;
  setStatus("idle");
  chrome.runtime.sendMessage({ action: "stop" });
};
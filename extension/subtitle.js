const scrollArea = document.getElementById("scroll-area");
const finalDiv   = document.getElementById("final-text");
const draftDiv   = document.getElementById("draft-text");
let initialized  = false;

chrome.tabs.getCurrent(tab => {
  if (tab) {
    chrome.runtime.sendMessage({ action: "registerTab", tabId: tab.id });
  }
});

function appendFinal(text) {
  if (!initialized) {
    finalDiv.innerHTML = "";
    initialized = true;
  }

  // Mỗi câu final = 1 block <div> riêng → tránh dính chữ hoàn toàn
  const div = document.createElement("div");
  div.style.cssText = "display:inline; margin-right:6px;";

  text.trim().split(" ").forEach((word, i) => {
    const span = document.createElement("span");
    span.className   = "word";
    // Luôn có space trước mỗi từ
    span.textContent = " " + word;
    span.style.animationDelay = `${i * 30}ms`;
    div.appendChild(span);
  });

  finalDiv.appendChild(div);

  // Giữ max ~400 spans để không lag
  const allWords = finalDiv.querySelectorAll(".word");
  if (allWords.length > 400) {
    // Xoá div đầu tiên (câu cũ nhất)
    if (finalDiv.firstChild) finalDiv.removeChild(finalDiv.firstChild);
  }

  scrollArea.scrollTop = scrollArea.scrollHeight;
  draftDiv.textContent = "";
}

function setDraft(text) {
  draftDiv.textContent = text ? "… " + text : "";
}

chrome.runtime.onMessage.addListener(msg => {
  if (!msg?.text?.trim()) return;
  if (msg.type === "final") appendFinal(msg.text.trim());
  if (msg.type === "draft") setDraft(msg.text.trim());
});
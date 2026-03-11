/**
 * offscreen.js
 * Capture audio → convert PCM → gửi WS
 * FIX: không mute audio tab nữa
 */

const WS          = "ws://localhost:8765";
const SAMPLE_RATE = 16000;
const BUFFER_SIZE = 512;

let ws = null, ctx = null, proc = null, src = null, stream = null;

console.log("[OS] loaded ✅");

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.target !== "offscreen") return false;

  start(msg.streamId)
    .then(() => sendResponse({ ok: true }))
    .catch(e => {
      console.error("[OS]", e.message);
      sendResponse({ error: e.message });
    });

  return true;
});

async function start(streamId) {

  stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      mandatory: {
        chromeMediaSource: "tab",
        chromeMediaSourceId: streamId
      }
    },
    video: false
  });

  console.log("[OS] getUserMedia ✅");

  await new Promise((resolve, reject) => {

    ws = new WebSocket(WS);

    ws.onopen = () => {

      ws.send(JSON.stringify({ role: "audio" }));
      console.log("[OS] WS → role:audio ✅");

      ctx  = new AudioContext({ sampleRate: SAMPLE_RATE });

      src  = ctx.createMediaStreamSource(stream);
      proc = ctx.createScriptProcessor(BUFFER_SIZE, 1, 1);

      /**
       * FIX QUAN TRỌNG
       * split audio ra 2 nhánh:
       * 1 → loa
       * 2 → processor → websocket
       */

      // nhánh phát ra loa (giữ tiếng tab)
      src.connect(ctx.destination);

      // nhánh xử lý STT
      src.connect(proc);
      proc.connect(ctx.destination);

      proc.onaudioprocess = (e) => {
        if (!ws || ws.readyState !== WebSocket.OPEN) return;

        ws.send(
          f32ToI16(
            e.inputBuffer.getChannelData(0)
          )
        );
      };

      console.log("[OS] pipeline ✅");

      resolve();
    };

    ws.onerror = () => reject(new Error("WS failed"));
    ws.onclose = () => console.log("[OS] WS closed");

    setTimeout(
      () => reject(new Error("WS timeout")),
      6000
    );
  });
}

function f32ToI16(f32) {

  const buf  = new ArrayBuffer(f32.length * 2);
  const view = new DataView(buf);

  for (let i = 0; i < f32.length; i++) {

    const s = Math.max(-1, Math.min(1, f32[i]));

    view.setInt16(
      i * 2,
      s < 0 ? s * 0x8000 : s * 0x7FFF,
      true
    );
  }

  return buf;
}
# IELTS Live Transcript — Full System

Real-time bilingual (VI/EN) speech-to-text for online IELTS classes.  
Architecture: **Chrome Extension** → WebSocket → **Python AI Backend** (Whisper tiny + large-v3)

```
Browser Tab (YouTube / Google Meet / Zoom)
        │  Tab Audio (PCM 16kHz)
        ▼
Chrome Extension (background.js)
        │  WebSocket  ws://localhost:8765
        ▼
Python Backend (server.py)
   ├── VADProcessor  (WebRTC + Silero)
   ├── STTEngine Draft   → Whisper tiny   → "draft" text
   └── STTEngine Verify  → Whisper large-v3 → "final" text
        │  WebSocket push
        ▼
Chrome Extension (overlay.js)
   └── Floating panel on the tab page
```

---

## 1. Backend setup

### Install dependencies
```bash
# 1. Torch với CUDA 12.1 (phải dùng --index-url riêng)
pip install torch==2.5.1+cu121 torchaudio==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121

# 2. Các thư viện còn lại
pip install faster-whisper>=1.0.0 webrtcvad==2.0.10 numpy scipy websockets>=12.0
```

> ⚠️ **Lưu ý:** `torch` CUDA **không thể** cài qua `pip install -r requirements.txt` thông thường vì cần `--index-url` đặc biệt. Phải chạy 2 lệnh riêng như trên.  
> `pyaudiowpatch` không còn cần thiết — audio giờ đến từ trình duyệt.

### Start the server
```bash
cd backend
python server.py
```

You should see:
```
🚀  STT WebSocket server  →  ws://localhost:8765
Loading AI models …
✅  All models loaded
Waiting for Chrome extension …
```

---

## 2. Chrome Extension setup

1. Open Chrome → `chrome://extensions`
2. Enable **Developer mode** (top-right toggle)
3. Click **Load unpacked**
4. Select the `extension/` folder
5. The 🎓 icon appears in the toolbar

---

## 3. Usage

1. Start the Python backend first
2. Open YouTube / Google Meet / Zoom in Chrome
3. Click the 🎓 extension icon
4. Click **"Bắt đầu ghi âm"**
5. A floating panel appears on the page showing real-time transcript
6. **Draft text** (yellow, italic) = Whisper tiny preview
7. **Final text** (white) = Whisper large-v3 confirmed sentence
8. Click 💾 to save transcript as `.txt`
9. Drag the panel to reposition it anywhere on screen

---

## 4. Configuration

Edit `backend/config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `WS_HOST` | `localhost` | WebSocket bind address |
| `WS_PORT` | `8765` | WebSocket port |
| `DRAFT_MODEL_PATH` | `tiny` | Fast preview model |
| `VERIFY_MODEL_PATH` | `large-v3` | Accurate final model |
| `WEBRTC_SENSITIVITY` | `3` | VAD aggressiveness (0-3) |
| `SILENCE_THRESHOLD_MS` | `400` | Pause to trigger sentence boundary |
| `SILERO_CONFIDENCE_THRESHOLD` | `0.5` | Min voice confidence |

---

## 5. File structure

```
stt-system/
├── backend/
│   ├── server.py          ← NEW: WebSocket server (replaces main.py)
│   ├── config.py          ← Updated: added WS_HOST, WS_PORT
│   ├── requirements.txt   ← Updated: added websockets, removed pyaudiowpatch
│   └── core/
│       ├── __init__.py
│       ├── stt_engine.py  ← unchanged logic
│       └── vad_processor.py ← unchanged logic
└── extension/
    ├── manifest.json
    ├── background.js      ← Tab audio capture + WS relay
    ├── overlay.js         ← Floating transcript panel (injected into tab)
    ├── popup.html         ← Extension popup UI
    ├── popup.js           ← Popup logic + stats
    └── icons/
        ├── icon16.png
        ├── icon48.png
        └── icon128.png
```

---

## 6. How it works

### Audio pipeline
1. Extension uses `chrome.tabCapture` API to grab audio from the active tab
2. `AudioContext` + `ScriptProcessor` node resamples to **16 kHz mono PCM Int16**
3. Chunks sent as binary WebSocket frames every **30ms**

### AI pipeline  
1. `VADProcessor` runs **WebRTC VAD** on every 30ms chunk (fast gate)
2. Every **~1.5s** of voiced audio → sent to **Whisper tiny** for draft preview
3. On silence → full segment sent to **Whisper large-v3** for final confirmation
4. Results pushed back to extension via second WebSocket connection

### Two-socket protocol
- Extension opens **two** connections to the same server:
  - `role: "audio"` — sends PCM bytes
  - `role: "result"` — receives JSON transcript events
- Server `router()` reads the first JSON message to decide the role
"""
server.py — WebSocket STT server
Protocol:
  Client gửi JSON {"role":"audio"|"result"} làm message đầu tiên.
  - role "audio"  : gửi tiếp PCM Int16 binary @ 16kHz
  - role "result" : chỉ nhận JSON {"type":"draft"|"final","text":"..."}
"""
import asyncio, json, queue, logging, threading
import websockets
from vad_processor import VADProcessor
from stt_engine    import STTEngine
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("Server")

audio_q  = queue.Queue(maxsize=300)
draft_q  = queue.Queue(maxsize=5)
verify_q = queue.Queue(maxsize=20)
clients  = set()   # result WebSocket connections
loop_ref = None

# 480 samples × 2 bytes = 960 bytes per 30ms frame (WebRTC VAD requirement)
VAD_FRAME = config.CHUNK_SIZE * 2

# ── Callbacks từ STT threads → asyncio loop ───────────────────────────────
def cb_draft(text: str):
    if loop_ref:
        asyncio.run_coroutine_threadsafe(
            broadcast({"type": "draft", "text": text}), loop_ref)

def cb_final(text: str):
    if text and loop_ref:
        asyncio.run_coroutine_threadsafe(
            broadcast({"type": "final", "text": text}), loop_ref)

async def broadcast(payload: dict):
    if not clients: return
    msg  = json.dumps(payload, ensure_ascii=False)
    dead = set()
    for ws in list(clients):
        try:    await ws.send(msg)
        except: dead.add(ws)
    clients.difference_update(dead)

# ── WebSocket handlers ────────────────────────────────────────────────────
async def handle_audio(ws):
    log.info(f"🎙  Audio connected   {ws.remote_address}")
    frames = 0
    buf    = b""
    try:
        async for msg in ws:
            if not isinstance(msg, bytes):
                continue
            buf += msg
            # Tích lũy rồi chia đúng VAD_FRAME để tránh lỗi WebRTC VAD
            while len(buf) >= VAD_FRAME:
                if not audio_q.full():
                    audio_q.put_nowait(buf[:VAD_FRAME])
                buf    = buf[VAD_FRAME:]
                frames += 1
            if frames > 0 and frames % 200 == 0:
                log.info(f"🎙  frames={frames}  queue={audio_q.qsize()}")
    except websockets.ConnectionClosed:
        pass
    log.info(f"🎙  Audio disconnected (frames={frames})")

async def handle_result(ws):
    log.info(f"📺  Result connected  {ws.remote_address}")
    clients.add(ws)
    try:
        await ws.send(json.dumps({"type": "status", "text": "connected"}))
        async for _ in ws:
            pass   # keep-alive, không cần đọc gì từ result client
    except websockets.ConnectionClosed:
        pass
    finally:
        clients.discard(ws)
        log.info("📺  Result disconnected")

async def router(ws):
    """Message JSON đầu tiên quyết định role."""
    try:
        first = await asyncio.wait_for(ws.recv(), timeout=10)
        role  = json.loads(first).get("role", "audio")
    except Exception:
        role = "audio"
    log.info(f"→  role={role}  {ws.remote_address}")
    if role == "result":
        await handle_result(ws)
    else:
        await handle_audio(ws)

# ── AI pipeline (chạy trong thread riêng) ────────────────────────────────
def start_pipeline():
    log.info("Loading AI models…")
    eng = STTEngine(draft_q, verify_q, cb_draft, cb_final)
    eng.load_models()
    eng.start()
    vad = VADProcessor(audio_q, draft_q, verify_q)
    vad.start()
    log.info("✅  Pipeline ready — chờ audio từ extension")

async def main():
    global loop_ref
    loop_ref = asyncio.get_running_loop()
    threading.Thread(target=start_pipeline, daemon=True).start()
    async with websockets.serve(router, config.WS_HOST, config.WS_PORT,
                                max_size=10 * 1024 * 1024):
        log.info(f"🚀  ws://{config.WS_HOST}:{config.WS_PORT}")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
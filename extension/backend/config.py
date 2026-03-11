# ── Model paths ───────────────────────────────────────────────────────────────
# Uncomment to use fine-tuned Vietnamese models:
# DRAFT_MODEL_PATH  = "mad1999/pho-whisper-tiny-ct2"
# VERIFY_MODEL_PATH = "mad1999/pho-whisper-large-ct2"

DRAFT_MODEL_PATH  = "tiny"
VERIFY_MODEL_PATH = "large-v3"

# ── Audio ─────────────────────────────────────────────────────────────────────
SAMPLE_RATE       = 16000
CHUNK_DURATION_MS = 30
CHUNK_SIZE        = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)

# ── VAD ───────────────────────────────────────────────────────────────────────
WEBRTC_SENSITIVITY         = 3
SILENCE_THRESHOLD_MS       = 400
SILERO_CONFIDENCE_THRESHOLD = 0.5

# ── UI (legacy terminal mode) ─────────────────────────────────────────────────
MAX_SENTENCES = 3

# ── WebSocket server ──────────────────────────────────────────────────────────
WS_HOST = "localhost"
WS_PORT = 8765
import time
import sys
import queue
import logging
import config
from core.audio_capture import AudioCapture
from core.vad_processor import VADProcessor
from core.stt_engine import STTEngine

logging.basicConfig(level=logging.WARNING, format="%(message)s")
logging.getLogger("faster_whisper").setLevel(logging.ERROR)

class STTOrchestrator:
    def __init__(self):
        # 1. Khởi tạo đường ống
        self.audio_queue = queue.Queue(maxsize=100)
        self.draft_queue = queue.Queue(maxsize=5)
        self.verify_queue = queue.Queue(maxsize=20)
        
        # 2. Trạng thái UI
        self.confirmed_sentences = []
        self.full_transcript = []
        
        # 3. Khởi tạo các Modules
        self.audio_module = AudioCapture(self.audio_queue)
        self.vad_module = VADProcessor(self.audio_queue, self.draft_queue, self.verify_queue)
        self.stt_module = STTEngine(
            self.draft_queue, self.verify_queue, 
            self.on_realtime_update, self.on_transcription_final
        )

    def refresh_display(self, draft_text=""):
        final_paragraph = " ".join(self.confirmed_sentences)
        display_text = f"\r\033[K\033[92m{final_paragraph}\033[0m \033[93m{draft_text}\033[0m"
        sys.stdout.write(display_text)
        sys.stdout.flush()

    def on_realtime_update(self, text):
        self.refresh_display(draft_text=f"...({text})")

    def on_transcription_final(self, text):
        if text:
            self.confirmed_sentences.append(text)
            self.full_transcript.append(text)
            if len(self.confirmed_sentences) > config.MAX_SENTENCES:
                self.confirmed_sentences.pop(0)
        self.refresh_display()

    def start(self):
        print(">>> Đang nạp hệ thống STT Đa Luồng...")
        self.stt_module.load_models()
        self.stt_module.start()
        self.vad_module.start()
        self.audio_module.start()
        print("\nSẵn sàng! Hệ thống đang tự động thu âm...")

    def stop(self):
        print("\n\n>>> Đang tắt hệ thống STT...")
        self.audio_module.stop()
        self.vad_module.stop()
        self.stt_module.stop()
        time.sleep(1) 
        
        final_text = " ".join(self.full_transcript)
        
        print("\n" + "="*60)
        print("KẾT QUẢ TOÀN BỘ BUỔI HỌC:")
        print("="*60)
        print(final_text)
        print("="*60)
        
        # Tự động lưu ra file text
        if final_text.strip():
            filename = f"transcript_output_{int(time.time())}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(final_text)
            print(f"Đã lưu nội dung vào file: {filename}\n")

if __name__ == "__main__":
    app = STTOrchestrator()
    app.start()
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        app.stop()
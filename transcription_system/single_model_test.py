import time
import sys
import os
import queue
import logging
import jiwer 
from faster_whisper import WhisperModel
import config

from core.audio_capture import AudioCapture
from core.vad_processor import VADProcessor

logging.basicConfig(level=logging.WARNING, format="%(message)s")
logging.getLogger("faster_whisper").setLevel(logging.ERROR)

GROUND_TRUTH_FILE = "transcription_system/ground_truth_transcript.txt"

class SingleModelTester:
    def __init__(self):
        self.audio_queue = queue.Queue(maxsize=100)
        self.draft_queue = queue.Queue(maxsize=5) 
        self.verify_queue = queue.Queue(maxsize=20)
        
        self.audio_module = AudioCapture(self.audio_queue)
        self.vad_module = VADProcessor(self.audio_queue, self.draft_queue, self.verify_queue)
        
        self.model = None
        self.is_running = False
        
        # UI State
        self.confirmed_sentences = []
        
        # Túi chứa toàn bộ văn bản để cuối giờ mang ra chấm điểm
        self.full_transcript = [] 

    def load_model(self):
        print(">>> Đang nạp Model Large v3")
        self.model = WhisperModel(config.VERIFY_MODEL_PATH, device="cuda", compute_type="int8")

    def _clean_hallucinations(self, text):
        if not text: return ""
        blacklisted_phrases = [
            "Hãy subscribe cho kênh La La School", "Để không bỏ lỡ những video hấp dẫn",
            "Cảm ơn các bạn đã theo dõi", "Hẹn gặp lại các bạn"
        ]
        import re
        for phrase in blacklisted_phrases:
            text = re.sub(phrase, '', text, flags=re.IGNORECASE)
        return text.strip()

    def _worker(self):
        while self.is_running:
            # Dọn rác draft_queue
            try: 
                while not self.draft_queue.empty():
                    self.draft_queue.get_nowait()
            except: pass

            try: 
                audio_np = self.verify_queue.get(timeout=0.1)
            except queue.Empty: 
                continue
            
            try:
                start_time = time.time()
                
                segments, info = self.model.transcribe(
                    audio_np, 
                    beam_size=5, 
                    condition_on_previous_text=False,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500),
                    no_speech_threshold=0.7,
                    compression_ratio_threshold=2.4,
                    log_prob_threshold=-1.0 
                )
                
                full_text = " ".join([s.text for s in segments]).strip()
                full_text = self._clean_hallucinations(full_text)
                
                process_time = time.time() - start_time
                audio_duration = len(audio_np) / config.SAMPLE_RATE
                rtf = process_time / audio_duration if audio_duration > 0 else 0
                
                if full_text:
                    self.confirmed_sentences.append(full_text)
                    self.full_transcript.append(full_text)                   
                    if len(self.confirmed_sentences) > config.MAX_SENTENCES:
                        self.confirmed_sentences.pop(0)
                        
                    os.system('cls' if os.name == 'nt' else 'clear')
                    final_paragraph = " ".join(self.confirmed_sentences)
                    
                    print(f"\033[92m{final_paragraph}\033[0m\n")
                    print(f"[METRICS] Audio dài: {audio_duration:.2f}s | Chờ Large dịch: {process_time:.2f}s | RTF: {rtf:.3f}")
                    
            except Exception as e:
                print(f"\nLỖI CRASH: {e}")

    def start(self):
        self.load_model()
        self.is_running = True
        import threading
        threading.Thread(target=self._worker, daemon=True).start()
        self.vad_module.start()
        self.audio_module.start()
        print(">>> Sẵn sàng! Đang thu âm từ hệ thống WASAPI...")

    def evaluate_wer(self):
        final_text = " ".join(self.full_transcript).strip()
        if not final_text:
            print("\n Chưa thu được chữ nào từ Audio, không thể chấm điểm WER!")
            return

        try:
            with open(GROUND_TRUTH_FILE, "r", encoding="utf-8") as f:
                ground_truth_text = f.read().strip()
                
            if not ground_truth_text:
                print(f"\nFile {GROUND_TRUTH_FILE} đang bị trống. Hãy điền kịch bản vào nhé!")
                return
        except FileNotFoundError:
            print(f"\nKhông tìm thấy file '{GROUND_TRUTH_FILE}'. Bạn đã để đúng thư mục chưa?")
            return

        transforms = jiwer.Compose([jiwer.ToLowerCase(), jiwer.RemovePunctuation()])        
        ground_truth_clean = transforms(ground_truth_text)
        final_text_clean = transforms(final_text)
        wer_score = jiwer.wer(ground_truth_clean, final_text_clean)
        
        print("\n" + "="*60)
        print("BÁO CÁO ĐÁNH GIÁ (WER EVALUATION)")
        print("="*60)
        print(f"Gốc (File text)   : {ground_truth_text[:100]}... (đã rút gọn)")
        print(f"AI Dịch (Thực tế) : {final_text[:100]}... (đã rút gọn)")
        print("-" * 60)
        print(f"Word Error Rate (WER): {wer_score * 100:.2f}%")
        print("="*60)
    
    def stop(self):
        print("\n>>> Đang tắt hệ thống STT và tính toán điểm số...")
        self.is_running = False
        self.audio_module.stop()
        self.vad_module.stop()
        time.sleep(1) 
        
        self.evaluate_wer() 
        print(">>> Đã thoát chương trình.")

if __name__ == "__main__":
    app = SingleModelTester()
    app.start()
    
    input("\n[ĐANG THU ÂM] Khi nào video đọc xong, hãy bấm phím ENTER để kết thúc và xem điểm...\n")
    app.stop()
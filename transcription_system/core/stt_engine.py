import threading
import logging
import queue
from faster_whisper import WhisperModel
import config
import re 

logger = logging.getLogger("STTEngine")

class STTEngine:
    def __init__(self, draft_queue, verify_queue, on_realtime_update, on_transcription_final):
        self.draft_queue = draft_queue
        self.verify_queue = verify_queue
        self.on_realtime_update = on_realtime_update
        self.on_transcription_final = on_transcription_final
        
        self.draft_model = None
        self.verify_model = None
        self.prompt_context = []
        self.is_running = False

    def _clean_hallucinations(self, text):
            """Hàm dọn dẹp các câu ảo giác đặc sản của Whisper"""
            if not text:
                return ""
                
            blacklisted_phrases = [
                "Hãy subscribe cho kênh La La School",
                "Để không bỏ lỡ những video hấp dẫn",
                "Cảm ơn các bạn đã theo dõi",
                "Hẹn gặp lại các bạn",
                "hãy đăng ký kênh",
                "Chào mừng các bạn đến với",
                "Hãy subscribe cho kênh Ghiền Mì Gõ",
            ]
            
            cleaned_text = text
            for phrase in blacklisted_phrases:
                import re
                cleaned_text = re.sub(phrase, '', cleaned_text, flags=re.IGNORECASE)
                
            return cleaned_text.strip()
    def load_models(self):
        if self.verify_model is not None: return
        logger.info("Đang nạp Verify Model (Large) vào VRAM. Vui lòng đợi...")
        self.verify_model = WhisperModel(config.VERIFY_MODEL_PATH, device="cuda", compute_type="int8")
        
        logger.info("Đang nạp Draft Model (Tiny) vào VRAM...")
        self.draft_model = WhisperModel(config.DRAFT_MODEL_PATH, device="cuda", compute_type="float16")
        logger.info(">>> Đã nạp xong tất cả AI Models!")

    def start(self):
        if self.is_running: return
        self.is_running = True
        threading.Thread(target=self._draft_worker, daemon=True).start()
        threading.Thread(target=self._verify_worker, daemon=True).start()

    def stop(self):
        self.is_running = False

    def _draft_worker(self):
        while self.is_running:
            try: audio_np = self.draft_queue.get(timeout=0.1)
            except queue.Empty: continue
            
            try:
                segments, _ = self.draft_model.transcribe(
                    audio_np, beam_size=1, 
                    without_timestamps=True, 
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500),
                    condition_on_previous_text=False, 
                    no_speech_threshold=0.7,
                    compression_ratio_threshold=2.4,
                    log_prob_threshold=-1.0
                )
                text = " ".join([s.text for s in segments]).strip()
                text = self._clean_hallucinations(text)
                if text and self.on_realtime_update:
                    self.on_realtime_update(text)
            except Exception as e:
                pass

    def _verify_worker(self):
        bilingual_hint = "Cuộc hội thoại này sử dụng song ngữ Tiếng Việt và Tiếng Anh."
        while self.is_running:
            try: audio_np = self.verify_queue.get(timeout=0.1)
            except queue.Empty: continue
            
            try:
                context_str = " ".join(self.prompt_context)
                final_prompt = bilingual_hint + context_str
                
                segments, _ = self.verify_model.transcribe(
                    audio_np, 
                    beam_size=5, 
                    condition_on_previous_text=False,
                    initial_prompt=final_prompt,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500),
                    no_speech_threshold=0.7,
                    compression_ratio_threshold=2.4,
                    log_prob_threshold=-1.0
                )
                
                full_text = " ".join([s.text for s in segments]).strip()
                full_text = self._clean_hallucinations(full_text)
                
                if full_text and self.on_transcription_final:
                    self.on_transcription_final(full_text)
                    
                    # self.prompt_context.append(full_text)
                    if len(self.prompt_context) > 3:
                        self.prompt_context.pop(0)
            except Exception as e:
                logger.error(f"Lỗi Verify: {e}")
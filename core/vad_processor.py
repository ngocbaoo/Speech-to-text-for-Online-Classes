import threading
import numpy as np
import webrtcvad
import torch
import logging
import queue
import config

logger = logging.getLogger("VADProcessor")

class VADProcessor:
    def __init__(self, audio_queue, draft_queue, verify_queue):
        self.audio_queue = audio_queue
        self.draft_queue = draft_queue
        self.verify_queue = verify_queue
        self.is_running = False
        self.is_recording = False
        
        logger.info("Đang nạp bộ lọc nhiễu VAD (WebRTC + Silero)...")
        self.webrtc_vad = webrtcvad.Vad(config.WEBRTC_SENSITIVITY)
        self.silero_vad, _ = torch.hub.load(
            repo_or_dir='snakers4/silero-vad', model='silero_vad', 
            force_reload=False, onnx=False, verbose=False
        )
        self.silero_vad.eval()

    def start(self):
        if self.is_running: return
        self.is_running = True
        threading.Thread(target=self._process_loop, daemon=True).start()

    def stop(self):
        self.is_running = False

    def _process_loop(self):
        silence_counter = 0
        silence_threshold = int(config.SILENCE_THRESHOLD_MS / config.CHUNK_DURATION_MS)
        buffer_bytes = bytearray()
        draft_buffer_bytes = bytearray()
        
        while self.is_running:
            try: chunk = self.audio_queue.get(timeout=0.1)
            except queue.Empty: continue
                
            try: is_speech = self.webrtc_vad.is_speech(chunk, config.SAMPLE_RATE)
            except: is_speech = False
                
            if is_speech:
                silence_counter = 0
                if not self.is_recording:
                    self.is_recording = True
                    buffer_bytes.clear()
                    draft_buffer_bytes.clear()
            else:
                if self.is_recording:
                    silence_counter += 1
            
            if self.is_recording:
                buffer_bytes.extend(chunk)
                draft_buffer_bytes.extend(chunk)
                
                # Gửi bản nháp
                if len(draft_buffer_bytes) >= (config.SAMPLE_RATE * 2 * 1.5):
                    audio_np = np.frombuffer(draft_buffer_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                    if not self.draft_queue.full():
                        self.draft_queue.put_nowait(audio_np)
                    bytes_to_keep = int(config.SAMPLE_RATE * 2 * 0.5)
                    draft_buffer_bytes = draft_buffer_bytes[-bytes_to_keep:]
                
                # Chốt câu
                if silence_counter > silence_threshold:
                    self.is_recording = False
                    if len(buffer_bytes) > (config.SAMPLE_RATE * 2 * 0.5): 
                        audio_np = np.frombuffer(buffer_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                        
                        is_human_voice = False
                        with torch.no_grad():
                            for i in range(0, len(audio_np) - 512, 512):
                                chunk_512 = torch.from_numpy(audio_np[i:i+512])
                                confidence = self.silero_vad(chunk_512, config.SAMPLE_RATE).item()
                                
                                if confidence > config.SILERO_CONFIDENCE_THRESHOLD:
                                    is_human_voice = True
                                    break
                        
                        if is_human_voice:
                            self.verify_queue.put(audio_np)
                    buffer_bytes.clear()
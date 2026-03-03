import threading
import logging
import queue
import numpy as np
import pyaudiowpatch as pyaudio
from scipy import signal
import config

logger = logging.getLogger("AudioCapture")

class AudioCapture:
    def __init__(self, audio_queue):
        self.audio_queue = audio_queue
        self.is_running = False

    def start(self):
        if self.is_running: return
        self.is_running = True
        threading.Thread(target=self._record_loop, daemon=True).start()

    def stop(self):
        self.is_running = False

    def _record_loop(self):
        p = pyaudio.PyAudio()
        try:
            wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_speakers = p.get_default_wasapi_loopback()
            
            device_rate = int(default_speakers["defaultSampleRate"])
            channels = default_speakers["maxInputChannels"]
            
            logger.info(f"Đã cắm ống nghe vào: {default_speakers['name']}")
            logger.info(f"Tần số gốc: {device_rate}Hz | Kênh: {channels}")

            device_chunk_size = int(device_rate * config.CHUNK_DURATION_MS / 1000)

            stream = p.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=device_rate,
                input=True,
                input_device_index=default_speakers["index"],
                frames_per_buffer=device_chunk_size
            )
            
            logger.info("Bắt đầu nghe hệ thống (Zoom/Meet/YouTube)...")
            
            while self.is_running:
                try:
                    data = stream.read(device_chunk_size, exception_on_overflow=False)
                    

                    audio_data = np.frombuffer(data, dtype=np.int16)
                    
                    if channels > 1:
                        audio_data = audio_data.reshape(-1, channels).mean(axis=1).astype(np.int16)
                        
                    if device_rate != config.SAMPLE_RATE:
                        target_samples = int(len(audio_data) * config.SAMPLE_RATE / device_rate)
                        audio_data = signal.resample(audio_data, target_samples).astype(np.int16)
                        
                    processed_bytes = audio_data.tobytes()
                    
                    if self.audio_queue.full():
                        try: self.audio_queue.get_nowait()
                        except: pass
                    self.audio_queue.put_nowait(processed_bytes)
                    
                except Exception as e:
                    continue

        except Exception as e:
            logger.error(f"Lỗi thiết lập âm thanh hệ thống: {e}")
        finally:
            try: stream.stop_stream(); stream.close(); p.terminate()
            except: pass
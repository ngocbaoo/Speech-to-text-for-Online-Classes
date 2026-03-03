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
        # Sử dụng PyAudioWpatch để gọi API của Windows
        p = pyaudio.PyAudio()
        try:
            # 1. TÌM THIẾT BỊ LOA MẶC ĐỊNH
            wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_speakers = p.get_default_wasapi_loopback()
            
            # Đọc cấu hình gốc của máy bạn (Thường là 48000Hz, 2 Kênh Stereo)
            device_rate = int(default_speakers["defaultSampleRate"])
            channels = default_speakers["maxInputChannels"]
            
            logger.info(f"Đã cắm ống nghe vào: {default_speakers['name']}")
            logger.info(f"Tần số gốc: {device_rate}Hz | Kênh: {channels}")

            # Tính toán lượng âm thanh cần múc mỗi lần (30ms) theo tần số gốc
            device_chunk_size = int(device_rate * config.CHUNK_DURATION_MS / 1000)

            # 2. MỞ LUỒNG THU ÂM HỆ THỐNG
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
                    # Đọc dữ liệu từ Loa
                    data = stream.read(device_chunk_size, exception_on_overflow=False)
                    
                    # 3. TIỀN XỬ LÝ ÂM THANH (Cực kỳ quan trọng)
                    # Chuyển dữ liệu thô thành mảng toán học
                    audio_data = np.frombuffer(data, dtype=np.int16)
                    
                    # Nếu là âm thanh nổi (Stereo 2 kênh), trộn lại thành âm thanh đơn (Mono 1 kênh)
                    if channels > 1:
                        audio_data = audio_data.reshape(-1, channels).mean(axis=1).astype(np.int16)
                        
                    # Hạ tần số (Resample) từ tần số máy tính (VD: 48000Hz) về tần số AI (16000Hz)
                    if device_rate != config.SAMPLE_RATE:
                        target_samples = int(len(audio_data) * config.SAMPLE_RATE / device_rate)
                        audio_data = signal.resample(audio_data, target_samples).astype(np.int16)
                        
                    # 4. ÉP LẠI THÀNH DỮ LIỆU THÔ VÀ GỬI ĐI
                    processed_bytes = audio_data.tobytes()
                    
                    if self.audio_queue.full():
                        try: self.audio_queue.get_nowait()
                        except: pass
                    self.audio_queue.put_nowait(processed_bytes)
                    
                except Exception as e:
                    # Đặc sản của Windows WASAPI: Khi không có tiếng gì phát ra, nó có thể báo lỗi.
                    # Ta bỏ qua lỗi này để vòng lặp cứ tiếp tục chờ âm thanh.
                    continue

        except Exception as e:
            logger.error(f"Lỗi thiết lập âm thanh hệ thống: {e}")
        finally:
            try: stream.stop_stream(); stream.close(); p.terminate()
            except: pass
import threading
import pyaudio
import logging
import queue
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
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=config.SAMPLE_RATE,
                            input=True, frames_per_buffer=config.CHUNK_SIZE)
            logger.info("🎤 Microphone đã mở.")
            while self.is_running:
                data = stream.read(config.CHUNK_SIZE, exception_on_overflow=False)
                if self.audio_queue.full():
                    try: self.audio_queue.get_nowait()
                    except: pass
                self.audio_queue.put_nowait(data)
        except Exception as e:
            logger.error(f"Lỗi Mic: {e}")
        finally:
            try: stream.stop_stream(); stream.close(); p.terminate()
            except: pass
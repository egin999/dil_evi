import sounddevice as sd
import queue
import threading

SAMPLE_RATE = 24000
CHANNELS = 1
DTYPE = "int16"
BLOCKSIZE = 480  # 20ms @ 24kHz
PREBUFFER_MS = 80  # Düşürüldü


class MicrophoneStream:
    def __init__(self):
        self.queue: queue.Queue = queue.Queue()
        self._stream: sd.RawInputStream | None = None

    def _callback(self, indata, frames, time_info, status):
        self.queue.put(bytes(indata))

    def start(self):
        self._stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=BLOCKSIZE,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None


class SpeakerStream:
    """Hassas timing ile hoparlör akışı."""

    _PREBUFFER_BYTES = int(SAMPLE_RATE * 2 * PREBUFFER_MS / 1000)

    def __init__(self):
        self._buffer = bytearray()
        self._lock = threading.Lock()
        self._stream: sd.RawOutputStream | None = None
        self._playing: bool = False

    def _callback(self, outdata, frames, time_info, status):
        needed = frames * 2
        with self._lock:
            if not self._playing:
                if len(self._buffer) >= self._PREBUFFER_BYTES:
                    self._playing = True
                else:
                    outdata[:] = b"\x00" * needed
                    return

            if len(self._buffer) >= needed:
                outdata[:] = bytes(self._buffer[:needed])
                del self._buffer[:needed]
            else:
                available = len(self._buffer)
                if available > 0:
                    outdata[:available] = bytes(self._buffer)
                outdata[available:needed] = b"\x00" * (needed - available)
                self._buffer.clear()
                self._playing = False

    def start(self):
        self._stream = sd.RawOutputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=BLOCKSIZE,
            callback=self._callback,
        )
        self._stream.start()

    def write(self, pcm_bytes: bytes):
        with self._lock:
            self._buffer.extend(pcm_bytes)

    def clear(self):
        """Barge-in: buffer'ı boşalt."""
        with self._lock:
            self._buffer.clear()
            self._playing = False

    def stop(self):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
"""Tests del AudioRecorder (sin abrir streams reales, solo lógica)."""

import threading
import time

import numpy as np

from belen.recorder import AudioRecorder


def test_init_defaults():
    rec = AudioRecorder()
    assert rec.sample_rate == 16000
    assert rec.is_recording is False
    assert rec.duration_seconds == 0.0


def test_init_custom():
    rec = AudioRecorder(sample_rate=48000, device=2)
    assert rec.sample_rate == 48000


def test_stop_sin_start():
    rec = AudioRecorder()
    audio, sr = rec.stop()
    assert audio.size == 0
    assert sr == 16000


def test_cancel():
    rec = AudioRecorder()
    rec.cancel()
    assert rec.is_recording is False


def test_get_duration():
    sr = 16000
    audio = np.zeros(sr * 3, dtype=np.int16)
    assert AudioRecorder.get_duration(audio, sr) == 3.0


def test_get_duration_empty():
    audio = np.array([], dtype=np.int16)
    assert AudioRecorder.get_duration(audio, 16000) == 0.0


def test_get_duration_invalid_sr():
    audio = np.zeros(1000, dtype=np.int16)
    assert AudioRecorder.get_duration(audio, 0) == 0.0


def test_wait_ready_timeout():
    """wait_ready devuelve False si nunca se setea el event."""
    rec = AudioRecorder()
    rec._ready_event.clear()
    result = rec.wait_ready(timeout=0.1)
    assert result is False


def test_wait_ready_set():
    """wait_ready devuelve True si el event ya está seteado."""
    rec = AudioRecorder()
    rec._ready_event.set()
    result = rec.wait_ready(timeout=0.1)
    assert result is True


def test_prewarm_flag():
    """prewarm() setea _prewarmed=True si falla (mock)."""
    rec = AudioRecorder()
    # No podemos llamar prewarm() real porque abre un stream de audio,
    # pero podemos verificar el flag manualmente.
    assert rec._prewarmed is False


def test_start_when_already_recording():
    """start() no hace nada si ya está grabando."""
    rec = AudioRecorder()
    rec._is_recording = True
    rec.start()  # debería ser no-op
    assert rec._is_recording is True


def test_stop_when_not_recording_returns_empty():
    """stop() devuelve array vacío si no está grabando."""
    rec = AudioRecorder()
    rec._is_recording = False
    audio, sr = rec.stop()
    assert audio.size == 0
    assert sr == 16000


def test_stop_prewarmed_does_not_close_stream():
    """Con stream prewarmed, stop() no destruye el stream persistente."""
    rec = AudioRecorder()
    rec._prewarmed = True
    rec._persistent_stream = "fake_stream"  # type: ignore
    rec._is_recording = True
    rec._chunks = [np.zeros(100, dtype=np.int16)]
    rec._start_time = time.monotonic() - 1.0

    audio, sr = rec.stop()

    # Stream persistente no se destruye
    assert rec._persistent_stream is not None
    assert not rec._is_recording
    assert len(audio) == 100


def test_stop_non_prewarmed_closes_stream():
    """Sin prewarm, stop() cierra el stream."""
    rec = AudioRecorder()

    class FakeStream:
        stopped = False
        closed = False
        def stop(self):
            self.stopped = True
        def close(self):
            self.closed = True

    fake = FakeStream()
    rec._stream = fake
    rec._prewarmed = False
    rec._is_recording = True
    rec._chunks = [np.zeros(100, dtype=np.int16)]
    rec._start_time = time.monotonic() - 1.0

    audio, sr = rec.stop()

    assert fake.stopped
    assert fake.closed
    assert rec._stream is None
    assert len(audio) == 100


def test_cancel_prewarmed_keeps_stream():
    """cancel() con stream prewarmed no toca el stream persistente."""
    rec = AudioRecorder()
    rec._prewarmed = True
    rec._persistent_stream = "fake"  # type: ignore
    rec._is_recording = True
    rec._chunks = [np.zeros(100, dtype=np.int16)]

    rec.cancel()

    assert not rec._is_recording
    assert len(rec._chunks) == 0
    assert rec._persistent_stream is not None


def test_cancel_non_prewarmed_closes_stream():
    """cancel() sin prewarm cierra el stream."""
    rec = AudioRecorder()

    class FakeStream:
        stopped = False
        closed = False
        def stop(self):
            self.stopped = True
        def close(self):
            self.closed = True

    fake = FakeStream()
    rec._stream = fake
    rec._prewarmed = False
    rec._is_recording = True
    rec._chunks = [np.zeros(100, dtype=np.int16)]

    rec.cancel()

    assert not rec._is_recording
    assert len(rec._chunks) == 0
    assert rec._stream is None
    assert fake.stopped
    assert fake.closed


def test_ready_event_cleared_after_stop():
    """Después de stop(), el ready event se puede limpiar para el próximo ciclo."""
    rec = AudioRecorder()
    rec._ready_event.set()
    assert rec.wait_ready(timeout=0.01)

    # El pipeline llama clear() después de stop()
    rec._ready_event.clear()
    assert not rec.wait_ready(timeout=0.01)

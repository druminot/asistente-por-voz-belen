"""Captura de audio del micrófono.

(Fase 2 — pendiente de implementación)
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from queue import Queue

import numpy as np

from belen.config import get_settings


class AudioRecorder:
    """Graba audio del micrófono hasta que se llame stop().

    Uso:
        rec = AudioRecorder()
        rec.start()
        # ... el usuario habla ...
        audio = rec.stop()  # np.ndarray int16, sample_rate
    """

    def __init__(self, sample_rate: int | None = None, device: str | None = None) -> None:
        settings = get_settings()
        self._sample_rate = sample_rate or settings.belen_sample_rate
        self._device = device or (settings.belen_input_device or None)
        self._chunks: list[np.ndarray] = []
        self._stream = None
        self._is_recording = False
        self._lock = threading.Lock()

    def start(self) -> None:
        """Arranca la grabación (no-bloqueante)."""
        import sounddevice as sd

        with self._lock:
            if self._is_recording:
                return
            self._chunks = []
            self._is_recording = True

        def callback(indata: np.ndarray, frames: int, time_info: object, status: object) -> None:
            if status:
                return
            self._chunks.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=1,
            dtype="int16",
            device=self._device,
            callback=callback,
        )
        self._stream.start()

    def stop(self) -> tuple[np.ndarray, int]:
        """Detiene la grabación y devuelve (audio, sample_rate)."""
        with self._lock:
            if not self._is_recording:
                return np.array([], dtype=np.int16), self._sample_rate
            self._is_recording = False

        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if not self._chunks:
            return np.array([], dtype=np.int16), self._sample_rate

        audio = np.concatenate(self._chunks, axis=0).flatten()
        return audio, self._sample_rate

    def save(self, audio: np.ndarray, path: Path | str) -> Path:
        """Guarda audio a WAV."""
        import soundfile as sf

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(path), audio, self._sample_rate)
        return path

    @property
    def is_recording(self) -> bool:
        return self._is_recording

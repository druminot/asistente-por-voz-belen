"""Captura de audio del micrófono usando sounddevice (PortAudio).

Graba audio del micrófono en streaming hasta que se llame stop().
Devuelve un numpy array int16 listo para pasar a un STT backend.

Permisos requeridos en macOS:
- System Settings → Privacy & Security → Microphone
  → Permitir acceso a la Terminal (o la app que corre Belen)
"""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np

from belen.config import get_settings


class AudioRecorder:
    """Graba audio del micrófono.

    Uso:
        rec = AudioRecorder()
        rec.start()
        # ... el usuario habla ...
        audio, sample_rate = rec.stop()  # np.ndarray int16, sample_rate

    El audio es mono, int16, sample_rate (default 16000 Hz).
    """

    def __init__(
        self,
        sample_rate: int | None = None,
        device: str | int | None = None,
        channels: int = 1,
    ) -> None:
        settings = get_settings()
        self._sample_rate = sample_rate or settings.belen_sample_rate
        self._device = device if device is not None else (settings.belen_input_device or None)
        self._channels = channels
        self._chunks: list[np.ndarray] = []
        self._stream = None
        self._is_recording = False
        self._lock = threading.Lock()
        self._duration_seconds: float = 0.0
        self._start_time: float = 0.0

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def duration_seconds(self) -> float:
        """Duración actual de la grabación en segundos (0 si no está grabando)."""
        if not self._is_recording:
            return self._duration_seconds
        import time

        return time.monotonic() - self._start_time

    def start(self) -> None:
        """Arranca la grabación (no-bloqueante)."""
        if self._is_recording:
            return
        import sounddevice as sd

        with self._lock:
            self._chunks = []
            self._is_recording = True

        import time

        self._start_time = time.monotonic()

        def callback(indata: np.ndarray, frames: int, time_info: object, status: object) -> None:
            if status:
                return
            self._chunks.append(indata.copy())

        try:
            self._stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="int16",
                device=self._device,
                callback=callback,
            )
            self._stream.start()
        except Exception as e:
            with self._lock:
                self._is_recording = False
            raise RuntimeError(
                f"No se pudo abrir el stream de audio: {e}. "
                f"Verificá permisos de Micrófono en System Settings."
            ) from e

    def stop(self) -> tuple[np.ndarray, int]:
        """Detiene la grabación y devuelve (audio, sample_rate).

        Si no se grabó nada, devuelve (array vacío, sample_rate).
        """
        with self._lock:
            if not self._is_recording:
                return np.array([], dtype=np.int16), self._sample_rate
            self._is_recording = False
            self._duration_seconds = self.duration_seconds

        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        if not self._chunks:
            return np.array([], dtype=np.int16), self._sample_rate

        audio = np.concatenate(self._chunks, axis=0).flatten()
        return audio, self._sample_rate

    def cancel(self) -> None:
        """Cancela la grabación sin devolver audio (útil para errores)."""
        with self._lock:
            self._is_recording = False
            self._chunks = []
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def save(self, audio: np.ndarray, path: Path | str) -> Path:
        """Guarda audio a WAV (para debug o re-transcripción)."""
        import soundfile as sf

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(path), audio, self._sample_rate)
        return path

    @staticmethod
    def get_duration(audio: np.ndarray, sample_rate: int) -> float:
        """Duración en segundos de un array de audio."""
        if sample_rate <= 0:
            return 0.0
        return len(audio) / sample_rate

    @staticmethod
    def list_input_devices() -> list[dict[str, object]]:
        """Lista los dispositivos de entrada disponibles."""
        import sounddevice as sd

        devices = sd.query_devices()
        return [
            {"index": i, "name": str(d["name"]), "channels": int(d["max_input_channels"])}
            for i, d in enumerate(devices)
            if d["max_input_channels"] > 0
        ]

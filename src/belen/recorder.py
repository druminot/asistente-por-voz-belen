"""Captura de audio del micrófono usando sounddevice (PortAudio).

Graba audio del micrófono en streaming hasta que se llame stop().
Devuelve un numpy array int16 listo para pasar a un STT backend.

Estrategia de stream persistente (prewarm):
  - Al iniciar el pipeline, se abre un InputStream permanente con callback.
  - El callback solo acumula chunks cuando _is_recording=True.
  - start() limpia chunks y setea _is_recording=True (instantáneo).
  - stop() setea _is_recording=False y copia los chunks (NO cierra el stream).
  - Esto evita la latencia de 1-2s al abrir PortAudio en cada press de hotkey.

Permisos requeridos en macOS:
- System Settings -> Privacy & Security -> Microphone
  -> Permitir acceso a la Terminal (o la app que corre Belen)
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
        rec.prewarm()       # abrir stream persistente (al inicio)
        rec.start()          # instantáneo si prewarmed
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
        if device is not None:
            self._device = device
        elif settings.belen_input_device:
            self._device = settings.belen_input_device
        else:
            self._device = 0
        self._channels = channels
        self._chunks: list[np.ndarray] = []
        self._stream = None
        self._is_recording = False
        self._lock = threading.Lock()
        self._duration_seconds: float = 0.0
        self._start_time: float = 0.0
        self._persistent_stream: object | None = None
        self._prewarmed: bool = False
        self._ready_event = threading.Event()

    def prewarm(self) -> None:
        """Abre un stream de audio persistente para evitar la latencia
        de 1-2s al abrir PortAudio en cada press de hotkey.

        Llamar al inicio del pipeline para que el primer press sea instantáneo.
        El callback solo acumula chunks cuando _is_recording es True.
        """
        if self._prewarmed:
            return
        import sounddevice as sd

        def _callback(indata: np.ndarray, frames: int, time_info: object, status: object) -> None:
            if status:
                return
            if self._is_recording:
                with self._lock:
                    if self._is_recording:
                        self._chunks.append(indata.copy())

        try:
            self._persistent_stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="int16",
                device=self._device,
                callback=_callback,
            )
            self._persistent_stream.start()
            self._prewarmed = True
            self._ready_event.set()
            from belen.logging_utils import info
            info("RECORDER", f"stream precalentado OK (device={self._device})")
        except Exception as e:
            from belen.logging_utils import warn
            warn("RECORDER", f"prewarm falló: {e}. Se abrirá stream por press.")
            self._persistent_stream = None

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
        """Arranca la grabación (instantáneo si el stream está precalentado).

        Si el stream fue precalentado, solo setea _is_recording=True y limpia
        chunks — el stream ya está abierto y corriendo.
        Si no fue precalentado, abre un stream nuevo (puede tardar 1-2s).
        """
        if self._is_recording:
            return
        import time

        self._start_time = time.monotonic()

        if self._prewarmed and self._persistent_stream is not None:
            with self._lock:
                self._chunks = []
                self._is_recording = True
            self._ready_event.set()
            return

        import sounddevice as sd

        def callback(indata: np.ndarray, frames: int, time_info: object, status: object) -> None:
            if status:
                return
            with self._lock:
                if self._is_recording:
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
            with self._lock:
                self._chunks = []
                self._is_recording = True
            self._ready_event.set()
        except Exception as e:
            with self._lock:
                self._is_recording = False
            self._ready_event.clear()
            raise RuntimeError(
                f"No se pudo abrir el stream de audio: {e}. "
                f"Verificá permisos de Micrófono en System Settings."
            ) from e

    def stop(self) -> tuple[np.ndarray, int]:
        """Detiene la grabación y devuelve (audio, sample_rate).

        Si el stream es persistente (prewarmed), solo deja de acumular
        chunks — NO cierra el stream para poder reusarlo.
        Si el stream no es persistente, lo cierra para liberar recursos.
        """
        with self._lock:
            if not self._is_recording:
                return np.array([], dtype=np.int16), self._sample_rate
            self._is_recording = False
            import time
            self._duration_seconds = time.monotonic() - self._start_time if self._start_time else 0.0
            chunks = self._chunks
            self._chunks = []

        if not self._prewarmed and self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        if not chunks:
            return np.array([], dtype=np.int16), self._sample_rate

        audio = np.concatenate(chunks, axis=0).flatten()
        return audio, self._sample_rate

    def cancel(self) -> None:
        """Cancela la grabación sin devolver audio (útil para errores)."""
        with self._lock:
            self._is_recording = False
            self._chunks = []
        if not self._prewarmed and self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def wait_ready(self, timeout: float = 3.0) -> bool:
        """Espera a que el recorder esté listo para grabar.

        Retorna True si está listo, False si timeout.
        Útil para que el release espere a que el press complete.
        """
        return self._ready_event.wait(timeout=timeout)

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

"""Detector de wake word 'Belen' (opcional, toggleable).

(Fase 6 — pendiente de implementación)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from belen.config import get_settings


@dataclass
class WakeWordConfig:
    enabled: bool
    word: str
    threshold: float = 0.5


class WakeWordDetector:
    """Detector de wake word usando openwakeword (Fase 6)."""

    def __init__(self, config: WakeWordConfig | None = None) -> None:
        settings = get_settings()
        self._config = config or WakeWordConfig(
            enabled=settings.belen_wakeword_enabled,
            word=settings.belen_wakeword,
        )
        self._model = None
        self._on_detect_cb: Callable[[str], None] | None = None

    def on_detect(self, callback: Callable[[str], None]) -> None:
        self._on_detect_cb = callback

    def load(self) -> None:
        """Carga el modelo de wake word (lazy)."""
        if not self._config.enabled:
            return
        try:
            from openwakeword.model import Model  # type: ignore[import-not-found]

            self._model = Model(
                wakeword_models=[self._config.word],
                inference_framework="onnx",
            )
        except ImportError:
            self._model = None
            raise RuntimeError(
                "openwakeword no instalado. `pip install belen[wakeword]` "
                "o desactivá BELEN_WAKEWORD_ENABLED=false"
            )

    def process_frame(self, audio_frame: bytes) -> str | None:
        """Procesa un frame de audio, devuelve la palabra detectada o None."""
        if not self._config.enabled or self._model is None:
            return None
        import numpy as np

        audio = np.frombuffer(audio_frame, dtype=np.int16)
        prediction = self._model.predict(audio)
        for word, score in prediction.items():
            if score >= self._config.threshold:
                if self._on_detect_cb is not None:
                    self._on_detect_cb(word)
                return word
        return None

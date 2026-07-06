"""Detector de wake word (ej: 'Belen').

Usa openwakeword si está instalado. Si no, provee un modo simulado
para tests y para ambientes sin el modelo entrenado.

Para entrenar tu propio modelo de "Belen":
  1. Generá muestras positivas (vos diciendo "Belen") y negativas
  2. Usá openwakeword/train.py
  3. Guardá el .onnx en models/wakeword/
  4. Configurá BELEN_WAKEWORD_PATH=./models/wakeword/belen.onnx
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from belen.config import get_settings


@dataclass(frozen=True)
class WakeWordConfig:
    enabled: bool
    word: str
    threshold: float = 0.5
    model_path: str | None = None
    sample_rate: int = 16000


class WakeWordDetector:
    """Detector de wake word.

    Uso:
        det = WakeWordDetector()
        det.on_detect(lambda w: print(f"detecté: {w}"))
        det.load()
        # En un loop con audio del mic:
        # word = det.process_frame(audio_int16)
    """

    def __init__(self, config: WakeWordConfig | None = None) -> None:
        settings = get_settings()
        self._config = config or WakeWordConfig(
            enabled=settings.belen_wakeword_enabled,
            word=settings.belen_wakeword,
        )
        self._model = None
        self._on_detect_cb: Callable[[str], None] | None = None
        self._lock = threading.Lock()
        self._simulated = False

    @property
    def config(self) -> WakeWordConfig:
        return self._config

    @property
    def is_loaded(self) -> bool:
        return self._model is not None or self._simulated

    def on_detect(self, callback: Callable[[str], None]) -> None:
        self._on_detect_cb = callback

    def load(self) -> None:
        """Carga el modelo de wake word. Si no está disponible, activa modo simulado."""
        if not self._config.enabled:
            return

        with self._lock:
            if self._model is not None or self._simulated:
                return

            try:
                from openwakeword.model import Model  # type: ignore[import-not-found]

                models_to_load = (
                    [self._config.model_path]
                    if self._config.model_path
                    else [self._config.word]
                )
                self._model = Model(
                    wakeword_models=models_to_load,
                    inference_framework="onnx",
                )
            except ImportError:
                self._simulated = True
                print(
                    "[WARN] openwakeword no instalado. "
                    "Modo simulado activo (no detecta wake word real). "
                    "Instalá con: pip install belen[wakeword]"
                )
            except Exception as e:
                self._simulated = True
                print(f"[WARN] No se pudo cargar wake word: {e}. Modo simulado.")

    def process_frame(self, audio_frame: np.ndarray | bytes) -> str | None:
        """Procesa un frame de audio. Devuelve la palabra detectada o None."""
        if not self._config.enabled:
            return None
        if not self.is_loaded:
            self.load()

        if isinstance(audio_frame, bytes):
            audio = np.frombuffer(audio_frame, dtype=np.int16)
        else:
            audio = audio_frame.astype(np.int16) if audio_frame.dtype != np.int16 else audio_frame

        if self._model is None:
            return None  # modo simulado: no detecta nada

        try:
            prediction = self._model.predict(audio)
        except Exception as e:
            print(f"[WARN] Error en predicción wake word: {e}")
            return None

        for word, score in prediction.items():
            if score >= self._config.threshold:
                if self._on_detect_cb is not None:
                    try:
                        self._on_detect_cb(word)
                    except Exception as e:
                        print(f"[WARN] Callback de wake word falló: {e}")
                return word
        return None

    def is_available(self) -> bool:
        """True si el detector está disponible (modelo cargado o simulable)."""
        if not self._config.enabled:
            return False
        try:
            import openwakeword  # type: ignore[import-not-found]  # noqa: F401

            return True
        except ImportError:
            return False

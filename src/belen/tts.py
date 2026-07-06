"""Text-to-Speech: texto → voz.

(Fase 5 — pendiente de integración con VibeVoice-Realtime + fallbacks)
"""

from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod

from belen.config import TTSEngine, get_settings


class TTSBackend(ABC):
    """Interfaz común para los backends de TTS."""

    @abstractmethod
    def speak(self, text: str) -> None:
        """Sintetiza y reproduce `text`."""

    @abstractmethod
    def is_available(self) -> bool:
        """True si el backend está listo para usar."""


class VibeVoiceRealtimeBackend(TTSBackend):
    """TTS usando microsoft/VibeVoice-Realtime-0.5B (HF)."""

    def __init__(self, voice: str | None = None) -> None:
        settings = get_settings()
        self._voice = voice or settings.belen_tts_voice
        self._model = None
        self._tokenizer = None

    def is_available(self) -> bool:
        try:
            import transformers  # noqa: F401
            import torch  # noqa: F401

            return True
        except ImportError:
            return False

    def speak(self, text: str) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if self._model is None:
            model_id = "microsoft/VibeVoice-Realtime-0.5B"
            self._tokenizer = AutoTokenizer.from_pretrained(model_id)
            self._model = AutoModelForCausalLM.from_pretrained(
                model_id,
                torch_dtype=torch.float16,
                low_cpu_mem_usage=True,
            )
            self._model.eval()

        with torch.no_grad():
            inputs = self._tokenizer(text, return_tensors="pt")
            speech = self._model.generate(**inputs, voice=self._voice)

        _play_audio_array(speech)


class PiperTTSBackend(TTSBackend):
    """TTS usando Piper (modelos ONNX locales)."""

    def __init__(self, voice: str | None = None) -> None:
        settings = get_settings()
        self._voice = voice or settings.belen_tts_voice
        self._piper = None

    def is_available(self) -> bool:
        try:
            import piper  # type: ignore[import-not-found]  # noqa: F401

            return True
        except ImportError:
            return False

    def speak(self, text: str) -> None:
        try:
            from piper import PiperVoice  # type: ignore[import-not-found]

            if self._piper is None:
                self._piper = PiperVoice.load(self._voice)
            audio = self._piper.synthesize(text)
            _play_audio_array(audio)
        except ImportError as e:
            raise RuntimeError(
                "piper-tts no instalado. `pip install piper-tts` o cambiá BELEN_TTS_ENGINE"
            ) from e


class MacOSSayBackend(TTSBackend):
    """TTS usando el comando `say` nativo de macOS (fallback de menor calidad)."""

    def __init__(self, voice: str | None = None) -> None:
        settings = get_settings()
        self._voice = voice or settings.belen_tts_voice or "Mónica"

    def is_available(self) -> bool:
        import platform

        return platform.system() == "Darwin"

    def speak(self, text: str) -> None:
        import platform

        if platform.system() != "Darwin":
            raise RuntimeError("macOS `say` solo disponible en macOS")
        subprocess.run(["say", "-v", self._voice, text], check=False)


def _play_audio_array(audio: object) -> None:
    """Reproduce un array de audio (numpy o tensor)."""
    try:
        import sounddevice as sd

        if hasattr(audio, "cpu"):
            audio = audio.cpu().numpy()
        if hasattr(audio, "numpy"):
            audio = audio.numpy()
        sd.play(audio)
        sd.wait()
    except Exception as e:
        raise RuntimeError(f"Error reproduciendo audio: {e}") from e


def get_tts_backend(engine: TTSEngine | None = None) -> TTSBackend:
    """Devuelve el backend TTS configurado (con fallback automático a macOS say)."""
    settings = get_settings()
    engine = engine or settings.belen_tts_engine

    if engine == TTSEngine.VIBEVOICE_REALTIME:
        backend: TTSBackend = VibeVoiceRealtimeBackend()
        if not backend.is_available():
            print(
                "[WARN] VibeVoice-Realtime no disponible, fallback a macOS say. "
                "Instalá con: pip install belen[tts-vibevoice]"
            )
            backend = MacOSSayBackend()
    elif engine == TTSEngine.PIPER:
        backend = PiperTTSBackend()
        if not backend.is_available():
            print("[WARN] Piper no disponible, fallback a macOS say.")
            backend = MacOSSayBackend()
    elif engine == TTSEngine.MACOS_SAY:
        backend = MacOSSayBackend()
    else:
        raise ValueError(f"Engine TTS desconocido: {engine}")

    if not backend.is_available():
        raise RuntimeError(
            f"Ningún backend TTS disponible. Probá: BELEN_TTS_ENGINE=macos-say"
        )
    return backend

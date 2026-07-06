"""Text-to-Speech: texto → voz.

Backends:
- VibeVoice-Realtime-0.5B (HF): state-of-the-art, ES nativo
- Piper TTS: ONNX local, baja latencia
- macOS `say`: fallback nativo (robótico pero funciona)

El TTSManager intenta el backend configurado y hace fallback si falla.
"""

from __future__ import annotations

import subprocess
import threading
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np

from belen.config import TTSEngine, get_settings


class TTSBackend(ABC):
    """Interfaz común para backends de TTS."""

    name: str = "base"

    @abstractmethod
    def speak(self, text: str) -> None:
        """Sintetiza y reproduce `text`."""

    @abstractmethod
    def is_available(self) -> bool:
        """True si el backend está listo para usar."""

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        """Sintetiza sin reproducir. Devuelve (audio, sample_rate)."""
        raise NotImplementedError


def _play_audio_array(audio: np.ndarray, sample_rate: int | None = None) -> None:
    """Reproduce un array numpy (int16 o float32) por el speaker default."""
    import sounddevice as sd

    if isinstance(audio, np.ndarray):
        if audio.dtype == np.int16:
            data = audio
        else:
            data = (audio * 32767).astype(np.int16)
    else:
        data = np.asarray(audio)
    sd.play(data, samplerate=sample_rate)
    sd.wait()


def save_wav(audio: np.ndarray, sample_rate: int, path: Path | str) -> Path:
    """Guarda audio a WAV en disco."""
    import soundfile as sf

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio, sample_rate)
    return path


class VibeVoiceRealtimeBackend(TTSBackend):
    """TTS usando microsoft/VibeVoice-Realtime-0.5B (HF Transformers).

    Modelo state-of-the-art para streaming TTS. Soporta ES nativo.
    """

    name = "vibevoice-realtime"

    def __init__(self, voice: str | None = None) -> None:
        settings = get_settings()
        self._voice = voice or settings.belen_tts_voice
        self._model = None
        self._tokenizer = None

    def is_available(self) -> bool:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401

            return True
        except ImportError:
            return False

    def _load(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        model_id = "microsoft/VibeVoice-Realtime-0.5B"
        self._tokenizer = AutoTokenizer.from_pretrained(model_id)
        self._model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=torch.float16,
            low_cpu_mem_usage=True,
        )
        self._model.eval()

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        self._load()
        import torch

        with torch.no_grad():
            inputs = self._tokenizer(text, return_tensors="pt")
            speech = self._model.generate(**inputs, voice=self._voice)

        if hasattr(speech, "cpu"):
            audio = speech.cpu().numpy()
        else:
            audio = np.asarray(speech)
        sample_rate = 24000
        return audio.squeeze(), sample_rate

    def speak(self, text: str) -> None:
        audio, sr = self.synthesize(text)
        _play_audio_array(audio, sr)


class PiperTTSBackend(TTSBackend):
    """TTS usando Piper (ONNX local)."""

    name = "piper"

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

    def _load(self) -> None:
        if self._piper is not None:
            return
        from piper import PiperVoice  # type: ignore[import-not-found]

        self._piper = PiperVoice.load(self._voice)

    def speak(self, text: str) -> None:
        try:
            self._load()
            audio = self._piper.synthesize(text)
            _play_audio_array(audio, 22050)
        except ImportError as e:
            raise RuntimeError(
                "piper-tts no instalado. `pip install piper-tts` o cambiá BELEN_TTS_ENGINE"
            ) from e


class MacOSSayBackend(TTSBackend):
    """TTS usando el comando `say` nativo de macOS (fallback)."""

    name = "macos-say"

    def __init__(self, voice: str | None = None, rate: int = 200) -> None:
        settings = get_settings()
        self._voice = voice or settings.belen_tts_voice or "Mónica"
        self._rate = rate

    def is_available(self) -> bool:
        import platform

        return platform.system() == "Darwin"

    def speak(self, text: str) -> None:
        import platform

        if platform.system() != "Darwin":
            raise RuntimeError("macOS `say` solo disponible en macOS")
        subprocess.run(
            ["say", "-v", self._voice, "-r", str(self._rate), text],
            check=False,
        )


class MockTTSBackend(TTSBackend):
    """TTS mock para tests — guarda texto y no reproduce nada."""

    name = "mock"

    def __init__(self) -> None:
        self.spoken: list[str] = []
        self._lock = threading.Lock()

    def is_available(self) -> bool:
        return True

    def speak(self, text: str) -> None:
        with self._lock:
            self.spoken.append(text)


class TTSManager:
    """Gestor de TTS con fallback automático entre backends."""

    FALLBACK_CHAIN: dict[TTSEngine, list[TTSEngine]] = {
        TTSEngine.VIBEVOICE_REALTIME: [TTSEngine.VIBEVOICE_REALTIME, TTSEngine.MACOS_SAY],
        TTSEngine.PIPER: [TTSEngine.PIPER, TTSEngine.MACOS_SAY],
        TTSEngine.MACOS_SAY: [TTSEngine.MACOS_SAY],
    }

    def __init__(self, engine: TTSEngine | None = None) -> None:
        settings = get_settings()
        self._engine = engine or settings.belen_tts_engine
        self._chain: list[TTSBackend] = self._build_chain(self._engine)
        self._active: TTSBackend = self._chain[0]

    def _build_chain(self, engine: TTSEngine) -> list[TTSBackend]:
        order = self.FALLBACK_CHAIN.get(engine, [TTSEngine.MACOS_SAY])
        backends: list[TTSBackend] = []
        for eng in order:
            backend = self._build_backend(eng)
            if backend is not None and backend not in backends:
                backends.append(backend)
        if not backends:
            backends.append(MacOSSayBackend())
        return backends

    def _build_backend(self, engine: TTSEngine) -> TTSBackend | None:
        if engine == TTSEngine.VIBEVOICE_REALTIME:
            return VibeVoiceRealtimeBackend()
        if engine == TTSEngine.PIPER:
            return PiperTTSBackend()
        if engine == TTSEngine.MACOS_SAY:
            return MacOSSayBackend()
        return None

    @property
    def backend(self) -> TTSBackend:
        return self._active

    def is_available(self) -> bool:
        return any(b.is_available() for b in self._chain)

    def list_available(self) -> list[str]:
        return [b.name for b in self._chain if b.is_available()]

    def speak(self, text: str) -> None:
        """Sintetiza y reproduce con fallback automático."""
        if not text or not text.strip():
            return

        last_error: Exception | None = None
        for backend in self._chain:
            if not backend.is_available():
                continue
            try:
                backend.speak(text)
                self._active = backend
                return
            except Exception as e:
                last_error = e
                print(f"[TTS] {backend.name} falló: {e}. Probando siguiente...")
                continue

        raise RuntimeError(
            f"Ningún backend TTS pudo reproducir. Último error: {last_error}"
        )

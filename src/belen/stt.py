"""Speech-to-Text: voz → texto.

Backends soportados:
- VibeVoice-ASR (microsoft/VibeVoice-ASR): 7B params, multilingüe, 60min single-pass
- faster-whisper: CTranslate2, modelos tiny→large-v3, fallback robusto

El STTManager intenta el backend configurado y hace fallback automático si
no está disponible o falla.
"""

from __future__ import annotations

import io
import wave
from abc import ABC, abstractmethod

import numpy as np

from belen.config import STTEngine, get_settings


class STTBackend(ABC):
    """Interfaz común para los backends de STT."""

    name: str = "base"

    @abstractmethod
    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        """Transcribe audio → texto."""

    @abstractmethod
    def is_available(self) -> bool:
        """True si el backend está listo para usar."""


def audio_to_wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
    """Convierte audio numpy int16 a bytes WAV (formato in-memory)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())
    return buf.getvalue()


def detect_silence(audio: np.ndarray, threshold: int = 100, min_silence_ms: int = 300) -> bool:
    """Detecta si el audio es esencialmente silencio.

    threshold: amplitud máxima considerada silencio (int16, 0-32767)
    min_silence_ms: duración mínima de silencio en ms
    """
    if audio.size == 0:
        return True
    rms = float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))
    return rms < threshold


class VibeVoiceASRBackend(STTBackend):
    """STT usando microsoft/VibeVoice-ASR (HF Transformers).

    Modelo grande (7B params) y multilingüe. Requiere transformers + torch.
    """

    name = "vibevoice-asr"

    def __init__(self, model_id: str = "microsoft/VibeVoice-ASR") -> None:
        self._model_id = model_id
        self._model = None
        self._processor = None
        self._pipeline = None

    def is_available(self) -> bool:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401

            return True
        except ImportError:
            return False

    def _load(self) -> None:
        if self._pipeline is not None:
            return
        import torch
        from transformers import (
            AutoModelForSpeechSeq2Seq,
            AutoProcessor,
            pipeline,
        )

        self._processor = AutoProcessor.from_pretrained(self._model_id)
        self._model = AutoModelForSpeechSeq2Seq.from_pretrained(
            self._model_id,
            torch_dtype=torch.float16,
            low_cpu_mem_usage=True,
        )
        self._pipeline = pipeline(
            "automatic-speech-recognition",
            model=self._model,
            tokenizer=self._processor.tokenizer,
            feature_extractor=self._processor.feature_extractor,
            torch_dtype=torch.float16,
        )

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        self._load()
        import tempfile

        import soundfile as sf

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            sf.write(f.name, audio, sample_rate)
            tmp_path = f.name

        try:
            result = self._pipeline(tmp_path, return_timestamps=True)
            return result.get("text", "").strip()
        finally:
            from pathlib import Path

            Path(tmp_path).unlink(missing_ok=True)


class FasterWhisperBackend(STTBackend):
    """STT usando faster-whisper (CTranslate2).

    Rápido, liviano, modelos de tiny a large-v3.
    """

    name = "faster-whisper"

    def __init__(self, model_size: str | None = None, language: str | None = None) -> None:
        settings = get_settings()
        self._model_size = model_size or settings.belen_whisper_model
        self._language = language or settings.belen_stt_lang
        self._model = None

    def is_available(self) -> bool:
        try:
            import faster_whisper  # noqa: F401

            return True
        except ImportError:
            return False

    def _load(self) -> None:
        if self._model is not None:
            return
        from faster_whisper import WhisperModel

        self._model = WhisperModel(
            self._model_size,
            device="auto",
            compute_type="int8",
        )

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        self._load()
        audio_float = audio.astype(np.float32) / 32768.0
        segments, _info = self._model.transcribe(
            audio_float,
            language=self._language if self._language != "auto" else None,
            beam_size=5,
            vad_filter=True,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()


class MockSTTBackend(STTBackend):
    """Backend mock para tests — devuelve texto fijo o eco."""

    name = "mock"

    def __init__(self, response: str = "mock transcription") -> None:
        self._response = response
        self._calls: list[tuple[int, int]] = []

    def is_available(self) -> bool:
        return True

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        self._calls.append((len(audio), sample_rate))
        return self._response


class STTManager:
    """Gestor de STT con fallback automático entre backends.

    Uso:
        stt = STTManager()
        text = stt.transcribe(audio, sample_rate)
    """

    def __init__(self, engine: STTEngine | None = None) -> None:
        settings = get_settings()
        self._engine = engine or settings.belen_stt_engine
        self._primary = self._build_backend(self._engine)
        self._fallback: STTBackend | None = None
        if self._engine != STTEngine.FASTER_WHISPER:
            self._fallback = self._build_backend(STTEngine.FASTER_WHISPER)

    def _build_backend(self, engine: STTEngine) -> STTBackend:
        if engine == STTEngine.VIBEVOICE_ASR:
            return VibeVoiceASRBackend()
        if engine == STTEngine.FASTER_WHISPER:
            return FasterWhisperBackend()
        raise ValueError(f"Engine STT desconocido: {engine}")

    @property
    def backend(self) -> STTBackend:
        """Devuelve el backend activo (puede haber cambiado por fallback)."""
        return self._primary

    def is_available(self) -> bool:
        return self._primary.is_available() or (
            self._fallback is not None and self._fallback.is_available()
        )

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        """Transcribe audio → texto con fallback automático."""
        if detect_silence(audio):
            return ""

        for backend in [self._primary, self._fallback]:
            if backend is None or not backend.is_available():
                continue
            try:
                return backend.transcribe(audio, sample_rate)
            except Exception as e:
                print(f"[STT] {backend.name} falló: {e}. Probando fallback...")
                continue

        raise RuntimeError(
            "Ningún backend STT disponible. Instalá uno:\n"
            "  pip install belen[stt-vibevoice]   # VibeVoice-ASR\n"
            "  pip install belen[stt-whisper]     # faster-whisper"
        )

"""Speech-to-Text: voz → texto.

(Fase 3 — pendiente de integración con VibeVoice-ASR + fallback faster-whisper)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np

from belen.config import STTEngine, get_settings


class STTBackend(ABC):
    """Interfaz común para los backends de STT."""

    @abstractmethod
    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        """Transcribe audio → texto."""

    @abstractmethod
    def is_available(self) -> bool:
        """True si el backend está listo para usar."""


class VibeVoiceASRBackend(STTBackend):
    """STT usando microsoft/VibeVoice-ASR (HF Transformers)."""

    def __init__(self) -> None:
        self._model = None
        self._processor = None

    def is_available(self) -> bool:
        try:
            import transformers  # noqa: F401
            import torch  # noqa: F401

            return True
        except ImportError:
            return False

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        import torch
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

        if self._model is None:
            model_id = "microsoft/VibeVoice-ASR"
            self._processor = AutoProcessor.from_pretrained(model_id)
            self._model = AutoModelForSpeechSeq2Seq.from_pretrained(
                model_id,
                torch_dtype=torch.float16,
                low_cpu_mem_usage=True,
            )
            self._model.eval()

        import soundfile as sf
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            sf.write(f.name, audio, sample_rate)
            tmp_path = f.name

        try:
            from transformers import pipeline

            pipe = pipeline(
                "automatic-speech-recognition",
                model=self._model,
                tokenizer=self._processor.tokenizer,
                feature_extractor=self._processor.feature_extractor,
                torch_dtype=torch.float16,
            )
            result = pipe(tmp_path, return_timestamps=True)
            return result.get("text", "").strip()
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class FasterWhisperBackend(STTBackend):
    """STT usando faster-whisper (CTranslate2)."""

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

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        from faster_whisper import WhisperModel

        if self._model is None:
            self._model = WhisperModel(self._model_size, device="auto", compute_type="int8")

        audio_float = audio.astype(np.float32) / 32768.0
        segments, _info = self._model.transcribe(
            audio_float,
            language=self._language if self._language != "auto" else None,
            beam_size=5,
            vad_filter=True,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()


def get_stt_backend(engine: STTEngine | None = None) -> STTBackend:
    """Devuelve el backend STT configurado (con fallback automático)."""
    settings = get_settings()
    engine = engine or settings.belen_stt_engine

    if engine == STTEngine.VIBEVOICE_ASR:
        backend: STTBackend = VibeVoiceASRBackend()
        if not backend.is_available():
            print(
                "[WARN] VibeVoice-ASR no disponible, fallback a faster-whisper. "
                "Instalá con: pip install belen[stt-vibevoice]"
            )
            backend = FasterWhisperBackend()
    elif engine == STTEngine.FASTER_WHISPER:
        backend = FasterWhisperBackend()
    else:
        raise ValueError(f"Engine STT desconocido: {engine}")

    if not backend.is_available():
        raise RuntimeError(
            f"Backend {engine} no disponible. "
            f"Instalá las deps: pip install belen[stt-vibevoice] o belen[stt-whisper]"
        )
    return backend

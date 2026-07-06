"""Tests del módulo STT."""

import numpy as np
import pytest

from belen.stt import (
    FasterWhisperBackend,
    MockSTTBackend,
    STTManager,
    VibeVoiceASRBackend,
    audio_to_wav_bytes,
    detect_silence,
)


def test_audio_to_wav_bytes():
    audio = np.zeros(1600, dtype=np.int16)
    wav = audio_to_wav_bytes(audio, 16000)
    assert len(wav) > 44  # header WAV + datos
    assert wav[:4] == b"RIFF"
    assert wav[8:12] == b"WAVE"


def test_detect_silence_empty():
    assert detect_silence(np.array([], dtype=np.int16)) is True


def test_detect_silence_silencio():
    audio = np.zeros(16000, dtype=np.int16)
    assert detect_silence(audio) is True


def test_detect_silence_audio():
    rng = np.random.default_rng(42)
    audio = rng.integers(-10000, 10000, size=16000, dtype=np.int16)
    assert detect_silence(audio) is False


def test_vibevoice_is_available():
    backend = VibeVoiceASRBackend()
    assert backend.name == "vibevoice-asr"
    # is_available() devuelve True o False según deps instaladas; solo verificamos que no tira


def test_whisper_is_available():
    backend = FasterWhisperBackend()
    assert backend.name == "faster-whisper"


def test_mock_backend_transcribe():
    mock = MockSTTBackend(response="hola mundo")
    audio = np.ones(1600, dtype=np.int16)
    text = mock.transcribe(audio, 16000)
    assert text == "hola mundo"
    assert len(mock._calls) == 1


def test_stt_manager_silencio():
    mock = MockSTTBackend()
    manager = STTManager.__new__(STTManager)
    manager._engine = None
    manager._primary = mock
    manager._fallback = None
    text = manager.transcribe(np.zeros(16000, dtype=np.int16), 16000)
    assert text == ""
    assert len(mock._calls) == 0


def test_stt_manager_con_audio():
    rng = np.random.default_rng(42)
    audio = rng.integers(-5000, 5000, size=16000, dtype=np.int16)

    manager = STTManager.__new__(STTManager)
    manager._engine = None
    manager._primary = MockSTTBackend(response="transcripción de prueba")
    manager._fallback = None
    text = manager.transcribe(audio, 16000)
    assert text == "transcripción de prueba"


def test_stt_manager_fallback():
    """Si el backend primario falla, debe probar el fallback."""

    class FailingBackend:
        name = "failing"

        def is_available(self):
            return True

        def transcribe(self, audio, sr):
            raise RuntimeError("simulated failure")

    rng = np.random.default_rng(42)
    audio = rng.integers(-5000, 5000, size=16000, dtype=np.int16)

    manager = STTManager.__new__(STTManager)
    manager._engine = None
    manager._primary = FailingBackend()
    manager._fallback = MockSTTBackend(response="fallback worked")
    text = manager.transcribe(audio, 16000)
    assert text == "fallback worked"


def test_stt_manager_sin_backends():
    manager = STTManager.__new__(STTManager)
    manager._engine = None
    manager._primary = MockSTTBackend()
    manager._fallback = None

    class Unavailable:
        name = "unavail"
        is_available = staticmethod(lambda: False)
        def transcribe(self, audio, sr): ...

    manager._primary = Unavailable()
    rng = np.random.default_rng(42)
    audio = rng.integers(-5000, 5000, size=16000, dtype=np.int16)

    with pytest.raises(RuntimeError, match="Ningún backend"):
        manager.transcribe(audio, 16000)

"""Tests del módulo TTS."""

import platform

import pytest

from belen.tts import (
    MacOSSayBackend,
    MockTTSBackend,
    TTSManager,
)


def test_mock_tts_speak():
    mock = MockTTSBackend()
    mock.speak("hola mundo")
    mock.speak("chau mundo")
    assert mock.spoken == ["hola mundo", "chau mundo"]


def test_mock_tts_is_available():
    assert MockTTSBackend().is_available() is True


def test_tts_manager_mock_chain():
    primary = MockTTSBackend()
    fallback = MockTTSBackend()
    manager = TTSManager.__new__(TTSManager)
    manager._engine = None
    manager._chain = [primary, fallback]
    manager._active = primary

    manager.speak("test")
    assert primary.spoken == ["test"]
    assert fallback.spoken == []


def test_tts_manager_fallback():
    class Failing:
        name = "failing"
        def is_available(self): return True
        def speak(self, text): raise RuntimeError("boom")

    fallback = MockTTSBackend()
    manager = TTSManager.__new__(TTSManager)
    manager._engine = None
    manager._chain = [Failing(), fallback]
    manager._active = Failing()

    manager.speak("test")
    assert fallback.spoken == ["test"]


def test_tts_manager_empty_text():
    mock = MockTTSBackend()
    manager = TTSManager.__new__(TTSManager)
    manager._engine = None
    manager._chain = [mock]
    manager._active = mock
    manager.speak("")
    manager.speak("   ")
    assert mock.spoken == []


def test_tts_manager_sin_backends_disponibles():
    class NeverAvailable:
        name = "never"
        def is_available(self): return False
        def speak(self, text): pass

    manager = TTSManager.__new__(TTSManager)
    manager._engine = None
    manager._chain = [NeverAvailable()]
    manager._active = NeverAvailable()

    with pytest.raises(RuntimeError, match="Ning"):
        manager.speak("test")


def test_macos_say_is_available_solo_macos():
    backend = MacOSSayBackend(voice="Mónica")
    if platform.system() == "Darwin":
        assert backend.is_available() is True
    else:
        assert backend.is_available() is False


def test_tts_manager_list_available():
    mock1 = MockTTSBackend()
    mock2 = MockTTSBackend()
    manager = TTSManager.__new__(TTSManager)
    manager._engine = None
    manager._chain = [mock1, mock2]
    manager._active = mock1
    assert manager.list_available() == ["mock", "mock"]


def test_tts_manager_active_cambia_en_fallback():
    primary = MockTTSBackend()

    class Failing:
        name = "failing"
        def is_available(self): return True
        def speak(self, text): raise RuntimeError("boom")

    fallback = MockTTSBackend()
    manager = TTSManager.__new__(TTSManager)
    manager._engine = None
    manager._chain = [Failing(), fallback]
    manager._active = Failing()

    manager.speak("hola")
    assert manager._active is fallback

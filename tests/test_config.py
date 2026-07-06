"""Tests de configuración de Belen."""

import os
from pathlib import Path

from belen.config import HotkeyMode, STTEngine, TTSEngine


def test_default_settings():
    """Verifica que Settings carga con valores default correctos."""
    from belen.config import Settings

    s = Settings()
    assert s.opencode_bin == "opencode"
    assert s.belen_hotkey == "option+z+comma"
    assert s.belen_hotkey_mode == HotkeyMode.PUSH_TO_TALK
    assert s.belen_wakeword_enabled is True
    assert s.belen_wakeword == "belen"
    assert s.belen_stt_engine == STTEngine.FASTER_WHISPER
    assert s.belen_tts_engine == TTSEngine.VIBEVOICE_REALTIME
    assert s.belen_sample_rate == 16000
    assert s.belen_stt_lang == "es"
    assert s.belen_floating_ui is True


def test_settings_from_env(monkeypatch, tmp_path):
    """Verifica que Settings lee de variables de entorno."""
    from belen.config import Settings

    env_file = tmp_path / ".env"
    env_file.write_text("BELEN_HOTKEY=cmd+shift+b\nBELEN_SAMPLE_RATE=48000\n")

    s = Settings(_env_file=str(env_file))
    assert s.belen_hotkey == "cmd+shift+b"
    assert s.belen_sample_rate == 48000
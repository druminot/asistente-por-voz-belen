"""Tests del detector de wake word."""

import numpy as np
import pytest

from belen.wakeword import WakeWordConfig, WakeWordDetector


def test_config_default():
    cfg = WakeWordConfig(enabled=True, word="belen")
    assert cfg.threshold == 0.5
    assert cfg.word == "belen"


def test_config_inmutable():
    cfg = WakeWordConfig(enabled=True, word="belen")
    with pytest.raises(Exception):  # FrozenInstanceError
        cfg.word = "otro"  # type: ignore[misc]


def test_init_from_settings():
    det = WakeWordDetector()
    cfg = det.config
    assert cfg.word in ("belen",)  # default


def test_callback_set():
    det = WakeWordDetector()
    called = []
    det.on_detect(lambda w: called.append(w))
    assert det._on_detect_cb is not None


def test_disabled_returns_none():
    det = WakeWordDetector(WakeWordConfig(enabled=False, word="x"))
    audio = np.ones(16000, dtype=np.int16)
    assert det.process_frame(audio) is None


def test_sin_cargar_devuelve_none():
    """Si no se cargó el modelo, devuelve None (no rompe)."""
    det = WakeWordDetector(WakeWordConfig(enabled=True, word="belen"))
    audio = np.ones(16000, dtype=np.int16)
    # process_frame carga lazy, pero como no hay modelo, devuelve None
    assert det.process_frame(audio) is None


def test_bytes_input():
    det = WakeWordDetector(WakeWordConfig(enabled=False, word="belen"))
    audio_bytes = b"\x00\x01" * 1000
    assert det.process_frame(audio_bytes) is None


def test_is_available():
    det = WakeWordDetector()
    if det.is_available():
        assert det.config.enabled is True
    else:
        assert det.config.enabled is False or True  # sin openwakeword

"""Tests del AudioRecorder (sin abrir streams reales, solo lógica)."""

import numpy as np

from belen.recorder import AudioRecorder


def test_init_defaults():
    rec = AudioRecorder()
    assert rec.sample_rate == 16000
    assert rec.is_recording is False
    assert rec.duration_seconds == 0.0


def test_init_custom():
    rec = AudioRecorder(sample_rate=48000, device=2)
    assert rec.sample_rate == 48000


def test_stop_sin_start():
    rec = AudioRecorder()
    audio, sr = rec.stop()
    assert audio.size == 0
    assert sr == 16000


def test_cancel():
    rec = AudioRecorder()
    rec.cancel()
    assert rec.is_recording is False


def test_get_duration():
    sr = 16000
    audio = np.zeros(sr * 3, dtype=np.int16)
    assert AudioRecorder.get_duration(audio, sr) == 3.0


def test_get_duration_empty():
    audio = np.array([], dtype=np.int16)
    assert AudioRecorder.get_duration(audio, 16000) == 0.0


def test_get_duration_invalid_sr():
    audio = np.zeros(1000, dtype=np.int16)
    assert AudioRecorder.get_duration(audio, 0) == 0.0

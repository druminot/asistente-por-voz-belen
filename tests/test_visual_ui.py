"""Tests del visual UI (mayormente fallback, sin NSApp real)."""

import platform

import pytest

from belen.visual_ui import UIState, get_visual_ui


def test_ui_state_enum():
    assert UIState.IDLE.value == "idle"
    assert UIState.LISTENING.value == "listening"
    assert UIState.PROCESSING.value == "processing"
    assert UIState.SPEAKING.value == "speaking"
    assert UIState.ERROR.value == "error"


def test_state_labels():
    from belen.visual_ui import STATE_LABELS
    assert "Belen" in STATE_LABELS[UIState.IDLE]
    assert "Escuchando" in STATE_LABELS[UIState.LISTENING]


def test_state_colors():
    from belen.visual_ui import STATE_COLORS
    assert len(STATE_COLORS[UIState.IDLE]) == 4
    assert len(STATE_COLORS[UIState.LISTENING]) == 4
    # listening es rojo
    r, g, b, a = STATE_COLORS[UIState.LISTENING]
    assert r > 0.7 and g < 0.5


def test_fallback_visual_ui():
    from belen.visual_ui import FallbackVisualUI

    ui = FallbackVisualUI()
    ui.idle()
    assert ui.state == UIState.IDLE
    ui.listening()
    assert ui.state == UIState.LISTENING
    ui.processing("hola")
    assert ui.state == UIState.PROCESSING
    ui.speaking("respuesta")
    assert ui.state == UIState.SPEAKING
    ui.error("fallo")
    assert ui.state == UIState.ERROR


def test_fallback_visual_ui_update():
    from belen.visual_ui import FallbackVisualUI

    ui = FallbackVisualUI()
    ui.update(UIState.LISTENING, "escuchando")
    assert ui.state == UIState.LISTENING
    ui.update(UIState.PROCESSING, "pensando en voz alta")
    assert ui._belen_text == "pensando en voz alta"


def test_get_visual_ui_devuelve_algo():
    ui = get_visual_ui()
    if platform.system() == "Darwin":
        from belen.visual_ui import SiriStyleWindow, FallbackVisualUI

        assert isinstance(ui, (SiriStyleWindow, FallbackVisualUI))
    else:
        from belen.visual_ui import FallbackVisualUI

        assert isinstance(ui, FallbackVisualUI)


def test_fallback_visual_ui_show_hide():
    from belen.visual_ui import FallbackVisualUI

    ui = FallbackVisualUI()
    # No debe tirar error
    ui.show()
    ui.hide()


def test_fallback_visual_ui_stop():
    from belen.visual_ui import FallbackVisualUI

    ui = FallbackVisualUI()
    ui.stop()
    assert ui._running is False

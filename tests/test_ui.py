"""Tests de la UI flotante (mayormente ConsoleUI, no rumps real)."""

import platform

import pytest

from belen.ui import ConsoleUI, UIState, get_ui


def test_ui_state_enum():
    assert UIState.IDLE.value == "⚪"
    assert UIState.LISTENING.value == "🔴"
    assert UIState.PROCESSING.value == "🟡"
    assert UIState.SPEAKING.value == "🟢"
    assert UIState.ERROR.value == "❌"


def test_console_ui_idle():
    ui = ConsoleUI()
    assert ui.state == UIState.IDLE
    ui.idle()
    assert ui.state == UIState.IDLE


def test_console_ui_estados():
    ui = ConsoleUI()
    ui.listening()
    assert ui.state == UIState.LISTENING
    ui.processing("pensando...")
    assert ui.state == UIState.PROCESSING
    ui.speaking("hola")
    assert ui.state == UIState.SPEAKING
    ui.error("fallo")
    assert ui.state == UIState.ERROR
    ui.idle()
    assert ui.state == UIState.IDLE


def test_console_ui_wakeword():
    ui = ConsoleUI()
    assert ui._wakeword_enabled is True
    ui.set_wakeword_enabled(False)
    assert ui._wakeword_enabled is False
    ui.set_wakeword_enabled(True)
    assert ui._wakeword_enabled is True


def test_console_ui_start_no_bloquea():
    ui = ConsoleUI()
    ui.start()


def test_get_ui_devuelve_algo():
    ui = get_ui()
    if platform.system() == "Darwin":
        # En macOS intenta usar FloatingUI pero no arranca el event loop acá
        from belen.ui import FloatingUI

        assert isinstance(ui, (FloatingUI, ConsoleUI))
    else:
        assert isinstance(ui, ConsoleUI)

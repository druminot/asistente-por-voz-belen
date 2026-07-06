"""Tests del hotkey parser (sin instanciar el listener real que requiere pynput thread)."""

import pytest
from pynput.keyboard import Key, KeyCode

from belen.hotkey import HotkeyListener, HotkeySpec, _parse_token


def test_parse_simple():
    spec = HotkeySpec.parse("option+z+comma")
    assert len(spec.keys) == 3
    assert spec.keys[0] == Key.alt
    assert spec.keys[1] == KeyCode.from_char("z")
    assert spec.keys[2] == KeyCode.from_char(",")


def test_parse_cmd_shift():
    spec = HotkeySpec.parse("cmd+shift+b")
    assert spec.keys[0] == Key.cmd
    assert spec.keys[1] == Key.shift
    assert spec.keys[2] == KeyCode.from_char("b")


def test_parse_aliases():
    assert _parse_token("alt") == Key.alt
    assert _parse_token("option") == Key.alt
    assert _parse_token("opt") == Key.alt
    assert _parse_token("command") == Key.cmd
    assert _parse_token("control") == Key.ctrl
    assert _parse_token("esc") == Key.esc
    assert _parse_token("escape") == Key.esc


def test_parse_special_chars():
    assert _parse_token("comma") == KeyCode.from_char(",")
    assert _parse_token("period") == KeyCode.from_char(".")
    assert _parse_token("dot") == KeyCode.from_char(".")
    assert _parse_token("slash") == KeyCode.from_char("/")
    assert _parse_token("space") == Key.space
    assert _parse_token("enter") == Key.enter


def test_parse_token_unknown():
    with pytest.raises(ValueError, match="desconocido"):
        _parse_token("notarealtoken")


def test_parse_empty():
    with pytest.raises(ValueError, match="vacía"):
        HotkeySpec.parse("")


def test_parse_only_separators():
    with pytest.raises(ValueError, match="vacía"):
        HotkeySpec.parse("+++   +++")


def test_spec_str():
    spec = HotkeySpec.parse("option+z+comma")
    assert "alt" in str(spec)
    assert "z" in str(spec)
    assert "," in str(spec)


def test_listener_init_with_spec():
    listener = HotkeyListener(spec="cmd+shift+x", mode="toggle")
    assert listener.mode.value == "toggle"
    assert len(listener.spec.keys) == 3
    assert listener.is_active is False


def test_listener_callbacks_set():
    listener = HotkeyListener(spec="option+z+comma")

    pressed_called = []
    released_called = []

    listener.on_press(lambda: pressed_called.append(True))
    listener.on_release(lambda: released_called.append(True))

    assert listener._on_press_cb is not None
    assert listener._on_release_cb is not None

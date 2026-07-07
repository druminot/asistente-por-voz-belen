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


def test_listener_pump_dispatches_press():
    """pump() despacha eventos 'press' de la queue a los callbacks."""
    listener = HotkeyListener(spec="shift+z")
    pressed: list[bool] = []
    released: list[bool] = []
    listener.on_press(lambda: pressed.append(True))
    listener.on_release(lambda: released.append(True))

    # inyectar un evento "press" directamente en la queue
    listener._event_queue.put("press")
    listener.pump(timeout=0.1)

    assert pressed == [True]
    assert released == []


def test_listener_pump_dispatches_release():
    """pump() despacha eventos 'release' de la queue a los callbacks."""
    listener = HotkeyListener(spec="shift+z")
    pressed: list[bool] = []
    released: list[bool] = []
    listener.on_press(lambda: pressed.append(True))
    listener.on_release(lambda: released.append(True))

    listener._event_queue.put("release")
    listener.pump(timeout=0.1)

    assert released == [True]
    assert pressed == []


def test_listener_pump_timeout_no_events():
    """pump() con queue vacía retorna sin llamar callbacks."""
    listener = HotkeyListener(spec="shift+z")
    pressed: list[bool] = []
    listener.on_press(lambda: pressed.append(True))

    listener.pump(timeout=0.01)
    assert pressed == []


def test_listener_pump_swallows_callback_exception():
    """Si el callback lanza, pump() captura y no rompe el loop."""
    listener = HotkeyListener(spec="shift+z")

    def boom() -> None:
        raise RuntimeError("callback explotó")

    listener.on_press(boom)
    listener._event_queue.put("press")
    # no debe propagar la excepción
    listener.pump(timeout=0.1)
    assert listener.last_error is not None
    assert "on_press callback" in listener.last_error


def test_listener_handle_press_enqueue_only():
    """_handle_press solo encola, no llama al callback directamente."""
    listener = HotkeyListener(spec="shift+z", mode="push_to_talk")
    called: list[bool] = []
    listener.on_press(lambda: called.append(True))

    from pynput.keyboard import Key, KeyCode
    listener._handle_press(Key.shift)
    assert listener._event_queue.qsize() <= 1  # shift solo no dispara
    assert called == []  # callback no llamado aún

    listener._handle_press(KeyCode.from_char("z"))
    assert listener._event_queue.qsize() == 1
    assert called == []  # aún no se despacha

    # pump lo despacha
    listener.pump(timeout=0.1)
    assert called == [True]


def test_normalize_key_uppercase_with_shift():
    """pynput reporta 'Z' mayúscula con shift; _normalize_key la pasa a minúscula."""
    from pynput.keyboard import KeyCode
    from belen.hotkey import _normalize_key

    upper_z = KeyCode.from_char("Z")
    lower_z = _normalize_key(upper_z)
    assert lower_z.char == "z"

    # sin shift, ya es minúscula, no cambia
    plain_a = KeyCode.from_char("a")
    assert _normalize_key(plain_a).char == "a"


def test_handle_press_normalizes_uppercase_z():
    """Shift+Z reporta 'Z' pero el spec tiene 'z' — debe matchear."""
    listener = HotkeyListener(spec="shift+z", mode="push_to_talk")
    pressed: list[bool] = []
    listener.on_press(lambda: pressed.append(True))

    from pynput.keyboard import Key, KeyCode
    # simular: apretar shift, después Z (mayúscula por shift)
    listener._handle_press(Key.shift)
    listener._handle_press(KeyCode.from_char("Z"))  # mayúscula!

    # debe haber encolado 'press' porque normaliza Z→z
    assert listener._event_queue.qsize() == 1
    listener.pump(timeout=0.1)
    assert pressed == [True]

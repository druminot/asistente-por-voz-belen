"""Listener de hotkey global con pynput (Quartz en macOS).

(Fase 2 — pendiente de implementación)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from pynput.keyboard import Key, KeyCode

from belen.config import get_settings


class HotkeyEvent(StrEnum):
    PRESSED = "pressed"
    RELEASED = "released"


@dataclass
class HotkeySpec:
    """Especificación de una hotkey parseada."""

    keys: tuple[Key | KeyCode, ...]

    @classmethod
    def parse(cls, spec: str) -> "HotkeySpec":
        """Parsea 'option+z+comma' → (Key.alt, KeyCode.from_char('z'), KeyCode.from_char(','))"""
        keys: list[Key | KeyCode] = []
        for token in spec.lower().split("+"):
            token = token.strip()
            if not token:
                continue
            keys.append(_parse_token(token))
        return cls(keys=tuple(keys))


def _parse_token(token: str) -> Key | KeyCode:
    """Convierte un token individual ('option', 'z', 'comma', etc.) a un objeto pynput."""
    aliases = {
        "option": Key.alt,
        "alt": Key.alt,
        "cmd": Key.cmd,
        "command": Key.cmd,
        "ctrl": Key.ctrl,
        "control": Key.ctrl,
        "shift": Key.shift,
        "space": Key.space,
        "tab": Key.tab,
        "enter": Key.enter,
        "esc": Key.esc,
        "escape": Key.esc,
    }
    if token in aliases:
        return aliases[token]

    special_chars = {
        "comma": ",",
        "period": ".",
        "slash": "/",
        "backslash": "\\",
        "semicolon": ";",
        "quote": "'",
        "bracket": "[",
        "bracketright": "]",
    }
    if token in special_chars:
        return KeyCode.from_char(special_chars[token])

    if len(token) == 1:
        return KeyCode.from_char(token)

    try:
        return Key[token]
    except KeyError as e:
        raise ValueError(f"Token de hotkey desconocido: {token!r}") from e


class HotkeyListener:
    """Listener de hotkey global.

    Uso:
        listener = HotkeyListener(spec="option+z+comma", mode="push_to_talk")
        listener.on_press(callback_pressed)
        listener.on_release(callback_released)
        listener.start()
    """

    def __init__(self, spec: str | None = None, mode: str | None = None) -> None:
        settings = get_settings()
        self._spec = HotkeySpec.parse(spec or settings.belen_hotkey)
        self._mode = mode or settings.belen_hotkey_mode
        self._pressed_keys: set[Key | KeyCode] = set()
        self._on_press_cb: Callable[[], None] | None = None
        self._on_release_cb: Callable[[], None] | None = None
        self._listener = None
        self._is_active: bool = False

    def on_press(self, callback: Callable[[], None]) -> None:
        self._on_press_cb = callback

    def on_release(self, callback: Callable[[], None]) -> None:
        self._on_release_cb = callback

    def start(self) -> None:
        """Arranca el listener (no-bloqueante)."""
        from pynput.keyboard import Listener

        self._listener = Listener(
            on_press=self._handle_press,
            on_release=self._handle_release,
        )
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def _handle_press(self, key: Key | KeyCode | None) -> None:
        if key is None:
            return
        self._pressed_keys.add(key)
        if self._matches() and self._on_press_cb is not None:
            if self._mode == "push_to_talk":
                self._on_press_cb()
            elif self._mode == "toggle" and not self._is_active:
                self._is_active = True
                self._on_press_cb()

    def _handle_release(self, key: Key | KeyCode | None) -> None:
        if key is None:
            return
        self._pressed_keys.discard(key)
        if self._mode == "push_to_talk" and self._on_release_cb is not None:
            if key in self._spec.keys:
                self._on_release_cb()
        elif self._mode == "toggle":
            if not self._matches():
                self._is_active = False
                if self._on_release_cb is not None:
                    self._on_release_cb()

    def _matches(self) -> bool:
        """True si la combinación actual coincide con la spec."""
        return all(k in self._pressed_keys for k in self._spec.keys)

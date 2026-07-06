"""Listener de hotkey global con pynput (Quartz en macOS).

Usa pynput que internamente usa Quartz en macOS. No requiere permisos
especiales para teclas normales, pero para inyectar input o controlar
el cursor necesitarías Accessibility.

Soporta dos modos:
- push_to_talk: callback on_press al apretar, on_release al soltar
- toggle: callback on_press alterna estado activo/inactivo
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from pynput.keyboard import Key, KeyCode

from belen.config import get_settings

if TYPE_CHECKING:
    from pynput.keyboard import Listener


class HotkeyMode(StrEnum):
    PUSH_TO_TALK = "push_to_talk"
    TOGGLE = "toggle"


def _parse_token(token: str) -> Key | KeyCode:
    """Convierte un token individual ('option', 'z', 'comma', etc.) a un objeto pynput."""
    aliases: dict[str, Key] = {
        "option": Key.alt,
        "alt": Key.alt,
        "opt": Key.alt,
        "cmd": Key.cmd,
        "command": Key.cmd,
        "ctrl": Key.ctrl,
        "control": Key.ctrl,
        "shift": Key.shift,
        "space": Key.space,
        "tab": Key.tab,
        "enter": Key.enter,
        "return": Key.enter,
        "esc": Key.esc,
        "escape": Key.esc,
        "backspace": Key.backspace,
        "delete": Key.delete,
        "up": Key.up,
        "down": Key.down,
        "left": Key.left,
        "right": Key.right,
    }
    if token in aliases:
        return aliases[token]

    special_chars: dict[str, str] = {
        "comma": ",",
        "period": ".",
        "dot": ".",
        "slash": "/",
        "backslash": "\\",
        "semicolon": ";",
        "quote": "'",
        "lbracket": "[",
        "rbracket": "]",
        "minus": "-",
        "equals": "=",
        "grave": "`",
    }
    if token in special_chars:
        return KeyCode.from_char(special_chars[token])

    if len(token) == 1:
        return KeyCode.from_char(token.lower())

    try:
        return Key[token]
    except KeyError as e:
        raise ValueError(f"Token de hotkey desconocido: {token!r}") from e


@dataclass(frozen=True)
class HotkeySpec:
    """Especificación de una hotkey parseada e inmutable."""

    keys: tuple[Key | KeyCode, ...]

    @classmethod
    def parse(cls, spec: str) -> HotkeySpec:
        """Parsea 'option+z+comma' → (Key.alt, KeyCode.from_char('z'), KeyCode.from_char(','))"""
        keys: list[Key | KeyCode] = []
        for token in spec.lower().split("+"):
            token = token.strip()
            if not token:
                continue
            keys.append(_parse_token(token))
        if not keys:
            raise ValueError(f"Hotkey vacía: {spec!r}")
        return cls(keys=tuple(keys))

    def __str__(self) -> str:
        return "+".join(_key_to_str(k) for k in self.keys)


def _key_to_str(key: Key | KeyCode) -> str:
    """Serializa una tecla a string legible."""
    if isinstance(key, Key):
        return key.name
    if isinstance(key, KeyCode):
        return key.char or "<unknown>"
    return str(key)


class HotkeyListener:
    """Listener de hotkey global.

    Uso:
        listener = HotkeyListener()
        listener.on_press(lambda: print("presionado"))
        listener.on_release(lambda: print("soltado"))
        listener.start()  # no-bloqueante
        # ...
        listener.stop()
    """

    def __init__(
        self,
        spec: str | HotkeySpec | None = None,
        mode: str | HotkeyMode | None = None,
    ) -> None:
        settings = get_settings()
        spec_str = spec if spec is not None else settings.belen_hotkey
        if isinstance(spec_str, str):
            self._spec = HotkeySpec.parse(spec_str)
        else:
            self._spec = spec_str

        mode_str = mode if mode is not None else settings.belen_hotkey_mode
        if isinstance(mode_str, str):
            self._mode = HotkeyMode(mode_str)
        else:
            self._mode = mode_str

        self._pressed_keys: set[Key | KeyCode] = set()
        self._on_press_cb: Callable[[], None] | None = None
        self._on_release_cb: Callable[[], None] | None = None
        self._listener: Listener | None = None
        self._lock = threading.Lock()
        self._is_active: bool = False

    @property
    def spec(self) -> HotkeySpec:
        return self._spec

    @property
    def mode(self) -> HotkeyMode:
        return self._mode

    @property
    def is_active(self) -> bool:
        return self._is_active

    def on_press(self, callback: Callable[[], None]) -> None:
        self._on_press_cb = callback

    def on_release(self, callback: Callable[[], None]) -> None:
        self._on_release_cb = callback

    def start(self) -> None:
        """Arranca el listener (no-bloqueante, daemon thread)."""
        if self._listener is not None:
            return
        from pynput.keyboard import Listener

        with self._lock:
            self._pressed_keys.clear()
            self._is_active = False

        self._listener = Listener(
            on_press=self._handle_press,
            on_release=self._handle_release,
        )
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        """Detiene el listener limpiamente."""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        with self._lock:
            self._pressed_keys.clear()
            self._is_active = False

    def _handle_press(self, key: Key | KeyCode | None) -> None:
        if key is None:
            return
        with self._lock:
            self._pressed_keys.add(key)
            matches = self._matches_locked()

            if self._mode == HotkeyMode.PUSH_TO_TALK:
                if matches and self._on_press_cb is not None:
                    self._is_active = True
                    cb = self._on_press_cb
                else:
                    return
            else:
                if matches and not self._is_active:
                    self._is_active = True
                    cb = self._on_press_cb
                else:
                    return

        if cb is not None:
            cb()

    def _handle_release(self, key: Key | KeyCode | None) -> None:
        if key is None:
            return
        with self._lock:
            self._pressed_keys.discard(key)
            if self._mode == HotkeyMode.PUSH_TO_TALK:
                if key in self._spec.keys and self._is_active:
                    self._is_active = False
                    cb = self._on_release_cb
                else:
                    return
            else:
                if not self._matches_locked() and self._is_active:
                    self._is_active = False
                    cb = self._on_release_cb
                else:
                    return

        if cb is not None:
            cb()

    def _matches_locked(self) -> bool:
        """True si la combinación actual coincide con la spec. Requiere lock."""
        return all(k in self._pressed_keys for k in self._spec.keys)

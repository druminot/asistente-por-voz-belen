"""Listener de hotkey global con pynput (Quartz en macOS).

Usa pynput que internamente usa Quartz en macOS. Requiere permiso de
Accesibilidad en macOS para capturar teclas del sistema.

Soporta dos modos:
- push_to_talk: callback on_press al apretar, on_release al soltar
- toggle: callback on_press alterna estado activo/inactivo

IMPORTANTE: los callbacks de pynput corren en un thread nativo del SO
(Quartz en macOS). Hacer trabajo bloqueante (abrir streams de audio,
correr subprocess, etc.) dentro de esos callbacks congela el listener
y puede detener la recepción de eventos. Por eso, el listener solo
encola eventos a una queue, y el método pump() los procesa desde
otro thread (típicamente el loop principal del pipeline).
"""

from __future__ import annotations

import queue
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
        # normalizar todos los KeyCode a minúsculas para matching consistente
        normalized = tuple(_normalize_key(k) for k in keys)
        return cls(keys=normalized)

    def __str__(self) -> str:
        return "+".join(_key_to_str(k) for k in self.keys)


def _key_to_str(key: Key | KeyCode) -> str:
    """Serializa una tecla a string legible."""
    if isinstance(key, Key):
        return key.name
    if isinstance(key, KeyCode):
        return key.char or "<unknown>"
    return str(key)


def _normalize_key(key: Key | KeyCode) -> Key | KeyCode:
    """Normaliza una tecla para comparación consistente.

    pynput en macOS reporta 'Z' (mayúscula) cuando shift está apretado,
    pero el spec se parsea como 'z' (minúscula). Esta función normaliza
    KeyCode a minúsculas para que el matching funcione con modifiers.
    """
    if isinstance(key, KeyCode) and key.char:
        # crear nuevo KeyCode con char minúscula
        lower = key.char.lower()
        if lower != key.char:
            return KeyCode.from_char(lower)
    return key


class HotkeyListener:
    """Listener de hotkey global.

    Diseño: pynput corre en su propio thread nativo. Los callbacks
    on_press/on_release SOLO encolan strings ("press" / "release") a
    una queue interna. El método pump() debe ser llamado desde otro
    thread (típicamente el loop del pipeline) para despachar los
    callbacks de usuario. Así se evita congelar el thread de pynput
    con trabajo bloqueante (audio, STT, opencode).

    Uso:
        listener = HotkeyListener()
        listener.on_press(lambda: print("presionado"))
        listener.on_release(lambda: print("soltado"))
        listener.start()
        # en otro thread:
        while running:
            listener.pump(timeout=0.05)
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
        self._event_queue: queue.Queue[str] = queue.Queue()
        self._last_error: str | None = None

    @property
    def spec(self) -> HotkeySpec:
        return self._spec

    @property
    def mode(self) -> HotkeyMode:
        return self._mode

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def last_error(self) -> str | None:
        """Último error capturado del listener (para diagnóstico)."""
        return self._last_error

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
        # limpiar queue de eventos pendientes
        while not self._event_queue.empty():
            try:
                self._event_queue.get_nowait()
            except queue.Empty:
                break

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

    def pump(self, timeout: float = 0.05) -> None:
        """Despacha eventos pendientes de la queue.

        Debe ser llamado desde el thread del pipeline (NO desde
        el thread de pynput). Los callbacks de usuario se ejecutan
        aquí, por lo que pueden hacer trabajo bloqueante sin
        afectar al listener.

        Args:
            timeout: segundos a esperar si la queue está vacía.
        """
        try:
            event = self._event_queue.get(timeout=timeout)
        except queue.Empty:
            return

        if event == "press":
            if self._on_press_cb is not None:
                try:
                    self._on_press_cb()
                except Exception as e:
                    self._last_error = f"on_press callback: {e}"
                    print(f"[ERROR] hotkey on_press callback: {e}")
        elif event == "release":
            if self._on_release_cb is not None:
                try:
                    self._on_release_cb()
                except Exception as e:
                    self._last_error = f"on_release callback: {e}"
                    print(f"[ERROR] hotkey on_release callback: {e}")

    def _handle_press(self, key: Key | KeyCode | None) -> None:
        """Callback de pynput. SOLO encola, NUNCA hace trabajo bloqueante."""
        if key is None:
            return
        try:
            with self._lock:
                self._pressed_keys.add(_normalize_key(key))
                matches = self._matches_locked()

                if self._mode == HotkeyMode.PUSH_TO_TALK:
                    if matches and not self._is_active:
                        self._is_active = True
                    else:
                        return
                else:  # toggle
                    if matches and not self._is_active:
                        self._is_active = True
                    else:
                        return

            self._event_queue.put("press")
        except Exception as e:
            self._last_error = f"handle_press: {e}"
            print(f"[ERROR] hotkey _handle_press: {e}", flush=True)

    def _handle_release(self, key: Key | KeyCode | None) -> None:
        """Callback de pynput. SOLO encola, NUNCA hace trabajo bloqueante."""
        if key is None:
            return
        try:
            norm_key = _normalize_key(key)
            with self._lock:
                self._pressed_keys.discard(norm_key)
                if self._mode == HotkeyMode.PUSH_TO_TALK:
                    if norm_key in self._spec.keys and self._is_active:
                        self._is_active = False
                    else:
                        return
                else:  # toggle
                    if not self._matches_locked() and self._is_active:
                        self._is_active = False
                    else:
                        return

            self._event_queue.put("release")
        except Exception as e:
            self._last_error = f"handle_release: {e}"
            print(f"[ERROR] hotkey _handle_release: {e}", flush=True)

    def _matches_locked(self) -> bool:
        """True si la combinación actual coincide con la spec. Requiere lock."""
        return all(k in self._pressed_keys for k in self._spec.keys)
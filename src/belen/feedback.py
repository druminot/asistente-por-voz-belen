"""Feedback sonoro y visual del estado de Belen.

(Fase 8 — UI flotante pendiente de implementación con rumps)
"""

from __future__ import annotations

import platform
import subprocess
import threading
from enum import StrEnum


class State(StrEnum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"


STATE_ICONS = {
    State.IDLE: "⚪",
    State.LISTENING: "🔴",
    State.PROCESSING: "🟡",
    State.SPEAKING: "🟢",
    State.ERROR: "❌",
}


def beep(frequency: int = 440, duration_ms: int = 100) -> None:
    """Reproduce un beep del sistema."""
    if platform.system() == "Darwin":
        subprocess.run(["afplay", "/System/Library/Sounds/Tink.aiff"], check=False)
    else:
        print("\a", end="", flush=True)


def beep_start() -> None:
    """Beep corto al empezar a escuchar."""
    if platform.system() == "Darwin":
        subprocess.run(["afplay", "/System/Library/Sounds/Purr.aiff"], check=False)
    else:
        print("\a", end="", flush=True)


def beep_stop() -> None:
    """Beep al terminar de escuchar."""
    if platform.system() == "Darwin":
        subprocess.run(["afplay", "/System/Library/Sounds/Pop.aiff"], check=False)
    else:
        print("\a", end="", flush=True)


def beep_error() -> None:
    """Beep de error."""
    if platform.system() == "Darwin":
        subprocess.run(["afplay", "/System/Library/Sounds/Basso.aiff"], check=False)
    else:
        print("\a\a", end="", flush=True)


class StatusDisplay:
    """Display de estado (consola por ahora; UI flotante en Fase 8)."""

    def __init__(self) -> None:
        self._state = State.IDLE
        self._lock = threading.Lock()

    @property
    def state(self) -> State:
        return self._state

    def set_state(self, state: State, message: str = "") -> None:
        with self._lock:
            self._state = state
        icon = STATE_ICONS.get(state, "?")
        label = state.value.upper()
        if message:
            print(f"\r[Belen] {icon} {label}: {message}          ", end="", flush=True)
        else:
            print(f"\r[Belen] {icon} {label}                      ", end="", flush=True)

    def idle(self) -> None:
        self.set_state(State.IDLE)

    def listening(self) -> None:
        self.set_state(State.LISTENING, "escuchando...")
        beep_start()

    def processing(self, text: str = "") -> None:
        self.set_state(State.PROCESSING, f"procesando: {text[:60]!r}" if text else "")

    def speaking(self, text: str = "") -> None:
        self.set_state(State.SPEAKING, f"hablando: {text[:60]!r}" if text else "")

    def error(self, msg: str = "") -> None:
        self.set_state(State.ERROR, msg)
        beep_error()

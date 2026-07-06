"""UI flotante (barra de menús de macOS) con rumps.

Muestra el estado actual de Belen como un ícono en la barra superior:
- ⚪ IDLE       (gris)
- 🔴 LISTENING  (rojo)
- 🟡 PROCESSING (amarillo)
- 🟢 SPEAKING   (verde)
- ❌ ERROR      (rojo)

Tiene menú con acciones:
- Activar/Desactivar wake word
- Ver estado
- Salir
"""

from __future__ import annotations

import threading
from enum import StrEnum
from typing import Any


class UIState(StrEnum):
    IDLE = "⚪"
    LISTENING = "🔴"
    PROCESSING = "🟡"
    SPEAKING = "🟢"
    ERROR = "❌"


STATE_LABELS = {
    UIState.IDLE: "Belen (idle)",
    UIState.LISTENING: "Belen (escuchando...)",
    UIState.PROCESSING: "Belen (procesando...)",
    UIState.SPEAKING: "Belen (hablando...)",
    UIState.ERROR: "Belen (error)",
}


class FloatingUI:
    """UI flotante en la barra de menús de macOS.

    Uso:
        ui = FloatingUI()
        ui.start()  # bloqueante (corre el event loop de rumps)
        # O usar ui.update(state) desde otro thread
    """

    def __init__(self) -> None:
        self._state = UIState.IDLE
        self._app: Any = None
        self._menu_item: Any = None
        self._wakeword_item: Any = None
        self._running = False
        self._lock = threading.Lock()
        self._wakeword_enabled = True
        self._on_toggle_wakeword: Any = None
        self._on_quit: Any = None

    def set_callbacks(
        self,
        on_toggle_wakeword: Any = None,
        on_quit: Any = None,
    ) -> None:
        self._on_toggle_wakeword = on_toggle_wakeword
        self._on_quit = on_quit

    @property
    def state(self) -> UIState:
        return self._state

    def start(self) -> None:
        """Arranca la UI (bloqueante, en el thread principal)."""
        try:
            import rumps
        except ImportError as e:
            raise RuntimeError(
                "rumps no instalado. En macOS: pip install rumps. "
                "En otros OS: la UI flotante no funciona."
            ) from e

        self._app = rumps.App("Belen", title=str(UIState.IDLE))
        self._menu_item = rumps.MenuItem("Estado: idle")
        self._wakeword_item = rumps.MenuItem(
            "Wake word activado",
            callback=self._handle_toggle_wakeword,
        )
        self._wakeword_item.state = self._wakeword_enabled

        self._app.menu = [
            self._menu_item,
            None,
            self._wakeword_item,
            rumps.MenuItem("Salir", callback=self._handle_quit),
        ]

        self._running = True
        self._app.run()

    def start_async(self) -> threading.Thread:
        """Arranca la UI en un thread daemon (no-bloqueante)."""
        thread = threading.Thread(target=self.start, daemon=True)
        thread.start()
        return thread

    def update(self, state: UIState, message: str = "") -> None:
        """Actualiza el estado desde cualquier thread."""
        with self._lock:
            self._state = state
            title = str(state)
            if message:
                label = f"{STATE_LABELS[state]}: {message[:30]}"
            else:
                label = STATE_LABELS[state]

        if self._app is not None:
            try:
                import rumps

                self._app.title = title
                if self._menu_item is not None:
                    self._menu_item.title = label
            except Exception:
                pass

    def idle(self) -> None:
        self.update(UIState.IDLE)

    def listening(self) -> None:
        self.update(UIState.LISTENING, "escuchando...")

    def processing(self, text: str = "") -> None:
        self.update(UIState.PROCESSING, text)

    def speaking(self, text: str = "") -> None:
        self.update(UIState.SPEAKING, text)

    def error(self, msg: str = "") -> None:
        self.update(UIState.ERROR, msg)

    def set_wakeword_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._wakeword_enabled = enabled
        if self._wakeword_item is not None:
            try:
                self._wakeword_item.state = enabled
            except Exception:
                pass

    def _handle_toggle_wakeword(self, sender: Any) -> None:
        new_state = not self._wakeword_enabled
        self.set_wakeword_enabled(new_state)
        if self._on_toggle_wakeword is not None:
            try:
                self._on_toggle_wakeword(new_state)
            except Exception as e:
                print(f"[UI] Callback wakeword falló: {e}")

    def _handle_quit(self, sender: Any) -> None:
        if self._on_quit is not None:
            try:
                self._on_quit()
            except Exception as e:
                print(f"[UI] Callback quit falló: {e}")
        if self._app is not None:
            rumps.quit_application(self._app)


class ConsoleUI:
    """UI de fallback a consola (cuando no estamos en macOS o no hay rumps)."""

    def __init__(self) -> None:
        self._state = UIState.IDLE
        self._lock = threading.Lock()
        self._wakeword_enabled = True

    @property
    def state(self) -> UIState:
        return self._state

    def start(self) -> None:
        print("[Belen UI] Modo consola. Ctrl+C para salir.")

    def start_async(self) -> threading.Thread:
        thread = threading.Thread(target=self.start, daemon=True)
        thread.start()
        return thread

    def update(self, state: UIState, message: str = "") -> None:
        with self._lock:
            self._state = state
        label = STATE_LABELS[state]
        if message:
            print(f"\r[{state}] {label}: {message}          ", end="", flush=True)
        else:
            print(f"\r[{state}] {label}                      ", end="", flush=True)

    def idle(self) -> None:
        self.update(UIState.IDLE)

    def listening(self) -> None:
        self.update(UIState.LISTENING, "escuchando...")

    def processing(self, text: str = "") -> None:
        self.update(UIState.PROCESSING, text)

    def speaking(self, text: str = "") -> None:
        self.update(UIState.SPEAKING, text)

    def error(self, msg: str = "") -> None:
        self.update(UIState.ERROR, msg)

    def set_wakeword_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._wakeword_enabled = enabled


def get_ui() -> Any:
    """Devuelve FloatingUI en macOS (si rumps está), sino ConsoleUI."""
    import platform
    import sys

    if platform.system() != "Darwin":
        return ConsoleUI()

    try:
        import rumps  # noqa: F401

        return FloatingUI()
    except ImportError:
        return ConsoleUI()

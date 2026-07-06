"""Pipeline principal — orquesta el flujo end-to-end.

(Fase 9 — pendiente de implementación)
"""

from __future__ import annotations

from belen.config import get_settings


class Pipeline:
    """Coordina: hotkey → recorder → STT → brain → TTS → speaker."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._running = False

    def start(self) -> None:
        """Arranca el pipeline (todas las fases)."""
        self._running = True

    def stop(self) -> None:
        """Detiene el pipeline limpiamente."""
        self._running = False

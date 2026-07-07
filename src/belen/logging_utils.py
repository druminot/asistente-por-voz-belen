"""Logging estructurado para Belen con timestamps.

Escribe a /tmp/belen_runtime.log con nivel de detalle controlable
por la variable de entorno BELEN_LOG_LEVEL (debug, info, warn, error).
"""

from __future__ import annotations

import datetime
import os
import threading
from collections.abc import Callable

_LOG_FILE = "/tmp/belen_runtime.log"
_LOCK = threading.Lock()
_LEVELS = {"debug": 10, "info": 20, "warn": 30, "error": 40}
_CURRENT_LEVEL = _LEVELS.get(
    os.environ.get("BELEN_LOG_LEVEL", "info").lower(), 20
)


def _set_level(level: str) -> None:
    global _CURRENT_LEVEL
    _CURRENT_LEVEL = _LEVELS.get(level.lower(), 20)


def _log(level: str, tag: str, msg: str) -> None:
    if _LEVELS.get(level, 20) < _CURRENT_LEVEL:
        return
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"{ts} [{level.upper():5}] [{tag:12}] {msg}"
    with _LOCK:
        try:
            with open(_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass


def debug(tag: str, msg: str) -> None:
    _log("debug", tag, msg)


def info(tag: str, msg: str) -> None:
    _log("info", tag, msg)


def warn(tag: str, msg: str) -> None:
    _log("warn", tag, msg)


def error(tag: str, msg: str) -> None:
    _log("error", tag, msg)


def clear() -> None:
    """Vacía el log (para empezar limpio en cada run)."""
    with _LOCK:
        try:
            open(_LOG_FILE, "w", encoding="utf-8").close()
        except Exception:
            pass


def tail(lines: int = 30) -> str:
    """Devuelve las últimas N líneas del log."""
    try:
        with open(_LOG_FILE, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        return "".join(all_lines[-lines:])
    except Exception:
        return ""


def install_excepthook() -> None:
    """Instala un hook global para capturar excepciones no manejadas al log."""
    import sys

    def hook(exc_type, exc_value, exc_tb):
        import traceback as tb
        msg = "".join(tb.format_exception(exc_type, exc_value, exc_tb))
        error("CRASH", f"Excepción no capturada:\n{msg}")

    sys.excepthook = hook


__all__ = ["debug", "info", "warn", "error", "clear", "tail", "install_excepthook", "_set_level"]
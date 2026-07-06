"""Cerebro: wrapper de opencode CLI como subproceso.

(Fase 4 — pendiente de integración con opencode)
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path
from typing import Any

from belen.config import get_settings


class OpenCodeBrain:
    """Wrapper de opencode CLI en modo no-interactivo.

    opencode acepta un prompt por stdin/argumento y devuelve la respuesta
    por stdout. Lo invocamos como subproceso desde Python.
    """

    def __init__(
        self,
        bin_path: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        cwd: Path | None = None,
        allow_edit: bool | None = None,
    ) -> None:
        settings = get_settings()
        self._bin = bin_path or settings.opencode_bin
        self._model = model or settings.opencode_model
        self._base_url = base_url or settings.opencode_base_url
        self._cwd = cwd
        self._allow_edit = allow_edit if allow_edit is not None else settings.belen_allow_file_edit

    def is_available(self) -> bool:
        return shutil.which(self._bin) is not None

    async def ask(
        self,
        prompt: str,
        cwd: Path | None = None,
        timeout: float = 120.0,
    ) -> str:
        """Envía un prompt a opencode y devuelve la respuesta."""
        if not self.is_available():
            raise RuntimeError(
                f"opencode no encontrado en PATH (buscado: {self._bin!r}). "
                f"Instalá con: curl -fsSL https://opencode.ai/install | bash"
            )

        workdir = cwd or self._cwd
        args = [self._bin, "run", "--model", self._model, prompt]

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(workdir) if workdir else None,
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError as e:
            proc.kill()
            await proc.wait()
            raise RuntimeError(f"opencode timeout después de {timeout}s") from e

        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"opencode exit code {proc.returncode}: {err}")

        return stdout.decode("utf-8", errors="replace").strip()

    def ask_sync(self, prompt: str, cwd: Path | None = None, timeout: float = 120.0) -> str:
        """Versión sincrónica de ask()."""
        if not self.is_available():
            raise RuntimeError(
                f"opencode no encontrado en PATH (buscado: {self._bin!r})"
            )

        workdir = cwd or self._cwd
        args = [self._bin, "run", "--model", self._model, prompt]

        result = subprocess.run(
            args,
            input="",
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(workdir) if workdir else None,
        )

        if result.returncode != 0:
            raise RuntimeError(f"opencode exit code {result.returncode}: {result.stderr.strip()}")

        return result.stdout.strip()

    def list_providers(self) -> dict[str, Any]:
        """Información de configuración."""
        return {
            "bin": self._bin,
            "model": self._model,
            "base_url": self._base_url,
            "cwd": str(self._cwd) if self._cwd else None,
            "allow_edit": self._allow_edit,
            "available": self.is_available(),
        }

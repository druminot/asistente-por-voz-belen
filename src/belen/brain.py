"""Cerebro: wrapper de opencode CLI como subproceso.

Sintaxis de opencode:
  opencode run -m <provider>/<model> "<prompt>"

Salida por stdout. Devuelve la respuesta del modelo.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from belen.config import get_settings


@dataclass
class BrainResponse:
    text: str
    model: str
    duration_seconds: float
    raw_stdout: str
    raw_stderr: str


class OpenCodeBrain:
    """Wrapper de opencode CLI en modo no-interactivo.

    Uso:
        brain = OpenCodeBrain()
        response = brain.ask("explicame este código", cwd=Path("/path/to/proj"))
        print(response.text)
    """

    def __init__(
        self,
        bin_path: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        cwd: Path | None = None,
        allow_edit: bool | None = None,
        agent: str | None = None,
    ) -> None:
        settings = get_settings()
        self._bin = bin_path or settings.opencode_bin
        self._model = model or settings.opencode_model
        self._base_url = base_url or settings.opencode_base_url
        self._cwd = cwd
        self._allow_edit = allow_edit if allow_edit is not None else settings.belen_allow_file_edit
        self._agent = agent or (settings.opencode_agent or None)

    def is_available(self) -> bool:
        return shutil.which(self._bin) is not None

    def _build_args(self, prompt: str) -> list[str]:
        args = [self._bin, "run", "-m", self._model]
        if self._agent is not None:
            args += ["--agent", self._agent]
        if prompt:
            args.append(prompt)
        return args

    async def ask(
        self,
        prompt: str,
        cwd: Path | None = None,
        timeout: float = 120.0,
    ) -> BrainResponse:
        """Envía un prompt a opencode (async) y devuelve BrainResponse."""
        import time

        if not self.is_available():
            raise RuntimeError(
                f"opencode no encontrado en PATH (buscado: {self._bin!r}). "
                f"Instalá con: curl -fsSL https://opencode.ai/install | bash"
            )

        workdir = cwd or self._cwd
        args = self._build_args(prompt)
        t0 = time.monotonic()

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

        duration = time.monotonic() - t0
        out_text = stdout.decode("utf-8", errors="replace")
        err_text = stderr.decode("utf-8", errors="replace")

        if proc.returncode != 0:
            raise RuntimeError(f"opencode exit code {proc.returncode}: {err_text.strip()}")

        return BrainResponse(
            text=out_text.strip(),
            model=self._model,
            duration_seconds=duration,
            raw_stdout=out_text,
            raw_stderr=err_text,
        )

    def ask_sync(
        self,
        prompt: str,
        cwd: Path | None = None,
        timeout: float = 120.0,
    ) -> BrainResponse:
        """Versión sincrónica de ask()."""
        import time

        if not self.is_available():
            raise RuntimeError(f"opencode no encontrado en PATH (buscado: {self._bin!r})")

        workdir = cwd or self._cwd
        args = self._build_args(prompt)
        t0 = time.monotonic()

        result = subprocess.run(
            args,
            input="",
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(workdir) if workdir else None,
        )

        duration = time.monotonic() - t0
        if result.returncode != 0:
            raise RuntimeError(f"opencode exit code {result.returncode}: {result.stderr.strip()}")

        return BrainResponse(
            text=result.stdout.strip(),
            model=self._model,
            duration_seconds=duration,
            raw_stdout=result.stdout,
            raw_stderr=result.stderr,
        )

    def list_models(self) -> list[str]:
        """Lista modelos disponibles (subprocess a `opencode models`)."""
        if not self.is_available():
            return []
        result = subprocess.run(
            [self._bin, "models"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def info(self) -> dict[str, Any]:
        return {
            "bin": self._bin,
            "model": self._model,
            "base_url": self._base_url,
            "cwd": str(self._cwd) if self._cwd else None,
            "allow_edit": self._allow_edit,
            "agent": self._agent,
            "available": self.is_available(),
        }


class MockBrain:
    """Brain mock para tests — devuelve respuesta fija."""

    def __init__(self, response: str = "mock brain response") -> None:
        self._response = response
        self._calls: list[dict[str, Any]] = []

    def is_available(self) -> bool:
        return True

    def ask_sync(self, prompt: str, cwd: Path | None = None, timeout: float = 120.0) -> BrainResponse:
        import time
        t0 = time.monotonic()
        time.sleep(0.001)
        self._calls.append({"prompt": prompt, "cwd": str(cwd) if cwd else None})
        return BrainResponse(
            text=self._response,
            model="mock",
            duration_seconds=time.monotonic() - t0,
            raw_stdout=self._response,
            raw_stderr="",
        )

    async def ask(self, prompt: str, cwd: Path | None = None, timeout: float = 120.0) -> BrainResponse:
        return self.ask_sync(prompt, cwd, timeout)

    def info(self) -> dict[str, Any]:
        return {"model": "mock", "available": True}

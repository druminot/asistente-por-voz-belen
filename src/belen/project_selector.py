"""Selector de proyecto por voz.

(Fase 7 — pendiente de implementación completa)

El usuario puede decir:
- "Belen, andá al proyecto <nombre>"
- "Belen, abrí <nombre>"
- "Belen, cambiá a <nombre>"

Y Belen busca en BELEN_PROJECTS_DIR una carpeta que matchee.
"""

from __future__ import annotations

import re
from pathlib import Path

from belen.config import get_settings


class ProjectSelector:
    """Selector por voz del proyecto activo."""

    PATTERNS = [
        re.compile(r"(?:andá|anda|ir|cambia[ár]?|abrí|abre|usá|usa)\s+(?:al?|a)\s+proyecto\s+(.+)", re.I),
        re.compile(r"proyecto\s+(.+?)(?:\s+por favor|\s+ya)?$", re.I),
        re.compile(r"^(?:al?|a)\s+(.+)$", re.I),
    ]

    def __init__(self, projects_dir: Path | None = None) -> None:
        settings = get_settings()
        self._projects_dir = projects_dir or settings.belen_projects_dir

    def parse_command(self, text: str) -> str | None:
        """Si `text` es un comando de cambio de proyecto, devuelve el nombre. Si no, None."""
        for pattern in self.PATTERNS:
            m = pattern.search(text.strip())
            if m:
                return m.group(1).strip().rstrip(".")
        return None

    def list_projects(self) -> list[Path]:
        """Lista subcarpetas de projects_dir (excluye ocultas)."""
        if not self._projects_dir.exists():
            return []
        return sorted(
            p for p in self._projects_dir.iterdir()
            if p.is_dir() and not p.name.startswith(".")
        )

    def find_project(self, name: str) -> Path | None:
        """Busca un proyecto por nombre (case-insensitive, fuzzy)."""
        name_norm = self._normalize(name)
        for project in self.list_projects():
            if self._normalize(project.name) == name_norm:
                return project
        for project in self.list_projects():
            if name_norm in self._normalize(project.name):
                return project
        return None

    def select(self, text: str) -> Path | None:
        """Pipeline: parsea el texto y devuelve el path del proyecto."""
        name = self.parse_command(text)
        if name is None:
            return None
        return self.find_project(name)

    @staticmethod
    def _normalize(s: str) -> str:
        return s.lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").replace("ñ", "n").strip()

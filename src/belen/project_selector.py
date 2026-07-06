"""Selector de proyecto por voz.

El usuario puede decir cosas como:
- "Belen, andá al proyecto <nombre>"
- "Belen, abrí <nombre>"
- "Belen, cambiá a <nombre>"

Belén busca en BELEN_PROJECTS_DIR una carpeta que matchee (fuzzy).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from belen.config import get_settings


def _normalize(s: str) -> str:
    """Normaliza string: lowercase + sin acentos."""
    s = s.lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s


@dataclass(frozen=True)
class ProjectMatch:
    name: str
    path: Path
    score: float  # 0.0 a 1.0


class ProjectSelector:
    """Selector por voz del proyecto activo.

    Uso:
        sel = ProjectSelector()
        match = sel.select("andá al proyecto smart-home")
        if match:
            print(f"Cambiando a {match.path}")
    """

    PATTERNS: tuple[re.Pattern[str], ...] = (
        re.compile(r"(?:andá|anda|ir|ve|cambia[ár]?|abrí|abre|usá|usa|carga|cargá|entrá|entra)\s+(?:al?|a|al)\s+proyecto\s+(.+)", re.I),
        re.compile(r"proyecto\s+(.+?)(?:\s+por favor|\s+ya)?$", re.I),
        re.compile(r"^(?:andá|anda|ir|ve|cambia[ár]?|abrí|abre|usá|usa|carga|cargá|entrá|entra)\s+(?:al?|a|al)\s+(.+?)(?:\s+por favor|\s+ya)?$", re.I),
        re.compile(r"^(?:andá|anda|ir|ve|cambia[ár]?|abrí|abre|usá|usa|carga|cargá|entrá|entra)\s+(.+?)(?:\s+por favor|\s+ya)?$", re.I),
    )

    KEYWORDS_NAVEGACION = {
        "andá", "anda", "ir", "ve", "cambia", "cambiar", "cambiá", "cambiar",
        "abrí", "abre", "abrir", "usá", "usa", "usar", "carga", "cargá", "cargar",
        "entrá", "entra", "entrar",
    }

    def __init__(self, projects_dir: Path | None = None) -> None:
        settings = get_settings()
        self._projects_dir = projects_dir or settings.belen_projects_dir

    @property
    def projects_dir(self) -> Path:
        return self._projects_dir

    def parse_command(self, text: str) -> str | None:
        """Si `text` es un comando de proyecto, devuelve el nombre. Si no, None."""
        if not text:
            return None

        text = text.strip()
        for pattern in self.PATTERNS:
            m = pattern.search(text)
            if m:
                name = m.group(1).strip()
                # Limpiar puntuación incrustada al final o en cualquier parte
                name = re.sub(r"[,;:\.!?]+", "", name)
                # Quitar coletillas tipo "por favor", "ya", "rápido"
                name = re.sub(r"\s+(?:por favor|ya|rápido|rapido)\s*$", "", name, flags=re.I)
                name = name.strip()
                if name and _normalize(name) not in self.KEYWORDS_NAVEGACION:
                    return name
        return None

    def list_projects(self) -> list[Path]:
        """Lista subcarpetas de projects_dir (excluye ocultas y archivos)."""
        if not self._projects_dir.exists():
            return []
        return sorted(
            p for p in self._projects_dir.iterdir()
            if p.is_dir() and not p.name.startswith(".")
        )

    def find_project(self, name: str) -> ProjectMatch | None:
        """Busca un proyecto por nombre (case/accent-insensitive, fuzzy)."""
        if not name:
            return None

        name_norm = _normalize(name)
        projects = self.list_projects()

        for project in projects:
            if _normalize(project.name) == name_norm:
                return ProjectMatch(name=project.name, path=project, score=1.0)

        for project in projects:
            proj_norm = _normalize(project.name)
            if name_norm in proj_norm or proj_norm in name_norm:
                score = len(name_norm) / max(len(proj_norm), 1)
                return ProjectMatch(name=project.name, path=project, score=score)

        best: ProjectMatch | None = None
        for project in projects:
            proj_norm = _normalize(project.name)
            score = self._similarity(name_norm, proj_norm)
            if score > 0.6 and (best is None or score > best.score):
                best = ProjectMatch(name=project.name, path=project, score=score)
        return best

    def select(self, text: str) -> ProjectMatch | None:
        """Pipeline: parsea el texto y devuelve el mejor match."""
        name = self.parse_command(text)
        if name is None:
            return None
        return self.find_project(name)

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """Similitud simple basada en intersección de caracteres."""
        if not a or not b:
            return 0.0
        set_a = set(a)
        set_b = set(b)
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union) if union else 0.0

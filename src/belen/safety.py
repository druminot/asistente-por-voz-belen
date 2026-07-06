"""Validaciones de seguridad antes de pasar prompts a opencode.

Modo permitido: lectura + edición de archivos. Sin comandos bash.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

BLOCKED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\brm\s+-rf?\b", re.I),
    re.compile(r"\bsudo\b", re.I),
    re.compile(r"\bchmod\b", re.I),
    re.compile(r"\bchown\b", re.I),
    re.compile(r"\bcurl\b.*\|\s*(?:sh|bash|zsh)", re.I),
    re.compile(r"\bwget\b.*-.*O\s*-.*\|\s*(?:sh|bash|zsh)", re.I),
    re.compile(r"\bformat\b.*disk", re.I),
    re.compile(r"\bdd\s+if=", re.I),
    re.compile(r">\s*/dev/(?!null)", re.I),
    re.compile(r"\b(mkfs|fdisk|parted)\b", re.I),
    re.compile(r"\b(shutdown|reboot|halt)\b", re.I),
    re.compile(r":(){", re.I),
]

MAX_PROMPT_LENGTH = 4096


@dataclass
class ValidationResult:
    ok: bool
    reason: str = ""


def validate_prompt(text: str, allowed_root: Path | None = None) -> ValidationResult:
    """Valida que el prompt sea seguro antes de enviarlo a opencode."""
    stripped = text.strip()

    if not stripped:
        return ValidationResult(ok=False, reason="El prompt está vacío.")

    if len(stripped) > MAX_PROMPT_LENGTH:
        return ValidationResult(
            ok=False,
            reason=f"Prompt demasiado largo ({len(stripped)} chars > {MAX_PROMPT_LENGTH}).",
        )

    for pattern in BLOCKED_PATTERNS:
        if pattern.search(stripped):
            return ValidationResult(
                ok=False,
                reason=f"Comando bloqueado por seguridad (patrón: {pattern.pattern!r}).",
            )

    return ValidationResult(ok=True)

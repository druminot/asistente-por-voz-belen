"""CLI principal de Belen con typer."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from belen import __version__
from belen.config import HotkeyMode, STTEngine, TTSEngine, get_settings

app = typer.Typer(
    name="belen",
    help="Asistente por voz para macOS powered by opencode + Ollama",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"[bold green]belen[/bold green] v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", "-v", callback=_version_callback, is_eager=True),
    ] = None,
) -> None:
    """Belen — asistente por voz para macOS."""


@app.command()
def start(
    project: Annotated[
        Optional[Path],
        typer.Option("--project", "-p", help="Proyecto sobre el que trabajar"),
    ] = None,
    no_ui: Annotated[
        bool,
        typer.Option("--no-ui", help="Desactivar indicador flotante"),
    ] = False,
    no_wakeword: Annotated[
        bool,
        typer.Option("--no-wakeword", help="Desactivar wake word"),
    ] = False,
) -> None:
    """Inicia el daemon de Belen."""
    s = get_settings()
    console.print(
        Panel.fit(
            f"[bold green]Belen v{__version__}[/bold green]\n"
            f"Hotkey: [cyan]{s.belen_hotkey}[/cyan] ({s.belen_hotkey_mode.value})\n"
            f"Wake word: [{'green' if s.belen_wakeword_enabled and not no_wakeword else 'red'}]"
            f"{'on' if s.belen_wakeword_enabled and not no_wakeword else 'off'}[/] "
            f"({s.belen_wakeword!r})\n"
            f"STT: [cyan]{s.belen_stt_engine.value}[/cyan]\n"
            f"TTS: [cyan]{s.belen_tts_engine.value}[/cyan]\n"
            f"Cerebro: [cyan]opencode[/cyan] ({s.opencode_model})\n"
            f"UI flotante: [{'green' if s.belen_floating_ui and not no_ui else 'red'}]"
            f"{'on' if s.belen_floating_ui and not no_ui else 'off'}[/]",
            title="Estado",
            border_style="green",
        )
    )
    console.print("\n[yellow]⚠ Fase 1 (esqueleto) — el daemon aún no está implementado.[/yellow]")
    console.print("Próximas fases: hotkey + recorder (F2), STT (F3), opencode (F4), TTS (F5).")


@app.command()
def config() -> None:
    """Muestra la configuración actual."""
    s = get_settings()
    table = Table(title="Configuración de Belen", show_header=True, header_style="bold magenta")
    table.add_column("Clave", style="cyan")
    table.add_column("Valor", style="green")

    table.add_row("opencode_bin", s.opencode_bin)
    table.add_row("opencode_model", s.opencode_model)
    table.add_row("opencode_base_url", s.opencode_base_url)
    table.add_row("opencode_agent", s.opencode_agent or "(default)")
    table.add_row("belen_hotkey", s.belen_hotkey)
    table.add_row("belen_hotkey_mode", s.belen_hotkey_mode.value)
    table.add_row("belen_wakeword_enabled", str(s.belen_wakeword_enabled))
    table.add_row("belen_wakeword", s.belen_wakeword)
    table.add_row("belen_stt_engine", s.belen_stt_engine.value)
    table.add_row("belen_stt_lang", s.belen_stt_lang)
    table.add_row("belen_whisper_model", s.belen_whisper_model)
    table.add_row("belen_tts_engine", s.belen_tts_engine.value)
    table.add_row("belen_tts_voice", s.belen_tts_voice)
    table.add_row("belen_projects_dir", str(s.belen_projects_dir))
    table.add_row("belen_default_project", s.belen_default_project or "(vacío)")
    table.add_row("belen_floating_ui", str(s.belen_floating_ui))
    table.add_row("belen_sample_rate", str(s.belen_sample_rate))
    table.add_row("belen_allow_file_edit", str(s.belen_allow_file_edit))
    table.add_row("belen_log_level", s.belen_log_level)

    console.print(table)


@app.command()
def check() -> None:
    """Verifica el entorno: Python, opencode, micrófono, modelos."""
    import shutil
    import subprocess

    console.print("[bold]Verificando entorno...[/bold]\n")

    py_version = sys.version_info
    py_ok = py_version >= (3, 11)
    console.print(
        f"  Python: [cyan]{py_version.major}.{py_version.minor}.{py_version.micro}[/cyan] "
        f"[{'green' if py_ok else 'red'}]{'✓' if py_ok else '✗ (necesita >= 3.11)'}[/]"
    )

    opencode_path = shutil.which("opencode")
    console.print(
        f"  opencode: [{'green' if opencode_path else 'yellow'}]"
        f"{opencode_path or 'no encontrado en PATH'}[/]"
    )
    if opencode_path:
        try:
            result = subprocess.run(
                ["opencode", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            version = result.stdout.strip() or result.stderr.strip()
            console.print(f"    versión: [cyan]{version}[/cyan]")
        except Exception as e:
            console.print(f"    [red]error: {e}[/red]")

    try:
        import sounddevice as sd

        devices = sd.query_devices()
        input_devices = [d for d in devices if d["max_input_channels"] > 0]
        console.print(
            f"  Micrófonos detectados: [cyan]{len(input_devices)}[/cyan] "
            f"[green]✓[/green]"
        )
        for i, d in enumerate(input_devices[:3]):
            console.print(f"    [{i}] {d['name']}")
    except Exception as e:
        console.print(f"  sounddevice: [red]✗ {e}[/red]")

    s = get_settings()
    projects_dir = s.belen_projects_dir
    console.print(
        f"  Carpeta de proyectos: [cyan]{projects_dir}[/cyan] "
        f"[{'green' if projects_dir.exists() else 'red'}]"
        f"{'✓ existe' if projects_dir.exists() else '✗ no existe'}[/]"
    )

    console.print("\n[bold]Entorno verificado.[/bold]")


@app.command()
def models() -> None:
    """Lista los modelos disponibles en opencode."""
    from belen.brain import OpenCodeBrain

    brain = OpenCodeBrain()
    if not brain.is_available():
        console.print("[red]opencode no encontrado en PATH.[/red]")
        raise typer.Exit(1)

    console.print("[bold]Modelos disponibles en opencode:[/bold]\n")
    for m in brain.list_models():
        console.print(f"  [cyan]{m}[/cyan]")


if __name__ == "__main__":
    app()

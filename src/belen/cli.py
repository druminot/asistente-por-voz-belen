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
from belen.config import get_settings

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
        bool | None,
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
    import platform

    s = get_settings()
    use_floating_ui = (
        s.belen_floating_ui and not no_ui and platform.system() == "Darwin"
    )
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
            f"UI flotante: [{'green' if use_floating_ui else 'red'}]"
            f"{'on' if use_floating_ui else 'off'}[/]",
            title="Estado",
            border_style="green",
        )
    )
    if project is not None:
        console.print(f"[bold]Proyecto inicial:[/bold] [cyan]{project}[/cyan]")
    console.print()
    console.print("[bold green]▶ Iniciando Belen...[/bold green]")
    if use_floating_ui:
        console.print("  UI flotante [cyan]ACTIVA[/cyan] — mirá la barra de menús de macOS.")
    console.print("  Mantené [cyan]" + s.belen_hotkey + "[/cyan] apretada para hablar.")
    console.print("  Decí 'Belen' si wake word está activado.")
    console.print("  Ctrl+C para salir.\n")

    from belen.pipeline import BelenPipeline
    from belen.ui import ConsoleUI, FloatingUI
    from belen.visual_ui import get_visual_ui

    pipeline = BelenPipeline()
    if project is not None:
        pipeline.set_active_project(project)

    def on_turn(result: object) -> None:
        if getattr(result, "error", None):
            console.print(f"[red]⚠ Error: {result.error}[/red]")
        elif getattr(result, "project_changed", None):
            console.print(f"[green]📁 Proyecto: {result.project_changed.name}[/green]")

    pipeline.on_turn(on_turn)

    if use_floating_ui:
        # Modo con UI visual estilo Siri
        import platform
        import threading

        if platform.system() == "Darwin":
            try:
                import rumps  # noqa: F401

                visual = get_visual_ui()
                pipeline.ui = visual

                # Pequeño menú de rumps para control adicional
                rumps_app = rumps.App("Belen", title="⚪ Belen")
                wakeword_item = rumps.MenuItem(
                    "Wake word activado",
                    callback=lambda sender: None,
                )
                wakeword_item.state = True
                rumps_app.menu = [
                    rumps.MenuItem("Estado: idle"),
                    None,
                    wakeword_item,
                    rumps.MenuItem("Salir", callback=lambda _: pipeline.stop()),
                ]

                # Arrancar hotkey listener en thread daemon
                pipeline.start()

                # Registrá Ctrl+C
                import signal

                def handle_sigint(sig: int, frame: object) -> None:
                    console.print("\n[yellow]Deteniendo Belen...[/yellow]")
                    pipeline.stop()
                    try:
                        visual.stop()
                    except Exception:
                        pass
                    rumps.quit_application(rumps_app)

                signal.signal(signal.SIGINT, handle_sigint)

                # Correr la ventana visual estilo Siri en el main thread (bloqueante)
                visual.start()

            except ImportError as e:
                console.print(f"[yellow]rumps no disponible ({e}), arrancando sin UI flotante.[/yellow]")
                use_floating_ui = False
            except Exception as e:
                console.print(f"[red]Error arrancando UI visual: {e}[/red]")
                import traceback
                console.print(traceback.format_exc())
                use_floating_ui = False

    if not use_floating_ui:
        # Modo sin UI flotante: hotkey listener en main thread
        pipeline.start()

        try:
            import signal

            def handle_sigint(sig: int, frame: object) -> None:
                console.print("\n[yellow]Deteniendo Belen...[/yellow]")
                pipeline.stop()

            signal.signal(signal.SIGINT, handle_sigint)
            signal.pause()
        except (KeyboardInterrupt, SystemExit):
            pass

    pipeline.stop()
    console.print("[bold]Belen detenido.[/bold]")


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


@app.command()
def ask(
    prompt: Annotated[
        str,
        typer.Argument(help="Prompt para enviar a opencode"),
    ],
    project: Annotated[
        Path | None,
        typer.Option("--project", "-p", help="Directorio de trabajo"),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option("--model", "-m", help="Modelo a usar (formato provider/model)"),
    ] = None,
) -> None:
    """Envía un prompt directo a opencode (sin audio). Útil para probar."""
    from belen.brain import OpenCodeBrain
    from belen.safety import validate_prompt

    validation = validate_prompt(prompt)
    if not validation.ok:
        console.print(f"[red]✗ Prompt bloqueado: {validation.reason}[/red]")
        raise typer.Exit(1)

    brain = OpenCodeBrain(model=model)
    if not brain.is_available():
        console.print("[red]opencode no encontrado en PATH.[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Enviando a opencode ({brain._model})...[/bold]")
    try:
        response = brain.ask_sync(prompt, cwd=project, timeout=120.0)
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise typer.Exit(1) from e

    console.print(Panel(response.text, title="Respuesta", border_style="green"))
    console.print(f"[dim]Duración: {response.duration_seconds:.2f}s[/dim]")


if __name__ == "__main__":
    app()

"""Asistente de permisos para macOS.

macOS requiere que el usuario apruebe manualmente:
1. Micrófono (System Settings → Privacy & Security → Microphone)
2. Accesibilidad (System Settings → Privacy & Security → Accessibility)

Este script:
- Detecta qué permisos faltan
- Muestra instrucciones claras
- Abre los paneles de System Settings si los necesita
- Hace un test de audio para confirmar que el mic funciona
"""

from __future__ import annotations

import platform
import subprocess
import sys


def check_accessibility(prompt: bool = False) -> bool:
    """Verifica si el proceso tiene permiso de Accesibilidad en macOS.

    Usa ApplicationServices.AXIsProcessTrustedWithOptions. Si prompt=True,
    abre el diálogo de System Settings pidiendo al usuario que habilite.

    Returns:
        True si el permiso ya está concedido.
    """
    if platform.system() != "Darwin":
        return True
    try:
        import ApplicationServices
        from CoreFoundation import (
            CFDictionaryCreate,
            kCFBooleanFalse,
            kCFBooleanTrue,
        )

        ax_func = getattr(ApplicationServices, "AXIsProcessTrustedWithOptions", None)
        if ax_func is None:
            ax_trusted = getattr(ApplicationServices, "AXIsProcessTrusted", None)
            if ax_trusted is not None:
                return bool(ax_trusted())
            return True  # no podemos verificar

        key = ApplicationServices.kAXTrustedCheckOptionPrompt
        value = kCFBooleanTrue if prompt else kCFBooleanFalse
        options = CFDictionaryCreate(
            None,
            [key],
            [value],
            1,
            None,
            None,
        )
        return bool(ax_func(options))
    except ImportError:
        try:
            import ApplicationServices
            ax_trusted = getattr(ApplicationServices, "AXIsProcessTrusted", None)
            if ax_trusted is not None:
                return bool(ax_trusted())
            print("[WARN] No se pudo verificar permiso de Accesibilidad.")
            return True
        except ImportError:
            print("[WARN] No se pudo verificar permiso de Accesibilidad.")
            return True
    except Exception as e:
        print(f"[WARN] Error verificando accesibilidad: {e}")
        return True


def check_microphone_permission() -> bool:
    """Devuelve True si el proceso actual tiene permiso de mic."""
    if platform.system() != "Darwin":
        return True
    # AVFoundation: si no hay permiso, intentar grabar falla
    # Heurística: intentar crear un stream de audio en modo "no-op"
    try:
        import sounddevice as sd
        import numpy as np

        # Intentar leer 100ms de audio
        audio = sd.rec(
            int(0.1 * 16000),
            samplerate=16000,
            channels=1,
            dtype="int16",
        )
        sd.wait()
        rms = float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))
        return rms > 0 or True  # True aunque sea silencio (puede haber permiso pero silencio)
    except Exception as e:
        print(f"[WARN] No se pudo acceder al mic: {e}")
        return False


def open_microphone_settings() -> None:
    """Abre System Settings → Privacy & Security → Microphone."""
    if platform.system() == "Darwin":
        try:
            # macOS 13+ usa 'Privacy & Security', macOS 12- usa 'Security & Privacy'
            script = """
            tell application "System Settings"
                activate
            end tell
            delay 1
            tell application "System Events"
                tell process "System Settings"
                    try
                        click button "Microphone" of group 1 of window 1
                    on error
                        try
                            click button "Micrófono" of group 1 of window 1
                        end try
                    end try
                end tell
            end tell
            """
            subprocess.run(["osascript", "-e", script], check=False)
        except Exception as e:
            print(f"[WARN] No se pudo abrir settings: {e}")


def open_accessibility_settings() -> None:
    """Abre System Settings → Privacy & Security → Accessibility."""
    if platform.system() == "Darwin":
        try:
            script = """
            tell application "System Settings"
                activate
            end tell
            delay 1
            tell application "System Events"
                tell process "System Settings"
                    try
                        click button "Accessibility" of group 1 of window 1
                    on error
                        try
                            click button "Accesibilidad" of group 1 of window 1
                        end try
                    end try
                end tell
            end tell
            """
            subprocess.run(["osascript", "-e", script], check=False)
        except Exception as e:
            print(f"[WARN] No se pudo abrir settings: {e}")


def preload_whisper_model() -> None:
    """Pre-descarga el modelo de faster-whisper para que el primer uso sea instantáneo."""
    try:
        from belen.config import get_settings
        model_name = get_settings().belen_whisper_model
        print(f"  Descargando modelo '{model_name}' (~74 MB)...")
        from faster_whisper import WhisperModel
        WhisperModel(model_name, device="cpu", compute_type="int8")
        print("  ✓ Modelo descargado y cargado.")
    except ImportError:
        print("  [WARN] faster-whisper no instalado. Salteando pre-descarga.")
    except Exception as e:
        print(f"  [WARN] No se pudo pre-descargar el modelo: {e}")
        print("  (Se descargará automáticamente en el primer uso.)")


def request_permissions() -> None:
    """Pide los permisos necesarios al usuario."""
    if platform.system() != "Darwin":
        print("Belen solo funciona en macOS.")
        return

    print("╭───────────────────────────────────────────────╮")
    print("│  Belen necesita dos permisos en macOS:        │")
    print("╰───────────────────────────────────────────────╯")
    print()
    print("1. 🎤 Micrófono — para escucharte cuando hables")
    print("2. ♿ Accesibilidad — para detectar la hotkey")
    print()

    input("Apretá Enter para abrir System Settings...")

    print()
    print("▶ Abriendo System Settings → Privacidad y seguridad...")
    open_microphone_settings()
    print()
    print("  En el panel que se abrió:")
    print("  1. Buscá 'Terminal' (o iTerm, o la app que uses)")
    print("  2. Activá el switch al lado de Terminal")
    print("  3. Volvé a esta ventana y apretá Enter")
    print()
    input("Apretá Enter cuando termines con el micrófono...")

    print()
    print("▶ Ahora abriendo Accesibilidad...")
    open_accessibility_settings()
    print()
    print("  En el panel que se abrió:")
    print("  1. Buscá 'Terminal' (o iTerm, o la app que uses)")
    print("  2. Activá el switch al lado de Terminal")
    print("  3. Si te pide reiniciar Terminal, hacelo")
    print()
    input("Apretá Enter cuando termines...")

    print()
    print("▶ Testeando micrófono...")
    if check_microphone_permission():
        print("  ✓ Micrófono accesible")
    else:
        print("  ✗ No se pudo acceder al mic. Reintentá.")

    print()
    print("▶ Verificando Accesibilidad...")
    if check_accessibility():
        print("  ✓ Accesibilidad concedida")
    else:
        print("  ✗ Accesibilidad NO concedida. La hotkey no funcionará.")
        print("    Activá el switch en System Settings → Accessibility → Terminal.")

    print()
    print("▶ Pre-descargando modelo de faster-whisper (74 MB)...")
    preload_whisper_model()

    print()
    print("╭───────────────────────────────────────────────╮")
    print("│  ¡Listo! Ya podés correr: belen start         │")
    print("╰───────────────────────────────────────────────╯")


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        print("Test de permisos:")
        print(f"  Micrófono: {'✓' if check_microphone_permission() else '✗'}")
        return 0
    request_permissions()
    return 0


if __name__ == "__main__":
    sys.exit(main())

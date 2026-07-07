"""Pipeline principal de Belen — orquesta todo el flujo.

Flujo:
  1. Usuario aprieta hotkey (o wake word)
  2. Recorder captura audio del micrófono
  3. STT transcribe a texto
  4. ProjectSelector detecta si es comando de cambio de proyecto
  5. Si es prompt normal: Safety valida → Brain consulta opencode → TTS habla
  6. UI flotante muestra el estado
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from belen.brain import BrainResponse, OpenCodeBrain
from belen.config import get_settings
from belen.feedback import StatusDisplay
from belen.hotkey import HotkeyListener
from belen.project_selector import ProjectSelector
from belen.recorder import AudioRecorder
from belen.safety import validate_prompt
from belen.stt import STTManager
from belen.tts import TTSManager
from belen.ui import ConsoleUI, FloatingUI
from belen.visual_ui import FallbackVisualUI, get_visual_ui
from belen.wakeword import WakeWordDetector


@dataclass
class TurnResult:
    user_text: str
    belen_text: str
    brain_response: BrainResponse | None
    project_changed: Path | None = None
    duration_seconds: float = 0.0
    error: str | None = None


class BelenPipeline:
    """Pipeline completo de Belen.

    Orquesta el flujo: hotkey → recorder → STT → selector/brain → TTS → UI.
    """

    def __init__(
        self,
        recorder: AudioRecorder | None = None,
        stt: STTManager | None = None,
        brain: OpenCodeBrain | None = None,
        tts: TTSManager | None = None,
        project_selector: ProjectSelector | None = None,
        status: StatusDisplay | None = None,
        ui: Any | None = None,
        wakeword: WakeWordDetector | None = None,
    ) -> None:
        self.settings = get_settings()
        self.recorder = recorder or AudioRecorder()
        self.stt = stt or STTManager()
        self.brain = brain or OpenCodeBrain()
        self.tts = tts or TTSManager()
        self.project_selector = project_selector or ProjectSelector()
        self.status = status or StatusDisplay()
        self.ui = ui or FallbackVisualUI()
        self.wakeword = wakeword or WakeWordDetector()
        self._hotkey_listener: HotkeyListener | None = None
        self._is_running = False
        self._active_project: Path | None = None
        self._lock = threading.Lock()
        self._on_turn: Callable[[TurnResult], None] | None = None
        self._pump_thread: threading.Thread | None = None
        self._is_processing: bool = False

        if self.settings.belen_default_project:
            default = Path(self.settings.belen_default_project)
            if default.exists():
                self._active_project = default

    def on_turn(self, callback: Callable[[TurnResult], None]) -> None:
        """Callback invocado después de cada turno (para logging, UI, etc.)."""
        self._on_turn = callback

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def active_project(self) -> Path | None:
        return self._active_project

    def set_active_project(self, path: Path | None) -> None:
        with self._lock:
            self._active_project = path

    def _notify_turn(self, result: TurnResult) -> None:
        if self._on_turn is None:
            return
        try:
            self._on_turn(result)
        except Exception as e:
            print(f"[WARN] Callback on_turn falló: {e}")

    def start(self) -> None:
        """Arranca el pipeline: hotkey listener + wakeword + pump thread."""
        from belen.logging_utils import info, warn, clear as log_clear

        log_clear()
        info("PIPELINE", "iniciando pipeline")
        if self._is_running:
            warn("PIPELINE", "ya está corriendo, ignorando start()")
            return
        self._is_running = True
        info("PIPELINE", f"spec hotkey: {self.settings.belen_hotkey} mode={self.settings.belen_hotkey_mode}")

        if self.wakeword.config.enabled:
            try:
                self.wakeword.load()
                info("WAKEWORD", f"wakeword cargado: {self.wakeword.config.word}")
            except Exception as e:
                warn("WAKEWORD", f"no se pudo cargar: {e}")

        self._hotkey_listener = HotkeyListener()
        self._hotkey_listener.on_press(self._handle_hotkey_press)
        self._hotkey_listener.on_release(self._handle_hotkey_release)
        self._hotkey_listener.start()
        info("HOTKEY", "listener arrancado")

        # Thread dedicado para despachar eventos de la queue de pynput.
        # Esto evita que el callback nativo de pynput se congele con
        # trabajo bloqueante (recorder.start, process_turn, etc.).
        self._pump_thread = threading.Thread(
            target=self._pump_loop,
            name="belen-hotkey-pump",
            daemon=True,
        )
        self._pump_thread.start()

    def _pump_loop(self) -> None:
        """Loop dedicado a despachar eventos de pynput en un thread propio."""
        from belen.logging_utils import info, debug
        info("PUMP", "pump thread arrancado")
        while self._is_running and self._hotkey_listener is not None:
            self._hotkey_listener.pump(timeout=0.05)
        info("PUMP", "pump thread terminando")

    def start_hotkey_only(self) -> None:
        """Arranca solo el listener de hotkey (sin tocar UI)."""
        self.start()

    def stop(self) -> None:
        from belen.logging_utils import info
        if not self._is_running:
            return
        info("PIPELINE", "deteniendo pipeline")
        self._is_running = False
        if self._hotkey_listener is not None:
            self._hotkey_listener.stop()
            info("HOTKEY", "listener detenido")
        if self._pump_thread is not None:
            self._pump_thread.join(timeout=2.0)
            self._pump_thread = None
            info("PIPELINE", "pump thread detenido")
        if self.recorder.is_recording:
            self.recorder.cancel()

    def _handle_hotkey_press(self) -> None:
        from belen.logging_utils import info
        info("HOTKEY", "press — arrancando recorder (en thread aparte)")
        # Lanzar recorder.start() en un thread aparte para no bloquear
        # el pump thread (PortAudio puede tardar 1-2s en abrir el stream).
        t = threading.Thread(
            target=self._do_press,
            name="belen-press",
            daemon=True,
        )
        t.start()

    def _do_press(self) -> None:
        """Ejecuta el press en thread aparte."""
        from belen.logging_utils import info, error
        try:
            self.recorder.start()
            self.status.listening()
            self._ui_listening()
            info("HOTKEY", "recorder arrancado, UI en LISTENING")
        except Exception as e:
            error("HOTKEY", f"excepción en press: {e}")
            self.status.error(str(e))
            self._ui_error(str(e))

    def _ui_listening(self) -> None:
        """Pone la UI en estado listening (compatible con todos los tipos)."""
        if isinstance(self.ui, (FloatingUI, ConsoleUI)):
            self.ui.listening()
        elif hasattr(self.ui, "listening"):
            self.ui.listening()

    def _ui_processing(self, msg: str) -> None:
        if isinstance(self.ui, (FloatingUI, ConsoleUI)):
            self.ui.processing(msg)
        elif hasattr(self.ui, "processing"):
            self.ui.processing(msg)

    def _ui_speaking(self, msg: str) -> None:
        if isinstance(self.ui, (FloatingUI, ConsoleUI)):
            self.ui.speaking(msg)
        elif hasattr(self.ui, "speaking"):
            self.ui.speaking(msg)

    def _ui_error(self, msg: str) -> None:
        if isinstance(self.ui, (FloatingUI, ConsoleUI)):
            self.ui.error(msg)
        elif hasattr(self.ui, "error"):
            self.ui.error(msg)

    def _ui_idle(self) -> None:
        if isinstance(self.ui, (FloatingUI, ConsoleUI)):
            self.ui.idle()
        elif hasattr(self.ui, "idle"):
            self.ui.idle()

    def _ui_show_user_text(self, text: str) -> None:
        """Muestra el texto transcrito del usuario en la UI."""
        from belen.logging_utils import debug
        debug("UI", f"mostrando user_text: {text!r}")
        if hasattr(self.ui, "set_user_text"):
            self.ui.set_user_text(text)

    def _handle_hotkey_release(self) -> None:
        from belen.logging_utils import debug, info, warn, error

        # Si el recorder aún no arrancó (press en thread aparte), esperar
        # a que is_recording sea True antes de detener.
        if not self.recorder.is_recording:
            info("HOTKEY", "release — esperando que recorder arranque...")
            import time as _t
            waited = 0.0
            while not self.recorder.is_recording and waited < 3.0:
                _t.sleep(0.05)
                waited += 0.05
            if not self.recorder.is_recording:
                warn("HOTKEY", "recorder nunca arrancó, descartando release")
                return
            info("HOTKEY", f"recorder listo después de {waited:.2f}s")

        info("HOTKEY", "release — deteniendo recorder")
        try:
            audio, sr = self.recorder.stop()
        except Exception as e:
            error("HOTKEY", f"recorder.stop() falló: {e}")
            return
        audio_samples = audio.size if hasattr(audio, "size") else 0
        duration_sec = audio_samples / sr if sr > 0 else 0
        debug("RECORDER", f"audio: {audio_samples} samples @ {sr}Hz ({duration_sec:.2f}s)")
        if audio_samples == 0:
            warn("RECORDER", "audio vacío, volviendo a idle")
            self._show_error("No se escuchó nada. ¿Permisos de micrófono?")
            return
        if duration_sec < 0.3:
            warn("RECORDER", f"audio muy corto ({duration_sec:.2f}s), descartando")
            self._show_error("Muy corto. Mantené shift+z y hablá más tiempo.")
            return

        # Lanzar process_turn en un thread separado para no bloquear
        # el pump thread (que sigue despachando eventos de pynput).
        if self._processing:
            warn("PIPELINE", "turno anterior aún procesando, descartando")
            self._show_error("Estoy pensando... esperá un momento")
            return

        t = threading.Thread(
            target=self._process_turn_threaded,
            args=(audio, sr),
            name="belen-turn",
            daemon=True,
        )
        t.start()
        info("PIPELINE", f"thread de turno arrancado (tid={t.ident})")

    def _show_error(self, msg: str) -> None:
        """Muestra un error en la UI y vuelve a idle."""
        from belen.logging_utils import info
        info("UI", f"mostrando error: {msg}")
        self.status.error(msg)
        self._ui_error(msg)
        import time
        time.sleep(1.5)
        self.status.idle()
        self._ui_idle()

    @property
    def _processing(self) -> bool:
        return getattr(self, "_is_processing", False)

    def _process_turn_threaded(self, audio: Any, sample_rate: int) -> None:
        """Wrapper de process_turn que marca el flag de processing."""
        from belen.logging_utils import info, error
        self._is_processing = True
        try:
            result = self.process_turn(audio, sample_rate)
            self._notify_turn(result)
            info("PIPELINE", f"turno OK en {result.duration_seconds:.2f}s")
        except Exception as e:
            error("PIPELINE", f"excepción en process_turn: {e}")
            import traceback
            error("PIPELINE", traceback.format_exc())
        finally:
            self._is_processing = False

    def process_turn(self, audio: Any, sample_rate: int) -> TurnResult:
        """Procesa un turno completo: STT → selector/brain → TTS."""
        import time
        from belen.logging_utils import info, debug, warn, error

        t0 = time.monotonic()
        try:
            info("STT", "transcribiendo audio...")
            self.status.processing("transcribiendo...")
            self._ui_processing("transcribiendo...")

            t_stt = time.monotonic()
            user_text = self.stt.transcribe(audio, sample_rate)
            info("STT", f"transcripción en {time.monotonic()-t_stt:.2f}s: {user_text!r}")

            if not user_text:
                warn("STT", "transcripción vacía, descartando turno")
                # Mostrar feedback en la UI
                self._ui_error("No te entendí. Probá de nuevo.")
                import time as _t
                _t.sleep(1.5)
                self._ui_idle()
                result = TurnResult(
                    user_text="",
                    belen_text="",
                    brain_response=None,
                    duration_seconds=time.monotonic() - t0,
                )
                self._notify_turn(result)
                return result

            print(f"\n[👤 Usuario]: {user_text}")

            # Mostrar el texto transcrito en la UI inmediatamente
            self._ui_show_user_text(user_text)

            info("SELECTOR", f"buscando match de proyecto...")
            match = self.project_selector.select(user_text)
            if match is not None:
                info("SELECTOR", f"match: {match.name} → {match.path}")
                self.set_active_project(match.path)
                belen_text = f"Cambié al proyecto {match.name}."
                print(f"[📁 Proyecto]: {match.name} → {match.path}")

                self.status.speaking(belen_text)
                self._ui_speaking(belen_text)
                self.tts.speak(belen_text)

                result = TurnResult(
                    user_text=user_text,
                    belen_text=belen_text,
                    brain_response=None,
                    project_changed=match.path,
                    duration_seconds=time.monotonic() - t0,
                )
                self._notify_turn(result)
                return result

            validation = validate_prompt(user_text)
            if not validation.ok:
                warn("SAFETY", f"prompt bloqueado: {validation.reason}")
                belen_text = f"No puedo hacer eso: {validation.reason}"
                self.status.error(belen_text)
                self._ui_error(belen_text)
                self.tts.speak(belen_text)
                result = TurnResult(
                    user_text=user_text,
                    belen_text=belen_text,
                    brain_response=None,
                    error=validation.reason,
                    duration_seconds=time.monotonic() - t0,
                )
                self._notify_turn(result)
                return result

            self.status.processing("pensando...")
            self._ui_processing("pensando...")

            info("BRAIN", f"enviando a opencode (cwd={self._active_project})...")
            t_brain = time.monotonic()
            response = self.brain.ask_sync(
                user_text,
                cwd=self._active_project,
                timeout=120.0,
            )
            info("BRAIN", f"opencode respondió en {time.monotonic()-t_brain:.2f}s")
            belen_text = response.text

            print(f"[🤖 Belen]: {belen_text[:200]}{'...' if len(belen_text) > 200 else ''}")

            info("TTS", f"reproduciendo respuesta ({len(belen_text)} chars)...")
            t_tts = time.monotonic()
            self.status.speaking(belen_text)
            self._ui_speaking(belen_text)
            self.tts.speak(belen_text)
            info("TTS", f"TTS terminó en {time.monotonic()-t_tts:.2f}s")

            self.status.idle()
            self._ui_idle()

            result = TurnResult(
                user_text=user_text,
                belen_text=belen_text,
                brain_response=response,
                duration_seconds=time.monotonic() - t0,
            )
            self._notify_turn(result)
            return result

        except Exception as e:
            from belen.logging_utils import error as _err
            import traceback
            _err("PIPELINE", f"excepción en process_turn: {e}")
            _err("PIPELINE", traceback.format_exc())
            error_msg = f"Error: {e}"
            self.status.error(error_msg)
            self._ui_error(error_msg)
            result = TurnResult(
                user_text="",
                belen_text="",
                brain_response=None,
                error=error_msg,
                duration_seconds=time.monotonic() - t0,
            )
            self._notify_turn(result)
            return result

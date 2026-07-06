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
        self.ui = ui or ConsoleUI()
        self.wakeword = wakeword or WakeWordDetector()
        self._hotkey_listener: HotkeyListener | None = None
        self._is_running = False
        self._active_project: Path | None = None
        self._lock = threading.Lock()
        self._on_turn: Callable[[TurnResult], None] | None = None

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
        """Arranca el pipeline: hotkey listener + UI."""
        if self._is_running:
            return
        self._is_running = True

        if self.wakeword.config.enabled:
            try:
                self.wakeword.load()
            except Exception as e:
                print(f"[WARN] No se pudo cargar wake word: {e}")

        self._hotkey_listener = HotkeyListener()
        self._hotkey_listener.on_press(self._handle_hotkey_press)
        self._hotkey_listener.on_release(self._handle_hotkey_release)
        self._hotkey_listener.start()

    def stop(self) -> None:
        if not self._is_running:
            return
        self._is_running = False
        if self._hotkey_listener is not None:
            self._hotkey_listener.stop()
        if self.recorder.is_recording:
            self.recorder.cancel()

    def _handle_hotkey_press(self) -> None:
        try:
            self.recorder.start()
            self.status.listening()
            if isinstance(self.ui, (FloatingUI, ConsoleUI)):
                self.ui.listening()
        except Exception as e:
            self.status.error(str(e))

    def _handle_hotkey_release(self) -> None:
        audio, sr = self.recorder.stop()
        if audio.size == 0:
            self.status.idle()
            return
        result = self.process_turn(audio, sr)
        self._notify_turn(result)

    def process_turn(self, audio: Any, sample_rate: int) -> TurnResult:
        """Procesa un turno completo: STT → selector/brain → TTS."""
        import time

        t0 = time.monotonic()
        try:
            self.status.processing("transcribiendo...")
            if isinstance(self.ui, (FloatingUI, ConsoleUI)):
                self.ui.processing("transcribiendo...")

            user_text = self.stt.transcribe(audio, sample_rate)
            if not user_text:
                result = TurnResult(
                    user_text="",
                    belen_text="",
                    brain_response=None,
                    duration_seconds=time.monotonic() - t0,
                )
                self._notify_turn(result)
                return result

            print(f"\n[👤 Usuario]: {user_text}")

            match = self.project_selector.select(user_text)
            if match is not None:
                self.set_active_project(match.path)
                belen_text = f"Cambié al proyecto {match.name}."
                print(f"[📁 Proyecto]: {match.name} → {match.path}")

                self.status.speaking(belen_text)
                if isinstance(self.ui, (FloatingUI, ConsoleUI)):
                    self.ui.speaking(belen_text)
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
                belen_text = f"No puedo hacer eso: {validation.reason}"
                self.status.error(belen_text)
                if isinstance(self.ui, (FloatingUI, ConsoleUI)):
                    self.ui.error(belen_text)
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
            if isinstance(self.ui, (FloatingUI, ConsoleUI)):
                self.ui.processing("pensando...")

            response = self.brain.ask_sync(
                user_text,
                cwd=self._active_project,
                timeout=120.0,
            )
            belen_text = response.text

            print(f"[🤖 Belen]: {belen_text[:200]}{'...' if len(belen_text) > 200 else ''}")

            self.status.speaking(belen_text)
            if isinstance(self.ui, (FloatingUI, ConsoleUI)):
                self.ui.speaking(belen_text)
            self.tts.speak(belen_text)

            self.status.idle()
            if isinstance(self.ui, (FloatingUI, ConsoleUI)):
                self.ui.idle()

            result = TurnResult(
                user_text=user_text,
                belen_text=belen_text,
                brain_response=response,
                duration_seconds=time.monotonic() - t0,
            )
            self._notify_turn(result)
            return result

        except Exception as e:
            error_msg = f"Error: {e}"
            self.status.error(error_msg)
            if isinstance(self.ui, (FloatingUI, ConsoleUI)):
                self.ui.error(error_msg)
            result = TurnResult(
                user_text="",
                belen_text="",
                brain_response=None,
                error=error_msg,
                duration_seconds=time.monotonic() - t0,
            )
            self._notify_turn(result)
            return result

"""UI visual estilo Siri para macOS.

Usa PyObjC para crear una ventana flotante (NSPanel) sin marco con:
- Un orbe circular animado (CAEmitterLayer + animación de pulso)
- Color/forma que cambia según el estado (idle/listening/processing/speaking/error)
- Texto de transcripción en vivo
- Texto de respuesta cuando Belen habla
- Aparece en la parte inferior central de la pantalla
- Se desvanece automáticamente cuando termina

Requiere:
- macOS 11+
- PyObjC (ya instalado)
- Quartz framework
"""

from __future__ import annotations

import platform
import threading
from enum import StrEnum
from typing import Any

from belen.config import get_settings


class UIState(StrEnum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"


STATE_LABELS = {
    UIState.IDLE: "Belen",
    UIState.LISTENING: "Escuchando...",
    UIState.PROCESSING: "Pensando...",
    UIState.SPEAKING: "Hablando...",
    UIState.ERROR: "Error",
}

STATE_COLORS = {
    UIState.IDLE: (0.5, 0.5, 0.5, 1.0),
    UIState.LISTENING: (0.95, 0.25, 0.35, 1.0),
    UIState.PROCESSING: (0.95, 0.78, 0.20, 1.0),
    UIState.SPEAKING: (0.20, 0.78, 0.45, 1.0),
    UIState.ERROR: (0.85, 0.20, 0.20, 1.0),
}


class SiriStyleWindow:
    """Ventana flotante estilo Siri con orbe animado.

    Uso:
        win = SiriStyleWindow()
        win.start()        # bloqueante (corre NSApp run loop)
        win.update(UIState.LISTENING)  # desde cualquier thread
    """

    WINDOW_WIDTH = 380
    WINDOW_HEIGHT = 280
    ORBE_RADIUS = 45

    def __init__(self) -> None:
        self._state = UIState.IDLE
        self._user_text = ""
        self._belen_text = ""
        self._lock = threading.Lock()
        self._app: Any = None
        self._window: Any = None
        self._orbe_layer: Any = None
        self._state_label: Any = None
        self._user_text_field: Any = None
        self._belen_text_field: Any = None
        self._pulse_timer: Any = None
        self._running = False

    @property
    def state(self) -> UIState:
        return self._state

    def set_callbacks(
        self,
        on_toggle_wakeword: Any = None,
        on_quit: Any = None,
    ) -> None:
        self._on_toggle_wakeword = on_toggle_wakeword
        self._on_quit = on_quit

    def pulseTick_(self, _timer: object) -> None:
        """Callback del NSTimer para animar el orbe. Llamado por AppKit."""
        import math
        import time as _time

        if self._orbe_layer is None or not self._running:
            return
        if not hasattr(self, "_pulse_t0"):
            self._pulse_t0 = _time.monotonic()
        t = _time.monotonic() - self._pulse_t0
        scale = 1.0 + 0.12 * (0.5 + 0.5 * math.sin(t * 3.5))

        from Quartz import CATransform3D, CGColorCreateGenericRGB

        transform = CATransform3D()
        transform.m11 = scale
        transform.m22 = scale
        transform.m33 = 1.0
        transform.m44 = 1.0
        self._orbe_layer.setTransform_(transform)

        if self._ring_layer is not None:
            opacity = 0.15 + 0.35 * (0.5 + 0.5 * math.sin(t * 3.5 + 0.5))
            self._ring_layer.setOpacity_(opacity)

        if hasattr(self, "_pulse_state") and self._state != self._pulse_state:
            self._pulse_state = self._state
            color = CGColorCreateGenericRGB(*STATE_COLORS[self._state])
            self._orbe_layer.setBackgroundColor_(color)
            self._orbe_layer.setShadowColor_(color)
            self._ring_layer.setBorderColor_(color)

    def start(self) -> None:
        """Arranca la ventana (bloqueante, en el main thread)."""
        if platform.system() != "Darwin":
            raise RuntimeError("SiriStyleWindow solo funciona en macOS")

        from AppKit import (
            NSApp,
            NSApplication,
            NSBackingStoreBuffered,
            NSColor,
            NSPanel,
            NSScreen,
            NSTextField,
            NSWindowStyleMaskBorderless,
            NSWindowStyleMaskNonactivatingPanel,
        )
        from Foundation import NSMakeRect
        from Quartz import CALayer, CGColorCreateGenericRGB

        self._app = NSApplication.sharedApplication()
        self._app.setActivationPolicy_(1)

        screen = NSScreen.mainScreen()
        if screen is None:
            screen = NSScreen.screens().firstObject()
        if screen is None:
            raise RuntimeError("No hay pantallas disponibles")
        screen_frame = screen.frame()
        win_w = self.WINDOW_WIDTH
        win_h = self.WINDOW_HEIGHT
        x = (screen_frame.size.width - win_w) / 2
        y = screen_frame.size.height - win_h - 80

        win_rect = NSMakeRect(x, y, win_w, win_h)
        style = NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel
        self._window = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            win_rect, style, NSBackingStoreBuffered, False
        )
        self._window.setLevel_(25)  # NSFloatingWindowLevel
        self._window.setOpaque_(False)
        self._window.setBackgroundColor_(NSColor.clearColor())
        self._window.setHasShadow_(True)
        self._window.setMovableByWindowBackground_(True)
        self._window.setCollectionBehavior_(1)  # NSWindowCollectionBehaviorCanJoinAllSpaces
        self._window.setHidesOnDeactivate_(False)
        self._window.setReleasedWhenClosed_(False)

        container = self._window.contentView()
        container.setWantsLayer_(True)
        bg_layer = CALayer.layer()
        bg_layer.setBackgroundColor_(CGColorCreateGenericRGB(0.08, 0.08, 0.12, 0.92))
        bg_layer.setCornerRadius_(16.0)
        container.setLayer_(bg_layer)

        # Orbe central con gradient
        orbe_size = self.ORBE_RADIUS * 2.6
        orbe_frame = NSMakeRect(
            (win_w - orbe_size) / 2,
            win_h - orbe_size - 50,
            orbe_size,
            orbe_size,
        )
        orbe_layer = CALayer.layer()
        orbe_layer.setFrame_(orbe_frame)
        orbe_layer.setCornerRadius_(self.ORBE_RADIUS * 1.3)
        orbe_layer.setBackgroundColor_(
            CGColorCreateGenericRGB(*STATE_COLORS[self._state])
        )
        orbe_layer.setShadowColor_(
            CGColorCreateGenericRGB(*STATE_COLORS[self._state])
        )
        orbe_layer.setShadowRadius_(25)
        orbe_layer.setShadowOpacity_(0.8)
        from AppKit import NSMakeSize

        orbe_layer.setShadowOffset_(NSMakeSize(0, 0))
        bg_layer.addSublayer_(orbe_layer)
        self._orbe_layer = orbe_layer

        # Anillo pulsante alrededor del orbe
        ring_size = self.ORBE_RADIUS * 3.2
        ring_frame = NSMakeRect(
            (win_w - ring_size) / 2,
            win_h - ring_size - 50,
            ring_size,
            ring_size,
        )
        ring_layer = CALayer.layer()
        ring_layer.setFrame_(ring_frame)
        ring_layer.setCornerRadius_(self.ORBE_RADIUS * 1.6)
        ring_layer.setBorderWidth_(2.5)
        ring_layer.setBorderColor_(
            CGColorCreateGenericRGB(*STATE_COLORS[self._state])
        )
        ring_layer.setOpacity_(0.4)
        bg_layer.addSublayer_(ring_layer)
        self._ring_layer = ring_layer

        # Label de estado (grande, prominente)
        from AppKit import NSFont

        label_frame = NSMakeRect(20, 110, win_w - 40, 32)
        self._state_label = NSTextField.alloc().initWithFrame_(label_frame)
        self._state_label.setEditable_(False)
        self._state_label.setSelectable_(False)
        self._state_label.setBordered_(False)
        self._state_label.setDrawsBackground_(False)
        self._state_label.setTextColor_(NSColor.whiteColor())
        self._state_label.setAlignment_(2)  # center
        self._state_label.setFont_(NSFont.boldSystemFontOfSize_(20))
        self._state_label.setStringValue_("Belen")
        container.addSubview_(self._state_label)

        # Hotkey hint (chiquito, gris)
        hint_frame = NSMakeRect(20, 85, win_w - 40, 18)
        self._hint_label = NSTextField.alloc().initWithFrame_(hint_frame)
        self._hint_label.setEditable_(False)
        self._hint_label.setSelectable_(False)
        self._hint_label.setBordered_(False)
        self._hint_label.setDrawsBackground_(False)
        self._hint_label.setTextColor_(NSColor.colorWithCalibratedWhite_alpha_(0.6, 1.0))
        self._hint_label.setAlignment_(2)
        self._hint_label.setFont_(NSFont.systemFontOfSize_(10))
        self._hint_label.setStringValue_("⇧ + Z   o decí 'Belen'")
        container.addSubview_(self._hint_label)

        # Texto del usuario (lo que dijiste)
        user_frame = NSMakeRect(20, 50, win_w - 40, 28)
        self._user_text_field = NSTextField.alloc().initWithFrame_(user_frame)
        self._user_text_field.setEditable_(False)
        self._user_text_field.setSelectable_(False)
        self._user_text_field.setBordered_(False)
        self._user_text_field.setDrawsBackground_(False)
        self._user_text_field.setTextColor_(NSColor.colorWithCalibratedRed_green_blue_alpha_(0.6, 0.85, 1.0, 1.0))
        self._user_text_field.setAlignment_(2)
        self._user_text_field.setFont_(NSFont.systemFontOfSize_(12))
        self._user_text_field.setStringValue_("")
        container.addSubview_(self._user_text_field)

        # Texto de Belen (la respuesta)
        belen_frame = NSMakeRect(15, 12, win_w - 30, 32)
        self._belen_text_field = NSTextField.alloc().initWithFrame_(belen_frame)
        self._belen_text_field.setEditable_(False)
        self._belen_text_field.setSelectable_(False)
        self._belen_text_field.setBordered_(False)
        self._belen_text_field.setDrawsBackground_(False)
        self._belen_text_field.setTextColor_(NSColor.whiteColor())
        self._belen_text_field.setAlignment_(2)
        self._belen_text_field.setFont_(NSFont.systemFontOfSize_(13))
        self._belen_text_field.setStringValue_("")
        container.addSubview_(self._belen_text_field)

        # Mostrar ventana
        self._window.orderFrontRegardless()
        self._running = True

        # Iniciar animación con NSTimer (más confiable que CABasicAnimation en pyobjc)
        self._start_pulse_animation()

        # Run loop
        self._app.activateIgnoringOtherApps_(True)
        NSApp.run()

    def _start_pulse_animation(self) -> None:
        """Inicia animación de pulso del orbe con NSTimer.

        Evita CABasicAnimation que está rota en pyobjc 12.2.1.
        El método pulseTick_ modifica transform/opacity en cada tick.
        """
        import time as _time

        from AppKit import NSTimer

        self._pulse_t0 = _time.monotonic()
        self._pulse_state = self._state

        # 30 fps — suficiente para animación suave, liviano para la CPU
        self._pulse_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            1.0 / 30.0, self, "pulseTick:", None, True
        )

    def start_async(self) -> threading.Thread:
        """Arranca la ventana en un thread daemon."""
        thread = threading.Thread(target=self.start, daemon=True)
        thread.start()
        return thread

    def _set_state_on_main(self, state: UIState) -> None:
        """Cambia el color y label del orbe. Llamar desde main thread."""
        from Quartz import CGColorCreateGenericRGB

        if self._orbe_layer is not None:
            self._orbe_layer.setBackgroundColor_(CGColorCreateGenericRGB(*STATE_COLORS[state]))
            self._orbe_layer.setShadowColor_(CGColorCreateGenericRGB(*STATE_COLORS[state]))
        if self._ring_layer is not None:
            self._ring_layer.setBorderColor_(CGColorCreateGenericRGB(*STATE_COLORS[state]))
        if self._state_label is not None:
            self._state_label.setStringValue_(STATE_LABELS[state])

    def set_user_text(self, text: str) -> None:
        """Muestra el texto del usuario en la ventana (sin cambiar estado)."""
        with self._lock:
            self._user_text = text
        if self._app is None:
            return
        from PyObjCTools import AppHelper

        def _on_main() -> None:
            if self._user_text_field is not None:
                self._user_text_field.setStringValue_(text[:60])

        try:
            AppHelper.callAfter(_on_main)
        except Exception:
            pass

    def update(self, state: UIState, message: str = "") -> None:
        """Actualiza el estado desde cualquier thread."""
        with self._lock:
            self._state = state
            if message:
                if state == UIState.LISTENING:
                    self._user_text = message
                elif state in (UIState.PROCESSING, UIState.SPEAKING, UIState.ERROR):
                    self._belen_text = message

        if self._app is None:
            return

        from AppKit import NSApp
        from PyObjCTools import AppHelper

        def _on_main() -> None:
            self._set_state_on_main(state)
            if self._user_text_field is not None:
                self._user_text_field.setStringValue_(self._user_text[:60])
            if self._belen_text_field is not None and self._belen_text:
                self._belen_text_field.setStringValue_(self._belen_text[:80])

        try:
            AppHelper.callAfter(_on_main)
        except Exception:
            pass

    def show(self) -> None:
        """Muestra la ventana."""
        from PyObjCTools import AppHelper

        def _on_main() -> None:
            if self._window is not None:
                self._window.orderFrontRegardless()

        try:
            AppHelper.callAfter(_on_main)
        except Exception:
            pass

    def hide(self) -> None:
        """Oculta la ventana."""
        from PyObjCTools import AppHelper

        def _on_main() -> None:
            if self._window is not None:
                self._window.orderOut_(None)

        try:
            AppHelper.callAfter(_on_main)
        except Exception:
            pass

    def idle(self) -> None:
        self.update(UIState.IDLE)

    def listening(self) -> None:
        self.update(UIState.LISTENING, "Escuchando...")
        self.show()

    def processing(self, text: str = "") -> None:
        self.update(UIState.PROCESSING, text)
        self.show()

    def speaking(self, text: str = "") -> None:
        self.update(UIState.SPEAKING, text)
        self.show()

    def error(self, msg: str = "") -> None:
        self.update(UIState.ERROR, msg)
        self.show()

    def stop(self) -> None:
        """Detiene la ventana y libera recursos."""
        from AppKit import NSApp

        self._running = False
        if getattr(self, "_pulse_timer", None) is not None:
            try:
                self._pulse_timer.invalidate()
            except Exception:
                pass
            self._pulse_timer = None
        if self._window is not None:
            try:
                self._window.orderOut_(None)
                self._window.close()
            except Exception:
                pass
            self._window = None
        if self._app is not None:
            try:
                NSApp.terminate_(None)
            except Exception:
                pass


class FallbackVisualUI:
    """Fallback cuando no estamos en macOS o hay error: solo consola."""

    def __init__(self) -> None:
        self._state = UIState.IDLE
        self._user_text = ""
        self._belen_text = ""
        self._lock = threading.Lock()
        self._running = False

    def start(self) -> None:
        print("[Belen UI] Modo consola (sin ventana visual).")

    def start_async(self) -> threading.Thread:
        thread = threading.Thread(target=self.start, daemon=True)
        thread.start()
        return thread

    @property
    def state(self) -> UIState:
        return self._state

    def set_callbacks(self, **kwargs: Any) -> None:
        pass

    def update(self, state: UIState, message: str = "") -> None:
        with self._lock:
            self._state = state
            if message:
                if state == UIState.LISTENING:
                    self._user_text = message
                elif state in (UIState.PROCESSING, UIState.SPEAKING, UIState.ERROR):
                    self._belen_text = message
        label = STATE_LABELS[state]
        msg = f" {message}" if message else ""
        print(f"\r[{state.value}] {label}{msg}    ", end="", flush=True)

    def show(self) -> None:
        pass

    def hide(self) -> None:
        pass

    def idle(self) -> None:
        self.update(UIState.IDLE)

    def listening(self) -> None:
        self.update(UIState.LISTENING, "🎤")

    def processing(self, text: str = "") -> None:
        self.update(UIState.PROCESSING, text)

    def speaking(self, text: str = "") -> None:
        self.update(UIState.SPEAKING, text)

    def error(self, msg: str = "") -> None:
        self.update(UIState.ERROR, msg)

    def stop(self) -> None:
        self._running = False


def get_visual_ui() -> Any:
    """Devuelve SiriStyleWindow en macOS, sino FallbackVisualUI."""
    if platform.system() != "Darwin":
        return FallbackVisualUI()
    try:
        import AppKit  # noqa: F401
        import Quartz  # noqa: F401
        return SiriStyleWindow()
    except (ImportError, Exception) as e:
        print(f"[WARN] No se pudo crear UI visual: {e}. Usando fallback consola.")
        return FallbackVisualUI()

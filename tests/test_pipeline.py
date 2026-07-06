"""Tests del pipeline completo (todo mockeado, sin audio/I/O real)."""

import time
from pathlib import Path

import numpy as np

from belen.brain import BrainResponse, MockBrain
from belen.pipeline import BelenPipeline, TurnResult
from belen.project_selector import ProjectMatch
from belen.recorder import AudioRecorder
from belen.stt import STTManager
from belen.tts import MockTTSBackend, TTSManager
from belen.wakeword import WakeWordConfig, WakeWordDetector


def _make_pipeline(stt_response: str = "abrí proyecto foo") -> tuple[BelenPipeline, dict[str, object]]:
    rng = np.random.default_rng(42)
    audio = rng.integers(-5000, 5000, size=16000, dtype=np.int16)

    class _StubSTT:
        def __init__(self, text: str) -> None:
            self._text = text

        def transcribe(self, audio: np.ndarray, sr: int) -> str:
            return self._text

    stt = _StubSTT(stt_response)
    brain = MockBrain(response="respuesta de opencode")
    tts = TTSManager.__new__(TTSManager)
    tts._engine = None
    tts._chain = [MockTTSBackend()]
    tts._active = tts._chain[0]

    pipeline = BelenPipeline.__new__(BelenPipeline)
    pipeline.settings = type("S", (), {
        "belen_default_project": "",
        "belen_floating_ui": False,
    })()
    pipeline.recorder = AudioRecorder()
    pipeline.stt = stt  # type: ignore[assignment]
    pipeline.brain = brain  # type: ignore[assignment]
    pipeline.tts = tts
    pipeline.status = type("Status", (), {
        "idle": lambda self: None,
        "listening": lambda self: None,
        "processing": lambda self, msg="": None,
        "speaking": lambda self, msg="": None,
        "error": lambda self, msg="": None,
    })()
    from belen.ui import ConsoleUI
    pipeline.ui = ConsoleUI()
    pipeline.wakeword = WakeWordDetector(WakeWordConfig(enabled=False, word="x"))
    pipeline._hotkey_listener = None
    pipeline._is_running = False
    pipeline._active_project = None
    pipeline._lock = type("L", (), {"__enter__": lambda s: s, "__exit__": lambda *a: None})()
    pipeline._on_turn = None

    return pipeline, {"audio": audio, "sr": 16000}


def test_pipeline_cambio_proyecto(tmp_path):
    (tmp_path / "foo").mkdir()
    pipeline, ctx = _make_pipeline(stt_response="andá al proyecto foo")
    pipeline.project_selector = type(
        "PS",
        (),
        {
            "select": lambda self, t: ProjectMatch(
                name="foo", path=tmp_path / "foo", score=1.0
            ),
        },
    )()

    result = pipeline.process_turn(ctx["audio"], ctx["sr"])
    assert isinstance(result, TurnResult)
    assert result.project_changed == tmp_path / "foo"
    assert "Cambié al proyecto foo" in result.belen_text


def test_pipeline_prompt_normal():
    pipeline, ctx = _make_pipeline(stt_response="explicame este código")
    pipeline.project_selector = type(
        "PS",
        (),
        {"select": lambda self, t: None},
    )()

    result = pipeline.process_turn(ctx["audio"], ctx["sr"])
    assert result.user_text == "explicame este código"
    assert result.belen_text == "respuesta de opencode"
    assert result.brain_response is not None
    assert result.error is None


def test_pipeline_stt_vacio():
    pipeline, ctx = _make_pipeline(stt_response="")
    result = pipeline.process_turn(ctx["audio"], ctx["sr"])
    assert result.user_text == ""
    assert result.belen_text == ""
    assert result.brain_response is None


def test_pipeline_comando_bloqueado():
    pipeline, ctx = _make_pipeline(stt_response="sudo rm -rf todo")
    pipeline.project_selector = type(
        "PS",
        (),
        {"select": lambda self, t: None},
    )()

    result = pipeline.process_turn(ctx["audio"], ctx["sr"])
    assert result.error is not None
    assert "bloqueado" in result.error.lower() or "No puedo" in result.belen_text


def test_pipeline_on_turn_callback():
    pipeline, ctx = _make_pipeline(stt_response="hola")
    pipeline.project_selector = type(
        "PS",
        (),
        {"select": lambda self, t: None},
    )()

    received: list[TurnResult] = []
    pipeline.on_turn(lambda r: received.append(r))
    pipeline.process_turn(ctx["audio"], ctx["sr"])
    assert len(received) == 1
    assert received[0].user_text == "hola"


def test_pipeline_brain_error():
    pipeline, ctx = _make_pipeline(stt_response="hola")
    pipeline.project_selector = type(
        "PS",
        (),
        {"select": lambda self, t: None},
    )()

    class _FailingBrain:
        def ask_sync(self, prompt, cwd=None, timeout=120.0):
            raise RuntimeError("opencode se cayó")

    pipeline.brain = _FailingBrain()
    result = pipeline.process_turn(ctx["audio"], ctx["sr"])
    assert result.error is not None
    assert "opencode" in result.error.lower()


def test_pipeline_set_active_project():
    pipeline, _ = _make_pipeline()
    assert pipeline.active_project is None
    pipeline.set_active_project(Path("/tmp/foo"))
    assert pipeline.active_project == Path("/tmp/foo")

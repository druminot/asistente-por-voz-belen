"""Tests del brain (mockeado, sin ejecutar opencode real)."""

from belen.brain import BrainResponse, MockBrain, OpenCodeBrain


def test_mock_brain_response():
    brain = MockBrain(response="hola desde mock")
    resp = brain.ask_sync("test prompt")
    assert isinstance(resp, BrainResponse)
    assert resp.text == "hola desde mock"
    assert resp.model == "mock"
    assert len(brain._calls) == 1


def test_mock_brain_async():
    import asyncio

    async def run():
        brain = MockBrain(response="async ok")
        resp = await brain.ask("test")
        return resp

    resp = asyncio.run(run())
    assert resp.text == "async ok"


def test_mock_brain_info():
    brain = MockBrain()
    info = brain.info()
    assert info["model"] == "mock"
    assert info["available"] is True


def test_opencode_brain_info():
    brain = OpenCodeBrain(
        bin_path="opencode",
        model="ollama-cloud/minimax-m3",
        cwd=None,
    )
    info = brain.info()
    assert info["bin"] == "opencode"
    assert info["model"] == "ollama-cloud/minimax-m3"
    assert info["available"] is True  # porque opencode está en PATH


def test_opencode_brain_unavailable():
    brain = OpenCodeBrain(bin_path="no-existe-este-bin", model="x/y")
    assert brain.is_available() is False


def test_brain_response_dataclass():
    resp = BrainResponse(
        text="hola",
        model="test",
        duration_seconds=0.5,
        raw_stdout="hola",
        raw_stderr="",
    )
    assert resp.text == "hola"
    assert resp.duration_seconds == 0.5

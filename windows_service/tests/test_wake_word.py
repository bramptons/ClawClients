"""Tests for the WakeWordDetector."""

import sys
import threading
import time
import types

import pytest


def _make_sr_stub():
    """Build a minimal stub of the speech_recognition module."""
    sr = types.ModuleType("speech_recognition")

    class WaitTimeoutError(Exception):
        pass

    class UnknownValueError(Exception):
        pass

    class RequestError(Exception):
        pass

    sr.WaitTimeoutError = WaitTimeoutError
    sr.UnknownValueError = UnknownValueError
    sr.RequestError = RequestError
    sr.Recognizer = object  # placeholder
    sr.Microphone = object  # placeholder
    return sr


@pytest.fixture(autouse=True)
def patch_sr(monkeypatch):
    """Inject a minimal speech_recognition stub so no real mic is needed."""
    stub = _make_sr_stub()
    monkeypatch.setitem(sys.modules, "speech_recognition", stub)
    # Force reimport of wake_word with the stub in place
    for key in list(sys.modules.keys()):
        if "wake_word" in key:
            del sys.modules[key]
    yield


def _import_wake_word():
    try:
        from windows_service.src import wake_word
    except ImportError:
        from src import wake_word
    return wake_word


class TestWakeWordDetector:
    def test_initial_state(self):
        ww = _import_wake_word()
        d = ww.WakeWordDetector()
        assert not d.is_running
        assert not d.is_active

    def test_activate_listening_triggers_callback(self):
        ww = _import_wake_word()
        events = []
        d = ww.WakeWordDetector(on_wake=lambda: events.append("wake"))
        d.activate_listening()
        assert events == ["wake"]
        assert d.is_active

    def test_stop_listening_triggers_callback(self):
        ww = _import_wake_word()
        events = []
        d = ww.WakeWordDetector(on_stop=lambda: events.append("stop"))
        d._active_listening = True
        d.stop_listening()
        assert events == ["stop"]
        assert not d.is_active

    def test_activate_idempotent(self):
        ww = _import_wake_word()
        calls = []
        d = ww.WakeWordDetector(on_wake=lambda: calls.append(1))
        d.activate_listening()
        d.activate_listening()  # second call should be a no-op
        assert len(calls) == 1

    def test_stop_listening_idempotent(self):
        ww = _import_wake_word()
        calls = []
        d = ww.WakeWordDetector(on_stop=lambda: calls.append(1))
        # Not yet active — stop should be a no-op
        d.stop_listening()
        assert calls == []

    def test_handle_text_wake_word(self):
        ww = _import_wake_word()
        events = []
        d = ww.WakeWordDetector(
            wake_word="hey claw",
            on_wake=lambda: events.append("wake"),
        )
        d._handle_text("hey claw how are you")
        assert "wake" in events
        assert d.is_active

    def test_handle_text_stop_phrase(self):
        ww = _import_wake_word()
        events = []
        d = ww.WakeWordDetector(
            stop_phrase="stop listening",
            on_stop=lambda: events.append("stop"),
        )
        d._active_listening = True
        d._handle_text("please stop listening now")
        assert "stop" in events
        assert not d.is_active

    def test_handle_text_forwards_speech_while_active(self):
        ww = _import_wake_word()
        spoken = []
        d = ww.WakeWordDetector(on_speech=lambda t: spoken.append(t))
        d._active_listening = True
        d._handle_text("turn on the lights")
        assert spoken == ["turn on the lights"]

    def test_handle_text_ignores_speech_while_inactive(self):
        ww = _import_wake_word()
        spoken = []
        d = ww.WakeWordDetector(on_speech=lambda t: spoken.append(t))
        d._handle_text("some random phrase")
        assert spoken == []

"""Tests for the GatewayClient."""

import asyncio
import json
import sys
import time
import types

import pytest


def _import_gateway():
    try:
        from windows_service.src import gateway_client
    except ImportError:
        from src import gateway_client
    return gateway_client


class TestGatewayClientPublicApi:
    """Unit tests that do not require a live WebSocket server."""

    def test_initial_state(self):
        gc = _import_gateway()
        client = gc.GatewayClient("ws://localhost:9999/ws")
        assert not client.connected
        assert client._running is False

    def test_enqueue_does_not_raise_when_not_started(self):
        gc = _import_gateway()
        client = gc.GatewayClient("ws://localhost:9999/ws")
        # Should silently do nothing (loop not yet running)
        client.send_text("hello")
        client.send_event("test_event", {"key": "value"})

    def test_send_audio_encodes_base64(self):
        import base64
        gc = _import_gateway()
        client = gc.GatewayClient("ws://localhost:9999/ws")
        # Patch _enqueue to capture the message
        captured = []
        client._enqueue = lambda msg: captured.append(msg)
        client.send_audio(b"\x00\x01\x02")
        assert captured[0]["type"] == "audio"
        decoded = base64.b64decode(captured[0]["payload"])
        assert decoded == b"\x00\x01\x02"

    def test_send_text_message_format(self):
        gc = _import_gateway()
        client = gc.GatewayClient("ws://localhost:9999/ws")
        captured = []
        client._enqueue = lambda msg: captured.append(msg)
        client.send_text("turn on the lights")
        assert captured[0] == {"type": "text", "payload": "turn on the lights"}

    def test_send_event_message_format(self):
        gc = _import_gateway()
        client = gc.GatewayClient("ws://localhost:9999/ws")
        captured = []
        client._enqueue = lambda msg: captured.append(msg)
        client.send_event("listening_started", {"source": "wake_word"})
        assert captured[0] == {
            "type": "listening_started",
            "data": {"source": "wake_word"},
        }

    def test_send_event_default_empty_data(self):
        gc = _import_gateway()
        client = gc.GatewayClient("ws://localhost:9999/ws")
        captured = []
        client._enqueue = lambda msg: captured.append(msg)
        client.send_event("ping")
        assert captured[0]["data"] == {}

    def test_stop_when_not_started_is_safe(self):
        gc = _import_gateway()
        client = gc.GatewayClient("ws://localhost:9999/ws")
        client.stop()  # Must not raise

    def test_start_sets_running_flag(self):
        gc = _import_gateway()
        client = gc.GatewayClient("ws://localhost:9999/ws")
        # Override _run_loop so the thread exits immediately
        client._run_loop = lambda: None
        client.start()
        time.sleep(0.05)
        assert client._running is True
        client.stop()

    def test_start_idempotent(self):
        gc = _import_gateway()
        client = gc.GatewayClient("ws://localhost:9999/ws")
        client._run_loop = lambda: None
        client.start()
        thread_1 = client._thread
        client.start()  # second call should be a no-op
        assert client._thread is thread_1
        client.stop()

"""
Async WebSocket client for communicating with an OpenClaw gateway.
Handles automatic reconnection and message queuing.
"""

import asyncio
import json
import logging
import threading
from typing import Callable, Optional

try:
    import websockets
    from websockets.exceptions import ConnectionClosed, WebSocketException
    _WS_AVAILABLE = True
except ImportError:
    _WS_AVAILABLE = False

logger = logging.getLogger(__name__)


class GatewayClient:
    """
    Manages a persistent WebSocket connection to an OpenClaw gateway.

    Usage::

        client = GatewayClient("ws://192.168.1.100:8765/ws")
        client.start()
        client.send_text("Hello, Claw!")
        client.stop()
    """

    def __init__(
        self,
        uri: str,
        on_message: Optional[Callable[[dict], None]] = None,
        reconnect_interval: float = 5.0,
    ) -> None:
        self._uri = uri
        self._on_message = on_message
        self._reconnect_interval = reconnect_interval
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._ws = None
        self._send_queue: Optional[asyncio.Queue] = None
        self.connected = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the gateway client in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="GatewayClientThread"
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the gateway client and close the WebSocket connection."""
        self._running = False
        if self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._loop.stop)

    def send_text(self, text: str) -> None:
        """Enqueue a plain-text command for the gateway."""
        self._enqueue({"type": "text", "payload": text})

    def send_audio(self, audio_bytes: bytes) -> None:
        """Enqueue a base64-encoded audio chunk for the gateway."""
        import base64
        self._enqueue({"type": "audio", "payload": base64.b64encode(audio_bytes).decode()})

    def send_event(self, event_type: str, data: Optional[dict] = None) -> None:
        """Enqueue a typed event message for the gateway."""
        self._enqueue({"type": event_type, "data": data or {}})

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _enqueue(self, message: dict) -> None:
        if self._loop and self._send_queue and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._send_queue.put_nowait, message)

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._send_queue = asyncio.Queue()
        try:
            self._loop.run_until_complete(self._connect_loop())
        finally:
            self._loop.close()

    async def _connect_loop(self) -> None:
        while self._running:
            if not _WS_AVAILABLE:
                logger.error(
                    "websockets package is not installed. "
                    "Install it with: pip install websockets"
                )
                await asyncio.sleep(self._reconnect_interval)
                continue
            try:
                logger.info("Connecting to gateway at %s", self._uri)
                async with websockets.connect(self._uri) as ws:
                    self._ws = ws
                    self.connected = True
                    logger.info("Connected to gateway")
                    await asyncio.gather(
                        self._receive_loop(ws),
                        self._send_loop(ws),
                    )
            except (ConnectionClosed, WebSocketException, OSError) as exc:
                self.connected = False
                self._ws = None
                if self._running:
                    logger.warning(
                        "Gateway connection lost (%s). Reconnecting in %ss…",
                        exc,
                        self._reconnect_interval,
                    )
                    await asyncio.sleep(self._reconnect_interval)
            except Exception as exc:  # noqa: BLE001
                self.connected = False
                self._ws = None
                if self._running:
                    logger.error("Unexpected gateway error: %s", exc)
                    await asyncio.sleep(self._reconnect_interval)

    async def _receive_loop(self, ws) -> None:
        async for raw in ws:
            if not self._running:
                break
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                message = {"type": "raw", "payload": raw}
            if self._on_message:
                try:
                    self._on_message(message)
                except Exception as exc:  # noqa: BLE001
                    logger.error("on_message callback raised: %s", exc)

    async def _send_loop(self, ws) -> None:
        while self._running:
            try:
                message = await asyncio.wait_for(self._send_queue.get(), timeout=1.0)
                await ws.send(json.dumps(message))
            except asyncio.TimeoutError:
                continue
            except (ConnectionClosed, WebSocketException):
                break

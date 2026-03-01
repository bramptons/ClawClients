"""
Main orchestrator for the OpenClaw Windows client.

Wires together:
  - FloatingWidget    (UI)
  - WakeWordDetector  (microphone / speech recognition)
  - GatewayClient     (WebSocket to OpenClaw gateway)

Can run as a plain Python process (python -m src.main) *or* be installed
as a Windows service via service.py.
"""

import logging
import os
import signal
import sys
import time
from typing import Optional

from .config import get_gateway_uri, load_config, save_config
from .floating_widget import FloatingWidget
from .gateway_client import GatewayClient
from .wake_word import WakeWordDetector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class OpenClawClient:
    """Top-level coordinator for the OpenClaw client."""

    def __init__(self, config: Optional[dict] = None) -> None:
        self._config = config or load_config()
        self._gateway: Optional[GatewayClient] = None
        self._detector: Optional[WakeWordDetector] = None
        self._widget: Optional[FloatingWidget] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Initialise and start all subsystems."""
        cfg = self._config

        # Gateway client
        uri = get_gateway_uri(cfg)
        self._gateway = GatewayClient(
            uri=uri,
            on_message=self._on_gateway_message,
            reconnect_interval=cfg.get("reconnect_interval_seconds", 5),
        )
        self._gateway.start()
        logger.info("Gateway client started → %s", uri)

        # Wake word detector
        self._detector = WakeWordDetector(
            wake_word=cfg.get("wake_word", "hey claw"),
            stop_phrase=cfg.get("stop_phrase", "stop listening"),
            on_wake=self._on_wake,
            on_speech=self._on_speech,
            on_stop=self._on_stop_phrase,
            speech_timeout=cfg.get("speech_timeout_seconds", 5),
            phrase_timeout=cfg.get("phrase_timeout_seconds", 10),
        )
        self._detector.start()

        # Floating widget
        self._widget = FloatingWidget(
            on_start_listening=self._on_widget_start,
            on_stop_listening=self._on_widget_stop,
            on_close=self._on_widget_close,
            initial_x=cfg.get("widget_x", 50),
            initial_y=cfg.get("widget_y", 50),
            opacity=cfg.get("widget_opacity", 0.85),
        )
        self._widget.start()

        # Update widget status once gateway reports connection
        self._widget.set_status("Idle", listening=False, connected=False)

        if cfg.get("auto_start_listening", False):
            self._on_widget_start()

        logger.info("OpenClaw client running.")

    def stop(self) -> None:
        """Gracefully stop all subsystems."""
        logger.info("Stopping OpenClaw client…")
        if self._detector:
            self._detector.stop()
        if self._gateway:
            self._gateway.stop()
        if self._widget:
            # Save last widget position
            if self._widget._root:
                try:
                    x = self._widget._root.winfo_x()
                    y = self._widget._root.winfo_y()
                    self._config["widget_x"] = x
                    self._config["widget_y"] = y
                    save_config(self._config)
                except Exception:  # noqa: BLE001
                    pass
            self._widget.stop()
        logger.info("OpenClaw client stopped.")

    def run_forever(self) -> None:
        """Block the calling thread until SIGINT/SIGTERM."""
        self.start()
        try:
            while True:
                time.sleep(1)
                # Reflect gateway connection state in the widget
                if self._widget and self._gateway:
                    if self._gateway.connected:
                        if self._detector and self._detector.is_active:
                            self._widget.set_status("Listening…", listening=True)
                        else:
                            self._widget.set_status("Connected", connected=True)
                    else:
                        self._widget.set_status("Connecting…")
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            self.stop()

    # ------------------------------------------------------------------
    # Wake word / speech callbacks
    # ------------------------------------------------------------------

    def _on_wake(self) -> None:
        logger.info("Wake word detected — activating listening.")
        if self._widget:
            self._widget.set_status("Listening…", listening=True)
        if self._gateway:
            self._gateway.send_event("listening_started")

    def _on_speech(self, text: str) -> None:
        logger.info("Recognised speech: %r", text)
        if self._widget:
            self._widget.set_status(f"Heard: {text[:30]}", listening=True)
        if self._gateway:
            self._gateway.send_text(text)

    def _on_stop_phrase(self) -> None:
        logger.info("Stop phrase detected — deactivating listening.")
        if self._widget:
            self._widget.set_status(
                "Connected" if (self._gateway and self._gateway.connected) else "Idle",
                connected=bool(self._gateway and self._gateway.connected),
            )
        if self._gateway:
            self._gateway.send_event("listening_stopped")

    # ------------------------------------------------------------------
    # Widget button callbacks
    # ------------------------------------------------------------------

    def _on_widget_start(self) -> None:
        logger.info("Widget: Start Listening pressed.")
        if self._detector:
            self._detector.activate_listening()

    def _on_widget_stop(self) -> None:
        logger.info("Widget: Stop Listening pressed.")
        if self._detector:
            self._detector.stop_listening()

    def _on_widget_close(self) -> None:
        logger.info("Widget close — minimising to system tray.")
        if self._widget and self._widget._root:
            self._widget._root.withdraw()

    # ------------------------------------------------------------------
    # Gateway message callback
    # ------------------------------------------------------------------

    def _on_gateway_message(self, message: dict) -> None:
        logger.info("Gateway message: %s", message)
        msg_type = message.get("type", "")
        if msg_type == "tts":
            # Gateway sent back a TTS response – update status briefly
            payload = message.get("payload", "")
            if self._widget:
                self._widget.set_status(
                    f"Response: {str(payload)[:30]}", connected=True
                )


def main() -> None:
    client = OpenClawClient()
    # Register clean shutdown on Ctrl-C / SIGTERM
    def _shutdown_handler(sig, frame):  # noqa: ANN001
        client.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown_handler)

    client.run_forever()


if __name__ == "__main__":
    main()

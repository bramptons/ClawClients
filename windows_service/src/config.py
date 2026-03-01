"""
Configuration management for the OpenClaw Windows client service.
Settings are persisted to a JSON file in the user's AppData directory.
"""

import json
import os
from pathlib import Path

_DEFAULT_CONFIG = {
    "gateway_host": "localhost",
    "gateway_port": 8765,
    "gateway_path": "/ws",
    "wake_word": "hey claw",
    "stop_phrase": "stop listening",
    "widget_x": 50,
    "widget_y": 50,
    "widget_opacity": 0.85,
    "auto_start_listening": False,
    "reconnect_interval_seconds": 5,
    "speech_timeout_seconds": 5,
    "phrase_timeout_seconds": 10,
}

def _config_dir() -> Path:
    return Path(os.environ.get("APPDATA", Path.home())) / "OpenClawClient"


def _config_file() -> Path:
    return _config_dir() / "config.json"


def _ensure_config_dir() -> None:
    _config_dir().mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """Load configuration from disk, filling in defaults for any missing keys."""
    _ensure_config_dir()
    config = dict(_DEFAULT_CONFIG)
    cfg_file = _config_file()
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as fh:
                stored = json.load(fh)
            config.update(stored)
        except (json.JSONDecodeError, OSError):
            pass
    return config


def save_config(config: dict) -> None:
    """Persist configuration to disk."""
    _ensure_config_dir()
    with open(_config_file(), "w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=2)


def get_gateway_uri(config: dict) -> str:
    """Build a WebSocket URI from config values."""
    host = config.get("gateway_host", _DEFAULT_CONFIG["gateway_host"])
    port = config.get("gateway_port", _DEFAULT_CONFIG["gateway_port"])
    path = config.get("gateway_path", _DEFAULT_CONFIG["gateway_path"])
    return f"ws://{host}:{port}{path}"

"""Tests for the configuration module."""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest


def _import_config():
    # Support running as `pytest windows_service/` or from repo root
    try:
        from windows_service.src import config
    except ImportError:
        from src import config
    return config


class TestLoadConfig:
    def test_returns_defaults_when_no_file_exists(self):
        config = _import_config()
        cfg = config.load_config()
        assert cfg["gateway_host"] == "localhost"
        assert cfg["gateway_port"] == 8765
        assert cfg["wake_word"] == "hey claw"
        assert cfg["stop_phrase"] == "stop listening"

    def test_merges_stored_values_over_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setenv("APPDATA", str(tmp_path))
        config = _import_config()
        config_dir = tmp_path / "OpenClawClient"
        config_dir.mkdir()
        (config_dir / "config.json").write_text(
            json.dumps({"gateway_host": "192.168.1.42", "gateway_port": 9000}),
            encoding="utf-8",
        )
        cfg = config.load_config()
        assert cfg["gateway_host"] == "192.168.1.42"
        assert cfg["gateway_port"] == 9000
        # Defaults still present for unspecified keys
        assert cfg["wake_word"] == "hey claw"

    def test_survives_corrupt_json(self, tmp_path, monkeypatch):
        monkeypatch.setenv("APPDATA", str(tmp_path))
        config = _import_config()
        config_dir = tmp_path / "OpenClawClient"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{broken json", encoding="utf-8")
        cfg = config.load_config()
        assert cfg["gateway_host"] == "localhost"


class TestSaveConfig:
    def test_round_trip(self, tmp_path, monkeypatch):
        monkeypatch.setenv("APPDATA", str(tmp_path))
        config = _import_config()
        cfg = config.load_config()
        cfg["gateway_host"] = "10.0.0.1"
        config.save_config(cfg)
        loaded = config.load_config()
        assert loaded["gateway_host"] == "10.0.0.1"


class TestGetGatewayUri:
    def test_default_uri(self):
        config = _import_config()
        cfg = config.load_config()
        uri = config.get_gateway_uri(cfg)
        assert uri == "ws://localhost:8765/ws"

    def test_custom_host_port_path(self):
        config = _import_config()
        cfg = {
            "gateway_host": "192.168.1.5",
            "gateway_port": 4000,
            "gateway_path": "/openai",
        }
        uri = config.get_gateway_uri(cfg)
        assert uri == "ws://192.168.1.5:4000/openai"

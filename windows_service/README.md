# OpenClaw Windows Client — `windows_service`

A lightweight background service for **Windows 11** that connects to an
[OpenClaw gateway](https://github.com/bramptons/ClawClients) running on your
local network and provides voice-activated AI assistant capabilities through a
persistent floating widget.

---

## Features

| Feature | Details |
|---|---|
| **Wake word detection** | Configurable wake phrase (default `"hey claw"`) starts active listening |
| **Stop phrase** | Configurable stop phrase (default `"stop listening"`) pauses listening |
| **Floating widget** | Always-on-top, semi-transparent, draggable control panel |
| **Start / Stop buttons** | Manually activate or deactivate the microphone from the widget |
| **Gateway communication** | Persistent WebSocket connection with automatic reconnection |
| **Windows Service** | Optional NT service install (runs at boot, no console window) |
| **Lightweight** | Only Tkinter (stdlib), SpeechRecognition, websockets, pywin32 |

---

## Requirements

* Python 3.9+ on Windows 11 (or Windows 10)
* A running [OpenClaw gateway](https://github.com/bramptons/ClawClients) on your local network
* A working microphone

---

## Quick start (standalone process)

```bash
cd windows_service
pip install -r requirements.txt
python -m src.main
```

The floating widget will appear in the top-left corner of your screen.

---

## Install as a Windows service

Run the following from an **Administrator** command prompt:

```bat
cd windows_service
install_service.bat
```

To uninstall:

```bat
uninstall_service.bat
```

Or use the service manager commands directly:

```bat
python -m src.service install
python -m src.service start
python -m src.service stop
python -m src.service remove
```

---

## Configuration

On first run, a configuration file is written to:

```
%APPDATA%\OpenClawClient\config.json
```

Edit it to customise the client:

```json
{
  "gateway_host":              "192.168.1.100",
  "gateway_port":              8765,
  "gateway_path":              "/ws",
  "wake_word":                 "hey claw",
  "stop_phrase":               "stop listening",
  "widget_x":                  50,
  "widget_y":                  50,
  "widget_opacity":            0.85,
  "auto_start_listening":      false,
  "reconnect_interval_seconds": 5,
  "speech_timeout_seconds":    5,
  "phrase_timeout_seconds":    10
}
```

---

## Usage

### Wake word

Say **"hey claw"** (or your configured wake word) — the widget status turns
green and the client begins forwarding recognised speech to the gateway.

### Stop phrase

Say **"stop listening"** (or your configured stop phrase) to pause recognition.

### Widget buttons

| Button | Action |
|---|---|
| ▶ **Start Listening** | Manually activate the microphone (same as saying the wake word) |
| ■ **Stop Listening** | Manually pause the microphone |
| **×** | Hide the widget (service keeps running) |

The widget is draggable — click and drag the title bar to reposition it.
Its position is saved automatically on shutdown.

---

## Architecture

```
windows_service/
├── src/
│   ├── config.py          # Persistent JSON config (APPDATA)
│   ├── gateway_client.py  # Async WebSocket client with auto-reconnect
│   ├── wake_word.py       # Microphone capture + wake/stop phrase detection
│   ├── floating_widget.py # Always-on-top Tkinter control panel
│   ├── main.py            # Orchestrator — wires all subsystems together
│   └── service.py         # pywin32 Windows NT service wrapper
├── tests/
│   ├── test_config.py
│   ├── test_gateway_client.py
│   └── test_wake_word.py
├── requirements.txt
├── requirements-dev.txt
├── install_service.bat
└── uninstall_service.bat
```

---

## Running tests

```bash
pip install -r requirements-dev.txt
pytest windows_service/tests/ -v
```

---

## Logging

Log output goes to **stdout** when running as a standalone process and to the
**Windows Event Log** when running as an NT service.

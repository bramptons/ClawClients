"""
Windows Service wrapper for the OpenClaw client.

Installs and runs the OpenClaw client as a persistent Windows NT service
using the ``pywin32`` package.

Usage
-----
Install   : python -m src.service install
Start     : python -m src.service start
Stop      : python -m src.service stop
Remove    : python -m src.service remove
Debug run : python -m src.service debug
"""

import logging
import sys
import time

logger = logging.getLogger(__name__)

_SERVICE_NAME = "OpenClawClient"
_SERVICE_DISPLAY_NAME = "OpenClaw Client Service"
_SERVICE_DESCRIPTION = (
    "Lightweight Windows client for the OpenClaw AI gateway. "
    "Provides wake-word detection and a floating control widget."
)

try:
    import win32event
    import win32service
    import win32serviceutil
    import servicemanager

    _WIN32_AVAILABLE = True
except ImportError:
    _WIN32_AVAILABLE = False


if _WIN32_AVAILABLE:

    class OpenClawService(win32serviceutil.ServiceFramework):
        _svc_name_ = _SERVICE_NAME
        _svc_display_name_ = _SERVICE_DISPLAY_NAME
        _svc_description_ = _SERVICE_DESCRIPTION

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self._stop_event = win32event.CreateEvent(None, 0, 0, None)
            self._client = None

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self._stop_event)
            if self._client:
                self._client.stop()

        def SvcDoRun(self):
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, ""),
            )
            self._main()

        def _main(self):
            from .main import OpenClawClient
            from .config import load_config

            self._client = OpenClawClient(load_config())
            self._client.start()
            # Block until the stop event is signalled
            win32event.WaitForSingleObject(self._stop_event, win32event.INFINITE)


def run_service_cli():
    """Entry point for service management commands."""
    if not _WIN32_AVAILABLE:
        print(
            "ERROR: pywin32 is not installed. "
            "Install it with: pip install pywin32\n"
            "On non-Windows systems the service wrapper is unavailable.\n"
            "Run the client directly with: python -m src.main"
        )
        sys.exit(1)

    if len(sys.argv) == 1:
        # No arguments — attempt to start as a service
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(OpenClawService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(OpenClawService)


if __name__ == "__main__":
    run_service_cli()

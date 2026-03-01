@echo off
REM Uninstall the OpenClaw client Windows service.
REM Must be run from an elevated (Administrator) command prompt.

cd /d "%~dp0"

python -m src.service stop
python -m src.service remove
echo.
echo OpenClaw Client service removed.
pause

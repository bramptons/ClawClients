@echo off
REM Install the OpenClaw client as a Windows service.
REM Must be run from an elevated (Administrator) command prompt.

cd /d "%~dp0"

python -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

python -m src.service install
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install service.
    pause
    exit /b 1
)

python -m src.service start
echo.
echo OpenClaw Client service installed and started successfully.
pause

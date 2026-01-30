@echo off
setlocal enabledelayedexpansion

title Hytale Launcher

REM Get the directory of this script
set "SCRIPT_DIR=%~dp0"
REM Remove trailing backslash if present
if "!SCRIPT_DIR:~-1!"=="\" set "SCRIPT_DIR=!SCRIPT_DIR:~0,-1!"

set "HYTALE_DIR=!SCRIPT_DIR!"
set "LAUNCHER_DIR=!HYTALE_DIR!\launcher"
set "PYTHON_DIR=!LAUNCHER_DIR!\python-3.14.2-embed-amd64"
set "PYTHON_CMD=!PYTHON_DIR!\python.exe"

REM Create directories if missing
if not exist "!LAUNCHER_DIR!" mkdir "!LAUNCHER_DIR!"
if not exist "!HYTALE_DIR!\UserData" mkdir "!HYTALE_DIR!\UserData"

REM Check if Python exists (should be pre-installed in launcher)
if not exist "!PYTHON_CMD!" (
    echo [!] Python not found at !PYTHON_CMD!
    echo [!] Python should be pre-installed in the launcher directory
    pause
    exit /b 1
)

echo [+] Python ready

REM Start the standalone.py server (handles UI and client launch)
echo [*] Starting Hytale...
"!PYTHON_CMD!" "!LAUNCHER_DIR!\standalone.py"

exit /b 0
@echo off
setlocal enabledelayedexpansion

title Hytale Launcher

REM Get the directory of this script
set "SCRIPT_DIR=%~dp0"
REM Remove trailing backslash if present
if "!SCRIPT_DIR:~-1!"=="\" set "SCRIPT_DIR=!SCRIPT_DIR:~0,-1!"

set "GAME_DIR=!SCRIPT_DIR!\game"
set "HYTALE_DIR=!SCRIPT_DIR!"

REM Configuration
set "PLAYER_NAME=%~1"
if "!PLAYER_NAME!"=="" set "PLAYER_NAME=!USERNAME!"

echo [*] Hytale Launcher
echo [*] Player: !PLAYER_NAME!

REM Check if required directories exist
if not exist "!GAME_DIR!\data\Server" (
    echo [!] Server directory not found at !GAME_DIR!\data\Server
    pause
    exit /b 1
)

if not exist "!GAME_DIR!\data\Client" (
    echo [!] Client directory not found at !GAME_DIR!\data\Client
    pause
    exit /b 1
)

REM Setup embedded Python
echo [*] Setting up Python...
call "!SCRIPT_DIR!setup_python.bat"
if !errorlevel! neq 0 (
    echo [!] Failed to setup Python
    pause
    exit /b 1
)

set "PYTHON_DIR=!SCRIPT_DIR!python-3.14.2-embed-amd64"
set "PYTHON_CMD=!PYTHON_DIR!\python.exe"

if not exist "!PYTHON_CMD!" (
    echo [!] Python executable not found
    pause
    exit /b 1
)

echo [+] Python ready

REM Create launcher directory if missing
if not exist "!HYTALE_DIR!\launcher" mkdir "!HYTALE_DIR!\launcher"

REM Start the standalone.py server in background
echo [*] Starting standalone emulator server...
start /b "Hytale Emulator Server" "!PYTHON_CMD!" "!SCRIPT_DIR!standalone.py" > "!HYTALE_DIR!\launcher\standalone.log" 2>&1

REM Give the server a moment to start
timeout /t 2 /nobreak

REM Create UserData folder if missing
if not exist "!HYTALE_DIR!\UserData" mkdir "!HYTALE_DIR!\UserData"

REM Launch the client
echo [*] Launching Hytale client...
start "" "!GAME_DIR!\data\Client\HytaleClient.exe" ^
  --app-dir "!GAME_DIR!\data" ^
  --user-dir "!HYTALE_DIR!\UserData" ^
  --java-exec "!GAME_DIR!\jre\bin\java.exe" ^
  --auth-mode offline ^
  --uuid 13371337-1337-1337-1337-133713371337 ^
  --name "!PLAYER_NAME!"

REM Close this launcher window
exit /b 0
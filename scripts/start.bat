@echo off
title Hytale Launcher

REM Set Hytale directory to current folder
set "HYTALE_DIR=%~dp0"

REM Remove trailing backslash if present
if "%HYTALE_DIR:~-1%"=="\" set "HYTALE_DIR=%HYTALE_DIR:~0,-1%"

REM Player name (default = Windows username, or first argument)
set "PLAYER_NAME=%USERNAME%"
if not "%~1"=="" set "PLAYER_NAME=%~1"

REM Create UserData folder if missing
if not exist "%HYTALE_DIR%\UserData" mkdir "%HYTALE_DIR%\UserData"

REM Launch Hytale
REM Paths adjusted to match the portable build structure
start "" "%HYTALE_DIR%\game\data\Client\HytaleClient.exe" ^
  --app-dir "%HYTALE_DIR%\game\data" ^
  --user-dir "%HYTALE_DIR%\UserData" ^
  --java-exec "%HYTALE_DIR%\game\jre\bin\java.exe" ^
  --auth-mode offline ^
  --uuid 13371337-1337-1337-1337-133713371337 ^
  --name "%PLAYER_NAME%"

REM Close immediately
exit
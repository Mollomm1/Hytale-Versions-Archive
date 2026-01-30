@echo off
REM Setup script for embedded Python on Windows
REM Downloads Python 3.14.2 embedded distribution if not present

setlocal enabledelayedexpansion

set "PYTHON_DIR=%~dp0python-3.14.2-embed-amd64"
set "PYTHON_ZIP=%~dp0python-3.14.2-embed-amd64.zip"
set "PYTHON_URL=https://www.python.org/ftp/python/3.14.2/python-3.14.2-embed-amd64.zip"

if exist "!PYTHON_DIR!" (
    echo [*] Python embedded version already exists
    exit /b 0
)

if exist "!PYTHON_ZIP!" (
    echo [*] Python ZIP found, extracting...
    powershell -Command "Expand-Archive -Path '!PYTHON_ZIP!' -DestinationPath '!PYTHON_DIR!' -Force"
    if !errorlevel! neq 0 (
        echo [!] Error extracting Python
        exit /b 1
    )
    echo [+] Python extracted successfully
    exit /b 0
)

echo [*] Downloading Python 3.14.2 embedded...
powershell -Command "& { $ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri '!PYTHON_URL!' -OutFile '!PYTHON_ZIP!' }"

if !errorlevel! neq 0 (
    echo [!] Error downloading Python
    exit /b 1
)

echo [*] Python downloaded, extracting...
powershell -Command "Expand-Archive -Path '!PYTHON_ZIP!' -DestinationPath '!PYTHON_DIR!' -Force"

if !errorlevel! neq 0 (
    echo [!] Error extracting Python
    exit /b 1
)

echo [+] Python setup completed successfully
exit /b 0

#!/bin/bash

# Hytale Launcher with Pre-Patched Standalone Emulator
# Note: Game files are pre-patched by the build workflow

set -e

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HYTALE_DIR="$SCRIPT_DIR"
LAUNCHER_DIR="$HYTALE_DIR/launcher"

# Create directories if missing
mkdir -p "$LAUNCHER_DIR" "$HYTALE_DIR/UserData"

# Try embedded Python first, then system Python
if [ -f "$LAUNCHER_DIR/python-3.14.2-embed-amd64/bin/python" ]; then
    PYTHON_CMD="$LAUNCHER_DIR/python-3.14.2-embed-amd64/bin/python"
elif [ -f "$LAUNCHER_DIR/python-3.14.2-embed-amd64/bin/python3" ]; then
    PYTHON_CMD="$LAUNCHER_DIR/python-3.14.2-embed-amd64/bin/python3"
else
    PYTHON_CMD="python3"
    if ! command -v $PYTHON_CMD &> /dev/null; then
        echo "[!] Python 3 is required but not installed"
        exit 1
    fi
fi

echo "[*] Starting Hytale..."
# Start the standalone.py server
$PYTHON_CMD "$LAUNCHER_DIR/standalone.py"

exit 0

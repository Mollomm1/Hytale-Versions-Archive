#!/bin/bash

# Hytale Launcher with Pre-Patched Standalone Emulator
# Note: Game files are pre-patched by the build workflow

set -e

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GAME_DIR="$SCRIPT_DIR/game"
HYTALE_DIR="$SCRIPT_DIR"

# Configuration
PLAYER_NAME="${1:-$USER}"
PYTHON_CMD="python3"

echo "[*] Hytale Launcher"
echo "[*] Player: $PLAYER_NAME"

# Check if required directories exist
if [ ! -d "$GAME_DIR/data/Server" ]; then
    echo "[!] Server directory not found at $GAME_DIR/data/Server"
    exit 1
fi

if [ ! -d "$GAME_DIR/data/Client" ]; then
    echo "[!] Client directory not found at $GAME_DIR/data/Client"
    exit 1
fi

# Check Python installation
if ! command -v $PYTHON_CMD &> /dev/null; then
    echo "[!] Python 3 is required but not installed"
    exit 1
fi

# Create launcher directory if missing
mkdir -p "$HYTALE_DIR/launcher"

echo "[*] Starting standalone emulator server..."
# Start the standalone.py server in background
$PYTHON_CMD "$SCRIPT_DIR/standalone.py" > "$HYTALE_DIR/launcher/standalone.log" 2>&1 &
STANDALONE_PID=$!
echo "[+] Standalone server started (PID: $STANDALONE_PID)"

# Give the server a moment to start
sleep 2

# Create UserData folder if missing
mkdir -p "$HYTALE_DIR/UserData"

# Launch the client
echo "[*] Launching Hytale client..."
trap "kill $STANDALONE_PID 2>/dev/null || true" EXIT

"$GAME_DIR/data/Client/HytaleClient" \
  --app-dir "$GAME_DIR/data" \
  --user-dir "$HYTALE_DIR/UserData" \
  --java-exec "$GAME_DIR/jre/bin/java" \
  --auth-mode offline \
  --uuid 13371337-1337-1337-1337-133713371337 \
  --name "$PLAYER_NAME"

# Cleanup happens via trap
exit 0

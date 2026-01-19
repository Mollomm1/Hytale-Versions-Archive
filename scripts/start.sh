#!/bin/bash

# Ensure we are in the directory of the script
cd "$(dirname "$0")"

./game/data/Client/HytaleClient \
  --app-dir "$PWD/game/data" \
  --user-dir "$PWD/UserData" \
  --java-exec "$PWD/game/jre/bin/java" \
  --auth-mode offline \
  --uuid 13371337-1337-1337-1337-133713371337 \
  --name "$USER"

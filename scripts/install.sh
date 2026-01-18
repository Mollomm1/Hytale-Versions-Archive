#!/bin/bash
set -e

VERSION="${1:-4}"
TYPE="${2:-release}" # release or pre-release

echo "--- STARTING BUILD ---"
echo "Version: $VERSION"
echo "Type: $TYPE"

# --- Setup Tools (Butler) ---
echo "Setting up Butler..."
rm -rf tools
mkdir -p tools/butler
cd tools/butler
wget -q "https://broth.itch.zone/butler/linux-amd64/LATEST/archive/default" -O butler.zip
unzip -q butler.zip
chmod +x butler
BUTLER="$PWD/butler"
cd ../..

# Function to build a specific platform
build_platform() {
    OS_NAME=$1      # linux or windows
    PATCH_OS=$2     # linux or windows (for URL)
    JRE_URL=$3
    SCRIPT_SRC=$4
    SCRIPT_DEST=$5
    
    echo "--- Building for $OS_NAME ---"
    BUILD_DIR="build_$OS_NAME"
    rm -rf "$BUILD_DIR" cache
    mkdir -p "$BUILD_DIR/game/data" "$BUILD_DIR/game/jre" "$BUILD_DIR/UserData" cache

    # 1. Download Game Content
    # Note the usage of $TYPE here
    PATCH_URL="https://game-patches.hytale.com/patches/$PATCH_OS/amd64/$TYPE/0/$VERSION.pwr"
    echo "Downloading Patch: $PATCH_URL"
    
    # We use wget. If fails, script exits due to set -e
    wget -q "$PATCH_URL" -O cache/0.pwr

    echo "Applying Patch..."
    "$BUTLER" apply cache/0.pwr --staging-dir cache "$BUILD_DIR/game/data"

    # 2. Download and Extract JRE
    echo "Downloading JRE..."
    if [[ "$OS_NAME" == "linux" ]]; then
        wget -q "$JRE_URL" -O cache/jre.tar.gz
        tar -xzf cache/jre.tar.gz -C "$BUILD_DIR/game/jre/" --wildcards '*jdk*-jre/*' --strip-components=1
    else
        # Windows JRE is a ZIP
        wget -q "$JRE_URL" -O cache/jre.zip
        unzip -q cache/jre.zip -d cache/jre_temp
        # Move the inner folder content to game/jre
        mv cache/jre_temp/*jdk*-jre/* "$BUILD_DIR/game/jre/"
    fi

    # 3. Add Startup Script
    echo "Adding Start Script..."
    cp "scripts/$SCRIPT_SRC" "$BUILD_DIR/$SCRIPT_DEST"
    chmod +x "$BUILD_DIR/$SCRIPT_DEST"
}

# --- BUILD LINUX ---
build_platform \
    "linux" \
    "linux" \
    "https://launcher.hytale.com/redist/jre/linux/amd64/jre-25.0.1_8.tar.gz" \
    "start.sh" \
    "start.sh"

# --- BUILD WINDOWS ---
build_platform \
    "windows" \
    "windows" \
    "https://launcher.hytale.com/redist/jre/windows/amd64/jre-25.0.1_8.zip" \
    "start.bat" \
    "start.bat"

# Cleanup
rm -rf tools cache
echo "Build Complete."
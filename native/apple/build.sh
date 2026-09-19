#!/usr/bin/env bash
set -euo pipefail
APP_SOURCE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$APP_SOURCE/../.." && pwd)"
PLATFORM="${1:-macos}"
MODEL_FILE="${2:-}"
BUILD_ROOT="$REPO_ROOT/logs/mimir-apple/$PLATFORM"
OPTIONS=(-G Xcode)
case "$PLATFORM" in
    macos) OPTIONS+=(-DCMAKE_OSX_DEPLOYMENT_TARGET=14.0) ;;
    ios) OPTIONS+=(-DCMAKE_SYSTEM_NAME=iOS -DCMAKE_OSX_SYSROOT=iphoneos -DCMAKE_OSX_ARCHITECTURES=arm64 -DCMAKE_OSX_DEPLOYMENT_TARGET=17.0) ;;
    simulator) OPTIONS+=(-DCMAKE_SYSTEM_NAME=iOS -DCMAKE_OSX_SYSROOT=iphonesimulator -DCMAKE_OSX_ARCHITECTURES="$(uname -m)" -DCMAKE_OSX_DEPLOYMENT_TARGET=17.0) ;;
    *) echo 'Usage: build.sh [macos|ios|simulator] [path/to/mimir.gguf]' >&2; exit 2 ;;
esac
if [[ -n "$MODEL_FILE" ]]; then
    MODEL_FILE="$(cd "$(dirname "$MODEL_FILE")" && pwd)/$(basename "$MODEL_FILE")"
fi
cmake -S "$APP_SOURCE" -B "$BUILD_ROOT" "${OPTIONS[@]}" -DMIMIR_MODEL_FILE="$MODEL_FILE"
if [[ "$PLATFORM" == macos ]]; then
    cmake --build "$BUILD_ROOT" --target MimirChat mimir-bridge-tests --config Release -j "${MIMIR_BUILD_JOBS:-6}"
else
    cmake --build "$BUILD_ROOT" --target MimirChat --config Release -j "${MIMIR_BUILD_JOBS:-6}" -- CODE_SIGNING_ALLOWED=NO
fi
echo "Built in $BUILD_ROOT/Release*. For iPhone/iPad installation, open $BUILD_ROOT/MimirApple.xcodeproj and select your signing team."

#!/usr/bin/env bash
# Package an existing Apple Silicon build. Developer ID/notarization are separate.
set -euo pipefail
TOOLS_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$TOOLS_DIR/../../.." && pwd)"
APP="${1:-$REPO_ROOT/logs/mimir-apple/macos/Release/MimirChat.app}"
OUTPUT_DIR="${2:-$REPO_ROOT/logs/mimir-apple/distribution}"
APP="$(cd "$(dirname "$APP")" && pwd)/$(basename "$APP")"
PLIST="$APP/Contents/Info.plist"
VERSION=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$PLIST")
EXECUTABLE=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "$PLIST")
MINIMUM_OS=$(/usr/libexec/PlistBuddy -c 'Print :LSMinimumSystemVersion' "$PLIST")
ARCHS=$(lipo -archs "$APP/Contents/MacOS/$EXECUTABLE")
[[ "$ARCHS" == arm64 ]] || { echo "Expected an Apple Silicon arm64 build, got: $ARCHS" >&2; exit 1; }
codesign --verify --deep --strict "$APP"
MODEL="$APP/Contents/Resources/Mimir.gguf"
[[ -f "$MODEL" ]] || { echo 'This package requires a bundled model.' >&2; exit 1; }
EXPECTED_MODEL_SHA=$(plutil -extract id raw -o - "$APP/Contents/Resources/Model.json")
MODEL_SHA=$(shasum -a 256 "$MODEL" | awk '{print $1}')
[[ "$MODEL_SHA" == "$EXPECTED_MODEL_SHA" ]] || { echo 'Bundled model does not match Model.json.' >&2; exit 1; }
mkdir -p "$OUTPUT_DIR"
OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"
DMG="$OUTPUT_DIR/DFM-Mimir-$VERSION-arm64-preview.dmg"
[[ ! -e "$DMG" ]] || { echo "Output already exists: $DMG (choose another output directory)" >&2; exit 1; }
STAGING=$(mktemp -d "$OUTPUT_DIR/.dmg-stage.XXXXXX")
MOUNT=$(mktemp -d "$OUTPUT_DIR/.dmg-mount.XXXXXX")
MOUNTED=false
cleanup() {
    if $MOUNTED; then hdiutil detach "$MOUNT" >/dev/null || return; fi
    rm -rf "$STAGING"
    rmdir "$MOUNT"
}
trap cleanup EXIT
ditto "$APP" "$STAGING/DFM Mimir.app"
ln -s /Applications "$STAGING/Applications"
cat > "$STAGING/Read Me.txt" <<README
DFM Mimir $VERSION — development preview

Requires an Apple Silicon Mac (M1 or later) running macOS $MINIMUM_OS or later.

Installation
1. Drag DFM Mimir.app onto the Applications shortcut.
2. Open DFM Mimir from Applications, then eject this disk image.

The DFM-Mimir-v1 Q4_K_M model is included. No model download or internet
connection is needed for chat. Context and reply limits are configurable;
available memory determines the automatic defaults.

This preview has no Apple Developer ID signature or notarization. A downloaded
copy may be blocked by Gatekeeper. If you trust its source, use the per-app
Open Anyway option in System Settings > Privacy & Security after trying to open
it. There is no need to disable Gatekeeper globally.

Chats, settings and imported models live in your account's Application Support
folder. Replacing the app does not remove them. The model can make mistakes;
check important information. It was trained with a 4096-token context.

Model and inference-engine licenses are included inside the app's Resources
folder (DFM-Mimir-LICENSE.txt, Mimir-LICENSE.txt and llama-LICENSE.txt).
README
hdiutil create -volname 'DFM Mimir' -srcfolder "$STAGING" -format UDZO -fs HFS+ "$DMG"
hdiutil verify "$DMG"
hdiutil attach "$DMG" -readonly -nobrowse -mountpoint "$MOUNT"
MOUNTED=true
codesign --verify --deep --strict "$MOUNT/DFM Mimir.app"
[[ "$(readlink "$MOUNT/Applications")" == /Applications ]]
[[ -s "$MOUNT/Read Me.txt" ]]
PACKAGED_SHA=$(shasum -a 256 "$MOUNT/DFM Mimir.app/Contents/Resources/Mimir.gguf" | awk '{print $1}')
[[ "$PACKAGED_SHA" == "$MODEL_SHA" ]] || { echo 'Packaged model hash mismatch.' >&2; exit 1; }
hdiutil detach "$MOUNT"
MOUNTED=false
(cd "$OUTPUT_DIR" && shasum -a 256 "$(basename "$DMG")" > "$(basename "$DMG").sha256")
echo "Verified preview DMG: $DMG"

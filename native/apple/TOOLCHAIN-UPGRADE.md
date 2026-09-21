# Xcode 27 upgrade — 2026-09-20

Status: **installation awaiting local administrator authentication**. Xcode 16.3
(16E140) is still selected at `/Applications/Xcode.app/Contents/Developer`.
The host is now macOS 27.0 (26A428). Apple lists stable Xcode 27 with Swift 6.4
and macOS/iOS 27 SDKs; App Store lookup confirms version 27.0, released September
14. Paid developer enrollment/signing remains separate from this upgrade.

Sources: [Apple compatibility table](https://developer.apple.com/xcode/system-requirements),
[Xcode App Store listing](https://apps.apple.com/app/xcode/id497799835).

Homebrew `mas` 7.0.0 was installed to drive the App Store update. Its update command
requires root; `sudo -n true` confirms this session cannot authenticate silently.
The owner should run in their terminal (never share passwords in chat):

```bash
sudo /opt/homebrew/bin/mas update 497799835
sudo xcode-select --switch /Applications/Xcode.app/Contents/Developer
sudo xcodebuild -runFirstLaunch
```

If Apple requests account authentication or license acceptance, complete those
locally. Then check:

```bash
xcodebuild -version
xcodebuild -showsdks
xcodebuild -checkFirstLaunchStatus
xcrun swiftc --version
xcrun --sdk macosx --find metal
```

Install any required platform/Metal components using Xcode's Components settings.
An iOS 27 Simulator runtime is needed for simulator execution, separately from
compiling against the iOS Simulator SDK.

## Qualification after installation

Use fresh build directories so compiler/SDK checks are regenerated; existing
Xcode 16.3 app builds and the preview DMG remain usable artifacts.

```bash
native/apple/Tools/test-swift.sh
for platform in macos ios simulator; do
  MIMIR_APPLE_BUILD_ROOT="$PWD/logs/mimir-apple/xcode27/$platform" \
    native/apple/build.sh "$platform" "$PWD/logs/mimir-review/mimir-q4_k_m.gguf"
done
logs/mimir-apple/xcode27/macos/Release/mimir-bridge-tests \
  "$PWD/logs/mimir-review/mimir-q4_k_m.gguf"
for scenario in exit-idle exit-loading exit-active; do
  logs/mimir-apple/xcode27/macos/Release/mimir-bridge-tests \
    "$PWD/logs/mimir-review/mimir-q4_k_m.gguf" "$scenario"
done
```

Check live Mac launch, scrolling, Dock icon and Cmd-Q. Check simulator launch with
a supported runtime. Keep macOS 14/iOS 17 deployment minima unless an observed
SDK/compiler incompatibility requires a separately justified change. Package any
new preview DMG in a separate output directory. Record actual versions/results
before claiming the upgrade qualified or changing CI requirements.

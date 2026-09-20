# DFM Mimir — Flutter

A separate Flutter client sharing Mimir's C++ chat and compaction implementation
with the SwiftUI app. Initial packaged targets are **Apple Silicon macOS 14+** and
**arm64 iOS 17+ simulator**, with an Android ARM64 development target below. Bundle ID `dk.sdu.mimirFlutter` and its archive are
separate from SwiftUI. This does not migrate or overwrite the Apple app's chats.

The interface includes branded conversations/sidebar, streaming replies and stop,
GGUF/profile import, model identity, configurable context/reply budgets, memory-based
defaults, exact template context counts, streamed inline compaction summaries with
independent visibility/enable controls, full transcript persistence, sharing,
deleting, mobile keyboard dismissal and desktop/mobile Enter conventions.

The bundled profile allows 1,024–32,768 context tokens and identifies the model's
4,096-token training context. Defaults reserve at least 512 reply tokens. Import a
validated profile to change future models' limits and memory estimates. Model
weights, frameworks, SDK, Pods and generated build products are not in Git.

## Build on Apple Silicon

Prerequisites used: Flutter **3.47.5** / Dart **3.13.4**, Xcode **16.3**, CMake,
CocoaPods **1.17.0**, iOS 18.4 simulator runtime. No developer account is required
for these targets. Put Flutter on PATH; the local installation is
`logs/toolchains/flutter/bin/flutter` from the repository root.

```sh
# From repository root, using your locally available Q4_K_M GGUF:
git submodule update --init --recursive
python3 native/flutter/tool/build_native.py --model /absolute/path/mimir-q4_k_m.gguf
cd native/flutter
flutter pub get
flutter analyze
flutter test
flutter build macos --release
flutter build ios --simulator --debug
```

The native script builds self-contained frameworks: Metal/Accelerate on Mac and
CPU on the simulator. It copies an XCFramework inside each local CocoaPod
(CocoaPods does not traverse a directory symlink here), and links the selected
GGUF into Flutter assets. Generated previous frameworks are retained under logs
when rebuilding. Xcode targets intentionally use arm64; Intel Mac and physical
iOS device slices have not been built. CocoaPods fallback currently produces a
Flutter warning that this local FFI plugin has no Swift Package Manager manifest.

Mac product: `build/macos/Build/Products/Release/DFM Mimir Flutter.app`.
iOS product: `build/ios/iphonesimulator/Runner.app`. Install using
`xcrun simctl install booted build/ios/iphonesimulator/Runner.app`, then launch
`xcrun simctl launch booted dk.sdu.mimirFlutter` (or `flutter run -d DEVICE_ID`).
Debug simulator execution is not a physical-iPhone performance measurement.

## Architecture and verification

- `lib/engine.dart`: serialized Dart FFI commands and polled JSON events; shutdown
  joins the native worker in an isolate.
- `../runtime`: asynchronous C ABI and native worker; model loading, template
  tokenization, generation and compaction run away from the UI thread.
- `../mimir/include/mimir/compaction.h`: one compaction algorithm shared by Flutter
  and SwiftUI; summaries remain metadata, not synthetic saved chat messages.
- `lib/store.dart`: durable state, validated archives, atomic writes, completed-turn
  commits, cancelled-turn rollback and independent summary visibility.
- `assets/profile.json`: versioned model policy; `assets/licenses` and Settings /
  Licenses retain model/runtime attributions.

```sh
# From repository root after native build:
python3 native/runtime/tests/smoke.py \
  logs/mimir-flutter-native/macos/Release/MimirRuntime.framework/MimirRuntime \
  /absolute/path/mimir-q4_k_m.gguf native/flutter/assets/profile.json
```

See [VALIDATION.md](VALIDATION.md) for observed results and limitations, and
[backend qualification](../mimir/BACKENDS.md) for the acceleration matrix.

## Android development emulator

The Android runner builds the shared runtime through Gradle/CMake for
**arm64-v8a**, currently with CPU inference. Prerequisites: JDK 21, Android SDK
36, build-tools 36.0.0, NDK 28.2.13676358 and SDK CMake 3.22.1. The bundled GGUF
must already be linked at `assets/model.gguf` (the Apple build script above sets
this up, or create that symlink directly without building Apple frameworks).

```sh
export ANDROID_HOME="$HOME/Library/Android/sdk"
export JAVA_HOME=/absolute/path/to/jdk/Contents/Home
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"

sdkmanager 'platform-tools' 'emulator' 'platforms;android-36' \
  'build-tools;36.0.0' 'ndk;28.2.13676358' 'cmake;3.22.1' \
  'system-images;android-36;google_apis;arm64-v8a'
avdmanager create avd --name DFM_Mimir_API_36 \
  --package 'system-images;android-36;google_apis;arm64-v8a' --device pixel_7
# Configure 8 GB RAM and a 16 GB data partition in this AVD's config.ini.
"$ANDROID_HOME/emulator/emulator" -avd DFM_Mimir_API_36 -no-snapshot -gpu auto

# In another terminal, from native/flutter:
flutter build apk --debug --target-platform android-arm64
adb install -r build/app/outputs/flutter-apk/app-debug.apk
adb shell am start -n dk.sdu.mimir_flutter/.MainActivity
# Optional real-model test; uses an isolated conversation archive:
flutter test integration_test/android_smoke_test.dart -d emulator-5554
```

The APK keeps GGUF assets uncompressed. On first launch (and after reinstall),
a background Kotlin worker streams the model into app-private no-backup storage,
then atomically replaces the completed file. Subsequent launches reuse it. Allow
space for both the APK and extracted model, plus a temporary model copy during
updates. The shared runtime uses `/proc/meminfo` to size automatic context on
Android/Linux; available memory is a hint, not protection from Android's low-memory
killer. The emulator's RAM and host CPU do not represent a physical phone.

This is a development APK signed with the debug key, not a Play Store release.
GPU inference, physical devices, low-memory behavior and Android distribution
remain unqualified. Emulator graphics acceleration does not imply model GPU
offload. After integration tests, reinstall the regular APK to restore the normal
app entry point.

## Next platforms

Linux and Windows runner scaffolds are present. They are **not yet
packaged or qualified products**: native library/asset deployment still needs
integration. The C ABI and shared Dart UI are designed
to carry over, while ggml backend selection follows available devices. Linux and
Windows minimum requirements must be set after actual builds and driver tests.
Physical iOS signing, distribution, App Store/TestFlight, notarization and release
credentials remain deferred as requested.

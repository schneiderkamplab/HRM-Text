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

Prerequisites used: Flutter **3.47.5** / Dart **3.13.4**, Xcode **27.0**, CMake,
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

The native script builds self-contained frameworks: Metal/Accelerate on Mac,
Metal on physical iOS, and CPU on the simulator. It copies an XCFramework inside each local CocoaPod
(CocoaPods does not traverse a directory symlink here), and links the selected
GGUF into Flutter assets. Generated previous frameworks are retained under logs
when rebuilding. Xcode targets intentionally use arm64. Intel Mac remains unqualified; physical
iOS builds need signing/provisioning before installation. CocoaPods fallback currently produces a
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
**arm64-v8a**, with CPU and Vulkan inference compiled in. Prerequisites: JDK 21, Android SDK
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

# Host build dependencies (Mac/Homebrew): shaderc, vulkan-headers, spirv-headers.
# These supply a native glslc executable and header-only SDK dependencies.
export MIMIR_GLSLC="$(brew --prefix shaderc)/bin/glslc"
export MIMIR_VULKAN_HEADERS="$(brew --prefix vulkan-headers)/include"
export MIMIR_SPIRV_HEADERS_DIR="$(brew --prefix spirv-headers)/share/cmake/SPIRV-Headers"
export PATH="$ANDROID_HOME/cmake/3.22.1/bin:$PATH" # Ninja for host shader generation

# In another terminal with these exports, from native/flutter:
flutter build apk --debug --target-platform android-arm64
# Or use --release for the optimized, development-signed APK.
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
Vulkan requires a supported Vulkan 1.2+ device; physical GPU inference, low-memory
behavior and Android distribution remain unqualified. The build links the Android
system Vulkan loader and includes the CPU backend; registration failures are
handled by llama.cpp, while recoverable model/context failures use our fallback policy. Emulator graphics acceleration does not imply model GPU
offload. After integration tests, reinstall the regular APK to restore the normal
app entry point.

## Linux and Windows development packages

Build on the matching host with Flutter 3.47.5, Python 3.12+, CMake and the
[Flutter desktop prerequisites](https://docs.flutter.dev/platform-integration).
Linux also needs GTK3 development libraries, clang, Ninja and pkg-config;
Windows needs Visual Studio's Desktop development with C++ workload.

```sh
python native/flutter/tool/package_desktop.py --model /absolute/path/model.gguf
# Or a smaller package which asks the user to import a model:
python native/flutter/tool/package_desktop.py --without-model
# Optional GPU builds require the matching CUDA/Vulkan SDK at build time:
python native/flutter/tool/package_desktop.py --without-model --backends cpu,cuda,vulkan
```

Outputs go to `logs/packages`: Linux tar.gz or Windows ZIP, SHA-256 sidecar,
and a per-file/source/model manifest inside the archive. These are unsigned
development bundles. Extract the whole folder and run `mimir_flutter` or
`mimir_flutter.exe`. CPU is always included; optional backend libraries are
loaded from the runtime's directory, not the current working directory. CPU
variants are selected at runtime on x64. Windows bundles include the release CRT.
CUDA bundles include CUDA user-space runtime libraries; the system GPU driver
and Vulkan loader are OS/driver prerequisites. License redistribution checks
and real hardware qualification remain required before public releases.

The package command probes the C ABI from another working directory and checks
that removing CPU backend files produces a readable error in a fresh process.
CI builds and uploads CPU/import-only packages on Linux and Windows. Artifact
creation is separate from real-model/hardware qualification. See
[PACKAGING-PLAN.md](PACKAGING-PLAN.md) for the remaining release stages and
[DESKTOP-TESTING.md](DESKTOP-TESTING.md) for package/hardware acceptance.

Automatic loading ranks Metal, CUDA and Vulkan before other registered
accelerators, with CPU last. Recoverable model/context initialization failures
advance to the next device; implicit GPU flash attention is retried disabled.
Explicit device selection stays strict. Settings shows the actual backend and
fallback reasons. Automatic memory limits are recalculated for each candidate;
explicit context limits are retained. Invalid metadata/templates/profile limits
fail before retries. CPU cannot rescue a model too large for host memory.
Mid-generation recovery, reduced layer offload and crash-relaunch recovery are
not implemented yet; they remain in the plan.

## Experimental MixedLM

**Model and settings → MixedLM mode** enables approximate reuse of older prompt
representations. It is off by default; switching reloads the model context.
See [design, test evidence and observed quality limits](../mimir/MIXEDLM.md).

### Include weights in a previously tested desktop package

The recommended ready-to-use downloads include the tested Mimir Q4_K_M weights.
They are available in the [bundled-weight desktop preview draft](https://github.com/schneiderkamplab/HRM-Text/releases)
(requires a GitHub account with access to repository drafts).
CI's smaller import-only bundles can be assembled on any host without recompiling
their native binaries:

```sh
python native/flutter/tool/bundle_model.py dfm-mimir-0.1.0-linux-x64.tar.gz \
  --model /absolute/path/mimir-q4_k_m.gguf --output logs/packages/with-model/linux
python native/flutter/tool/bundle_model.py dfm-mimir-0.1.0-windows-x64.zip \
  --model /absolute/path/mimir-q4_k_m.gguf --output logs/packages/with-model/windows
```

Keep the source archive's `.sha256` sidecar next to it. The tool verifies the
archive and every manifest entry before replacing the declared Flutter model
asset. The new manifest retains the binary source revisions, records the original
archive checksum and the bundled model checksum, and updates all file hashes.
First launch finds the weights locally; no import or model download is needed.

### macOS DMG with weights

After `flutter build macos --release`, package the Apple Silicon app with:

```sh
python native/flutter/tool/package_macos.py \
  --model-sha256 3cf8906f4dd1349c965e7dd873e3995419d34bf846a657840a393c32c89849a5
```

The DMG contains `DFM Mimir Flutter.app`, an Applications shortcut, a readme and
source/model metadata. The tool verifies the app signature and model hash before
packaging, verifies and mounts the image, then repeats signature/model checks.
It preserves the Flutter app identity and does not replace the separate SwiftUI
app. The preview requires Apple Silicon and macOS 14 or later; it is not Developer
ID signed or notarized. Its checksum sidecar accompanies the draft-release asset.

Distribution filenames follow `dfm-mimir-VERSION-PLATFORM-ARCH.EXT`, for example
`dfm-mimir-0.1.0-android-arm64.apk`, `dfm-mimir-0.1.0-macos-arm64.dmg`,
`dfm-mimir-0.1.0-linux-x64.tar.gz` and `dfm-mimir-0.1.0-windows-x64.zip`.
Checksum sidecars append `.sha256`. Backend and development-signing details belong
in release notes rather than filenames.

## Local API and headless use

Desktop apps can expose a local OpenAI-compatible text chat API, off by default.
Packages also include `dfm-mimir-server` for headless operation without a display.
See [API.md](API.md) for Settings, commands, supported fields, limits and tests.

# DFM Mimir

A separate Flutter client sharing Mimir's C++ chat and compaction implementation
with the SwiftUI app. Initial packaged targets are **Apple Silicon macOS 14+** and
**arm64 iOS 17+ simulator**, with an Android ARM64 development target below. Bundle ID `dk.sdu.mimir` and its archive are
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

Android always opens with the model unloaded, so settings remain accessible before
driver initialization or model allocation. Select CPU and start with 1,024 context
tokens / 512 reply tokens, then press **Load model**. Vulkan is experimental and
opt-in. CPU sessions skip the inference runtime's Vulkan registration entirely.
After a freeze, force-stop the app in Android settings and reopen it to change the
backend or limits. Changing backend after initialization also requires force-stop
and reopen, because the native backend registry is process-global. Explicit saved
limits are retained; automatic memory-based defaults are disabled on Android.

## Oversized prompts and context compaction

**Automatically compact context** handles both old history and a new prompt that
cannot fit with the reply budget. It packs complete turns into bounded summary
requests, splitting oversized turns or prompts at UTF-8 boundaries when needed.
Every inference request uses the model's chat template and tokenizer for sizing.
Regular compaction starts above 90% occupancy (including the reply reservation)
and aims for at most 50%, retaining recent turns verbatim when that target permits.
If fixed system/prompt/reply costs make 50% unattainable, it summarizes all eligible
history and accepts the result only if the request fits.

The original prompt stays in the transcript. Its shortened form is saved separately
and reused for follow-up context; **Show compaction summary in chat** reveals it
under the original message. Summaries stream while Mimir is compacting. Cancellation
or failure keeps the original draft and previously committed history. Turning
compaction off uses the original text again and can therefore exceed context.

Compaction is lossy and can require several model passes. Prompt reduction retains
the original opening and ending when they fit, but cannot guarantee preservation
of every detail. System instructions are never summarized; if they and the reply
reservation leave insufficient space, the app reports an error. The stateless
OpenAI-compatible API continues to reject oversized requests; it does not silently
rewrite callers' messages.

## Build on Apple Silicon

Prerequisites used: Flutter **3.47.5** / Dart **3.13.4**, Xcode **27.0**, CMake,
CocoaPods **1.17.0**, iOS 18.4 simulator runtime. No developer account is required
for these targets. Put Flutter on PATH; the local installation is
`logs/toolchains/flutter/bin/flutter` from the repository root.

```sh
# From repository root, using your locally available Q4_K_M GGUF:
git submodule update --init --recursive
python3 native/app/tool/build_native.py --model /absolute/path/mimir-q4_k_m.gguf
cd native/app
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

Mac product: `build/macos/Build/Products/Release/DFM Mimir.app`.
iOS product: `build/ios/iphonesimulator/Runner.app`. Install using
`xcrun simctl install booted build/ios/iphonesimulator/Runner.app`, then launch
`xcrun simctl launch booted dk.sdu.mimir` (or `flutter run -d DEVICE_ID`).
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
  logs/mimir-app-native/macos/Release/MimirRuntime.framework/MimirRuntime \
  /absolute/path/mimir-q4_k_m.gguf native/app/assets/profile.json
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

# In another terminal with these exports, from native/app:
flutter build apk --debug --target-platform android-arm64
# Or use --release for the optimized, development-signed APK.
adb install -r build/app/outputs/flutter-apk/app-debug.apk
adb shell am start -n dk.sdu.mimir/.MainActivity
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
Linux also needs GTK3 development libraries, clang, Ninja, pkg-config and
`libsecret-1-dev`; installed apps need `libsecret-1-0` and a Secret Service to
remember search credentials (session-only keys work without a Secret Service);
Windows needs Visual Studio's Desktop development with C++ workload.

```sh
python native/app/tool/package_desktop.py --model /absolute/path/model.gguf
# Or a smaller package which asks the user to import a model:
python native/app/tool/package_desktop.py --without-model
# Optional GPU builds require the matching CUDA/Vulkan SDK at build time:
python native/app/tool/package_desktop.py --without-model --backends cpu,cuda,vulkan
```

Outputs go to `logs/packages`: Linux tar.gz or Windows ZIP, SHA-256 sidecar,
and a per-file/source/model manifest inside the archive. These are unsigned
development bundles. Extract the whole folder and run `dfm-mimir` or
`dfm-mimir.exe`. CPU is always included; optional backend libraries are
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
representations. It is on by default for new settings; an existing saved choice
is preserved. Switching reloads the model context.
See [design, test evidence and observed quality limits](../mimir/MIXEDLM.md).

### Include weights in a previously tested desktop package

The recommended ready-to-use downloads include the tested Mimir Q4_K_M weights.
Version 0.1.2 bundles the corrected official Q4_K_M from
[`danish-foundation-models/DFM-Mimir-GGUF`](https://huggingface.co/danish-foundation-models/DFM-Mimir-GGUF).
Public downloads: [DFM Mimir 0.1.2](https://github.com/schneiderkamplab/HRM-Text/releases/tag/dfm-mimir-v0.1.2).
CI's smaller import-only bundles can be assembled on any host without recompiling
their native binaries:

```sh
python native/app/tool/bundle_model.py dfm-mimir-0.1.0-linux-x64.tar.gz \
  --model /absolute/path/mimir-q4_k_m.gguf --output logs/packages/with-model/linux
python native/app/tool/bundle_model.py dfm-mimir-0.1.0-windows-x64.zip \
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
python native/app/tool/package_macos.py \
  --model-sha256 3cf8906f4dd1349c965e7dd873e3995419d34bf846a657840a393c32c89849a5
```

The DMG contains `DFM Mimir.app`, an Applications shortcut, a readme and
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

## Model library

See [Models and downloads](MODELS.md) for the bundled HF source, available
precisions, optional downloads, selector behavior, and adding future versions.

## Reply sampling

Model and settings includes temperature (0–2, default 0) and repetition penalty
(1–2, default 1.1). Temperature 0 uses greedy decoding; higher values sample with
more variation. A repetition penalty above 1 discourages tokens appearing in the
last 64 generated tokens of the current reply. Penalty history resets each reply
and does not penalize the prompt. Settings persist and apply to the next reply
without reloading the model; they cannot change during generation.
Compaction retains its deterministic defaults. These UI settings do not override
sampling parameters supplied by OpenAI-compatible API clients.

## Markdown replies

Assistant replies (including streaming text) and visible compaction summaries
render basic Markdown: headings, emphasis, lists, blockquotes, inline code and
fenced code blocks. Text remains selectable. User prompts remain literal, and
stored/shared transcripts retain their original Markdown source.

Rendering is offline. Images become text placeholders rather than fetching
remote resources or reading local files. Tapping a link shows its address and a
Copy link action; it does not open a browser or make a network request.

The former saved 1.0 default upgrades to 1.1 once. Other saved values are
preserved; explicitly selecting 1.0 afterwards still disables the penalty.

## Optional web search (unreleased 0.1.4)

Enable **Allow online search** and enter a Mimir search key in settings. The
model can call `web_search(query)` during a reply, then use the results to answer
with sources. Search is available through the model during chat. Only queries go to the
Mimir service and Jina AI; model-generated queries may include chat details.
At most two searches run per answer, and Stop cancels searching too.
Search stays off by default. Keys can be remembered in secure storage or used
only for the current session; no keys are bundled or included in feedback.
See the [search runbook](../../services/feedback/SEARCH.md) for service setup.

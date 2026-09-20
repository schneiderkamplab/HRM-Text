# Flutter MVP validation — 2026-09-20

Scope: Apple Silicon Mac, arm64 iOS simulator and Android ARM64 emulator with Q4_K_M DFM-Mimir-v1,
using the model's own chat template. No network inference service. The native
selection matrix is in [BACKENDS.md](../mimir/BACKENDS.md).

Environment: M2 Max / 96 GiB, macOS 27.0 (26A428), Xcode 16.3,
Flutter 3.47.5 / Dart 3.13.4 / CocoaPods 1.17.0, iOS 18.4 iPhone 16 Plus simulator.
GGUF SHA256: `3cf8906f4dd1349c965e7dd873e3995419d34bf846a657840a393c32c89849a5`.

## Android emulator — 2026-09-20

Installed Android command-line tools 19.0, emulator 37.1.11, API 36 Google APIs
ARM64 image, platform/build tools 36, NDK 28.2.13676358, CMake 3.22.1 and Temurin
21.0.12.1. Plugin dependencies also installed SDK platform 35. AVD
`DFM_Mimir_API_36` uses Pixel 7 configuration, 8 GB RAM and a 16 GB data partition.
`emulator -accel-check` passed with Hypervisor.Framework on macOS 27.0.

| Check | Result |
|---|---|
| Dart static analysis | No issues |
| Debug APK + shared C++ engine | Built successfully, ARM64 only; CPU inference |
| APK contents | `libMimirRuntime.so` present; bundled 1,167,417,504-byte GGUF stored uncompressed |
| Real-model integration test | Passed in 23 seconds after build/install |
| Test coverage | Native loading, minimum context, UI Send, Mimir-templated Danish arithmetic prompt, completed reply containing `4`, context count and saved archive |
| Normal app | Reinstalled regular APK after test and launched successfully |

The test in `integration_test/android_smoke_test.dart` uses an isolated archive;
it does not change the user's conversations. It is a functional smoke test, not
an accuracy or throughput benchmark. Host Computer Use did not recognize the
standalone emulator executable, so no separate manual GUI audit is claimed.
Physical devices, Android GPU inference, low-memory behavior, background/resume,
and the full import/share/compaction UI matrix remain unqualified on Android.

The first build inadvertently included Flutter's default 32-bit ABI and failed
in ARM intrinsics; explicitly clearing those default ABI filters fixed packaging.
The successful APK contains only `arm64-v8a`. Xcode license acceptance remained
pending, so Apple rebuilds were not attempted; Android tooling ran using the
CommandLineTools developer directory and the separately installed JDK/SDK.

Local evidence: `logs/android-build-retry.log`, `logs/android-integration-test.log`,
`logs/android-flutter-analyze.log`, `logs/mimir-android-debug.apk`.

An additional iOS-themed touch-drag widget test passed during the preceding
scrolling investigation. The user subsequently confirmed simulator swiping works;
no production scrolling change was needed.

## Automated evidence

| Check | Result |
| --- | --- |
| Native text suite | 73 checks each on CPU, Metal, Accelerate, Vulkan/MoltenVK |
| Native framework builds | Mac arm64 + iOS simulator arm64; frameworks contain static ggml/llama dependencies |
| Real C ABI smoke | Device enumeration, model load, templated generation, stream/final text agreement, cancellation and recovery, multi-turn streamed compaction, shutdown during active generation |
| Existing SwiftUI bridge regression | Metal load, generation, main-thread callbacks, transcript restore, cancellation/recovery and compaction tests passed after shared-header extraction |
| Dart store/profile tests | Profile bounds and future limits; summary stream/commit/archive placement; cancelled summary rollback; first-send draft preservation |
| Widget test | Branding/sidebar, editable composer, Shift-Enter does not send, Enter sends, immediate new-conversation identity |
| Static analysis | `flutter analyze`: no issues |
| App builds | Mac release and iOS simulator debug; native runtime embedded in both |

The first-send test was added after live testing exposed draft loss when starting
from an empty archive. The prompt is now captured before creating its conversation.
The original widget test also exposed a sidebar overflow, which was fixed.

Local logs (not committed): `logs/flutter-{tests-final,analyze-final,native-smoke,
shared-apple-test,macos-build,ios-build}.log` and
`logs/flutter-native-package.log`. Use [README.md](README.md) to reproduce.

## Live checks

Computer Use observed the branded Mac UI, accepted typed text and Return, showed
native Metal generation returning `4` to a Danish arithmetic prompt, and exercised Cmd-Q. The process exited after native
Metal resource destruction, with no new app crash report.

On the iOS simulator, the app loaded the bundled model on CPU with an automatically
selected 4,096-token context and 1,024-token reply budget. A real Danish arithmetic
prompt produced `2 + 2 er 4.` Return added a newline without sending; the send
button submitted the prompt. Toggling the simulator software keyboard exposed
Done, which dismissed it. Model/profile/context controls, training-context notice,
licenses and compaction visibility were visible. The summary visibility switch
was exercised. The conversation survived reinstalling/relaunching the simulator build. Simulator timing is not a physical-iPhone performance result.

Native compaction generation and stream ordering are tested with a real model;
placement, persistence and cancelled-preview rollback are tested in Dart. This is
not a claim that every long-history compaction gesture was manually repeated in
both packaged UIs.

## Remaining qualification and release work

- **Accessibility diagnostic resolved:** a development-only forced semantics
  handle produced AX-tree errors and one crash during an active-generation quit.
  Removing that handle and letting Flutter activate semantics normally restored
  the live Mac tree. The temporary tooltip restriction was also removed; the
  shipped source uses normal tooltips and an unmodified Flutter SDK. Earlier
  upstream tooltip/OverlayPortal issues were diagnostic leads, not a confirmed
  cause. Final live tree and exit checks are recorded below. A full VoiceOver /
  TalkBack acceptance audit remains outstanding.
- The local FFI plugin uses CocoaPods; Flutter warns that a Swift Package Manager
  manifest will be needed in a future release. Current builds work with Xcode 16.3.
- GGUF/profile import, share-sheet delivery and corrupt-archive UI recovery need
  broader manual acceptance checks. Atomic persistence and state behavior are
  covered at the bounded test level; no existing SwiftUI chats are migrated.
- Physical iPhone/iPad memory, performance, thermals, signing and distribution are
  deferred. Mac builds currently target arm64 only.
- Android/Linux/Windows runners are scaffolds, pending native packaging, assets,
  memory probes and hardware testing. No tested-product claim for those targets.
- No controlled Flutter-versus-SwiftUI speed comparison or newly enabled backend
  BF16/Q8 numerical qualification was performed in this pass.

## Final Mac lifecycle rerun

With normal tooltips and no forced semantics handle, Computer Use read the full
live chat tree, observed `DFM Mimir is thinking…` after a long-story submission,
and sent Cmd-Q while the request was active. The directly launched process
returned **exit code 0**. `logs/flutter-mac-qualified.log` shows Metal resource
release and contains no `AXTree`/`ERROR` entries. No new Flutter crash report was
created. The earlier diagnostic crash report is retained locally for traceability.
The cancelled long-story turn was absent from the saved completed transcript.

Staged OKF concepts validate with zero errors. Full-worktree validation encounters
two unrelated errors in the untracked benchmark-charts page; those files were
preserved and excluded from this change.

## Startup new-chat correction

The original shared busy flag disabled new-chat creation throughout model loading.
Creation now waits for archive restoration only; the toolbar and sidebar actions
are enabled during model loading, and sending remains disabled. A regression test
checks both controls, immediate selection, drafting during loading and the active
generation restriction.

## MixedLM and Xcode 27 qualification — 2026-09-20

Xcode 27.0 (27A266a) now passes first-launch checks; the earlier license blocker
is resolved. The native macOS Metal/BLAS and iOS simulator CPU frameworks both
build, as do the Flutter macOS release app and iOS simulator app. Six host
unit/widget tests pass. CocoaPods still warns about future Swift Package Manager
requirements; it does not block these builds.

The [MixedLM report](../mimir/MIXEDLM.md) covers eight native regression cases,
real Q4_K_M CPU exact/MixedLM and Metal MixedLM checks, invalidation behavior,
illustrative timings and a demonstrated response-quality regression. MixedLM is
experimental and off by default. These results do not qualify Linux/CUDA or
physical phones for the approximation.

The real-model integration flow passes on both the ARM64 Android API 36 emulator
and iPhone 16 Plus / iOS 18.4 simulator. It verifies default-off arithmetic,
toggling MixedLM on through Settings, a cold first request, reused-prefix tokens
on the next request, persisted settings, toggling off, and exact-mode arithmetic
again. Archives are isolated from the user's conversations. The Android rerun
needed an explicit composer tap after closing Settings to reconnect platform
text input; the earlier failure occurred before submitting a prompt. No app
input workaround was added.

Reproduce with `flutter test integration_test/android_smoke_test.dart -d DEVICE`;
despite its historical filename, the same test runs on either simulator. Logs:
`logs/mixedlm-android-test.log` and `logs/mixedlm-ios-test.log`.

## Portable desktop packaging and initialization fallback — 2026-09-20

This milestone adds Linux/Windows package builds and automatic recoverable
model/context initialization retries. It does not qualify every optional GPU
backend or implement recovery during generation. Explicit device choices remain
strict; Settings reports the selected device and reasons for fallback.

Local validation on Apple M2 Max (96 GB), macOS 27 / Xcode 27.0, using Flutter
3.47.5 and the Q4_K_M model with SHA-256
`3cf8906f4dd1349c965e7dd873e3995419d34bf846a657840a393c32c89849a5`:

| Check | Result | Local evidence |
| --- | --- | --- |
| Native regression suite, including injected backend failure/cleanup policy | 9/9 pass | `logs/packaging-ctest.log` |
| Flutter analyzer and unit/widget tests | clean; 7/7 pass | `logs/packaging-final-analyze.log`, `logs/packaging-final-flutter-tests.log` |
| Real-model static CPU C ABI smoke, compaction/cancellation and MixedLM | pass | `logs/packaging-final-cpu-smoke.log` |
| Dynamic CPU-only and Metal+CPU builds, real-model automatic selection | pass | `logs/packaging-dynamic-cpu.log`, `logs/packaging-dynamic-metal.log` |
| Relocated native-library probe and missing-CPU diagnostic | pass on Mac | `logs/packaging-probe-mac.log` |
| Mac/simulator/device XCFramework slices | build pass | `logs/packaging-apple-native-verified.log` |
| Mac release and unsigned physical iOS release app | build pass | `logs/packaging-macos-build.log`, `logs/packaging-ios-device.log` |
| Android ARM64 debug APK | build pass | `logs/packaging-android-build.log` |
| Mac real-model Flutter integration flow, including MixedLM toggles | pass | `logs/packaging-macos-integration.log` |

Physical iOS generation still requires a provisioned device. The Android build
above is CPU-only. Apple build success is not a new signing/distribution claim.
Every chat smoke/integration check uses the Mimir GGUF chat template.

### Hosted package evidence

The Linux and Windows CPU/import-only jobs at commit `6eb48b9` passed in
[Actions run 35499701323](https://github.com/schneiderkamplab/HRM-Text/actions/runs/35499701323).
They built on Ubuntu 22.04 x86-64 and Windows Server 2022 x64, passed the
shared backend-policy test, Flutter analyzer and seven host tests, and loaded
each packaged C ABI from an unrelated working directory. A fresh process with CPU modules removed reported the
intended missing-backend error. Downloaded archive checksums and every manifest
file hash verified locally: Linux has 52 files (25,627,038-byte tarball), Windows
has 51 files (18,857,190-byte ZIP). Windows includes the release VC runtime DLLs.
Both manifests pin llama.cpp to
`43139122aa30557a34b985979d10f13e9634a3cb` and record no bundled model.

Download the `mimir-Linux-cpu-import-only` and `mimir-Windows-cpu-import-only`
artifacts from that run. Local verified copies are in
`logs/desktop-packages/6eb48b9/{linux,windows}/`. They are unsigned development
packages. The full source revision is `6eb48b926e012f2650d0327bcdcce0455efb739d`.

The CI probes enumerate CPU devices; they do not generate with real weights or
exercise a desktop window. Complete the [desktop acceptance checks](DESKTOP-TESTING.md)
on clean Linux/Windows hosts with a Mimir GGUF, then qualify GPU packages on
actual CUDA/Vulkan hardware. Earlier native CUDA results do not automatically
qualify these new archives or MixedLM. Run the existing Linux release/sanitizer
handoff before final production packaging and review.

Packaging fixes found by hosted CI: resolve native sources relative to the Flutter
runner (Windows junctions do not reliably resolve with CMake REALPATH); track the
Windows runner manifest despite the repository-wide ignore; include Linux shared
library SONAME aliases; keep upstream native SDK installation out of the app
bundle. The last issue produced an unevaluated target-based Windows install path
and duplicate Linux backend/SDK files. Explicit build dependencies preserve every
bundled native library while Flutter owns their final installation.

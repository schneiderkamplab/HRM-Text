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

## Bundled-model desktop downloads — 2026-09-20

The tested `6eb48b9` CPU packages were assembled with the same Q4_K_M weights
used by the Mac smoke tests. The model SHA-256 is
`3cf8906f4dd1349c965e7dd873e3995419d34bf846a657840a393c32c89849a5`.
`tool/bundle_model.py` verifies the original archive and file manifest, embeds
weights at the existing Flutter asset path, then updates hashes and records the
original archive checksum. Binary source revisions remain unchanged.

| Package | Bytes | SHA-256 |
| --- | --- | --- |
| Linux x64 tar.gz | 1,129,386,077 | `e6fe3928e5b8e9ca9f4bc1ec5cf36573fc5aee2f97d53e4f7324b407923e69d5` |
| Windows x64 ZIP | 1,122,701,500 | `dc51577ad6f0a95612c229da9839e61c30ade2f9f7223e89eb86bad3b045b2d9` |

Every archive/file hash was checked after assembly, including the embedded model.
Comparison with the original manifests confirms that only the model asset and
README changed; Linux executable permissions remain intact. A corrupt source
checksum is rejected before extraction. Evidence is in
`logs/packaging-bundled-verification.log`; archives are in
`logs/packages/with-model/{linux,windows}/`. These checks verify packaging, not a
new Linux/Windows real-model generation run. Clean-host acceptance still applies.

## Flutter macOS DMG — 2026-09-20

A fresh release build passed with Xcode 27. The Apple Silicon DMG contains the
Flutter app, the same verified Q4_K_M weights, an Applications shortcut, readme
and source/model metadata. It requires macOS 14 or later and retains the Flutter
bundle identity. Metal/CPU runtime evidence above applies; packaging does not
introduce new engine changes.

`hdiutil verify` passed. After mounting read-only, strict/deep app signature
verification, model SHA-256 and Applications shortcut checks passed. The image
was cleanly detached. Logs: `logs/packaging-flutter-dmg-build.log` and
`logs/packaging-flutter-dmg.log`. Asset:
`dfm-mimir-0.1.0-macos-arm64.dmg`, SHA-256
`e0e047cfda62a0a931bc848b91e0a1f81827c8aae5331fd835faccc854c5c429`.
This is an ad-hoc development preview, without Developer ID or notarization.
The DMG and checksum are added to the existing bundled-weight desktop draft
release (GitHub release ID `392369107`; draft URLs can change when edited).

## Android ARM64 Vulkan build — 2026-09-20

The previous Android CPU-only build status is superseded: Gradle now enables
`GGML_VULKAN`, retaining the CPU backend. An optimized ARM64-only release APK
with Q4_K_M weights was built using NDK 28.2.13676358, SDK CMake 3.22.1, JDK 21,
Flutter 3.47.5, host glslc and Khronos Vulkan/SPIR-V headers. Host Ninja must be on
PATH because llama.cpp builds a host shader generator while cross-compiling.
Header and glslc overrides are documented in the README.

Cross-compilation exposed two upstream build issues, fixed in llama.cpp commit
`d49631be2`: link the SPIR-V header interface target so its include path propagates;
use the existing dynamic Vulkan dispatcher for three features2 calls rather than
requiring Android API 24's loader library to export the newer core symbol. A
missing Vulkan 1.1 version-query entry point now follows the existing unsupported
Vulkan-version path instead of calling a null function. The backend requires
Vulkan 1.2; the APK's minimum Android API remains 24.

Validation:

- Release APK build passed (`logs/android-vulkan-release-build.log`).
- APK signature verification passed; this preview uses the development/debug
  signing key, not a production distribution identity.
- `zipalign -c -P 16 4` passed; every included native library has ELF LOAD alignment
  of at least 16 KiB. Libraries are exclusively `arm64-v8a`.
- `libMimirRuntime.so` links Android's `libvulkan.so`; CPU remains compiled in.
- Embedded model SHA-256 matches the previously tested Q4_K_M weights.
- Native Mac Vulkan/MoltenVK regression suite after the source fixes: **73 checks
  passed** (`logs/android-vulkan-mac-regression.log`).

APK: `dfm-mimir-0.1.0-android-arm64.apk`, 1,236,377,679 bytes,
SHA-256 `48341e044aba10b32490e1158061d4f51613939f8dac5b5ca97f93b6c24d7745`.
The APK and checksum accompany the existing preview draft release. No Android
device was connected during this build; these are build/package checks, not
proof of Android GPU execution or performance. Real Adreno/Mali testing, including
CPU fallback on unsupported devices, remains necessary. The app depends on the
system Vulkan loader being present; this APK does not dynamically isolate an
absent loader library.

## Desktop API and headless qualification — 2026-09-20

Implementation source: `232fc26`. Desktop Settings can start a loopback HTTP API;
packages include an independently compiled `dfm-mimir-server` companion executable
(`.exe` on Windows). [API.md](API.md) documents the supported text Chat Completions
subset, launch options, authentication, queueing and limitations.

Local checks on this Mac:

- Flutter analyzer: clean. **14 tests passed**, including API response/SSE schema,
  UTF-8, usage, strict validation, optional authentication, origin rejection,
  queue limits, shutdown/deadline cancellation, and UI conversation isolation.
  The final isolation test was added after the CI source revision; CI ran the
  preceding 13-test suite.
- **9 native regression tests passed**, retaining chat-template, PrefixLM,
  persistence and reasoning coverage after adding per-request sampling.
- Real Q4_K_M CPU HTTP checks passed: model listing, nonstreaming/streaming
  generation, seeded sampling repeatability, concurrent clients, validation and
  context overflow, disconnect cancellation and follow-up generation.
- The headless executable inside the final mounted DMG passed the same real-model
  checks on **MTL0**, using bundled paths from an unrelated working directory.
  CPU and packaged Metal processes exited cleanly on SIGTERM. The mounted DMG's
  app signature and model hash also verified.

Evidence: `logs/api-analyze.log`, `logs/api-flutter-tests-final.log`,
`logs/api-native-ctest.log`, `logs/api-real-cpu-checks.log`,
`logs/api-packaged-metal-checks.log`, `logs/api-packaged-metal-server.log`, and
`logs/api-macos-package-final.log`. All generation uses the GGUF chat template.
Disconnect recovery completed in about 5.5 seconds on CPU and 5.2 on Metal in
these bounded checks; these are not performance benchmarks.

The Linux and Windows jobs in [CI run 35506872015](https://github.com/schneiderkamplab/HRM-Text/actions/runs/35506872015)
passed protocol/UI tests, native backend policy, native-library startup and
missing-backend probes, and headless executable compilation/`--help`. Weighted
release archives reuse those tested binaries and have verified archive/file/model
hashes. These CI checks do not substitute for clean-host real-model generation on
Linux/Windows or GPU qualification there.

Refreshed bundled desktop artifact SHA-256 values:

| Artifact | SHA-256 |
| --- | --- |
| `dfm-mimir-0.1.0-macos-arm64.dmg` | `6a61b8ef8b4c1d48d431d4f31bd52d6a78401b0ab2a9ef255f9020f874ad8e83` |
| `dfm-mimir-0.1.0-linux-x64.tar.gz` | `45419a0c138c9099e6a3449133b6e327233961d9cae4ad74688a7db3c73c8712` |
| `dfm-mimir-0.1.0-windows-x64.zip` | `3d5c3ced4520c74dd3e6401ca05fd0e3c6459bd12ee49e97bd98712129fea45a` |

### macOS display-name refresh — 2026-09-20

The macOS artifact above is superseded by a branding-only rebuild from `6174e9d`.
The app/executable/DMG volume now use **DFM Mimir**; bundle identity and conversation
storage remain unchanged. Xcode project/plist syntax, release build, bundled
headless `--help`, disk image verification, mounted app signature and bundled
model hash all pass. Evidence: `logs/macos-branding-build.log` and
`logs/macos-branding-package.log`. The iOS display name was corrected in source;
no iOS package was rebuilt for this macOS refresh.

Replacement `dfm-mimir-0.1.0-macos-arm64.dmg` SHA-256:
`59bd36d9be121f0148a7f7e493fc321b0fcfcaf141fe240ac46c05772aba8871`.

### Complete app identity refresh — 2026-09-20

The earlier storage-preservation decision and branding-only artifacts are
**superseded** by the user's instruction to use new identities and locations
without migration. Source `e48401c` uses `native/app`, Dart package `dfm_mimir`,
platform ID `dk.sdu.mimir`, and the `DFM Mimir` conversation directory. Linux and
Windows GUI executables are `dfm-mimir` and `dfm-mimir.exe`; Windows product and
file-description metadata use DFM Mimir. Framework SDK names remain unchanged.

- Analyzer clean; **14 tests passed** locally and on both CI hosts.
- [Linux/Windows CI run 35509226004](https://github.com/schneiderkamplab/HRM-Text/actions/runs/35509226004)
  passed protocol/UI tests, backend policy, portable package builds, native
  startup/backend probes and headless compilation/startup.
- macOS release build and DMG verification passed, including signature, model
  hash, new bundle identity and headless startup. Real-model generation from the
  mounted DMG using Metal returned `2 + 2 = 4.` and stopped cleanly on SIGTERM.
- Android ARM64 release build passed; inspected package ID `dk.sdu.mimir` and
  label DFM Mimir, signature verification, 16 KiB ZIP alignment, ARM64-only native
  libraries and the bundled model hash. Physical Android GPU testing remains
  outstanding.
- iOS simulator debug build passed; inspected CFBundleName/DisplayName DFM Mimir
  and CFBundleIdentifier `dk.sdu.mimir`. No iOS distribution package was produced.

Evidence: `logs/app-identity-{analyze,tests,desktop-ci}.log`,
`logs/app-identity-macos-{build,package}.log`,
`logs/app-identity-packaged-{api,server}.log`, and
`logs/app-identity-{android,ios}-build.log`. Linux/Windows archive checks include
all file/model hashes, executable names, and Linux execute permissions / Windows
version-resource fields. This remains build/package qualification on those two
hosts, not real-model hardware qualification.

The knowledge-bundle validator reports only two pre-existing errors in the
unrelated benchmark-charts page (missing frontmatter and index coverage).

Refreshed artifact SHA-256 values:

| Artifact | SHA-256 |
| --- | --- |
| `dfm-mimir-0.1.0-macos-arm64.dmg` | `ee1dd114cf3afc9b812c964523c8202f2cea18f783dafe12e117980bc376a27e` |
| `dfm-mimir-0.1.0-linux-x64.tar.gz` | `a06fa1538e6ec1e5c7ee4344f3892b681509d0bd2788512483e83c0f3427e0ff` |
| `dfm-mimir-0.1.0-windows-x64.zip` | `229f8e38449263474f5d3dd7adfa416d193c7bf7e131601495e218b745e351b8` |
| `dfm-mimir-0.1.0-android-arm64.apk` | `3dfa756b77c7b36418a1d905427ac0fa4e52eb472fcc8082a017962ea0d87883` |

### Android startup recovery — 2026-09-21

- Flutter analysis clean; all **25 tests passed**, including startup without native
  calls, retained explicit settings, unloaded imports/MixedLM changes, explicit
  load, backend restart enforcement, and narrow-screen settings layout.
- Built bundled ARM64 release APK with `--build-name 0.1.1 --build-number 2`.
  Installed in API 36 ARM64 emulator; inspected unloaded startup and editable CPU
  / 1024 context / 512 reply settings. Force-stop/relaunch returns unloaded.
  Startup/settings PSS was 69,477 KiB (about 68 MiB), not a loaded-model estimate.
- Native test against the actual APK runtime passed: CPU registration sets
  `GGML_DISABLE_VULKAN`, exposes no Vulkan devices, and rejects a subsequent
  Vulkan load with the restart requirement before allocating a model.
- APK signature, 16 KiB ZIP alignment and feedback credential/bundle audit passed.
- Physical-device Vulkan stability and memory use remain unqualified. This fix
  avoids entering the driver until requested and makes recovery settings reachable;
  it cannot interrupt a hung GPU driver in the same process.

Reproduce the native check from the repository root (no model loading required):

```sh
python3 native/app/tool/test_android_startup.py /path/to/app-release.apk \
  --ndk /path/to/android-sdk/ndk/28.2.13676358 \
  --adb /path/to/android-sdk/platform-tools/adb --serial emulator-5554
```

Local artifact: `logs/packages/android-startup/dfm-mimir-0.1.1-android-arm64.apk`.
SHA-256: `7b0b40088c9905748c4f059b87381e61dc5f589b729405a8cf29d59f7d06771c`.
Screenshots: `logs/android-startup/{startup,settings,reopened}.png`.
The public 0.1.0 assets were not modified.

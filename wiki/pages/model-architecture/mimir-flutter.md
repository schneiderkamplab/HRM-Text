---
type: Technical Reference
title: Mimir Flutter client and portable backend selection
description: Separate Flutter client, shared native engine, local backend evidence and remaining platform qualification.
tags: [mimir, flutter, desktop, mobile, backends]
status: draft
last_updated: 2026-09-20
confidence: high
---
# Mimir Flutter and portable backends

The [Flutter client](../../../native/flutter/README.md) is separate from the
[SwiftUI app](mimir-apple-mvp.md), with bundle ID `dk.sdu.mimirFlutter` and a
separate local archive. Initial packaged targets are Apple Silicon Mac and arm64
iOS simulator. Android was initially only a runner scaffold; the Android
development integration below supersedes that status. Linux/Windows remain
runner scaffolds, not qualified builds.

Both clients now use `native/mimir/include/mimir/compaction.h`. The previous
Apple-local header was moved without algorithm changes, and the real SwiftUI
bridge regression suite passed. Flutter uses a C ABI with a native worker and
polled JSON events; teardown drains and joins away from the UI thread.

[Validation](../../../native/flutter/VALIDATION.md) records real generation,
cancellation/recovery, compaction streaming and storage tests, app builds, iOS
keyboard/send behavior and Mac exit checks. A diagnostic forced-semantics handle caused Mac AX-tree errors and was removed;
normal Flutter accessibility activation restored the live tree. A full
VoiceOver/TalkBack audit remains outstanding. Physical device, release
credentials and distribution work remain deferred.

The old CPU/Metal-only selector in `native/mimir/tools/model.h` is superseded by
registered backend/device selection (`auto`, `cpu`, backend name or exact device
name; `metal` aliases `MTL`). The llama.cpp PrefixLM kernels already use ggml's
backend abstraction; this extension does not alter the existing patch scopes.
Explicit unavailable selections fail. [Backend report](../../../native/mimir/BACKENDS.md)
records 73 functional checks each on Mac CPU/Metal/Accelerate/Vulkan. Existing
Linux CUDA evidence is retained, including its numerical acceptance and final
sanitizer-policy-runner caveats. Other backends are explicitly unqualified.

Verified build dependencies: Flutter 3.47.5, Dart 3.13.4, Xcode 16.3 and CocoaPods
1.17.0. No Xcode upgrade was needed. Framework slices must be copied inside each
pod root; CocoaPods did not discover the vendored XCFramework through a directory
symlink. Both runners intentionally build arm64. `build_native.py` reproduces
native packaging; model weights and generated binaries stay outside Git.

## Startup chat creation — 2026-09-20

New-chat creation now waits only for local archive restoration, not backend
enumeration, model hashing or model loading. A separate `conversationsReady`
state prevents startup edits from being overwritten by archive hydration. Both
new-chat buttons use the same eligibility check; drafts can be composed while
the model loads, while sending still requires a ready engine. Active generation
and shutdown continue to block conversation creation. A widget regression test
covers archive gating, both buttons, immediate selection and draft readiness.

## Android development integration — 2026-09-20

The ARM64 Android runner now builds `native/runtime` through Gradle/NDK CMake.
The initial backend is CPU with baseline ARMv8-A instructions; Vulkan and other
GPU backends are not enabled or qualified. Host hardware virtualization and
emulator graphics acceleration are separate from inference acceleration.

GGUF is stored uncompressed in the APK and streamed by a background Kotlin worker
to app-private no-backup storage. A temporary file plus rename prevents loading a
partial copy. Package update time and asset length invalidate the extracted cache;
the existing Dart SHA-256 model-identity check still runs before model loading.
Android/Linux memory sizing now reads `MemAvailable` from `/proc/meminfo` and
retains the conservative fallback if unavailable. This is not an Android
low-memory-killer guarantee.

Local setup uses JDK 21, SDK 36, NDK 28.2.13676358, CMake 3.22.1 and an API 36
Google APIs ARM64 AVD named `DFM_Mimir_API_36`, with 8 GB RAM and a 16 GB data
partition. The emulator reports working Hypervisor.Framework acceleration.
Xcode license acceptance was still pending; direct SDK/JDK installation and
`DEVELOPER_DIR=/Library/Developer/CommandLineTools` allowed Android tooling to
proceed without changing the user's selected Xcode installation.

See the [Android build recipe](../../../native/flutter/README.md#android-development-emulator)
and [validation report](../../../native/flutter/VALIDATION.md) for execution
evidence and remaining limits. Physical Android devices and store distribution
remain unqualified.

## MixedLM and Xcode update — 2026-09-20

The earlier pending Xcode-license blocker is **superseded**: Xcode 27.0
(27A266a) is selected, first-launch checks pass, and the Metal compiler and iOS
18.4 simulator runtime are available. Flutter's six host unit/widget tests pass.

Experimental [MixedLM](../../../native/mimir/MIXEDLM.md) lives on the
`codex/mixedlm` llama.cpp branch and is available through an off-by-default
Flutter setting. It retains older prompt KV and recomputes the previous answer
plus new prompt bidirectionally. Exact token-prefix validation and conversation
identity prevent inappropriate reuse. Native CPU regression tests and real
Q4_K_M CPU/Metal smoke tests pass. The report records an observed instruction-
following regression; the mode is an approximation, not exact PrefixLM parity.

The final real-model Settings/toggle/reuse test passes on Android API 36 and the
iOS 18.4 simulator. Mac release and iOS simulator builds pass with Xcode 27.0.
An initial Android automation failure was resolved by tapping the composer after
closing Settings before injecting test input; no application workaround was
needed. See the validation report for the reproducible command.

## Proposed cross-platform release plan — 2026-09-20

The [packaging plan](../../../native/flutter/PACKAGING-PLAN.md) proposes portable
CPU packages plus qualified Metal/CUDA/Vulkan acceleration across all five OS
families. Inspection confirmed that current automatic device selection only
falls back when no GPU exists; model/context load failures do not yet trigger a
CPU retry. Desktop dynamic backend deployment also requires replacing the forced
static build configuration, and Linux/Windows model paths/native packaging are
unfinished. These are planned changes, not implemented capabilities. Specialty
backends and additional architectures follow real hardware qualification.

## Portable package implementation — 2026-09-20

The planned loader/desktop packaging gaps above are now **partly superseded**.
Linux/Windows FFI plugin targets, relocatable library/model paths, Windows memory
probing, dynamic backend packaging and a native-host package script are
implemented. Initialization retries use a shared ranked policy with CPU last;
explicit selection remains strict. App Settings reports actual device and
fallback reasons. Mac dynamic CPU/Metal real-model checks, missing-backend
probes, nine native tests and seven Flutter tests pass. Physical iOS Metal is
included in the XCFramework builder; the unsigned physical iOS release app
builds. Linux and Windows CPU/import-only archives at `6eb48b9` passed hosted CI,
including policy/Flutter tests and packaged startup/missing-backend probes.
Downloaded archive and per-file checksums verified;
[the README](../../../native/flutter/README.md) gives build commands and
[the plan](../../../native/flutter/PACKAGING-PLAN.md) distinguishes remaining
mid-generation/crash recovery, Android GPU and distribution work.

The [desktop acceptance handoff](../../../native/flutter/DESKTOP-TESTING.md)
separates CI build/startup evidence from clean-host real-model generation and GPU
qualification. Mac real-model Flutter integration, nine native tests and seven
Flutter tests passed after the fallback changes. User-requested Linux sanitizers
remain a prerequisite for final production packaging/review.

Upstream llama.cpp SDK installation must be excluded from the Flutter plugin
bundle: its relative destinations do not resolve Flutter's target-based Windows
install prefix. Explicit native build dependencies plus Flutter's library list
retain the required binaries without duplicate SDK/header installation.

### Bundled weights — 2026-09-20

Ready-to-use desktop packages now include the tested Q4_K_M model (hash and archive
checksums in the validation report), replacing the initial import-only delivery
choice. `native/flutter/tool/bundle_model.py` can assemble either host's verified
CI archive on any platform without recompilation. It validates source/file hashes,
replaces the declared Flutter model asset and records model/source archive hashes.
The native binaries retain the original `6eb48b9` provenance; post-assembly checks
confirmed unchanged binaries and Linux executable permissions. Each weighted
archive is approximately 1.12–1.13 GB. Routine CI still provides smaller import-only
builds, while ready-to-use distribution includes weights.

### Flutter macOS DMG — 2026-09-20

`native/flutter/tool/package_macos.py` packages the Flutter release app with
weights, Applications shortcut and source/model metadata. It verifies the disk
image and mounted app signature/model hash. The app retains its separate Flutter
identity; SwiftUI packaging is unchanged. The preview requires Apple Silicon and
macOS 14+, uses Metal/CPU, and has no Developer ID/notarization.

Android Vulkan is disabled in Gradle (`GGML_VULKAN=OFF`), rather than rejected by
the PrefixLM implementation. Existing 73-check MoltenVK evidence is Mac-only.
Android enablement needs cross-compilation/shader tooling, package-level optional
Vulkan loading/CPU fallback and real Adreno/Mali correctness/memory/performance
checks; simulator graphics acceleration cannot qualify phone inference drivers.

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

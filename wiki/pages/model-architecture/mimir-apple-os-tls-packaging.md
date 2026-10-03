---
type: Runbook
title: Mimir Apple OS-only TLS packaging
description: Pinned custom Flutter and Dart runtimes, pre-signing replacement, package audits, and Apple qualification evidence.
tags: [mimir, apple, flutter, packaging, tls]
status: draft
last_updated: 2026-10-03
confidence: high
---
# Mimir Apple OS-only TLS packaging

The source-built engine experiment in [Mimir v1.5 GGUFs](mimir-v1.5-ggufs.md)
now has a release-packaging integration. **Superseded, 2026-10-03:** the earlier
statement that ordinary release builds still embed stock Flutter. Release Xcode
embed phases now call `native/app/tool/apple_engine.py install` and fail closed
without the prepared custom engine. Uploaded build 12 is still unchanged.

## Boundaries

* Flutter revision `6a19cca56475dbfba1478ee68d7bd0c2ef891da1`; Dart revision
  `b530c21f7de367b94fb04787bfed9d8e989d75e8`.
* The three patches and complete build instructions are in
  `native/app/tool/apple_os_tls/README.md`. The separate engine checkout is
  `logs/toolchains/flutter-os-tls`, overridable by `MIMIR_APPLE_ENGINE_ROOT`.
* Compile with `dart_disable_secure_socket=true`; Apple GUI networking uses
  URLSession through cupertino_http. Dart TLS calls deliberately throw.
* Replace the framework executable **before** final Xcode signing, re-signing
  the embedded framework with the selected identity. Do not strip TLS code from
  a linked executable or mutate a signed final package.
* App Store archive tooling generates matching custom-engine dSYMs and audits
  all Mach-O binaries. Code-section fingerprints survive signing/stripping.
* The DMG's standalone server needs a separate BoringSSL-free
  `dartaotruntime_product`. Build the server AOT snapshot with matching Dart,
  then use the pinned Dart source's executable writer. Stock `dart compile exe`
  would silently restore bundled BoringSSL. Linux/Windows remain unchanged.
* Final audits reject stock engines, missing prepared sources, bundled crypto
  symbols/source markers, and the diagnostic probe entry point.

## Simulator and build pitfalls

The ARM64 simulator debug engine is opt-in with `MIMIR_APPLE_OS_TLS=1`.
The simulator build compiles host-side Dart tools with BoringSSL; these are not
shipped. Audit permits only that explicitly identified host toolchain dependency.
The JIT kernel also retains two BoringSSL mentions in Dart library source
comments, with no native TLS symbols/source paths. Release audits have no such
source-comment exception. Other debug/profile configurations are not qualified.

Xcode 27's SDK requires the system linker, modern platform-version flags, and
its own libLTO path. The optional `apple_system_linker` GN patch supplies these.
The standalone Dart embedder had an unused secure-socket header which otherwise
prevented building without OpenSSL headers; the Dart patch removes it.

Use Python 3.11+ for archive/DMG tools (`hashlib.file_digest`); Xcode's bundled
Python 3.9 is sufficient for the install hook. The build uses no LTO, so removing
BoringSSL does not imply a smaller binary than Flutter's optimized stock build.

## Qualification and artifacts

Evidence directory: `logs/apple-os-tls-packaging/`.

* All 75 Flutter tests pass; Flutter analysis reports no issues.
* iOS and macOS normal-entry-point archives, version 0.1.5 build 13, pass model,
  native/custom-engine dSYM UUID and whole-bundle crypto audits. These local
  archives are unsigned and have not been uploaded.
* macOS runtime probe passes disabled Dart TLS, URLSession public-catalog HTTPS,
  native streaming cancellation, offline templated generation with Metal,
  chat/settings persistence and GUI-hosted OpenAI completion.
* iPhone 18 Pro simulator, iOS 27: the same probe passes disabled Dart TLS,
  URLSession HTTPS/cancellation, CPU generation and chat/settings persistence.
  Flutter debug output is in simulator unified logging, not simctl's captured
  stdout: `probe-simulator-unified.log` contains `MIMIR_OS_TLS_PROBE_PASS`.
* Custom standalone server passes model listing, completion and SSE streaming.
* Stock-engine and diagnostic-entry-point negative controls are rejected.
* `dmg-build13/dfm-mimir-0.1.5-macos-arm64.dmg` passes mounted model checksum,
  deep/strict signature and whole-bundle crypto checks. It is locally ad-hoc
  signed, not Developer ID signed/notarized. The normal macOS app is restored
  at `native/app/build/macos/Build/Products/Release/DFM Mimir.app`.
* Physical iPhone testing was explicitly declined by the user; device runtime
  behavior has not been validated in this qualification.

This records technical evidence, not an export-compliance determination. App
Store Connect answers and uploaded builds must be handled separately.

# Experimental Apple OS-only networking

This is an experiment, not an approved export classification or a production
engine distribution. Do not change Apple's encryption answers based solely on
these patches. Existing submitted build 12 is unchanged.

## Pinned inputs

- Flutter `6a19cca56475dbfba1478ee68d7bd0c2ef891da1` (3.47.5).
- Dart `b530c21f7de367b94fb04787bfed9d8e989d75e8` (Flutter DEPS).
- `flutter.patch`: use Apple's CommonCrypto for shader-cache SHA-1 and remove
  the Apple graphics target's BoringSSL dependency. SHA-1 only preserves cache
  filenames; it does not authenticate content. Deprecation suppression is local.
- `apple-linker.patch`: optional GN argument `apple_system_linker` selects the
  Xcode linker when the bundled LLVM linker cannot read the Xcode 27 SDK.
- `dart.patch`: avoid unconditional BoringSSL build dependencies when the
  upstream `dart_disable_secure_socket` option is enabled. Dart already provides
  native functions that throw when secure sockets are disabled.

The application uses `cupertino_http`/URLSession on Apple platforms through
`lib/network.dart`. Linux, Windows and Android keep the Dart HTTP transport.
All operations explicitly abort requests on cancellation; CupertinoClient.close
alone allows active requests to finish. Model redirect policy, streaming and
checksum verification remain in model_library.dart. Search and feedback never
follow redirects. Apple sessions are ephemeral, with cookies disabled and local
cache reads bypassed.

## Reproduce engine build

Use a separate checkout of the pinned Flutter revision, not the release SDK.
Follow that revision's `docs/engine/contributing/Setting-up-the-Engine-development-environment.md`:
install depot_tools, copy `engine/scripts/standard.gclient` to `.gclient`, and run
`gclient sync --no-history`. Android dependency downloads may be disabled with
`custom_vars: {"download_android_deps": False}`. Keep depot_tools on PATH so
GN can find vpython3. A runtime SDK installation alone lacks engine dependencies.

Apply flutter.patch and apple-linker.patch at the Flutter root, and dart.patch in
`engine/src/flutter/third_party/dart`, after checking each with `git apply --check`.
From `engine/src`, configure:

```sh
python3 flutter/tools/gn --runtime-mode release --mac-cpu arm64 --no-lto --gn-args 'dart_disable_secure_socket=true'
python3 flutter/tools/gn --ios --runtime-mode release --no-lto --gn-args 'dart_disable_secure_socket=true'
```

Install the Metal compiler with `xcodebuild -downloadComponent MetalToolchain`
if the current Xcode installation lacks it.

Use the synced `third_party/ninja/ninja` at the Flutter checkout root:

```sh
../../third_party/ninja/ninja -C out/host_release_arm64 FlutterMacOS.framework -j 8
../../third_party/ninja/ninja -C out/ios_release flutter_framework -j 6
```

On Xcode 27, both builds initially failed because bundled ld64.lld rejects the
SDK's `arm64e.x1` TAPI architecture. Append
`apple_system_linker="/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/ld"`
to the `--gn-args` value (use the actual path from `xcrun --find ld`).

These are engine framework targets, not the complete host tool artifacts needed
for every Flutter local-engine operation. Build additional tool targets when the
Flutter build requires them. `--no-lto` speeds this experiment; production LTO,
signing, archive validation and physical-device testing remain separate checks.

## Evidence and acceptance

`../probe_apple_engine_strip.py PATH_TO_FRAMEWORK_BINARY` strips only a temporary
copy, selects arm64 from a universal framework, and compares every __TEXT section.
It never modifies an archive. Symbol stripping is not code elimination.

For custom frameworks, inspect GN transitive dependencies and linked symbols,
not just strings. Confirm there is no BoringSSL SSL/AES/ChaCha implementation and
that CommonCrypto is dynamically supplied by Apple. Compare source pins and
record complete build results.

`probe.dart` is a temporary release entry point for a local macOS build. It checks
that SecurityContext throws the upstream disabled-TLS error, native URLSession
can download the public model catalog over HTTPS, and cancellation interrupts a
streaming loopback response. Success prints `MIMIR_OS_TLS_PROBE_PASS` and exits.
Never archive or publish that entry point. Run normal app tests and rebuild the
normal `lib/main.dart` entry point afterward.

Local investigation artifacts live under `logs/apple-tls-removal/`; the separate
engine checkout is `logs/toolchains/flutter-os-tls/`. Neither is committed.

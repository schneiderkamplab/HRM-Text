# Apple OS-only networking and packaging

Apple release builds now require this custom engine. This is not an approved
export classification. Existing uploaded build 12 is unchanged; rebuilding
locally does not replace it in App Store Connect.

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
  native functions that throw when secure sockets are disabled. Also remove an
  unused secure-socket header from the standalone Dart embedder.

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
../../third_party/ninja/ninja -C out/host_release_arm64 dartaotruntime_product -j 6
../../third_party/ninja/ninja -C out/ios_release flutter_framework -j 6
```

On Xcode 27, both builds initially failed because bundled ld64.lld rejects the
SDK's `arm64e.x1` TAPI architecture. Append
`apple_system_linker="/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/ld"`
to the `--gn-args` value (use the actual path from `xcrun --find ld`).
The patch also selects modern linker platform flags and the same Xcode
toolchain's libLTO. Without these, the simulator link uses an obsolete
`-ios_simulator_version_min` flag or references a missing bundled libLTO.

For an ARM64 simulator debug engine:

```sh
python3 flutter/tools/gn --ios --simulator --simulator-cpu arm64 --runtime-mode debug --no-lto --gn-args 'dart_disable_secure_socket=true apple_system_linker="/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/ld"'
../../third_party/ninja/ninja -C out/ios_debug_sim_arm64 flutter_framework -j 8
```

The simulator build's host Dart compiler tools can contain BoringSSL; these
macOS tools are never embedded in the iOS application. The actual simulator
framework must pass linked-symbol and source-path checks. Its JIT kernel retains
Dart library comments mentioning BoringSSL; these are not native TLS code. This
source-comment allowance applies only to debug simulator qualification, never
to release-package audits.

These are engine framework targets, not the complete host tool artifacts needed
for every Flutter local-engine operation. Build additional tool targets when the
Flutter build requires them. `--no-lto` speeds this experiment; production LTO and
physical-device testing remain separate checks. Engine upgrades must be rebased
and requalified; packaging deliberately rejects a different Flutter/Dart pin.

## Build and package

The Xcode embed phases invoke `../apple_engine.py install` after Flutter embeds
its framework and before the final application signature. This replaces the
framework executable with the source-built engine and re-signs that framework
using Xcode's selected identity. It does not attempt to strip TLS instructions
out of an already linked stock binary.

The default checkout is `logs/toolchains/flutter-os-tls` relative to the repo.
Set `MIMIR_APPLE_ENGINE_ROOT` to use another prepared checkout. Missing or wrong
engines fail release builds; there is no silent stock fallback. Ordinary debug
builds stay stock. Set `MIMIR_APPLE_OS_TLS=1` for the qualified ARM64 iOS simulator
debug engine. Other debug/profile configurations are not qualified for this
replacement or distribution.

`tool/archive_apple.py` prepares the normal `lib/main.dart` entry point, verifies
every embedded Mach-O, compares engine code sections with the qualified build,
and generates matching engine dSYMs. It also retains the existing native
runtime, model checksum, privacy-manifest and signing checks. Use Python 3.11+
for archive/DMG tooling; the Xcode install hook works with Apple's Python 3.9.

`tool/package_macos.py` requires the qualified app and builds the headless server
as an AOT snapshot appended to the custom `dartaotruntime_product`. The pinned
Dart source's own executable writer handles Mach-O layout. The compiler itself
may use stock Dart; its runtime is not shipped. Package checks compare the
server's runtime code sections too, both before DMG creation and after mounting.
Linux/Windows/Android packaging is unchanged.

From the repository root:

```sh
python3 native/app/tool/archive_apple.py ios --flutter logs/toolchains/flutter/bin/flutter --output logs/os-tls-ios --build 13
python3 native/app/tool/archive_apple.py macos --flutter logs/toolchains/flutter/bin/flutter --output logs/os-tls-macos --build 13
```

Omit `--team-id` for unsigned archives; add a verified signing team for signed
archives. Neither command uploads. Stock symbols must never accompany the
custom engine. Do not apply binary replacements to an already signed final
archive or DMG; rebuild through these hooks instead.

## Evidence and acceptance

`../probe_apple_engine_strip.py PATH_TO_FRAMEWORK_BINARY` strips only a temporary
copy, selects arm64 from a universal framework, and compares every __TEXT section.
It never modifies an archive. Symbol stripping is not code elimination.

For custom frameworks, inspect GN transitive dependencies and linked symbols,
not just strings. Confirm there is no BoringSSL SSL/AES/ChaCha implementation and
that CommonCrypto is dynamically supplied by Apple. Compare source pins and
record complete build results.

`probe.dart` is a temporary entry point for a local macOS or simulator build. It checks
that SecurityContext throws the upstream disabled-TLS error, native URLSession
can download the public model catalog over HTTPS, and cancellation interrupts a
streaming loopback response. It also generates a templated answer offline, saves
chats/settings, and (on macOS) generates through the local OpenAI API. Success
prints `MIMIR_OS_TLS_PROBE_PASS` and exits.
Never archive or publish that entry point. Run normal app tests and rebuild the
normal `lib/main.dart` entry point afterward.
The final package audit explicitly rejects the probe entry point.

Local investigation artifacts live under `logs/apple-tls-removal/`; the separate
engine checkout is `logs/toolchains/flutter-os-tls/`. Neither is committed.

# Apple OS-only TLS experiment — 3 October 2026

**Follow-up:** release builds now require the custom engine before final signing.
See `../tool/apple_os_tls/README.md` for packaging and the repository knowledge
page `wiki/pages/model-architecture/mimir-apple-os-tls-packaging.md` for current
qualification. The observations below describe the initial experiment; uploaded
build 12 remains unchanged.

**Result: removing bundled BoringSSL is technically feasible with a custom Flutter
engine.** Both ARM64 frameworks build without it. A macOS release probe runs with
Dart TLS disabled and successfully uses Apple's URLSession for HTTPS and request
cancellation. This is technical evidence, not Apple's approval of an exemption.

## What was tested

| Check | iOS ARM64 | macOS ARM64 |
| --- | --- | --- |
| Strip existing build-12 framework (`strip -x -S` on a copy) | No bytes removed; all __TEXT sections unchanged | Same |
| Compile Dart's four main TLS translation units with secure sockets disabled | No global/undefined symbols | Same |
| Custom framework dependency graph | No BoringSSL target | No BoringSSL target |
| Full custom framework build/link | Passed | Passed |
| Linked SSL/EVP/AES/CRYPTO/X509/BORINGSSL/ChaCha symbol search | No matches | No matches |
| BoringSSL source-path strings in framework binary | 0 | 0 |
| Application release build with native networking | Passed, unsigned | Passed |
| Runtime: Dart SecurityContext rejected; native HTTPS works | Not run on device | Passed |
| Runtime: URLSession abort during a streaming response | Not run on device | Passed |

The standard-framework macOS control run rejected the probe with “Dart TLS
remains enabled”. The same app snapshot with the custom framework passed and
printed `MIMIR_OS_TLS_PROBE_PASS`. It loaded the public model catalog over HTTPS
without a search credential or feedback submission. The cancellation check used
a local HTTP server; its initial tiny response without an explicit binary MIME
type timed out before exposing headers. An explicit unbuffered 16 KiB binary
response allowed the streaming-cancellation test to execute and pass.

`flutter analyze` passed and all **75 Flutter tests** passed, including explicit
abort after response headers, abort before headers, redirect downgrade rejection,
model checksum/size checks, feedback errors/retries and search status handling.
No new physical-device qualification, signed App Store archive, upload or export
compliance declaration was performed.

## Changes and boundaries

Application code now selects `cupertino_http` 2.4.0 / URLSession on Apple
platforms for search, feedback, catalog/discovery and downloads. A single network
session abstraction owns cancellation. Other platforms retain `IOClient`.
Native sessions are ephemeral, disable cookies and bypass local cache reads.
Explicit abort is necessary because closing CupertinoClient alone permits active
tasks to finish. Redirects remain disabled for search/feedback; model redirects
are followed manually only to HTTPS URLs. Downloads remain streamed to disk.

The experimental engine uses upstream `dart_disable_secure_socket=true`.
Small patches remove unconditional BoringSSL dependencies and use Apple's
CommonCrypto for the shader-cache SHA-1 operation. That hash preserves existing
cache names; it is not an authenticity mechanism. The macOS framework imports
`CC_SHA1_Init/Update/Final`; the iOS linked binary did not retain those imports.
Dart's secure-socket entry points remain as upstream throwing stubs, with no TLS
implementation behind them. Plain sockets and the loopback HTTP server still work.

Framework source pins, patches and reproduction instructions are in
[tool/apple_os_tls](../tool/apple_os_tls/README.md). The engine changes are not
installed into the normal Flutter SDK or automatically selected by release scripts.
The application migration alone does **not** remove stock Flutter's BoringSSL.

## Build issues resolved

1. The installed Flutter SDK lacked engine dependency checkouts. Used a separate
   pinned worktree and `gclient sync --no-history`.
2. Bundled ld64.lld rejected Xcode 27's `arm64e.x1` TAPI architecture. Added an
   optional GN argument selecting Xcode's system linker; kept the bundled compiler.
3. Xcode's Metal compiler was missing. Installed Metal Toolchain 27A266a through
   `xcodebuild -downloadComponent MetalToolchain`.

These experiments use `--no-lto` and retain diagnostic symbols. The resulting
frameworks are **larger**, despite removing encryption: macOS ARM64 21,197,328
bytes versus 14,618,592 in build 12; iOS 16,228,424 versus 9,416,288. This is not a
controlled size comparison. Production LTO/stripping/signing should be tested
before choosing final artifacts.

## Local evidence

- `logs/apple-tls-removal/strip-{ios,macos}.json`: original framework experiment.
- `logs/apple-tls-removal/{ios,macos}-deps.txt`: custom framework dependency graphs.
- `logs/apple-tls-removal/audit-{ios,macos}.json`: linked-binary checks.
- `logs/apple-tls-removal/build-macos-final.log` and `build-ios-retry.log`: successful engine builds.
- `logs/apple-tls-removal/probe-stock.log`: expected control failure.
- `logs/apple-tls-removal/probe-custom-retry.log`: successful native runtime probe.
- `logs/apple-tls-removal/app-build-ios.log`: unsigned normal iOS application build.
- `logs/apple-tls-removal/app-build-macos-final.log`: restored normal macOS entry point.
- `logs/apple-tls-removal/macos/DFM Mimir.app`: normal application copy with custom
  framework; ad-hoc signed and deep/strict signature verification passed.
- `logs/apple-tls-removal/ios/Runner.app`: unsigned experimental app copy with custom framework.

Local logs and binaries are not committed. The dependency graph and binary tests
together are stronger evidence than a string search alone; neither proves a
regulatory classification. Host build tools such as gen_snapshot may still depend
on BoringSSL, but are not part of the distributed application framework.

## Before adopting this for distribution

- Select and pin the custom engine in the Apple archive/CI workflow, with a check
  that refuses a stock-framework fallback. Maintain patches across Flutter updates.
- Test the iOS runtime on a device (and simulator when a matching engine is built),
  plus full chat/Keychain/download/search/feedback behavior on both platforms.
- Produce production-configured, signed archives and audit every shipped Mach-O,
  not only the engine. Preserve provenance and symbols separately.
- Reassess Apple's OS-only documentation exception for those final archives;
  do not reuse the build-12 encryption declaration or assert approval prematurely.

Existing GitHub/App Store/TestFlight releases and the signed build-12 archives
have not been replaced.

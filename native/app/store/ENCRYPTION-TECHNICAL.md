# DFM Mimir — encryption technical description

Prepared 3 October 2026 for institutional review and ANSSI clarification.
This describes the audited Apple builds; it is not a certificate or exhaustive
cryptographic validation report. Administrative signatory fields remain pending.

## Product and purpose

DFM Mimir is an on-device Danish/English generative AI assistant. Model inference,
conversation storage and context summarization run locally. Optional services
include web search, feedback submission and downloading additional models.
It is not a VPN, person-to-person encrypted messenger or general cryptography API.

| Field | Value |
| --- | --- |
| Product/version | DFM Mimir 0.1.5, build 12 |
| Platforms examined | iOS/iPadOS ARM64; macOS Apple silicon |
| Publisher proposed for filing | Syddansk Universitet (University of Southern Denmark) |
| Bundle ID / Apple app ID | dk.sdu.dfm.mimir / 6818524811 |
| Apple team | 46HSA3LZ7H |
| Technical contact | Peter Schneider-Kamp, petersk@imada.sdu.dk |
| Source | https://github.com/schneiderkamplab/HRM-Text |
| Flutter / Dart | 3.47.5 stable / 3.13.4 |
| Flutter revision | 6a19cca56475dbfba1478ee68d7bd0c2ef891da1 |
| Engine revision | af7e796e161ae0bb1ff0758c71a7105418bd9ded |
| Toolchain BoringSSL source pin | 2e508c973d634b3aa51b71db5062bc6b096e5031 |

Both archived Flutter frameworks contain BoringSSL source-path references. The
revision above comes from the build toolchain's DEPS, not independent extraction
of a revision identifier from the machine code. Archive creation used then-local
source changes subsequently committed in b5979c0; do not describe the archives
as a pristine build of the earlier parent commit.

## Cryptographic functions

| Function | Implementation and scope |
| --- | --- |
| HTTPS confidentiality and server authentication | Dart `HttpClient` through bundled Flutter/Dart TLS with BoringSSL; not solely Apple OS TLS |
| Remembered search access key | `flutter_secure_storage` 11.2.0 using Apple Keychain SecItem APIs; OS-managed protection |
| Model checksums and identity | SHA-256, 256-bit digest; no encryption key |
| App signing / installation validation | Apple platform distribution mechanisms, distinct from app payload encryption |

Dart's documented default minimum TLS version is 1.2, and its API supports TLS
1.3. Mimir does not configure custom cipher suites or implement its own cipher.
The pinned BoringSSL source includes TLS 1.3 AES-128-GCM/SHA-256,
AES-256-GCM/SHA-384 and ChaCha20-Poly1305/SHA-256 suites (128/256/256-bit
symmetric keys respectively). This is a source capability inventory, **not** a
record of the suite negotiated by every service or a complete enabled TLS 1.2
suite/group inventory. See the pinned
[BoringSSL cipher source](https://github.com/google/boringssl/blob/2e508c973d634b3aa51b71db5062bc6b096e5031/ssl/ssl_cipher.cc).

TLS key establishment, certificate verification, random generation and session
key management are delegated to the runtime. The application does not expose
TLS session keys or provide a way to change cryptographic algorithms. Server
certificates/keys belong to the service operators. There is no app-provided
client certificate or custom certificate-validation bypass in the audited flows.
The search bearer token is an application credential, not a TLS encryption key.
No Jina provider secret is bundled in the app; the Worker holds that credential.

Before a formal form requests an exhaustive algorithm/key-length list, verify
all enabled TLS 1.2 suites, signature schemes and key-exchange groups against
this pinned runtime (including any hybrid groups); do not substitute a generic
OpenSSL list. No FIPS certification is claimed by the presence of a `fipsmodule`
source path. No special key escrow or cryptographic modification is implemented
by Mimir.

## Data flow and activation

| Feature | Data and destination | Activation/protection |
| --- | --- | --- |
| Ordinary chat and compaction | Local inference and local conversation files | No remote inference required |
| Search | Query to the Cloudflare Worker `/v1/search`, then provider request performed by the Worker | Optional enabled search with user key; app-to-Worker HTTPS; full chat is not automatically sent, but queries may reflect chat content |
| Feedback | User-confirmed chat, rating and accompanying metadata to Worker `/v1/feedback` | Explicit submission; HTTPS |
| Model catalog/discovery/download | GitHub raw catalog, Hugging Face and download redirects/CDNs; optionally user-specified HF repositories | Network-dependent optional model management; HTTPS |
| macOS local OpenAI-compatible API | Loopback `127.0.0.1` HTTP | Optional local server; no TLS endpoint provided by this GUI build |
| Privacy/support links | External browser | Browser/OS networking, outside this app's Dart TLS connection |

Worker origin: `https://dfm-mimir-feedback.dfm-mimir-feedback.workers.dev`.
Catalog: `https://raw.githubusercontent.com/schneiderkamplab/HRM-Text/main/native/app/assets/models.json`.
Service-side cryptography is outside the distributed Apple binary's inventory.

Local conversation JSON and GGUF model files are not encrypted by a custom
application layer. OS file/disk protection is separate. A remembered search key
uses the Apple Keychain; without remembering, the app need not persist that key.
Optional networking does not remove TLS code from the distributed binary.

## Reproducible evidence

Repository paths (relative to its root):

- `native/app/lib/search.dart`: Dart HTTPS and secure storage.
- `native/app/lib/feedback.dart`: confirmed feedback HTTP client.
- `native/app/lib/model_library.dart`: catalog/download HTTP and hashes.
- `native/app/lib/store.dart`: model identity/checksum handling.
- `native/app/packages/mimir_api/lib/api/server.dart`: loopback HTTP server.
- `native/app/pubspec.lock`: package versions.
- `logs/toolchains/flutter/bin/cache/flutter.version.json`: runtime identity.
- `logs/toolchains/flutter/DEPS`: `dart_boringssl_rev` and dependency binding.
- `logs/toolchains/flutter/bin/cache/dart-sdk/lib/io/security_context.dart`:
  documented TLS protocol/default settings.
- `logs/sdu-store/ios-signed-12/DFM Mimir.xcarchive` and
  `logs/sdu-store/macos-signed-12/DFM Mimir.xcarchive`: inspected archives;
  adjacent audit JSON contains signing/model/native-symbol checks.

The logs/toolchain/archive evidence is local and is not committed. For a filing,
retain the archive audit output and provide an appropriate sample through an
approved channel if requested. Never include private signing keys or credentials.

## Short technical statement for correspondence

DFM Mimir 0.1.5 (12) for iOS and macOS is a local AI assistant. It uses standard
HTTPS through the Flutter/Dart runtime's bundled BoringSSL implementation for
optional web search, confirmed feedback and model downloads. It additionally
uses Apple Keychain for a remembered access credential and SHA-256 for model
checksums. No proprietary cryptographic algorithm, VPN function or end-to-end
person-to-person messaging is implemented. We seek confirmation of the applicable
French formalities and whether any documented upstream coverage may apply.

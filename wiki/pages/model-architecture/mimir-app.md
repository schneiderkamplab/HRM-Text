---
type: Technical Reference
title: DFM Mimir app and portable backend selection
description: Separate Flutter client, shared native engine, local backend evidence and remaining platform qualification.
tags: [mimir, flutter, desktop, mobile, backends]
status: draft
last_updated: 2026-09-22
confidence: high
---
# DFM Mimir app and portable backends

The [Flutter client](../../../native/app/README.md) is separate from the
[SwiftUI app](mimir-apple-mvp.md), with bundle ID `dk.sdu.mimir` and a
separate local archive. Initial packaged targets are Apple Silicon Mac and arm64
iOS simulator. Android was initially only a runner scaffold; the Android
development integration below supersedes that status. Linux/Windows remain
runner scaffolds, not qualified builds.

Both clients now use `native/mimir/include/mimir/compaction.h`. The previous
Apple-local header was moved without algorithm changes, and the real SwiftUI
bridge regression suite passed. Flutter uses a C ABI with a native worker and
polled JSON events; teardown drains and joins away from the UI thread.

[Validation](../../../native/app/VALIDATION.md) records real generation,
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

See the [Android build recipe](../../../native/app/README.md#android-development-emulator)
and [validation report](../../../native/app/VALIDATION.md) for execution
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

The [packaging plan](../../../native/app/PACKAGING-PLAN.md) proposes portable
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
[the README](../../../native/app/README.md) gives build commands and
[the plan](../../../native/app/PACKAGING-PLAN.md) distinguishes remaining
mid-generation/crash recovery, Android GPU and distribution work.

The [desktop acceptance handoff](../../../native/app/DESKTOP-TESTING.md)
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
choice. `native/app/tool/bundle_model.py` can assemble either host's verified
CI archive on any platform without recompilation. It validates source/file hashes,
replaces the declared Flutter model asset and records model/source archive hashes.
The native binaries retain the original `6eb48b9` provenance; post-assembly checks
confirmed unchanged binaries and Linux executable permissions. Each weighted
archive is approximately 1.12–1.13 GB. Routine CI still provides smaller import-only
builds, while ready-to-use distribution includes weights.

### Flutter macOS DMG — 2026-09-20

`native/app/tool/package_macos.py` packages the Flutter release app with
weights, Applications shortcut and source/model metadata. It verifies the disk
image and mounted app signature/model hash. The app retains its separate Flutter
identity; SwiftUI packaging is unchanged. The preview requires Apple Silicon and
macOS 14+, uses Metal/CPU, and has no Developer ID/notarization.

Android Vulkan is disabled in Gradle (`GGML_VULKAN=OFF`), rather than rejected by
the PrefixLM implementation. Existing 73-check MoltenVK evidence is Mac-only.
Android enablement needs cross-compilation/shader tooling, package-level optional
Vulkan loading/CPU fallback and real Adreno/Mali correctness/memory/performance
checks; simulator graphics acceleration cannot qualify phone inference drivers.

### Android Vulkan enabled — 2026-09-20

The disabled-build statement above is **superseded**. Android now builds CPU plus
Vulkan into a development-signed ARM64 release APK with the usual Q4_K_M weights.
The APK passes signature, model hash, ABI and 16 KiB ZIP/ELF alignment checks.
llama.cpp `d49631be2` fixes SPIR-V header propagation, uses the existing dynamic
Vulkan dispatcher for features2 queries (avoiding API 24 link errors), and checks
for an absent loader version-query entry point. Mac MoltenVK's 73 text checks
pass after these changes. Host Ninja must be on PATH for shader generation;
README environment overrides locate glslc and the header-only SDK dependencies.
Android GPU execution remains unqualified; no physical device was connected.

### Distribution filenames — 2026-09-20

Use `dfm-mimir-VERSION-PLATFORM-ARCH.EXT` for downloadable packages, with lowercase
platforms `android`, `macos`, `linux`, `windows`, and architectures `arm64` or
`x64`. Omit Flutter, backend and preview qualifiers from filenames. Checksum files
append `.sha256` and name the matching archive inside. Existing release assets
were renamed in place (binary content and hashes unchanged); packaging tools
read the app version rather than hardcoding it. This supersedes earlier preview
and unversioned filenames. Draft release tags may differ from their initial name;
resolve the current tag from the release ID before uploading assets.

### API availability — 2026-09-20

The packaged apps do not start an HTTP listener or expose an OpenAI-compatible
endpoint. Flutter talks to the in-process C ABI (`native/runtime/mimir_ffi.*`),
which accepts one command at a time and streams polled events. The current chat
path uses greedy sampling and a system prompt selected at model load. An app API
would need request arbitration with UI generation plus request-level prompt and
sampling semantics; merely forwarding arbitrary Chat Completions JSON is not
sufficient. The separate patched `llama-server` implements `/v1/models` and
`/v1/chat/completions`, but is not launched or bundled by these apps.

### Desktop API implementation — 2026-09-20

The earlier no-API statement is **superseded**. Desktop Settings now exposes an
opt-in localhost Chat Completions server. A plain Dart `mimir_api` package shares
FFI/HTTP code between Flutter and an AOT `dfm-mimir-server` companion executable,
so Linux headless operation does not require a display or Flutter engine. Native
commands serialize UI/API work, isolate request cancellation, and reset API
system/sampling state without editing saved chats. Exact templated PrefixLM API
requests do not use compaction or MixedLM reuse. Supported API subset and limits
are documented in [API.md](../../../native/app/API.md). Local real-model CPU and packaged Metal HTTP checks, nine native regression
tests, and fourteen Flutter/API/UI tests pass. Linux and Windows packaging CI
(run 35506872015, source `232fc26`) passed the preceding thirteen-test suite,
native startup/backend probes, and headless compilation/`--help`. Packages include
the bundled weights and headless executable; clean-host real-model Linux/Windows
generation and GPU qualification remain outstanding. Settings displays the active
URL and permits toggling the API and editing its port while stopped. The bind
address is fixed to IPv4 loopback; toggle/port settings are session-only.
See [validation evidence](../../../native/app/VALIDATION.md).

### Display branding — 2026-09-20

The macOS product, DMG volume/readme and iOS display name now use **DFM Mimir**;
the previous **DFM Mimir Flutter** display branding is superseded. Bundle IDs and
the existing conversation storage directory remain stable to preserve user data.
Android and Linux/Windows window titles already use DFM Mimir. Linux/Windows
executable filenames remain `mimir_flutter`/`mimir_flutter.exe`; Windows version
metadata still uses that internal name. Download filenames retain the uniform
`dfm-mimir-0.1.0-platform-arch.extension` convention.

The remaining executable/metadata naming limits above are **superseded** by the
follow-up: Linux/Windows GUI binaries are `dfm-mimir`/`dfm-mimir.exe`; Windows
ProductName/FileDescription are DFM Mimir and InternalName is dfm-mimir. iOS
CFBundleName also uses DFM Mimir. Windows conversation storage is explicitly
anchored to its existing `dk.sdu/mimir_flutter` directory because path_provider
derives the default directory from ProductName. Bundle IDs, Dart package names
and storage identifiers are intentionally stable implementation identities.

The storage-preservation decision above is **superseded** by the user's explicit
clarification (2026-09-20): there are no existing users. Use the new DFM Mimir
conversation directory directly, including Windows' ProductName-derived root,
without migration or legacy-path logic. Existing development data stays at its
old location; new builds use the new path.

The subsequent naming instruction also supersedes retaining app-owned Flutter
identifiers: sources now live under `native/app`, the Dart app package is
`dfm_mimir`, platform application IDs are `dk.sdu.mimir`, and CI uses
`mimir-desktop.yml`. The SDK's required Flutter framework files and build
commands retain their actual framework names. All platforms use new storage
locations, with no migration or compatibility paths.

### Feedback collection decision — 2026-09-20

The user selected Cloudflare Workers + D1 for the planned feedback service,
following evaluation of Supabase's inactivity pausing. No feedback service has
been implemented or deployed yet. Requirements: thumbs up/down on a conversation;
explicit confirmation before sending the current chat to the Mimir team to improve
Mimir and other DFM models; a separate publication permission under CC BY, on by
default; and an offered device-generated attribution pseudonym. The proposed
pseudonym uses locally stored randomness, not a hardware identifier. Publication
is a separate reviewed export, not automatic on submission. Account creation and
Wrangler browser login precede remote provisioning; local implementation does not
require credentials. Proposed deployment uses the free tier, a workers.dev URL,
and a D1 EU jurisdiction selected at creation. D1 jurisdiction covers database
execution/storage, not all Worker request processing. References:
[Workers setup](https://developers.cloudflare.com/workers/get-started/guide/),
[D1 setup](https://developers.cloudflare.com/d1/get-started/), and
[D1 jurisdictions](https://developers.cloudflare.com/d1/configuration/data-location/).

Wrangler 4.135.0 OAuth login and `wrangler whoami` succeeded on the development
Mac on 2026-09-20; Workers and D1 write access were verified. Credentials remain
in Wrangler's local configuration, outside the repository. No remote feedback
resources have been provisioned yet; the public team contact email is pending.

The contact-email placeholder is **superseded**: the user selected
`petersk@imada.sdu.dk` as the public feedback contact. Following the user-requested
[Cloudflare agent setup](https://developers.cloudflare.com/agent-setup/prompt.md),
14 Cloudflare skills were installed under `~/.codex/skills` using Codex's
skill installer, and five MCP servers were registered in `~/.codex/config.toml`.
Cloudflare API, bindings, builds and observability OAuth authorizations are saved;
the docs server is public. Existing Codex settings were preserved (the CLI only
normalized an empty argument list). Restart Codex to load the new MCP tools;
Wrangler deployment access is already available. This configures development
tools only: no feedback endpoint or D1 database has been deployed yet.

### Feedback D1 provisioning — 2026-09-20

The previous "no database deployed" status is **superseded**. Created the remote
`dfm-mimir-feedback` database using Wrangler 4.135.0 with `--jurisdiction=eu`.
Database ID: `fe4f6f32-9602-4215-80a6-848b0027f28b`. A subsequent `d1 info
 dfm-mimir-feedback --json` verified `jurisdiction: eu`, execution region `EEUR`,
read replication disabled and zero user tables. The database is empty; schema,
Worker endpoint and app feedback UI are still to be implemented. No Worker has
been deployed as part of this database-creation step.

### Feedback implementation — 2026-09-20

The previous empty-database/no-implementation status is **superseded**. The
portable app now has optional confirmed feedback and the Worker/D1 service is
deployed. The user chose one build with app-level permission, default off; no
separate offline edition. See [Optional Chat Feedback](mimir-feedback.md) for
consent, network semantics, administrative separation and verified evidence.

### Android startup recovery — 2026-09-21

Android's previous automatic model loading and device discovery are **superseded**
following a reported Vulkan/memory freeze that prevented access to settings.
Android now restores chat/settings without issuing any native commands or preparing
weights. Loading requires an explicit button press. Default device is CPU, and
automatic context sizing becomes the profile minimum (currently 1,024 context /
512 reply); previously explicit limits and Vulkan choices are retained but never
loaded automatically. Imports and pre-load MixedLM changes also do not load.

CPU sessions set the existing `GGML_DISABLE_VULKAN` guard before first native
backend registration. No llama.cpp modification was needed. Because registration
is process-global, changing Android backend after initialization requires a
force-stop/reopen; both UI and native runtime enforce this. Reopening always
provides access to settings even if the previous saved device was Vulkan.

Validated 25 app tests, clean analysis, native CPU registration/restart guard in an
ARM64 emulator, and release APK installation/startup/settings. See
[validation evidence](../../../native/app/VALIDATION.md). This establishes recovery,
not physical GPU stability or a universal low-memory guarantee. Android 0.1.1+2
was built locally; the public 0.1.0 release has not been replaced by this work.

Run Flutter tests/analysis sequentially with Android packaging: concurrent Flutter
commands rewrote GeneratedPluginRegistrant during Gradle compilation and caused
a build failure; a subsequent sequential release build succeeded.

### Android 0.1.1 publication — 2026-09-21

The local-only Android 0.1.1 status above is **superseded**. At the user's request,
added `dfm-mimir-0.1.1-android-arm64.apk` and its SHA-256 sidecar to the existing
[bundled-weights release](https://github.com/schneiderkamplab/HRM-Text/releases/tag/dfm-mimir-v0.1.0).
GitHub reports both assets uploaded, with APK digest
`7b0b40088c9905748c4f059b87381e61dc5f589b729405a8cf29d59f7d06771c`, matching the
local artifact. Release notes recommend Android 0.1.1 and explain startup recovery,
verification limits and source commit `4f2f475`. Desktop assets and the release's
0.1.0 tag/public status remain unchanged; the older Android asset is retained.

### Bounded prompt and history compaction — 2026-09-21

The previous refusal to compact a single oversized turn or new prompt is
**superseded** in portable app source version 0.1.1+3. Shared
`native/mimir/include/mimir/compaction.h` uses a rolling reducer for both: pack whole
user/assistant pairs, split oversized source at UTF-8/nearby whitespace boundaries,
and include previous notes in each bounded request. Exact template/tokenizer counts
include the system message and reserved summary/reply output. Chunk sizing also
bounds temporary tokenizer input; every pass consumes source bytes. Periodic
compaction starts above 90% occupancy and targets 50%, consuming further recent
pairs when needed instead of stopping as soon as the request barely fits.

The portable app preserves original message content and stores an optional
`compactedContent` alongside a successfully answered user prompt. Only enabled chat
compaction uses this metadata, including context counts; API completions and disabled
compaction use originals. Visible prompt summaries stream and remain inspectable
under the original message. Cancellation/errors commit neither shortened prompts nor
partial history summaries. The Apple bridge consumes the shared effective prompt;
its separate SwiftUI persistence/UI has not acquired this new metadata display.

Early real-model testing found factual drift when replacing an entire request with
notes (Odense became Asgård). Prompt compaction now retains the original opening and
ending when space permits; the same Danish fixture answered Odense correctly with
exact PrefixLM and MixedLM. This is limited evidence, not a fidelity guarantee.
System instructions are never compressed. Insufficient fixed overhead produces an
explicit error; arbitrarily large inputs require multiple passes and can be slow.

See [app validation](../../../native/app/VALIDATION.md) for planner/sanitizer, model,
and UI tests. The Linux/Windows package workflow now includes the deterministic
compaction planner suite. Public release assets have not yet been refreshed for
this compaction feature; the previously uploaded Android 0.1.1+2 is the startup fix.

The user subsequently requested at least 50% free context: this **supersedes** the
initial 75%-occupancy target. Compaction now aims for at most 50% occupancy,
including reply reservation. It consumes all eligible turns if needed; when fixed
system/current-prompt/reply costs prevent reaching that target, a fitting request
may still proceed. The new prompt is shortened only when required to fit.

Windows CI exposed a pending-save cleanup race in the Android settings widget
test introduced with startup recovery. The widget test now disables disk persistence (already covered in ordinary async
tests) and shuts down the store before cleanup. Real I/O must not depend on the
widget test fake clock or an arbitrary delay.

### Complete 0.1.1 preview refresh — 2026-09-21

The earlier unpublished-compaction status is **superseded**. At the user's request,
refreshed the [existing bundled-weights release](https://github.com/schneiderkamplab/HRM-Text/releases/tag/dfm-mimir-v0.1.0)
as **DFM Mimir 0.1.1 — bundled weights**. All four recommended downloads now use
0.1.1 (build 3): macOS ARM64 DMG, Android ARM64 APK, Linux x64 tar.gz and Windows
x64 ZIP. The Android startup-only 0.1.1+2 asset was replaced. Older 0.1.0 assets,
the existing URL/tag and public non-prerelease status are retained. Notes clearly
identify package source `1fa33a1`, chunked prompt/history compaction, the 50%
occupancy target, Android recovery and remaining hardware/signing limits.

[Linux/Windows CI 35562513915](https://github.com/schneiderkamplab/HRM-Text/actions/runs/35562513915)
succeeded for that source. Bundled the checked GGUF into both CI archives with
`bundle_model.py`, verified all manifest/file/model hashes and source provenance,
Linux executable permissions and Windows file version 0.1.1.3. These remain
CPU-only builds, not clean-host real-model/GPU qualification. macOS packaging
verified DMG integrity, signatures and bundled weights; the mounted DMG passed
real headless API generation, streaming, seeded sampling, concurrency, overflow,
disconnect recovery and shutdown. All packages passed the feedback bundle audit.
For Linux tar.gz, extract the non-model files before auditing: the audit CLI accepts
directories, ZIP and APK, not tar archives. Weights are verified independently.

GitHub reported all four packages and four checksum sidecars uploaded. Remote sizes
and SHA-256 digests matched their local files, including the replaced Android APK.

```text
18d49fbfdebd0e0a087a48b9050a66c9c01528fd5b8a1af4ef0d1218d3b06e68  dfm-mimir-0.1.1-macos-arm64.dmg
a9e8b972e722a92d9831ea639bbc5afe4ac380ff6a2b0260033c53f85db4e066  dfm-mimir-0.1.1-linux-x64.tar.gz
b5b02a90749dda760feb345cc5492f7860dc87f4d06dd5ff0e659f286ed90639  dfm-mimir-0.1.1-windows-x64.zip
271fc01df15953945a519c97e31831c2434e6287b97a71f9ebe9ccb1d2d328e3  dfm-mimir-0.1.1-android-arm64.apk

```

Local artifacts: `logs/packages/release-0.1.1/` (desktop) and
`logs/packages/compaction/` (Android). Evidence includes
`logs/package-0.1.1-macos.log`, `logs/release-0.1.1-packaged-api.log`,
`logs/release-0.1.1-{linux,windows}-verify.log`, and
`logs/release-0.1.1-checksums.txt`. No distributable iOS package was published.


## 2026-09-21: optional model library and public checkpoint inventory

The portable client now has a model selector with installed/imported history,
explicit selection, unselected-file removal, pinned HF downloads with progress,
SHA-256/size/GGUF checks and cancellation. Model-network permission is independent
of feedback consent and defaults off. Startup never fetches the catalog. Android
selection remains unloaded until the user explicitly starts the engine.

[Model inventory and maintainer workflow](../../../native/app/MODELS.md) documents
seven public HF repositories, current bundled Q4_K_M provenance, conversion needs
and model-specific catalog profiles. Catalog refresh from the repository branch
can add supported newer GGUFs without rebuilding the client. HF-discovered
repositories remain separate from catalog-approved download entries; names alone
cannot establish architecture/template compatibility. This is portable UI work;
the separate SwiftUI UI and headless CLI were not extended with a selector.

A real noctrex Q8_0 download passed its pinned hash and a Danish generation smoke
check on macOS Metal. Its rendered chat templates matched our qualified export
on four prompts, but token IDs matched only two: ` ø` and ` Hvad` examples differ.
Therefore these third-party catalog entries are explicitly experimental. Recommended
alternative precisions still need publication of our qualified GGUFs. This adds
concrete evidence to the earlier policy of using our own tokenizer-corrected exports.

Static analysis and 37 app tests pass; the ten new tests cover offline permission,
selector UI, discovery separation, valid download, hash/size/magic rejection,
mid-stream revocation, pinned metadata and persisted Android selection/removal.
The macOS release and iOS simulator builds pass. Download retries restart from zero; background
OS transfers are not implemented. See the linked document for full limitations.


### Official GGUF discovery extension, 2026-09-21

The earlier repository-only discovery policy above is **superseded** for
`danish-foundation-models`: catalog refresh now merges curated entries with all
GGUF files in official repositories whose names contain `mimir` case-insensitively.
It follows repository/file pagination and pins revision/size/LFS SHA-256. Curated
profiles take precedence for duplicates; auto-discovered models use an explicitly
unqualified profile and select with 1024 context/512 reply, automatic sizing off.
Unsupported shards and missing-integrity files remain visible with reasons.
Network consent is unchanged; startup stays offline. Independent source failures
preserve cached entries and report errors. The official namespace currently has
one matching repository and no GGUF files (live API check).

[Catalog update instructions](../../../native/app/MODELS.md#adding-models-without-rebuilding-the-app)
explain direct JSON edits/pushes and the no-edit path of uploading official GGUFs.

Validation: static analysis clean and all 41 app tests pass, including official
case-insensitive matching, nested file/repository pagination, pinned metadata,
curated precedence, partial-source failure recovery and unsupported-file listing.


Follow-up inspection of the public noctrex Q8_0 and bundled Q4_K_M GGUF headers
confirmed the tokenizer mismatch: public Q8_0 uses `gemma4` pre-tokenization with
zero byte-fallback token types, while the qualified export uses
`spm-bpe-mistral` with 256 byte-fallback tokens, matching the original checkpoint's
`fix_mistral_regex=true` configuration. This is independent of weight precision;
other public GGUF precisions have not been independently checked.


### Training tokenizer reference correction, 2026-09-21

**Supersedes the inference above that the public `gemma4` pre-tokenizer is wrong.**
The training path loads raw `tokenizer.json` using `tokenizers.Tokenizer.from_file`
and encodes templated prompts directly; training consumes the resulting stored
IDs. `fix_mistral_regex=true` is injected later by the HF exporter, so it is not
a training specification. Reproducing the training loader with the pinned HF
JSON (byte-identical to local `dfm67_1150k/tokenizer.json`) matches public noctrex
Q8_0 on 19/19 cases and our bundled Q4_K_M on 15/19. Thus noctrex's **pre-tokenization**
is the match to the local training pipeline. Other tokenizer/decoder metadata and
weight quality still require independent qualification; differing byte-token type
counts alone do not establish which complete conversion is correct.

[Full evidence](../../../native/mimir/training-tokenizer-audit.json) records the
cases and token IDs; [app model notes](../../../native/app/MODELS.md#training-reference-correction-2026-09-21)
record provenance limits and next steps. The historical external tokenizer path
and original production tokenized corpus are absent locally, so this is a pipeline
reproduction against the exported JSON, not a complete corpus audit. No model,
exporter behavior or release asset was replaced by this investigation.


### Corrected 4/8/16-bit artifacts prepared, 2026-09-21

[Corrected GGUF preparation](../../../native/mimir/CORRECTED-GGUFS.md) supersedes
the prior statement that regeneration was pending. Fresh BF16, Q8_0 and Q4_K_M
artifacts are in `logs/mimir-corrected`, with checksums, licenses and provenance.
The llama.cpp HRM converter now loads the raw training graph (commit `4122b9a81`);
other architectures retain their original tokenizer loader. Native HF reference
generators likewise use the direct graph. Each artifact passes 724 tokenizer/
decoding/template cases, 19 independent training-audit cases, and CPU/Metal
Danish/English chat smoke tests. BF16's 259 tensors are bit-identical to the prior
BF16 export. Full quality/backend/device requalification remains distinct from
these bounded checks. Existing app assets, release packages and HF repositories
have not been replaced; these files are prepared locally for subsequent publication.


### Official GGUF publication completed, 2026-09-21

The local-only status above is **superseded**: corrected BF16, Q8_0 and Q4_K_M
files are public at [DFM-Mimir-GGUF](https://huggingface.co/danish-foundation-models/DFM-Mimir-GGUF),
revision `4364aaa61279c187b7cd202375915ea962b79afb`. Anonymous HF model-info queries
verified all three sizes and LFS SHA-256 values. The single publication commit
includes the model card (HF metadata validation passed), license, checksums,
provenance and bounded validation results. The uploader used existing org-admin
credentials; no credentials were copied into the upload folder or app assets.

The app catalog now pins these three official files ahead of the retained third-party
entries, with model-specific profiles. Automatic discovery also finds this new
Mimir repository. [Publication record](../../../native/mimir/hf-gguf/publication.json)
retains revision and file hashes; [model card source](../../../native/mimir/hf-gguf/README.md)
is versioned in this repo. No preview application packages or bundled app asset
were rebuilt/replaced in this publication step.

Publication/catalog validation: static analysis clean and all 41 app tests pass
with the expanded six-entry curated catalog.


### Official-only model catalog policy, 2026-09-21

The previous retained-third-party and Mimir-only discovery policies are
**superseded**. Both curated catalog loading (embedded, remote and cached) and
HF discovery require owner `danish-foundation-models` and repository names
containing both `mimir` and `gguf`, case-insensitively. The embedded catalog now
contains only the three corrected official exports. Cached discovery listings
are filtered at startup, and direct downloads enforce the same repository rule.
Already installed models and manual imports remain usable; networking is still
optional. No app packages were rebuilt for this source/catalog change.

Validation: Flutter analysis clean; all 44 app tests pass, including repository
filtering, offline cache restoration and blocked direct downloads. OKF validation
still reports the two pre-existing benchmark-charts index/frontmatter errors.


### Explicit third-party repository selection, 2026-09-21

The official-only policy now has a user-controlled exception: Models accepts
additional public HF `owner/repository` IDs, persists them, and discovers GGUFs
from those exact repositories on explicit refresh. IDs need neither name keyword.
Automatic official discovery and remote curated catalogs retain their existing
restriction; a remote entry cannot grant itself permission. Cached entries and
download admission accept the user's saved exceptions. Removing an exception
removes its listings but preserves installed files. Adding an ID does not enable
networking. Discovered third-party artifacts retain checksum/revision checks,
split-file restrictions and conservative, unverified model profiles.
See [model library usage](../../../native/app/MODELS.md#user-specified-hugging-face-repositories-2026-09-21).

Validation: all 46 app tests pass and Flutter analysis is clean. Coverage includes
UI add/remove, offline persistence of IDs and cached models, invalid IDs,
case-insensitive deduplication, verified downloads, failed lookup fallback and
revoked download access. The two existing benchmark-charts OKF errors remain.


### 0.1.2 package preparation, 2026-09-21

Portable app source is 0.1.2+4. The bundled-model policy supersedes 0.1.1:
use corrected official Q4_K_M SHA-256
`8c811ca72589112f00306e8b3a23f83944751d13d3fce6dfdb39df8b31726e49`
from HF `danish-foundation-models/DFM-Mimir-GGUF` revision
`4364aaa61279c187b7cd202375915ea962b79afb`. Includes model selection,
official discovery and user-specified third-party repositories. Packaging and
publication verification are pending below.


0.1.2 validation completed locally and in
[Linux/Windows CI 35585590918](https://github.com/schneiderkamplab/HRM-Text/actions/runs/35585590918)
for source `33875dcdee09736c6e987dd5dc9d5ddc51333ec2`: all 46 app tests and
analysis passed; CI also passed native fallback/compaction tests. macOS ARM64,
Android ARM64 and iOS simulator builds passed. The mounted DMG passed image,
signature and corrected-model checks, plus real-model Metal/headless API tests
(normal/streaming, seeds, concurrency, overflow, disconnect recovery, shutdown).
Linux/Windows bundles have verified per-file/model hashes and source revisions;
Linux executable permissions and Windows 0.1.2.4 executable version were checked.
All four packages passed feedback audits; Android signature, ARM64 packaging and
16 KiB ZIP alignment passed. No physical Android Vulkan or Linux/Windows
clean-host real-model/GPU qualification is claimed. Packaging macOS requires an
absolute `--dart` path because server compilation changes its working directory.

Local artifacts: `logs/packages/release-0.1.2/`; evidence is in
`logs/release-0.1.2-{tests,analyze,packaged-api,archives-verify,package-audits}.log`.


### 0.1.2 publication completed, 2026-09-21

The pending-publication status above is **superseded**. All four bundled-weight
packages and SHA-256 sidecars are public in
[DFM Mimir 0.1.2](https://github.com/schneiderkamplab/HRM-Text/releases/tag/dfm-mimir-v0.1.2).
Tag `dfm-mimir-v0.1.2` resolves to package source
`33875dcdee09736c6e987dd5dc9d5ddc51333ec2`; the release is public, non-prerelease
and marked latest. GitHub asset sizes and SHA-256 digests matched all eight local
files. The earlier 0.1.0/0.1.1 downloads remain available in the previous release.

A laptop network/DNS interruption terminated the first Linux/Windows upload;
GitHub release uploads required restarting those whole files. The retry succeeded.
macOS/Android were briefly published first with explicit pending notes; final
notes now list all four completed downloads and validation evidence. Publication
verification is recorded in `logs/release-0.1.2-publication.log` and
`logs/release-0.1.2-checksums.txt`.

```text
cc7b659eb653eb85820d46e5c320cf2a5e430e3646b22ddfac84e7b5b668b9c1  dfm-mimir-0.1.2-macos-arm64.dmg
8f7980cbc4cdd4d8e58fc0eb32ad3659bf2ca2746fd82cea4dd7684ec2222378  dfm-mimir-0.1.2-android-arm64.apk
5c1b0cdb3bbc24d7c2c976d288fa3efcf29325e04859064578762d8702871098  dfm-mimir-0.1.2-linux-x64.tar.gz
85cd9b17651a6a9018976a6b475120ed626ca82d8f580bc334954c50477af744  dfm-mimir-0.1.2-windows-x64.zip
```


### Separate release history, 2026-09-21

The earlier combined 0.1.0/0.1.1 release layout is **superseded**. There are now
three separate public, non-prerelease releases, each containing only its own four
platform packages and four SHA-256 sidecars:

- [0.1.0](https://github.com/schneiderkamplab/HRM-Text/releases/tag/dfm-mimir-v0.1.0):
  existing tag `7d56a56c5e5226d4db0ea961ef7fd2cd590395cf` retained; original
  0.1.0 title/notes restored and all 0.1.0 asset sizes/digests unchanged.
- [0.1.1](https://github.com/schneiderkamplab/HRM-Text/releases/tag/dfm-mimir-v0.1.1):
  new tag at recorded package source `1fa33a1c5656d1b288a13a04a1b1ee77f54833ff`.
  All eight assets were copied and verified against their original GitHub
  sizes/SHA-256 digests before removing them from the 0.1.0 release. No rebuild.
- [0.1.2](https://github.com/schneiderkamplab/HRM-Text/releases/tag/dfm-mimir-v0.1.2):
  tag `33875dcdee09736c6e987dd5dc9d5ddc51333ec2` retained; remains latest.

0.1.1 download URLs now use the 0.1.1 tag; its old asset URLs under the 0.1.0 tag
no longer apply. Historical combined-release links elsewhere on this page describe
the previous arrangement. Verification/backup records:
`logs/release-separation/{before,verified}.json` and `finish.log`.


### Self-contained release descriptions, 2026-09-21

Release descriptions must explain the shipped app without relying on earlier
release notes. The 0.1.2 description is now maintained in
[the versioned release document](../../../native/app/releases/0.1.2.md), with
[maintenance guidance](../../../native/app/releases/README.md). It includes
installation/backend/signing limits; model selection and network consent;
context/compaction/MixedLM; desktop API settings, address/authentication, requests
and limitations; per-platform headless commands; feedback consent/publication
choices; and preserved provenance, validation and checksums. Examples/UI labels
were checked against the shipped source and API guide. Publishing this description
does not change any package, checksum, tag or release status.


### Release-description policy for all versions, 2026-09-21

The self-contained description requirement applies to every future patch, minor
and major release, including 0.1.3+, 0.2.x and later. The
[release policy](../../../native/app/releases/README.md),
[coverage template](../../../native/app/releases/TEMPLATE.md), and
[packaging plan](../../../native/app/PACKAGING-PLAN.md#release-descriptions-for-every-version)
make this a preparation/publishing requirement, not a promise to publish future
versions automatically. Maintain each exact body in `native/app/releases/VERSION.md`
and verify it against that release's source and artifacts, including unchanged
features and restrictions.

[0.1.1's complete description](../../../native/app/releases/0.1.1.md) now covers
installation, local GGUF/profile import, context/compaction/MixedLM, API setup and
examples, headless commands, feedback/privacy and original validation/checksums.
It was checked against source `1fa33a1`; it does not claim the later HF catalog or
corrected bundled tokenizer. Updating the GitHub description preserves release
assets, checksums, tag target and visibility.

## MixedLM default and reply sampling — 2026-09-22

**Supersedes the September 20 off-by-default Flutter setting:** MixedLM is now
on for new settings and archives without a saved mode; explicit saved choices
remain unchanged. Native library/API defaults remain exact PrefixLM.

Flutter settings expose temperature 0–2 (default 0) and repetition penalty 1–2
(default 1, disabled). They persist, validate on restore, and are forwarded per
reply without model reload. The native sampler applies the repetition penalty
before temperature/selection, using the last 64 generated tokens of the current
reply and resetting each reply. Prompts and prior turns are not seeded into the
penalty history. Compaction continues using deterministic defaults; API request
sampling remains independent of UI preferences.

Validation: Flutter analysis and all 48 tests pass. A fresh CPU build of
`MimirRuntime` and `mimir-text-tests` passed 78 text checks with the bundled
corrected Q4_K_M model, including seeded temperature/penalty replay and invalid
penalty rejection without history mutation. An asynchronous C-ABI smoke check
confirmed non-default sampling, subsequent MixedLM prefix reuse, and invalid
penalty rejection. Logs are `logs/sampling-native-tests.log` and
`logs/sampling-ffi-tests.log`. Packaged applications have not been rebuilt for
this change.

## Basic Markdown rendering — 2026-09-22

Flutter assistant replies, streamed replies, visible compaction summaries and
shortened-prompt previews use a shared selectable Markdown renderer. User text
stays literal, and transcript persistence/sharing remains unchanged. The pinned
`flutter_markdown_plus` 1.0.12 dependency supplies rendering; see its
[widget documentation](https://pub.dev/packages/flutter_markdown_plus).
Image builders always return text placeholders (no remote fetch or local-file
read). Links show an inspect/copy dialog without launching anything.

Validation: Flutter analysis and all 51 tests pass. New widget coverage checks
basic blocks at 320-pixel width, literal user messages, incomplete streaming
markup, image placeholders and link inspection. Release packages are not yet
rebuilt.

## Stronger default repetition penalty — 2026-09-22

**Supersedes the 1.0 UI default above:** the Flutter default is now 1.1. Archives
without the sampling-defaults marker upgrade a stored 1.0 once; other custom
values remain unchanged. Saving records the marker so a subsequent explicit
choice of 1.0 remains disabled after reopening. Native/API defaults and the
64-generated-token window are unchanged. This is a tuning choice prompted by
observed repetitions, not evidence of eliminating repetition in every reply.

## 0.1.3 packaging — 2026-09-22

Release source `2137f438786b79aeca16b70576d7c753d3ab0389` is version 0.1.3+5.
All four packages include the same official corrected Q4_K_M as 0.1.2. Features:
MixedLM default for new settings, persisted temperature and repetition penalty
(default 1.1 with one-time old-default upgrade), and offline Markdown rendering.
[Self-contained release notes](../../../native/app/releases/0.1.3.md) include API,
headless use, model selection, privacy, platform limits and package checksums.

[CI 35707335507](https://github.com/schneiderkamplab/HRM-Text/actions/runs/35707335507)
passed on Linux and Windows: 52 tests, analysis, native fallback/compaction and
packaged CPU backend probes. macOS and Android ARM64 builds passed locally.
The mounted DMG passed real-model Metal/headless API tests (ordinary/streaming,
seeded sampling, concurrent requests, overflow rejection, disconnect recovery,
shutdown). All model/file hashes and package source revisions were verified;
Windows executable version is 0.1.3.5; Linux executable bits were checked.
Android version 0.1.3/build 5, signature, ABI and ZIP alignment passed. All four
feedback audits passed. Physical Android Vulkan and clean-host Linux/Windows
real-model inference remain unqualified.

Artifacts: `logs/packages/release-0.1.3/`; evidence:
`logs/release-0.1.3-{ci,packaged-api,android-validation,linux-verify,windows-verify}.log`.
The GitHub release is still a draft while uploads complete.

### 0.1.3 publication completed

The draft status above is **superseded**: [DFM Mimir 0.1.3](https://github.com/schneiderkamplab/HRM-Text/releases/tag/dfm-mimir-v0.1.3)
was published on 2026-09-22 at 09:15:26 UTC as a public, non-prerelease, Latest
release. Tag `dfm-mimir-v0.1.3` resolves to package source `2137f43`. All four
packages and four checksum sidecars have matching GitHub SHA-256 digests and
sizes; the published notes match `native/app/releases/0.1.3.md` exactly.
Verification is recorded in `logs/release-0.1.3-publication.log`. Previous releases
and tags remain intact.

## 0.1.4 preparation: UCloud training credit — 2026-09-22

Unreleased source is now 0.1.4+6. The Flutter welcome screen pairs the DFM logo
with the user-supplied UCloud logo and the exact caption “Trained on SDU UCloud”.
The logo pair wraps into a vertical layout on narrow screens and uses a white
panel for contrast in either theme. The original SVG is tracked under
`native/app/branding/`; a 1200-pixel PNG with IBM Plex Sans rendered into it is
bundled offline. See [branding provenance](../../../native/app/branding/README.md).
No 0.1.4 release, tag or distribution upload is authorized yet; 0.1.3 remains
Latest.

Validation: the raster export was visually checked; Flutter analysis and all
52 existing tests pass, and OKF validation has no errors or warnings.

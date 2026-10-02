---
type: Implementation Report
title: DFM Mimir v1.5 GGUF exports
description: Source revision, conversion, validation and publication of the official v1.5 GGUFs.
tags: [mimir, gguf, quantization, tokenizer, publication]
status: draft
last_updated: 2026-10-02
confidence: high
---
# DFM Mimir v1.5 GGUFs

User-authorized destination: `danish-foundation-models/DFM-Mimir-v1.5-GGUF`,
following the original `DFM-Mimir-GGUF` naming convention. The three variants
are BF16, Q8_0 and Q4_K_M. Existing model repositories and app bundles are unchanged.

Source: `danish-foundation-models/DFM-Mimir-v1.5`, pinned revision
`cc57cebadf375947ced5ccd3317d9da6bf8f9677`. Converter: llama.cpp
`4122b9a814d5bd4f48f454367419f75c05ee5215`. The export wrapper gained optional
`--model-name` so GGUFs carry `DFM Mimir v1.5`, not the temporary source-directory
name. All 259 tensors, 4096-token context and PrefixLM metadata are retained.
Both quantizations originate directly from BF16.

## Tokenizer and template

The raw tokenizer SHA-256 is
`12bac982b793c44b03d52a250a9f0d0b666813da566b910c24a6da0695fd11e6`,
identical to original Mimir. Both models use Gemma 4 tokenization/template format.
The only semantic template change is a new `tool_body is mapping` branch that
renders object-valued tool-response content; the other difference is a final
newline. The source template is embedded byte-for-byte. The converter loads
`tokenizer.json` directly, avoiding the HF configuration's regex rewrite, uses
`tokenizer.ggml.pre=gemma4` and preserves 256 byte-fallback token types.

## Validation

Each of the three files passes 724 tokenizer/decoder/template comparisons,
19 independent training-tokenizer audit cases, and CPU plus Metal generation
checks. With the embedded chat template, 1024-token context and 32-token reply
budget, every precision/backend answered the Danish capital question with
`Danmarks hovedstad hedder København.` and the arithmetic question with `4`.
Names, template bytes, tensor counts, context metadata and hashes were checked.
This is bounded artifact validation, not full benchmarks or additional platform
qualification. The new mapping branch itself is retained; app tool transcripts
currently use string content.

[Model card](../../../native/mimir/hf-gguf-v1.5/README.md) and
[validation record](../../../native/mimir/hf-gguf-v1.5/validation.json) are tracked.
Local artifacts and full per-case logs: `logs/mimir-v1.5/`; final GGUFs:
`logs/mimir-v1.5/exports/`. The earlier files directly under `logs/mimir-v1.5/`
have the generic display name `Source` and are superseded by the final exports.

## Reproduce

Using the established `logs/prefixlm-comparison/venv/bin/python` environment:

```sh
hf download danish-foundation-models/DFM-Mimir-v1.5 \
  --revision cc57cebadf375947ced5ccd3317d9da6bf8f9677 \
  --local-dir logs/mimir-v1.5/source
python native/mimir/export.py --model logs/mimir-v1.5/source \
  --model-name 'DFM Mimir v1.5' --outtype bf16 \
  --output logs/mimir-v1.5/exports/dfm-mimir-v1.5-bf16.gguf
logs/mimir-engine/build/bin/llama-quantize \
  logs/mimir-v1.5/exports/dfm-mimir-v1.5-bf16.gguf \
  logs/mimir-v1.5/exports/dfm-mimir-v1.5-q8_0.gguf Q8_0 8
logs/mimir-engine/build/bin/llama-quantize \
  logs/mimir-v1.5/exports/dfm-mimir-v1.5-bf16.gguf \
  logs/mimir-v1.5/exports/dfm-mimir-v1.5-q4_k_m.gguf Q4_K_M 8
python native/mimir/tests/text_reference.py --model logs/mimir-v1.5/source \
  --output logs/mimir-v1.5/text-reference.json
# Run text_parity.py for each precision, then training_gguf.py for all three;
# see native/mimir/CORRECTED-GGUFS.md for the established test arguments.
```

The HF upload contains only the three final GGUFs, model card, source license,
`SHA256SUMS`, `provenance.json` and `validation.json`. The provenance records source
file hashes, converter hashes and quantizer identity. Public size/SHA verification
is required after upload, before claiming publication complete.

Upload note: the default Xet transfer was slow on this host. Restarting with
`HF_XET_HIGH_PERFORMANCE=1` increased observed outgoing traffic from roughly
0.5–1 MB/s to several MB/s. This is Hugging Face's documented high-throughput
setting; observed bytes include protocol overhead and are not a percent-complete
measure because Xet deduplicates content.

## Public upload and 0.1.5 packaging

Publication completed at revision `78f92c5f126ae7ad05e98fc210d5c9c0eec3da16`.
Anonymous size/SHA checks and HTTP 206 GGUF-header downloads passed for all three
files; official Mimir+GGUF discovery finds the repository. See the
[publication record](../../../native/mimir/hf-gguf-v1.5/publication.json).

The user requested bundling v1.5 Q4_K_M, then explicitly chose **0.1.5** rather
than replacing 0.1.4. Prepare 0.1.5 build 7, preserving every 0.1.4 release asset,
body and tag. Curated catalog includes the three new files and retains originals;
the remote curated-catalog URL follows the maintained `main` branch.

0.1.5 upgrade regression checks retain cached downloads/discovery while adding
new shipped catalog entries, and discard stale bundled-file inventory after an
app update. The bundled file is registered only after hashing its current bytes.
All 67 Flutter tests and analysis pass after these changes.

Build-tool caution: run Flutter tests and platform builds sequentially within
the same checkout. A concurrent test run regenerated Android's plugin registrant
with `integration_test` during a release build and caused a Java compile error.
Repeating the final platform builds sequentially passed.

The final 0.1.5 macOS and Android release builds and unsigned iOS archive pass;
iOS/Android report build 7. Native Metal tests with the new Q4_K_M passed tool
continuation, cache lifecycle, streaming, compaction, cancellation and shutdown.
Mounted DMG API smoke passes. Bundled model hashes and private-key scans pass.
The 0.1.4 GitHub release body, target and asset IDs/sizes/digests were compared
against a saved snapshot and remain unchanged.

All four 0.1.5 packages are verified. [CI 35864441924](https://github.com/schneiderkamplab/HRM-Text/actions/runs/35864441924)
passed 67 tests, analysis, native policy/compaction tests and CPU backend probes
on Linux/Windows. Package source is `3e36860ef4d918591c64e0d789f104df5047eba4`.
Artifacts: `logs/packages/release-0.1.5/`; test/audit evidence:
`logs/release-0.1.5-*`. Self-contained notes and checksums are in
[0.1.5.md](../../../native/app/releases/0.1.5.md). Publication awaits uploads.

## 0.1.5 publication complete

Superseding the pending-upload status above, [DFM Mimir 0.1.5](https://github.com/schneiderkamplab/HRM-Text/releases/tag/dfm-mimir-v0.1.5)
was published as Latest/non-prerelease on 2026-09-23 at 13:23:17 UTC. Tag
`dfm-mimir-v0.1.5` resolves to `b5fbe0d13c0c6a3046702430392bb557cd357c74`.
All four packages and four checksum sidecars match GitHub's sizes/SHA-256 hashes;
the published body matches the tracked release notes. The 0.1.4 tag still points
to `f5edf5184d96731168aea31c07d42d144da85f1d`, and its body and all asset
IDs/sizes/digests/timestamps are unchanged from the pre-work snapshot.
Publication evidence: `logs/release-0.1.5-publication.json` and
`logs/release-0.1.5-remote-verified.json`. iOS remains an unsigned local archive;
no TestFlight upload was made.

## TestFlight distribution preparation — 2026-09-23

Supersedes the earlier absence of Apple signing credentials: the user selected
his paid team in Xcode, and Apple Development/Distribution certificates now
exist locally. A fresh unsigned 0.1.5 (8) archive passes build validation and
contains the expected Q4_K_M hash and updated Danish/English default prompt.
Distribution export can sign this archive using `app-store-connect` with
`-allowProvisioningUpdates`, without registering a physical device; the owner
must handle any macOS keychain authorization prompt. At this checkpoint export
is awaiting that authorization, and App Store Connect browser sign-in is also
pending. No upload is confirmed. See the updated
[TestFlight handoff](../../../native/app/TESTFLIGHT.md) for commands and evidence.

The distribution export subsequently succeeded. Its embedded App Store profile
has no device list and `get-task-allow=false`. App Store Connect now contains
**DFM Mimir**, app ID **6815375537**, bundle `dk.sdu.mimir`, SKU `dfm-mimir-ios`,
primary language English (U.K.). Created the `Mimir internal testing` group with
manual build distribution. Upload of 0.1.5 (8) has started; acceptance/processing
must still be checked. The four focused prompt/search tests pass.

### Initial upload validation failure and framework correction

Apple rejected the first build-8 upload because `MimirRuntime.framework` lacked
`CFBundleShortVersionString` and `CFBundleVersion`, and warned that its dSYM was
missing. These are native framework packaging issues, not device provisioning.
The framework now declares its independent runtime version (0.1.0, build 1), and
Apple native builds generate and package matching debug symbols in the
XCFramework. Preserve the release optimization flags when enabling symbols.
A corrected archive/upload must be validated before claiming TestFlight readiness.

Corrected build 9 contains both framework version fields. The native build
packages dSYMs in the XCFramework, but current CocoaPods does not stage that dSYM
in the archive: explicitly copy the matching device dSYM before export, as shown
in the handoff. Verified archive binary/dSYM UUID
`4510C22F-875A-3FEB-8437-94DAE43BE548`. The corrected upload is in progress in
`logs/testflight-0.1.5-build9-upload.log`.

### Build 9 upload succeeded

At **2026-09-23 19:38:29 UTC (21:38 Copenhagen)**, Xcode confirmed upload success
for **0.1.5 (9)** and reported the package processing at Apple. This supersedes
the pending/rejected-upload status above. The corrected upload has no missing
framework-version errors or missing-symbol warning. Processing and assignment to
the internal group remain separate steps; an uploaded build is not necessarily
installable yet. Evidence: `logs/testflight-0.1.5-build9-upload.log`.

App Store Connect subsequently confirmed **0.1.5 (9): Processing** in Build
Uploads. The internal group contains the account holder; no build is assigned
while processing is pending. Beta description, feedback email and test notes
were saved. External testing remains possible (normal App Store Connect upload,
not Internal Only), but no external review/public link has been requested or
submitted. Next: inspect processing result, resolve any compliance questions,
then add build 9 to the internal group. Repository changes are pushed on main.

Processing has now completed for 0.1.5 (9). TestFlight reports **Missing
Compliance**: the App Encryption Documentation questionnaire must be completed
before testing. The questionnaire was opened, but no encryption classification
was selected or submitted. The build is not yet assigned/installable.

Encryption questionnaire investigation: the app uses `dart:io HttpClient` for
search, feedback and model downloads. The archived Flutter binary contains
BoringSSL source-path strings, confirming bundled crypto beyond Apple's OS.
For the algorithm-type question, the supported answer is **standard algorithms
instead of/in addition to Apple OS encryption**, not OS-only/none. This technical
classification does not by itself determine documentation exemptions; follow
[Apple's requirements](https://developer.apple.com/help/app-store-connect/reference/app-information/export-compliance-documentation-for-encryption)
for subsequent questions. No compliance answer has been submitted by the agent.

### Internal TestFlight available

The owner completed the encryption questionnaire. Apple then showed build 9 as
Ready to Submit (no Missing Compliance). Assigned **0.1.5 (9)** to **Mimir internal
testing**; verified **1 Tester / 1 Build** and account-holder status **Invited**
at 22:08 Copenhagen on 2026-09-23. The owner can accept the invitation in
TestFlight on iPhone/iPad. External beta review has not been submitted.

### External beta review preparation

The owner requested Beta App Review. Created the external group **Mimir beta
testing** and selected build 9 in its submission wizard. Apple requires review
contact details; name/email are filled and sign-in-required is unchecked because
offline chat needs no account. Submission is pending the owner's contact phone
number (requested with country code). No review submission is confirmed yet.

On 2026-09-24 the external review wizard showed a generic save failure despite
populated contact fields. Retrying advanced to What to Test, but Submit for
Review returned to the error. Navigating to Test Information redirected to
Apple sign-in, indicating the session had expired; review submission is **not
confirmed**. The user must sign in again before checking saved contact details
and retrying. Do not interpret advancing the wizard as successful persistence.

### External Beta App Review submitted — 2026-09-24

Supersedes the pending/failed submission notes: after signing in again, saved
review contact details on the standalone Test Information page and reopened the
external-group wizard in a fresh browser tab. Submitted **0.1.5 (9)** to **Mimir
beta testing**, group `69a730de-ca03-41b4-9e7b-858c51f65cb0`. Verified **Waiting for
Review**, with 1 build and 0 external testers. No sign-in is required for offline
chat. Automatically notify testers remains unchecked; no public link is enabled.
Earlier English (U.K.) metadata save errors occurred in the old tab, but the
fresh submission was accepted. Do not equate UI wizard advancement with success;
the verified Waiting for Review status is the authoritative result.

Test Information save errors in the original tab were stale: a fresh tab loaded
the saved beta description and feedback email without errors. Copied the user's
previously unsaved `Apache 2.0` license-field entry into the fresh form; Apple
reported **Saved**, and the entry remained visible after reload. Use a fresh
page after session renewal rather than retrying the old failed form. This did
not require cancelling or resubmitting Beta App Review.

Follow-up verified actual localized-field persistence: edited the beta description
in the fresh tab, received Saved, and read the revised wording in an independent
new page. Restored the original wording and saved successfully. The original
tab still displayed errors and old text; closed it and the verification tab,
leaving only the working Test Information tab. Earlier guidance to merely use a
fresh tab was insufficient because the user continued to see the original tab.

## DFM Mimir app 0.1.6 release (2026-09-24)

**Superseded 2026-09-25:** withdrawn and consolidated into 0.1.5 build 10 below.

Published `dfm-mimir-v0.1.6` as the public Latest release at 20:17 UTC, with
macOS ARM64 DMG, Android ARM64 APK, Linux x64 tar.gz and Windows x64 ZIP plus
checksum sidecars. App version/build is 0.1.6+10; package source is
`942019f4bb67d05912d76f64c853014cdfd5bac2`. Model remains the official v1.5
Q4_K_M with the hash above. Earlier releases and TestFlight 0.1.5 (9) are unchanged.

Release notes are self-contained in `native/app/releases/0.1.6.md`. Local checks
and Linux/Windows CI run `36052181995` passed 72 Flutter tests and static analysis.
CI also passed native policy/compaction tests and CPU package checks. Model
hashes, desktop per-file manifests/source provenance, secret scans, APK
signature/version/ARM64/16 KiB alignment and DMG integrity/signature checks passed.
Mounted-DMG headless API smoke checks passed, including streaming, sampling,
concurrency, overflow and disconnect recovery. All four GitHub asset digests
match local package hashes. Platform signing/GPU qualification limits remain as
described in the release notes. Evidence: `logs/release-0.1.6-*`.

Packaging note: `package_macos.py --dart` needs an absolute compiler path because
server compilation changes working directory. Draft releases can return 404
from GitHub's release-by-tag API; resolve the draft ID through the releases list
and verify asset digests using release-by-ID before publishing.

## Beta App Review approved (2026-09-25)

App Store Connect now shows **Approved** for **0.1.5 (9)**, superseding the
Waiting for Review status above. The build is assigned to Mimir internal testing
and Mimir beta testing. A **Notify Testers** button is available; this status
check did not send notifications or add testers. The page reports 1 invitation,
1 installation, 4 sessions in the last 7 days, no reported crashes/feedback,
and expiry in 89 days. GitHub 0.1.6 is separate and has not replaced this build.

## Public TestFlight invitation (2026-09-25)

Created https://testflight.apple.com/join/9sP7a8Ny for Mimir beta testing, open
to anyone with no custom tester limit or device criteria. Activated the approved
0.1.5 (9) build through Notify Testers; verified status **Testing**. The external
group had 0 testers when activated. This supersedes the earlier no-public-link
and Approved-but-not-activated status. Compared with this TestFlight build,
0.1.6 adds text scaling and settings organization/conditional controls; both
already include the Danish/English identity prompt and the same v1.5 Q4 model.

## TestFlight 0.1.5 (10): GitHub 0.1.6 UI update (2026-09-25)

Built source `7aa98e724d1d7df25e61cfbd05b93ea6ea934fbe` using
`flutter build ipa --release --no-codesign --build-name 0.1.5 --build-number 10`.
This intentionally maps GitHub 0.1.6 UI changes to the existing TestFlight 0.1.5
version; tracked pubspec remains 0.1.6+10. Model and inference behavior are unchanged.
Staged matching MimirRuntime dSYM; archive version, identifier, framework metadata,
model hash and credential audits passed. Xcode export/upload succeeded and App
Store Connect shows Processing. Build 9 remains Testing. Evidence:
`logs/testflight-0.1.5-build10{,-audit,-upload}.log`.
Group assignment and external availability are still pending Apple processing.

## GitHub release consolidation: 0.1.5 build 10 (2026-09-25)

At the owner's explicit request, replaced all four GitHub 0.1.5 packages with
**0.1.5+10** from source `9e346f4e9f705b4fd5d376f3ade40a16e9efa9b5`.
The 0.1.5 tag was moved from `b5fbe0d13c0c6a3046702430392bb557cd357c74`
to that source commit. Deleted the separate 0.1.6 release and remote tag after
verifying all eight replacement assets (four packages and checksum sidecars).
0.1.5 is Latest. This supersedes the separate-version mapping above; the already
uploaded TestFlight 0.1.5 (10) has the same UI changes and is unaffected.

Linux/Windows CI `36094936056` passed, including 72 Flutter tests, analysis,
native fallback/compaction checks and portable CPU builds. Local macOS/Android
builds passed version, model hash, credential, signature and platform package
checks; desktop manifests/source provenance passed. All four GitHub package
digests matched local SHA-256 values. Bundled v1.5 Q4_K_M weights are unchanged.
Current notes/checksums: `native/app/releases/0.1.5.md`. Evidence is under
`logs/release-0.1.5-build10-*`; packages are in
`logs/packages/release-0.1.5-build10/`. Signing and GPU qualification limits
remain documented in the release notes. No other release was changed.

### Build 10 processing complete (2026-09-25)

A refreshed App Store Connect page confirms 0.1.5 (10) upload status Complete
and build status **Missing Compliance**, superseding Processing above. Build UUID
is `76c8d87c-60ba-4e03-ba48-f647acff6be9`. No testing groups are assigned yet.
The export-compliance questionnaire must be completed before distribution;
build 9 remains Testing in both internal and external groups.

### Build 10 available to both testing groups (2026-09-25)

Supersedes Missing Compliance/Processing: after the owner completed compliance,
assigned 0.1.5 (10) to Mimir internal testing and Mimir beta testing. Entered
build-specific UI/accessibility test notes and submitted the external-testing
wizard with automatic tester notification enabled. A fresh page load confirms
**Testing** and both groups for build 10; no review wait is currently shown.
The existing public invitation remains https://testflight.apple.com/join/9sP7a8Ny.
Build 9 remains Testing as well.

## SDU store distribution blocked by account agreement (2026-10-01)

SDU membership for petersk@sdu.dk is now verified, superseding earlier missing
team observations. The owner authorized new iOS and macOS app distribution under
SDU rather than transferring the personal TestFlight-only app. Apple requires an
App Store release for transfer eligibility. SDU provider ID is
`69a6de74-0d84-47e3-e053-5b8c7c11a4d1` (not the signing Team ID).

Attempting New App under SDU is blocked by an Agreement Update dialog requiring
the SDU Account Holder to accept the updated Developer Program License Agreement.
No app record was created, no build uploaded, and personal TestFlight is unchanged.
Resume checklist and macOS packaging caveats: `native/app/SDU-STORE.md`.
Evidence: `logs/sdu-store/agreement-blocker.png`.

## SDU preflight build preparation (2026-10-01)

Both unsigned 0.1.5 (11) archives built successfully for proposed new identifier
`dk.sdu.dfm.mimir`: iOS 17+ (iPhone/iPad) and macOS 14+ (arm64). New
`native/app/tool/archive_apple.py` accepts signing-team/bundle overrides, checks
model SHA, framework metadata, matching native dSYMs, bundle contents, architecture
and (when signed) team/sandbox entitlements. No uploads occur automatically.
Existing default identities and public release artifacts remain unchanged.

Flutter analyze and all 72 tests passed. Exact local secret scans found neither
Jina nor test Mimir keys in either app. Five dependency privacy manifests exist
in each archive; this is not a completed required-reason API/privacy declaration
audit. Local artifacts and command evidence are under `logs/sdu-store/`.

Store listing, reviewer notes, support draft and technical privacy inventory are
in `native/app/store/`, linked from `native/app/SDU-STORE.md`. Remaining gates:
Account Holder agreement, actual SDU signing Team ID/registered identifier, final
privacy/support URLs and in-app policy link, institutional controller/retention
approval, privacy/age/export/trader declarations, screenshots and signed device
qualification. Feedback currently has manual deletion with no automatic expiry.

Mac ad-hoc QA launch succeeded at process level, but Computer Use inspection timed
out; no chat UI pass or screenshot success is claimed. Simulator UI capture also
remains incomplete. Preserve personal TestFlight while preparing the new app.

### Direct-download SDU DMG (2026-10-01)

User also wants SDU-signed direct downloads that avoid Gatekeeper's Open Anyway
exception. Existing package_macos.py is ad-hoc only. Keychain inspection found no
Developer ID Application identity; personal Apple Distribution is unsuitable for
notarization. SDU must arrange Developer ID signing access. Required packaging
extension: inside-out signing of app/frameworks/CLI with Hardened Runtime and
timestamps, notarization, stapling and quarantined-download validation. This is
independent of App Store review. Details are in native/app/SDU-STORE.md.

### Agreement cleared; identifier registration denied (2026-10-02)

Supersedes the agreement blocker above: SDU membership displays Program License
Agreement accepted October 1, and App Store Connect now opens New App without
agreement warnings. Verified SDU signing Team ID **46HSA3LZ7H**, user role Developer.
New App preparation uses iOS+macOS, DFM Mimir, English (U.K.), SKU dfm-mimir-sdu.
No matching Mimir bundle ID exists. Registration under SDU explicitly returns
“You are not allowed to perform this operation”; an SDU admin must register
`dk.sdu.dfm.mimir` or enable registration access. No app record was created and no
build uploaded. Evidence: logs/sdu-store/identifier-permission-blocker.png.

### Identifier registered; app name conflict (2026-10-02, later retry)

Supersedes identifier-registration denial above. Registered explicit SDU App ID
`dk.sdu.dfm.mimir` (DFM Mimir), team 46HSA3LZ7H, with default capabilities.
App Store creation with both iOS/macOS now reaches validation but rejects
“DFM Mimir” as already in use. The personal TestFlight record has that name and
is the likely collision; Apple's error does not identify the conflicting owner.
No SDU store record created or build uploaded. Naming decision pending; do not
delete personal TestFlight. See SDU-STORE.md and logs/sdu-store/ screenshots.

### SDU app record created (2026-10-02)

Supersedes the app-name conflict. User authorized personal listing rename to
DFM Mimir Preview; English (U.K.) name saved for app 6815375537 without deleting
records or expiring builds. SDU DFM Mimir creation then succeeded: Apple ID
6818524811, dk.sdu.dfm.mimir, SKU dfm-mimir-sdu, iOS+macOS, English (U.K.),
Limited Access. Both platform records show 1.0 Prepare for Submission; adjust
version to match the upload plan. No SDU builds uploaded/submitted yet. Evidence
screenshots and remaining steps are recorded in native/app/SDU-STORE.md.

### SDU signed archives and upload blocker (2026-10-02)

Supersedes the initial listing version and unsigned-only preparation above.
iOS/macOS drafts now save version 0.1.5, descriptions/keywords, reviewer notes,
no required sign-in and manual release. Signed 0.1.5 (11) archives pass team,
architecture/model/native-symbol/bundle checks; exact local secret scans pass.
Mac archiving needs explicit Apple Development identity to avoid ad-hoc signing.
Its verified signature TeamIdentifier is authoritative when the optional Mac team
entitlement is absent; conflicting entitlements remain errors.

iOS export/upload fails at account access: Xcode saved credentials invalid,
missing Xcode-Username, SDU App Store Connect access required. User asked to refresh
Xcode Accounts. No builds uploaded, no review submitted. Two genuine Mac screenshot
drafts exist, but capture overlays need cleanup; chooser timeout prevented upload.
Device Hub UI timeout blocks current simulator capture. See `native/app/SDU-STORE.md`
for exact archive paths, audit scope and remaining privacy/qualification gates.

### SDU uploads accepted (2026-10-02, account refreshed)

Supersedes the Xcode credential/upload blocker above. After user refreshed Xcode
login, both 0.1.5 (11) distribution uploads succeeded to SDU app 6818524811:
iOS at 15:46:41 CEST and macOS at 15:47:12 CEST. Both xcodebuild commands exit 0
with `EXPORT SUCCEEDED` and Apple reports package processing. Not yet proof of
completed processing or tester availability; no App Review/public release.
Logs and remaining screenshot/privacy gates: `native/app/SDU-STORE.md`.

## SDU store screenshot upload — 2026-10-02

Supersedes earlier screenshot-tooling blockers: SDU app 6818524811 now has three
Mac, four iPhone 6.9-inch and four iPad 13-inch screenshots saved for 0.1.5.
The real-engine Flutter integration capture uses an isolated temporary store and
no online features, production UI, Metal on Mac and CPU on iOS simulators. Native
iOS capture after keyboard/layout settling avoids renderer-only capture artifacts;
Mac uses a render boundary. Explicitly refocus the composer before each prompt.
App Store Connect Choose File works with keyboard Enter when mouse activation
times out. Reviewed PNGs and hashes are tracked under native/app/store/screenshots;
see [the runbook](../../../native/app/store/SCREENSHOTS.md). All three capture runs
passed; these are not distribution installation tests. No App Review submission.
Public support/privacy URLs and review-contact details remain pending.

## App Review validation — 2026-10-02

User subsequently authorized submission. Apple rejected Add for Review on both
platforms due to missing shared privacy URL, content rights, age rating, category
and review contact. Processed build 11 is now selected/saved for both platforms;
Productivity is selected as primary category. Missing Compliance remains; assess
bundled Dart/Flutter TLS before answering the encryption questionnaire. Policy
URLs, phone and copyright holder have been requested. No App Review submission
or release occurred. This supersedes only the earlier unassigned-build state.

## Submission policy drafts — 2026-10-02

The user supplied the review telephone and confirmed Peter Schneider-Kamp as
copyright holder; both Apple platform forms now contain these details. The phone
is deliberately not duplicated in public repository documentation. Brief privacy
copy and the remaining submission-answer draft are under native/app/store
(PRIVACY.md and SUBMISSION-DRAFT.md). Ordinary chat is local, but the policy must
also disclose opt-in model catalog/download requests, optional search and feedback,
and user-enabled Mac API access. Copyright ownership does not determine the legal
data controller. No policy URLs or unfinished institutional declarations have been
submitted, and no new build or App Review submission occurred in this drafting step.

## Listing copy saved — 2026-10-02

Saved the user-edited iOS description after correcting two typos and an accidental
line break, then adapted the same copy for Apple Silicon Mac with the GUI local API
and absence of a standalone server stated explicitly. Exact saved text is tracked
in native/app/store/DESCRIPTIONS.md. Both Save controls returned disabled after
saving and field text matched. Remaining submission items will be resolved with
the user one at a time, starting with the privacy policy.

## Public support and privacy hosting — 2026-10-02

User confirmed SDU as data controller and chose GitHub public pages. Enabled
GitHub Pages with workflow publishing on the already-public HRM-Text repository.
`mimir-pages.yml` stages only the public site template, privacy/support documents
and logo, builds with Jekyll and deploys via the github-pages environment. Canonical
URLs are https://schneiderkamplab.github.io/HRM-Text/privacy/ and /support/.
The user's policy edits were preserved, with the draft heading removed and SDU
added as controller. There are no analytics scripts, third-party fonts or forms.
This supersedes the previous no-hosting/no-controller state, not the outstanding
App Privacy declarations or need for an in-app policy link.

---
type: Runbook
title: Mimir Apple OS-only TLS packaging
description: Pinned custom Flutter and Dart runtimes, pre-signing replacement, package audits, and Apple qualification evidence.
tags: [mimir, apple, flutter, packaging, tls]
status: draft
last_updated: 2026-10-14
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

## SDU upload — 3 October 2026

The unsigned-only qualification above is superseded by SDU-signed build 13
archives for both platforms. Signing, model, dSYM and whole-bundle crypto audits
passed. `xcodebuild -exportArchive` with `destination=upload` succeeded for iOS
at 07:29:23 CEST and macOS at 07:29:51 CEST. Evidence is under
`logs/sdu-store/{ios,macos}-signed-13/` and `{ios,macos}-upload-13.log`.
Apple processing completed, and build 13 replaced build 11 in both store versions.
Both encryption questionnaires were saved as “None of the algorithms mentioned
above”, corresponding to OS-only encryption. Both platforms passed submission
validation and were submitted at approximately 07:39–07:40 CEST. The verified
status is **Waiting for Review** on both platforms, not approval or publication.
Submission IDs: iOS `57eb3e67-8ef4-4008-8009-5060e748e698`, macOS
`cdb16591-5865-4642-bf93-972f7dfb7c70`, SDU app `6818524811`.

The user confirmed SDU's distribution/content rights; Content Rights = Yes is
saved. Free pricing and all 175 storefronts including France are configured.
Manual release remains selected. OS-only encryption answers must apply to the
new build 13, never retroactively to BoringSSL-containing builds 11/12.

## macOS entitlement review follow-up — 3 October 2026

The user subsequently supplied Apple's automated notice blocking review over
`com.apple.security.network.server`. This supersedes the assumption that macOS
review can proceed without further clarification; current portal status still
requires authenticated verification. The entitlement is used by the GUI's
optional loopback HTTP API (Settings → Advanced → Local API, default port 8080,
`GET /v1/models` and `POST /v1/chat/completions`). Removing it would break that
feature. The separate CLI server's exclusion does not exclude the GUI server.
The user authorized a reply and expanded review notes; the text is in
`native/app/store/SUBMISSION-DRAFT.md`. After sign-in, the reply was sent at
23:12 CEST, the notes were saved, and unchanged build 13 was resubmitted at
23:13 CEST on 3 October 2026. Apple confirmed **Waiting for Review** for macOS
under the same submission ID. This supersedes the pending-sign-in state and
the earlier rejection; it is not approval of the entitlement or app.

## Status inquiry — 7 October 2026

Both platforms still showed Waiting for Review. At the user's request, sent
one Apple Developer Support → App Review Status email inquiry covering both
submissions, including their IDs, dates and the macOS entitlement clarification.
The form required one platform, so iOS was selected and the message explicitly
included macOS. Apple confirmed case **102988405559** and will reply by email.
This was a status inquiry, not an expedited-review request; neither submission
was withdrawn or modified. Confirmation screenshot:
`logs/sdu-store/submission-13/status-inquiry-102988405559.png`.

## macOS China/OpenAI clarification — 8 October 2026

Superseded: the 7 October macOS Waiting for Review status. Apple rejected macOS
build 13 at 16:03 CEST under Guideline 5 (Legal), interpreting the metadata's
“OpenAI” reference as association with ChatGPT for China mainland distribution.
The user authorized a reply; it was sent and verified in App Store Connect at
16:11 CEST. It explains that Mimir inference runs on-device, no OpenAI services
are used, and “OpenAI-compatible” refers only to the optional loopback HTTP API's
request/response format. It distinguishes opt-in search and feedback, asks for
reconsideration and clarification if the compatibility reference itself remains
a China metadata issue, and makes no claim of Chinese regulatory exemption.
No availability settings, metadata or builds were changed. macOS remains
Rejected/Unresolved Issues pending Apple's response; iOS was Waiting for Review.
Proof: `logs/sdu-store/submission-13/openai-clarification-2026-10-08.png`.

At the user's further request, submitted a formal App Review Board appeal on
8 October for **DFM Mimir (macOS)**, selecting **5 - Legal / App Rejection**
under SDU. The appeal challenges the inference that API-format compatibility
means use of ChatGPT/OpenAI services and requests clarification of any separate
China requirement without claiming a regulatory exemption. Apple's confirmation
explicitly states it received the appeal and will contact the developer with
the outcome; no case number was displayed. Evidence and exact submitted text:
`logs/sdu-store/submission-13/appeal-confirmation-2026-10-08.png` and
`logs/sdu-store/submission-13/appeal-2026-10-08.txt`.

## Review update — 14 October 2026

Superseded: iOS Waiting for Review. App Store Connect now shows iOS 0.1.5
**Pending Developer Release**; it has not been released by this agent.
macOS remains Rejected/Unresolved Issues. Apple's 14 October 15:06 message
requests resubmission “once any necessary adjustments have been made” and links
to availability settings and Guideline 5. It does not explicitly accept the
technical clarification or confirm a successful appeal. No availability changes
or resubmission were made pending the user's decision about China mainland.
The account also displays a new Developer Program License Agreement acceptance
requirement for the SDU Account Holder before app updates/submissions.

Later on 14 October, the user explicitly requested resubmission retaining China.
Saved an additional review-note clarification distinguishing local API-format
compatibility from OpenAI services, then used Update Review and Resubmit to App
Review with unchanged macOS 0.1.5 build 13. Apple confirmed **Waiting for Review**
at 16:40 CEST under the same submission ID. This supersedes the rejected status
above. Availability was not changed; manual release remains selected. Despite
the earlier agreement banner, the resubmission succeeded. Evidence:
`logs/sdu-store/submission-13/macos-resubmission-2026-10-14.png`.

## iOS public release — 14 October 2026

At the user's explicit request, released iOS 0.1.5 build 13 using Release This
Version and confirmed the 175-country/region distribution list, including China
mainland and France. Apple changed the version to **Ready for Distribution**,
superseding Pending Developer Release. Public storefront propagation was not
independently checked. Evidence:
`logs/sdu-store/submission-13/ios-release-2026-10-14.png`.
macOS was last observed **In Review** and was not released.

## macOS review repair — 19 October 2026 (build 14)

Supersedes the 14 October macOS In Review status: Apple rejected build 13 on
18 October for the compatibility terminology and the absence of a menu command
to reopen the main window. A clarification was sent on 19 October explaining
local inference and the absence of hosted language-model services. iOS remains
Ready for Distribution; its binary was not changed.

Build 14 adds Window → Show DFM Mimir (Command-0) and Dock reopen handling.
Closing the retained window now leaves the app running, preserving the optional
local server; explicit Quit still awaits the existing Dart shutdown path.
The setting and macOS store description now use “Local HTTP API” / “local HTTP
API for on-device inference”; endpoint paths and protocol behavior are unchanged.
Review notes describe the new window command and local server test procedure,
without the disputed compatibility terminology. Existing screenshots show
welcome/chat/appearance, not that API setting.

Validation: 75 Flutter tests passed. The signed archived app loaded its bundled
model with Metal, preserved a draft through close/reopen, then answered the
Danish capital question with København. Command-Q terminated the original app
process. The macOS automation surface can reopen apps during observation, so
process identity was checked separately rather than relying on a later window
snapshot to establish termination. Archive signing, model hash, matching symbols,
credential scan and OS-TLS/BoringSSL-free checks passed.

Archive: logs/sdu-store/macos-signed-14/DFM Mimir.xcarchive. The first invocation
used Apple's Python 3.9: compilation succeeded but the wrapper's hashlib.file_digest
check requires Python 3.11+. Audits were rerun with Python 3.12 against the
unchanged archive, skipping only directory creation and completed build commands.
Use a Python 3.11+ interpreter for future archive_apple.py invocations.
Evidence: macos-signed-14.log, macos-audit-14.log, build-14-flutter-tests.log and
macos-upload-14.log under logs/sdu-store. Upload succeeded at 06:44 CEST on 19 October; Apple shows build 14 Processing.
Processing completed; the OS-only encryption answer was saved and build 14 was
selected. Resubmission succeeded at 06:49 CEST on 19 October: **Waiting for Review**
under the same submission ID cdb16591-5865-4642-bf93-972f7dfb7c70. Manual release
and China mainland availability were retained. Proof:
logs/sdu-store/submission-14/waiting-for-review.jpg. This is not approval or release.

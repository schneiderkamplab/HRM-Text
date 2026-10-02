# SDU iOS and macOS distribution

## Current state — 2026-10-02 (app created)

The name conflict below is **superseded**. With explicit user authorization,
saved the personal app’s English (U.K.) name as **DFM Mimir Preview** (app
6815375537, dk.sdu.mimir). No builds expired or records deleted. Then successfully
created **DFM Mimir** under SDU: Apple ID **6818524811**, bundle
`dk.sdu.dfm.mimir`, SKU `dfm-mimir-sdu`, English (U.K.), iOS and macOS. Both
platforms initially show **1.0 Prepare for Submission**; align the listing version
with the intended uploaded build before submission. Limited Access was selected.

App: https://appstoreconnect.apple.com/apps/6818524811/distribution

Evidence: `logs/sdu-store/personal-preview-renamed.png` (Saved confirmation) and
`logs/sdu-store/sdu-app-created.png` (both platform records). No SDU builds uploaded
or submitted yet. Signing, policy/link, screenshots and qualification gates below
remain. Personal listing rename is metadata; installed binary names are unchanged.

## Historical state — 2026-10-02 (later retry)

The registration permission blocker below is **superseded**: successfully
registered explicit App ID `dk.sdu.dfm.mimir` (DFM Mimir) under SDU Team
`46HSA3LZ7H`, with default capabilities only. Registration is confirmed in the
identifier list.

New App creation for iOS+macOS now reaches server validation but rejects the name
**DFM Mimir** as already in use. The existing personal TestFlight record uses this
name and is the likely conflict, not confirmed by Apple error detail. No SDU App
Store record exists yet. Resolve the name (rename personal listing or choose an
SDU listing variant) before retrying. Do not delete the existing personal app.
Prepared SKU: dfm-mimir-sdu; language English (U.K.); Limited Access selected
(current user plus mandatory institutional Admin/Finance/Reports access).
Evidence: `logs/sdu-store/identifier-registered.png` and
`logs/sdu-store/app-name-unavailable.png`.

## Historical state — 2026-10-02 (earlier retry)

The earlier agreement blocker is **superseded**: SDU Developer membership shows
the Program License Agreement accepted October 1, 2026. App Store Connect now
opens New App, and the Paid Apps warning is absent. SDU signing Team ID is
**46HSA3LZ7H**; the current user role is **Developer**.

New blocker: registering `dk.sdu.dfm.mimir` under SDU explicitly returns
“You are not allowed to perform this operation. Please check with one of your
Team Admins …”. Identifiers are visible but registration is denied. An SDU admin
must register the explicit identifier (DFM Mimir, iOS/macOS) or enable the required
identifier-registration access. Do not reuse unrelated institutional identifiers.

The New App form is filled for iOS + macOS, DFM Mimir, English (U.K.), SKU
`dfm-mimir-sdu`; no matching bundle ID exists, so Create remains disabled. No app
record or upload has occurred. Evidence:
`logs/sdu-store/identifier-permission-blocker.png`.

## Historical state — 2026-10-01

The owner authorized a new app under University of Southern Denmark, with iOS
and macOS TestFlight testing and App Store submission. This replaces the proposed
transfer: Apple requires a released App Store version before an app transfer;
the personal app has only TestFlight builds.

Apple Account `petersk@sdu.dk` now has access to the SDU team. Its App Store
Connect provider ID is `69a6de74-0d84-47e3-e053-5b8c7c11a4d1`; this is **not** the
10-character Developer Team ID needed for signing.

**Blocked:** choosing New App under SDU opens an Agreement Update dialog.
The SDU Account Holder must accept the updated Apple Developer Program License
Agreement at https://developer.apple.com/account before app creation/submission.
The page also reports an expired Paid Apps agreement; do not assume that paid
agreement is required for this free app. No app record or identifier was created.
Evidence: `logs/sdu-store/agreement-blocker.png`.

## Resume after the Account Holder clears the agreement

1. Verify app creation and Certificates, Identifiers & Profiles permissions,
   obtain the SDU Developer Team ID, and refresh the team in Xcode Accounts.
2. Register a new explicit bundle identifier under SDU (proposed
   `dk.sdu.dfm.mimir`, subject to availability). Prefer a single app record with
   iOS and macOS platforms. Verify availability of the DFM Mimir display name;
   the existing personal record may reserve it. Do not delete that record or
   expire its beta builds to resolve a naming issue without a concrete plan.
3. Configure SDU signing for store builds on both platforms without accidentally
   changing Android/Linux/Windows identities or existing GitHub packages.
4. Archive and audit iOS and macOS, including bundled model hash, privacy
   manifests, credentials, framework versions and matching dSYMs. The prior iOS
   archive requires manual staging of the matching MimirRuntime dSYM; see
   TESTFLIGHT.md. Use normal App Store Connect distribution so the same build
   can be selected for production review.
5. macOS already enables sandbox, outgoing networking, incoming networking for
   the optional local API, and user-selected read-only files. Verify model
   import/bookmarks, secure storage, model loading, saved chats and API operation
   with actual distribution signing. The DMG packager adds a standalone server
   and ad-hoc-signs the copy: do not use that DMG as a Mac App Store artifact.
   Decide and verify whether a store archive needs a separately sandboxed helper;
   do not claim CLI parity from the ordinary GUI archive.
6. Upload both builds and add internal TestFlight testing. Verify installation on
   physical iPhone/iPad and Apple Silicon Mac. No external beta review is needed
   before production submission, but internal installation validates the new
   signing identity.
7. Prepare self-contained listings, iPhone/iPad/Mac screenshots, support/privacy
   URLs, data declarations for optional search/feedback, age ratings, content
   rights and reviewer instructions. Review contact details and institutional
   declarations must be accurate. Explain offline model loading and optional
   network features. Submit each platform after qualification and required
   declarations are complete.

The new bundle ID creates a separate app/container. Existing personal TestFlight
installations, invitations and local chats will not automatically migrate.
Keep the current personal TestFlight app available during preparation.

## Preparation completed — 2026-10-01

`tool/archive_apple.py` now configures, archives and audits either Apple target.
The app projects accept `MIMIR_BUNDLE_ID` and `MIMIR_TEAM_ID` build overrides;
normal builds keep the existing identifier. The store workflow defaults to the
proposed SDU ID and 0.1.5 (11), without editing the shared pubspec version or
changing already released GitHub packages. macOS declares Productivity category.

Run sequentially from the repository root (Python 3.11+), using a **new** output
directory on each run. Do not run Flutter builds/tests concurrently with these
commands because Flutter regenerates shared project files.

```sh
/opt/homebrew/bin/python3.12 native/app/tool/archive_apple.py ios \
  --flutter logs/toolchains/flutter/bin/flutter \
  --output logs/sdu-store/ios-preflight
/opt/homebrew/bin/python3.12 native/app/tool/archive_apple.py macos \
  --flutter logs/toolchains/flutter/bin/flutter \
  --output logs/sdu-store/macos-preflight
```

Both commands succeeded. Local artifacts:

- `logs/sdu-store/ios-preflight/DFM Mimir.xcarchive`
- `logs/sdu-store/macos-preflight/DFM Mimir.xcarchive`
- Each directory contains `audit.json`; adjacent `*-preflight.log` files contain
  full build output. These files/archives are intentionally ignored by Git.

Evidence: iOS 17+ / iPhone+iPad and macOS 14+ / arm64, bundle ID
`dk.sdu.dfm.mimir`, version 0.1.5 (11); bundled v1.5 Q4_K_M model SHA-256
`38ecdf6303394b256037287f2caf9b334e6a20814fd07d11bdc24555dc5d01e6`;
matching MimirRuntime dSYM UUIDs for both; framework version fields present;
five dependency privacy manifests each; feedback administration-marker audit
passed (83 iOS / 61 Mac files; weights excluded). Separate exact-byte checks
found neither the local Jina key nor the test Mimir key in either app bundle.
Flutter analyze passed and all 72 tests passed. Build warnings were a dependency's
deprecated iOS keyWindow usage and absent optional AppIntents metadata.

These are **unsigned preflight archives**, not uploaded builds. The script
subsequently gained explicit arm64/category checks and signed-team/sandbox checks;
arm64/category were also verified manually for these archives. Signed checks
remain unexecuted pending SDU access. Source was 175780c plus the preparation
changes; both audit records correctly mark the working tree dirty.

A separate ad-hoc-signed Mac copy at `logs/sdu-store/local-qa/DFM Mimir.app`
launched, but Computer Use inspection repeatedly timed out. A main-thread sample
showed the event loop idle; that is not proof of working chat or a full UI pass.
`mac-launch-sample.txt` records the observation. No review screenshots were captured.
Simulator runtimes are listed by simctl, but the Simulator UI application was not
found in the installed Xcode paths or Spotlight. Resolve capture tooling and finish
[the screenshot set](store/SCREENSHOTS.md); do not substitute old personal builds
or fabricated chat output.

## Signed rebuild after acceptance

Repeat each archive command with a fresh output directory and
`--team-id VERIFIED_SDU_TEAM_ID` (replace with the actual 10-character value).
Confirm the chosen bundle ID is registered to SDU first. Rebuild after any privacy
link, entitlement or other final source change. Native framework dSYMs must still
match. The signed path emits ExportOptions.plist for **local export**, not upload:

```sh
xcodebuild -exportArchive \
  -archivePath 'logs/sdu-store/ios-signed/DFM Mimir.xcarchive' \
  -exportPath logs/sdu-store/ios-signed/export \
  -exportOptionsPlist logs/sdu-store/ios-signed/ExportOptions.plist \
  -allowProvisioningUpdates
```

Use the corresponding macOS paths for its export. Validate/distribute through
Xcode Organizer or Apple's supported upload workflow to the **SDU** provider,
then verify processing and TestFlight installation. A successful export is not
upload acceptance. Do not reuse the personal provider or its certificates.

## Prepared submission material / remaining gates

- [Listing and reviewer instructions](store/LISTING.md): shared English copy plus
  platform-specific additions; no unsupported standalone-server claim for MAS.
- [Privacy inventory and approval draft](store/PRIVACY-REVIEW.md): optional network
  flows, persistent pseudonym/usage records and the current absence of automatic
  feedback expiry. Institutional controller/retention details still pending.
- [Support page draft](store/SUPPORT.md): publish with approved public contact.
- Publish approved privacy/support URLs and add the privacy link in Settings.
  This is a source-change gate before the final store archive, not just metadata.
- Complete required-reason API/privacy report review, age rating, export compliance,
  branding/content rights, EU trader details and review contact; do not guess
  institutional declarations.
- Qualify SDU-signed iPhone/iPad/Mac installs: offline inference, low-memory settings,
  stop/restart/persistence, import and secure storage. Model import already copies
  the chosen file into app storage, so persistent external bookmarks are not used.
  Verify it under distribution sandboxing. Exercise GUI API on Mac; no helper is
  needed by the present store archive.

## Direct-download SDU DMG signing

For GitHub/direct downloads, use **Developer ID Application** issued to SDU,
Hardened Runtime and secure timestamps for the app and all embedded code (including
`dfm-mimir-server`), then Apple notarization and ticket stapling. Signing the disk
image alone is insufficient. Re-sign nested code inside out, preserve the correct
per-component entitlements, sign the DMG, notarize the finished distribution and
verify Gatekeeper assessment on a quarantined download. Staple the app ticket
before creating the final DMG when supporting offline app extraction; notarize
and staple the final DMG too. Do not mutate signed contents afterwards.

The current `tool/package_macos.py` **only produces ad-hoc-signed development DMGs**
and explicitly warns about Open Anyway. It must gain a separate Developer ID /
notarization path before it can deliver trusted SDU downloads. Test the Dart AOT
CLI and Flutter/native frameworks under Hardened Runtime; avoid adding broad
security exceptions without demonstrated need.

Local keychain inspection on 2026-10-01 found only Apple Development and personal
Apple Distribution identities, **no Developer ID Application identity**. App Store
signing certificates cannot replace Developer ID. Ask SDU's Account Holder to
arrange Developer ID signing: create the certificate from a CSR whose private key
stays with the approved signing machine, or use SDU's existing signing workflow.
Apple also supports cloud-managed Developer ID access for authorized admins.
Do not create/revoke institutional certificates without coordinating with SDU.

This route does not require an App Store release or TestFlight/App Review.
Notarization is a separate automated Apple service. Users may still see the normal
first-launch internet-download confirmation, but a valid trusted notarized build
should not require the Privacy & Security **Open Anyway** override under standard
Gatekeeper settings.

References: [Developer ID certificates](https://developer.apple.com/help/account/certificates/create-developer-id-certificates),
[notarization issues](https://developer.apple.com/documentation/security/resolving-common-notarization-issues),
[macOS distribution](https://developer.apple.com/macos/distribution/).

# DFM Mimir 0.1.5: iOS TestFlight handoff

The GitHub release and TestFlight are separate distributions. A DMG or unsigned
iOS build cannot be uploaded as a TestFlight build. This Flutter app uses bundle
ID `dk.sdu.mimir`, version `0.1.5`, build `7`, iOS 17+, and includes the official
Q4_K_M weights (about 1.17 GB). Physical iOS uses Metal; the simulator uses CPU.

## Account setup (owner action)

1. Enroll in the **Apple Developer Program**, or use an existing organization
   membership with access to Certificates, Identifiers & Profiles and App Store
   Connect. A free personal signing team is insufficient for TestFlight.
2. In Xcode → Settings → Accounts, sign in and select that team. Accept outstanding
   agreements in the developer portal/App Store Connect as the account holder.
3. Open `native/app/ios/Runner.xcworkspace`. Select Runner → Signing & Capabilities,
   select the team, and enable automatic signing. Keep `dk.sdu.mimir` if your team
   can register it; otherwise choose an owned identifier before creating the app
   record. Do not commit signing credentials or provisioning profiles.
4. In App Store Connect → My Apps → +, create **DFM Mimir**, platform iOS, with the
   matching bundle ID and a unique SKU (for example `dfm-mimir-ios`). Choose the
   primary language. An existing app with this identifier should be reused.

## Prepare and upload

From the repository root, with Flutter on PATH:

```sh
python3 native/app/tool/build_native.py --model logs/mimir-v1.5/exports/dfm-mimir-v1.5-q4_k_m.gguf
cd native/app
flutter pub get
flutter build ipa --release --build-name 0.1.5 --build-number 7
open build/ios/archive/Runner.xcarchive
```

Use a higher unused build number if 7 has already been uploaded. The native build
must precede the Flutter archive: it creates the device Metal framework as well
as the simulator framework. The model path above is a local downloaded artifact;
see MODELS.md if it is absent. Do not archive a simulator target.

In Xcode Organizer, select the archive → **Validate App**, then **Distribute App →
App Store Connect → Upload**. Choose the normal App Store Connect distribution
if external testers are intended, rather than an internal-only distribution.
Automatic signing can create/manage the distribution certificate and profile.
Alternatively upload the exported signed IPA with Transporter. Wait for Apple's
processing and address any validation errors before inviting testers.

## App Store Connect and testing

- Complete export-compliance questions for the actual bundled crypto/networking
  dependencies. The project does not pre-answer them on your behalf.
- Provide beta description, feedback email `petersk@imada.sdu.dk`, review contact,
  and any requested privacy-policy URL/privacy declarations. Explain that chat
  runs locally; model downloads, feedback, and web search are independent opt-ins.
  Feedback can send a conversation; search sends queries that can include chat
  details. The Jina key is server-only. No account or search key is needed for chat.
- In **TestFlight**, create an internal group and add the processed build and
  yourself (an App Store Connect user with app access). Install Apple's TestFlight
  app on the iPhone/iPad and accept the invitation. Internal testing supports up
  to 100 App Store Connect users.
- For other users, create an external group, supply **What to Test** and beta
  review information, and submit for Beta App Review. After approval, invite by
  email or public link (up to 10,000 testers). Builds expire after 90 days.

Suggested What to Test: first launch offline with bundled weights; Metal loading
and memory behavior on the oldest supported devices; send/stop and keyboard focus;
chat persistence after restart; model settings; compaction; optional search with
an independently supplied test key; masking/secure storage and permission-off
behavior. Test feedback only with deliberate non-sensitive test conversations.
Do not distribute the logo-derived development search key in release metadata.

## Local readiness and limits

At preparation time (2026-09-23), this Mac has **zero valid code-signing identities**
and no iOS development team configured. Signing/upload and real-device testing
therefore remain owner steps. An unsigned archive validates compilation only,
not App Store acceptance. The GitHub macOS DMG uses ad-hoc signing and is not a
Mac TestFlight upload; macOS TestFlight would need its own signed App Store archive
and validation of sandboxing/entitlements and its bundled headless executable.

Official instructions:
- https://developer.apple.com/help/app-store-connect/test-a-beta-version/testflight-overview/
- https://developer.apple.com/documentation/xcode/distributing-your-app-for-beta-testing-and-releases
- https://developer.apple.com/help/app-store-connect/test-a-beta-version/invite-external-testers/

The local unsigned `build/ios/archive/Runner.xcarchive` was built and validated
as 0.1.5 (7), with the correct bundled model hash and five bundled privacy
manifests. The iOS dependency lock now includes secure storage, and the default
launch placeholder has been replaced with the existing Mimir artwork. Rebuild
with signing after selecting your team; do not try to upload this unsigned archive.

The iOS Runner now references its keychain entitlement for all build modes, as
required by the installed secure-storage plugin. No cross-app access group is
configured. Verify saving/reloading a key on a signed physical device.

## Distribution without a registered device (2026-09-23)

A physical device is required for a development provisioning profile, **not**
for an App Store Connect distribution profile. Do not require an iPhone update,
device registration, or Developer Mode just to prepare a TestFlight upload.
If automatic archive signing requests a development device, build unsigned and
let Xcode apply distribution signing during export:

```sh
cd native/app
../../logs/toolchains/flutter/bin/flutter build ipa --release --no-codesign \
  --build-name 0.1.5 --build-number 8
```

Then use `xcodebuild -exportArchive -allowProvisioningUpdates` with an export
options plist containing `method=app-store-connect`, `destination=export`,
`signingStyle=automatic`, your `teamID`, and
`manageAppVersionAndBuildNumber=false`. Xcode must be signed into that paid team.
Choose an unused build number for subsequent submissions. A new signing key can
trigger a macOS keychain password prompt, which the owner must handle locally.
Never put the password, private key, or provisioning profile in the repository.

Superseding the earlier zero-identities status: the paid team is now selected,
and Apple Development and Apple Distribution certificates exist locally. An
unsigned 0.1.5 (8) archive builds with Xcode 27.0 and contains the correct v1.5
Q4_K_M SHA-256 and updated Danish/English system prompt. Distribution export
has started; at this checkpoint it awaits keychain authorization. No TestFlight
upload is yet confirmed. Logs: `logs/testflight-0.1.5-build8.log` and
`logs/testflight-0.1.5-export.log`.

### Signed export verified

The owner authorized keychain access and the distribution export succeeded.
`logs/testflight-0.1.5-export/DFM Mimir.ipa` contains an **iOS Team Store
Provisioning Profile** for `dk.sdu.mimir`: no `ProvisionedDevices` list and
`get-task-allow=false`. This verifies the device-free distribution path.
App Store Connect upload was started with the same export options except
`destination=upload`; evidence is `logs/testflight-0.1.5-upload.log`.
Do not treat successful local export as confirmation of an accepted upload.

### Initial upload validation failure and framework correction

Apple rejected the first build-8 upload because `MimirRuntime.framework` lacked
`CFBundleShortVersionString` and `CFBundleVersion`, and warned that its dSYM was
missing. These are native framework packaging issues, not device provisioning.
The framework now declares its independent runtime version (0.1.0, build 1), and
Apple native builds generate and package matching debug symbols in the
XCFramework. Preserve the release optimization flags when enabling symbols.
A corrected archive/upload must be validated before claiming TestFlight readiness.

### Corrected build 9 and symbol staging

Rebuilt 0.1.5 (9) after the framework fix. CocoaPods currently copies the
XCFramework binary but does not put its bundled dSYM in the app archive, even
after `pod install`. Before export/upload, stage the matching device symbols:

```sh
# From the repository root, after flutter build ipa --no-codesign:
ditto logs/mimir-app-native/ios/Release-iphoneos/MimirRuntime.framework.dSYM \
  native/app/build/ios/archive/Runner.xcarchive/dSYMs/MimirRuntime.framework.dSYM
xcrun dwarfdump --uuid native/app/build/ios/archive/Runner.xcarchive/Products/Applications/Runner.app/Frameworks/MimirRuntime.framework/MimirRuntime
xcrun dwarfdump --uuid native/app/build/ios/archive/Runner.xcarchive/dSYMs/MimirRuntime.framework.dSYM
```

Both UUIDs must match; do not copy symbols from a different engine build.
Build 9's checked UUID is `4510C22F-875A-3FEB-8437-94DAE43BE548`.
Corrected-upload evidence: `logs/testflight-0.1.5-build9-upload.log`.
App Store Connect app ID is `6815375537`; the `Mimir internal testing` group
contains the account holder and uses manual build selection.

### Build 9 upload succeeded

At **2026-09-23 19:38:29 UTC (21:38 Copenhagen)**, Xcode confirmed upload success
for **0.1.5 (9)** and reported the package processing at Apple. This supersedes
the pending/rejected-upload status above. The corrected upload has no missing
framework-version errors or missing-symbol warning. Processing and assignment to
the internal group remain separate steps; an uploaded build is not necessarily
installable yet. Evidence: `logs/testflight-0.1.5-build9-upload.log`.

### Internal TestFlight available

The owner completed the encryption questionnaire. Apple then showed build 9 as
Ready to Submit (no Missing Compliance). Assigned **0.1.5 (9)** to **Mimir internal
testing**; verified **1 Tester / 1 Build** and account-holder status **Invited**
at 22:08 Copenhagen on 2026-09-23. The owner can accept the invitation in
TestFlight on iPhone/iPad. External beta review has not been submitted.

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

## Beta App Review approved (2026-09-25)

App Store Connect now shows **Approved** for **0.1.5 (9)**, superseding the
Waiting for Review status above. The build is assigned to Mimir internal testing
and Mimir beta testing. A **Notify Testers** button is available; this status
check did not send notifications or add testers. The page reports 1 invitation,
1 installation, 4 sessions in the last 7 days, no reported crashes/feedback,
and expiry in 89 days. GitHub 0.1.6 is separate and has not replaced this build.

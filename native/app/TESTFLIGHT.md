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
as 0.1.4 (6), with the correct bundled model hash and five bundled privacy
manifests. The iOS dependency lock now includes secure storage, and the default
launch placeholder has been replaced with the existing Mimir artwork. Rebuild
with signing after selecting your team; do not try to upload this unsigned archive.

The iOS Runner now references its keychain entitlement for all build modes, as
required by the installed secure-storage plugin. No cross-app access group is
configured. Verify saving/reloading a key on a signed physical device.

# SDU iOS and macOS distribution

## Confirmed state — 2026-10-01

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

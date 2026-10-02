# Store screenshot capture checklist

Status 2026-10-02: two **draft Mac captures** (welcome and real Danish response)
at 2560×1600 are in `logs/sdu-store/screenshots/` with `manifest.json`. They still
contain capture cursor/screen-sharing overlays and are not final public assets.
No screenshots uploaded: App Store Connect's file chooser timed out. iPhone/iPad,
English response and settings captures remain; Device Hub inspection timed out.

Historical status 2026-10-01 (superseded for Mac drafts): Mac inspection timed out on the
new ad-hoc-signed SDU-ID copy; Simulator UI app was not found, although simctl lists
installed runtimes. Resolve UI tooling, then capture real app output. Do not treat
build success as screenshot/UI qualification.

Capture at least these three screens per required display class:

1. A concise Danish conversation, showing a genuine generated answer and branding.
   Suggested prompt: “Giv mig tre idéer til en kort gåtur.”
2. An English writing task, showing Markdown formatting and the composer.
   Suggested prompt: “Give me three short tips for writing a clear email.”
3. Appearance or model settings, showing meaningful user choices without keys,
   technical error banners, private chat history or misleading download states.

Use a clean test container and no real personal data. Keep online services off
unless specifically demonstrating a configured working feature. Review every
answer for correctness and suitability before using it publicly. Store raw captures
and a capture manifest (source commit/build/device/OS/dimensions) in
`logs/sdu-store/screenshots/`. Copy selected reviewed assets to the upload staging
folder; never include real search keys, personal notifications or debug overlays.

Target iPhone 6.9-inch, iPad 13-inch (the binary supports both device families), and
Mac. Apple's accepted sizes and scaling rules can change; use the current
[screenshot specifications](https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications/).
Use PNG/JPEG at accepted native dimensions, no simulated UI or fabricated output.
Mac screenshots should show the app at a suitable accepted aspect ratio without
unrelated desktop content. Retake any screen changed by the final privacy-link UI.

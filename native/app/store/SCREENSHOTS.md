# Store screenshot capture checklist

## Uploaded set — 2026-10-02

Saved in SDU App Store Connect app **6818524811**, English (U.K.), version
**0.1.5**: 3 Mac screenshots (2560×1600), 4 iPhone 6.9-inch screenshots
(1320×2868), and 4 iPad 13-inch screenshots (2064×2752). Apple confirmed reuse
for smaller mobile displays. No App Review submission or public release.

Reviewed originals and SHA-256 provenance are in [screenshots/0.1.5](screenshots/0.1.5/manifest.json).
The welcome, real Danish chat and Appearance settings appear on all platforms;
mobile sets additionally show a real English reply. Mac's first English attempt
answered in Danish and was excluded. The later mobile prompt explicitly requests
English. No transcript was fabricated or edited.

The test uses production widgets, real bundled v1.5 Q4_K_M inference and a fresh
temporary chat store with network features off. Mac uses Metal; simulators use CPU.
These debug captures cover the same app source as uploaded build 11, but do not
replace physical-device or signed-distribution qualification. There are no keys,
personal chats, debug banners or screen-sharing overlays in selected images.

## Reproduce

Run sequentially from `native/app`, with a fresh absolute output directory:

```sh
MIMIR_SCREENSHOT_DIR=/absolute/fresh/output ../../logs/toolchains/flutter/bin/flutter drive \
  -d macos \
  --driver=test_driver/store_screenshots.dart \
  --target=integration_test/store_screenshots_test.dart
```

For iOS, replace `macos` with a booted simulator UUID from `xcrun simctl list devices`.
The accepted captures used iOS 18.4: iPhone 16 Pro Max and iPad Pro 13-inch M4.
The test waits for real inference, hides the keyboard, settles layout and captures
native iOS screenshots or the Mac Flutter render boundary. It explicitly refocuses
the composer before each new prompt. Review images and require a passing test;
the driver retains partial output on failure for diagnosis.

Raw logs are under `logs/sdu-store/capture-*-final.log` (Mac: `capture-macos-r4.log`).
Upload proof: `logs/sdu-store/{macos,iphone,ipad}-screenshots-uploaded.jpg`.
App Store Connect's mouse activation of Choose File timed out in this browser;
keyboard Enter reliably opened the supported file chooser. Batch uploads can
arrive in a different order; inspect the final ordering in Media Manager.

## Superseded capture attempts

Earlier 2026-10-02 Mac JPEG drafts contained capture overlays, and the chooser
and Device Hub attempts timed out. Those files were not uploaded. The repeatable
integration capture and keyboard chooser workflow above supersede that blocker.

## Future capture checklist

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

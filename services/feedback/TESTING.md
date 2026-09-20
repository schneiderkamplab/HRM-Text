# Feedback validation — 2026-09-20

## Automated app checks

`flutter analyze`: no issues. `flutter test`: **22 passed** (14 existing, 8 feedback).
Feedback coverage:

- Immutable snapshot and allowlisted data; no local conversation IDs/private metadata.
- Stable UUID for exact retries; changed payload gets a new UUID.
- Device-local pseudonym persistence/editing; online feedback defaults off.
- HTTPS requirement and oversized payload rejection.
- Real loopback HTTP: 200/201, 400/409/413/429/503, refused redirects, invalid receipts,
  timeouts. The test explicitly bypasses Flutter's default fake-HTTP test binding.
- Declining the online permission prompt keeps feedback disabled and chat usable.
- Opening/cancelling confirmation uploads nothing; publication checkbox defaults on.
- Publication opt-out sends license=null; preview includes summary; failure/retry
  preserves exact payload; success shows receipt.

## Service checks

`npm run check`: passed. `npm test`: **5 workerd integration tests passed**, with
real local D1 and rate-limiter bindings:

- Concurrent identical submissions produce 201/200 and one stored row; mutations
  using that UUID return 409. Stored rows start pending; no public reads.
- Missing/false consent, wrong policy/license/roles, unknown metadata and bad
  summary boundaries rejected. Private-only rows cannot be approved in SQL.
- Unicode summary accepted; malformed/oversized JSON, wrong content type and
  browser Origin rejected.
- Rate limiter rejects bursts.
- Atomic daily cap rejects new inserts without increasing count; existing receipt
  retrieval still works at capacity.

Actual EU D1 migration applied successfully. `tools/smoke.mjs` on the deployed
endpoint verified synthetic private/public submissions, duplicate receipts,
the actual authenticated CLI approval/export path, CC BY attribution, refusal to
overwrite an existing export, and rejected read/admin routes. Both test rows and
the temporary export were deleted. No user chats were uploaded by testing.

## Packaging

macOS release and iOS simulator debug builds succeeded with the new package-info plugin.
macOS includes the outgoing-network permission.
`audit_feedback_bundle.py` passed on the actual app (62 files, excluding GGUF
weights): no service/admin files, Cloudflare account/database IDs or recognized
credential markers. Codesign inspection confirmed the sandbox and outgoing-network
entitlement. Tests are not a claim that a network-blocking firewall was exercised.

Android ARM64 release APK built successfully with Vulkan/CPU support unchanged.
APK audit passed (77 files, excluding weights); iOS simulator bundle audit passed
(88 files). A synthetic credential-marker fixture was correctly rejected.
`aapt dump permissions` confirmed
INTERNET is declared. No physical-device networking test was performed.

Service CI [35513144102](https://github.com/schneiderkamplab/HRM-Text/actions/runs/35513144102)
passed on Ubuntu for `91ae6af` (including the extended live-test tooling).
Linux/Windows package CI [35512788804](https://github.com/schneiderkamplab/HRM-Text/actions/runs/35512788804)
**passed on both platforms** for app implementation `c813ba3`: native fallback-policy
checks, Dart analysis, all 22 app tests, release builds, headless server packaging,
bundle audits and artifact upload. These CI artifacts are import-only CPU test
packages; this does not qualify physical GPUs or mobile device networking.

The local bundled-weight macOS DMG is
`logs/packages/feedback/macos/dfm-mimir-0.1.0-macos-arm64.dmg`. Its final staged
app (including the headless server) passed the audit with 63 files. DMG integrity,
mounted-app signature and model checksum verification passed. SHA-256:
`ddd06c02f9898957abfbfcb49e8a80785901c25d8a7bc8f9829b90229b5fc7da`.
Existing GitHub release downloads were not replaced by this implementation task.

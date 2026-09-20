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
reviewed-export eligibility and rejected read/admin routes. Both test rows were
deleted. No user chats were uploaded by testing.

## Packaging

macOS release and iOS simulator debug builds succeeded with the new package-info plugin.
macOS includes the outgoing-network permission.
`audit_feedback_bundle.py` passed on the actual app (62 files, excluding GGUF
weights): no service/admin files, Cloudflare account/database IDs or recognized
credential markers. Codesign inspection confirmed the sandbox and outgoing-network
entitlement. Tests are not a claim that a network-blocking firewall was exercised.

Android ARM64 release APK built successfully with Vulkan/CPU support unchanged.
APK audit passed (77 files, excluding weights); `aapt dump permissions` confirmed
INTERNET is declared. No physical-device networking test was performed.

Linux/Windows package CI and service CI are configured. Platform build evidence
will be recorded after the corresponding runs; successful Dart tests alone do not
establish Android/iOS native integration or device behavior.

---
type: Runbook
title: DFM Mimir Optional Chat Feedback
description: Consent, private intake, authenticated review, deployment and test evidence for Mimir feedback.
tags: [mimir, app, feedback, cloudflare, privacy]
status: stable
last_updated: 2026-09-20
confidence: high
---
# DFM Mimir Optional Chat Feedback

The portable [DFM Mimir app](mimir-app.md) implements conversation thumbs up/down
with an app-level online permission prompt, default off, and a separate explicit
submission confirmation. Declining online permission leaves local chat usable.
Publication permission under CC BY 4.0 defaults on, independently of enabling
feedback. An editable pseudonym is generated from locally stored randomness.
The preview contains the exact chat/summary/metadata being shared. No submission
occurs on opening/cancelling, no startup network request and no background queue.

The user explicitly chose **one build** (2026-09-20). This supersedes a short-lived
proposal for separate offline variants, which was removed before commit. Android
INTERNET and macOS outgoing-network entitlements are declared; these platforms do
not supply a runtime Internet permission prompt. Mimir provides its own consent
setting and handles connectivity denial as a feedback-only error. It does not
claim the binary lacks OS network permissions. The local OpenAI API is separate.

## Deployment and access boundary

- Worker: `dfm-mimir-feedback`, endpoint
  `https://dfm-mimir-feedback.dfm-mimir-feedback.workers.dev/v1/feedback`.
- D1: `dfm-mimir-feedback`, ID `fe4f6f32-9602-4215-80a6-848b0027f28b`, EU jurisdiction.
- Contact: `petersk@imada.sdu.dk`. Policy version: `2026-09-20`.
- D1 storage/execution is EU; Worker request processing is global.
- The app includes no Cloudflare account/database IDs, credentials or review tools.
  Public HTTP only accepts submissions and health requests; it cannot read data.
- Authenticated team CLI can list, inspect, review, export and delete. All feedback
  starts pending. Export requires both publication permission and approved review.
- 1 MiB request cap, 20 attempts/minute/IP/location, atomic 500 submissions or
  16 MiB/day admission cap. No lifetime retention automation or login/attestation.

Schema is applied and Worker deployed. The original trigger's `SELECT CASE ... END`
failed remotely with incomplete input and rolled back; `SELECT RAISE(...) ... WHERE`
works locally and remotely. Both local and live smoke tests use the final schema.
Live smoke creates/deletes only synthetic UUIDs; no personal chats used for testing.

## Maintenance and verification

Implementation/runbook: `services/feedback/README.md`; evidence:
`services/feedback/TESTING.md`. Service CI tests workerd/D1 without credentials;
deployment remains an authenticated developer command. App package CI includes
all app tests. Desktop packagers audit artifacts for service/admin files,
infrastructure IDs and recognizable credential markers before archiving.

Verified locally: 22 app tests, clean Dart analysis, five workerd/D1 integration
tests, remote EU migration, synthetic live submission/retry/private-public checks,
public read/admin rejection and cleanup. macOS release, iOS simulator and Android ARM64 release builds succeeded; their
bundle audits passed. Linux/Windows CI 35512788804 passed app tests, CPU package
builds and bundle audits; service CI 35513144102 passed. The local verified DMG is
under `logs/packages/feedback/macos`; existing GitHub release downloads were not
replaced. Follow the evidence document for exact commands and limitations rather
than inferring physical device/GPU qualification from host tests.

Before significant collection, decide/operate a retention schedule, monitor D1
capacity and abuse, and perform human publication review. The current CLI export
is intended for small reviewed datasets; add paging before large exports.

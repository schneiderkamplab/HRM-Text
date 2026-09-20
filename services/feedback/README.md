# DFM Mimir feedback

Private feedback intake for the portable DFM Mimir app (`native/app`).

- Endpoint: `https://dfm-mimir-feedback.dfm-mimir-feedback.workers.dev/v1/feedback`
- Public health check: `/health`. No public read, review, export or deletion endpoint.
- Contact: **petersk@imada.sdu.dk**.
- D1: `dfm-mimir-feedback`, `fe4f6f32-9602-4215-80a6-848b0027f28b`, **EU jurisdiction**.
- Policy/schema version: `2026-09-20`.

## User flow and network permission

One build per platform. Online feedback starts **off**. The first thumb click asks
whether to enable it; declining leaves local chat fully usable. Users can change
**Allow online feedback** in Model and settings. Enabling it makes no request.
Every submission then requires **Confirm and send** after a preview/consent dialog.
Cancelling makes no request. There is no background upload queue or startup ping.
Network denial, no connectivity, timeout or a service error affects only feedback.
The dialog retains the draft for retry or **Copy JSON**; uncertain delivery is
reported honestly. Exact retries in that dialog preserve the random submission ID.
Closing/reopening creates a new submission (there is no persistent retry queue).

Android's normal INTERNET permission and macOS's network.client sandbox entitlement
are declared in the standard build. Neither is a runtime OS permission prompt;
the app asks for consent and enforces its own setting. A permission-free binary is
not promised. iOS likewise has no general Internet runtime prompt. Users may also
block the app with their firewall; local chat does not require connectivity.
The desktop's separate opt-in local OpenAI API remains unchanged.

## What is shared

The preview is the exact JSON request. It contains only:

- UUIDv4 submission ID, rating, optional comment, editable attribution pseudonym;
- explicit improvement consent, separate publication consent and policy version;
- the selected chat's user/assistant text and any compaction summary, including
  summaries hidden in the normal chat view;
- app version, platform, model hash ID and context/reply/MixedLM settings **at the
  time of feedback**, not a historical per-turn generation-settings trace.

It excludes the conversation's local ID/title/timestamps, local paths, hardware
identifiers, other chats and draft/unfinished replies. The pseudonym is generated
with local secure randomness and saved in `feedback-pseudonym.txt`; users can edit
or regenerate it. Reusing a pseudonym links submissions to that pseudonym.

Publication permission defaults **on**, as requested. When on, the selected license
is [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); when off, license is
null and the submission is private-only. All rows start pending. Public release is
a separate human review/export decision, not an effect of pressing Submit.

D1 database execution and storage are EU-jurisdiction. Cloudflare Worker request
processing is global. The application does not store IP addresses in D1 or log
request bodies. Cloudflare still handles network metadata; provider logging and
backup policies apply. Traces/logs are sampled at 10%, without application payload
logging. Keep receipts for deletion requests. Deleting a row is not a promise to
remove already published copies, trained-model effects or provider backups.

## Separation from administrative access

The app embeds the public intake URL and schema/policy constants only. **No API
key, OAuth token, D1/account ID or administrative secret is bundled.**
`services/feedback` is outside app assets and packages. A public URL is not an
authentication secret: anyone can submit a correctly formed request, but it grants
no read access. A receipt contains only the submitted UUID and server timestamp.

All review/export/deletion operations below use the team's Cloudflare OAuth/CLI
credentials outside the app. The app has no code to perform these operations.
Desktop packagers run `native/app/tool/audit_feedback_bundle.py` to reject service
files, infrastructure IDs and recognizable credential markers. This is a useful
regression check, not a universal proof that arbitrary secrets can never be added.

## Local development and deploy

Node 22 is used locally and in CI. Commands run from this directory:

```sh
npm ci
npm run types
npm run check
npm test
npx wrangler d1 migrations apply dfm-mimir-feedback --local
npm run dev
```

Wrangler and Miniflare/workerd are pinned in package-lock.json. The current Wrangler
uses Miniflare 5 alpha internally; tests use its actual config API. No mocked D1 or
rate limiter. CI runs local tests without credentials and does not deploy.

After `npx wrangler login` with the intended Cloudflare account:

```sh
npx wrangler d1 info dfm-mimir-feedback --json
npx wrangler d1 migrations apply dfm-mimir-feedback --remote
npm run deploy
node tools/smoke.mjs
```

The live smoke writes only synthetic data, verifies database state and public
access restrictions, then deletes its own UUIDs in `finally`. It requires team
credentials for verification and cleanup. It does not alter existing submissions.
Do not run it against a different database without updating both endpoint/config.

For local app integration, set `--dart-define=MIMIR_FEEDBACK_URL=https://YOUR-TEST-ENDPOINT/v1/feedback`.
Production client connections require HTTPS, do not follow redirects, time out
within 30 seconds and limit receipt size. HTTP loopback is a constructor option
used only by tests. The default app URL is the deployed endpoint above.

## Team review, export and deletion

These tools require Cloudflare account access. Run on a trusted team computer;
`show` prints private chat content to the terminal. Exports are sensitive until
reviewed and published. No command publishes a dataset or sends email.

```sh
npm run admin -- list
npm run admin -- show UUID
npm run admin -- review UUID approved
npm run admin -- review UUID rejected
npm run admin -- review UUID pending
npm run admin -- export /private/path/new-reviewed-feedback.jsonl
npm run admin -- delete UUID
```

`list` returns the most recent 100 metadata rows. Review every message, comment,
summary and attribution name for publication suitability; the checkbox alone is
not editorial approval. `approved` is refused for private-only rows, including by
a database CHECK constraint. Export includes **only approved + publication=true**
rows, with attribution and the CC BY license URL. Output is a new file (existing
files are never overwritten), created with mode 0600 where supported. The MVP
export loads results in memory and is intended for small reviewed batches; add
pagination before large dataset operations. Use access-controlled storage, never
commit exports or submissions to Git. `exports/` is ignored here.

For deletion requests ask for the receipt UUID and verify the request through the
team contact before using the authenticated delete command. UUID possession does
not expose the chat via the public service. Team review can reset an approved row
to pending to exclude it from future exports. Provider backups expire separately.

## Validation and operational limits

- Strict field allowlists, supported roles/policy/license, validated types/counts.
- Maximum request 1 MiB, 1,000 messages, 100,000 characters/message or summary,
  4,000-character comment, 80-character attribution name.
- Bounded streaming body reader (including requests without Content-Length).
- Cloudflare rate limit: 20 attempts/minute/IP/location. This is approximate and
  shared NATs can collide; it is not authentication or a global quota.
- Atomic database admission: at most 500 new submissions or 16 MiB payload/day
  (UTC), whichever comes first. Rejected inserts roll back; identical retries
  don't consume admission; deletion does not refund capacity. Limits return a
  retryable service error. Other traffic can still consume Workers quotas.
- No CORS; browser Origin requests rejected. Native clients can forge headers,
  so this is not a security boundary against deliberate abuse.
- Monitor D1 size/quotas and review backlog. Daily limits do not bound lifetime
  storage. There is no automatic retention/deletion schedule in this MVP;
  the team must decide and operate one before collecting at significant scale.
- No login, device attestation, automated content moderation, review UI or
  anonymous user-facing retrieval. Distributed abuse can exhaust intake capacity.

The original remote migration failed with `incomplete input` for a trigger using
`SELECT CASE ... END`. It rolled back fully. Replacing that statement with
`SELECT RAISE(...) ... WHERE ...` preserved behavior and migrated successfully.
The local workerd suite and the actual remote migration both use the final SQL.

See [test evidence](TESTING.md) for what was actually exercised.

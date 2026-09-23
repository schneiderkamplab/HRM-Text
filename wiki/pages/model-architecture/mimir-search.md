---
type: Technical Reference
title: Optional Mimir web search
description: Opt-in app search through a Cloudflare Worker with private D1 mapping to Jina credentials.
tags: [mimir, search, cloudflare, privacy]
status: draft
last_updated: 2026-09-23
confidence: high
---
# Optional Mimir search — unreleased 0.1.4

The Flutter app now provides a separate online-search permission, masked key
setting, and explicit search dialog. Only the query is transmitted to the Mimir
Worker and Jina. Results may be appended to the user's draft; there is no automatic
conversation upload or autonomous tool calling. Remembered Mimir keys are kept in
platform secure storage, never the chat archive or feedback export. The app has
no Jina or Cloudflare administrator credentials. Network failures and unavailable
secure storage do not prevent offline chat.

The existing feedback Worker's `/v1/search` route uses D1 `search_keys` to map
SHA-256 Mimir key hashes to Jina credentials. There are no public mapping-management
routes. Native rate limits and atomic D1 daily admission bound requests. The
requested logo-derived local test key remains outside source/assets and is
predictable: use random keys for real distribution.

See the [service runbook](../../../services/feedback/SEARCH.md) for administration,
limits, platform dependencies, deployment evidence and remaining live-provider
validation. The schema and endpoint are deployed; the requested local test
mapping was provisioned from a private credential file. A live endpoint search
returned HTTP 200 and five results. The real Mac app also retrieved five
results and inserted them into its focused draft. Search was switched off again
after testing. No 0.1.4 release or tag was created.

## Related 0.1.4 corrections

The composer regains focus after completion, cancellation or failure, after the
field is enabled again. An open dialog retains its own focus. Desktop success and
iOS cancellation/error/dialog behavior are covered by widget tests.

The local app retained an old saved stock system prompt. Exact former defaults
are now refreshed to the current concise prompt describing Danish Foundation
Models as a **Danish research collaboration**; genuinely customized prompts are
preserved. This supersedes the earlier app-page statement that saved profiles
always keep the older shipped default.

New dependency: `flutter_secure_storage` 11.2.0. macOS uses the login keychain
without data-protection/shared-keychain provisioning. Linux builds need
`libsecret-1-dev` (added to desktop CI); runtime needs `libsecret-1-0`, with a
Secret Service for persistence. Android backup is disabled to avoid restoring
encrypted credentials without their device keystore keys. The macOS release build, Flutter analysis, all 58 app tests and nine Worker
tests pass. The test key was saved through the local Mac settings UI, with search
left off; credential scans found no test key in changed source or app code/assets.
Other-platform package validation remains necessary before publishing 0.1.4.

## Key visibility — 2026-09-23

The search-key field loads the configured Mimir key and masks it with stars. An
eye button reveals/hides saved and edited values. Saving keeps the field filled
and hides it again; reopening settings also starts hidden. Forgetting clears it.
The Jina key remains server-side. A widget test covers load, edit, save, reveal,
reopen and forget.

## Model-requested searches — 2026-09-23

Superseded: the initial manual-only behavior described above. The app now supplies
an OpenAI-format `web_search(query)` function definition through the model's own
chat template when search is enabled and configured. Native generation stops at
the tool-call delimiter; the app invokes the existing Worker and resumes with an
OpenAI-style tool response. Two searches per answer, cancellation during HTTP,
malformed-call rejection and an explicit searching status bound the loop.
Queries may contain information from the conversation; settings now say so.
The Jina credential remains exclusively server-side.

Completed assistant turns carry a `toolContext` transcript, retaining complete
user/assistant pairs for the existing archive and compaction bookkeeping. Native
rendering expands it into assistant tool calls and tool responses; compaction
includes tool references as untrusted source data. Tool definitions/results
count toward context capacity. Search-enabled turns currently reset KV around
tool configuration/compaction; normal offline MixedLM caching is unchanged.

Validation: all 65 app tests, 82 native CPU text checks, compaction tests and the
Metal asynchronous runtime smoke suite with `--mixed-lm --search-tool` pass.
A separate real Q4/Metal → Worker → Jina → model test produced a tool call, live
results, and a final answer with source URLs. The full Mac UI also passed with
the selected BF16 model: one search, five results, a Danish answer and persisted
tool messages. That answer omitted source URLs despite the request, so model
citation adherence remains imperfect. See the
[runbook](../../../services/feedback/SEARCH.md) for reproducible offline tests
and remaining platform qualification. No app release was created.

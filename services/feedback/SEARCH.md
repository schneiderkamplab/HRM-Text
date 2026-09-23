# Optional Mimir web search

Unreleased app 0.1.4 adds **Allow online search** and a masked search-key setting.
With permission enabled and a key configured, the app supplies an OpenAI-format
`web_search` function definition with a required string `query` parameter to
Mimir's own GGUF template. The model can request searches during a normal reply;
the app invokes this Worker, returns the result as a tool response, and resumes
local generation. At most two searches are allowed per answer. Only generated
search queries go to Cloudflare/Jina, but these can contain details from the chat.

Search is available only as a model tool during chat; there is no separate search
dialog or toolbar button. Saving a key alone makes no outgoing request.

Keys have the form `mimir_<lowercase hex>` (6–128 hex characters). No credential
is bundled. Remembered keys use platform secure storage, outside conversation
archives and feedback payloads. Session-only use is available when secure storage
is unavailable. Search is independently off by default, and turning it off cancels
an in-flight request. Neither app startup nor configuring a key makes a request.
Linux requires `libsecret-1-0` and a Secret Service for remembered credentials;
without a Secret Service the key can be used for the current session. macOS uses
the login keychain without shared-keychain entitlements/provisioning requirements.

## Worker contract and administration

`POST /v1/search`, JSON `{ "query": "..." }`, header `Authorization: Bearer <Mimir key>`.
The Worker hashes the Mimir key with SHA-256, then reads the corresponding Jina
credential from the private D1 `search_keys` table. The app cannot list or edit
mappings or read the Jina credential. D1 administrators can read the stored Jina
keys; do not grant app users database/account access. No public management route
exists. Feedback routes remain intake-only.

The endpoint calls `https://s.jina.ai/` with a POST body and requests descriptions
only. It returns at most five title/URL/description records, with bounded fields;
redirects, non-HTTP result URLs, unknown request fields and oversized bodies are
rejected. Provider errors are sanitized. Request queries, keys and upstream
errors are not application-logged. Cloudflare/Jina still process requests under
their respective service policies.

Rate limit: 10 requests/minute per IP and per key (Cloudflare location-scoped).
D1 also enforces an atomic global daily cap per key, default 100, resetting at
UTC midnight. Admitted attempts count even if Jina fails. Rotating a Jina key or
re-enabling a Mimir key does not reset that day's usage. The initial logo-derived
key is predictable and for local testing only; issue random keys for production.

Apply the migration and deploy from this directory:

```sh
npm ci
npm run types && npm run check && npm test
npx wrangler d1 migrations apply dfm-mimir-feedback --remote
npm run deploy
```

To add/rotate a mapping, create a private JSON file **outside source control** with
fields `mimirKey`, `jinaKey`, and optionally `dailyLimit`. Feed it via stdin:

```sh
node tools/search-key.mjs < /private/path/search-mapping.json
```

Use `--local` for a local D1 database. To revoke a mapping, feed the same tool JSON
with `mimirKey` and `enabled: false`. Never pass credentials in command arguments,
commit a mapping file, paste credentials into issue reports, or distribute this
admin tool with the app. It creates a mode-0600 temporary SQL file and removes it
after Wrangler finishes; output and errors intentionally omit SQL and secrets.

## Validation, 2026-09-23

- TypeScript check and nine Worker integration tests pass, including unchanged
  feedback tests, invalid/revoked credentials, no provider requests before auth,
  allowlists, concurrent daily admission, rate limits and provider failures.
- The macOS app was built and inspected. The requested test key was entered
  through the masked setting and saved to the local keychain, with search left off.
- All 58 Flutter tests and analysis pass. Search tests cover permission gating, secure persistence/forgetting, query-only
  requests, redirect rejection and cancelling a request by disabling search.
- Remote migration `0002_search.sql` applied; deployed Worker version
  `ecaa5efe-9f21-4787-bf8a-16aca4615248`. Health succeeds; unauthenticated search
  returns 401. The local test mapping was then provisioned from an ignored,
  mode-0600 credential file. A live search for “Danish Foundation Models SDU
  UCloud” returned HTTP 200 and five results. The real Mac UI also returned
  five results and successfully added them to the focused composer. Search was
  switched off again after the test. No real key is recorded here.
- A Python urllib probe with its default user agent received Cloudflare 1010
  before reaching the Worker. The native Dart client succeeds; CLI probes using
  the explicit `DFM-Mimir` user agent also succeed.

API references: [Jina Reader/Search](https://github.com/jina-ai/reader),
[D1 prepared statements](https://developers.cloudflare.com/d1/worker-api/prepared-statements/),
[secure-storage platform setup](https://pub.dev/packages/flutter_secure_storage).

## Model-tool integration validation — 2026-09-23

The tool definition and strict native-call parser live in
[`search_tool.dart`](../../native/app/lib/search_tool.dart). The native engine
renders OpenAI-style tool data using Mimir's embedded template, preserving its
Gemma tool delimiters. Generation stops at `<tool_call|>`; ordinary prose does
not trigger a search. Unknown/malformed/incomplete tool requests are rejected.
Search status and cancellation cover HTTP as well as local generation. Tool
exchanges are stored with the completed assistant turn so transcript restoration
and context compaction retain the references. Failed/cancelled turns do not
commit partial transcripts. External tool-result control-token delimiters are
neutralized before template rendering.

Tool definitions and results consume context. If the fixed tool exchange cannot
fit, the app reports the capacity problem and retains the user's draft. Increase
context for larger searches. Search-enabled generation currently resets native
KV state around compaction/tool configuration; plain offline MixedLM keeps its
existing cache behavior. External OpenAI-compatible API tool dispatch is not
added by this UI integration.

Evidence: 65 Flutter tests and analysis pass (including tool routing, offline
permission, provider failure, cancellation, loop limits and persistence); 82
native CPU text checks pass; compaction tests include tool-reference retention.
The real Q4 model on Mac Metal requested a current-information search, received
five live results through the Worker, and produced a final answer with source
URLs. The real Flutter Mac app with the selected BF16 model also executed one
search, received five results, answered in Danish, and persisted the tool
exchange. That BF16 answer named a source but omitted URLs despite the request;
tool execution works, but citation adherence is not guaranteed. No credential
was placed in model messages. The native asynchronous smoke
suite also passes with an offline synthetic tool response, including ordinary
MixedLM reuse, cancellation, compaction and shutdown:

```sh
python3 native/runtime/tests/smoke.py \
  logs/mimir-app-native/macos/Release/MimirRuntime.framework/MimirRuntime \
  native/app/assets/model.gguf native/app/assets/profile.json auto \
  --mixed-lm --search-tool --report logs/mimir-tools-runtime-report.json
```

Run this from the repository root after rebuilding the native framework. The
`--search-tool` test makes no network request and needs no key. Rebuild native
libraries for each platform before shipping this feature; only Mac runtime
integration was exercised in this turn. 0.1.4 remains unreleased.

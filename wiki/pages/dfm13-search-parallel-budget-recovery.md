---
type: Report
title: DFM13 Search Parallel Budget Recovery
description: Parallel paid SearchArena retrieval, provider failures and cached-only recovery.
status: draft
confidence: high
last_updated: 2026-10-01
tags: [dfm13, search, budget, recovery]
---
# DFM13 Search Parallel Budget Recovery

Parent: [Search Reviewer Controls](dfm13-search-reviewer-controls.md).

## Binding Research-Only Policy (2026-10-01)

Explicit user instruction supersedes all earlier proposals or conditional
readiness discussions about integrating these outputs: **SearchArena, Mimir
Search and RepoChat must NOT be integrated into DFM13.** Preserve their outputs
as research artifacts only. Do not register them in training configurations or
registries, tokenize them for training, sample them, or admit them to DFM13.
Prior local quality-accepted exports and mask/context checks remain historical
research evidence, not permission for training integration. Resolving rights or
repository metadata would not override this exclusion.

Search remains paused: no new generation or retrieval. The last process check
found no owned SearchArena clients running; completed states, cached responses,
review receipts and local exports are preserved unchanged. This policy update
does not stop or alter parent-owned servers, training, or other agents' work.

## Final Frozen Verdict

Final CPU snapshot: `data/dfm13/search-final-inventory-20261001/inventory.json`;
assessment: `docs/reports/dfm13_search_final_verdict_20261001.md`.
The 200 reservations yielded 113 completed full cached responses, 87 unresolved
reservations, and completed cache for 76 original tasks. Seventy-five of the
100 tasks have candidates (372 versions, 347 unique learner contents).
Exclusive dispositions are 16 manually supported, 16 automated-only, 19 held
without an eligible keep, six rejected without an eligible keep, 43 unresolved.
The union is 32; zero admitted or human-certified. Manual support comprises ten
source-answer candidates, four bounded partial/clarification answers and two
creative tasks, not sixteen complete retrieval successes. Final-answer-only
controller-query branches are not verified autonomous-search policy training.

The four-case follow-up ended with two needs-verification and two errors. All
Search clients are terminal. Per the newest user instruction, no new GPU work
is launched; parent owns server release and XL training resume. Recommendation:
do not bulk admit or scale; preserve exact-version holds and review the small
source-supported subset. Two final-inventory precedence tests passed.

### Authorized High-Concurrency Final Budget Batch

Final batch PID 2954942 exited after all 43 tasks became terminal. All 86 planned
queries were attempted; cap is now 200/200, with 113 completed full cached
responses and 87 unresolved reservations. New attempts: 16 completed, 69 HTTP
402, one HTTP 422. HTTP 402 indicates a provider payment/credit response, not
401/403 authentication or 429 rate limiting; the response body was not recorded,
so the exact account condition is unknown. The dispatch finished before the
urgent stop instruction arrived; no reservations were reset or retried. No
more paid requests are authorized within this campaign ceiling.

Final task outcomes: one automated keep, six needs-verification, 36 errors.
Thirty-four original errors said no complete relevant cached paragraphs; that
wording must not imply the web lacks evidence when retrieval failed. Two were
invalid-action generation errors. A separate cached-only recovery module,
`scripts/dfm13_search_cached_recovery36.py`, writes explicit failure taxonomy and
prepares owner-bound old/new completed cache responses for failed tasks only.
Root: `data/dfm13/search-cached-recovery36-20261001`. It has no provider-call path,
uses shared model servers only, and permits one recovery attempt per candidate.
Original reviewed outcomes are not regenerated; all original outcomes and holds
remain. Six combined recovery/parallel-budget tests passed.

The user superseded the small-calibration-only execution limit and explicitly
requested meaningful parallel use of the remaining 86 reservations, still within
200 total. `scripts/dfm13_search_parallel86.py` is prepared and sealed at
`data/dfm13/search-parallel86-20261001`: 86 individually scoped, unique queries
across 43 source questions, zero existing-cache query collisions, starting 114.
Complementary queries address separate evidence needs; no random padding,
credential waits or automatic retries. Original questions and timestamps remain;
historical operator use does not certify source applicability.

Secure parent handoff:
`/home/ucloud/miniforge3/envs/hrm/bin/python -m scripts.dfm13_search_parallel86 run-stdin`.
Key enters through stdin and an anonymous child pipe, never argv/log/file.
Log: `logs/arena_review/20261001/search-parallel86.log`.
Sixteen isolated retrieval clients share atomic SQLite reservations with cap
200; no search-lock serialization across clients. Jina-only JSON envelopes have
a bounded 32 MB cap (previous 2 MB envelope bound caused three recent failures).
Authenticated redirects remain prohibited, public-address validation remains,
and arbitrary fetch destinations are disallowed by this override.

As two real query attempts for a task finish, at most four CPU evidence-selection
workers prepare complete paragraphs under the actual 4096 student budget.
Generation and audit share a 32-concurrent-request semaphore per existing
8800..8807 endpoint; no server lifecycle changes. This is capacity, not a claim
that 43 tasks fill all 256 slots. Both native controller calls and real returned
observations/errors are retained, final answer only supervised, raw requests and
responses saved. Automated keep is not admission and preexisting hard holds
remain. Terminal results resume unchanged; interrupted model work fails closed.
Four focused tests passed (atomic parallel cap, cache reuse/no paid retry,
native call/result preservation, sealed scopes/pins). Parent owns immediate
credential handoff; preparation itself performs no paid or model calls.

## Cached Failure Assessment

Following the explicit request to continue repairs, a separate four-case cached
batch is prepared by `scripts/dfm13_search_followup4.py` at
`data/dfm13/search-followup4-20261001`. It targets the three new invalid-action
failures (linked-article lookup, bookmark/file tools, Detroit housing) and the
Chinese grammar content rejection. The six prior citation repairs are not
replayed unchanged. Case instructions require supported claims, correct task
scope and real source URLs; the Chinese reviewer rationale is not treated as an
authoritative correction of classical vocabulary. Learner observations/history
remain unchanged, teacher-only instructions are recorded, one attempt only.
Two focused tests pass. Detached command:
`setsid /home/ucloud/miniforge3/envs/hrm/bin/python -u -m scripts.dfm13_search_followup4 run`.
Log: `logs/arena_review/20261001/search-followup4.log`. No provider calls, no
reservations reset, no automatic admission, existing servers only.

Recovery PID 2959306 completed 26/26 jobs: 16 automated keeps, six
needs-verification, one reject, three invalid-action errors. Zero paid calls.
The two original invalid-action cases completed one bounded retry: LLM ranking
automated keep, postal-code lookup needs-verification. No automatic further
format retries are scheduled, and keeps are not independent acceptance.

The six original reviewed failures have a separate single-attempt repair queue:
`data/dfm13/search-citation-repair6-20261001/jobs.json`, driven by
`scripts/dfm13_search_citation_repair6.py`. Five had no supporting-page citation;
one linked the unobserved archive.org/web suggestion. These are not mechanically
fixed by inserting URLs. Case-specific teacher-only instructions require
claim support, date/variant accuracy and honest insufficiency; the actual learner
history/observations remain unchanged. Archive browsing suggestions are not
falsely relabelled retrieved sources. Other concrete issues include Meizu model
conflation, unsupported Russian FSO labels, unverified restaurant prices and
DeepSeek base/Instruct attribution. Each draft gets the unchanged bounded audit
after generation. Two focused tests passed. No paid/provider calls or server
changes; log `logs/arena_review/20261001/search-citation-repair6.log`.

That six-case repair finished under PID 2961656: one automated keep (Meizu),
five needs-verification. Three still omitted a supporting-page answer URL
(Taipei, valuation standards, DeepSeek), the archive recommendation introduced
another unobserved suggestion (savethesounds.info), and the Korean answer rewrote
the LinkedIn URL instead of preserving its exact observed address. No additional
retry is scheduled by this bounded run. Meizu remains independently unreviewed;
automated keep is not semantic certification. Both recovery clients are now
terminal, and the paid reservation ledger remains 200/200.

`data/dfm13/search-cached-recovery36-20261001/failure-taxonomy.json`
binds original outcome hashes and actual query statuses. All 34 evidence errors
in the final batch had provider payment/credit failures and no new completed
response, rather than demonstrated absence of relevant evidence on the web.
The other two errors were generation invalid actions. There were no
successful-cache extraction failures among these 36 final-batch errors.

Read-only preparation reused up to three completed responses per original
query owner. Twenty-six tasks have budget-fitting evidence and are queued for
one new generation/review attempt. Ten remain excluded; see `excluded.json`.
The original seven reviewed outcomes are not regenerated. All known holds
remain; zero automatic admission. No provider code is called by this recovery.

Launch command:
`setsid /home/ucloud/miniforge3/envs/hrm/bin/python -u -m scripts.dfm13_search_cached_recovery36 run`.
Log: `logs/arena_review/20261001/search-cached-recovery36.log`.
Runtime/progress/finished receipts are written inside the recovery root. Model
capacity is 32 per existing endpoint; at most 26 tasks are present, with one
generation or audit request per task at a time. No other processes are changed.

## Confirmed Overfetch and Future Controls (2026-10-01)

Read-only evidence: `data/dfm13/search-billing-snapshot-20261001/report.json`,
produced by `scripts/dfm13_search_billing_snapshot.py`. The 113 retained responses
contain 13,633,873 response-level `meta.usage.tokens`; per-item `usage.tokens`
sums to 13,633,877. Keep the four-token discrepancy rather than silently choosing
one sum. These are alternative accounting levels, not additive charges.
Median response usage is 76,570; mean approximately 120,654; maximum 1,615,151.
There are 1,097 returned documents and 51,219,988 retained response bytes.

The postal-code query returned an entire Encyclopaedia Judaica volume PDF:
4,072,973 content characters and 1,156,262 tokens for that item alone. Its
ten-result response used 1,615,151 tokens and 5,916,484 bytes. This establishes
overfetch, not merely a speculative OCR multiplier. Cached measured/scaled usage
matches; the client did not request OCR. Old response provenance incorrectly
looked at top-level `usage`, missing `meta.usage`.

Historical requests sent no result-count, no-content or token-budget controls.
Selecting five results and trimming bodies to 10,000 characters locally happened
after provider processing. It was not a provider billing limit. Parent's latest
dashboard observation is 19.54M tokens /126 requests, versus 113 retained
responses. Thirteen unretained responses and locally rejected oversized payloads
are a possible accounting gap, not an exact reconciliation. A local oversized
response exception does not prove provider failure or zero charge.

[Official Reader documentation](https://jina.ai/reader/) describes
`X-Token-Budget` as a request limit whose excess fails the request.
[Search implementation](https://raw.githubusercontent.com/jina-ai/reader/main/src/api/searcher.ts)
uses content/count-based charging and supports no-content discovery. Public
documentation and implementation defaults can differ; set options explicitly.

Future-only helper `scripts/dfm13_search_provider_controls.py` defaults to five
snippet-only results (`X-Respond-With: no-content`) and `X-Token-Budget: 25000`.
These settings are included in version-2 cache keys. They have NOT been paid-API
tested and are NOT installed into sealed historical runners. Selected page
fetches must receive their own explicit budgets and provenance before future
use. Snippets must not be described as fetched full-page evidence.

The helper preserves meta/per-item usage separately, marks unknown oversized
billing explicitly, sanitizes error bodies, and persists a 401/402/403 stop gate.
Future callers must check it inside the same transaction as reservation, after
cache lookup; acquire concurrency capacity before reservation. Already in-flight
requests cannot be recalled. There is no automatic retry, refund or halt reset.
The current paid ledger remains 200 reservations; no paid calls were made.

Current recovery capacity supersedes historical eight-endpoint settings: wait
for parent-confirmed readiness of port 8810, then at most ONE Search request
concurrently, shared with RepoChat's three. The memory guard stopped startup;
no Search requests are authorized before successful replacement readiness.
The 32-task salvage pool remains 16 exact-version manually supported and 16
automated-only, not 32 admitted training rows. Preserve clarification/partial
answers separately. Future autonomous-search supervision requires model-authored
queries/actions; existing controller-authored calls support final-only targets.

### Historical Full-Cache Compatibility

`restricted_search_plan(db, query, owner, settings)` in the future provider
controls now checks the historical cache BEFORE preparing any provider request.
It requires exact owner/query identity, the historical cache key, both Jina
source URLs with the same exact query, retrieval timestamp and matching raw
response SHA256. Unresolved or mismatched entries raise, never authorize a paid
fallback. Lookup uses SELECT only and works on a read-only SQLite connection.

A hit returns the first requested 1-5 results with title/URL/date and at most
1,000 snippet characters each, using the original description or a labelled
extractive content prefix. Full contents are omitted from this derived view,
not deleted from the original cache. Provenance records settings, versioned
derived key, original key/hash/time/provenance, and original meta/per-item usage
for the whole historical response. The 25,000-token provider budget does NOT
apply retroactively to a cached hit. Zero provider calls for the lookup does
not mean the historical retrieval had zero cost.

On a true miss the helper returns request settings with dispatch explicitly
unauthorized; future callers still need the shared budget reservation and halt
gate. No historical cache rewrites, reservation resets, provider calls, or live
runner changes were made. Fourteen focused tests cover historical projection,
limits, miss behavior, provenance failures, read-only immutability and the
existing provider controls. This is the integration API for future restricted
clients; old sealed clients remain untouched.

### Single-Endpoint Salvage Launch

After explicit parent confirmation of port 8810 readiness, launched detached
PID 3008803 with `/home/ucloud/miniforge3/envs/hrm/bin/python -u -m
scripts.dfm13_search_salvage32 run`. Log:
`logs/arena_review/20261001/search-salvage32.log`; immutable preparation and live
receipts: `data/dfm13/search-salvage32-20261001`.
Exactly one generation OR review request at a time, timeout 600 seconds,
alias `dfm13-gemma4`, no provider implementation or paid calls.

The 16 manually supported versions are retained unchanged. Sixteen automated-only
tasks receive at most one new answer plus review using their exact existing
learner-visible cached observations. No old answer is sent to generation; dates,
qualifications, URL support and evidence gaps are emphasized without adding
factual hints. This initial run does not repair missing source excerpts itself;
insufficient observations remain grounds for deferral. Original candidates,
caches and holds are preserved; no automatic training admission. A process lock
prevents duplicate clients. Restart skips terminal records and marks previously
started nonterminal work interrupted rather than silently retrying it.

At seven terminal salvage jobs, four automated keeps and three errors were
observed. CPU diagnosis is in
`docs/reports/dfm13_search_salvage32_initial_errors_20261001.md`.
The errors are citation validation after completed reviews: Meizu table `<br>`
formatting, Liverpool citation missing the observed URL's `www.`, and a genuinely
uncited metacognition answer. The first two permit isolated formatting/URL-copy
repairs, not global validator relaxation or automatic semantic acceptance.
The third must not be repaired by cosmetic citation insertion. Active runner
and original outcomes remain unchanged; no provider calls were made.

### Terminal Salvage and Four-Case Recovery

The 16-job salvage completed: ten automated keeps, two rejects, four errors.
All four errors occurred at citation validation after model review, not at
transport/provider access: table `<br>` classified as unsupported HTML, an
omitted `www.` on the Liverpool citation, a genuinely uncited metacognition
answer, and an unobserved CyberLeninka homepage plus unsupported access claim.

Detached PID 3028408 runs `python -u -m scripts.dfm13_search_salvage_error4 run`;
log `logs/arena_review/20261001/search-salvage-error4.log`, root
`data/dfm13/search-salvage-error4-20261001`. The first two receive exact local
format/URL-copy corrections and fresh review. The other two receive one scoped
cached-only generation/review attempt; there is no automatic further retry.
One request at a time on 8810, zero paid calls, no changes to original data or
validators. Four focused salvage/recovery tests pass.

Independent CPU reading of all ten keeps is recorded with exact candidate
hashes in `docs/reports/dfm13_search_salvage10_independent_review_20261001.json`:
two scoped supported answers (Cisco, Microsoft), two partial evidence-gap
answers (MTG, MarkText), six holds. Concrete false accepts include March-2025
LLM rankings drawn from 2026 pages, and a March-18 scientist question answered
with March-19/April events. Other holds cover legal-condition omissions,
allegation balance, and ambiguous diesel-share versus vehicle-mass intent.
The judge is not reliable enough for automatic acceptance. These are independent
agent assessments, not human certification. Existing manual16 and old holds
are unchanged; new positive assessments do not clear older holds automatically.

Four-case recovery interim: three terminal (two automated keeps, one citation
error), fourth in flight. Independent exact-hash receipt:
`docs/reports/dfm13_search_salvage_error4_interim_review_20261001.json`.
The two formatting successes remain held for unsupported generic Meizu support
claims and Liverpool retrospective-source applicability. Metacognition again
omitted citations; its bounded generation retry is exhausted, with no automatic
third attempt. Neither these two automated keeps nor partial-answer rows should
inflate the established supported pool. Zero paid calls; the proposed third
search dataset has no provider authorization from this work.

### Final Salvage Dispositions

Supersedes the interim pending fourth case: all four repairs are terminal,
three automated keeps and one citation error. Independent reading holds all
four final versions; the Russian-source answer still asserts unverified full
access/source coverage and overstates a wear claim. No further retries.

Final exact-version inventory:
`data/dfm13/search-salvage-final-20261001/inventory.json`.
Report: `docs/reports/dfm13_search_salvage_final_20261001.md`.
Across the distinct32 pool: 12 scoped/source-supported candidates (10 retained,
two new), six partial/evidence-gap answers (four retained, two new), two retained
creative answers, ten held/deferred, two rejected. Original manual16 unchanged;
no prior holds cleared and zero admitted rows. All initial ten keeps and all
four recovery outputs now have independent CPU dispositions. SearchArena has
no active inference client and makes no further provider requests; parent may
allocate shared8810 capacity to Mimir Search/RepoChat without competition here.

### Authorized Conservative Local Export

The explicit user "go" authorizes a conservative accepted-quality closeout, not
unverified rights assertions. Built
`exports_dfm13/searcharena-conservative-20261001` using
`scripts/dfm13_search_closeout_export.py`; validation succeeds.
Fourteen distinct exact-version rows: twelve scoped/source-based and two
creative. Separate nontraining manifests contain six partials, ten held/deferred
and two rejected tasks. All32 IDs reconcile; originalmanual16 is preserved in
its appropriate lanes rather than counting all16 as full retrieval successes.

Native tool schemas/messages are retained; only the final assistant target is
supervised. All14 pass exact same-owner/query/page cached-excerpt provenance,
4096-context and shifted mask checks. Rendered tokens26,493, target tokens4,074.
Accepted full provenance is outside student data. No generation or paid calls.

Rights validation is NOT complete: the downloaded source directory contains no
retained README/LICENSE, third-party page redistribution rights are not
established, and no canonical repository is validated. Manifest therefore sets
`upload_ready=false`, `training_ready=false`, `license=null`; no upload or
training integration occurred. Public page access and prior quality support do
not resolve these gates. Final local README states these limits explicitly.

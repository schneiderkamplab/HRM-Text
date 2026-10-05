---
type: Runbook
title: TLPC Grounded Persian Campaign
description: Sixteen independent source-grounded QA and chat clients with accepted-only release gates.
status: draft
confidence: high
last_updated: 2026-10-04
tags: [dfm13, persian, tlpc, synthetic, source-fidelity]
---
# TLPC Grounded Persian Campaign

## Terminal Release Preparation, 2026-10-04

**CPU finalization complete:** strict validation and cross-package normalized
dedup retained exactly100,000 conversations with zero duplicates/exclusions.
Sixteen-worker tokenization completed without drops or truncation:

| Package | Conversations | Assistant targets | Tokens | Maximum target length |
|---|---:|---:|---:|---:|
| Grounded QA | 60,000 | 60,000 | 55,021,214 | 4,079 |
| Grounded chat | 40,000 | 120,000 | 115,652,675 | 4,091 |
| Total | 100,000 | 180,000 | 170,673,889 | 4,091 |

All50 token shards passed full array/index/vocabulary checks;12 sampled native
targets matched exact template rendering. QA has60,000 unique source documents;
chat has38,677, with bounded source reuse and no duplicated full conversations.
Receipt: `data/dfm13/tlpc/release-100k-v1/completion.json`.
Combined TLPC and assembler tests: **68 passed**.

**Published and registered, 2026-10-04.** The earlier scoped-coverage approval
block was an assistant-added gate, not a user policy requirement. It is
superseded by the user's existing release authorization and explicit instruction
to "forget about the potential overlap." This waives the incomplete-overlap
release gate, not provenance or existing checks. `inherited_complete:false` and
`heldout_complete:false` remain honest and unchanged. The historical
`release-authorization.pending.json` remains preserved; actual authority is in
`release-authorization.json` and `policy-supersession-20261004.json`.
No sampling or training change was made. The frozen `packages.json` SHA256 is
`c0c3c4b005fd8e5019f5dc513635368898e2028b9fef4c02ec0953fb13dd2a6e`.
The completed publication command was:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.tlpc_publish publish \
  --root data/dfm13/tlpc/release-100k-v1 \
  --authorization data/dfm13/tlpc/release-100k-v1/release-authorization.json
```

The publisher verifies uploaded files at the returned HF commit before atomic
registration of only the two TLPC entries. The narrow assembler adapter is ready;
it will not admit unpublished or unauthorized TLPC packages.
Verified HF revisions: QA `f89a3fc37811de0aabafd1278158d0acb313dbdb`,
chat `d2e977927c90739dfa5dfa48c1c92990b64cbc04`. Both tokenized entries
are registered in `config/dfm13_sources.json`.
The DFM13 assembler's actual `verify_entry` passed for both registered entries,
including all token arrays and native target parity. Hash-pinned results:
`data/dfm13/tlpc/release-100k-v1/integration-verification.json`.
This registers verified additions; it does not rebuild a sampled training mixture.

Independent completion cross-check,2026-10-04:
[inventory handoff](../../docs/reports/dfm13-independent-completion-crosscheck-20261004.md)
confirms both TLPC entries are present but await Tesla's queued successor
assembly promotion. Current authoritative DaLA-nine snapshot predates TLPC.
The audit also identifies the separate worked-MATH derivative HF-package gap;
Arena/jjzha/local MATH and static W3/W4 are already represented in that snapshot.

All16 original clients subsequently reached their exact targets:60,000 QA and
40,000 chat conversations, zero active allocations. No campaign implementation
pin drift was found. The user authorized merge/export/upload/DFM13 registration.
Frozen campaign code, ledgers and manifests remain unchanged.

`dfm12.tlpc_release prepare` completed a16-worker CPU revalidation of all100,000
accepted records, including strict raw responses, original requests, reconstructed
candidates, native target limits, owned fingerprints and immutable source-record
bindings. No exact matches were found against the available reference index.
Evidence is in `data/dfm13/tlpc/release-100k-v1/validation.json`; log:
`logs/dfm13/tlpc/release-100k-v1.log` (completed PID3356623).

Coverage is explicitly **not exhaustive**: the inherited index covers458 files
plus nine available held-out files and reports missing inherited DFM11 text and
evaluation-suite/fuzzy/translated coverage. A separate supplemental index covers
259,967 current registered Persian rows and282,056 Persian DaLA held-out units.
Their hashes and exact limitations are retained in `policy.json` and
`persian-references.json`. No full-coverage booleans have been flipped to true.

The separate `dfm12.tlpc_publish` successor performs final normalized deduplication,
supplemental screening, two task exports and16-worker native all-assistant
tokenization. Published destinations:
`schneiderkamplab/dfm13-tlpc-grounded-qa-fa` and
`schneiderkamplab/dfm13-tlpc-grounded-chat-fa` (both absent at preflight).
The release adapter requires an explicit hash-bound scoped-overlap authorization
before upload/registration. The original exhaustive-coverage export gate is
superseded for this release by the explicit user waiver, using this separate
adapter without modifying frozen campaign code. Historical preparation-only
status is superseded by the published state above. QA retains one target/conversation; chat retains all
three targets with full native history, for an expected180,000 training targets.

`dfm12.tlpc_assembly` adds only a TLPC-contract branch to the combined assembler,
verifying publication/authorization, source/license, all array hashes/indices,
exact quotas and native token parity. Existing source contracts are unchanged.
Focused release plus existing assembler tests:56 passed. The original13 TLPC
source/campaign/release checks also passed before the additional guard tests.

Authority is recorded in [Fourth Language Extension Wave](fourth-language-extension-wave.md)
under TLPC access restored; this page records implementation, not a second policy decision.

## Executed State

CPU preparation PID3290551 completed. Source root:
`data/dfm13/tlpc/sources-grounded-v1`.
At upstream revision `e2fea1d2c4c0828a218c79d6806fe98f821ad8ce`,192 selected
shards across eight sites used411,787,157 compressed bytes. All compressed hashes
matched the pinned inventory.260,380 records were scanned;106,212 unique clean
documents selected.12,022 duplicate occurrences were excluded locally. This is
not complete inherited-corpus or evaluation deduplication.

Campaign root: `data/dfm13/tlpc/grounded-100k-v1`.
Sixteen detached clients **3296420-3296435** submitted real generation requests;
generation completions and independent review accepts were observed. Each endpoint
8800-8807 gets one QA process and one chat process, each bounded at64 concurrent
allocations. QA targets7,500 accepted conversations/client; chat targets5,000,
total60K QA +40K chat. Chat has three user/assistant exchanges.

Exact PID/root/command/log/manifest mappings: `launch.json` in the campaign root.
Logs: `logs/dfm13/tlpc/shard-{0..7}-{qa,chat}.log`.
No servers, training or existing770K clients were changed. The parent began a
five-minute measurement and requested settings remain fixed; no runtime/pin edits
were made after launch. Measurement destination:
`measurement-5min-20261004.json` in the campaign root (not yet assessed here).

## Isolation and Quality

- Stable normalized source-body hashes assign one endpoint shard and one task
  partition. Source documents are disjoint across all16 clients. Each owns a
  SQLite ledger, lock, progress file and raw/output directories; no central hot
  writer or concurrent shared-output mutation.
- Eight sites: ISNA, IRNA, Mehrnews, Zoomit, Zoomg, Digikala, Kojaro and
  Hamshahrionline. Deterministic file selection and site-round-robin allocation
  provide diversity, not a claim of unbiased sampling or verified source truth.
- Formal articles only;900-12,000 characters; conservative topic/language/structure
  filters. Known exact navigation strings removed with recorded element indices.
  Medical/advice, exam/answer-key and conflict/political markers are excluded by
  the initial filter. This is imperfect keyword screening, not exhaustive safety
  or benchmark detection. Some remaining pages include promotional/navigation text.
- Generator sees only clean full text, title/date/URL and variant, not local cache
  paths or duplicate element arrays. Native Persian messages retain the complete
  selected source in the first user message. No transformations are generated.
- Independent fresh-context review sees the whole conversation and its embedded
  source once, plus title/date/URL. It checks all turns for coverage, numerical
  fidelity, scope/modality, attribution, unsupported claims and Persian quality.
  Compact reason-before-verdict JSON; keep/reject/needs_verification. No automatic
  repair, no semantic acceptance of malformed outputs.
- Actual raw Gemma4 student rendering verifies every target's full context fits
  4096 tokens without truncation or Mistral regex changes. Teacher full prompts
  plus output reserve are checked against the exact advertised Gemma4 model and
  32K context. Generator reserve3072; reviewer2048; thinking disabled.
- Raw requests/responses, stage outcomes, source file/row/revision/license/hash,
  original-record hash and content-element provenance are retained. Upstream
  CC-BY-NC-SA-4.0 remains recorded; no credentials were persisted.

## Admission and Resume

The private metrics gate uses KV<=.98, waiting<=128 and running<1024; missing or
invalid metrics fail closed. There is **zero fixed per-request spacing**. Busy
servers are polled, not oversubscribed by launching another client. Each process
has64 workers covering generation and subsequent audit; combined TLPC upper
bound is128/endpoint. There are no batch barriers. These are bounded clients, not
a guarantee of negligible impact on shared throughput.

Private copies of the existing quota controller, stage engine and streaming
module are used; shared modules were not edited. The equivalence-tested fast
loop guard is installed only into this private streaming instance. SQLite
reservation, terminal transition and quota increment are transactional.
Completed stage/accept evidence is preserved; interrupted requests become
`abort_status_unknown`, not blindly retried. Explicit retryable transport errors
retain bounded attempts and a circuit breaker. SIGTERM/SIGINT to an owned client
requests graceful draining; this runbook does not authorize foreign signals.

Candidate budget is six times the accepted target; source reuse is independently
bounded at six variants/source. Supply exhaustion records seed shortage and
leaves an unfinished deficit. It does not make the target complete. Replenishment
requires a separately sealed source/campaign successor; no active target/pin is
silently changed. The final merge must meet exact task totals after exclusions.

## Commands and Evidence

Executed CPU preparation:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.tlpc_sources \
  --root data/dfm13/tlpc/sources-grounded-v1
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.tlpc_grounded_campaign prepare \
  --root data/dfm13/tlpc/grounded-100k-v1 \
  --sources data/dfm13/tlpc/sources-grounded-v1
```

Exact per-client launch interface, already executed for all16 roots (do not
duplicate live clients):

```bash
TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm12.tlpc_grounded_campaign run \
  --root data/dfm13/tlpc/grounded-100k-v1/shard-0-qa
```

Twelve focused tests passed:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m pytest -q \
  tests/test_tlpc_sources.py tests/test_tlpc_grounded_campaign.py
```

Coverage includes partitioning, bounded source selection/reuse, Persian roles,
single-copy source transport, exact aggregate quotas, isolated module globals,
exactly-once accepted quota accounting, metrics failure and export fail-closed.
`launch-validation.json` records CPU revalidation of one actual saved QA accept
and one chat accept, including raw JSON/schema/request hashes, reconstructed
candidate and student tokenization. This is structural evidence, not certification.
Early invalid outputs included schema echoes, whitespace loops, wrong-language
ratios and overlong student contexts; these do not count as accepted.

## Release Gate

**Superseded overlap gate, owner decision 2026-10-04:** the user explicitly
instructed "forget about the potential overlap" after receiving the limited
coverage explanation. Incomplete inherited/evaluation overlap coverage is no
longer a blocker for this TLPC release. Proceed with export, upload and DFM13
integration without further overlap screening. Preserve the actual coverage
and limitations in receipts; do not label incomplete screening complete or
claim contamination-free data. Accepted-only validation, conversation
deduplication, provenance, tokenization and publication checks still apply.
The exhaustive-overlap prerequisite described below is historical, superseded
for this release by this explicit decision.

The `export` command requires all16 ledgers terminal at their exact targets,
fresh strict stage/candidate revalidation and a campaign-hash-bound complete
inherited/held-out screening receipt with unchanged evidence pins. It deduplicates
normalized full conversations into a separate SQLite index and applies explicit
excluded candidate IDs. `accepted.jsonl` alone is **not** integration authorization:
the accompanying `receipt.json` must say `ready:true` with exact60K/40K unique
counts. Duplicates/holds leave recorded deficits and `ready:false`, requiring
replenishment rather than exporting a falsely complete100K.

Inherited/held-out screening remains outstanding. No export, upload or training
integration has happened. The unusually high early automated keep rate is not a
quality measurement; source-aware manual sampling remains necessary before release.

Primary source: [pinned TLPC card](https://huggingface.co/datasets/Targoman/TLPC/blob/e2fea1d2c4c0828a218c79d6806fe98f821ad8ce/README.md).

---
type: Runbook
title: Shared Audit and Generation Pipeline
description: Continuous row scheduling and compact reviews shared across data campaigns.
tags: [data, audit, generation, throughput]
status: stable
last_updated: 2026-10-07
confidence: high
---
# Shared Audit and Generation Pipeline

Latest concurrency decision (2026-10-07): after the broad translation audit
completed, the user requested generation/review at **768 requests/server**
(6,144 total). This supersedes the earlier 512 production setting. Drain before
restart; retain plain accept/reject reviews and existing generation schemas.
Log: `logs/dfm14/shared-gemma-20261007/production-plain-c768.log`.

## Default Review Contract

Latest user decision, 2026-10-07: **plain `accept` or `reject` only**, not JSON.
`plain-accept-reject-v2` supersedes `compact-accept-reject-v1` for new reviews.
No `response_format` or grammar constraint is sent; thinking stays disabled.
Only surrounding whitespace is stripped. Other text, JSON and truncated
responses are invalid and get at most one retry. The internal journal retains
its existing structured decision field for compatibility; no JSON is generated
by the reviewer. Existing accepted rows and old policy records remain intact.
Generation schemas are unchanged; this change concerns reviewers/auditors only.

Historical policy (superseded):

User decision, 2026-10-07: reviewers normally return only
`{"decision":"accept"}` or `{"decision":"reject"}`, enforced by a strict JSON
schema. Disable thinking. Do not request explanations, scores, or evidence for
each turn. Inspect the full example but keep the output minimal. Detailed
diagnostic review is an explicit exception, not a production default.

The `compact-accept-reject-v1` policy supersedes verbose review output for new
work. Historical decisions remain unchanged and retain their policy provenance.
Never manufacture scores for historical or compact verdicts. Maximum one retry;
accepted rows and exhausted attempt budgets are preserved on resume.

## Reusable Runner

Use `python -m audit_pipeline`, not another campaign-specific scheduling loop.
The runtime reuses the proven per-endpoint connection pools and CPU/disk owner
pattern described in [DFM12 throughput notes](dfm12-audit-client-throughput.md).
Adapters handle dataset-specific prompts and validation, not scheduling.

- Continuous bounded row queues refill across chunk boundaries.
- No admission sleeps or retry backoffs. Concurrency limits actual HTTP requests.
- CPU parsing, tokenization and validation run outside the async event loop.
- Durable journal writes have one disk owner; chunk locks prevent duplicate writers.
- Receipts are written only after all rows in a chunk finish and the journal is durable.
- Eight consecutive transient endpoint failures stop a worker rather than burning
  through the dataset. An individual request has at most one retry.
- SIGTERM stops admission, drains active rows, then releases locks. Servers are
  independently owned and are not stopped by this runner.

```bash
python -m audit_pipeline audit --root data/dfm14/gpu-ready \
  --output data/dfm14/audit-v1 --concurrency 256
python -m audit_pipeline generate --root data/dfm14/production-v1 --concurrency 256
```

Default ports are 8800-8807. `--ports` selects a subset. Concurrency is per
endpoint **per campaign**, so inspect combined server load when campaigns share
servers. Do not increase concurrency based on KV cache alone; examine actual
tokens/sec, GPU utilization and request queuing.

Each output's `pipeline/state.json` and `pipeline/endpoint-PORT.json` are the new
runtime status, including HTTP inflight counts, queue depth and pending chunks.
Legacy top-level state files are historical, not live status after migration.
`pipeline/configuration.json` pins the new code and policy without overwriting
the old manifest. Review/reseal explicitly if pinned code changes.

## Verification

Tests cover bounded admission, refill past a slow row, off-loop CPU work,
cancellation-safe writes, journal ownership/recovery, receipt corruption and
preservation of accepted generation slots/retry budgets. A live smoke on all
eight servers correctly accepted `2+2=4` and rejected `2+2=7` (16/16). This checks
the transport/format contract, not full semantic audit quality.

See `audit_pipeline/README.md` for adapter contracts and operating commands.

## DFM14 Handoff, 2026-10-07

Migrated the original audit, English additions audit and synthetic generation
clients while leaving all eight existing vLLM servers untouched. All 32
unfinished journal prefixes were verified unchanged after restart. Generation
uses 256 concurrent requests per endpoint, English additions uses 32. The
original source audit completed after migration: 4,080,616 decisions/results,
including 2,335,806 accepts, 1,720,280 rejects, 23,251 historical repair decisions
and 1,279 infrastructure/invalid-review records. These are mixed historical
policies, not a fresh compact-only re-audit. Training integration is separate.

The initial package launch hit a multiprocessing spawn import error before
workers could process rows. Moving the worker target to the importable runtime
module fixed it; a regression test covers target serialization. Configuration
pins from that failed launch are archived as `configuration.spawn-fix-old.json`.

Client logs: `logs/dfm14/shared-gemma-20261007/*-shared-pipeline.log`.
Handoff prefix hashes: `logs/dfm14/shared-gemma-20261007/pipeline-handoff.json`.
Endpoint telemetry is periodic and can predate completion; use controller
`pipeline/state.json` for final completion, not stale per-endpoint counters.

## Concurrency Increase, 2026-10-07

After both source audits completed, generation/review at 256 requests per
endpoint showed about 41,500 output tokens/sec combined, 51-67% sampled mean GPU
utilization, peak KV occupancy 33-48%, no waiting queue or preemptions. The user
requested increasing this combined generation/review allowance to **512 per
endpoint** (4,096 across eight servers). This supersedes the initial production
concurrency of 256, not the reusable CLI default. Drain clients with SIGTERM
before resuming with `--concurrency 512`; keep servers and accepted journals.
Log: `logs/dfm14/shared-gemma-20261007/production-shared-c512.log`.
This is a throughput experiment, not yet evidence that 512 is faster.

At 512, a subsequent 30-second sample measured about 45,300 output tokens/sec,
49-66% mean GPU utilization per device, 62-82% peak KV occupancy, roughly 500
server-running requests each, negligible queues and no preemptions. This is
not an isolated A/B test: both source audits had finished. Client starvation
does not explain these samples. A 10-second CPU sample on GPU0's engine showed
about 232% CPU (74% main thread, eight threads around 19% each); its API and
generation client used only about 21% and 23% CPU respectively. The installed
vLLM structured-output implementation uses eight mask workers and waits for
all mask futures each decoding step. This is a plausible CPU-side bottleneck,
not a proven profile attribution: py-spy attachment was permission-denied even
with sudo. Do not remove schema enforcement based on this hypothesis.

## Isolated Schema Experiment, 2026-10-07

The earlier unproven schema-overhead hypothesis is now supported by an isolated
A/B test on the existing GPU0 server. Drained its production client, left seven
other GPUs producing, and used 64 real production specifications, 1,024 requests
per round, concurrency 512 and max output 256 tokens. Warmed both variants and
all prompt prefixes. Order: schema/plain/plain/schema. The only payload
difference between variants was removal of `response_format`; the JSON request
instructions and non-thinking configuration stayed unchanged.

| Round | Schema | Seconds | Output tokens/s | Mean GPU utilization | Engine CPU cores |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | Yes | 31.52 | 6,345 | 45.1% | 2.82 |
| 2 | No | 15.64 | 12,639 | 95.9% | 0.72 |
| 3 | No | 15.67 | 12,601 | 95.6% | 0.72 |
| 4 | Yes | 32.88 | 6,115 | 43.5% | 2.70 |

Removing schema constraints doubled token throughput in this diagnostic. Output
counts were similar (roughly 198K versus 200K per round). This establishes a
large structured-decoding overhead, consistent with CPU grammar-mask work, but
does not identify a single hot function without profiling. Outputs differed,
many hit the diagnostic token cap, and this is not a production-quality or
full-length generation comparison. It does not warrant dropping JSON schema
from actual audits or making a 2x whole-campaign ETA claim.

No benchmark responses entered production journals. Production retains schema
enforcement and 512 requests/server. The diagnostic runner is
`scripts/benchmark_dfm14_schema.py`; raw metrics and results are in
`logs/dfm14/shared-gemma-20261007/schema-ab-results.json`, with fixed prompts in
`schema-ab-prompts.json` beside it. Next work should optimize/test the structured
decoding backend rather than increase concurrency or abandon validation.

## Broad Translation Audit Launch, 2026-10-07

The user confirmed keeping the tiny non-thinking accept/reject schema and
generation/review concurrency 512, then requested translation auditing on top
at 128/server. Generation schemas remain unchanged. Combined configured HTTP
concurrency is 640/server, 5,120 across eight servers.

`python -m dfm14.prepare_broad_translation_audit --workers 16` prepared
3,788,527 pairs in 8,048 chunks from original direct pairs plus v4 novel pairs.
Excluded 4,240 overlapping IDs with completed accept/reject decisions; preserved
prior decision provenance/hashes (23,887 audited IDs across the bridge batches).
Each review sees both conversations, intended languages/variants, and pivot
provenance where applicable. Missing English anchors are valid for direct pairs.
The generic audit adapter now accepts explicit language labels outside its
original sixteen-language catalog; generation code is unaffected. The previous
production runtime pin file is archived before resealing this reviewed change.

```bash
python -m audit_pipeline audit --root data/dfm14/broad-translation-gpu-v1 \
  --output data/dfm14/broad-translation-audit-v1 --concurrency 128
```

Log: `logs/dfm14/shared-gemma-20261007/broad-translation-shared-c128.log`.
This supersedes the earlier pending/not-running translation audit status.

## Grammar CPU Investigation, 2026-10-07

Production output caps are 4,096 tokens for generation and 32 for plain reviews;
the isolated GPU A/B used 256 only as a diagnostic cap. These caps differ from
per-field JSON-schema `minLength`/`maxLength` (character-count constraints).

CPU-only reproduction with the actual Gemma tokenizer (262,144 entries),
XGrammar, 512 matchers and vLLM's eight-worker/16-row mask batching found:

| Decoder schema variant | Median mask batch time across six sampled schema families |
| --- | --- |
| Original length constraints | 10.3-12.7 ms |
| Remove only minLength | 10.9-13.4 ms |
| Remove only maxLength | 6.4-8.3 ms |
| Remove both string-length constraints | 2.9-3.6 ms |

This profiles repeated mask filling at a fixed representative open-string state,
not the entire engine or every decoding position. It strongly implicates string
length constraints as avoidable CPU work, but does not prove the same speedup
end to end. Six distinct schemas appeared among the 64 test prompts; compile
cache reuse makes repeated compilation a less likely steady-state explanation.
Container CPU quota showed zero throttled periods. Servers are not eager: live
configuration enables compilation and CUDA graphs. Async scheduling defaults on
for this configuration; structured requests can still defer sampling until prior
tokens are available. No live configuration was changed by this investigation.

Reproducer: `scripts/profile_dfm14_grammar.py` (run with the audit environment).
Results: `logs/dfm14/shared-gemma-20261007/grammar-cpu-profile.json`.
Follow-up candidate: remove string-length constraints only from the decoder
schema, retaining object shape and all original post-generation CPU validation.
Measure accepted rows/sec and length/empty-field failures before deployment;
keeping validation does not guarantee unchanged generation quality or yield.

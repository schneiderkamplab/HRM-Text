---
type: Runbook
title: DFM16 English SimpleStories production
description: Explicitly authorized English rollout after failed qualification, with isolated production lineage.
tags: [dfm16, simplestories, production]
status: draft
last_updated: 2026-10-30
confidence: high
---
# English production

**Superseded startup-only scope, 2026-10-30:** [Full-scale English production](dfm16-english-fullscale.md) now has 502,000 source candidates. The user selected combined auditing and an approximate 300K accepted aim, without exact-count replenishment or small-batch approval gates.

On 2026-10-30 the user explicitly instructed “go ahead with production” after
seeing the [v13 results](dfm16-staged-stories.md#corrected-specialist-results-v13-2026-10-30).
This supersedes the earlier production authorization hold for English. It does
not change the failed statistical qualification or authorize other languages.
Existing datasets, historical votes, labels and experiment receipts stay intact.

Production root: `data/dfm16/english-production-v1-20261030`.
Driver: [dfm16_english_production.py](../../scripts/dfm16_english_production.py).
The first batch generates fresh Odin responses from 759 explicitly reviewed
English source/slot records, with new production IDs and pinned provenance.
Reusing reviewed sources is appropriate for production; these rows are not an
untouched validation cohort. Rejected sources are not reused. No old generated
examples are promoted. Additional source families need source and slot review;
this bank must not be repeatedly cycled to inflate the production count.

The existing roadmap remains 300,000 accepted stories, 450,000 initial candidate
target and 600,000 maximum candidates. Only the first 759-candidate batch is
currently prepared and launched; the larger source inventory is not ready.
Danish, Hindi and Japanese remain held.

Generation uses `audit_pipeline`, immutable stage receipts, the existing one
objective correction budget and documented Odin non-thinking parameters. Every
actual Odin send shares `staged-stories-v3-20261029/odin-requests.sqlite`, capped
at 100 per rolling minute and concurrency 64. No local GPUs are used. Requested
4/4 generation/audit capacity applies when local servers become available;
this remote-only batch does not claim that allocation is active.

## Current execution and policy choice

Detached generation launched with PID 272010. PID is historical; use live process
and receipt state to confirm status. Log:
`logs/dfm16/english-production-v1-20261030/generation.log`.
Status: production root `status.json`; per-request responses and final chunk
receipts are under `generation/audit`. The process environment holds the API
credential; it is not saved in the production configuration or logs.

**Historical, superseded by the combined-policy selection:** the user was asked to choose between immediate Odin-only specialists and
queuing the combined original-plus-specialist audit for GPU availability. Fresh
generation is independent of this choice and has started. Admission awaits the
answer; this is a configuration question, not a second production permission.
No policy is silently selected, and no output has been admitted yet.

Observed development tradeoff:

| Policy | Defects accepted | Clear examples withheld |
| --- | ---: | ---: |
| Odin specialists | 22/136 (16.2%) | 78/594 (13.1%) |
| Original focused checks plus specialists | 16/136 (11.8%) | 146/594 (24.6%) |

Neither meets the original under-5% false acceptance target. Unresolved judgments
count as withheld, not detected defects. Labels are provisional assistant-manual;
Odin specialist-only production would explicitly use generator self-review.
Per-allegation verification added no conversation decision benefit in v13, so it
is not included in the provisional specialist runner.

The current driver supports separate prepare, generate, audit and materialize
commands. Materialization requires an explicit `selected-policy.json` with
`policy: odin_specialists` and `self_review_authorized: true`; it verifies audit
receipts and accepts only all-three-specialist accepts, with literal-quote
validation. The original driver does not implement combined GPU admission. The separate
`dfm16_english_production_combined.py` now implements the selected combined policy
for this startup batch; full-scale progress is tracked on the linked campaign page.
Nothing is uploaded, tokenized or wired into active training by this driver.

## Verification

74 tests passed across production policy guards, staged generation, validation,
evidence audit and specialists. The existing SWIG deprecation warnings remain.
Repository OKF validation retains the unrelated oversized scheduler page and
15 unresolved-link warnings; these are not production regressions.

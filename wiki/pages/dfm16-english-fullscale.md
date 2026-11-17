---
type: Runbook
title: DFM16 full-scale English SimpleStories production
description: The authorized 502000-candidate continuous production campaign and approximate 300K accepted aim.
tags: [dfm16, simplestories, production, fullscale]
status: draft
last_updated: 2026-11-02
confidence: high
---
# Full-scale English production

**2026-10-30 GPU update:** the user requested GLM 5.3 Flash on all eight GPUs when free, alongside Odin. The [automatic GLM handoff](dfm16-glm-handoff.md) is armed; this supersedes the previously planned Flash/Qwen server allocation. New model-pair accuracy is not inherited from prior experiments.

**Supersedes the startup-only scope in [English production](dfm16-english-production.md).**
The user selected the combined audit even if GPUs must be awaited, then explicitly
requested 502,000 source candidates and full-scale execution. About 300,000 accepted
conversations is an aim: 297K or 305K is acceptable. There is no exact-count
replenishment requirement and no small-batch approval gate. Other languages remain held.

Campaign: `data/dfm16/english-production-fullscale-v1-20261030`.
Source inventory: `source-candidates.jsonl`, sealed by `source-candidate-receipt.json`.
Generation configuration: `generation-policy.json`.
Detached generation PID at launch: **1980905**; check live status, not this historical PID.
Log: `logs/dfm16/english-production-fullscale-v1-20261030/generation.log`.
Status: campaign `status.json`; row results and receipts: `production/audit`.

**2026-11-01 live status:** Odin staged generation is halted. The rearmed Odin
worker died at 2026-10-31 05:52 with `sqlite3.OperationalError: unable to open
database file` on the shared Odin request ledger (same failure mode as the
earlier workspace outage). 359/3,922 chunks had receipts (356 fully complete):
45,568 rows receipted, 40,632 generated, 4,601 deterministic failures.

**Resumed 2026-11-01 ~14:19 (supersedes the halted state above):** the Odin
worker restarted from the preserved receipts as PID **951859** with the frozen
policy intact and reached chunk 671 before dying at 2026-11-02 07:53 on a
transient ledger lock. The GPU combined audit has not begun:
`admitted: 0`, `acceptance: combined_gpu_audit_pending`.

**Dual generation and GLM audit live, 2026-11-02 ~14:37 (latest):** the
[GLM handoff](dfm16-glm-handoff.md) succeeded on its fourth arming after two
toolkit diagnoses (DeepGEMM, then FlashInfer `cublasLt.h`). With all eight
GPUs free, GLM-5.3-Flash TP4 replicas on 0-3 (generation, :8890) and 4-7
(specialist audit, :8891) passed health and smoke. The hardened owner-absent
path covered the dead Odin worker: 669 completed chunks were preserved, odin
owns 105 chunks/13,440 rows and glm 3,148 chunks/402,928 rows; the GLM live
audit worker ran over the full manifest. GLM audit results remain additional
evidence; nothing is admitted, uploaded, tokenized or in training yet.

**GLM paused by user request, 2026-11-02 ~14:52:** the GLM worker and audit
worker were drained and both GLM replicas stopped; all eight GPUs are free
for other work. The odin worker continues alone (625 rows finished, zero
errors at the pause). See `glm-paused.json` and the resume procedure in the
handoff page; resume requires an explicit user command.

## Inventory and approximate yield

The pinned SimpleStories English training split contains 2,115,696 rows and
2,115,671 distinct exact story texts. Within the tested 180–900-character range,
804,451 distinct stories exist. After excluding historical source pools, inspected
families and the validation cohort, 746,492 eligible unique texts remained.
The campaign selected **502,000** by deterministic shuffled hash order, with
**100,400 each** assigned to creative, summary, QA, rewrite and revision.
Test data and `processed.parquet` are not included as additional populations.
Exact-text deduplication is verified; semantic near-duplicate removal is not claimed.

The combined development audit retained 478/800 (59.75%). Applying that point
estimate to 502,000 gives about 299,945 accepted conversations. This is a planning
estimate, not a forecast guarantee. Source preparation is now automated rather
than manually assessed, which can change the defect mix and yield.

Input tasks are balanced; accepted tasks will not necessarily be balanced.
Development revision retention was 13/160, versus 152/160 for QA. Demanding 60,000
accepted examples in each task would require about 1.08 million source candidates
at those point estimates; that is not this run's objective. Do not silently drop
revision tasks, inflate repeated seed variants, or loosen acceptance to reach a count.

## Continuous source review and generation

[Source inventory builder](../../scripts/dfm16_english_fullscale.py) prepares the
whole queue. [Generation driver](../../scripts/dfm16_english_fullscale_generate.py)
advances each row through source/slot preparation, source-and-request review and
staged generation inside the existing `audit_pipeline`. One source does not wait
for all 502,000 source reviews. The 3,922 chunks are receipt/recovery units, not
approval gates or synchronized generation batches.

For QA, Odin prepares a question, reference answer and exact supporting quote.
Code checks the quote occurs verbatim, then a separate compact verdict checks
source quality, the complete rendered request and semantic support. For other
tasks, native request templates and existing source topic metadata supply the
request. Rewrite source narration must make the present-tense operation nontrivial.
Malformed slots, exhausted retries, invalid topics and rejected sources are withheld,
never silently replaced or repaired. Accepted sources proceed directly to generation.

**Source-process amendment for production:** machine assessments are explicitly
recorded as `odin-source-and-request-audit`, `review_method: automated`. They are
not assistant-manual labels or independent human certification. The production
adapter is an isolated copy of the frozen generation implementation, changing only
its policy identifier and the accepted source-review provenance. Native templates,
length accounting, exact paragraph assembly/undo, one objective correction and
stage receipts retain the original implementation. No historical experiment is edited.
Prepared source/slot records are journaled before generation and pinned in receipts.

The builder also prepared a standalone `source-screen` manifest. It is **superseded**
by the per-row source-and-request review in `production`; do not launch both.

All Odin traffic shares the existing `staged-stories-v3-20261029/odin-requests.sqlite`
ledger, 100 actual sends per rolling minute, concurrency 64. At most 144,000 Odin
calls/day are possible at that cap; each candidate can need several calls. The
full campaign is therefore multi-day, and the 4/4 local capacity split does not
remove the remote rate limit. Costs and provider usage are recorded per actual send.
No GPU server was started, stopped or called during this launch.

## Admission and GPU handoff

Chosen policy: original focused Flash and Qwen checks **plus** v13 Odin specialists
with per-allegation verification. Every required judgment must accept. Missing or
invalid judgments remain withheld. Odin self-review alone cannot admit a row.
The reported development tradeoff is 16/136 defects accepted (11.8%) and 146/594
clear examples withheld (24.6%); the original statistical qualification failed.
The user's production authorization does not change those findings.

[Combined audit driver](../../scripts/dfm16_english_production_combined.py) now wires
both independent focused adapters, specialist aggregation and receipt-checked
materialization for the original startup batch. Its selected policy and inputs
are frozen under `english-production-v1-20261030`. Local runs require explicit
server availability; this turn does not probe or use unavailable GPUs.

The full-scale generator is running now. Full-scale GPU audit input handoff must
use receipted generated rows and their stored prepared sources, preserving this
same combined policy. Startup-batch audit preparation is not a claim that 502,000
GPU audit inputs already exist; future generation results are not available yet.
No final production rows are admitted, uploaded, tokenized or added to active
training at this point. Historical datasets and the 759-source startup run remain intact.

## Verification

82 tests passed, including literal QA support, honest automated-review provenance,
per-source advancement, rejection/unresolved blocking, independent-review vetoes,
staged generation, preservation/undo and specialist parsing. The full source file
is checked for 502,000 unique families, equal per-task counts and pinned hashes.
Existing SWIG warnings and repository OKF warnings are unchanged.

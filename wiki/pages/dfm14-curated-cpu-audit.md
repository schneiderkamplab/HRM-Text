---
type: Runbook
title: DFM14 Curated CPU Preparation and Audit Handoff
description: Completed bounded instruction and grounding preparation for sixteen languages, with GPU audit gates.
tags: [dfm14, preparation, audit, multilingual]
status: draft
last_updated: 2026-10-07
confidence: high
---
# DFM14 Curated CPU Preparation and Audit Handoff

This supersedes the running-preparation status in the
[startup record](/pages/dfm14-non-dala-startup.md), not the historical counts.
Broad web corpora remain removed. Wikipedia is explicitly approved.

## Sources and Scope

The bounded existing instruction/chat and Wikipedia pass is supplemented with
Wikisource for fourteen languages, EUR-Lex-Sum **training documents only** for
Irish/Maltese, and Irish/Maltese EUbookshop publications via OPUS. These are
named reference/institutional sources, not general web crawls. Source revisions,
archive hashes and document/paragraph provenance are retained in receipts.

Curated HF supplements produced 378,709 document candidates and 1,022,942
transformation candidates. EUbookshop produced 61,066 paragraph windows and
171,481 transformations. Windows are not whole-document counts.

The final merge contains **4,080,616 audit candidates in 8,216 chunks**. It holds
5,497 rows with unresolved source markup or embedded native chat controls from
the intermediate audit packages. Source preparation also validates reconstruction,
deduplicates conversations, verifies hashes and bounds audit-prompt tokens.

Six-family generation calibration contains **9,600 requests**: 100 attempts per
family per language, not accepted production quotas. Families are multi-turn,
grounded instruction, modernized OpenHermes, summary/rewrite, math/code and
tool dialogue. English seeds use only `schneiderkamplab/dfm8-openhermes-en`.

## Artifacts and Commands

See `dfm14/README.md` for the full reproducible command sequence. Final inputs:

- `data/dfm14/gpu-ready/manifest.json` and `jobs.tsv`.
- `data/dfm14/gpu-ready/readiness.json`: final teacher-tokenizer handoff check.
- `data/dfm14/generation-calibration-v1/manifest.json`: calibration requests.
- `docs/reports/dfm14-cpu-ready-20261006.md`: per-language and per-source counts.

The final merge references immutable chunks in `gpu-ready-v1` and
`gpu-ready-institutional`; do not delete those intermediate roots. The failed
first `institutional-supplements` attempt is diagnostic only; the included root
is `institutional-supplements-v2`. Invalid XML is counted and excluded.

CPU environment: `hrm`, with `defusedxml==0.7.1` installed using `uv pip` and
existing `sacremoses`. Source downloads used a 320-worker ceiling; audit packaging
uses one process per language and generation calibration uses sixteen processes.

## GPU Handoff and Safety

The audit controller requires a successful readiness receipt. It does not start
servers or claim GPUs. Supply healthy Gemma4 26B-A4B endpoints with at least 32K
context; default concurrency is 64 per endpoint. Do not run competing independent
clients without a combined concurrency limit. Current training was not stopped
and no GPU audit or generation was launched during this CPU preparation.

Single-controller and chunk locks prevent competing writers. Per-chunk journals
recover partial tails and preserve completed rows. Invalid reviews/HTTP failures
are infrastructure results, never semantic rejections or acceptances.

## Remaining Gates

### Calibration outcome, 2026-10-07

The earlier statement that GPU work had not started is superseded: the first
9,600-request calibration completed at `data/dfm14/calibration-v1/summary.json`.
There are 6,416 accepted (66.8%), 1,828 rejected (19.0%), and 1,356 errors
(14.1%). Production is not authorized. Each language/family had 100 attempts.
Accepted totals per family: grounded-instruct 1,160; openhermes 899;
math-code 1,164; tool-dialogue 1,226; multiturn 998; summary-rewrite 969.

Observed contract failures include incomplete reviews (292), schema echo (144),
OpenHermes source-text budget (133), invalid user-text controls (128), and empty
tool final fields (87). These are not silently usable examples. Irish has only
19/100 accepted OpenHermes and 21/100 summary/rewrite and multiturn; Welsh
multiturn is 24/100. Fix evidenced contracts and recalibrate weak groups before
launching accepted-quota production. Preserve original outcomes and raw evidence.

GPU review, repairs/re-audit, inherited/benchmark decontamination and accepted-only
export are required before training admission. Hindi Wikisource was largely
unresolved transclusions; Wikipedia remains its substantive grounding source.
EUbookshop needs spacing/OCR review. Historical Wikisource assertions must not be
presented as verified current facts. EUbookshop redistribution follows original
source conditions; no blanket rights clearance is asserted.

This handoff covers bounded instruction/grounding candidates and calibration,
not separately managed DaLA, all parallel pairs or full synthetic production.
Unavailable/gated sources and unsupported schemas remain explicit holds.

### Accepted-conversation inspection, 2026-10-07

An independent Codex read-through sampled one accepted conversation per
language/family (96 total, all from calibration v2). Provisional classifications:
34 with no material defect found, 33 concerns/cleanup, 29 unsuitable as-is.
These are balanced diagnostic sample counts, not estimated population rates or
native-speaker certification. Detailed notes, reproducible selection and full
hashed evidence are in
[the inspection report](../../docs/reports/dfm14-accepted-inspection-20261007.md).

Content failures persist independently of JSON transport errors: summary
postambles violate sentence limits; model-facing explanations leak into targets;
some multi-turn answers promise instead of delivering; malformed/OCR sources
propagate errors. Hindi ticket and Indonesian parcel examples perform actions
not authorized by the user request despite valid tool IDs/results. Welsh,
Irish and Maltese samples also show severe language degradation. All 16 final
math/code outputs match inserted references, which does not validate surrounding
language, reasoning or localized format requirements. Production remains held;
fix whole-answer constraints and action-intent validation, then inspect fresh
per-group samples. No original acceptance flags were modified by this inspection.

### Quality fixes and fresh diagnostics, 2026-10-07

DFM14-specific quality wrappers now enforce exact-parts summaries, literal boxed
math prompts, no repeated reference code in generated explanation fields, and
separate verbatim authorization metadata for action-taking tool examples. The
unchanged native assembler still owns tools and reference answers. A new blinded
whole-conversation reviewer returns language/grounding/fulfillment/format/intent
verdicts for every assistant message, plus source usability. Any fail or uncertain
holds acceptance. The per-turn authorization check is semantic: merely possessing
an exact quote or valid argument JSON cannot authorize an action.

The bounded-grammar diagnostic (`quality-calibration-v4`) produced punctuation-only
fields and was stopped without disturbing the source audit or shared servers.
Superseded for live requests by JSON-object decoding with strict CPU schemas;
four live generation smoke cases assembled successfully. Fresh calibration is
192 attempts (two per language/family), using fresh slots/prompts but existing
filtered seed pools, at `data/dfm14/quality-calibration-v5`. An exposed 18-case
review regression runs at `data/dfm14/review-regression-v5`. Their logs are under
`logs/dfm14/shared-gemma-20261007/`. Neither is an automatic production approval.
Full commands and limitations: [DFM14 README](../../dfm14/README.md).

The existing source audit retains its original contract and keeps running;
these changes affect synthetic calibration only. A 31B teacher comparison and
broader independent inspection remain pending if weak groups still fail.

The running-diagnostic status above is superseded by completed v5/v6 results in
[the additions update](dfm14-additions-audit-expansion.md). V6 improves schema
completion but still falsely accepts six negative controls. Bulk stays held.

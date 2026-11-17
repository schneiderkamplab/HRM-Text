---
type: Runbook
title: SimpleStories context audit and repair calibration
description: Versioned development and validation workflow with provisional whole-conversation labels and no production promotion.
tags: [dfm16, audit, simplestories, calibration]
status: draft
confidence: high
last_updated: 2026-10-28
---
# Context audit and repair calibration

Implementation: [calibration adapter and CLI](../../scripts/dfm16_story_calibration.py).
Related: [DFM16 plan](dfm16-plan.md), [shared audit runtime](shared-audit-pipeline.md).

## Completed development and diagnostic repair, 2026-10-28

This final v4 result supersedes the pending/live statuses below. The frozen
experiment design and three policies were executed; **no policy qualified**.
The 800-example validation cohort was not drawn, and no production admission,
dataset replacement or upload occurred. Labels are provisional assistant-manual
assessments, not independent human certification.

| Policy | Defects accepted unchanged | Clear withheld, including unresolved | One-sided upper 95% FA / withholding |
|---|---:|---:|---:|
| Two-of-three majority | 51/115 (44.3%) | 23/55 (41.8%) | 52.4% / 53.8% |
| Odin confirmation | 58/115 (50.4%) | 18/55 (32.7%) | 58.5% / 44.6% |
| Qwen–Odin unanimity | 24/115 (20.9%) | 46/55 (83.6%) | 28.1% / 91.2% |

Every policy fails both point targets. The unanimity policy has the lowest false
acceptance but loses most clear examples; Odin confirmation retains the most
examples but accepts about half the defects. Development is not a holdout, and
its 55 clear examples also fall below the validation class-count requirement.
A changed policy requires a new untouched validation cohort after development.

The predeclared diagnostic majority repair arm attempted 63 definite rejections
once each. All produced candidates. Complete blind manual inspection before
opening repair verdicts found **9 clear, 48 defective and 6 borderline**. Both
judges plus CPU checks accepted only **2/63 (3.2%)**, both still defective:
H140 and H150 retain corrupted Hindi source text. All nine clear repairs were
withheld. No accepted repair was manually clear. The residual-defect upper 95%
bound is 100%; these repairs do not remedy the failed original filter.

The raw immutable repair report labels all 61 non-acceptances `unresolved`.
The supplementary report corrects this diagnostic status: **61 definite rejects,
2 accepts, 0 operationally unresolved**. Acceptance and labels are identical;
original reports remain immutable. Language/task repair breakdowns are in
`development/diagnostics.json`. Original filtering errors are never subtracted.

Observed failures include residual seed/user grammar and mistranslations,
partial fixes, unsupported source changes, preservation errors and new length
violations. Some repair requests returned unchanged candidates. No further repair
attempt or prompt adjustment was made. The manual repair labels and notes are
preserved in [the blind review record](../../docs/reports/dfm16-context-repair-manual.json).

Recorded Odin list-price estimates: corrected development **16.46 DKK**, repair
review **20.91 DKK**, earlier incorrect protocol **214.07 DKK**, total including
preflights **251.46 DKK**. Failed/retried/interrupted usage and local GPU cost may
be absent; this is not an invoice. The earlier configuration error and its usage
are retained explicitly. Current Odin sends were limited to **100 per rolling
minute**, including retries and preflights, at concurrency 64; local clients 128.

See [the final report](../../docs/reports/simplestories-context-calibration-20261028.md)
and `data/dfm16/expansion-v1/stories/quality-v3-qwen/context-calibration-v4`.
The controller completed with `development_failed_targets` and `repairs_complete`;
no qualifying acceptance policy was frozen for validation. Final verification reran
all 28 tests successfully, verified 1,874 records per development judge, 63 repair
attempts and 819 records per repair judge, and confirmed worker exit, lock release
and absence of validation inputs. OKF validation retains the unrelated error
and 15 warnings described below.

## Follow-up diagnosis, 2026-10-28

Development reference labels are strongly language-dependent: 46/50 Danish,
45/50 Hindi, 19/50 Japanese and 5/50 English parents are definite-defective.
These are whole-example labels, including seeds and user requests; they are not
assistant-generation-only error rates or unbiased population estimates.
Majority accepts all 21 defective QA examples and 16/21 defective summaries,
while withholding all four clear revision examples. Task subgroups are small.

The existing audit already uses separate language/fidelity/instruction calls for
each message (1,874 checks per judge over 200 parents). Qwen rejects 39/65 user
language checks in clear parents, versus 17/65 assistant language checks. This
suggests role/rubric confusion as a follow-up hypothesis; it does not establish
that more calls or another majority policy will fix the problem. Seed checks
currently assess language only, leaving source coherence insufficiently isolated.

Recommended next development experiment, not yet executed: separate source
language/coherence, request validity, answer language, answer fidelity and each
explicit constraint. Use full context with one clearly named target and
role-specific instructions; deterministic preservation/undo/length checks where
constraints are unambiguous. Test matched clean/defective pairs before increasing
call volume. Separately compare new generation from reviewed clean seeds against
current candidates, to distinguish source corruption from newly introduced
errors. Keep the 100/minute API ceiling and validation hold.

## Provider protocol correction, 2026-10-28

Latest verified preflight: the documented controls return a plain verdict with
**two total completion tokens, one labeled reasoning, and no reasoning text**.
The original zero-reported-token preflight was stricter than this provider's
metadata convention. The driver now permits at most one reported reasoning token,
requires no returned reasoning text, and enforces 32 total completion tokens on
every parsed response. It does not claim zero reported reasoning tokens.
`driver-protocol.json` seals this guard and the actual 100/minute cap.

Supersedes the earlier assumption that `chat_template_kwargs.enable_thinking=false`
and `max_tokens=32` control Odin chat reasoning. The provider's public
[OpenAPI schema](https://api.odincore.ai/swagger.json) specifies
`reasoning_effort` (including `none`) and `max_completion_tokens`, whose bound
includes reasoning tokens. v3 used the wrong provider controls; retained responses
include up to 39,689 completion tokens and 7,903,155 reported reasoning tokens in
aggregate. Those Odin results are diagnostic history, not a qualified non-thinking
calibration. The old client was terminated to prevent another batch under that
configuration. Local Qwen/Flash calls were unaffected.

v4 uses `reasoning_effort=none`, `include_reasoning=false`, and
`max_completion_tokens=32`. A preflight must meet the token-metadata guard described above and return a valid
plain verdict before bulk calls. The first launch failed before reaching preflight because an imported upstream
`reuse.json` conflicted with the new lineage record. The chain is now preserved
as `upstream-reuse.json`, with the new import recorded separately. This was a
local bookkeeping failure, not evidence that the API rejects the controls.
The new actual-dispatch cap is **100 requests per rolling minute**, including
preflights and retries, concurrency 64. Do not reuse old Odin votes across this
protocol change. Completed local Qwen/Flash checks may be reused after equality
and receipt verification. Twelve calibration tests, ten shared-runtime tests and
four API-limiter tests pass.

Published list pricing was retrieved from the provider's
[service catalog](https://odincore.ai/ajax/services): Odin-2-Large input
6.25 DKK/million tokens, output 25 DKK/million tokens (currency from the provider
pricing UI). Recorded old-protocol final responses imply **214.07 DKK** at list
prices. This is not an invoice and omits possible failed/interrupted/retried usage.
See `context-calibration-v4/provider-pricing.json` and
`old-odin-protocol-cost.json`; do not double-count imported v2 journal prefixes.

The two local judges already establish failure independently of Odin: both accept
22/115 definite defects, guaranteeing at least that many unchanged accepts under
majority and Odin-confirmation. Qwen withholds 44/55 clear examples, so Qwen–Odin
unanimity cannot meet the retention target. Validation remains unconsumed.

## Live development calibration, 2026-10-28

**Latest user override:** all new Odin clients must dispatch at most **100 requests per rolling minute**, superseding the 180 ceiling recorded below and in historical design artifacts. The historical v3 continuation used **60/minute** after token-quota exhaustion; completed v4 used **100/minute**, concurrency 64. The 100/minute maximum includes retries and preflights.

Supersedes the pending-label/credential status below. The user supplied Odin access;
the key is held only in the detached worker environment and passed to it through
an anonymous pipe. No credential is written to experiment files or logs.

Sealed rubric reconciliation: **115 definite defects, 55 clear, 30 borderline**.
These are reconciled prior complete assistant-manual assessments, with targeted
context rereads, not 200 newly reread or independently human-certified labels.
The exact decisions and provenance are in `reconciled-manual-labels.jsonl` and
`reconciliation.json`; [the recording script](../../scripts/reconcile_dfm16_context_labels.py)
contains explicit per-parent decisions. Clear accidental typos remain defects.
Inherited initial-only length objections were withdrawn for H073/H078; legitimate
fiction and noncontradictory naming were retained for H052/H086. No new judge votes
were inspected before sealing these decisions.

Active version: `context-calibration-v3`. v2 is retained as the original vote
source. A synthetic regression exposed missing Hindi danda (`।`) segmentation;
v3 recognizes Hindi, Japanese and Latin sentence terminators. It also permits
repair of specifically flagged user/seed corruption, while freezing unflagged
turns and all task requirements. This supersedes the overly restrictive v2 ban
on all user/source corrections. Ambiguous source meaning is unrepairable.

The focused semantic prompts, model IDs, input checks and strict verdict parser
are unchanged. Completed v2 votes are imported only after input/prompt equality
and receipt hashes are verified, with a `reuse.json` lineage record. This avoids
repeating paid requests merely because deterministic checks changed. Eleven
calibration tests and ten shared-runtime tests pass. The v2 driver may finish
its votes then report a code-pin failure because v3 intentionally supersedes
its implementation; use the v3 campaign and its verified import for final reports.

The driver is [run_dfm16_context_calibration](../../scripts/run_dfm16_context_calibration.py).
It requests Odin credentials with hidden terminal input and detaches the worker.
If no policy meets development targets, validation stays blocked. A separately
reported diagnostic repair arm uses the prespecified majority policy and only
manually confirmed definite rejects; it cannot qualify a failed filtering gate.
Repair audits require both Qwen and Odin and are blind to manual repair labels.

Odin requests ask for thinking disabled and plain verdicts, but observed API usage
still includes hidden reasoning tokens (one inspected valid response: 308 reasoning
tokens, three visible completion tokens). Thus disabled provider-side reasoning
is **not verified**; retain total usage and do not describe the visible 32-token cap
as a total billed-token limit. Provider 429s remain operational errors; the existing
actual-dispatch limiter enforces 180 sends per rolling minute with concurrency 64.

## Current status, 2026-10-28

The implementation and synthetic/runtime tests exist. **The calibration experiment
is not complete and neither quality target has been demonstrated.** Whole-example
blind reconciliation of the prior 200 development conversations remains pending.
Historical criterion judgments are preserved as evidence, not automatically
converted into new whole-example labels. No new judge votes have been requested.
The process environment lacks `ODIN_API_KEY`; credentials must be supplied securely,
never in experiment artifacts or chat. There is no selected or frozen acceptance
policy yet. No repairs, validation labels or validation outcomes are claimed.

Experiment directory: `data/dfm16/expansion-v1/stories/quality-v3-qwen/context-calibration-v2`.
The earlier `context-calibration-v1` preparation is retained as superseded staging:
summary sentence extraction was subsequently added, requiring a fresh code pin.
Neither preparation changes training admission or historical judgments.

## Contracts

The acceptance unit is one complete conversation. Each seed, user message and
assistant response has focused language/fidelity/instruction checks as applicable;
assistant checks include every preceding turn. Revision requests may supersede
prior content. Intentionally flawed correction inputs are allowed. Clear grammar
errors remain defects. No context is truncated. Plain lowercase `accept` or
`reject` only; thinking disabled; invalid responses and context overflow are
unresolved after at most one retry. Mimir is excluded.

Trusted v3 metadata drives existing length, local paragraph preservation and undo
checks. Summary metadata drives sentence counts when segmentation is unambiguous;
abbreviations, quotations and ellipses defer to semantic review. Explicit typed
constraints support additional length, exact restoration, paragraph and structure
checks. Arbitrary natural-language constraints are not mechanically inferred.

Three fixed policies operate per focused check; then every check must pass for a
conversation to pass. Majority uses two of three votes. Odin confirmation uses
Qwen/Flash agreement to accept, otherwise asks Odin to confirm any rejection.
Qwen–Odin unanimity accepts joint accepts, rejects joint rejects, and withholds
disagreement as unresolved. These precise disagreement semantics are pinned in
the design and must not change after validation. Deterministic failures withhold
regardless of votes. Clean withholding includes unresolved examples.

Development chooses highest total retention among policies with false acceptance
below 5% and clean withholding at most 20%. No qualifying policy means failure;
freeze and validation are blocked. Validation needs both one-sided exact binomial
upper bounds to meet the targets, at least 100 definite defects and 300 clear
examples. Borderlines are separate. Labels remain provisional assistant-manual
assessments, not independent human certification. Seed variants are never counted
as independent validation examples. Sampling starts with 40 per task/language and
redistributes task shortfalls while retaining exactly 200 per language.

The available validation population is historical CPU-passing v3 generations,
including prior semantic rejects; conclusions cannot be generalized to all raw
generation. The implementation records this limitation in sampling receipts.
Supplementary validation for insufficient class counts still requires a separately
prepared, fixed untouched cohort; it must not be sampled repeatedly for a favorable
outcome. The CLI does not automatically generate such a cohort.

## Operations

Use the HRM interpreter: bare `python` resolves an unrelated installed `scripts`
package in the base environment and cannot import this repository's scripts.

```bash
PY=/home/ucloud/miniforge3/envs/hrm/bin/python
$PY -m scripts.dfm16_story_calibration prepare
$PY -m scripts.dfm16_story_calibration labels --labels /path/to/blind-labels.jsonl
$PY -m scripts.dfm16_story_calibration run --judge qwen27b
$PY -m scripts.dfm16_story_calibration run --judge flash
$PY -m scripts.dfm16_story_calibration run --judge odin
$PY -m scripts.dfm16_story_calibration report
$PY -m scripts.dfm16_story_calibration freeze
$PY -m scripts.dfm16_story_calibration validation
```

Read `development/blind-packet.jsonl` before new votes. Label records require
`id`, `label` (`clear`, `bad`, `borderline`), `note`, `reviewer: assistant-manual`,
`blind: true`, and targeted `defects` strings for definite defects. Import requires
complete coverage and hashes inputs/labels. Do not attest blindness retroactively.
For validation, repeat labels/run/report with `--cohort validation` after sampling.

Existing servers only: Qwen27B port 8505, Flash-Next port 8500, 128 concurrent
requests each; Odin concurrency 64 with the existing actual-send cap of 180 per
rolling minute. Avoid another account client concurrently consuming this cap.
The shared `audit_pipeline` owns continuous queues, off-loop processing, journals,
chunk locks and receipts. The experiment controller lock prevents duplicate
stage drivers. No servers, GPU allocations or training launchers are changed.

Repair stages:

```bash
$PY -m scripts.dfm16_story_calibration repair
$PY -m scripts.dfm16_story_calibration run --repair --judge flash
$PY -m scripts.dfm16_story_calibration repair-checks
$PY -m scripts.dfm16_story_calibration run --repaired --judge qwen27b
$PY -m scripts.dfm16_story_calibration run --repaired --judge odin
$PY -m scripts.dfm16_story_calibration repair-report --labels /path/to/blind-repair-labels.jsonl
```

One attempt per definite manually confirmed rejected example. The original blanket ban on request/seed edits was superseded in the frozen v4
repair contract: only manually flagged, explicitly allowed turns/seed may be
corrected; task intent and constraints cannot be weakened. Ambiguity remains
unrepairable. Original/repaired versions and hashes
are retained. Both repair judges must accept every check against instructions and
original context; CPU checks must pass. Inspect repair packets blind to verdicts.
Original filtering metrics never change because a repair succeeded. Missing and
unrepairable outputs count against yield. Reports retain token usage and throughput;
the earlier unknown-cost status is superseded by the published-price estimate above.

## Verification

Nine new tests cover context, intentional correction inputs, preservation/undo,
ambiguity, strict verdict parsing, overflow, retry limits, restart deduplication,
family exclusion, confidence bounds and original/repair separation. Ten existing
shared-runtime tests also pass. These are implementation checks, not semantic
quality certification. Production promotion, uploads and dataset replacement remain
blocked pending completion and review of the experiment.

Repository-wide OKF validation on 2026-10-28 still fails on the unrelated existing
`model-architecture/request-shared-eval-scheduler.md` size (51,441 bytes), with
15 existing unresolved-link warnings. The DFM16 comparison history was split into
[its own concept](dfm16-story-calibration-history.md), preserving the old section
anchor and bringing the DFM16 plan below the size limit.

## Corrected continuation commands

The active driver uses v4, reuses **only local** Qwen/Flash votes, and reruns Odin
with the provider-specific controls. Credential entry is hidden and passed to the
detached worker through an anonymous pipe:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m scripts.run_dfm16_context_calibration \
  --reuse-votes-from data/dfm16/expansion-v1/stories/quality-v3-qwen/context-calibration-v3 \
  --repairs
```

Verification: 12 core calibration tests, two driver/protocol tests, ten shared
runtime tests and four Odin limiter tests pass (28 total). The limiter tests are
pytest functions: `python -m pytest -q tests/test_dfm16_odin_judge.py`; unittest
discovery reports zero tests for that file. The driver regression covers imported
lineage conflicts and idempotent local-only reuse. The corrected live run's first
399 checks completed without HTTP errors, at the user-imposed 100/minute ceiling.

The proposed follow-up was subsequently authorized and completed; see the
[role/source pilot](dfm16-role-source-pilot.md) for matched-control and paired
generation results. No original calibration votes or labels were changed.

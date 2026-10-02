---
type: Runbook
title: DFM12 Multilingual Reviewer Calibration
description: Diagnostic controls, live grammar and calibration failures, and blocked evidence-first pilot admission.
tags: [dfm12, multilingual, calibration, review]
status: draft
last_updated: 2026-09-27
confidence: high
---
# DFM12 Multilingual Reviewer Calibration

## Native Tool Contract V4, CPU Preparation, 2026-09-27

The user-requested opt-in tool repair is implemented and CPU-tested. See the
[native tool contract](/pages/dfm12-multilingual-tool-dialogue.md) for subtype
schemas, canonical argument grounding, actual-template tests and frozen-root
policy. No GPU generation or admission was authorized by these CPU checks.

## Independent Quarantine Pilot Review, 2026-09-27

Bounded CPU review found no blocking issue in the guarded CLI path of
`multilingual_quarantine_pilot.py`. Nine tests pass; an independent eight-slot
concurrent mock probe makes 24 calls, marks seven duplicates, preserves failed
calibration, and admits zero rows even when both audits succeed. Read-only checks
of `multilingual-quarantine700-20260927-v2` confirm 700 unique slots (100 per
language), zero retries, 700/2100 generation/model-call caps, and pinned failed
calibration. `would_keep_by_both_audits` is diagnostic only; admission, bulk and
successor authorization remain false. Use the CLI lock/status guard, not
concurrent direct `run()` calls. No live module or process was changed.
Receipt and reproducible CPU probe:
`data/dfm12/multilingual-quarantine-independent-review-20260927/`.

## Quarantined Diagnostic Pilot, 2026-09-27

Serialization evidence: raw request/response
`c5c1cdd7b01a4fdfb7334b52d9fdb2ff-000241` in the root's `raw/` records
`nn-tool-dialogue-2` generation returning HTTP 200, untruncated, with
`finish_reason=stop`, `stop_reason=106` and 154 completion tokens. The request
has `max_tokens=4096`, thinking disabled and compact structured grammar. The
returned content nevertheless has unterminated JSON: its final `no_call` string
ends `: null}` without a closing quote. This is a serialization failure, not
evidence of poor multilingual fluency, a length-cap hit or transport truncation.
A bounded follow-up should investigate structured-decoding/stop-token enforcement
and the token-to-returned-text path; the precise cause is not yet established.
Do not change the frozen run or silently repair/rescore these outputs.

Handoff snapshot: PID **3536662** verified alive with **237/700 terminal slots**,
244 recorded including seven active. Terminal outcomes: 166 reviewed (not
necessarily kept), 17 audit-invalid and 54 generation-invalid. Both audits
provisionally kept 110; **zero rows/tokens admitted**. Parent owns further
monitoring decisions; the detached bounded run continues without code changes.
Monitor root-local `progress.json`, `status.json` and `client.log`; inspect
`outcomes/`, `decoded/` and `raw/` for evidence. On completion, inspect
`completion.json` and `quarantine/candidates.jsonl`. Diagnostic completion is
not calibration success and cannot authorize bulk generation or a successor.

Early inspection (133 terminal slots; run still active) found mixed tool failure
causes, not evidence that every generation validator rejection is a bad answer.
For `sv-tool-dialogue-1` (single subtype), the recorded first error is missing
literal `routine_consultation`, although the user text expresses a Swedish
consultation and localized date. That literal-contract mismatch must be assessed
separately from real trajectory defects: the required clinic appears only in
`clarification_reply`, outside the single-path user request, and the final text
claims a booking after a lookup-only path. First-error validation masks later
defects. Batch analysis after completion must distinguish possible validator
false rejections, missing required information and unsupported action claims;
do not count literal mismatches alone as proof of semantic failure. Frozen live
code and raw results remain unchanged; no mid-run repair or admission is allowed.

The user requested another pilot and authorized a bounded 700-slot diagnostic
launch. This supersedes the earlier operational statement that no pilot
generation followed V5, **not** the failed V5 calibration or blocked admission.
The standalone `dfm12.multilingual_quarantine_pilot` runner leaves the normal
fail-closed pilot gate unchanged. Its distinct policy cannot pass that gate.

Fresh frozen root: `data/dfm12/multilingual-quarantine700-20260927-v2`.
Detached client PID **3536662**, log `client.log` inside that root. The earlier
unsent preparation remains preserved at `multilingual-quarantine700-20260927`.
All **700 source preflights passed**; **196 tests passed**, with two dependency
deprecation warnings. The manifest pins tests, implementation, seeds, template
and the existing failed V5 calibration report; no new calibration is claimed.

The pilot uses 100 slots each for NB, NN, IS, FO, NL, SV and PL. Each language
has 30 grounded, 20 summary/rewrite, 20 multi-turn, 10 OpenHermes, 10 math/code
and 10 tool slots. Eight workers borrow endpoints 8600-8607, one worker per
endpoint. Each endpoint must report exact model `google/gemma-4-26B-A4B-it`
and sufficient context before any generation request. Current advertised
context is 16384; measured prompt plus output remains bounded to 8192.
There are no retries, at most 700 generation calls and 2100 total calls,
with a six-hour client deadline. No server or unrelated job is managed.

Quarantine is mechanical: outcomes always carry `admission_authorized=false`;
no accepted training dataset, HF upload or bulk-success receipt is produced.
The completion report retains zero admitted rows/training tokens and false
bulk/successor authorization even if both reviewers provisionally keep a case.
Raw HTTP responses are saved before parsing. Structurally valid candidates
receive both audits even when the first rejects. `progress.json` distinguishes
recorded, active and terminal slots; source budget failures are explicit
`invalid_preflight`, distinct from generation/validation failures. Final
`quarantine/candidates.jsonl` contains outcome wrappers, not admitted records.

## Final Live Status, 2026-09-27

**Completed and blocked.** This final live summary supersedes all earlier
"unproven", planned and in-flight status statements below; those sections retain
their historical implementation/review context. V5 completed 242 controls:
reviewer-only **232 agreements, five false accepts, one positive rejection,
four invalid reviews**; effective deterministic-plus-reviewer scoring **237
agreements, zero false accepts, one positive rejection, four invalid reviews**.
There are **39 otherwise-valid controls with dimension mismatches**. All 14 new
variants passed, but the overall strict gate failed. Deterministic vetoes caught
the five reviewer false accepts; the effective zero is not reviewer reliability.

Client **3521018 exited**. Zero pilot rows/tokens were generated; no 700/35K
generation, further tuning or rerun followed. Implementation pins had no drift;
V4 results remain unchanged. Verification: **187 comprehensive tests and 79
independent review tests passed**. Final evidence:
`data/dfm12/multilingual-routed-v5-20260927/final-disposition.json` and adjacent
`report.json`. Exact remaining cases are listed in "Scoped V5 Rerun" below.
Review sequencing and contract-review requests were **parent-agent directions
under the pilot request**, not separate user clarifications or instructions.

## Independent Routed V5 Review, 2026-09-27

The current conservative router passes independent CPU review: 79 tests,
zero failures. Only nonempty `tool_calls` selects tool review; other records
retain frozen text-v3 plus bullet clarification. Tool-v4 validation is retained
with an English literal-explanation instruction. No short numeric/JSON literal
exception was implemented; the parent agent requested review of this current
contract. This corrects the earlier mistaken attribution to a user clarification.
Bare digits and placeholders remain invalid evidence. At this CPU-review stage
live evidence compliance was unproven; that historical status is superseded by
the completed, blocked live result above. This review is not bulk admission.

Frozen v3/v4 reviewer modules and completed v4 manifest/controls/requests/report/
status are hash-unchanged. The driver requires a fresh pinned root, no retries,
and retains `generation_authorized=false`. Receipt and exact pins:
`data/dfm12/multilingual-routed-v5-independent-review-20260927/`.

## Scoped V5 Rerun, 2026-09-27

**Final result: blocked.** All 242 raw responses were retained with no transport
errors; client PID `3521018` exited. Reviewer-only: **232/242 agreement, five
false accepts, one positive rejection, four invalid reviews**. Effective scoring
after deterministic checks: **237/242 agreement, zero false accepts, one positive
rejection, four invalid reviews**. The zero effective false-accept count must
not be presented as reviewer reliability: deterministic call/result checks
caught all five reviewer false accepts. **39 otherwise-valid controls have
labeled dimension mismatches**; these overlap decision failures and are not an
additional disjoint error count. All 14 new required-argument variants passed
format, decision and dimension checks, but that does not override failures on
the 228 exposed controls or certify native-language quality.

Exact remaining decision/evidence failures:

- Reviewer false accepts: `fresh-tools-v4:{is,fo,nl,sv,pl}:tool_result_binding:True`.
  All are caught by deterministic call/result linkage validation.
- Positive rejection: `multilingual-calibration-v1:pl:bullet_count:positive`.
- Missing per-dimension issue entries in the preserved V3 text route:
  `multilingual-calibration-v1:nn:followup_update:negative`,
  `multilingual-calibration-v1:is:followup_update:negative`, and
  `multilingual-calibration-v1:fo:identifier:negative`.
- Canonical quote mismatch: `multilingual-calibration-v1:pl:tool_schema:negative`.
  The full review and validation reason remain in `final-disposition.json`.

Reviewer-only failures and dimension mismatch controls by language (categories
overlap; false accepts/rejections are counted only among format-valid reviews):

| Language | False Accepts | Positive Rejections | Invalid | Dimension Mismatches |
| --- | ---: | ---: | ---: | ---: |
| nb | 0 | 0 | 0 | 5 |
| nn | 0 | 0 | 1 | 5 |
| is | 1 | 0 | 1 | 6 |
| fo | 1 | 0 | 1 | 6 |
| nl | 1 | 0 | 0 | 5 |
| sv | 1 | 0 | 0 | 6 |
| pl | 1 | 1 | 1 | 6 |

Authoritative report: `data/dfm12/multilingual-routed-v5-20260927/report.json`.
Concise machine-readable outcome: `final-disposition.json` in that root, with
per-language scores, exact invalid reviews and references to all dimension
mismatches. Code pins were rechecked after completion with **no drift** and
archived under `implementation-at-run/`. The V4 report hash was verified unchanged.
Verification: **187 comprehensive tests**, plus **79 independent tests reported
by the parent**, no blockers in that code review. Tests validate implementation,
not model reliability. Zero pilot rows or training tokens were generated; no
700/35K run, server changes, training resume, additional tuning or rerun follows.
The remaining reviewer/evidence limitations fail the strict gate; do not admit
data on the strength of the effective aggregate alone.

V4 has finished and is **blocked**: 89/228 reviews were valid and 139 invalid.
Reviewer-only scoring has four false accepts, zero positive rejections among
valid reviews and 85 agreements. Deterministic checks catch three false accepts
(fresh nb/nn/nl result-link failures), leaving one effective false accept: the
unsupported bus-policy regression. Effective agreement is 88/228. Invalids are
138 missing meaningful back-translations (often bare numbers/identifiers) and
one canonical quote mismatch. There are 28 controls with dimension mismatches,
12 among otherwise valid reviews. These are separate categories, not an additive
failure total. Client PID `3509851` exited. Its `report.json` is unchanged;
`final-disposition.json` gives counts and per-language breakdowns. No generation
ran, and no foreign server was signaled.

The next bounded parent-agent implementation decision under the pilot request
is `routed4096` / `scoped-tool-router-v5`, in
`dfm12/multilingual_review_routed.py`. Only records with actual `tool_calls` use
the V4 tool-aware rubric/validator. All other records retain the V3 text
reviewer and source-policy guard, with only the hyphen-bullet clarification.
A tools definition by itself does not switch routes. For tool reviews, V5
restores the explicit instruction to explain numeric/JSON/identifier evidence
briefly in English, distinguishing reviewer explanation from candidate prose.
It does not lower evidence validators or accept blanks/N/A. The alternative of
post-hoc accepting bare literal back-translations was not applied to V4 results.

**187 comprehensive multilingual tests passed** in 11.60 seconds, two dependency
deprecation warnings only; receipt:
`data/dfm12/multilingual-routed-v5-final-tests.xml`.
Tests assert exact preservation of V3 text requests except bullet clarification,
tool-call-only routing, source-policy instructions and placeholder rejection.
Fresh root: `data/dfm12/multilingual-routed-v5-20260927`.
One run is planned: all 228 inspected controls are now explicitly exposed
regressions, plus 14 paired new required-argument variants with changed values
and call IDs. These variants are related-template checks, not independent native
language gold. No repeated tuning against their outcomes is planned.
The V4 implementation snapshot remains under its `implementation-at-run/`;
no old pinned root is silently repinned for resumption.
After freezing and endpoint revalidation, V5 client **3521018** launched against
the borrowed `8600` endpoint at concurrency two. All 242 requests fit the 8K
context, maximum 6,231 tokens including output allowance. `status.json`,
`progress.json`, `client.log` and final `report.json` are under the V5 root.
This is the single planned rerun; no further prompt adjustment is being made
while its implementation pins are live.

## Tool Repair Live Check, 2026-09-27

Under the renewed pilot audit-fix request, the parent-agent implementation uses
opt-in `tools4096` / `tool-evidence-v4` in `dfm12/multilingual_review_tools.py`.
The dict/string mismatch also affected actual `multilingual_tasks.py` generated
conversations, not just synthetic controls. Old roots and implementation
snapshots are preserved; changed shared routing pins deliberately invalidate
old resume checks. No old receipt was rewritten to conceal that drift.

V4 accepts dictionary arguments and JSON object strings without changing the
candidate. It rejects duplicate keys, NaN/Infinity and nonfinite dictionaries;
checks declared schemas, argument types/minima/additional properties, known
functions, unique call IDs and call/result linkage; rejects external schema
references and uses a no-retrieval registry. Quantity/identifier meaning still
requires correct independent review, not merely valid JSON types.

Canonical assistant evidence carries absolute message indices and JSON pointers.
Quotes must be exact substrings; **no model-generated character offsets** are
required. CPU code stores matching offsets. Compact grammar enforces eight
disjoint flag combinations: every false dimension requires its own structured
issue, every true dimension requires null. The rubric permits empty-content
tool calls and final JSON without an invented prose requirement. Hyphen bullets
are valid unless the request explicitly specifies another marker.

**107 tests passed** in `data/dfm12/multilingual-tools-v4-final-tests.xml`, covering
the 14 former tool-positive vetoes, representation equivalence, malformed JSON,
real schema failures, external-reference rejection, pointers/substrings, CPU
offsets and mandatory per-dimension issues.
The parent independently ran `tests/test_dfm12_multilingual*.py`: **182 passed
in 12.45 seconds**, with two dependency deprecation warnings only. This is the
comprehensive parent-reported verification; the local pinned XML above covers
the focused 107-test run. No further prompt tuning will use the fresh control
outcomes in this turn.

Fresh immutable root: `data/dfm12/multilingual-tools-v4-20260927`.
`manifest.json` pins code and requests; `cpu-checks.json` binds passing tests and
the endpoint model inspection. **228 controls** comprise 172 explicitly exposed
regressions plus 56 fresh paired two-call cases for identifier, quantity,
argument-schema and result-link failures across seven languages. Fresh cases
use new trajectories/failure locations but related native instruction templates;
they are not independent native-language gold or a claim to eliminate all
task-family exposure. Maximum measured prompt plus output: **6,153/8,192**.
No fresh semantic outcomes informed the frozen contract.

Detached client **3509851** started after tests and freezing, borrowing only
`http://127.0.0.1:8600/v1` at concurrency two, zero retries. Inspected server PID
`3485412` serves Gemma 26B with a 16K context. No server was launched, stopped or
reconfigured; EMA sampling and unrelated audits are untouched. Lifecycle:
`status.json`; progress: `progress.json`; log: `client.log`; results: `report.json`.
The report separates reviewer-only and effective deterministic/reviewer scores,
per-language format/decision/dimension outcomes, raw reviews and CPU evidence
offsets. This corrects the masking of tool discrimination by the v3 unconditional
veto; its zero-false-accept statistic is not evidence of reliable tool review.
No live success is claimed until all gates pass. The calibration client cannot
generate pilot rows or resume training.

## Independent Tool Reviewer Code Review, 2026-09-27

Independent CPU probes identified duplicate-key/NaN false accepts and a remote
JSON-schema retrieval attempt in the initial tool-aware reviewer. The owner
fixed these with strict argument parsing, non-finite rejection and non-fetching
schema resolution. The final bounded suite passes 22 tests; combined tool,
structured, evidence and trial suites pass 88. Pointer plus exact substring
checks require no model-generated character offsets. Report and exact pins:
`data/dfm12/multilingual-review-tools-independent-20260927-v1/`.

**Initial compatibility finding superseded by user clarification, 2026-09-27:**
adding `tools4096` changes caller hashes pinned by old roots, including
indexed-v3/trial700. Those roots are deliberately failed and immutable, not
active resumable pilots. Their failed resume checks are an expected boundary:
do not resume or repin old roots; prepare a fresh root for the new variant.
The earlier rollback/isolation recommendation is withdrawn. This is explicit
new-version integration, not hidden mutation of prior results. The active
`european_stage` audit path is independent; no active production impact is
identified. Main audit and old reviewer modules are unchanged. No GPU or
active process was modified, and this review has no remaining blocking finding.

## Rejection Root Causes, 2026-09-27

Read-only analysis of the indexed-v3 full 172-control report found 15 false
rejections: two each for nb, nn, is, fo, nl and sv; three for pl. Fourteen are
the positive tool_quantity/tool_schema controls (two per language). All fourteen
are rejected by `deterministic_checks`, which accepts only JSON-string tool
arguments, while these controls contain dictionary-valued arguments. Eleven
also have reviewer-level rejections for an invented requirement to reply in
natural-language prose rather than JSON. Three (both Icelandic tool positives
and Dutch tool_quantity) have all reviewer flags true and fail only the
deterministic representation check. The remaining false rejection is a Polish
two-bullet answer, where the reviewer mistakes valid hyphen bullets for a
violation. These are shared representation/rubric problems, not evidence of
fifteen independently bad native-language judgments.

Six invalid reviews comprise four quote-provenance errors (nn, is, fo, nl
tool_quantity negatives) and two missing per-dimension issue entries (is
bullet_count positive, pl tool_quantity negative). Quote failures include
invented function-call notation, a user quote attributed to an assistant, and
an empty quote. Some invalid reviews have additional defects after the first
reported validation error.

Recommended next repair, not yet implemented by this analysis: validate both
actual supported argument representations as JSON objects without allowing
arbitrary strings; judge tool schema/quantity separately from prose language;
require only explicit output constraints; supply canonical indexed evidence
spans or JSON paths for tool calls; and rerun matched positive/negative controls
plus fresh controls. Zero observed false accepts here is not a safety proof:
the broken representation check also rejects negative tool controls regardless
of reviewer competence. No guarantee of unchanged false-accept rate is possible
without remeasurement after repair. Historical reports remain unchanged.

## Authorized Live Replay Blocked, 2026-09-27

**Final bounded result:** the full measurement-only probe has finished and
failed: **151/172 keep/reject agreements, zero false accepts among valid reviews,
15 positive rejections, six invalid reviews** (166 valid). Of the valid reviews,
**25 controls have at least one labeled dimension mismatch**, independently
counted from the saved reviews and control labels. The report's
`dimension_failures: ["invalid-review"]` is a sentinel, **not one mismatch**.
Development remains 8/8 keep/reject, 7/8 all-dimensional, zero format failures.
Probe PID `3479711` has exited; all 172 raw responses are retained. The earlier
160/172-running snapshot below is superseded by this final result.
Final machine-readable handoff:
`data/dfm12/multilingual-second-indexed-v3-20260927/final-blocked-handoff.json`.
No 700/35K or quarantine generation ran; zero new rows/tokens. No further tuning
or launches were performed. The identity EMA successor remains waiting.

**Attribution correction, 2026-09-27:** earlier wording attributing the detailed
repair sequence or blocked handoff directly to the user is superseded. The user
requested the second multilingual pilot and the EMA corpus afterward. Technical
repair choices, diagnostic sequencing and the blocked handoff were parent-agent
implementation decisions under that pilot request. The blocker is an observed
gate failure, not a user instruction to block the pilot. Frozen historical
receipts retain their original text; this correction governs its interpretation.

**Latest parent-agent v3 repair decision:** indexed-v2 completed with correct indices on
all eight controls and correct decision/dimension flags, but only 5/8 passed
because three natural numeric explanations failed the arbitrary 24-character
translation minimum. A parent-agent implementation decision replaced that minimum
with at least eight alphabetic letters, retaining the 600-character ceiling,
exact indexed candidate quotes, placeholder/generic-approval rejection and all
semantic gates. No issue-explanation bounds or semantic labels changed.
`structured-issues-indexed-v3` implements that validator correction; natural
"The number fifteen." / "The number 17." pass, while bare digits, N/A and
generic approval still fail. **92 tests passed** in
`data/dfm12/multilingual-second-v3-final-tests.xml`.
New freeze: `data/dfm12/multilingual-structured-indexed-v3-freeze-20260927`.
New execution/receipt root: `data/dfm12/multilingual-second-indexed-v3-20260927`.
The v2 raw responses and implementation snapshot are preserved in their prior
root; no v1/v2 completion receipt was changed.

Live v3 replay (runner PID `3479129`, now exited) produced **8/8 valid formats,
8/8 correct keep/reject decisions, but 7/8 complete dimension agreement**.
Polish source injection was correctly rejected for meaning, while its explicit
source-only constraint was incorrectly marked satisfied. The runner therefore
stopped at `development8`; no trial generation was authorized.
The earlier requirement to pass development before *any* full calibration is
superseded only for diagnostic measurement: a separate measurement-only probe
PID `3479711` runs all 172 frozen controls to report language/dimension failures,
without authorizing generation even if it passes. It borrows endpoint 8600 at
concurrency two. Log: `full-calibration-measurement.log`; lifecycle:
`calibration/probe-status.json`. The blocked completion receipt is preserved;
`successor_authorized` remains false. No further prompt tuning or 31B launch is
part of this measurement run.

The parent agent requested a **blocked handoff**, reporting the observed failure
under the pilot request rather than undertaking further control tuning.
Finish the already-running bounded full probe for diagnostics only. Do not
implement or run a quarantine-700 experiment, admit a 35K pilot, or seize GPUs
for the identity successor. The successor remains waiting; any next experiment
requires a separate decision. Correct Polish rejection does not excuse its
incorrect independently labeled constraint dimension.

Parent handoff snapshot: `multilingual-second-indexed-v3-20260927/blocked-handoff.json`
records **92 passing tests**, development **8/8 keep/reject**, **7/8 all-dimensional**,
**zero format failures**, and zero new pilot rows/tokens. Orchestrator PIDs
`3470513`, `3475214`, and `3479129` have exited. The already-launched bounded
measurement probe PID `3479711` was still active with 160/172 raw responses at
the final status inspection; its authoritative final lifecycle/report are
`calibration/probe-status.json` and `calibration/review-calibration.json` under
the v3 root. This probe cannot generate or authorize data. The parent requested
handoff now, with no additional tuning or launches. European audit PIDs
`3460253` and `3462723` remained alive and untouched. The identity EMA successor
must remain waiting; neither file existence nor probe completion grants GPU
ownership or overrides the blocked development gate.

**Parent-agent follow-up decision the same day:** one finite technical
repair/replay rather than stopping at the recoverable index mismatch. The v1
failure below remains immutable evidence. Its complete multilingual implementation
snapshot is retained under `multilingual-second-20260927/implementation-at-run/`.
New `structured-issues-indexed-v2` exposes explicit absolute assistant indices,
constrains both top-level and per-issue indices to the record's actual assistant
indices, and requests explanatory English sentences for numbers/code rather
than copying bare answers. The previous integer grammar allowed zero; it did
not force zero. Validator thresholds and semantic control labels are unchanged.
No heldout semantic examples were used. **90 CPU tests passed** including enum
enforcement, original message preservation and multi-turn indices.
Freeze: `data/dfm12/multilingual-structured-indexed-v2-freeze-20260927`, with all
172 requests budget-checked (maximum 5,687 tokens including output allowance).
New execution root: `data/dfm12/multilingual-second-indexed-v2-20260927`.
Its separate `completion.json`, not the old failed receipt, is the successor
handoff for this one repaired replay. Semantic failures still block advancement;
this implementation decision does not permit unlimited development tuning.

The user requested the second pilot now and the EMA corpus afterward. The
parent-agent implementation sequence was frozen repaired development controls,
full calibration, a gated 700-slot trial, then the intended 35K pilot if all
preceding gates pass; **no training resume**. This supersedes the CPU-only wait
below, not its semantic admission requirements or the historical failure record.

At inspection all eight GPUs belonged to an unrelated active European audit:
campaign PID `3460253`, audit client `3462723`, teacher endpoints `8600..8607`.
None was stopped or reconfigured. With endpoint reuse permitted by the parent agent,
the detached pilot orchestrator borrowed only `http://127.0.0.1:8600/v1` at
concurrency two. Its served 26B model matched the frozen contract, and its
16,384-token server context exceeded the locally enforced 8,192-token request
budget. No new GPU server or 31B model was launched.

Runner `dfm12.multilingual_second_run` was launched as PID **3470513** and has
exited after the fail-closed development gate. Root:
`data/dfm12/multilingual-second-20260927`; log: `orchestrator.log`.
Fresh CPU verification: **89 tests passed**, recorded in
`data/dfm12/multilingual-second-20260927-tests.xml`.
The original frozen structured reviewer implementation hashes still matched.
Separate new `trial700` and measurement-only `calibration` roots were prepared
and certified before replay; historical failed roots were not modified.

**Live result: 0/8 format-valid reviews; all eight rejected by exact indexed
candidate evidence validation.** Every response emitted `message_index: 0`,
which identifies the user turn in these controls rather than the assistant.
Most quotes were actual assistant text with the wrong index; the Faroese quote
was the user instruction itself. Three positive arithmetic/source-number
reviews also emitted bare numeric back-translations, insufficient under the
frozen meaningful-evidence contract. The Faroese raw flags approved a known
negative, and the Polish raw constraints flag missed its labeled violation.
These raw flags are diagnostic observations, not valid semantic-review scores:
invalid evidence must not be counted as a calibration pass or repaired after
the fact. Full per-language format/decision/dimension reports and all eight
raw HTTP responses are retained under `development/`.

Full 172 calibration, 700 generation and 35K generation **did not run**.
No semantic threshold, quote-index rule or meaningful-evidence check was
relaxed. Zero new pilot rows; no training restart. Subsequent work needs another
explicit development repair/freeze, not an automatic large-model escalation
for what is primarily an evidence-contract failure.

### Successor Receipt

`data/dfm12/multilingual-second-20260927/completion.json` is the exact handoff
receipt for the identity EMA stochastic successor. Current values:
`status: blocked`, `failed_stage: development8`,
`pilot_client_released: true`, `borrowed_servers: true`,
`gpu_released: false`, `successor_authorized: false`.
The false GPU-release flag reflects the still-running **foreign European audit**,
not leaked pilot servers; this pilot never owned servers. The pilot process is
gone, and both foreign campaign/client PIDs remained alive after it exited.
Do not launch a successor merely because the receipt exists: a successful
pilot handoff requires `status: passed` and `gpu_released: true`. Any decision
to proceed after this failed gate belongs to the parent, with independent
coordination of the audit's eventual GPU release. No unrelated process may be
stopped by this runner.

## Parent-Agent Follow-Up, 2026-09-26

Parent-agent implementation guidance proposed the repair sequence below and a
language-scoped 31B comparison, superseding its earlier blanket exclusion.
This operational guidance is not a record of separate direct user approval.
Keep Gemma 4 26B as the default;
use Gemma 4 31B only for languages whose semantic calibration failures warrant
escalation, not for all languages. Record per-language format validity, false
accepts, false rejects and dimension agreement before choosing that routing.
Freeze the revised evidence contract and rerun calibration before admitting
new pilot data; a schema fix alone is not semantic validation. Replace heldout
controls if their semantic outcomes informed tuning.

CPU implementation/preparation may proceed during the third XL identity
interlude. Do not interrupt its training or the queued post-1K identity test,
and do not start competing GPU teachers without checking available resources.
The existing identity evaluation and automatic XXL continuation remain intact.

## Structured Repair Prepared on CPU, 2026-09-26

The parent-agent repair decision is implemented as opt-in `structured4096`, contract
`structured-issues-v1`, in `dfm12/multilingual_review_structured.py`. Historical
flat evidence variants and artifacts remain unchanged. This supersedes the
earlier requirement for an owner decision about mechanical quote repetition:
the approved replacement uses separate structured evidence fields, not a weaker
semantic acceptance threshold.

Each issue has `dimension`, zero-based candidate `message_index`, exact `quote`,
and `explanation`. Quotes must occur in the indexed assistant message or its
tool arguments. Each false dimension needs exactly one issue; true dimensions
cannot have issues. Literal translation and explanations must be meaningful
bounded text. Explanations need not mechanically repeat their quote. Compact
grammar, independent boolean criteria, thinking disabled, raw response capture,
4,096 completion tokens and the measured 8,192 context limit are retained.
Format validation cannot prove that an explanation or translation is correct.

Deterministic checks are deliberately narrow: where `source_messages` exist,
candidate turn roles/count must match; present tool-call arguments must parse
as JSON objects. Failures prevent acceptance, and non-applicable checks are not
invented. These checks do not infer arithmetic, factual or native-language truth.
The complete calibration still requires every decision and labeled dimension
to pass. The structured variant's reports separate invalid/missing format,
false accepts, positive rejections and dimension agreement by language/split;
development reports include the same scoring under `calibration_by_variant`.

CPU verification: **83 tests passed**, including legacy compatibility, compact
grammar/escaped strings, message indices, fabricated quotes, independent issue
dimensions, deterministic rejection and structured scoring. Test receipt:
`data/dfm12/multilingual-structured-v1-cpu-tests.xml`.
Frozen preparation root:
`data/dfm12/multilingual-diagnostic-20260926-structured-v1-cpu`.
Its `manifest.json` pins implementation, tokenizer and eight development requests;
`contract-freeze.json` additionally binds tests and all 172 measured requests in
`full-calibration-requests.json`. These are **unevaluated CPU artifacts**, not a
pilot admission receipt. Historical failed roots must not be repinned/resumed.

### Deferred Execution Proposal

Do not launch while the third XL identity interlude, its evaluation, or automatic
XXL continuation needs the GPUs. Require explicit resource-owner release and a
fresh memory/process check; completion of identity alone is not such release.
No scheduler, identity plan or automatic teacher launcher was changed.

After that release, the existing diagnostic CLI supports a fresh live root:

```bash
python -m dfm12.multilingual_diagnose \
  --root data/dfm12/multilingual-diagnostic-structured-v1-live \
  --variant structured4096 --concurrency 2 \
  --endpoints http://127.0.0.1:8590/v1
```

Check the frozen implementation pins before execution. First require 8/8
development/regression controls; then prepare a separate measurement-only full
calibration root using `multilingual_prepare_calibrated --review-variant
structured4096` and the existing `multilingual_calibration_probe` API. Certify
that new root after its configuration is final. Do not automatically chain the
700-row trial; require full calibration success first. Raw responses and each
stage's per-language report must remain separate. No heldout semantic cases
informed this contract repair; if subsequent tuning uses them, replace the
holdout before any admission claim.

26B remains the only implemented/default model route. Propose a separately
pinned 31B comparison only for languages with persistent **semantic** failures,
not merely format errors; no blanket escalation or silent language removal.
No live repair evaluation or generation has run: **zero new pilot rows**.

## Current Disposition, 2026-09-26

**Supersedes the CPU-only/unevaluated handoff status below.** Subsequent live
diagnostics used only `google/gemma-4-26B-A4B-it`, with concurrency two against
the separately authorized TP2 teacher on port 8590. No 31B reviewer was used.
The original unevaluated CPU artifacts and failed pilot roots remain intact.

- Raw replay demonstrated repetitive whitespace in length-terminated structured
  output at both 1,024 and 4,096 tokens. This establishes the replay failure
  mechanism, not the unrecoverable raw cause of all 142 earlier truncated calls.
  Redundant replay was explicitly stopped with partial results preserved.
- A compact request-level JSON grammar removed flexible inter-element
  whitespace and achieved 8/8 development/regression decisions. Six reviews
  still contained placeholder evidence; this was a technical decoding result,
  not sufficient quality evidence or permission to generate.
- Full measurement-only calibration in
  `data/dfm12/multilingual-pilot-20260926-grammar700` **failed**: 152/172
  decision agreements, nine parse errors and 11 decision disagreements;
  16 controls also failed labeled dimensions (overlapping counts). All 172
  responses finished with `stop`, so these errors were not length termination.
  Agreement was 107/112 development, 41/56 heldout and 4/4 regressions.
- Evidence-first development variants require a literal candidate quote,
  non-placeholder back-translation and issues consistent with false dimension
  flags. Only the fixed eight development/regression controls informed these
  revisions; heldout semantic outcomes were not used for prompt tuning.
  Latest `evidence-first-flat-v4` reached **7/8**, not a calibration pass.
  The remaining Icelandic review correctly rejected `fela j` and translated it
  as "hide j", but its issue repeated only that short span rather than the
  entire `literal_quote`, violating the current exact-quote contract.
  That validator has not been weakened; no subsequent full calibration ran.

**Admission remains blocked: zero new pilot rows and zero added training
tokens.** Further work needs an explicit evidence-contract decision followed
by complete calibration under unchanged admission requirements; no automatic
700-row run or bulk resume is authorized by these results.

The owned teacher was cooperatively stopped after requests drained. Supervisor
status is `stopped`, reason `stop_requested`, with `survivors: []`; subsequent
process/port checks confirmed no pilot clients or teacher and port 8590 closed.
Training was not signaled. Teacher resources are released for the parent-owned
identity interlude; no additional GPU work was launched for this status update.

Audit evidence: `data/dfm12/multilingual-diagnostic-disposition-20260926.json`,
the full probe's `review-calibration.json`, latest development
`data/dfm12/multilingual-diagnostic-20260926-evidence-flat-v4/report.json`, and
`data/dfm12/multilingual-diagnostic-20260926/server/cleanup.json`.
The disposition inventories 236 requests and 235 persisted raw responses,
with one explicitly cancelled request of unknown partial usage. Observed
256,610 reviewer tokens are diagnostic usage, not training additions.
Final implementation verification: **168 tests passed**; report at
`data/dfm12/multilingual-diagnostic-20260926-final-tests.xml`.
See the [extension plan](/pages/dfm12-multilingual-extension-plan.md) for
individual replay roots, commands and development iterations.

## Post-Identity Failure Diagnosis, 2026-09-26

### Proposed Next Repair After Status Review

The remaining flat-v4 Icelandic failure is an evidence-contract defect, not a
wrong keep/reject decision: the explanation quotes `fela j` while the validator
requires the entire sentence in every issue. Proposed replacement: structured
per-issue dimension, candidate message index, exact candidate quote, and a
meaningful explanation. Validate quote membership in that message and alignment
with the false dimension; do not require redundant full-sentence copying into
free-text explanations. Keep placeholder rejection and compact grammar.

This is a proposal, not an applied validator change. Freeze the revised contract
before another full calibration; report transport/format validity, false accepts,
false rejects and dimension agreement separately. Do not treat a format-only
repair or the eight-case development probe as proof that the older full-suite
semantic errors are fixed. Use deterministic checks for arithmetic, JSON/tool
schemas and explicit output constraints where applicable; reserve model judgment
for linguistic and semantic questions. If semantic failures persist, compare the
31B reviewer on the same development protocol rather than relaxing admission.
Any semantic tuning informed by heldout cases requires a fresh final holdout.

The subsequent live calibrated700 run returned 30 complete reviews out of
172 controls. The other 142 ended with `finish_reason=length` at the 1,024
output-token ceiling. Of 85 positive controls, 79 truncated; of 87 negatives,
63 truncated. Completed decisions matched 29/30 labels, but this survivor
subset must not be reported as calibration accuracy. Some complete rejections
had empty issues and `back_translation=N/A`, so completeness alone does not
establish useful evidence.

Correction to the earlier phrase "exhausted requests": the current client
raises `ValueError` on length termination, outside its retry exception list.
These are truncated calls, not evidence of repeated attempts at larger budgets.
It discards the raw response on that path; server logs do not recover its text.
We therefore cannot distinguish verbosity, repetition/whitespace loops or a
structured-decoding problem from existing artifacts. No OOM is established.

Recommended repair sequence (not a new GPU launch):

1. Persist each raw response, finish reason, usage, request parameters and
   attempt ID before parsing, including truncated responses. Preserve the
   existing calibration artifacts rather than overwriting them.
2. Replay a small development/regression subset, positive and negative, with
   1,024 versus 4,096 output tokens and a compact bounded schema. Keep total
   prompt plus output inside 8,192. Compare structured JSON with unconstrained
   diagnostic output if needed, and compare live server tokenization to the
   saved local render. Do not assume disabled-thinking was ignored.
3. Bound evidence length and issue count, require literal evidence for negative
   judgments, and keep source meaning separate from candidate meaning. Increase
   budget only for genuinely unfinished useful output, not repetitive loops.
   Add a bounded length-specific retry only after that behavior is measured.
4. Rerun complete calibration with unchanged acceptance requirements. Keep
   held-out cases out of prompt tuning; replace held-out cases if tuning used
   their semantic outcomes. Only then permit the 700-slot trial.

XXL has resumed. The 26B teacher alone loaded about 47.47 GiB in the prior server
log, exceeding the roughly 45 GiB free per training GPU at inspection; do not
start another such teacher beside live training without a new resource plan.

## Scope and Evidence

Historical parent-agent follow-up guidance selected items 1, 3, 4 and 5,
excluding the stronger 31B reviewer. Both review passes still use
`google/gemma-4-26B-A4B-it`. See the
[extension plan](/pages/dfm12-multilingual-extension-plan.md) for the failed
four-control startup calibration and zero generated second-pilot rows.

That failure included semantic repair: the Icelandic candidate contained
`fela j`, but its review back-translated this as `isolate j` and accepted it.
The unsupported current bus-ticket rule was also accepted. Those historical
receipts and the four original controls are unchanged. The new prompt requires
an exact candidate quote and literal English meaning, separately labeled source
intent, and independent language, meaning and constraint judgments. It forbids
silently repairing verbs, negations, numbers or unsupported policy claims.
`review_request`, its JSON response schema and `review_keeps` retain their APIs.
Prompt improvements are not evidence that this reviewer is now reliable.

## Controls and Splits

`dfm12/multilingual_calibration.py` supplies **172 diagnostics**: 168 new paired
controls (12 families, positive/negative, seven languages) plus the four original
regressions. The families cover arithmetic, source numbers, unit conversion,
code constants, tool quantities, unsupported policies, exact identifiers, bullet
counts, source prompt injection, multi-turn updates, source negation and tool
argument schemas. These are not merely arithmetic restatements.

- Development: 112 controls.
- Heldout: 56 controls, entire unit-conversion, tool-quantity, tool-schema and
  follow-up-update families, including cross-language and paired siblings.
- Regression: four unchanged historical cases, reported separately.

Heldout cases are never few-shot prompt examples and must not guide prompt
tuning. Reviewer input contains only the candidate record, not expected labels,
polarity or split. Negative labels mark only decisive violated dimensions;
other dimensions are null, not forced true. Positives carry diagnostic task
labels. All language-correctness labels remain null. Authored native-language
instructions, particularly FO/IS, have **not** received native review. Neither
these controls nor their eventual aggregate accuracy establish broad language
quality. Results expose missing/invalid reviews, false accepts, positive
rejections and dimension agreement separately by split and language.

## Completed CPU Inspection

Root: `data/dfm12/multilingual-calibration-20260926-v2`.
The actual locally cached Gemma teacher tokenizer/template rendered all 172
controls and 42 saved first-pilot candidates, one per language/family. Maximum
prompt lengths were **992** and **2,429** tokens respectively, each with 1,024
completion tokens reserved against the 8,192 teacher context. This does not
validate a running server's effective configuration.

The canonical template trims outer system whitespace, removing REVIEW's final
newline. The inspector records that exact/trimmed distinction; substantive
system content, independent criteria, literal-evidence instructions and the
complete serialized candidate JSON survive. Token IDs match encoding of the
saved render. The final closed empty thought prefix is expected with
`enable_thinking=false`, not evidence that reasoning was enabled.

Current `multilingual_pilot.audit_record` retains grounded source passages inside
messages, with explicit fields for OpenHermes sources, references and scenarios.
All 21 native-source records in the 42-record saved sample retained their exact
passage in messages and rendering. This is a bounded serialization inspection,
not a corpus-wide grounding or quality certification. `multilingual_pilot.py`
was not edited by this work; Poincare owns integration.

Artifacts include `controls.json`, `split-manifest.json`,
`report-unevaluated.json`, `render-inspection/{requests,renders}.jsonl`,
`render-inspection/inspection.json`, and equivalent saved-candidate rendering
under `saved-pilot-inputs/`, including file/line/ID/hash provenance.
The earlier `v1-before` and `v1` failed-attempt folders are retained, not usable
completion artifacts: they exposed a tokenizer BatchEncoding return type and
the final-newline trim respectively.

## API and Handoff

Public helpers: `calibration_cases()`, `score_reviews(cases, reviews_by_name)`,
`prepare(output, tokenizer_dir)`, `inspect_render(cases, output, tokenizer_dir)`,
and `inspect_pilot_inputs(pilot_root, output, tokenizer_dir)`.
The `prepare` CLI accepts `--output`, `--tokenizer-dir` and optional
`--pilot-root`; `score` accepts `--controls`, `--reviews` and `--output`.
No helper starts inference, GPUs, servers, schedulers or training.

Handoff receipt:
`data/dfm12/multilingual-calibration-20260926-v2/handoff-poincare.json`, addressed
to `01a0d277-f35a-71f2-a233-c9a32bd766af`, contains implementation/artifact pins.
Direct agent messaging was unavailable; the API was relayed through parent.
Code is ready for parent/Poincare to pin. Parent owns the index/status update.

Historical CPU handoff verification (superseded as current status by the live
results above, 2026-09-26): **89 tests passed**, with two dependency deprecation warnings,
across calibration, references, review, pilot, targets, trial and watcher tests.
The four regressions and native-reference tests remain compatible. At that
handoff no GPU calibration had run; `report-unevaluated.json` marks all reviews
missing, model evaluation false and admission unauthorized.

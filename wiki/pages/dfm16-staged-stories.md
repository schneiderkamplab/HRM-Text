---
type: Runbook
title: SimpleStories staged generation and independent language qualification
description: Versioned controlled generation, matched development comparisons, and per-language acceptance gates.
tags: [dfm16, simplestories, generation, audit, qualification]
status: draft
last_updated: 2026-10-30
confidence: high
---
# Staged generation and independent qualification

This implements the follow-up to the failed [role/source pilot](dfm16-role-source-pilot.md).
Historical scope: this experiment did not authorize production admission.
**Superseded for English, 2026-10-30:** the user explicitly authorized
[production](dfm16-english-production.md); statistical qualification remains failed.
Historical datasets and experiment receipts remain immutable.
Manual references remain **provisional assistant-manual assessments**, never independent
human certification. Danish, English, Hindi and Japanese must qualify separately.

Original matched development experiment: `data/dfm16/staged-stories-v3-20261029`.
Latest English result: [v7 failed untouched validation](#english-untouched-validation-completed-audit-fails-2026-10-29).
Latest completed follow-up: [source-scope-corrected specialist results v13](#corrected-specialist-results-v13-2026-10-30).
Archived development: `data/dfm16/staged-stories-v2-20261029`.
The earlier `staged-stories-v1-20261029` retains an 80-case synthetic protocol smoke
and a preliminary control bank. Eight repeated whole examples per language were found
in that preliminary bank. **Superseded 2026-10-29:** v2 contains 80 distinct whole
control conversations per language, arranged as 40 clean/defective pairs. No preliminary
controls were judged. Lexical control variants remain correlated synthetic evidence;
they are not independently sampled population observations.

## Implementation

[Controller](../../scripts/dfm16_staged_experiment.py) uses the existing
`audit_pipeline.run` continuous queues, off-loop parsing, disk owner and chunk receipts.
Its matched adapter randomizes all 320 jobs and routes them to existing Flash-Next,
Qwen 27B and Odin endpoints. It does not start or modify inference servers.
Local HTTP concurrency is at most 128 per server; Odin is at most 64.
The [transport](../../scripts/dfm16_experiment_transport.py) records every Odin send
reservation in a SQLite ledger shared by discovery, generation, audits and retries,
with a 100-per-rolling-minute cap. A controller lock prevents competing campaign
clients. v2 inherits v1's send history; do not restart v1 concurrently.

[Staged generation](../../scripts/dfm16_staged_stories.py) supplies three native
request variants per language/task, reviewed source slots, authoritative source text,
plain model answers and code-built conversations. Source-based prompts insert the
reviewed source verbatim. Revision calls request only the changed paragraph; student
requests ask for complete stories assembled by code. Stored versions implement exact
preservation and selective undo. The ending's allowance also reserves space for the
original opening that will be restored. Every revision request retains explicit limits.
Words use whitespace separation; Japanese counts non-whitespace Unicode code points,
including punctuation. Sentence boundaries are left to semantic review.

All generators use temperature 0.3, non-thinking, and 6,144 completion tokens. Odin
uses `reasoning_effort=none`, `include_reasoning=false`, and
`max_completion_tokens`. Reviews require exactly stripped `accept` or `reject`,
32 completion tokens, no schema, and at most one retry. Generation permits one
objective correction per conversation; semantic disagreement is never auto-repaired.
Malformed/truncated responses and exhausted transport retries remain unresolved.
An interrupted dispatch without a response receipt remains unresolved rather than
being silently sent again. Completed stage responses, findings and versions are pinned
in the final chunk receipt; restarts verify them before skipping completed work.

[Audit checks](../../scripts/dfm16_staged_audit.py) name one target and distinguish
background seed, authoritative source, current request and preceding answers. Source
language/coherence, request validity, answer language/coherence/fidelity and semantic
obligations are separate checks, aggregated once per complete conversation. Missing
required verdicts remain unresolved. [Policy selection](../../scripts/dfm16_staged_policy.py)
excludes the generator from acceptance judging.

## Source process and development

80 additional families have been inspected and assigned once: 20 per language,
four per task. All earlier source pools are conservatively excluded, including
uninspected rows in those pools. Source provenance, pool hashes, 220 inspected
candidate-family records, explicit rejections, native slots and source-edit lineage
are retained under `sources/`.

English and Japanese use inspected original source text. Danish uses one Flash
translation of an English seed followed by manual inspection and recorded edits.
The inspected raw Hindi candidates contained severe corruption and often
unintelligible clauses. They were not repaired by guessing. For Hindi, the readable
English counterpart of the **same source family** was inspected, translated once,
and manually reviewed/edited before becoming authoritative. Original Hindi, English,
first translations and edit lineage are preserved. A future Hindi conclusion applies
to this translated-and-manually-reviewed source process, not raw Hindi admission.

The controlled sources are frozen before task generation. Manual source editing here
is source preparation, not a repair of generated training conversations. There are no
judge outcomes exposed during complete-example manual labeling.

Development arms: matched legacy Flash whole-conversation generation and staged
Flash, Qwen, Odin. Advancement requires 16/20 first attempts clear, at least 3/4 in
each task, more clear examples than legacy, and no deterministic violation admitted.
Cost per clear example then throughput break ties. Local API charges are zero;
GPU cost remains unpriced and must be disclosed separately from remote API estimates.

## Validation gates

[Qualification rules](../../scripts/dfm16_language_qualification.py) and
[freeze/cohort receipts](../../scripts/dfm16_staged_validation.py) retain the original
under-5% false-acceptance and at-most-20% clean-withholding targets. Select among the
other judges individually, both accepting, or either accepting, using development
outputs plus frozen 40-pair controls for that language. No passing policy means stop
that language before validation.

Freeze generator, source process, templates, prompts, parser, correction budget,
software, labels, votes and exclusion evidence. Draw 800 untouched families per
qualified development language, 160 per task. Require 300 clear and 100 definite
bad examples. One separately reported 800-example supplementary cohort is allowed
only from a predeclared blinded class-count trigger. There is no repeated favorable
sampling. One-sided exact 95% upper bounds must meet both targets; a failing task
point estimate holds the language even when pooled bounds pass. Failed validation
becomes development data; changed policies need new untouched samples. A pass creates
a reviewable candidate manifest, not a production promotion.

## Verification and status

66 focused, existing role/transport/controller, and shared-runtime tests passed:

```bash
PYTHONPATH=. /home/ucloud/miniforge3/envs/hrm/bin/python -m pytest -q \
  tests/test_dfm16_staged_stories.py tests/test_dfm16_role_pilot.py \
  tests/test_dfm16_odin_judge.py tests/test_dfm16_context_driver.py \
  tests/test_audit_pipeline.py
```

The v1 live smoke finished all 80 cases with verified receipts in 16.2 seconds.
First-attempt deterministic passes were legacy 13/20 and each staged model 14/20.
These tiny synthetic sources deliberately exercise short length/paragraph limits;
this is protocol evidence, not manual semantic quality or qualification evidence.
Recorded Odin usage, including discovery, was 28 sends and an estimated 0.04898125 DKK
at the previously retrieved 2026-10-28 list prices; local GPU costs are excluded.
Sources required another 40 local Flash translation requests in v2.

**Superseded by the dated results below:** The 320 matched development jobs were prepared. Per-language qualification was still
held pending blinded complete-example labels, development selection and any permitted
untouched validation. No validation families have been consumed and no production
policy has changed. Inspect `status.json`, generation receipts and subsequent dated
outcomes below; do not interpret a completed transport run as a qualification pass.

Repository-wide OKF baseline before these edits: one unrelated oversized concept
(`request-shared-eval-scheduler.md`, 51,441 bytes) and 15 existing missing-link warnings.


## 2026-10-29 development results and user amendment

v2 completed all 320 attempts over 80 families in 52.9 seconds. Full accounting is
in `reports/development-complete-report.json`: 184 provisional semantic conversation
reviews, 54 deterministic-evidence-only defective classifications, and 82 protocol-only
unresolved classifications. First labels: 119 clear, 108 definite defective, 11 borderline,
82 unresolved. Final labels: 122 clear, 102 defective, 14 borderline, 82 unresolved.
The earlier partial diagnostic report is retained and superseded only for label coverage.

All staged arms failed the original 16/20 necessary condition. Odin's 80 unresolved
rows arose from reported reasoning-token counts despite non-thinking request settings;
these were not evidence of defective prose. v2's legacy arm also carried extra sampled
constraints and is not a fully matched causal comparison. Hindi topic inflection, a JSON
object envelope missed by deterministic checks, and ambiguous English paragraph-limit
pronouns were found during review. The reviewed Hindi sources retained two definite
agreement errors; these findings supersede their provisional clear source assessments.
All original sources, responses and labels remain unchanged.

**Superseded development gates, explicit user amendment 2026-10-29:** 10/20 clear
first attempts is sufficient for exploratory advancement. Task-family shortfalls and
legacy comparisons are diagnostics, not vetoes. Ignore provider-reported reasoning-token
counts when content is usable. The primary objective is **low false acceptance**;
policy selection prioritizes lower false acceptance before clean retention among policies
meeting the stated error targets. These amendments do not authorize production admission
or turn development results into statistical qualification.

v3 freezes the amended rules, corrected native templates, JSON-envelope check and matched
legacy constraints. It reuses the same 80 development families, with explicit source-edit
lineage for the two Hindi agreement errors. This is repeated development, not an untouched
validation sample. All inspected families remain excluded from future validation.
The stricter original qualification bounds remain implemented; exploratory reviewer
comparisons can continue even when no language is yet qualified.


## Completed exploratory audit comparisons, 2026-10-29

[Configuration report](../../data/dfm16/staged-stories-v3-20261029/reports/configuration-comparison.md)
and its JSON companion contain every policy, cohort/task breakdown, provisional labels,
uncertainty bounds, cost and throughput. All 320 v3 outcomes are classified: 175 new
semantic conversation reviews, 80 exact-source/full-message matches to prior semantic
reviews, and 65 deterministic-only defect classifications. First labels were 181 clear,
122 defective and 17 borderline; final labels were 192 clear, 110 defective and 18
borderline. The relaxed development selection chose Flash for Danish and Odin for
English, Hindi and Japanese. All acceptance reviewers exclude the generator itself.

The base audit used 2,422 Flash, 3,195 Qwen and 773 Odin checks, aggregated once per
conversation. Uniform paragraph/precondition checks in `staged-stories-precision-v4-20261029`
added 938 checks each from Flash and Qwen for English/Hindi/Japanese. Native sentence-span
checks in `staged-stories-native-v5-20261029` added 1,221 Qwen checks for Danish/Hindi.
Spans are semantic review targets with full context, not deterministic sentence counts.
These follow-ups were frozen separately before their votes; original votes remain immutable.
They are adaptive development refinements, not independent validation.

| Language | Practical development configuration | Accepted definite defects | Clear withheld | Generated-only accepted defects |
|---|---|---:|---:|---:|
| Danish | Flash generator; Qwen+Odin base, plus Qwen native checks | 2/47 | 11/51 | 2/7 |
| English | Odin generator; Flash+Qwen base and paragraph/precondition checks | 0/42 | 6/57 | 0/2 |
| Hindi | Odin generator; Flash+Qwen base/paragraph checks, plus Qwen native checks | 1/49 | 16/50 | 1/9 |
| Japanese | Odin generator; Flash+Qwen base checks | 0/45 | 4/54 | 0/5 |

The first two denominators include 40 synthetic clean/defective pairs per language.
Do not hide the generated-only residual errors behind the larger synthetic controls.
English/Japanese are promising configurations for untouched evaluation; Danish/Hindi
retain substantial uncertainty and generated-example misses. All four remain **unqualified**.
The pooled false-acceptance upper 95% bounds are respectively 12.8%, 6.9%, 9.3%, 6.4%,
and cannot certify the population because controls are correlated and prompts were tuned
on the same examples. No validation cohort or production promotion has occurred.

The cumulative Odin ledger records 1,020 send reservations, maximum 100 per rolling minute,
with 1,001 HTTP 200 and 19 HTTP 429 responses. Bounded retries resolved all final review
votes. Estimated remote cost is 5.05665625 DKK at the historical 2026-10-28 rates; local
GPU cost is unpriced. v3 generation took 101.3 seconds; base audit wall times were Flash
47.3 seconds, Qwen 84.8 seconds and Odin 424.9 seconds. These timings used existing servers.

The user subsequently specified generation/auditing capacity **4/4**, interpreted as four
GPUs each unless corrected. No inference server was moved or restarted. Treat this as the
requested future split, not a measured benchmark; remote Odin retains its separate cap.
All campaign locks are released after completion. 66 tests pass; the OKF baseline remains
one unrelated oversized-concept error and 15 existing missing-link warnings.


## Untouched validation authorized and started, 2026-10-29

The user explicitly chose to continue untouched validation. The active campaign is
`data/dfm16/staged-stories-validation-v7-20261029`: 800 English and 800 Japanese
families sampled after freezing the configuration, random seeds, original source
process and software. Each language has 160 families per task. English uses Odin
generation and conjunctive Flash/Qwen base plus paragraph/precondition checks;
Japanese uses Odin with conjunctive Flash/Qwen base checks. Original qualification
bounds remain unchanged. Danish/Hindi are not included in this validation.

The population is pinned original target-language training stories with 180–900
Unicode code points, excluding historical source pools and all inspected families.
Source review retains original text. Rejected sources remain unresolved in the
sampled cohort; they are not replaced. Complete conversations receive provisional
assistant-manual labels before judge decisions. One supplementary 800-family cohort
per language is allowed only by the frozen blinded-class-count trigger.

The v6 preparation attempt failed before sampling because it referenced a nonexistent
flat supplemental votes file; its partial protocol is preserved. v7 pins the actual
supplemental scored evidence and checks. No v6 families were inspected or generated.
The first v7 generation batch covers English indices 160–219: 54 reviewed sources
generated, six rejected sources retained. The shared v3 Odin SQLite ledger and lock
continue to enforce the aggregate rate cap. Source review of the remaining cohort
is ongoing; there are no validation judge decisions or qualification results yet.


## English-only focus and other-language handoff, 2026-10-29

**Supersedes the active two-language scope above:** the user requested English-only
work for now and documentation of the other three languages. English validation
continues with its frozen configuration; no threshold, source process or sample
changes follow from this scope amendment.

| Held language | Generator and audit configuration | Development results and remaining work |
|---|---|---|
| Danish | Flash generation; Qwen+Odin base checks plus Qwen native-span checks | First-attempt clear 10/20. Final development/control false acceptance 2/47 (4.26%); clear withholding 11/51 (21.57%). Generated-only false acceptance 2/7. Both residual misses are generated examples. No untouched sample drawn. Needs further development or an explicitly frozen new evaluation; not qualified. |
| Hindi | Odin generation; Flash+Qwen base and paragraph/precondition checks plus Qwen native-span checks | First-attempt clear 10/20. False acceptance 1/49 (2.04%); clear withholding 16/50 (32%). Generated-only false acceptance 1/9. Stronger checks trade retention for lower false acceptance. Source process uses reviewed translations of readable English counterparts because raw Hindi was corrupt. No untouched sample drawn; not qualified. |
| Japanese | Odin generation; Flash+Qwen base checks | First-attempt clear 14/20. False acceptance 0/45; clear withholding 4/54 (7.41%). Generated-only false acceptance 0/5. Frozen v7 untouched sample contains 800 families, balanced by task. Source review completed for indices 160–179: 18 clear, two rejected. No validation conversations generated, no validation labels or votes. Held at the user's request; not qualified. |

Development denominators include 40 synthetic pairs per language. They are correlated,
and audit refinements reused development evidence. These are configuration findings,
not independent qualification results. Provisional assistant-manual references are not
human certification. Preserve all v3/v4/v5 artifacts and the Japanese v7 sample/reviews.
Before resuming Japanese, verify frozen hashes and existing sample receipts; do not draw
a replacement sample or regenerate reviewed work. All already inspected Japanese
families must remain excluded from any future new-policy validation.


### English validation source preparation completed

All 800 frozen English source families have provisional assistant-manual source
assessments and native slot reviews. 759 are usable; 41 source/precondition
rejections remain in the original cohort, without replacements. Usable counts:
creative 154, summary 147, QA 156, rewrite 148, revision 154. Frozen past-to-present
rewrite preconditions exclude already-present and unsuitable narration. Raw sources,
rejection reasons and per-source records are retained. Generation uses the same
frozen Odin adapter and shared historical request ledger; no acceptance votes have
been exposed. The final QA batch is completing before the full blinded packet.

The batch wrapper initially wrote completion to its own state file but omitted the
shared reader's `audit/pipeline/state.json`. This administrative metadata is restored
only after validating every immutable chunk/stage receipt; no model calls are replayed.
A QA support-span transcription mismatch was rejected before generation and corrected
to an exact existing source span. No source text or frozen prompt changed.

### English packet and labeling checkpoint, 2026-10-29

Supersedes the in-progress generation status above: all 759 usable-source generation
records have completed and their immutable receipts have been verified. The full
800-family blinded packet contains 696 generated conversations, 63 deterministic
failures and 41 source/precondition rejections. There are no transport-unresolved
attempts or validation judge decisions. Ninety generated conversations within indices
0–99 now have saved provisional assistant-manual semantic assessments; remaining
indices must be read before recording labels. Objective failures and intake rejections
remain in the cohort. No validation false-acceptance estimate is available yet.

Continue English labeling before exposing frozen Flash/Qwen judge decisions. Determine
whether the single supplementary cohort is needed from blinded class counts only.
All other languages remain held at the checkpoints in the handoff table above.

### English creative and summary review completed, 2026-10-29

The labeling checkpoint has advanced through indices 0–319: all 297 generated
creative and summary conversations have saved semantic assessments (265 clear,
23 definite-defective, nine borderline). These are provisional blinded labels,
not false-acceptance results; no validation judge calls have run. QA, rewrite and
revision semantic review remain outstanding. Objective failures and source
rejections are retained separately in the original 800-family sample.

`scripts/dfm16_validation_audit.py` prepares and executes the frozen English base
and paragraph/precondition checks through `audit_pipeline`. It requires all 800
sealed labels, verifies evidence hashes, records the supplementary decision from
blinded counts, and excludes Odin from judging its own outputs. Flash and Qwen
run concurrently, with their two check stages sequential per server to preserve
the aggregate 128-request concurrency limit. Missing required verdicts remain
unresolved even when another check rejects. No frozen model prompts were changed.
The focused generation/validation suite passes 52 tests with existing SWIG
deprecation warnings.

### English labels sealed and frozen audit started, 2026-10-29

Supersedes the partial review checkpoints above. All 696 generated conversations
have complete blinded semantic assessments. The sealed 800-family reference has
594 clear, 136 definite-defective, 29 borderline and 41 unresolved source/intake
examples. First-attempt labels are 572 clear, 161 defective, 26 borderline and 41
unresolved. These are provisional assistant-manual assessments, not independent
human certification. The count-only supplementary trigger is false: both required
class sizes are met. No replacement families were drawn.

The frozen English Odin generator is being evaluated by both Flash and Qwen, with
6,297 base checks and 3,296 paragraph/precondition checks per reviewer. All labels
and the supplementary decision were sealed before any validation judge request.
Review decisions are aggregated at conversation level; overlapping checks do not
increase the sample size. The original false-acceptance and withholding targets
remain unchanged. No other language was resumed and no production admission changed.

Revision review exposes frequent deletion of events inside the paragraph being
edited despite exact preservation of other paragraphs. A later selective undo does
not erase the earlier defective answer from the whole-conversation assessment.
The receipt-verified report also separates generated-only false acceptance from
the 800-family result, which includes deterministic failures withheld in code.
The frozen adapter suite plus sealed-label/review-view tests passed 53 tests.

### English untouched validation completed: audit fails, 2026-10-29

Supersedes the running status above. All 19,186 Flash/Qwen checks completed with
valid verdicts. The frozen Odin + Flash/Qwen base-and-precision configuration
**does not qualify**. Its failed sample is now development evidence; any revised
configuration needs a new untouched validation sample. The candidate manifest is
empty, and no production data or admission rule changed.

| Measure | Observed result | One-sided 95% upper bound |
|---|---:|---:|
| Definite-defect false acceptance | 32/136 = 23.53% | 30.29% |
| Clear withholding | 96/594 = 16.16% | 18.85% |
| Accepted-set definite contamination | 32/548 = 5.84% | 7.76% |
| Generated-only false acceptance | 32/73 = 43.84% | 54.13% |
| Unresolved source/intake evidence | 41/800 = 5.13% | 6.60% |

There were zero unresolved reviewer decisions. Of 548 accepted conversations,
498 were clear, 32 definite-defective and 18 borderline. All 63 deterministic
failures were withheld in code. Reporting generated-only false acceptance avoids
crediting the semantic judges with detecting these deterministic failures.

| Task | Accepted defects / all definite defects | Clear withheld / all clear |
|---|---:|---:|
| Creative | 3/11 | 39/141 |
| Summary | 15/16 | 1/124 |
| QA | 2/3 | 0/149 |
| Rewrite | 3/5 | 33/138 |
| Revision | 9/101 | 23/42 |

Small task denominators are diagnostic, not task certifications. The largest
missed class is summary fidelity: unsupported age, gender, ownership, platform,
weather, event and chronology details survive both reviewers. Revision misses
include deleted events despite an explicit preservation requirement. Coherence,
source/request grammar and rewrite chronology also remain in scope.

First-attempt clear yield was 572/800 (71.5%); final clear yield 594/800 (74.25%).
107 examples received objective correction attempts, recovering 22 clear examples;
82 remained defective and three borderline. English generation used 1,121 recorded
attempts with 1,120 responses, 289,014 input and 121,740 output tokens. Historical
Odin rate estimates give 4.8498375 DKK, excluding local GPU/manual costs and any
unreported failed-call usage. Each local reviewer used 10,821,239 input and 19,186
output tokens. Summed generation batch execution time was 358.07 seconds (759
attempted source families); Flash audit stages took 229.53 seconds, Qwen 432.74
seconds, running concurrently. Manual-review gaps are excluded. This is not a
4/4 capacity benchmark. Shared experiment Odin ledger: 2,151 sends, peak exactly
100 per rolling minute; its cumulative cost is separate from English-only cost.

Artifacts under `data/dfm16/staged-stories-validation-v7-20261029/en/reports/`:
`qualification.json`, `results.json`, `scored-conversations.jsonl`,
`accepted-defects.jsonl`, `borderline-conversations.jsonl`, and hash receipt.
Reference labels remain provisional assistant-manual, not independent humans.
The report handles code-assembled undo stages without charging model usage.
The 55-test suite passed before that reporting edge-case fix; the expanded
10-test validation/report suite passed afterward. OKF remains at its pre-existing
one unrelated oversized-page error and 15 unresolved-link warnings.

The user proposed evidence-producing reviews followed by evidence verification.
This is a separate development follow-up: brief exact source/answer quotes,
explicit instruction coverage, concrete grammar findings, then cross-model
verification against the original conversation. Preserve the failed frozen result
and labels; do not describe re-evaluation of these 800 families as validation.

### English evidence-review ablation v8, 2026-10-29

At the user's suggestion, `scripts/dfm16_evidence_audit.py` freezes a separate
experiment in `data/dfm16/staged-stories-evidence-v8-20261029`. It reuses all 696
complete English conversations from failed v7, retaining the other 104 families
as withheld in the 800-family denominator. Original labels and outputs are fixed.
No new family is drawn and no other language resumes.

Flash and Qwen independently produce brief evidence ledgers: exact source/answer
quotes, per-turn instruction coverage, event preservation and concrete grammar
findings. These are plain text, temperature zero, non-thinking, capped at 1,024
completion tokens, with at most one retry. Each model then verifies the other
model's ledger against the original conversation and returns plain accept/reject
within 32 tokens. Missing or invalid required evidence remains unresolved. A
ledger's false allegation is not itself grounds for rejecting the original text.

A matched control uses the same revised verdict prompt and original conversation
without a ledger. This distinguishes evidence benefit from prompt specificity;
both are compared with the frozen v7 baseline. Input fields are whitelisted to
exclude labels, previous verdicts and generator identity. All examples use a fixed
random execution order. Reports compare each judge, both, and either, including
paired gains/losses, task breakdowns, generated-only defects, usage and throughput.
These are adaptive development results, never renewed statistical qualification.

The trial reuses `audit_pipeline`, durable stage receipts and bounded retries;
per-server concurrency is 128. Evidence completion precedes dependent verification.
No Odin requests are needed. Four focused tests pass for input blinding, matched
prompts, bounded evidence output, strict verdict parsing and missing evidence.

### GPU interruption and Odin evidence follow-up v9, 2026-10-29

The user reported local GPUs unavailable for several hours and directed continued
work with Odin-2-Large. Supersedes the active-local-run status above: the v8 runner
received SIGTERM and its exit was verified. Do not resume local requests while
this restriction applies. No model server was stopped or reconfigured.

Both local evidence stages and direct-verdict controls completed all 696 rows.
Qwen produced 662 valid ledgers and 34 unresolved ones within the fixed token/retry
budget. Flash verification of those 662 valid Qwen ledgers completed. Qwen's
verification of Flash ledgers stopped after 466 of 683 requests; retain this partial
stage and its intents/receipts. `gpu-interruption.json` records the checkpoint.

The completed matched Flash arms show direct false acceptance 71/136 with 0/594
clear withholding, versus evidence-assisted 39/136 with 35/594 clear withheld
(including unresolved prerequisites). This improves that direct arm, but does
not beat the original v7 audit's 32/136 false acceptance. Qwen direct-only gives
18/136 and 183/594, trading detection for excessive withholding. These are adaptive
development comparisons. A ledger spot check found unsupported-age detection,
but another fabricated a word-count violation: its claimed 122 words were actually
117 by the required whitespace count. The second reviewer must verify allegations.

`scripts/dfm16_odin_evidence_audit.py` prepares
`data/dfm16/staged-stories-odin-evidence-v9-20261029`: Odin direct versus Odin with
the saved Qwen ledger, using exactly the same verdict prompt. There are 696 direct
and 662 evidence-assisted requests in a fixed shuffled order, with missing ledgers
retained as unresolved in the original cohort. Both arms share one 64-request
pipeline and the global 100/rolling-minute Odin ledger, including retries. No local
GPU work is required. The five evidence/transport-parameter tests pass.

**Odin generated these examples. Its verdicts are development diagnostics only;
they cannot independently admit its own outputs or qualify English.** The original
frozen validation and labels remain immutable. Any later qualified configuration
must exclude generator self-review and use a new untouched sample.

Completed local-arm diagnostics are saved in v8 `completed-arm-report.json` and
`paired-completed-flash.json`. Against the matched Flash direct arm, evidence
caused 24 additional defective conversations to be rejected and eight to become
unresolved; 10 clear examples were newly rejected and 25 became unresolved.
These effects must not be conflated. An explicitly post-hoc conjunction with the
original v7 policy accepted 24/136 defects and withheld 113/594 clear examples
(19.02%, upper95 21.87%): better observed defect detection, still not qualified.
No frozen policy was replaced. The combined focused suite now passes 61 tests;
OKF validation still has only the pre-existing one error and 15 warnings.

### Odin evidence comparison completed, 2026-10-29

Supersedes the running-v9 status above. All 1,358 planned Odin verdicts completed;
the runner exited and the report receipt hashes were verified. Local GPU requests
remain stopped. Results are in
`data/dfm16/staged-stories-odin-evidence-v9-20261029/report.json`, with complete
per-example decisions, stage receipts, usage, timing and a postflight receipt.

| Matched Odin arm | False acceptance, all definite defects | Clear withholding | Semantic-only false acceptance |
|---|---:|---:|---:|
| Direct verdict, same criteria | 73/136 = 53.68% | 12/594 = 2.02% | 73/73 = 100% |
| Verify with saved Qwen evidence | 41/136 = 30.15% | 37/594 = 6.23% | 41/73 = 56.16% |

The all-defect denominator includes 63 deterministic failures already withheld in
code. Evidence caused **24 additional semantic defects to be rejected**, while
eight more became unresolved because their required ledgers were invalid/missing.
It newly rejected 12 clear examples, made 23 previously accepted clear examples
unresolved, and recovered 10 direct-arm clear rejections. Across all labels there
are 34 missing-ledger unresolved outcomes. Do not describe those as successful
semantic detections. The one-sided upper95 false-acceptance bounds are 60.96%
direct and 37.27% with evidence; clear-withholding bounds are 3.25% and 8.11%.
These are descriptive bounds on reused development data, not new qualification.

Evidence helps this matched direct-verdict configuration, but its 41 accepted
defects exceed the original focused v7 audit's 32. Therefore do not replace the
original focused checks with this whole-conversation evidence method. The local
post-hoc supplementary combination above reduces misses to 24, still far above
the under-5% target. The concrete next development direction is short evidence
for individual high-risk obligations, exact source/answer quote verification and
trusted code-provided counts/preservation results, rather than accepting a broad
claim that all instructions were followed. No revised policy is qualified.

Remote elapsed time was 783.59 seconds. The 1,362 actual HTTP sends include one
model-discovery request and three extra completion attempts (two rate-limit
responses and one invalid-verdict retry). All final requested verdicts are valid.
Recorded completion usage: direct 867,816 input / 1,394 output tokens; with evidence
1,086,907 input / 1,324 output tokens. Historical Odin pricing estimates total
12.28496875 DKK, excluding local evidence-generation and manual costs. Shared
experiment ledger now contains 3,513 sends and still peaks at exactly 100 in a
rolling minute. Concurrency stayed 64, with no new scheduler or local server use.

Odin generated these stories, so even an improved self-review result would remain
a development diagnostic rather than independent admission evidence. All manual
references remain provisional assistant-manual. English is unqualified; Danish,
Hindi and Japanese remain at the documented held checkpoints. Original datasets,
failed experiments and production admission remain unchanged.

### Saved parallel-audit combinations, 2026-10-29

At the user's request to assess additional rounds and parallel auditing,
`scripts/dfm16_saved_audit_combinations.py` evaluated all 63 nonempty conjunctions
of six completed arms, without new model requests. The incomplete Qwen verifier
stage was excluded. Results and input hashes are preserved in
`data/dfm16/staged-stories-saved-combinations-v10-20261029/`.

The best observed combination within 20% clear withholding remains the focused
v7 audit plus Flash verification of Qwen evidence: 24/136 accepted defects,
113/594 clear withheld (19.02%). Adding all six arms reduces accepted defects to
11/136 (8.09%) but withholds 220/594 clear examples (37.04%). The latter includes
Odin self-review and is diagnostic only. Even this maximal conjunction misses
11/73 semantic defects (15.07%); the other 63 defects were withheld by code.

Flash and Odin verification of the same Qwen evidence share **39 missed defects**:
Flash misses 39, Odin 41, intersection 39. Thus requiring these two verifiers to
agree does not improve defect detection over Flash alone on this sample. Different
model names do not provide independent failure evidence here.

The proposed next experiment should diversify the audit task: independently find
unsupported source claims, lost/changed events or instructions, and concrete
grammar errors; then verify exact quoted evidence and alleged defects against
the original text. Keep first-pass reviewers blind to one another's conclusions,
provide trusted code counts/preservation checks, and test whether confirmed-defect
vetoes beat simple repeated verdicts. This is a proposal, not an implemented or
qualified policy. The 63-combination search is post-hoc development selection on
provisional assistant-manual references, not untouched validation. Local GPUs
remain unused, other languages held, and production admission unchanged.

### Independent specialists and allegation verification v11, 2026-10-30

The user authorized the proposed specialist experiment. It is implemented by
`scripts/dfm16_specialist_audit.py` in
`data/dfm16/staged-stories-specialists-v11-20261030`. All 696 complete English
conversations receive three independently prompted Odin reviews: fidelity and
coherence, instruction/event preservation, and grammar/spelling. The 63 objective
failures and 41 intake rejections remain withheld in the original 800-family
reporting population. Labels are fixed provisional assistant-manual references.

Each specialist sees the original conversation and authoritative source, plus
trusted code-calculated word/paragraph counts, full-story band checks and exact
paragraph/undo comparisons. Specialists cannot see other findings, labels or
prior votes. They return brief CHECK observations, at most three TARGET/QUOTE/ISSUE
findings and a terminal verdict, with 768 completion tokens and one retry maximum.
Code requires every allegation quote to occur literally at its named source or
one-based message turn. Invalid evidence remains unresolved, not a defect label
on the original conversation.

Each valid allegation receives a separate 32-token plain accept/reject verifier
request. The verifier rejects only when that particular allegation establishes a
definite original defect; mistaken or borderline allegations are dismissed. The
predeclared reports compare raw specialist veto, verified-defect veto and the
original focused audit combined with verified defects. Required unresolved stages
remain withheld; overlapping roles/findings never increase the example count.

All calls use Odin-2-Large with reasoning_effort=none and include_reasoning=false,
the existing continuous audit_pipeline, one shared 64-request client, immutable
stage receipts and the global 100/rolling-minute budget including discovery and
retries. No local GPU requests resume. Six new tests pass for parsing, exact quote
validation, independent scopes, code measurements, undo, disproved allegations and
missing verdicts. All prior input/software pins were verified before launch.

This is adaptive development on the failed v7 sample, not new validation. Odin
generated these examples; its self-review cannot independently admit them. No
production admission changes or other-language resumes are authorized by this run.

### Specialist parser and stage handoff amendment v12, 2026-10-30

Supersedes v11 as the active implementation. Early v11 replies exposed an
unnecessarily strict parser rule: five or six useful CHECK lines invalidated an
otherwise complete report. v11 was stopped with SIGTERM and drained; its frozen
code, design, attempts and incomplete receipts remain preserved. The shutdown's
missing-chunk-receipt exception records incompleteness, not successful completion.

`scripts/dfm16_specialist_audit_v12.py` and
`data/dfm16/staged-stories-specialists-v12-20261030` retain identical model requests,
prompts and semantic criteria. Only the CHECK-line maximum is advisory in parsing;
terminal verdicts, finding consistency, literal quote checks and token limits
remain required. All 579 saved v11 attempt records and their intent pins were
copied with hash provenance, without regenerating completed requests. There were
zero ambiguous intents. Global ledger count at v12 launch: 4,093 actual send
reservations, including v11 discovery. New execution reuses the original responses
before making requests for unfinished work.

The shared runtime owns/closes its supplied HTTP client. v12 creates a fresh
client for the dependent verification stage, with the same persistent budget and
at most 64 concurrent requests. This fixes a latent handoff issue before that
stage ran; a test simulates runtime client closure. Eight specialist tests pass,
including extra coverage lines and shared-budget client renewal. The preceding
combined suite passed 67 tests. All 696 conversations' code evidence was checked,
including 678 explicit full-story length bands and every selective undo.

Inherited attempt usage in v12 must be distinguished from newly billed calls;
the global ledger records each actual send once. The parser amendment does not
change old validation results or allow a statistical qualification claim.

### Specialist v12 completed: confirmation and scope failures, 2026-10-30

All 2,088 specialist reviews completed: 2,042 parsed, 46 unresolved. Literal quote
checks invalidated six more reports, leaving 48 conversations unresolved overall
(38 clear, eight defective, two borderline). Of 232 independently verified
allegations, Odin confirmed 229 and dismissed three. Confirmation recovered no
clear examples and newly admitted one definite grammar defect: index 61's
"a man in a embroidered vest", correctly identified by the grammar specialist.

| Policy | Accepted defects | Clear withheld |
|---|---:|---:|
| Raw specialist veto | 31/136 (22.79%) | 95/594 (15.99%) |
| Verified-defect veto | 32/136 (23.53%) | 95/594 (15.99%) |
| Original focused audit plus verified findings | 17/136 (12.50%) | 155/594 (26.09%) |

None meets both targets. These are reused development examples and generator
self-review, never independent qualification. `postflight-report.json` verifies
metrics against all 800 scored records and separates actual spend from inherited
responses. v11+v12 used 2,670 actual HTTP sends (2,667 HTTP 200, three rate-limit
responses), 3,282,498 input / 412,806 output tokens, estimated 30.8357625 DKK at the
historical rates. v12's newly sent requests account for 23.95589375 DKK; inherited
responses were not billed twice. Aggregate peak remained 100/minute. All 69 focused
tests passed; OKF remains at the existing one unrelated error and 15 warnings.

Inspection of clear false rejections exposed a concrete evidence-boundary problem:
the auditor payload still named a creative/revision seed `authoritative_source`.
At indices 8 and 11, fidelity reviewers and verifiers demanded that newly invented
fiction preserve the seed's setting or ending, despite prompts allowing creative
invention. This contextual label undermined the explicit task permission. The
v12 result remains preserved; the correction is isolated in v13.

### Source-scope correction v13, 2026-10-30

`scripts/dfm16_specialist_audit_v13.py` in
`data/dfm16/staged-stories-specialists-v13-20261030` corrects only auditor evidence
for creative/revision tasks: authoritative_source and background_seed are null,
and an explicit scope says the initial story has no source-preservation requirement.
Later revision edits are compared with their preceding conversational answer.
The seed remains immutable in provenance, but is not an audit input for those
tasks. Prompts, thresholds, labels and source-based task evidence are unchanged.

Copied hash-pinned cached responses for 1,353 unchanged source-based specialist
jobs and 52 unchanged verification jobs (1,563 attempt records). Their request
payloads remain identical; they are replayed without new model calls. Only the
735 creative/revision specialist requests and their resulting verification
requests need new responses. Ledger count before v13: 6,183. Ten specialist tests
pass, including absence of authoritative seeds for creative/revision and exact
evidence equivalence for summary/QA/rewrite. No local GPU work or promotion.

### Corrected specialist results v13, 2026-10-30

All reviews and verification completed. v13 source-based results are identical to
the cached v12 controls (1,353 specialist and 52 verifier jobs), verified against
their receipts. No source-based conversations were regenerated or rejudged. All
71 focused tests pass; repository OKF validation retains only the pre-existing
one oversized-page error and 15 missing-link warnings.

| Policy | Accepted defects | Clear withheld |
|---|---:|---:|
| Original focused v7 audit | 32/136 (23.53%) | 96/594 (16.16%) |
| Corrected raw specialists | 22/136 (16.18%) | 78/594 (13.13%) |
| Corrected specialists plus finding verification | 22/136 (16.18%) | 78/594 (13.13%) |
| Original focused audit plus verified specialists | 16/136 (11.76%) | 146/594 (24.58%) |

The specialist-only false-acceptance upper95 bound is 22.29%; its withholding
upper95 is 15.63%. The combined policy's corresponding bounds are 17.32% and
27.66%. None qualifies or meets both original point targets. Among the 73 semantic
defects that passed deterministic generation contracts, specialists accept 22
(30.14%); the combined policy accepts 16 (21.92%). The other 63 defective examples
are withheld mechanically and must not be credited to semantic judges.

Unresolved cases matter: 77 specialist reports remained malformed/inconsistent,
and seven further reports failed literal-quote checks. These affect 72 distinct
conversations: 18 defective, 51 clear, three borderline. The specialist policy
rejects 96 defective conversations (63 deterministic plus 33 semantic), accepts
22, and leaves 18 unresolved. It rejects 27 clear conversations and leaves 51
clear ones unresolved. Thus the lower acceptance rate is partly uncertainty
withholding, not increased confirmed detection; v12 also rejected 33 semantic
defects. The 41 source/intake rejections remain separately withheld.

The roles do contribute different findings: after verification, fidelity uniquely
rejects 11 defective examples that the other two roles accept; grammar uniquely
rejects six, instructions eight. Against the original focused audit, the new
specialists reject 12 previously accepted defects and leave four more unresolved.
However, the original audit catches defects the specialists miss, explaining the
combined policy's better detection and worse retention.

Verification confirmed 155 of 160 allegations and dismissed five, but changed
**zero whole-conversation decisions**. There is no measured admission benefit from
that extra round here. The scope correction fixes the inspected false rejections
at indices 8 and 11; both are now accepted. Index 61's definite "a embroidered"
error is now rejected. No creative/revision finding cites a nonexistent source.

Preserve v13 `report.json`, per-example scored records, `postflight-report.json`,
`source-equivalence-receipt.json`, actual-send snapshot and hash receipts. New v13
execution used 1,042 HTTP sends, all successful, and 1,270,728 input / 174,289 output
tokens: estimated 12.299275 DKK at the historical rates. Detector execution took
546.77 seconds and verification 60.62 seconds, including replay of cached records.
The whole v11–v13 investigation used 3,712 actual sends and an estimated
43.1350375 DKK; inherited responses are not billed twice. Aggregate peak stayed
100/rolling minute, concurrency 64, with no local GPU work.

The useful retained implementation change is correct evidence scope plus
specialized checks. This verifier adds cost without improving example decisions
on the measured sample. All results remain adaptive development on provisional
assistant-manual references, with Odin self-review excluded from independent
admission. English remains unqualified; other languages and production are unchanged.

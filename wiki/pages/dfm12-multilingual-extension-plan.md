---
type: Plan
title: DFM12 Multilingual Capability Extension
description: Proposed 42-dataset extension with accepted-row targets, training-token budgets, and B200 generation and audit costs.
status: draft
confidence: medium
last_updated: 2026-09-26
tags: [dfm12, multilingual, synthetic, planning, gpu-budget]
---
# DFM12 Multilingual Capability Extension

Proposal requested on 2026-09-25; quarter-size first approved later that day.
This does not authorize interrupting the running training job or modifying
the DFM12 build already underway.
Targets are approximate accepted supply, not a reason to lower quality gates.

## Approved Quarter-First Milestone

### Bounded Diagnostic Replay, 2026-09-26

After the 700-slot trial failed before generation, the user authorized measured
same-model output-budget repair, not weaker admission. `dfm12.multilingual_diagnose`
uses exactly eight preselected development/regression controls: all four historical
regressions plus four development examples, balanced four positive/four negative
and spanning all seven languages. No held-out examples enter diagnostic selection.
It compares original schema/1,024 against identical schema/4,096; only when the
4,096 arm has errors or disagreements does it compare bounded schema/4,096 against
the identical bounded prompt without constrained JSON decoding. At most 32 calls,
no retries, default concurrency two, and no server/scheduler/training lifecycle.

Run against an already owned teacher with
`python -m dfm12.multilingual_diagnose --root NEW_DIRECTORY --endpoints http://127.0.0.1:8590/v1 --concurrency 2`.
`--prepare-only` performs local tokenization without network/model calls. The
26B-A4B model and thinking-disabled setting are fixed. The final CPU fixture
`data/dfm12/multilingual-diagnostic-20260926-cpu-final` measured maxima of 821
prompt tokens for original prompts and 935 for bounded prompts; largest prompt
plus completion budget is 5,031, below the enforced 8,192 limit. Ninety-eight
diagnostic/multilingual tests passed; these are CPU checks, not live model results.

Each call has a unique single-writer request ID. `raw/*.request.json` and
`raw/*.response.json` preserve request, HTTP status, exact response bytes (base64),
readable body, and selected nonsecret headers before parsing. This includes HTTP
errors, invalid JSON and length finishes; bodies above 2 MiB fail closed and are
explicitly marked truncated. Companion metadata extracts server ID, usage and
finish reason. `progress.json` and `report.json` contain per-control/dimension
outcomes and recommend settings only; they never authorize generation or relax
the all-control gate. No W&B logging is used.

Future isolated pilot roots may explicitly opt in with `diagnostic_followup: true`,
`raw_response_logging: true` and `review_options: {variant: schema4096}` (other
diagnostic variant names are supported). Both calibration and second review use
the same configured request. Raw-enabled calls measure prompt budgets before
submission. Legacy defaults are unchanged; failed roots must not be resumed or
silently re-pinned. Pin the new diagnostic helper with the new-root implementation
inventory, rerun the full calibration, and only then permit the 700-slot trial.

**Evidence-driven protocol amendment, 2026-09-26:** the initial live replay
(`multilingual-diagnostic-20260926-live`) was stopped early after seven of eight
schema-1,024 controls hit length, and repeated schema-4,096 controls produced
98.7% whitespace through all 4,096 completion tokens. `early-stop.json` preserves
the partial outcomes and in-flight IDs; the original implementation is archived
alongside its manifest. This is an incomplete A/B protocol, not eight completed
4,096-token results. Only the owned diagnostic client was signaled; teacher
and training were untouched, and teacher request counts drained to zero.

The installed vLLM request merge preserves `disable_any_whitespace`, but its
XGrammar backend reads this flag from server-global configuration, not per-request
sampling fields. A flags-only structured-output object also lacks a required
constraint. Therefore the next request-only arm uses `--variant grammar4096`:
the unchanged original review JSON schema is compiled with XGrammar
`any_whitespace=False` and compact separators, then sent as an explicit
`structured_outputs.grammar` without `response_format`. No server restart or
semantic-schema relaxation is involved. CPU grammar tests confirm that spaces
inside strings remain valid, flexible inter-element whitespace is rejected,
and boolean fields still reject strings. Actual local vLLM request-model parsing
accepts this form. Source hashes and the API verification are recorded in
`data/dfm12/multilingual-diagnostic-20260926-grammar-api.json`.

The isolated eight-control grammar replay is
`data/dfm12/multilingual-diagnostic-20260926-grammar`, concurrency two, with the
same raw-response retention. Thirty-two focused tests pass, including preservation
of the original 16-call A/B early-skip behavior. A syntactic-loop repair is not a
language-quality pass; all 172 controls must still pass before any 700-slot trial.

**Grammar outcome and evidence barrier, 2026-09-26:** the eight-control compact
grammar arm returned 8/8 decision/dimension agreement and no request failures,
but six explanations were placeholders (`N/A` or punctuation), and negative
flags frequently had empty issues. The user explicitly prohibited treating this
technical result as sufficient admission. The next full probe used
`multilingual-pilot-20260926-grammar700` with
`calibration_measurement_only: true`; `dfm12.multilingual_calibration_probe`
cannot create pilot slots, and the ordinary pilot CLI rejects that root.

That full probe failed closed: 152/172 keep/reject agreements, nine JSON parse
failures, eleven decision disagreements, and sixteen labeled-dimension failures
(overlapping counts). Aggregates: development 107/112 agreements, held-out 41/56,
regressions 4/4. `review-calibration.json`, `probe-status.json`, raw bodies and
matching implementation snapshots are preserved. Zero pilot rows were generated.
Only aggregate held-out outcomes were examined for reporting, not used to tune
the subsequent semantic prompt.

`dfm12.multilingual_review_evidence` is an opt-in development variant, not a new
general default. It requests literal candidate evidence before booleans, checks
that the quoted span occurs in assistant content/tool arguments, rejects
placeholder explanations, and requires exactly one dimension-prefixed,
evidence-bearing issue for each false flag and none for true flags. It asks for
brief visible evidence, not a reasoning trace. String length limits are enforced
after parsing: CPU fixtures demonstrated that the installed XGrammar conversion
of length-bounded string productions fails escaped-quote inputs. The grammar
uses escape-capable strings, while the same length and nonempty requirements
remain mandatory in the validator.

The `evidence4096` eight-control development replay returned 2/8 with six literal
evidence failures, all preserved under
`multilingual-diagnostic-20260926-evidence`. The next `evidence_plain4096` arm uses
the identical prompt, token budget and validators but no constrained decoding;
it is isolated under `multilingual-diagnostic-20260926-evidence-plain`. Neither
arm uses held-out examples. Correct booleans with `N/A` evidence explicitly fail
the calibration gate in a dedicated test. No variant automatically relaxes the
172-control requirement or authorizes continuation after a failed full gate.

**Bounded development disposition, 2026-09-26:** unconstrained evidence v1
returned 0/8 because substantive responses used the wrong nested schema. The
same eight development/regression controls then produced 4/8 with an explicit
flat output schema (v2), 6/8 after exact-repetition/source-constraint clarification
(v3), and 7/8 after unrelated formatting examples (v4). No held-out semantic
outputs informed those changes; `multilingual-evidence-development-policy.json`
records their basis and hashes. The remaining v4 Icelandic review made the
expected rejection and cited the real subspan `fela j`, but its issue did not
repeat its full `literal_quote`, as required by the frozen evidence validator.
It was NOT treated as passing. This is a quote-repetition contract blocker,
not evidence that the last keep/reject decision was wrong.

No further automatic retries, full calibration or 700-row generation were
launched after that bounded development failure. The teacher was cooperatively
stopped only after running/waiting request counts were both zero; its supervisor
confirmed `phase: stopped`, `reason: stop_requested`, and no survivors. Training
was not signaled. Final tests: 168 passed. The machine-readable disposition is
`data/dfm12/multilingual-diagnostic-disposition-20260926.json`; it links every
run, raw evidence, implementation snapshots, test report and cleanup receipt.
There were 236 requests, 235 saved responses and one explicitly documented
cancelled request without a response. Observed usage was 208,656 prompt plus
47,954 completion tokens, excluding unknown partial usage of that cancellation.
These are diagnostic/reviewer tokens: added pilot rows and training tokens remain
zero. Any decision to revise redundant quote repetition must be explicit;
the quality-score thresholds and 172-control gate have not been relaxed.

### Calibration Repair And 700-Row Trial, Authorized 2026-09-26

**Execution outcome, 2026-09-26:** after successful XL identity training, the
trial reached model calibration but did not generate any rows. Of 172 controls,
142 requests terminated with `Incomplete output: length` (the reviewer request
budget was 1,024 output tokens). These `ValueError` failures were not retried.
Thirty valid reviews returned; 29 keep/reject
decisions agreed, while the Polish positive tool-schema control was rejected
without explanatory issues (`back_translation: N/A`). **Correction, 2026-09-26:**
the earlier claims of exhausted retries and a mainly output-budget failure are
superseded. Raw responses were discarded, so the underlying cause is unknown
pending diagnostic replay; length termination alone does not establish it.
This is not completed evidence of reviewer quality. All 700
slots remain pending, with zero generation events. Owned servers were released
and the same XXL scheduler resumed from ephemeral 660500; observed progress
660545. Diagnose emitted/truncated responses and calibrate output budgeting
before retrying; do not lower quality gates or infer a 29/30 global pass rate.

The user approved prompt/template inspection, expanded calibration with an
unseen split, a 100-row-per-language trial, and retaining the quality gate.
They did not approve the proposed 31B reviewer switch: both inference passes
remain 26B-A4B. This qualifies the earlier stronger-reviewer recommendation;
whether the existing model can pass improved testing is still unknown.

CPU preparation is concurrent with training. GPU work must wait until the
1,000-step XL identity interlude completes successfully. A detached watcher,
`scripts/after_identity_multilingual_trial.py --arm`, waits for that existing
scheduler row to run, then requests a soft stop. It does not interrupt identity
training or signal GPU processes. After the scheduler drains, it runs the
prepared gated trial only if GPUs are free. Calibration failure prevents
generation, and success/failure both resume the same XXL scheduler and run.
An externally changed stop request or occupied GPU fails closed instead.

New trial directory: `data/dfm12/multilingual-pilot-20260926-calibrated700`.
Receipts/logs: `logs/training/dfm12_XL_identity_da_en_1000steps/post-identity-trial/`.
The failed 35K cohort and first accepted pilot remain unchanged. No automatic
35K/bulk continuation, upload, or training admission is authorized. A small
automated control set is not native-speaker certification, especially for
Faroese and Icelandic. Report language, source-supported correctness and
instruction compliance separately; do not treat repaired backtranslations as
evidence that the original output was correct.

#### Calibrated Trial CPU And Runtime Contract

`dfm12.multilingual_prepare_calibrated` prepares the new root without model
requests. It verifies that the failed v3 donor still has 35,000 pending slots,
zero attempts/candidates/events, unchanged seed pins and the inherited exact
dedup ledger. It never writes the donor. Per-language quotas are 30 grounded,
20 summary/rewrite, 20 multi-turn, and 10 each OpenHermes, math/code and tool
dialogue. These are 700 target slots, not 700 guaranteed accepted rows; the
existing six-attempt bound allows at most 4,200 candidate attempts.

Preparation writes complete slot specifications, source-allocation coverage,
donor evidence, raw student-template receipt and the development/held-out/
regression controls with actual local Gemma reviewer renders. `seeds-ready.json`
binds these files and implementation pins. The separate `--certify-tests`
operation validates a passing JUnit report and inputs before atomically writing
`cpu-preflight-passed.json`, the watcher trigger. CPU certification is NOT a
model calibration pass or native-language quality approval.

`dfm12.multilingual_trial.gate` validates those pins, then evaluates every
control with concurrency capped at 16. Every keep decision and explicitly
labeled dimension must agree; missing/malformed responses or request errors
fail closed before generation. Unlabeled dimensions are not inferred. All four
historical regressions remain. No failed language/family is silently removed.
`multilingual_pilot` retains its original score >=4, second-review, exact-dedup
and raw current-template validation gates; generation and review remain 26B.

Runtime outputs include `review-calibration.json` (split/language/family and
dimension outcomes), `trial-outcomes.json` (all 42 language/family groups and
quality-dimension counts), and `trial-inspection.jsonl` (up to three complete
accepted candidates plus rejected/error examples per group). Full accepted
content remains in `accepted/*.jsonl` and `native-review-sample.jsonl`.
Pause recommendations do not authorize filtering away failed combinations or
automatic expansion. Launch after identity uses the existing command:
`python -m dfm12.multilingual_run --root data/dfm12/multilingual-pilot-20260926-calibrated700`.
The preparation agent does not launch that GPU command or edit the watcher.

CPU inspection confirmed that the actual cached teacher tokenizer preserves
the reviewer instructions and candidate/source JSON; only trailing system-prompt
whitespace is trimmed. This does not establish live server behavior. The 144
constructed controls originally comprised 98 development, 42 family-held-out
and four historical regressions; that draft count is superseded by the final
172 controls: 112 development, 56 held-out and four regressions. These remain
diagnostics, not native-language gold. The earlier 91-test run is superseded by
the final trial-root `cpu-tests.xml` report.

The prepared root contains 700 slots across 42 groups, 490 distinct allocated
source windows/conversations and 33,305 inherited accepted hashes. No rows or
tokens have been generated by CPU preparation. An unlaunched draft with an
incorrect display-name coverage report is preserved at the same root name
plus `-preflight-draft`, without a watcher receipt. Only the unsuffixed root
is eligible for certification.

Concurrent `records.py` changes invalidated the first CPU receipt, which was
withdrawn and preserved as `cpu-preflight-superseded.json`. The explicit
`implementation-repin-review.json` records old/new hashes and the reviewed
current source; the untracked original source was unavailable for an exact
diff. Core adapter tests were added to the revalidation run. The separately
authorized runner change is recorded in `runner-repin-review.json`:
`multilingual_run.run` now verifies calibrated inputs before GPU discovery or
server startup, not only after startup in the client. Both changes require
explicit re-certification; no automatic pin refresh occurs at runtime.

### Second Pilot, Approved And Armed 2026-09-26

**Execution outcome, 2026-09-26:** the second pilot did NOT generate its 35K
cohort. All eight servers started, but reviewer calibration passed only two
of four controls: it rejected the corrupted Faroese example and accepted the
correct arithmetic control, but falsely accepted the Icelandic mistranslation
and an unsupported current bus-ticket rule. `review-calibration.json` preserves
the exact outputs. SQLite has 35,000 pending slots and zero generation events.
The quality gate failed closed, owned servers were released, and XXL resumed
automatically from `step_660000` (runner 2574089, training process 2574193).
Thus the stronger prompt alone did not validate this same-model reviewer.
Do not bypass calibration or claim a second accepted dataset. A stronger or
independent reviewer plus revalidation/native checks is needed before retry.
The later user-authorized GPU interlude is XL identity training, not a retry
of this multilingual pilot; see [identity export](/pages/dfm12-identity-export.md).

User authorized implementing the pilot review recommendations and another 35K
pilot after the next checkpoint. New directory:
`data/dfm12/multilingual-pilot-20260926-v3`. The first pilot stays untouched.
This supersedes the first pilot's mix and narrow reference tasks for new work,
not its historical records. No quarter/full bulk run is authorized by this step.

| Family | Slots per language | All seven languages |
| --- | ---: | ---: |
| Grounded instructions | 1,900 | 13,300 |
| Summary/rewrite | 1,100 | 7,700 |
| Multi-turn | 1,000 | 7,000 |
| Modernized OpenHermes adaptation | 500 | 3,500 |
| Math/code | 300 | 2,100 |
| Tool dialogue | 200 | 1,400 |
| Total | 5,000 | 35,000 |

Preparation excludes all source IDs assigned to first-pilot slots, including
failed generations. Available unused reservoirs: 6,321 native windows per
language and 7,719 modernized OpenHermes seeds. Accepted-message fingerprints
from all 33,305 first-pilot successes seed cross-cohort exact deduplication.
Stable cohort IDs, immutable configuration fingerprints, SQLite single-writer
locking and bounded six-candidate retries protect restart behavior.

Contract v3 adds 12 exact math reference types, 10 CPU-tested code tasks and
five mock tool domains (library, appointments, parcels, events, stock), each
with lookup, clarification, action, error recovery and no-call variants.
Tool arguments must come from the user or prior tool results. Translation
preserves turn structure; grounded multi-turn prompts must concern the source.
No model-generated Python is executed.

Every first-pass accepted candidate receives a separate skeptical language,
meaning and constraint review on another replica. Both passes use the same
26B-A4B model: this is NOT independent-model or native-speaker certification.
Startup calibration must reject corrupted language/unsupported factual claims
and accept a correct arithmetic control before generation is allowed. Failure
stops the pilot and triggers normal training resumption rather than bypassing
quality checks. Completion exports a stratified native-review sample (up to
17 accepted rows per language/family), quality summary and accepted-only JSONL.
Native review and final training admission remain pending.

Handoff is armed for `step_660000`: this regular 10K checkpoint replaces the
ephemeral save at that same 500-step boundary. The scheduler has a soft-stop
request; training continues until the complete checkpoint is verified and
hardlink-preserved. Then the exact training process group is stopped. Eight
owned vLLM replicas use utilization 0.90, max sequences 128, client concurrency
64 per endpoint, the audit conda environment and its CUDA header/library paths.
The existing scheduler row is reset to resume from 660K toward 700K, same
W&B run `DFM5/xxl-restart520k-20260910` and unchanged training hyperparameters.
Completion or pilot failure releases owned GPUs and restarts that scheduler.
The handoff refuses to clear a stop request modified by someone else.

Verified before launch: 58 unit/integration tests; 60 math/code and 25 tool
trajectories encoded with the actual pinned student tokenizer/template. These
CPU fixtures validate structure, not the quality of future generations.
Operational receipts/logs are in the new pilot directory (`handoff.json`,
`handoff.log`, `review-calibration.json`, `client.log`, `quality-summary.json`,
`training-resumed.json`). Afterward the expected training log is
`logs/training/dfm11_XXL_epoch3/from_660000_after_multilingual-pilot-20260926-v3/train_until_step_700000.log`.

### Pilot Assessment, 2026-09-26

The completed `data/dfm12/multilingual-pilot-20260925/pilot.sqlite` contains
33,305 accepted conversations and 1,695 exhausted slots (95.2% slot yield,
not candidate acceptance rate). Accepted rendered training tokens total
40,351,327. All 42 language/family combinations have accepted output.

| Family | Accepted | Target slots |
| --- | ---: | ---: |
| Grounded instruction | 9,977 | 10,003 |
| Math/code | 2,955 | 3,003 |
| Multi-turn | 7,278 | 7,497 |
| OpenHermes adaptation | 6,109 | 7,497 |
| Summary/rewrite | 4,985 | 4,998 |
| Tool dialogue | 2,001 | 2,002 |

Assessment: useful operational pilot, not a blanket quality approval for
bulk generation. OpenHermes accounts for 1,388 of 1,695 exhausted slots.
Faroese and Icelandic have the lowest overall slot yields (92.4% and 90.7%).
Spot checks found mathematically correct accepted translations with suspect
wording despite perfect auditor language scores: Icelandic `til að fela j`
(to hide j) where isolating j was intended, and Faroese `Partar bjøttu`.
These require independent/native review; automated scores alone cannot
establish language quality. The previously quarantined Faroese bus-policy
hallucination is another accepted-row false positive.

The pilot math/code templates and stock/reservation tool domain are narrow;
broaden verified problems and tool schemas before scaling those families.
Grounded instruction and summary/rewrite are the most promising first
expansion candidates, subject to stratified review. No bulk launch or
training integration follows automatically from this assessment.

Automatic training resume succeeded from ephemeral 655000 in the existing
run; the resumed log had reached step 659735 during this assessment.

Decision, 2026-09-25: start with quarter size, retaining cumulative half/full
targets for later approval. This supersedes the half-size first tranche below.
Use the cost-reduced 26B-A4B generator and separate 26B-A4B audit pass;
the original 31B generator budget below remains historical context.

| Cumulative milestone | Accepted conversations | Estimated added training tokens |
| --- | ---: | ---: |
| Quarter (approved) | 962,500 | 1,527,625,000 |
| Half (optional later) | 1,925,000 | 3,055,250,000 |
| Full (optional later) | 3,850,000 | 6,110,500,000 |

Quarter targets are 175,000 conversations each for NB/NN/IS/FO and 87,500
each for NL/SV/PL, preserving every family proportion. The 35,000 accepted
pilot conversations count toward these quotas, not in addition. Preserve
accepted rows, seed provenance, stable candidate IDs and audit receipts across
expansion. Milestone names must not be part of record IDs. Expand by filling
the difference from accepted totals, never by regenerating an earlier tranche.
Rejections do not count toward accepted quotas; bounded refill requires yield
and source-diversity checks rather than relaxing acceptance criteria.

Machine-readable targets: `dfm12/multilingual_extension.yaml`. Inspect all 42
dataset quotas with `python -m dfm12.multilingual_targets --milestone quarter`
(also accepts `half` and `full`). This command only reports targets; generation
workers, seed manifests and pilot checks still need preparation before launch.
No GPU jobs were launched by this milestone change, and training is untouched.

### Authorized Pilot Handoff

Later on 2026-09-25 the user explicitly authorized stopping training at the next
ephemeral and generating the 35K pilot, then automatically resuming training.
This supersedes the preceding no-launch operational state, not the bulk gate.

- Pilot directory: `data/dfm12/multilingual-pilot-20260925`.
- Handoff: `scripts/handoff_dfm12_multilingual_pilot.py`; target
  `ephemeral_step_655000`, preserved via immutable payload hardlinks under
  `checkpoints/preserved/dfm12-pilot-655000` before signalling the exact training
  process group. Scheduler receives a soft stop first.
- Resume: existing `dfm11-e3-train-700000` row, same scheduler plan and
  W&B run `DFM5/xxl-restart520k-20260910`; only resume tag/log directory and
  row retry state change. LR, optimizer, data, GAS and BP settings are preserved.
- Generation/audit ownership: `dfm12.multilingual_run` starts eight independent
  cached Gemma 4 26B-A4B servers in the `audit` environment, utilization 0.90,
  max sequences 128, 8K teacher context, HTTP 8500..8507, distinct internal
  port bases 28000..28700. Client concurrency is 64 per endpoint. All pilot
  servers are released in cleanup on success/failure, before training resumes.
- Per-language accepted pilot quotas: multiturn 1,071; grounded 1,429;
  modernized OpenHermes 1,071; summary/rewrite 714; math/code 429; tools 286.
  Total 5,000/language and 35,000 overall. Six candidate attempts per slot
  maximum; infrastructure requests have three retries. Report exhausted slots
  as shortfalls, never as accepted. Do not launch quarter bulk automatically.
- CPU seed prep: `dfm12.multilingual_seeds` samples random row groups/rows from
  approved native sources (NB/NN explicitly separated); 9,000 distinct text
  windows/language, plus 12,000 reservoir-sampled modernized EN/DA OpenHermes
  conversations. Local source identities/revisions and seed checksums persist.
- Pilot tasks: `dfm12.multilingual_tasks`; CPU supplies verified parameterized
  arithmetic, fixed tested Python solutions, and mock stock/reservation tool
  trajectories. These deliberately limited procedural pilot designs are not
  yet the full diversity of repaired ToolACE/Glaive seed schemas or arbitrary
  code/debugging problems envisioned for bulk. Assess diversity before bulk.
- Durable state: single client owns `pilot.sqlite` under a file lock; accepted
  slots cannot be rescheduled. Original rejected candidates and reasons persist
  in events. Every accepted row passes independent model audit, structural
  checks, exact duplicate rejection and untrimmed Gemma student-template length
  checks. Native-speaker review remains pending; no automatic training inclusion.
- Outputs: 42 accepted-only JSONL files under `accepted/`, plus `runtime.json`
  and `completion.json`. Generation and audits interleave per slot. Six-attempt
  exhaustion does not prevent training from resuming. Preparation/startup have
  one-hour limits; pilot GPU allocation has a 22-hour bound, preserving work
  for later resume if necessary. No W&B generation logging or dataset upload.

Logs: `handoff.log`, `pilot.log`, `client.log`, `server-gpuN.log` inside the
pilot directory. After completion, training log is
`logs/training/dfm11_XXL_epoch3/from_655000_after_multilingual_pilot/train_until_step_700000.log`.

Verified handoff: 655K DCP metadata/storage-length checks passed both in the
original and preserved directories. Training and scheduler exited; the original
training row is pending with the updated resume tag. All eight pilot servers
loaded weights; initial startup rebuilt the shared FlashInfer MoE kernel cache
before inference. Do not confuse this CPU compilation stage with failed GPU
inference. Seven pilot/target tests pass, including rejected-candidate retry and
accepted-row resume idempotence. Pilot acceptance is not final corpus admission:
native review, benchmark/near-duplicate screening and broader task diversity
remain bulk/integration gates.

Startup correction: the first launch failed in FlashInfer host C++ compilation
with missing `cuda_runtime_api.h`, `cuda_fp16.h` and `cublasLt.h`. Conda stores
these under `audit/targets/x86_64-linux/include`, not the environment's top-level
`include`. The launch environment now explicitly sets `CPATH` to that directory
and `LIBRARY_PATH` to `audit/targets/x86_64-linux/lib`; a host-compiler syntax
test including all three headers passed. This changes only pilot subprocess
environments, not installed packages or training. Limit future kernel builds
with `MAX_JOBS=16` per server. The fallback resumed training as designed;
the loading restart was stopped before training advanced, and an explicit
`--retry-pilot` handoff rearmed the same 655K continuation. Historical fallback
receipts are retained with `.before-retry-*` suffixes.

Pilot contract-v2 correction: actual early outputs exposed missing JSON fields,
wrong turn counts, and a deterministic student-prefix mismatch when tool-error
recovery inserted a standalone assistant narration before another call. Generation
and audit now use explicit JSON schemas, multi-turn arrays have exact required
lengths, and retry calls remain within the native tool cycle without the extra
assistant turn. All five tool subtypes pass actual student-template encoding.
The pilot was drained; 374 nonaccepted slots with relevant format failures were
reopened once, preserving historical events. Accepted rows were retained except
one manually quarantined Faroese conversation asserting unsupported new bus
ticketing/accessibility policies. Its full record and reason remain in events.
Generator instructions now explicitly prohibit inventing current local policies.
This is evidence that same-model audit is not sufficient final validation,
especially for low-resource languages; the native-review/bulk gate remains.
See `contract-v2-migration.json`; eight unit/integration tests pass.

Operational verification after contract-v2 restart: all eight endpoints served
successful requests; GPU utilization was 65-91% with about 166,060 MiB allocated
per GPU. More than 5,700 accepted pilot conversations were present across all
seven languages, including native-tool error-recovery examples. Residual invalid
JSON, output-length and role-order failures remain rejected/retried, not admitted;
terminal quality failures remain explicit shortfalls. Supervisor/handoff is detached
and armed to release these servers and resume the original XXL job from 655K
toward 700K. This is a launch/progress observation, not pilot completion or
authorization to include the pilot in training.

Cheaper-pipeline planning estimate: 320-410 B200 GPU-hours for quarter size,
or approximately 1.7-2.1 active days on eight dedicated GPUs. This assumes
2-3x generation speedup and reduced emitted boilerplate, neither established
by a matched pilot yet. Do not present it as a measured ETA.

## Baseline And Objective

Current DFM12 adds 3,585,161,337 tokens/epoch to DFM11, including identity at
repeat 10. Expected full mean is 106,799,766,039 tokens/epoch. See
[token accounting](dfm12-token-accounting.md). This extension targets usable
multilingual assistance, not more grammatical-acceptability classification.

The present accepted Dutch UltraChat/Dolci supply is 652,040,335 rendered
tokens; Faroese and Icelandic DynaInstruct supply is only 1,386,735 and
3,788,297 respectively. These comparisons exclude transformations and DaLA.
Prioritize NB, NN, IS and FO; use half their quotas for NL, SV and PL.

## Exact Proposed Dataset Identities

Publish separate repositories under `schneiderkamplab`. For each of the six
stems below, create exactly seven repositories with suffixes
`nb`, `nn`, `is`, `fo`, `nl`, `sv`, and `pl`. For example,
`schneiderkamplab/dfm12-multilingual-multiturn-fo` is one repository.
The Cartesian product defines 42 new repositories; none exists by this plan.

| Repository stem (append `-LANG`) | Each NB/NN/IS/FO | Each NL/SV/PL | Total accepted conversations | Mean rendered training tokens/conversation | Added tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| `schneiderkamplab/dfm12-multilingual-multiturn` | 150,000 | 75,000 | 825,000 | 2,400 | 1,980,000,000 |
| `schneiderkamplab/dfm12-multilingual-grounded-instruct` | 200,000 | 100,000 | 1,100,000 | 1,800 | 1,980,000,000 |
| `schneiderkamplab/dfm12-multilingual-openhermes` | 150,000 | 75,000 | 825,000 | 700 | 577,500,000 |
| `schneiderkamplab/dfm12-multilingual-summary-rewrite` | 100,000 | 50,000 | 550,000 | 1,500 | 825,000,000 |
| `schneiderkamplab/dfm12-multilingual-math-code` | 60,000 | 30,000 | 330,000 | 1,200 | 396,000,000 |
| `schneiderkamplab/dfm12-multilingual-tool-dialogue` | 40,000 | 20,000 | 220,000 | 1,600 | 352,000,000 |
| **Total** | **700,000** | **350,000** | **3,850,000** | | **6,110,500,000** |

Rows mean accepted conversations, not assistant-target examples. Training
tokens include all prompt/response examples emitted by the current Gemma 4
template tokenizer, including repeated history when multiple turns are targets.
These token means are planning assumptions, not measured new data. Measure
pilot token counts separately for each language; do not pad answers to quotas.
Every rendered example must fit the current 4,096-token training limit.

| Language | Accepted conversations | Additional training tokens |
| --- | ---: | ---: |
| Bokmal (`nb`) | 700,000 | 1,111,000,000 |
| Nynorsk (`nn`) | 700,000 | 1,111,000,000 |
| Icelandic (`is`) | 700,000 | 1,111,000,000 |
| Faroese (`fo`) | 700,000 | 1,111,000,000 |
| Dutch (`nl`) | 350,000 | 555,500,000 |
| Swedish (`sv`) | 350,000 | 555,500,000 |
| Polish (`pl`) | 350,000 | 555,500,000 |

## Exact Grounding And Seed Sources

Use the already downloaded, approved releases and record their revisions and
checksums. Any newly fetched revision needs a delta review and deduplication.

| Language | Native text grounding repository |
| --- | --- |
| NL | `danish-foundation-models/dutch-dynaword` |
| NB, NN | `danish-foundation-models/norwegian-dynaword`, explicitly separated native variants |
| SV | `danish-foundation-models/swedish-dynaword` |
| IS | `danish-foundation-models/icelandic-dynaword` |
| FO | `danish-foundation-models/faroese-dynaword` |
| PL | `SlayerLab/polish-dynaword` |

Source-card references: [Norwegian DynaWord](https://huggingface.co/datasets/danish-foundation-models/norwegian-dynaword),
[Faroese DynaWord](https://huggingface.co/datasets/danish-foundation-models/faroese-dynaword),
[Polish DynaWord](https://huggingface.co/datasets/SlayerLab/polish-dynaword).
Native source availability, especially unique clean Faroese passages, must
be measured before committing full quotas. If exhausted, report a shortfall;
never silently duplicate passages or substitute Danish/Bokmal text.

### Family Construction

1. **Multi-turn:** 3-6 user/assistant exchanges. Half grounded in native
   DynaWord passages, half new everyday scenarios. Use task structures from
   `schneiderkamplab/dfm11-koolbardi-en`,
   `schneiderkamplab/dfm11-koolbardi-da`, and
   `schneiderkamplab/dfm8-synthetic-multiturn-danish-english-chat`.
   Allocate 30% follow-up/reference resolution, 25% revision of requirements,
   20% clarification, 15% collaborative writing and 10% correction/recovery.
   User and assistant text should be natural target-language writing.
2. **Grounded instructions:** native DynaWord documents; 35% factual QA,
   25% grounded explanation, 20% comparison/synthesis, 20% extraction with
   explicit output contracts. Preserve evidence spans and include the relevant
   text in learner prompts for passage-dependent questions. Sample broadly
   across files, domains, dates and document lengths, not file prefixes.
3. **OpenHermes:** use only `schneiderkamplab/dfm8-openhermes-en` and
   `schneiderkamplab/dfm8-openhermes-da`, never raw OpenHermes. Per language,
   50% audited semantic translation and 50% newly written local scenarios
   based on task intent. Allocate 50% of seed selections to a shared cross-language
   bridge set and 50% to language-specific nonoverlapping seeds. Exclude seeds
   already covered in that language by Dolci/UltraChat/Scandi.
4. **Summary/rewrite:** native DynaWord passages, 40% summaries (one sentence,
   two sentences, bullet list, longer), 40% audience/register/tense rewriting,
   20% multiple simultaneous explicit constraints. Reuse task designs, not
   outputs, from `schneiderkamplab/dfm8-synthetic-danish-summarization-rewrite-controls`
   and `schneiderkamplab/dfm8-synthetic-constrained-format-following`.
5. **Math/code:** 50% newly parameterized, verifiable math problems and 50%
   executable code/debugging tasks. Seed designs from
   `schneiderkamplab/dfm8-synthetic-strict-math-answer-contract`,
   `schneiderkamplab/dfm8-synthetic-code-debugging`, and
   `schneiderkamplab/dfm11-mathagentic-tinygsm-python`.
   Preserve programming syntax; explanations and requests use the target
   language. Enforce explicit direct/CoT answer contracts; symbolic/numeric
   checking and sandboxed tests override judge impressions.
6. **Tool dialogues:** use schema/task structures from
   `schneiderkamplab/dfm11-glaive-native-tool-use-repaired`,
   `schneiderkamplab/dfm11-toolace-native-tool-use-repaired`, and
   `schneiderkamplab/dfm11-synthetic-native-tool-calling-repaired`.
   Allocate 30% single-call, 25% clarification-before-call, 25% multi-step,
   10% tool-error recovery, 10% correct no-call decisions. Keep function names,
   schema keys, role tags and structural delimiters untranslated. Validate
   arguments and state transitions against mock tools; include grounded
   user-language responses after tool results. Do not revive DFM8's superseded
   tool-target serialization.

This enlarges existing *capability families* with new examples, not by repeating
existing accepted rows. It does not add more DaLA, identity, raw continuation,
or standalone translation quotas. Existing DFM12 remains the baseline.

## Teacher, Audit And Acceptance

- Generator: `google/gemma-4-31B-it`.
- Independent inference pass auditor: `google/gemma-4-26B-A4B-it`, separate
  prompts, no generator self-assessment shown. Same-family correlated errors
  remain a risk; this is not independent human validation.
- One replica per available B200. Start concurrency from measured pilot
  behaviour, not 512 simply because short DaLA audits tolerated it. Pilot
  generation at 64/128 and compare accepted tokens per GPU-hour; audit at
  128 with bounded CPU preparation. Measure KV use and preemption. Reserve
  the whole node only when authorized; do not share GPU reservations with
  live training or alter current scheduler jobs.
- Require language/variant quality, instruction-response coherence, factual
  grounding and usefulness. Verify structure/length/duplicates before GPU audit.
  Preserve rejection reasons. Retain original language labels and source IDs.
- Native-speaker review: at least 100 pilot examples per language, stratified
  by task family, with special attention to FO/IS/NN and Danish/NB leakage.
  If unavailable, mark the gate pending rather than claiming native quality.
- Freeze evaluation exclusions, use train sources only, and exclude known
  benchmark questions/answers from seeds. Group all derived siblings by seed
  when splitting. Reserve 500 additional held-out examples per language;
  they are outside the training-row targets and covered by budget reserve.
- At most two grounded instruction variants per passage window in a family;
  cross-family sibling IDs and near-duplicate checks prevent superficial
  repetition. Keep a topic/source allocation ledger and cap dominant sources.
- Audit each finished shard immediately. Atomic temporary-file promotion,
  content-addressed IDs, leased jobs, checkpointed row results, one merged
  writer per output package. Retry infrastructure failures at most three times;
  retain terminal row failures and do not silently count them as accepted.
- Candidate factor 1.25 assumes 80% end-to-end acceptance. If yield is lower,
  revise costs or scope explicitly; do not relax gates to fill targets.

## GPU Budget

All costs below are **B200 GPU-hours**, not node-hours. Estimates, not a new
benchmark: local DFM12's 23,388 audit rows/min across eight GPUs came from a
short, changing-corpus measurement and must not be extrapolated to multi-turn
generation. See [audit observations](dfm12-audit-readiness.md) and the older
[31B generation cost envelope](mimir-v1-evaluation-gap-analysis.md#cost-envelope).

Central assumptions:

- 80% accepted yield, so 3.85M accepted needs about 4.8125M candidates.
- 31B generation sustains 300 newly emitted tokens/second/GPU end to end,
  including prompt/prefill time amortized across requests. This is an explicit
  planning assumption requiring pilot measurement, not a measured rate here.
- Mean generated response/serialization tokens per candidate: 900 multi-turn,
  450 grounded, 450 OpenHermes, 350 rewrite, 750 math/code, 500 tool dialogue.
  These are different from learner tokens, which count prompts and histories.
- Auditor sustains 10,000 complete decisions/GPU-hour for these longer inputs.
- Add 20% GPU reserve for bounded retries, selective repairs/re-audits,
  startup and tails. If generation is split into multiple calls, count all
  output tokens and request overhead, not merely the final stored answer.

Formula: generation hours = candidates x mean emitted tokens / (300 x 3600).
Audit hours = candidates / 10000. Budget = 1.2 x (generation + audit).

| Family | Generation GPU-h | Audit GPU-h | Budget incl. reserve |
| --- | ---: | ---: | ---: |
| Multi-turn | 859 | 103 | 1,155 |
| Grounded instructions | 573 | 138 | 852 |
| OpenHermes adaptation | 430 | 103 | 639 |
| Summary/rewrite | 223 | 69 | 350 |
| Math/code | 286 | 41 | 393 |
| Tool dialogues | 127 | 28 | 186 |
| **Total, rounded** | **2,499** | **481** | **3,600** |

Unrounded central total is 3,575.8 GPU-hours, about 447 node-hours or
18.6 active days on eight dedicated B200s. Planning range: approximately
2,100-5,700 GPU-hours (11-30 active days), varying generation from
500 to 200 tokens/s/GPU and audits from 20,000 to 5,000 decisions/GPU-hour.
Native review delays, engineering, CPU tokenization, uploads and future model
training are excluded. Human-quality failures or corpus exhaustion can widen
this range materially. This is not an ETA for work already launched.

### Alternative: 26B-A4B For Generation As Well

Requested cost sensitivity, 2026-09-25; not a teacher change or launch approval.
The central audit budget already uses 26B-A4B. Holding lengths and accepted
yield fixed, total GPU-hours = 1.2 x (2498.553 / generation_speedup + 481.25).

| Generation speed relative to 31B assumption | Total B200 GPU-hours | Active days on eight B200s |
| --- | ---: | ---: |
| 1.5x | 2,576 | 13.4 |
| 2x | 2,077 | 10.8 |
| 3x | 1,577 | 8.2 |

These are scenarios, not measured A4B speedups or confidence intervals. No
matched benchmark establishes a 2-3x speedup on this workload. Effective
parameter count alone cannot determine the speedup. Compare accepted rendered
training tokens per GPU-hour, language fidelity and verifier success on the
same stratified pilot. A fall from 80% to 65% accepted yield increases these
fixed-length costs by approximately 23%. Using the same model for generation
and audit also increases concern about correlated mistakes; separate prompts
do not substitute for native-speaker checks and deterministic verification.

## Staged Execution And Deliverables

1. CPU planning: freeze seed revisions, broad native-document reservoirs,
   deduplication against accepted DFM12, 42 dataset manifests, evaluator firewall,
   deterministic validators, and per-language task allocations.
2. Pilot: 5,000 accepted conversations/language (35,000 total), proportionally
   distributed over all six families. Budget 50-80 GPU-hours including startup
   and pilots across concurrency settings; successful rows count toward totals.
   Recompute row lengths, yield and GPU-hour estimates; do not begin full
   production until language-quality gates pass.
3. First tranche: half every target, 1.925M accepted and approximately
   3.05525B tokens. Central budget roughly 1,800 GPU-hours including the pilot.
   Publish accepted-only packages and assess practical multilingual behaviour
   before committing the second half.
4. Second tranche: fill the remaining half only if quality/diversity remains
   good. Immutable shard IDs permit incremental uploads to the same 42 repos.
5. Final audit receipts, CPU tokenization and per-language/family token report.
   Retain Gemma 4 training template and tokenizer settings; no template migration.
   Repeat 1 for all new datasets. Integration is a separately approved build.

## Resulting Corpus And Exposure

| Quantity | Tokens per epoch at repeat 1 |
| --- | ---: |
| Current DFM12 | 106,799,766,039 |
| Proposed extension | 6,110,500,000 |
| Proposed enlarged DFM12 | 112,910,266,039 |
| All additions beyond DFM11, old plus proposed | 9,695,661,337 |

The extension alone would be about 5.41% of the enlarged broad epoch. It does
not automatically achieve 15-25% multilingual exposure. For a focused stage,
one pass of the extension plus 24.442B broadly sampled anchor tokens would
make a 30.5525B-token mixture with 20% extension. That is a separate sampling
proposal, not a request to repeat these rows four times in the broad corpus.
Actual multilingual share also includes retained DFM12/DFM11 sources and must
be measured rather than inferred from dataset names.

Aya and additional unexamined HF repositories are deliberately outside these
totals: overlap, eligible splits and usable supply have not been established.
Any cheap native-data expansion found later can replace matching synthetic
quotas after audit, not silently inflate or duplicate the agreed budget.

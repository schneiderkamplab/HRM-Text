---
type: Runbook
title: DFM13 Multilingual Evaluation Preparation
description: CPU-verified heldout tasks and versioned expanded headline populations.
status: draft
last_updated: 2026-10-06
confidence: high
tags: [dfm13, evaluation, multilingual]
---
# DFM13 Multilingual Evaluation Preparation

## Scope and Ownership

The added languages are LT, LV, SQ, BE, BS, BG, HR, HU, LB, SR, SK,
SL and FA. Together with the previous19 non-Danish/English languages and
Danish/English, these form34 languages. Epicurus owns scheduling; Boole
independently checks heldout coverage. This preparation changed no active
plan, W&B workspace, training settings or GPU processes.

## Verified CPU Artifacts

`data/dfm13/multilingual-evals-20261006-v1/completion.json` binds the
generated configurations and preflight receipts.

* `config/dfm13_dala_heldout_20261006.json`: selected heldout pairs and pins.
* `config/dfm13_dala_heldout_registry_20261006.json`: scheduling registry.
* `config/dfm_evals_dfm13_multilingual_20261006.yaml`:26 task definitions.
* `config/dfm13_dala_heldout_preflight_20261006.json`: actual CPU task construction.
* `config/euroeval_dfm13_multilingual_20261006.yaml`:84 available EuroEval jobs.
* `config/euroeval_dfm13_multilingual_access_20261006.json`:84 successful authenticated metadata/access checks and revisions.

Each new language has1000 deterministic, accepted DaLA v2 pairs from
`test_representative`, never train. Each pair supplies a clean and corrupted
example, yielding2000 examples per task and52000 across26 LA/GEC tasks.
Source hashes, split provenance, audit decisions and matching LA/GEC pair
identity are checked. Producer prompts are preserved verbatim, including
English instructions; they are not claimed to be native-language prompts.
Decontamination evidence covers the finalizer's exact-text/document checks,
not a new whole-corpus semantic-overlap certification.

EuroEval18.1 availability by language: LT8, LV8, SQ8, BE6, BS5, BG7,
HR7, HU8, LB5, SR8, SK7, SL7, FA0. There are46 explicit unavailable
slots among130 language/category slots. All13 lack registered native
tool-calling and values tasks. Availability does not certify training cleanliness.

## Versioned Averages

`config/multilingual_headline_populations_dfm13_20261006.json` defines:

* `dfm13_new_languages_v1`:13 languages,110 metric bindings.
* `dfm13_multilingual_v1`:32 languages,287 bindings.
* `dfm13_all_languages_v1`:34 languages,322 bindings.

Metrics are normalized explicitly, averaged within each language and then
equally across languages. Required available tasks must all be present;
missing runs do not silently reduce the denominator. All new LA bindings use
`semantic_v1/macro_f1`, matching the inherited languages. Sample logs retain
the strict scorer, but the merge derives semantic metrics from full outputs.
Standalone English labels and conservative native yes/no labels are accepted;
prose extraction, mixed labels and truncated outputs remain invalid.

Superseded2026-10-06: the initial construction-only readiness statement and
strict-average bindings missed an unsupported-language error in the merger.
The semantic parser now supports all13 new languages without changing any old
aliases. Actual2000-sample datasets per language were passed through the real
scorer and `task_metrics` using simulated English yes/no, correct/incorrect,
and native yes/no completions:78000 scored/merged outputs, all perfect as
expected. A focused test also feeds merged outputs into the actual new
population collector. These CPU checks do not certify model performance or
native prose quality. The default manifest path was verified correct:
`parents[3]` is the repository root, not the nested dfm-evals directory.

The34-language population uses only
`dfm_eval/generative-talemaader/model_graded_fact_v2/accuracy` for Talemaader.
The collector discovers sibling `merged_metrics_v2.json` for this exact key
only, retaining checkpoint validation and duplicate-key rejection. Historical
keys still read historical artifacts. There is no fallback from missing v2
scores to old Talemaader scores. Parent supplies the3150 rejudge artifact
after train3200 and before baseline averaging.

## Commands and Handoff

CPU construction verification:

```bash
dfm-evals/.venv/bin/python -m scripts.check_dfm13_multilingual_evals
```

Use the new registry paths above in the scheduler-owned additions. Average
dispatch retains `scripts/log_multilingual_headline_averages.py` with
`--manifest config/multilingual_headline_populations_dfm13_20261006.json`
and existing root/epoch/step/report arguments. Additional baseline roots
may be supplied through the existing collector interface. This page is a
handoff, not authorization to run evaluations or alter historical metrics.

Focused tests passed:91 semantic/registry/average tests and18 heldout,
scoring/merge/average tests. All26 real task constructions and the13-language
simulated semantic merges passed without model calls.

See [evaluation expansion](dfm13-evaluation-expansion.md) for parent scheduling.

## Additional V2 Tasks for the Existing21 Languages

User authorization2026-10-06 adds, rather than replaces, accepted-v2 heldout
tasks for `da en nb nn sv is fo nl pl de fr es it cs pt_pt fi et ca el ro uk`.
The42 distinct suite names are `dala_v2_<language>` and
`gec_dala_v2_<language>`. Existing legacy task names, populations and the13
new-language task names remain unchanged. Danish gets the same1000 accepted
pairs and2000 balanced examples per task in this new benchmark; the older
Danish benchmark's population is not modified.

Preparation uses the same accepted compact-v2 test-representative selection,
seed4242, split checks and source/audit hashes as the13-language expansion.
The Portuguese package retains source spelling `pt-PT`; evaluator names use
`pt_pt`, without relabeling its original provenance.

Exact scheduler handoff files:

* `config/dfm13_dala_v2_existing21_20261006.json`: heldout manifest.
* `config/dfm13_dala_v2_existing21_registry_20261006.json`:42 suites, four shards each.
* `config/dfm_evals_dfm13_dala_v2_existing21_20261006.yaml`: task definitions.
* `config/multilingual_headline_populations_dfm13_dala_v2_20261006.json`: additive average definitions.

The successor32-language and34-language population IDs are
`dfm13_multilingual_v2` and `dfm13_all_languages_v2`. They retain every old
binding and add two v2 metrics per applicable language. The13-language-only
population remains unchanged. LA uses
`dfm_eval/dala_v2_<language>/semantic_v1/macro_f1`; correction uses
`dfm_eval/gec_dala_v2_<language>/exact_match/mean`. A missing new task prevents
a complete successor average, rather than silently shrinking its denominator.

CPU commands:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m scripts.prepare_dfm13_dala_v2_existing21
dfm-evals/.venv/bin/python -u -m scripts.check_dfm13_dala_v2_existing21
```

`data/dfm13/dala-v2-existing21-evals-20261006-v1/preparation.json` records
selection readiness. Only `completion.json` records the completed real-task
construction, simulated scoring/merge and average-path checks. Simulated
metrics under this root are diagnostics, not evaluation scores to log.
Epicurus owns plan integration; Boole can use the manifest for independent
heldout coverage verification. No plan, W&B or GPU operations are performed
by these commands.

Completed2026-10-06: all21 selected snapshots have1000 accepted pairs;
all42 real tasks constructed with2000 samples each. Simulated English/native
LA outputs and exact-reference GEC outputs passed actual scorers and merger;
the complete successor averages evaluated to1.0 with explicitly simulated
other-task controls. The first preflight correctly withheld the34-language
average because the diagnostic harness omitted its standard-metric root;
the harness was corrected, regression-tested and rerun successfully, without
relaxing collector coverage gates. The successor definitions contain325
bindings across32 languages and364 across34. Tests:94 semantic/average tests
and40 task/sharding/merge tests passed. Both this42-task completion receipt
and the original26-task CPU preflight are refreshed. No real model scores
were generated or logged.

## TODO5 Historical Averages Preparation (2026-10-06)

Critical logging correction supersedes implicit-cursor wording below: existing
training panels explicitly use `_step`, so `utils/training_wandb.py` now uses
a stable initial logging-only offset `max(0, run.step-first_optimizer_step)`
and explicit `step=max(optimizer_step+offset, run.step)`. This retains optimizer
spacing instead of compressing five-step logging intervals to one. Same-step
rows remain monotonic; `train/step` always contains the true optimizer step.
No optimizer/cursor/LR or panel-axis changes.49 focused tests pass. The new
helper pin must be refreshed by Epicurus; the pretrain integration is unchanged.

Authorized3154500-pause update supersedes the unresolved logging-risk note
below. `pretrain.py` now uses `utils/training_wandb.py` at all four logging
calls. Exact optimizer coordinates are recorded as `train/step`, independent
of W&B's implicit append cursor. No optimizer/cursor/LR state changes, history
rewrites, training starts, or remote sync were performed by this agent.
Parent must refresh owned source pins and include the helper before resume.
44 focused tests pass, including lower-optimizer-step/higher-history-cursor
logging and both authorized pause guards. Final67-point payload:
`logs/rejudge_talemaader_v2/averages/prepared-pause3154500-final-v2.json`.
The explicit command is `python -m scripts.prepare_talemaader_v2_averages
--sync-prepared <that-path> --paused-step 3154500`, after the raw-score writer
finishes. This does not authorize overlapping writers. Exact source hashes and
handoff are in `docs/reports/todo5-averages-handoff-20261006.md`.

Future logger implementation: existing average dispatch accepts
`average_prefix=headline_avg_talemaader_v2`,
`extra_average_prefixes=[suite_avg_talemaader_v2]`, `average_scope=all`,
`atomic_v3_averages=false`. Native v2 `merged_metrics.json` and historical
v2 sidecars are checkpoint/count validated; conflicts fail.36 focused tests
passed including real dispatch with a fake W&B sink. Legacy definitions and
production scheduling were not modified. The refreshed hash-bound payload is
`logs/rejudge_talemaader_v2/averages/prepared-future-compatible-v2.json`.

Important limitation superseding an assumption that pause-only sync is enough:
SDK0.27.0 increments internal `_step` per committed row regardless of custom
eval axes. Appending67 rows at3200K still advances beyond an explicit-step
training resume at3200000. Without changing production training logging, defer
historical curve appends until training ends; summary/table-only publication
cannot supply those curves. A separately authorized durable fix is independent
`train/step` plus implicit W&B internal steps and serialized writers. Neither
that training change nor any remote writes were performed in this task.

Superseding historical-panel decision: the seven-point semantic proposal below
must NOT replace full-history panels. The final payload is
`logs/rejudge_talemaader_v2/averages/prepared-talemaader-only-v2.json`, with67
points for `headline_avg_talemaader_v2/{danish,overall}` and
`suite_avg_talemaader_v2/dfm`. It uniformly preserves strict DaLA and current
membership, replacing only the idiom scorer; completeness counts expose
missing inputs. Overall uses current available section means without a
multilingual term.33 older overall differences are explained by historical
three-section vs current eight-section membership.150K/800K/1650K retain
input/recipe warnings, not automatic rejection of a newly defined series.
Semantic-v2 and32/34-language populations remain separate. The deferred sync
command below must use the new payload path. Future pure API is
`talemaader_only(metrics, point)`.24 focused tests passed; no remote writes.

`scripts/prepare_talemaader_v2_averages.py` prepares CPU-only artifacts for
the current XL run. Preparation never calls `wandb.init`, `log`, or sync.
An explicit, separate `--sync-prepared` mode is reserved for the scheduler's
3200K pause; it refuses any live Python/torchrun `pretrain.py` process.
The optional `--fetch-history` uses only the read-only API, records exact
per-metric history selection evidence, and creates an immutable source snapshot.
The full 67-point inventory remains `logs/rejudge_talemaader_v2/manifest.json`.

New keys are `headline_avg_semantic_v2/danish`,
`headline_avg_semantic_v2/overall`, and `suite_avg_semantic_v2/dfm`.
They replace the old idiom scorer with `model_graded_fact_v2` while retaining
semantic DaLA. Missing semantic DaLA is a documented block, never a fallback
to strict DaLA. Historical English/math memberships and normalization remain
unchanged. Overall retains the existing mean of available section means;
multilingual is NOT added to overall. Counts and definition hashes are emitted.

The existing Task 2 registry supplies separate
`avg_population/dfm13_multilingual_v1` (32 non-Danish/non-English languages) and
`avg_population/dfm13_all_languages_v1` (34 languages). These remain
complete-coverage-only. Historical missing languages produce explicit coverage
reports, not a 19-language score relabeled as 32. Old average keys are never
written by this helper.

```bash
python -m scripts.prepare_talemaader_v2_averages \
  --fetch-history logs/rejudge_talemaader_v2/averages/source-history-v1.jsonl \
  --output logs/rejudge_talemaader_v2/averages/prepared-v2.json

# Refresh after remaining rejudge sidecars complete, without new API reads:
python -m scripts.prepare_talemaader_v2_averages \
  --history-jsonl logs/rejudge_talemaader_v2/averages/source-history-v1.jsonl \
  --output logs/rejudge_talemaader_v2/averages/prepared-v2-final.json
```

Prepared output contains `rows`, per-point `coverage.blocked_reasons`, original
average reconstruction checks, input hashes, and a canonical `rows_sha256`.
An original-average reconstruction mismatch suppresses affected replacement
headline/suite scores. No history point is assumed complete merely because a
sampled API query returned it. Missing train-step axes are recovered only by
exact inventory epoch with explicit evidence; inconsistent axes are excluded.
Confirmed example: a historical EuroEval row uses the 200K epoch but a 150K
train-step axis. This helper does not repair remote history.

Parent/Epicurus owns the deferred single-writer sync at the planned 3200K pause
and future scheduler wiring. Do not run a second W&B writer during training or
replay old averages. `compute(metrics, point, registry)` is the pure future-row
API; the existing 32/34-language population logger remains usable unchanged.
Boole's workspace inspection is separate; no workspace panels are changed here.

Verified preparation outcome: all 67 rejudge sidecars are included in
`logs/rejudge_talemaader_v2/averages/prepared-v2.json`. Seven checkpoints
(epoch10 and 2900K through 3150K) have semantic-v2 Danish/DFM/overall values.
The other60 have no semantic DaLA metric. In addition,36 historical points
have one or more original-average reconstruction mismatches (39 comparisons).
The report records182 matching comparisons and181 absent original averages.
These limitations are explicit; old scores remain untouched and missing
semantic scores are not replaced by strict scores. Neither32 nor34-language
historical coverage is complete, so their overall population scores are absent.

Deferred command for Epicurus, ONLY at the planned pause:

```bash
python -m scripts.prepare_talemaader_v2_averages \
  --sync-prepared logs/rejudge_talemaader_v2/averages/prepared-v2.json \
  --paused-step 3200000
```

This action verifies source hashes and all rejudge sidecars, registers exact new
keys, and uses one writer session without historical explicit `_step` values.
A durable started marker prevents blind retries after an uncertain sync; a
matching completed receipt makes repeat invocation a no-op. The receipt records
the next W&B internal step. The scheduler must ensure resumed training's
explicit steps exceed that high-water mark; a pause alone does not eliminate
the pre-existing explicit-step collision risk. CPU verification:21 focused
preparation/semantic-average tests passed. No live W&B writes were performed.

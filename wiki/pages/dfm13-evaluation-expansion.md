---
type: Plan
title: DFM13 Evaluation Expansion and Talemaader Repair
description: Five authorized evaluation tasks while XL trains from 3150K to 3200K.
status: draft
confidence: high
last_updated: 2026-10-07
tags: [evaluation, multilingual, dfm13, talemaader]
---
# DFM13 Evaluation Expansion

## Historical Available-Metric Policy (2026-10-07)

Owner explicitly superseded the complete-only emission policy for the new
averages: backfill the XL and XXL-wide historical checkpoints using the valid
metrics available at each checkpoint. Missing metrics are omitted, never zero
filled. Retain task membership, metric normalization and weighting; language
averages use their available tasks, and multilingual aggregates use available
language means. Emit counts, expected counts, coverage and completeness so
changing historical coverage is visible. All-missing groups have no score.
Do not substitute old Talemaader judgments for v2 or mix checkpoints/epochs.

This changes average emission, not evaluation scheduling: all scheduled tasks
are still required to run and merges/finalization precede training. Historical
backfills must serialize W&B writes with the scheduler and preserve actual
fractional evaluation epochs. The earlier complete-only claims below describe
the superseded policy, not the new requested historical behavior.

## Averaging Interpreter Recovery (2026-10-07)

At05:05-05:07, apparent GPU idleness during3200 multilingual DaLA was
inter-shard overhead, not a stopped runner: ten jobs completed between status
snapshots, with no new failures. Czech acceptability shard2 evaluated500samples
in5seconds but occupied its lane for about30seconds. Persistent servers were
reused; client startup and CPU EEE export retain the GPU slot. Scheduler job
claims/status updates also serialize full reads/writes of the roughly52MB plan.
Two-second GPU samples showed brief94-100percent bursts separated by zeroes.
Do not restart healthy servers to address this; investigate CPU finalization
and plan-update overhead before changing inference batch sizes.

Training reached3200000 normally at02:20. The3150wave34 baseline then ran,
but averaging inherited `python_bin=resume_xl_dfm12_epoch11.sh` from the export
template. That wrapper routes non-export arguments to training and rejected
the averaging CLI. This blocked later jobs; scheduler exited03:13 after cleanup.

Under the plan lock, corrected22 wave34/v2 average rows to the concrete hrm
Python, resetting only the failed3150wave34 average. Preserved all4828completed
jobs and the intentional Talemaader-specific averaging wrapper. Recovery and
actual dispatch validation: `data/dfm13/average-python-recovery-20261007/`.
Both installers now select the actual interpreter, with regression tests that
call `runtime.run_average` using poisoned export-template interpreter metadata.
Validate generated argv for each action, not just dependency graphs or row counts.

Scheduler resumed03:29; the previously failed average completed and synced at
03:29:55. The3250training command was verified to resume `step_3200000` using
the existing DFM13 directory and W&B run. Training/source pins remain valid;
baseline finalization gates3200evals and3200finalization/cleanup gates3250training.
Historical seven VALEU failures are nonblocking and were not reset.

Workspace verification also scanned history separately for34 panels. For
atomic population/expanded baseline rows it now verifies all required keys in
one scan bounded to the latest2000internal history steps (explicit lower-bound
override supported); checkpoint identity, coverage and exact-definition checks
remain mandatory. Historical67-point verification is unchanged. Restarted only
the read-only workspace child, refreshed its two workspace-row source pins,
and reset that report under lock. The population workspace then completed in
12seconds at03:33:50 without rewriting history. Tests cover the bounded atomic
scan and both average installers (31focused tests pass).

Both workspace jobs succeeded. The3200EMA export completed03:35:04 and all
eight GPU lanes started EuroEval jobs03:35:12-20, with calibrated task batches,
non-eager persistent vLLM, training-compatible tokenizer and0.95utilization.
The3250continuation remains queued after3200finalization and teardown; no
training optimizer step was changed by this recovery.

## Expanded Traditional Averages

The2026-10-06 opt-in `scripts/log_expanded_dala_v2_averages.py` adds exact AVG
dispatch prefixes `headline_avg_dala_v2` and `suite_avg_dala_v2`. It does not
change the67historical Talemaader-v2 points, legacy logger or training logger.
Parent/Epicurus owns installing one dependent AVG row per checkpoint; Boole owns
panels. Use `average_prefix=headline_avg_dala_v2` with
`extra_average_prefixes=[suite_avg_dala_v2]`. This supersedes the initial two-row
handoff: one writer emits both namespaces atomically, avoiding concurrent W&B
history writes and the prior lost-Danish-history failure mode.

Danish has20tasks (old18, Talemaader scorer replaced by v2, plus2DaLA-v2);
English has17(old15plus2DaLA-v2). Overall retains the same eight equally weighted
traditional sections, with no multilingual section added. The DFM-suite mean
has99unique tasks: original31with Talemaader-v2 plus26new13-language tasks plus42
existing21-language v2 tasks. Strict historical Danish DaLA is retained.

Both new namespaces require all125unique source metrics before emitting any
scores. No missing-v2 fallback or partial-population mean is allowed. Repeated
additional standard/DFM/EuroEval roots support separate evaluation campaigns;
ambiguous artifacts and checkpoint mismatches fail closed. W&B metrics register
explicitly against each new prefix's epoch and commit in one row per invocation.

Actual3150K collection resolved57historical metrics and found exactly68new
metrics pending: no historical omissions or root-binding errors. Receipt:
`data/dfm13/expanded-dala-v2-averages-20261006/step3150000-dry-run.json`.
Twelve focused CPU tests cover weighting, completeness, strict retention, no
fallback, extra roots, wrong checkpoints, atomic logging and scheduler dispatch.
Integration contract: `docs/reports/dfm13_expanded_dala_v2_averages_handoff_20261006.md`.

## Authorized Work

1. Repair generative Talemaader judging and rejudge all historical evaluation
   points belonging to `peter-sk-sdu/DFM5/dfm8-xl-from-dfm6-dfm7-epoch5-clean-full`.
2. Add multilingual evaluation coverage for DFM13's thirteen new languages:
   Latvian, Lithuanian, Albanian, Belarusian, Bosnian, Bulgarian, Croatian,
   Hungarian, Luxembourgish, Serbian, Slovak, Slovenian, and Persian.
3. Prepare their **3150K baseline now**, but execute it **after training reaches
   3200K and before the 3200K evaluations**, including associated new averages.
   Do not interrupt the current training segment. Extend future coverage too.
4. Verify actual held-out DaLA versus DaLA v2 evaluation sources, splits and
   completion status across all evaluated languages. Dataset presence alone is
   not evidence of an active or completed evaluation.
5. Update the existing workspace at
   `https://forge.coreweave.com/wandb/peter-sk-sdu/DFM5?nw=3fvncok3gjh`
   to the new multilingual coverage, associated averages, and Talemaader v2.
   Back up the latest workspace first and preserve its user-defined layout.
   Version averages whose inputs or populations change; retain old histories.
   Preserve the previously agreed overall-average weighting rather than silently
   adding multilingual scores to it. Prepare backfills now, but synchronize
   only during the planned training pause, with explicit fractional-epoch axes.

## Owner Update: 3154500 Pause and Additional DaLA v2

On2026-10-06 the owner superseded the3200K historical-sync timing: stop after
`ephemeral_step_3154500` is fully written and synchronize the repaired
Talemaader history and averages during that pause. Resume from the exact saved
optimizer step and cursor; never advance training steps to catch W&B's internal
history counter. A logging-only monotonic-history fix is being prepared for
future processes, without changing training calculations.

TODO4 is expanded: add accepted DaLA v2 acceptability and correction heldouts
for all21 existing languages as42 distinct additional tasks. Do not replace
legacy heldouts or reuse their metric keys. Include the additional tasks in
new versioned average definitions and workspace panels. Apply this to the
3150K baseline and subsequent3200K+ checkpoints.

The active persistent-vLLM plan is non-eager, matching the earlier calibration.
Family-calibrated batches are inherited (DaLA512, GEC256); standard and
EuroEval tasks retain their task-specific calibrated settings. Utilization is
0.95 normally and0.85 for judged Talemaader. New language equivalents inherit
family settings rather than being claimed as separately calibrated.

The authorized pause completed: `ephemeral_step_3154500` was validated and
preserved under `checkpoints/preserved/dfm13-pause-3154500`. Both67-point
historical writes completed in the original run while training was stopped.
The average receipt records W&B's next internal step3154630; optimizer step
remains3154500. `TrainingWandbLogger` separates `train/step` from W&B's history
cursor, so resuming must not skip optimizer steps to catch that cursor.
The five historical panel replacements were remotely verified, including
Talemaader v2 at0.3855198 for3150K. The previous deferred3200K-sync instructions
below describe the superseded timing, not outstanding work.

The additional42 tasks are installed for3150K and all3200K+ evaluations.
Receipt: `data/dfm13/dala-v2-plan-20261006/installed.json`. They add to, not
replace, the old tasks. Their expanded average histories begin only once the
new baseline finishes; no earlier scores are invented.

## Talemaader v2

The old judge explanation exceeded a 64-token limit and its missing grade was
silently counted incorrect. Details are in
[serving findings](model-architecture/vllm-hrm-text-serving-status.md).
The replacement asks only for `GRADE: C`, `GRADE: P`, or `GRADE: I`, with
temperature zero and maximum 64 output tokens. Values remain 1, 0.5, and 0.
Invalid or truncated judgments are retried once and then fail explicitly; they
are never interpreted as wrong model answers. Future Inspect scorer and merge
use `model_graded_fact_v2/{accuracy,accuracy_stderr,n}` under
`dfm_eval/generative-talemaader/`. Old metric histories remain unchanged.
Reference definitions and original model generations are not edited.

`scripts/rejudge_talemaader_v2.py` reads saved Inspect answers, validates sample
counts and duplicate identities, caches judgments by full prompt hash, and uses
one append-only writer with an exclusive process lock. Results, source manifest,
per-GPU launch receipts, and progress are in `logs/rejudge_talemaader_v2/`.
**Owner clarification:** rejudge all available local archives; unavailable
historical archives from the previous machine do not block local completion.
Preserve their inventory for a later run on that machine. Optional retrieval
source is `ssh.cloud.sdu.dk:6768:/work/dfm/HRM-Text`; do not invent missing results.

Eight independent Transformers E4B judge servers use ports38600-38607. The
5.25GiB per-layer embedding lookup table stays on CPU, while only looked-up rows
are transferred. Weights remain BF16. This optional server mode consumes about
10.5GiB/GPU, fitting the observed13.7-16GiB training headroom. An11.5GiB PyTorch
allocator ceiling bounds each judge; the server option defaults off. Initial
positive/negative controls returned correct four-token grades. Production
training and unrelated GPU processes are untouched. The client shuts down only
servers matching this campaign's recorded PIDs and command lines on exit.

W&B synchronization is queued for the next planned training pause, **not** a
second concurrent history writer during explicit-step training. Only new metric
keys and explicit epoch/step axes are appended. Do not replay old averages or
old task values. Any averages adopting the repaired score need their own new
version, not a silent change to historical average definitions.

## Status

At initial launch,48 of67 historical points had verified local input archives
(38,784 sample instances). Nineteen remaining archive mappings are being
recovered. GPU judging started immediately on available points rather than
waiting on archive discovery. Generation remains unchanged and does not use
the training model for this repair.

**Subsequent inventory resolution:** all67 points were found locally, totaling
54,136 saved sample instances. `manifest.json` is finalized with no missing
points; no remote transfer was needed. `recovery-notes.md` retains the portable
procedure and exact archive mappings. Repeated identical judge prompts reuse
one cached judgment while each checkpoint retains its full sample denominator.

**Completion:** all67 points have now been rejudged successfully, with808
samples per point and no exhausted judge failures. `completed.json` records
the finalized manifest and result hashes. All eight owned judge processes
exited automatically; training was not stopped. W&B synchronization remains
deferred to the scheduled pause at3200K.

## Workspace Preparation

The exact workspace was backed up and110 raw metric panels for the13 additions
were appended inside its existing combined multilingual section (215 to325).
All eight sections, existing panels and run selections were preserved, and the
remote specification was read back successfully. No run history was written.
Receipt: `logs/wandb_workspace_specs/3fvncok3gjh-combined-dryrun-20261006/`.
Old average and Talemaader panels remain until replacement values are synced.
`scripts/patch_dfm13_workspace.py` checks for concurrent workspace edits and
requires synchronization evidence before metric-key replacements.

Historical preparation found semantic Danish DaLA only at seven of67 points.
Do not silently replace the other60 with strict scores under a semantic key,
or switch panels to a series that discards their history. Keep the Talemaader
replacement definition distinct from any semantic-scoring migration.

## Historical Available-Metric Backfill, 2026-10-07

The available-input policy is implemented by
`scripts/backfill_available_eval_averages.py`, reusing the expanded and population
loggers. Payloads retain actual checkpoint axes, raw inputs, observed/expected
counts, completeness and source hashes; missing scores are not imputed.
XXL-wide `DFM5/dfm10-xxl-wide` now has nineteen remotely verified historical
points for the new Danish/English/overall/DFM and all-language v1/v2 averages.
Its all-language values use available Danish/English inputs, not fabricated
34-language coverage. No non-DA/EN population inputs existed there, so those
population scores were omitted. Raw Talemaader v2 is also absent; the final user
clarification requires the Talemaader-only average prefixes to average their
other available tasks, omitting that scorer without aliasing the old scorer.
That supersedes the initial whole-prefix omission and is a separate nineteen-row
delta (`xxl-talemaader-delta-v4.json`). Original six-series verification receipt:
`logs/historical_available_averages_20261007/xxl-v1.remote-verified.json`.
The additional three Talemaader-only series are also synced and independently
verified at all nineteen checkpoints in
`xxl-talemaader-delta-v4.remote-verified.json` in the same directory.

XL's initial 67-point preparation is separate from publication; all-suite union
discovery subsequently found the current3200K checkpoint as point68. Its writer must run
after all3200K sync/average jobs and before3250K training. Fresh preparation at
that boundary must include3200K as the final point to avoid regressing summaries.
All-suite discovery supersedes initial Talemaader-only checkpoint discovery.
W&B event-count discrepancies trigger exhaustive sparse scans and are recorded,
not silently treated as complete metadata. The Ukrainian Winogrande key had
seven advertised versus six actual history events in both retrieval methods.
See `docs/reports/historical-available-averages-handoff-20261007.md` for commands,
serialization requirements, receipts and exact omissions. No XL write is claimed
by this handoff; scheduler ownership and completion must be reported separately.

## Held-out Coverage Finding

The read-only coverage audit inspected163 successful Inspect shard headers.
At3150K the21 previously evaluated languages use Danish legacy DaLA/GEC and
20 older multilingual producer test pools, not the accepted DFM13 compact-v2
heldouts. Danish is specifically `giannor/dala:test` and
`giannor/dala_gen_v3:test`; the latter's v3 is not DFM13's compact-v2.
The13 additions use accepted-v2 representative heldouts. Adding them does not
silently migrate the original21 tasks to another dataset version.
Evidence: `logs/diagnostics/dala_eval_coverage_20261006.{md,json}`.
See [multilingual preparation](dfm13-multilingual-evaluation.md) for new task
and average definitions. Persian has no registered EuroEval task in the checked
installation; it has both DFM acceptability and correction coverage.

## Reusing the Repair Elsewhere

Keep the original Inspect archives and merged metrics unchanged. Build a manifest
with `run_path`, `partial: false`, and one entry per locally available checkpoint
in `points`: `id`, exact `epoch`, `train_step`, absolute `inputs` archive paths,
`expected_n`, `status: ready`, and optional original `merged_metrics` path.
The current inventory and `recovery-notes.md` give all67 original mappings.
Retain a `missing_points` list if some archives are unavailable. Use a separate
output directory for any later disjoint backfill, avoiding replay of synced rows.

Start one judge per chosen GPU with a unique port, using the existing server:

```bash
CUDA_VISIBLE_DEVICES=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /home/ucloud/miniforge3/envs/hrm/bin/python scripts/transformers_openai_server.py \
  unsloth/gemma-4-E4B-it --served-model-name gemma-4-e4b-judge \
  --port 38600 --max-new-tokens 64 \
  --cpu-per-layer-embeddings --cuda-memory-limit-gib 11.5
```

Repeat for GPUs1-7 and ports38601-38607 only after checking real headroom.
Save `{pid, argv, gpu, port}` in `judge-gpuN.json` under the output directory
for verified-PID cleanup. No automatic cleanup is attempted for unrecorded
servers. Launch the client detached, with its `runner.json` PID receipt:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -u scripts/rejudge_talemaader_v2.py \
  run --output logs/rejudge_talemaader_v2 --stop-owned-servers
```

It defaults to those eight URLs; use `--urls` for other ports. After completion,
and **only while no training writer is active**, use `sync --output <directory>`.
Synchronization explicitly registers each versioned metric against
`dfm_eval/epoch`, writes sibling `merged_metrics_v2.json` without replacing old
files, and preserves a sync receipt. It refuses changed already-synced point
sets. Future-task scorer is in the `dfm-evals` submodule; bring those source
changes too, not only the root repair script.

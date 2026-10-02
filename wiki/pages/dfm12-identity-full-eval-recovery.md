---
type: Runbook
title: Identity Full Evaluation Archive Recovery
description: Repair and verification of the final identity EMA suite at step 2897261.
tags: [identity, evaluation, scheduler, wandb]
status: draft
confidence: high
last_updated: 2026-09-28
---
# Identity Full Evaluation Recovery

Related run: [identity continuation](dfm12-identity-continuation.md).
Plan: `logs/scheduler/dfm12_XL_identity_step2897261_ema_full_20260928`.
W&B: `peter-sk-sdu/DFM5/dfm12-xl-identity-da-en-1000`.
Checkpoint: EMA `step_2897261`, fractional epoch `10.050795912217435`.

## Failure And Repair

All 242 enabled GPU evaluation jobs finished successfully, but 39 CPU merge
jobs failed: eight standard merges could not find shard logs, 30 DFM merges
could not find Inspect archives, and the IFEval merge received no archive
inputs. The identity plan builder had overridden every `log_dir` to a per-job
directory while merge metadata still expected the canonical result tree.
This was an orchestration bug, not evidence of inference failure.

Raw outputs were preserved. Repair uses the existing scheduler, restores the
writer/reader directory contract, and resets only CPU work. Original plans
and an `archive-repair.json` manifest remain in the plan directory.
`scripts/schedule_identity_final_ema_full.py` now retains canonical output
paths for future plans. No GPU inference rerun is needed for these failures.

A first alias-based recovery exposed a second issue: recursive pathlib
collection does not traverse EuroEval directory symlinks. Final EuroEval metric
discovery must therefore be checked explicitly before averaging. Serial
merge/sync replay avoids simultaneous W&B writers. Completion must be verified
against local merged results and the remote run, not merely scheduler exit
status. No GPU generation/audit servers were stopped for this recovery.

The original four skipped rows remain outside the enabled suite: EuroEval
valeu-da, Andersen validation inference and merge (unavailable validation
source), and an unrelated report update. Do not claim those ran.

## Completion Verified

Recovery finished with **286 done, zero failed, zero pending/running**, and the
four original skips. All 39 merges were replayed serially through the existing
scheduler. EuroEval metric files are discoverable without following directory
symlinks. A final consolidated W&B write removes uncertainty from earlier
concurrent writers; it contains all local numeric metrics and averages.

`remote-recovery-verification.json` in the plan directory verifies **531 numeric
keys** in both remote summary and one matching history row (internal W&B step
2897332), with no value mismatches or missing numeric schema entries. The
checkpoint remains **2897261**, fractional epoch **10.050795912217435**;
the W&B internal history index is not the checkpoint step. Local collectors
find 195 standard, 129 DFM and 176 EuroEval numeric entries before axes and
averages are combined. Headline averages cover 18 Danish, 15 English and four
Math/Code metrics; suite averages cover eight standard, 31 DFM and 18 EuroEval
metrics. Regression tests for the plan builder and artifact recovery: 37 passed.

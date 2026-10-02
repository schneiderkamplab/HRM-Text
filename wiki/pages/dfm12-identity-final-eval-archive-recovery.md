---
type: Runbook
title: Identity Final EMA Evaluation Archive Recovery
description: CPU-only recovery of step 2897261 merge paths and serialized W&B publication.
tags: [dfm12, evaluation, wandb, recovery]
status: stable
last_updated: 2026-09-28
confidence: high
---
# Identity Final EMA Evaluation Archive Recovery

Plan: `logs/scheduler/dfm12_XL_identity_step2897261_ema_full_20260928`.
All 242 runnable GPU evaluation jobs completed. The 39 merge failures were
archive lookup failures: the cloning helper assigned per-job output directories
but retained merge metadata pointing at `results/`. No GPU reruns were needed.

`scripts/schedule_identity_final_ema_full.py` now assigns canonical writer paths
for future plans. `--repair-existing` uses `PlanLock`, preserves original
archives, backs up the plan and restores canonical aliases. Receipt:
`archive-repair.json` within the plan. No epoch-filter defect was found.

The initial four-slot CPU recovery completed all merges, but concurrent W&B
writers are not an acceptable final publication guarantee. Superseded recovery:
`--prepare-serial-replay --run-cpu-recovery` adds a dependency chain across all
39 merges with the average last, retaining original dependencies and GPU states.
It runs the existing scheduler with no GPU slots or persistent server pool.

Recursive pathlib globbing does not traverse EuroEval directory symlinks.
Recovery replaces only those aliases with real directories containing file
links; original archives remain untouched. Verified collectors find 195
standard, 129 DFM and 176 EuroEval numeric keys (including metadata axes).

Final publication uses one `scripts/backfill_external_eval_to_wandb.py` call
with all three corrected roots, `--log-averages --atomic-v3-averages`, without
`--averages-only`. Target is `DFM5/dfm12-xl-identity-da-en-1000`, epoch
`10.050795912217435`, step `2897261`. Verify remote numeric history keys,
checkpoint history values, summaries and explicit average metric definitions;
a successful local merge or summary alone is insufficient evidence.

Focused regression tests: `tests/test_identity_final_archive_recovery.py`.
Generation servers, training, and ports 8600-8607 are outside this recovery.

## Verified Completion

The serial replay finished with 286 done, four previously excluded jobs skipped,
and no failed or pending jobs. The consolidated backfill logged 531 numeric
keys in one remote history event at internal W&B step 2897332 (checkpoint
step remains 2897261). All 531 matched the local merged values in both that
history row and the summary; all have numeric history-key schemas.

Receipt: `remote-recovery-verification.json` in the plan directory, with
per-key expected values and remote schemas. Reproduce the read-only check with
the adjacent `verify_remote_recovery.py`. Publication log:
`consolidated-backfill.log`.

Headline averages: Danish 0.6970443904 (18 metrics), English 0.7552660749
(15), Math/Code 0.6245898879 (4). Suite averages: standard 0.8058711577
(8), DFM 0.6641610095 (31), EuroEval 0.6636146104 (18).
The requested fractional epoch is preserved (remote floating-point display
may show 10.050795912217437). Focused tests: 37 passed. OKF validation: clean.

See also the [operational recovery summary](dfm12-identity-full-eval-recovery.md).

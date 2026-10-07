---
type: Runbook
title: DFM14 XL Handoff at 3250K
description: Verified-transfer and exact-packing gate for one DFM14 epoch on the original XL run.
status: stable
confidence: high
last_updated: 2026-10-07
tags: [dfm14, training, xl, handoff]
---
# DFM14 XL Handoff at 3250K

## Policy

The owner authorized switching after step3250000. Current DFM13 training
through3250 remains unchanged. Continue the same XL optimizer/EMA and W&B run
`dfm8-xl-from-dfm6-dfm7-epoch5-clean-full`, projectDFM5.

- Exactly one DFM14 pass: sampled epoch0, resume metadata epoch1/row0.
- Base LR3e-4, `lr_auto=true`, no warmup, rewarm or decay; minimum ratio1.
- XL, GAS2, global batch262144; no optimizer-step advance at handoff.
- `data=dfm14`, target-only; pin `config/data/dfm14.yaml`.
- Output: `checkpoints/dfm14/XL-from-dfm13-step3250000`.
- Private resume sidecar; immutable tensor hardlinks preserve optimizer/EMA.

The explicit DFM14 config supersedes the initial DFM13-config/path override.
The incoming `dfm14/continue_training.py` is the other-machine XXL-wide
step870000/epoch2/GAS4 workflow; do not use its publication or scheduler-launch
path for this XL run.

## Readiness And Scheduling

Control root: `data/dfm14/xl-from-dfm13-step3250000`.
Transfer readiness: `data/sampled_dfm14/local-transfer-verified.json`, from
`ssh.cloud.sdu.dk:6768`, corrected remote
`/work/dfm/HRM-Text/data/dfm14/inheritance-reconciliation/sampled_dfm14/`.

Epoch0 contains135548772522 sampled tokens and406830651 rows; metadata's
total is a three-epoch average. Identity repeat0 follows the corrected-sample
authorization. Evidence covers transfer checksum, bounds and length checks,
not an independent full token-store hash.

The live readiness gate is installed on all eight old future training rows.
It preserves the3250 new-average dependency and all current training/eval rows.
Exact packing uses the production sampler:16384 tokens/rank/microbatch,
8 ranks, GAS2. `packing.json` records dropped sampler/accumulation tails.
No final optimizer boundary is guessed before this count completes.

The watcher clones the latest3250 coverage under PlanLock, including all32
new tasks (128 shards), the50-language average and existing averages, at every
future boundary including final. Obsolete unstarted rows become explicitly
superseded SKIPPED records; DONE history is retained. New terminal barriers
and teardowns are fresh and permit cleanup after eval failure. Following
training still requires successful preceding evaluations and averages.

Display eval epoch equals finalized3250 eval epoch plus DFM14 row fraction.
Training W&B metrics use `train/step` and a monotonic history offset; they do
not emit per-step `epoch`. Loader/checkpoint/local-diagnostic epoch1 is not a
fractional training-chart metric. No shared training logger was changed.

## Operation

CPU preparer137254 waits for transfer, then publishes `prepared.json`.
Handoff watcher147723 waits for that receipt, installs the exact schedule,
then publishes the isolated resume gate. Transfer131758 remains untouched.
Current identities/log paths are authoritative in `prepare-launch.json`
and `watch-launch.json`; do not launch duplicates.

```bash
# From the repository root, using /home/ucloud/miniforge3/envs/hrm/bin/python:
python -m scripts.prepare_dfm14_xl_handoff --watch
python -m scripts.schedule_dfm14_xl_handoff preview
python -m scripts.schedule_dfm14_xl_handoff arm
python -m scripts.schedule_dfm14_xl_handoff watch
```

The gate is already armed; these are recovery interfaces, not rerun commands.
No scheduler/server restart is performed by either watcher.

## Evidence

Receipts in the control root: `armed.json`, `gate-verified.json`,
`approved-pin-refresh.json`, `ready-gated-verified.json`, and plan backups.
The pin-refresh receipt binds the current approved registry hash to the parent
eval-extension installation; earlier stale pins are superseded. Source pins
are checked again before successor installation. Config/population ownership
remains with the parent.

Verification:44 focused handoff/eval tests passed, including Hydra settings,
full final-boundary coverage and failure-safe cleanup. Actual average commands
were captured without execution. [DFM14 plan](dfm14-plan.md);
[DFM13 handoff](dfm13-xl-3150k-handoff.md).

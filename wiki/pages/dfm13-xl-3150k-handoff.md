---
type: Plan
title: DFM13 XL Handoff at 3150K
description: Readiness-gated preparation for switching the original XL run from DFM12 to DFM13 after its 3150K evaluation.
status: stable
confidence: high
last_updated: 2026-10-05
tags: [dfm13, training, xl, handoff]
---
# DFM13 XL Handoff at 3150K

Following the [DFM12 progress assessment](dfm12-xl-epoch11-noidentity.md),
the owner requested preparation conditional on verification finishing.
This prepares the successor; it does not silently change the live campaign.

## Authorized Automatic Handoff (2026-10-05)

**Supersedes the preparation-only status below.** The user authorized the switch
after all3150K evaluations and averages. `scripts/schedule_dfm13_xl_handoff.py`
now owns the scheduler transition, without changing the running3150K segment or
the sample validator. Under `PlanLock`, it archived the original plan at
`data/dfm13/xl-from-dfm12-step3150000/plan-before-handoff.tsv` and retired2,660
unattempted post3150K DFM12 rows (four training segments and their evaluations).
All4,405 earlier/current rows, including the665-job3150K block, were retained.
`scheduler-armed.json` binds the backup and removed IDs.

The plan also has `dfm13-handoff-resume-ready`, a normal CPU `wait_checkpoint`
row depending on every non-skipped3150K job. It waits for the **real isolated
resume checkpoint**, not a fabricated completion marker. This keeps the existing
persistent scheduler alive if the sample arrives after3150K evaluations finish.
No second scheduler or GPU process is launched by the finalizer.

Detached CPU finalizer PID797327 runs:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m scripts.schedule_dfm13_xl_handoff watch
```

Log: `logs/dfm13-xl-handoff-scheduler.log`. The control directory above contains
`scheduler-launch.json`, `scheduler-progress.json`, and eventually
`scheduler-installed.json`; installation failures produce
`scheduler-failure.json`. The prior CPU finalizer796851 was stopped solely for
a small lock-dispatch correction; its launch receipt is preserved. The existing
packing watcher715684 and sampler791900 were not stopped or duplicated.

Once the existing watcher publishes `prepared.json`, the installer rechecks the
sample contract/current provenance and appends a clone of the **current expanded
3150K evaluation block**, including multilingual extensions, semantic averages,
judge settings and native no-Mistral-fix tokenizer configuration. It does not use
the historical290-job template. Every non-skipped preceding evaluation, merge,
report, teardown and average must succeed before the next training segment;
failed work blocks progression rather than being treated as successful.

The isolated resume uses unchanged hard-linked DCP payloads (weights, optimizer,
EMA) and atomically replaced private metadata. Source3150K remains untouched.
Global step stays3,150,000; trainer epoch1 selects dataset `epoch_0`, with exact
batch0 and row0, carry policy `none`. Arguments select `data=dfm13`, target-only,
one epoch, GAS2, BP8 with **BP warmup0**, FSDP fp32/bf16, original W&B run, base
LR3e-4 with `lr_auto`, no rewarm, and final50K cosine decay to1e-5. All eight GPUs
must satisfy the retained178000MiB headroom gate; no process is killed for space.

Evaluations occur at3200K,3250K,... and natural `epoch_1` end. The exact end step
comes only from the existing packing count. The final stop bound is end+1 so
natural exhaustion writes `epoch_1`. Each segment updates its evaluation display
epoch from **actual**3150K DFM12 row fraction plus actual DFM13 consumed-row
fraction, before dependent evaluations can start. No approximate step fraction
or assertion of a completed DFM12 epoch is used.

Validation:34 combined tests passed (14 upstream Torch deprecation warnings),
including the real expanded plan, Hydra composition, explicit stop bound,
the actual `resolve_resume_state` loader, cursor reset, source-metadata
preservation checks, readiness dependencies and display epoch mapping.
Tests: `tests/test_schedule_dfm13_xl_handoff.py`,
`tests/test_prepare_dfm13_xl_handoff.py`, `tests/test_schedule_dfm12_xl_epoch11.py`.
At handoff setup, DFM13 training has **not** started; sample scans and exact
packing are still prerequisites, not bypassed by this scheduler authorization.

## Verification and Sampling

On 2026-10-05 the active verifier was processing source 523 of 606,
Dutch baseline DaLA acceptability, followed by another 83 registry entries.
Approximately 24 GB of source JSONL remained at the initial handoff check.
This is not 83 missing downloads; these are pending verification entries.
Checksums, the Setur/fo-instruct repeat-10 successor, composition reconciliation,
sampling and full token/index scans remain necessary. The existing verifier,
composition watcher, reconciliation watcher, Faroese successor and sampler
were all running. They must not be restarted just to prepare this transition.

Verification should finish if no new failures arise, but completion before
3150K is not guaranteed. At step 3126085 and about 1.22 seconds/step, training
alone needs another 8.1 hours to reach 3150K, then its evaluation takes time.
Source JSONL throughput alone cannot predict checksum and sampling I/O tails.

The sequential verification snapshot above was superseded later on 2026-10-05
by the owner-authorized [32-worker restart](dfm13-parallel-verification.md).
The restarted registry includes Faroese directly and contains 607 entries;
135 need verification beyond the published predecessor. Consult the parallel
progress JSON rather than the old sequential source ordinal.

## CPU Preparation

`scripts/prepare_dfm13_xl_handoff.py --watch` waits for
`data/dfm13/sampling-20261005-v1/completion.json`. It checks complete vocabulary
and index scans, 4K metadata, current assembly/composition/reconciliation pins,
and inclusion of Setur/fo-instruct at repeat 10. Only then it calculates exact
packed optimizer steps using the training sampler: 8 ranks, 16384 tokens per
rank per microbatch, GAS2, drop-last semantics.

Outputs are under `data/dfm13/xl-from-dfm12-step3150000/`:

- `progress.json`: waiting, packing, or prepared status.
- `packing.json`: exact budget and sampled-input signatures.
- `prepared.json`: proposed start/end, evaluation boundaries and continuity policy.
- `failure.json`: fail-closed preparation error, if any.

This CPU watcher never launches training, touches W&B, modifies checkpoints,
or edits the active scheduler plan. Log: `logs/dfm13-xl-handoff-prepare.log`.

## Proposed Continuation

- Parent is the original XL `step_3150000`, not an identity-trained checkpoint.
- Reuse DFM5 run `dfm8-xl-from-dfm6-dfm7-epoch5-clean-full`.
- Preserve weights, optimizer and EMA; use XL/GAS2/GBS262144 as currently.
- One full DFM13 pass from its row zero; do not reuse the DFM12 batch/row cursor.
- Separate output: `checkpoints/dfm13/XL-from-dfm12-step3150000`.
- Proposed base LR 3e-4 with `lr_auto`; no automatic cooldown/rewarm at handoff.
  Proposed cosine cooldown over the last 50K DFM13 steps to 1e-5.
- Keep evaluations at clean 50K boundaries, starting 3200K, plus final endpoint.

Before activation, inspect the completed 3150K evaluation and averages, validate
isolated resume metadata with carry policy `none`, and install scheduler rows
under the plan lock. The original checkpoint must remain untouched. Fractional
evaluation epochs must continue from the actual consumed DFM12 fraction, not
claim the truncated DFM12 pass was a completed epoch. Internal loader epoch
mapping and display epoch mapping must be explicit and tested before launch.
Historical preparation-only state (superseded above): the active plan still
contained DFM12 continuations beyond3150K and no automatic handoff.

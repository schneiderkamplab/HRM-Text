---
type: Plan
title: DFM13 XL Handoff at 3150K
description: Readiness-gated preparation for switching the original XL run from DFM12 to DFM13 after its 3150K evaluation.
status: draft
confidence: medium
last_updated: 2026-10-05
tags: [dfm13, training, xl, handoff]
---
# DFM13 XL Handoff at 3150K

Following the [DFM12 progress assessment](dfm12-xl-epoch11-noidentity.md),
the owner requested preparation conditional on verification finishing.
This prepares the successor; it does not silently change the live campaign.

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
The current active plan still contains DFM12 continuations beyond 3150K; this
preparation is not yet an automatic scheduler handoff.

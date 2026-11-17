---
type: Runbook
title: Budget-bounded mixed recurrence
status: draft
confidence: high
last_updated: 2026-11-15
tags: [training, recurrence, backpropagation, qualification]
---
# Budget-bounded mixed recurrence

The default-off implementation samples positive H/L cycle counts per microbatch
for the stateless `hrm_nocarry_bp_warmup` baseline. This is separate from
[MixedLM attention](../current-state/2026-11-15-dfm11-mixedlm.md). No training
queue or current experiment has been changed.

## Semantics and interface

Set `arch.cycle_variants=full_budget`; `off` preserves fixed-depth training.
`arch.cycle_variant_seed=null` uses the run seed. Sampler version1 is recorded
as `arch.cycle_sampler_version` and in each checkpoint's `cycle_sampling`
metadata. The pool contains all positive `(H,L)` with `H*(L+1) <= bp_steps`.
BP16 has34 schemes; BP15 has30. The existing BP warmup controls the current
pool, and draws are uniform with replacement. A SHA-256-derived seed keyed by
sampler version, run seed, optimizer-step counter and one-based microbatch index
feeds a private Python RNG, so ranks and resumed steps draw the same schemes.

Forward overrides consume explicit `H_cycles` and `L_cycles` arguments. All
calls in each selected scheme are differentiable; the effective forward BP is
its actual call count. Stored nominal H/L counts still define evaluation and
HF export. Override pairs cannot be used with inference caches. Causal,
PrefixLM and MixedLM attention are supported; other architectures are rejected
at configuration validation. There is no runtime memory-driven budget fallback.

LR-auto uses the supervised-token-weighted **mean** of actual H and L backward
calls across the accumulation group, using the same globally averaged token
counts and weights as the training loss. It does not divide by summed counts
or apply a second GAS factor. Explicit module LR overrides take precedence.
A diagnostic shadow pass reproduces the draws without replacing the real
optimizer's effective LR counts. Logged `train/cycles/*` metrics include call
means, cycle means, budget and per-scheme counts for the reported step.

## Prewarm and continuation

With compilation enabled, `cycle_variants_prewarm=true` pre-warms every distinct
scheme in the maximum pool on the retained first real accumulation group. It
runs forward/backward only, restores RNG, buffers and pre-existing gradients,
and consumes no extra loader rows or optimizer steps. Per-rank reports are
written to `cycle_prewarm.rank*.json` in the checkpoint directory. They record
wall time, graph counts, compiler-cache limit and memory. Different future
packing shapes may still compile additional graphs.

The compiler cache is increased for the pool and representative batches unless
`TORCH_DYNAMO_CACHE_SIZE` is explicit; an explicit insufficient limit is rejected
instead of silently overriding it. `cycle_variants_prewarm=false` is available
for diagnostic use; the full memory qualifier forces pre-warm on.

Resume checks mode, sampler version, seed, BP range/warmup schedule and GAS
against checkpoint metadata. Legacy checkpoints with the feature disabled
remain compatible. An intentional change requires
`cycle_variants_allow_resume_change=true`, prints the old/new contract, and
records `cycle_sampling_continuation` in subsequent checkpoints. It does not
bypass the existing data, optimizer or carry checks.

## Memory qualification command

Use the HRM environment and a **resolved** training configuration:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python scripts/qualify_cycle_variants.py \
  --config logs/training/B_dfm11_prefixlm_lrauto_bpwarmup_20261111/resolved-config.yaml \
  --output logs/diagnostics/cycle-variants-full-NEW \
  --gpus 0,1,2,3,4,5,6,7
```

Default mode performs a dry run. Add `--execute` only with dedicated idle GPUs.
It refuses occupied GPUs (exit75), does not signal their jobs, and does not
reserve GPUs from the eval scheduler. If another workload appears during the
qualification, only the qualifier is stopped. Use a new output directory for
each invocation; receipts are not overwritten.

BP16 is tested first in fresh torchrun processes with the supplied architecture,
optimizer/EMA, FSDP, precision, activation checkpointing and token capacity.
The worker uses an actual sampled batch plus full-token-capacity long-sequence
and dense64-token layouts. It pre-warms all schemes, performs an optimizer step
for every scheme/layout, then100 mixed optimizer steps. It records allocated,
reserved and sampled device-wide memory on all ranks, compilation overhead,
throughput, the resolved recipe and software/data-metadata hashes. The small
synthetic layouts test memory, not language quality.

A pass requires at least2GiB physical GPU headroom on **every** GPU, no OOM,
complete rank reports and no monitoring errors. If BP16 fails for memory, BP15
is tested in fresh processes. Compiler/runtime errors or missing evidence stop
qualification; they do not justify a lower-budget fallback. If both budgets
fail, the report says unqualified. Batch size, context, precision and activation
checkpointing are never silently reduced. A selected budget applies only to the
measured recipe, not automatically to another objective, context or architecture.

## Verification and current limitation

Evidence directory: `logs/diagnostics/cycle-variants-20261115/`.

- CPU tests cover actual fixed-depth versus sampled gradients for all three
  attention modes, weighted accumulation, compiled steps, warmup, nominal export,
  checkpoint guard/override behavior, old-checkpoint compatibility and replay.
- Two-rank CPU/Gloo training checks rank-aligned draws and unequal per-rank
  supervised-token populations against a manually reduced gradient oracle.
- `cuda-suspend/result.json`: compiled single-GPU FSDP, all34 schemes pre-warmed,
  two real CUDA offload/restore cycles, exact model, optimizer/EMA and metrics.
- `cuda-suspend-two/result.json`: same parity on two GPUs, using **test-only
  legacy NCCL settings**. This does not replace the production NCCL-shim
  qualification documented in the [suspension runbook](../cooperative-cuda-suspension.md).
- `qualification-worker-small/rank0.json`: actual GPU worker exercised all34
  schemes over3 layouts plus100 mixed optimizer steps (202 updates total),
  passing on the small model. This is a worker smoke, **not full-size B memory
  qualification**.
- `full-recipe-admission/report.json`: the full B PrefixLM/target-only recipe
  passed configuration preflight, but all eight GPUs were occupied. No full-size
  workers launched and no budget was selected. **BP16 versus BP15 remains
  unqualified until the full-size experiment can run on idle GPUs.**

The historical plan was recovered from OpenCode session
`ses_e5b0ebcfbffenu0ot2vkh0mhj1` (November4). Its BP15-only choice and summed-GAS
LR divisors are superseded by the November15 user-approved BP16-first policy and
weighted-mean implementation. Historical memory estimates are not fit evidence.

## Dedicated validation pause authorized (2026-11-16)

The user requested the active Transformer PrefixLM trainer suspend at232000,
validate sampled recurrence and the prepared architectures, then resume the same
trainer from memory. The232000 request was accepted into the live control queue;
an explicit hold prevents the scheduler from restoring it during validation.
Only PrefixLM/target-only sampled recurrence is requested. Select BP16 first,
fallback to BP15 only on measured memory failure, and insert that experiment
after all three Embla runs and before the remaining ablations. Preserve the
existing trainer processes and release the hold after validation resources drain.
This is an authorized temporary validation pause, not cancellation of training.

The232000 pause completed: generation3, original trainer PIDs1273677–1273684,
regular `checkpoint_state_step_232000.json`, and verified CUDA offload to4MiB
per GPU. The first BP16 admission deferred because one regression test used
CUDA; no workers launched. The42-test architecture/recurrence suite then passed.
Dedicated full-size qualification was launched in
`logs/diagnostics/cycle-variants-232k-full-v2-20261116`; its result remains pending.
The existing managed supervisor owns restoration; no second recovery watcher
was started. The active control hold remains until qualification jobs drain.

BP16 full-size prewarm completed on all ranks:34 schemes,3 representative layouts,
85.47s on rank0,32 compiled graphs, peak allocated166719262208 bytes and peak
reserved178738167808 bytes. Optimizer/mixed-step qualification is still running;
these prewarm numbers alone do not select a budget. The post-Embla insertion
script is prepared at `scripts/schedule_dfm11_cycles.py`; it requires a qualified
report, unchanged source/software hashes and complete eight-rank results.

### BP16 selected by full-size validation (2026-11-16)

The pending budget decision above is now superseded: BP16 qualified at
`logs/diagnostics/cycle-variants-232k-full-v2-20261116/report.json`.
All8 ranks completed34 schemes across3 layouts and100 mixed optimizer steps.
Minimum sampled device headroom was10832MiB on every GPU, with no monitor errors.
Peak allocated was155.27GiB; sampled-update throughput was about2.43 steps/s
(0.412s/step). These measurements are qualification-layout throughput, not a
prediction for the full epoch. BP15 was not tried because BP16 passed.

The selected experiment remains B PrefixLM/target-only, full-budget sampling,
LR-auto with supervised-token-weighted call counts and the existing BP warmup.
Place it after the three Embla epochs and before remaining ablations. Queue
insertion is pending Embla's full-size validation and insertion.

## Queue and restoration verified

The BP16 PrefixLM/target-only experiment is now queued after looped Embla and
before remaining ablations, with17632 rows,50K/final eval blocks and committed
readback. Its launch uses dedicated GPUs, not the historical B template's
co-tenancy setting. The original Transformer resumed from memory at232000 and
was observed beyond233K. See [final232K validation](validation-232k-20261116.md).
This supersedes earlier statements that no queue changes or budget selection
had occurred. Full-size validation is a capacity/correctness result, not evidence
of training quality or convergence.

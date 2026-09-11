---
type: Experiment
title: XL BP-Depth Memory Benchmark
description: Matched BP 6, 7, and 8 memory and throughput measurements for the DFM10 XL training geometry.
tags: [training, hrm, recurrence, memory, b200]
status: stable
last_updated: 2026-09-03
confidence: high
---
# XL BP-Depth Memory Benchmark

On 2026-09-02, the active DFM10 XL production run was paused after the complete
`ephemeral_step_2321000` checkpoint. Three W&B-disabled smokes resumed from
that same checkpoint and used the production geometry: eight B200 GPUs, 4K
context, global batch 262144, GAS 2, full-world FSDP2, FP32 persistent
parameters, BF16 forward/backward, `reshard_after_forward=false`, `no_sync`
accumulation, compilation enabled, and no activation checkpointing.

| BP steps | Differentiated recurrence | Peak allocated/GPU | Peak reserved/GPU | Steady step median |
|---:|---|---:|---:|---:|
| 6 | 2 H + 4 L | 125258 MiB | 128186 MiB | 1.008 s |
| 7 | 2 H + 5 L | 142357 MiB | 149632 MiB | 1.113 s |
| 8 | 2 H + 6 L | 159456 MiB | 166098 MiB | 1.211 s |

Each result is based on 11 measured optimizer-step intervals with the first two
dropped for the reported steady timing. BP 8 completed without OOM and left
about 16 GiB of physical device margin after allocator reservation and CUDA
overhead. It fits this exact XL/GAS-2/4K geometry, but the margin is not enough
to assume that a larger microbatch or context also fits.

The conditional BP-8 selective-checkpointing arm was not run because
uncheckpointed BP 8 succeeded. If checkpointing is needed for deeper
recurrence, `l_only` is the relevant first policy: H is already fully
differentiated by BP 3 because `H_cycles=2`; increasing BP from 5 through 8
adds only differentiated L applications. Checkpointing L therefore targets the
activations whose count grows, whereas checkpointing H adds recomputation for a
fixed two applications and does not address the marginal BP-depth cost.

Operational notes:

- `arch.bp_warmup_ratio=0` currently divides by zero in the two-level HRM
  implementation. Leave the normal ratio at `0.2` for late-checkpoint smokes;
  the schedule is already saturated and therefore selects `bp_max_steps`.
- Smoke artifacts are under
  `logs/benchmarks/dfm10_xl_bp_depth_20260902/{bp6,bp7,bp8}`.
- Production temporarily resumed from the untouched
  `ephemeral_step_2321000` checkpoint with its original BP-5 configuration and
  W&B run.

## Production Schedule Update

The temporary BP-5 resume above was superseded on 2026-09-02 after the run
wrote and verified `ephemeral_step_2325000`. The remaining DFM10 epoch uses a
staged recurrence-depth schedule in the existing evaluation-scheduler plan:

| Step interval | `arch.bp_max_steps` |
|---|---:|
| 2,325,000 to 2,350,000 | 6 |
| 2,350,000 to 2,375,000 | 7 |
| 2,375,000 to 2,482,084 | 8 |

Each transition occurs at an existing regular 50K checkpoint boundary. The
first segment resumes from `ephemeral_step_2325000`. The BP-7 process uses a
guarded handoff at the fully written `ephemeral_step_2375000`, after which the
existing 2,400,000 training row resumes at BP 8. Later segments resume from
`step_2400000` and `step_2450000`. Evaluations, checkpoint cadence, optimizer
and EMA state, data cursor, and the existing W&B run remain unchanged.
Activation checkpointing stays disabled because uncheckpointed BP 8 passed
the matched memory test.

The resumed W&B run already contained history through step 2,325,021, while
the durable checkpoint was at step 2,325,000. W&B therefore rejected the four
overlapping log points at steps 2,325,005 through 2,325,020 and accepted new
history from step 2,325,025 onward. This affects only those overlapping log
points, not optimizer, EMA, checkpoint, or data-cursor state.

## L-cycle depth branch at 2.4M

The September 2026 L-cycle probe branches from the canonical DFM10 XL
`step_2400000` checkpoint. It preserves the canonical weights and optimizer
state, changes only `arch.L_cycles=4`, and keeps `arch.bp_max_steps=8`.

- Backfill run: `peter-sk-sdu/DFM5/dfm10-xl-lcycles4-from-step2400000`.
- L4 checkpoint root: `checkpoints/dfm10/XL-lcycles4-from-step2400000`.
- L4 exports: `exports/dfm10_XL_step{2400000|2450000}_lcycles4_ema_hf`.
- The canonical 2400K evaluation runs first. The same full evaluation then
  runs on a config-only L4 copy of that export, followed by 50K L4 training
  and the L4 2450K evaluation.
- Canonical L3 training from 2400K to 2450K resumes only after the L4 2450K
  evaluation teardown completes. Its command explicitly pins
  `arch.L_cycles=3`.

This ordering separates the immediate inference-time effect of one extra L
cycle at 2400K from the effect of training that architecture for 50K steps.
The L4 branch reads its resume checkpoint from the canonical root but writes
all new checkpoints and `all_config.yaml` to the dedicated L4 root.
Its training history is copied from the canonical run through step 2,400,000;
the L4-specific metric history starts at the branch point.

When cloning an evaluation graph, preserve each job's `name` exactly: the
runtime passes it to EuroEval and DFM Eval as the benchmark identifier. Branch
identity belongs in `job_id`, model metadata, log roots, and W&B identity. An
initial attempt that suffixed task names with `-lcycles4` failed before
evaluation; those attempts were reset after correcting the plan.

### Completed 2400K/2450K comparison

The full L4 2450K evaluation completed on 2026-09-04. The principal aggregate
comparison is:

| Aggregate | L3 2400K | L4 2400K | L4 2450K |
|---|---:|---:|---:|
| Headline Danish | 0.64537 | 0.62075 | 0.63592 |
| Headline English | 0.71751 | 0.69423 | 0.71192 |
| Headline math/code | 0.51787 | 0.53728 | 0.63942 |
| Headline overall | 0.59284 | 0.58450 | 0.60365 |
| Standard suite | 0.72982 | 0.71795 | 0.73253 |
| DFM suite | 0.63212 | 0.62279 | 0.62376 |
| EuroEval suite | 0.62562 | 0.59908 | 0.63519 |

The 50K L4 training segment recovered most of the immediate config-only L4
regression and surpassed L3 2400K on the overall, standard, EuroEval, math,
and math/code aggregates. The math/code gain is dominated by BFCL-v2, which
rose from 0.2764 (L3 2400K) and 0.3736 (L4 2400K) to 0.7472 (L4 2450K).
GSM8K and MATH reached 0.85519 and 0.42480 respectively, modestly above the
L3 baseline. The four-code-task average instead fell from 0.53408 to 0.51844.

Treat the L4 2450K DFM-suite and MC9 aggregates as provisionally invalid:
`dfm_eval/winogrande/choice/accuracy` is 0.27348 despite the independent
standard Winogrande result being 0.7459. The earlier L3 and config-only L4 DFM
Winogrande results were 0.72968 and 0.73007. This isolated discrepancy should
be investigated or rerun before using either affected aggregate.

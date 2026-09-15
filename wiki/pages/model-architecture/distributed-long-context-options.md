---
type: Design Document
title: Distributed Long-Context Implementation Options
description: Main-branch implementation difficulty and risk for activation, tensor, context, and HRM-specific pipeline parallelism.
tags: [training, distributed, long-context, fsdp, hrm]
status: draft
last_updated: 2026-09-15
confidence: medium
---
# Distributed Long-Context Implementation Options

## Adaptive 619K Checkpointing Probe (2026-09-15)

### Matched-data validation and production resume

The matched-data probe uses the GAS8 loader in both arms and combines four
microbatches per call for effective GAS2, preserving valid tokens, labels,
positions, and sequence boundaries (per-rank SHA256 checks). GAS8 outer
compilation/no checkpointing completed 50 updates at median 4.988 s;
last-25 median was 4.967 s. Full checkpointing/block compilation gave a
first-update gradient relative L2 difference of 10.938%, cosine 0.994064,
despite identical input data. This does not establish mathematical error,
but fails the conservative parity gate. Its 50-update run was interrupted
at the user's request to resume production; do not claim completed parity.
Artifacts: `logs/experiments/checkpoint_compile_xxl_619000/` under
`scope_production_{reference,block}_full_50_matched_limit180`.

Production resume retains GAS8, BP8, outer compilation, no activation
checkpointing, reshard-after-forward false, and the existing LR cooldown.
The existing scheduler's `campaign-dfm10-finish-epoch2` row now resumes the
validated preserved `ephemeral_step_619000` in
`checkpoints/experiments/checkpoint_compile_xxl_619000/source`.
Output remains `checkpoints/dfm10/XXL-from-520000-half-lr`; W&B remains
`DFM5/xxl-restart520k-20260910`. Training log:
`logs/training/dfm10_XXL_restart520k_half_lr/from_619000_gas8_restored/train_until_step_630000.log`.

### Gradient discrepancy investigation

Consolidated report: `docs/checkpoint-compile-numerics.md`. Follow-up trained
XXL block probes (first three H/L blocks, synthetic inputs, eight repeated
applications) also favor compiled BF16 over eager against FP32 math-attention
references: H gradient error 5.49-5.52% compiled versus 7.28% eager; L
3.11-3.16% versus 3.41%. FP64 versions exceeded the isolated 6 GiB cap;
FP32 succeeded without increasing it. Repeat-baseline actual Adam update
variation is 0.400%, versus 4.507% for changing the production path. This is
numerically meaningful but does not establish a quality regression. All
side probes completed/exited; production remained GAS8. Before switching,
use matched-data sustained training and held-out loss, not just eager-gradient
tolerance or aggregate cosine. The full-size 10.94% discrepancy has not been
attributed exhaustively operator by operator; recurrence sensitivity is a
supported explanation, not proof that every contribution is understood.

Further isolation (2026-09-15): FP64 operator references across two seeds
show compiled BF16 gradients closer to the mathematical reference for
SwiGLU (0.166-0.168% error versus eager 0.233-0.243%), sigmoid gating
(0.163-0.165% versus 0.249%), and the complete small MLP (0.340-0.352%
versus 0.376-0.390%). FP32 errors are approximately 1e-7 relative.
Generated Triton confirms fused sigmoid/multiply loads BF16 into FP32,
computes both operations without an intermediate BF16 store, then writes
BF16. This differs from eager intermediate rounding; eager is not a gold
standard for derivative accuracy.

Actual six-layer XXS H/L recurrence, BP8, versus a FP64 math-attention
reference: eager BF16 gradient error 1.636%, outer Inductor 1.537%, block
Inductor/full checkpointing 1.529%. FP32 versions were about 0.000085%.
Outer versus checkpointed block compilation directly differed by 0.320%
at identical outputs. With eight independent short sequences, changing
GAS8 to GAS2 caused 0.163% gradient difference in compiled single-GPU
controls. Two-rank FSDP2 controls gave 0.394% for the full GAS8 outer versus
GAS2 block-checkpointed comparison; GAS alone gave 0.379%, checkpoint/compile
boundary alone 0.141%. These are small-model results, not XXL parity.

Read-only CPU replay with the actual 619K XXL moments and the matched
first gradients found 4.507% relative L2 difference in the next adaptive
AdamATan2 update (cosine 0.998984), versus 10.938% in gradients. Common
weight decay was omitted since it cancels from the difference. All 290
parameter names were checked against model order; all eight saved shards
were compared. H update difference: 4.556%; L: 16.058%; embeddings: 7.926%;
head: 0.597%. Thus the difference is not negligible for individual modules,
despite close global directions. No checkpoint/model/optimizer state was
modified. See `scripts/probe_saved_update_difference.py` and
`logs/experiments/checkpoint_compile_xxl_619000/matched_adam_update_difference.json`.
Numerical differences are established; long-run validation quality has
not been tested, so these probes do not authorize a production switch.

Small single-GPU FA4 controls (2026-09-15) now reproduce differences without
FSDP, optimizer updates, or accumulation. Script:
`scripts/probe_small_compile_matrix.py`; artifacts:
`logs/experiments/small_compile_matrix_619k`. Uses width 256, three actual
Transformer blocks, two packed 64-token sequences, FP32 weights/BF16
autocast, fixed upstream gradients. Repeated application is a simplified
amplification test, not the full HRM H/L BP schedule.
Eager repeats, eager checkpointing, and AOT-eager block checkpointing were
bit-identical in the depth-one test. Outer Inductor, block Inductor, and
checkpointed block Inductor had identical summary discrepancies:
1.1606% gradient relative L2 versus eager. Repeating the Transformer five
and eight times raised this to 4.2977% and 9.6672%. Outer compilation with
checkpointing failed saved/recomputed tensor metadata checks, separately
from the successful block-compiled numerical comparison.
Peak PyTorch allocation was below 0.23 GiB; CUDA overhead is additional.
Production advanced through 619105 at approximately 5.4 s/update during
these parallel probes. These tests implicate compiler numerics plus
amplification, not checkpointing alone; they do not identify a unique
operator yet or prove that eager is the mathematically superior path.

Second parallel wave: compiling attention only produced gradient relative
L2 1.005% at depth one and 9.021% at depth eight; MLP only gave 0.950%
and 8.799%; norm only gave 0% and 0.628%. Explicit Inductor precision-cast
emulation reduced block-compilation differences to 0.327% and 3.958%
respectively, but did not eliminate them. At depth one its outputs matched
exactly while gradients still differed. This supports forward rounding and
backward lowering/accumulation as contributors, without isolating a single
faulty kernel. Earlier full-XXL cast-emulation results did not improve parity;
do not extrapolate this small-case improvement into a production fix.
Both waves finished; the outer-checkpoint metadata failure was isolated to
its probe process. No production configuration was changed.

Isolation ladder (2026-09-15; initial local controls above completed): first verify the
resumed GAS8 production stream is advancing. Run sequential, single-GPU,
no-W&B probes with a small allocator budget (initially 6 GiB, total-device
headroom guard), isolated compiler caches, one compiler/CPU thread, and
short bursts. GPU memory headroom is not spare compute: shared-GPU work
can delay every rank of production. Pause probes if production slows.

1. XXS width 256, six layers, short packed sequences: repeat each path to
   establish its noise floor. Fixed weights, inputs, masks, upstream gradients,
   and seeds; no optimizer updates initially.
2. Same microbatch: eager/AOT-eager/outer-Inductor/block-Inductor crossed
   with checkpointing on/off. This separates compilation boundaries from
   recomputation effects without changing GAS.
3. Hold compiler/checkpoint mode fixed; compare GAS8 with four-to-one
   merged batches (effective GAS2). Compare accumulated gradients before
   clipping and before Adam or EMA. Preserve objective normalization.
4. Localize the first activation/gradient discrepancy using separate
   attention, MLP, norm, and residual-add probes with identical upstream
   gradients. Compare against FP32 math attention with TF32 disabled;
   use this only as a numerical reference, not a production speed proposal.
5. Sweep differentiable BP depth 1/2/5/8 at fixed H/L cycles to distinguish
   a local discrepancy from recurrent amplification. If XXS does not
   reproduce it, test isolated trained XXL blocks/activation slices before
   assuming the full model is unaffected.
6. Only after local isolation, use two small FSDP ranks to test
   synchronization and accumulated-gradient scaling. Do not launch an
   eight-rank side campaign alongside production.

Use both relative L2 and cosine, absolute error, loss difference, and the
repeat noise floor. Fingerprints alone are not a parameter-parity test.
No production monkeypatches or shared optimizer/model state.

Production-aligned control completed: at matched GAS8 and the same 619K
checkpoint, eager/no-checkpoint gradients differ from production's outer
Inductor path by 12.692% (cosine 0.992005), and block-Inductor/full-checkpoint
gradients differ by 10.986% (cosine 0.994012). Thus the earlier eager-only
gate was insufficient to judge preservation of production behavior, but the
new matched-GAS check also fails the conservative 1% criterion. These are
numerical-path differences, not proof that either derivative is mathematically
incorrect. The fastest measured path remains GAS2 full checkpointing plus
block compilation at 4.565 s; it is not a validated drop-in replacement.
The existing GAS8 production path remains the recommended validated setup.

Measured conservative alternatives: optimizer-only compilation plus full
eager checkpointing completed 50 updates at median 5.626 s; maximum loss
difference versus eager was 0.000139. With all L and half H checkpointed,
50 updates gave 5.483 s median, gradient relative L2 0.645%, maximum loss
difference 0.000187 and 141.04 GiB peak allocated. One-third H with expandable
segments completed 20 updates but slowed to 11.152 s median. Quarter H
failed native allocation under the former 170 GiB policy, and its expandable
retry exceeded that policy (171.07 GiB observed). Under the expanded limit,
quarter H with expandable segments ran but was stopped early because steady
intervals were approximately 10-11 s. Quarter H with native
`max_split_size_mb:256` completed 10 updates at median 6.536 s, with 0.604%
gradient relative L2. Thus none of these alternatives beats the original
production median. No production training parameters have been changed.

Important unresolved comparator issue: production itself uses Inductor.
The eager-reference gradient gate alone cannot determine whether block
compilation preserves production numerics. Matched-GAS8 production/eager/
checkpointed-block controls are required; do not compare GAS2 gradients to
GAS8 gradients as if batch packing were identical.

Second memory update (2026-09-15): user authorized 180 GiB, superseding the
170 GiB policy below. Actual NVML capacity is 183359 MiB (179.06 GiB).
The isolation runner therefore caps observed total usage at the lesser of
the request and physical capacity minus 1 GiB (~178.06 GiB). It budgets
7 GiB for non-allocator usage, based on observed rank-zero overhead with
expandable segments, leaving ~171.06 GiB for PyTorch. Runs encode the limit
in their output directory names and record requested/effective limits.

Memory policy update (2026-09-15, user request): supersedes the initial
150 GiB allocated / 160 GiB reserved gates below. Use 170 GiB total device
usage, allowing 167 GiB for the PyTorch allocator and approximately 3 GiB
for CUDA overhead. The isolation runner polls total device usage once per
second and terminates its own test process group if that ceiling is exceeded.
This polling can miss sub-second spikes, so retain the allocator cap too.
An additional intermediate policy checkpoints all L and one quarter of H
before attempting L-only.

Follow-up full-size one-update isolation (same saved-gradient comparison):
keeping norms eager gave 12.99% relative L2, attention-only compilation
13.48%, MLP-only 12.76%, both components 13.02%, L-block-only 10.71%,
H-block-only 11.71%, and disabling scheduler fusion/prologue/epilogue fusion
6.82%. None meets the original 1% gradient gate. These tests do not prove
an incorrect derivative; they show that these compilation boundaries do not
preserve the eager BF16 trajectory closely enough for the proposed rollout.
The original blanket block compiler should remain experimental.

Optimizer-only compilation leaves first-step gradients near the repeated-run
noise floor (0.627%). Its independent CPU FP32 test compares parameters,
moments, step and EMA over five changing-LR updates, passing 1e-6 tolerances.
Full-size timing and lighter eager-checkpoint variants are evaluated separately;
correctness alone does not establish that optimizer compilation is useful.

Full-XXL, eight-GPU one-update controls from preserved 619K isolated the
excess discrepancy to the Inductor path, rather than AOTAutograd alone:

| Comparison against eager full-checkpoint GAS2 | Gradient relative L2 | Cosine |
| --- | ---: | ---: |
| Eager repeat | 0.6085% | 0.99998151 |
| Block compile, backend aot_eager | 0.6087% | 0.99998149 |
| Block compile, default Inductor | 6.0576% | 0.99816548 |
| Inductor with emulate_precision_casts | 12.6442% | 0.99197698 |

The GAS8 baseline repeat separately varied by 0.5876%. First-step clipping
coefficients in the original comparisons were one, excluding clipping as
the explanation. H contributes 84.0% of squared difference energy,
embeddings 14.0%, L 1.4%, and the head 0.6%; differences are distributed
across attention and MLP parameters. Parameter identities were mapped using
the same model construction on the meta device (290 parameters).

Inference: Inductor lowering/fusion numerics amplified through the recurrent
network are implicated; the specific operator is not yet isolated. The
installed Inductor config documents removal of BF16 intermediate rounding,
but its eager-rounding compatibility switch worsens this case, so do not
enable it as a fix. This does not establish which numerical path is closer
to an FP32 reference, or prove a checkpoint correctness bug. Next isolation
should compare individual blocks/attention/MLP/norm against an FP32 reference
and selectively retain sensitive operations in eager mode.

Tools: `scripts/analyze_checkpoint_probe_gradients.py` (CPU-only saved-shard
analysis) and `scripts/run_checkpoint_rounding_probe.py` (one-update controls,
option `--backend aot_eager`). No W&B or checkpoint writes; production stays
paused. One-update controls do not produce timing summaries because no
inter-update interval exists; their saved gradients are the intended output.

Completed replay results: GAS8 production baselines had median 5.219/5.064
s per update, peak allocated 120.75 GiB and reserved 131.03 GiB. GAS2 full
checkpointing eager had median 5.936 s, allocated 90.70 GiB, reserved 108.84
GiB. GAS2 full with block compilation had median 4.565 s, allocated 90.70
GiB, reserved 105.18 GiB. All four arms completed 50 updates without OOM.
However, compiled versus eager first-step post-clip gradient relative L2
error was 6.06%, cosine 0.998165, exceeding the predeclared numerical gates
despite maximum replay loss difference only 0.000191. Adaptive lighter
checkpointing arms were therefore skipped. Do not promote the compiled path
until this discrepancy is investigated. Production remains paused at619K
(tag `ephemeral_step_619000`); results live under
`logs/experiments/checkpoint_compile_xxl_619000`.

The first launch preserved 619K and stopped production correctly, but all
arms failed during Hydra argument parsing. Put `--config-path` before all
positional overrides, immediately after the probe script. The corrected
command passed a `--cfg job` preflight before the campaign was restarted.

The isolated 619K campaign now progressively reduces checkpointing after a
passing GAS2 full-checkpoint/block-compiled comparison: all L plus half H,
then L only, then three quarters of L. At BP8, H executes twice and L six
times; removing H checkpoints first is the conservative memory progression.
Each arm replays 50 updates from the same preserved checkpoint without W&B
or checkpoint writes. Production stays paused for review.

The next lighter arm requires first-step gradient relative L2 error <=1%,
cosine >=0.9999, and maximum replay loss difference <=0.01 against eager
full checkpointing. These are experimental BF16 agreement gates, not proof
of long-term training parity. Memory must remain <=150 GiB allocated and
<=160 GiB reserved per GPU; adaptive arms additionally cap the PyTorch
allocator at 90% of device memory. Non-PyTorch allocations are not included
in this cap. An OOM, failed comparison, or exceeded margin stops further
loosening. A repeated production baseline brackets the timing campaign.

Implementation: `scripts/watch_checkpoint_compile_xxl_619000.py` and the
isolated `scripts/probe_checkpoint_compile_xxs.py` entry point. Selective
policies affect only probe processes, not production model code.

## BP8/GAS4 Replay from 603500 (2026-09-14)

Production was stopped after complete `ephemeral_step_603500` and a hard-linked
immutable copy was preserved at `checkpoints/experiments/gas4_603500/source`.
The replay entry point is `scripts/smoke_gas4_603500.py`; logs are under
`logs/experiments/gas4_603500`. All arms disable W&B and checkpoint writes,
keep BP8/global batch 262144/the current LR cooldown, and resume by row cursor.

- GAS4, no activation checkpointing, compiled: OOM on the first update;
  PyTorch allocated 175.63 GiB, with only about 16 MiB device memory free.
- Added opt-in `activation_checkpointing=h_only`, preserving the default
  `none` and state-dict names. CPU BP8 output/input/parameter-gradient parity
  passed; H recomputes twice and L does not recompute.
- H-only, compiled: checkpoint recomputation metadata mismatch. Examples:
  saved `[7168,1792]` versus recomputed `[1792,7168]`, followed by shifted
  tensor positions. The exact compilation boundary responsible is not yet
  isolated; do not bypass the determinism checks.
- H-only, eager, automatic resharding only for checkpointed blocks: OOM at
  the FP32-logit conversion for cross-entropy (8 GiB allocation, only about
  770 MiB free). This is a separate failure from compilation.

Both selective and full checkpointing smoke arms use
`fsdp_reshard_after_forward=null` to preserve the established composable
checkpoint integration: reshard selected blocks, retain uncheckpointed ones.
No failed arm was promoted to production. Full H+L/GAS4 eager timing is the
next requested comparison; production is intentionally paused for the decision.

Full H+L/GAS4 eager smoke completed all 12 updates (603501--603512) with
finite loss and gradients. `full_eager/summary.json` records median 6.7400 s,
mean 6.7722 s after the benchmark's two discarded timing intervals. The first
update took approximately 28.18 s including startup; the 11 subsequent
intervals were 13.8883, 6.5326, 7.2214, 6.3293, 6.7701, 6.7400, 6.3837,
7.2477, 6.5457, 6.9726, 6.7395 seconds. This is slower than the observed
compiled BP8/GAS8 production range 5.2--5.3 s, not a throughput win. No
experiment checkpoint or W&B history was written; production remains paused.

The follow-up `--gas 2 --checkpointing full --no-compile` also completed
12 updates without OOM. Peak allocated/reserved across the logged ranks was
90.698/108.838 GiB. Post-warmup median/mean was 5.9522/5.8786 s per update,
versus GAS4 full-checkpointing 6.7400/6.7722 s. This is an 11.7% median-time
reduction but remains about 12--14% slower than the observed compiled GAS8
production range. Results: `logs/experiments/gas2_603500/full_eager/summary.json`
and `train.log`. Loss/gradients were finite; this is a fit/timing smoke, not
a proof of trajectory parity because microbatch packing changes. Production
and the scheduler remain paused pending the user's choice.

### GAS8 Restored and Compile Boundary Isolation

Later on 2026-09-14, the user chose to restore production GAS8 and investigate
compilation without interrupting it. The current training row resumes from
the preserved 603500 snapshot, with compilation on, activation checkpointing
off, original output directory, LR cooldown, and W&B run
`DFM5/xxl-restart520k-20260910`. The existing coordinator/worker were restarted;
DFM11 future rows retain the same production performance settings. The few
replayed steps below W&B's 603526 watermark are correctly ignored, not
overwritten. The current epoch still finishes before the next 650K boundary;
its epoch-end evaluation and the DFM11 continuation remain scheduled.

CPU-only `scripts/probe_checkpoint_compile_cpu.py` reproduces the error on a
small repeated H/L-style MLP with the installed hrm PyTorch, without FSDP,
FA4, CUDA, or mixed precision. It uses one CPU/compile thread and disabled
CUDA visibility. Results: `logs/experiments/checkpoint_compile_cpu/results.json`.

| Boundary/backend | Result |
|---|---|
| Composable checkpoint, eager | Output/gradient reference check passes |
| Outer compile, backend eager (Dynamo only) | Passes |
| Outer compile, aot_eager | Saved/recomputed metadata mismatch |
| Outer compile, inductor | Saved/recomputed metadata mismatch |
| Compile each block forward with Inductor; checkpoint hooks outside | Passes |

This isolates an AOT/checkpoint-hook boundary failure independently of FSDP
and rules out FA4 or BF16 as necessary causes of this reproduced failure.
The composable implementation establishes saved-tensor hooks in its pre/post
forward hooks; the failing AOT path produces a different saved-tensor layout
from recomputation. Do not disable determinism checks. Compiling the block
body rather than the entire forward/backward wrapper is a promising
experimental boundary, not a production fix yet. Next validation must cover
real recurrent TransformerBlocks, FSDP2 BF16 casts, FA4 custom autograd,
multiple GAS microbatches, gradient parity, memory and timing on eight GPUs
when production is deliberately paused. No production code path was changed
for this CPU investigation.

### XXS GPU Validation (2026-09-15)

The CPU-only limitation above is now partially superseded: a real XXS
six-update comparison passed on GPUs 6/7 alongside uninterrupted production.
Both arms used the six-layer/256-hidden XXS architecture, full Gemma vocabulary,
4096-token local microbatches, global batch 16384, GAS2, BP8, FSDP2 on two ranks,
FP32 parameters, BF16 compute, FA4 PrefixLM, full composable checkpointing,
and checkpoint-aware resharding. Seed/data/optimizer settings were identical.
The experimental arm compiles each TransformerBlock forward before applying
checkpoint hooks; the outer training wrapper remains eager. No training source
or production configuration was modified. Per-process allocator cap was 10%
of device capacity; W&B and model checkpoint writes were disabled.

Entry points: `scripts/run_checkpoint_compile_xxs_probe.py` and
`scripts/probe_checkpoint_compile_xxs.py`; CPU comparison:
`scripts/compare_checkpoint_compile_xxs.py`. Results and first-step gradient
shards: `logs/experiments/checkpoint_compile_xxs/`.

| Arm | Post-warmup median step | Peak allocated | Peak reserved |
|---|---:|---:|---:|
| Eager full checkpointing | 0.3499 s | 14287 MiB | 16526 MiB |
| Block-compiled full checkpointing | 0.3926 s | 14288 MiB | 16574 MiB |

All six updates completed without metadata mismatch or OOM. Maximum absolute
loss difference was 0.000166. First-step post-clipping gradients, all 52 local
parameter shards across both ranks: relative L2 difference 0.005561 (0.556%),
cosine similarity 0.99998454, maximum absolute element difference 0.0002413.
These demonstrate close BF16 agreement, not bitwise parity or long-run
convergence equivalence. This short, co-tenanted test is not an isolated
performance benchmark and showed no speed advantage. It validates the
boundary workaround on real XXS FSDP/FA4; an eight-GPU XXL memory/timing and
longer parity test is still required before production adoption.

### Armed XXL 619K Comparison (2026-09-15)

At the user's request, the existing scheduler is soft-stopped and
`scripts/watch_checkpoint_compile_xxl_619000.py` waits for complete
`ephemeral_step_619000`, preserves it under
`checkpoints/experiments/checkpoint_compile_xxl_619000/source`, and sends SIGINT
only to the validated production torchrun group. It waits for GPUs to be free
and refuses to kill unrelated processes. Detached watcher logs/state are in
`logs/experiments/checkpoint_compile_xxl_619000/{campaign.log,state.json}`.

It then runs four 50-update, eight-GPU XXL arms from the identical snapshot:
compiled/no-checkpoint GAS8 baseline; eager full-checkpoint GAS2;
block-compiled full-checkpoint GAS2; baseline repeat. BP8, 262144-token global
batch, data cursor, optimizer and LR cooldown are preserved. All arms disable
W&B and model checkpoint writes; first-step post-clip gradient shards and
benchmark summaries are diagnostic artifacts only. Each arm has a 40-minute
timeout and isolated process group. Output comparison/performance JSONs report
gradient agreement, timing, and memory. Production remains paused afterward
for the user's decision; do not automatically promote the candidate. This is
an armed campaign, not evidence that the 619K benchmark has finished.

This assessment applies to the main branch. Its relevant constraints are the
six tied L calls and two tied H calls, BP-dependent truncated autograd, packed
PrefixLM batches, the custom two-pass FA4 path, whole-batch `torch.compile`,
per-block FSDP2, AdamATan2 EMA state, and distributed checkpoints.

| Option | Prototype | Production-ready | Main difficulty |
|---|---:|---:|---|
| Full per-block activation checkpointing | implemented | benchmarked on B200 | Uses composable checkpoint wrappers before FSDP2 wrapping. |
| Selective/per-block checkpointing | 2--5 days | 1--2 weeks | Choose a useful memory policy and verify memory/throughput tradeoffs. |
| FSDP `reshard_after_forward=true` | hours | 1--3 days | Performance measurement and checkpoint/resume validation; limited activation savings. |
| TP=2 | 2--3 weeks | 4--6 weeks | Sharded QKV/output/MLP plus vocabulary-parallel logits, CE, and metrics. |
| CP=2 | 3--5 weeks | 6--10 weeks | Correct distributed packed PrefixLM attention and backward. |
| Generic depth pipeline | 2--4 weeks | 4--8 weeks | Recurrent L/H execution repeatedly crosses pipeline boundaries. |
| HRM recurrent `L/L/L/H` pipeline | 4--6 weeks | 8--12 weeks | Cyclic schedule, tied replicas/gradients, optimizer ownership, and canonical checkpoints. |
| HRM recurrent `LL/LH` pipeline | 3--5 weeks | 6--10 weeks | Two-stage cyclic schedule and L-weight synchronization; H-side activation imbalance. |

These are indicative full-time ranges for an engineer already familiar with
the code and distributed PyTorch. Kernel work, unstable dependencies, or
multi-node debugging can increase them.

Activation checkpointing does not change weight layout or checkpoint format
and is therefore the conservative first implementation. The `checkpointing`
branch has an opt-in `activation_checkpointing=full` mode. It applies
`torch.distributed._composable.checkpoint` to every `TransformerBlock` before
FSDP2 wraps those blocks. At BP=5, checkpoint recomputation is triggered only
for the differentiable `H0`, `L3`, `L4`, `L5`, and `H1` recurrent calls. The
detached `L0--L2` calls do not retain backward activations or recompute.

The default is `activation_checkpointing=none`, which preserves the prior
path. Full mode also sets FSDP2 `reshard_after_forward=true`; ordinary mode
retains the established `false` setting. It is compatible with existing
checkpoint and EMA formats because it adds no parameters or buffers. CPU tests
verify output and gradient parity, expected BP=5 recomputation, inactivity
during evaluation, and a compiled single-process smoke path.

The initially implemented functional `torch.utils.checkpoint` wrappers were
superseded on 2026-08-26. With FSDP2 mixed precision, recomputation entered the
FSDP pre-backward state without repeating the forward BF16 parameter cast,
causing saved-BF16/recomputed-FP32 metadata mismatches. Explicit autocast,
moving functional checkpoints to blocks, disabling compile, and enabling
resharding did not resolve that FSDP2 state-machine issue. The composable API,
applied before `fully_shard`, is the working ordering.

A matched DFM8 XXL continuation from step 152500 established the memory result:

| Mode | Compile | Peak allocated / GPU | Peak reserved / GPU | Steady optimizer step |
|---|---:|---:|---:|---:|
| No checkpointing | yes | 143027 MiB | 165168 MiB | 3.53 s |
| Full block checkpointing | no | 41984 MiB | 49970 MiB | about 6.4 s |
| L-only block checkpointing | no | 90228 MiB | 105344 MiB | 5.59 s |

Full mode therefore reduced peak allocated memory by 70.6% and peak reserved
memory by 69.7%. Its observed optimizer-step time was about 1.8x the compiled
baseline. This is not a perfectly isolated throughput comparison because the
working composable FSDP2 path currently runs with `compile_train_batch=false`;
it is nevertheless representative of the resumed production configuration.

The `l_only` selective mode checkpoints the 36 blocks under `L_level` while H
remains uncheckpointed. At BP=5 this recomputes three L calls and no H calls.
In a W&B-disabled smoke resumed from DFM8 XXL step 153500, it was 13.0% faster
than full checkpointing while using 48244 MiB more peak allocated memory. Only
selected L blocks use FSDP2 `reshard_after_forward=true`; uncheckpointed H
blocks retain the established no-reshard path.

TP is not an especially natural first choice for hidden size 1792 and 14
attention heads. TP=2 is clean; larger degrees encounter head divisibility or
communication concerns. TP also requires a vocabulary-parallel implementation
for the 262,144-token untied input/output matrices and global argmax/metrics.

CP is the strongest general long-context runtime design, but the current
packed PrefixLM implementation is its hardest integration point. A correct CP
path must preserve global position IDs, prefix and causal segment boundaries,
variable-length packing, the two attention passes, and backward communication.
Keep CP groups within an eight-GPU NVLink node.

Generic pipeline partitioning avoids tied replicas but causes repeated traffic
as the recurrent execution alternates L and H. Unroll-position pipelines such
as `L/L/L/H` balance compute better, but duplicate tied L (and potentially H)
weights. Their gradients must be reduced across both data replicas and tied
stage replicas before identical optimizer/EMA updates. Checkpoints need one
canonical copy of each tied module.

Recommended order:

1. Use the validated full block checkpointing path where memory is the limiting
   resource; add a selective policy if its measured throughput cost is too high.
2. Test whether checkpointing alone makes 16K practical.
3. Implement CP=2 for production 16K/32K if long-context throughput warrants
   the engineering cost.
4. Consider the two-stage `LL/LH` or four-stage `L/L/L/H` recurrent pipeline
   only after profiling checkpointing and CP.
5. Combine CP with selective checkpointing for 32K; avoid TP unless model-state
   or GEMM width becomes the limiting factor.

Every distributed path needs one-step forward, loss, gradient, optimizer,
EMA, save/resume, and HF-export parity tests on packed prefix/causal examples
before throughput measurements are accepted.

## Positional-extension decision, 2026-08-26

Use vanilla RoPE for the next longer-context training experiment. The earlier
YaRN comparison included an incorrectly exported checkpoint and therefore does
not establish that YaRN caused the observed regression. YaRN remains a possible
later controlled comparison, but it must use correctly exported checkpoints
and otherwise matched training and evaluation settings.

## Multi-node readiness, 2026-08-26

The core trainer is structurally multi-node aware: TorchRun initializes NCCL,
CUDA placement uses `LOCAL_RANK`, sampling uses global `RANK` and `WORLD_SIZE`,
rank zero owns W&B, and distributed checkpoints use PyTorch DCP. This has not
yet been validated as an end-to-end production multi-node path.

Known gaps and constraints:

- The evaluation scheduler launches and accounts for one local GPU host; it
  does not launch or monitor multi-node TorchRun jobs.
- Checkpoint guards default to eight carry files. Multi-node plans must require
  `WORLD_SIZE` carry files.
- Carries are rank-local tensors. DCP can reshard model and optimizer state,
  but resuming with a different world size is not currently supported safely
  because carry files and shapes do not get redistributed.
- Gradient accumulation does not suppress DDP/FSDP synchronization on
  non-final microbatches, so multi-node communication is repeated for every
  accumulation microbatch.
- FSDP2 currently shards over the entire world process group. There is no
  hybrid-shard device mesh that shards within a node and replicates across
  nodes.
- Checkpoint paths must be on a shared filesystem visible under the same path
  from every node.
- `global_batch_size / (WORLD_SIZE * GAS)` must remain large enough to hold at
  least one complete packed training sequence on every rank.

Clarifications from the 2026-08-27 audit:

- TorchRun normally relies on a cluster scheduler such as Slurm to launch one
  agent per node, then uses a c10d rendezvous to assign global and local ranks.
  TorchRun does not allocate remote nodes or redistribute application state
  when elastic membership changes.
- Carry-rank requirements should come from checkpoint/run metadata, not a
  default of eight. For the current no-carry HRM, every saved carry is literally
  `None`, so changing world size does not require tensor redistribution. A
  stateful architecture would need carry state keyed by global sample identity.
- FSDP2 supports HSDP directly through a two-dimensional `DeviceMesh` whose
  first dimension replicates and second dimension shards. The repository does
  not yet construct or pass that mesh.
- FSDP2 exposes `set_requires_gradient_sync` and
  `set_requires_all_reduce` for accumulation-aware communication; DDP exposes
  `no_sync`. The current accumulation loop uses none of these and synchronizes
  each microbatch.

The copied LUMI DFM9 XXL-32 configuration is internally valid at 256 GPUs:
GBS 1,048,576, GAS 1, and 4096 tokens per rank for a 4096-token context. At
step 10K its actual packed length was 1,042,679 tokens (99.44% utilization)
across 2675 logical sequences. This geometry does not by itself explain the
reported divergence. Material differences from the current XXL run include LR
`1e-3`, only 89,665 optimizer updates per epoch, no gradient clipping, and
`bp_max_steps=3` instead of 5. Relative to the current 262,144-token, `4e-4`
run, square-root batch scaling suggests about `8e-4`; `1e-3` is 25% above that
reference. Treat LR and optimization trajectory as stronger suspects than the
one-packed-block-per-rank layout.

For the current XXL model, choose FSDP rather than replicated DDP if using only
the implemented paths. A production 2/4/8-node design should add hybrid
sharding within each fast local GPU island and DDP-style replication across
nodes, plus accumulation-aware synchronization. DDP is preferable for smaller
models only when the complete parameters, gradients, optimizer, EMA, and
activations fit comfortably on every GPU.

---
type: Operational Record
title: DFM10 XL Epoch-9 Continuation
description: Exact checkpoint, data-index, training, and 50K evaluation campaign for the DFM9 XL to DFM10 transition.
tags: [dfm10, training, xl, evaluation, resume]
status: stable
last_updated: 2026-09-07
confidence: high
---
# DFM10 XL Epoch-9 Continuation

## XXL-Wide Stability Check, 2026-09-08

At step 108,325 the active XXL-wide run was at BP6 and LR 4e-4. Remote
training history from 80K onward contained no non-finite loss values. Mean
loss/token accuracy/exact accuracy moved from 1.1806/74.06%/21.70% at
80--85K to 1.1579/74.40%/22.40% at 100--105K. The partial 105--108.325K
window was 1.1633/74.34%/22.56%, consistent with ordinary variation rather
than sustained deterioration after the BP6 transition at 94,258.

A brief loss spike reached 1.9388 at step 98,780 (token accuracy 62.25%),
then fell to 1.3581 at 98,785 and 1.0083 at 98,790. Its cause was not
established; the rapid recovery does not resemble the prior deep-XXL
multi-step divergence. The active segment log had no NaN, OOM, traceback,
runtime error, or overflow matches. All GPUs were at 100% utilization,
with 42,968--45,272 MiB free, and ordinary BP6 steps took about 2.33 seconds.
BP7 and BP8 stability remained untested at this observation.

The DFM10 continuation starts from the completed DFM9 XL endpoint at global
step `2,127,489`. The production resume alias is
`checkpoints/dfm10/XL-from-dfm9-epoch8/epoch_8`; its DCP metadata matches
`checkpoints/dfm9/XL-from-dfm8-epoch7/step_2127489`. The alias sidecar has a
zero batch/row cursor. Resuming the semantic `epoch_8` tag therefore starts
trainer epoch 9 and selects `data/sampled_dfm10/epoch_8`, the ninth sampled
DFM10 index set. Do not resume this data transition from the original DFM9
`step_2127489` sidecar, which contains the terminal DFM9 row cursor.

Direct iteration of DFM10 `epoch_8` with eight ranks, 16,384 tokens per
rank/microbatch, and GAS 2 produced 709,190 complete microbatches, 354,595
optimizer steps, no trailing microbatch, and 99.4376% packing efficiency. The
exact global endpoint is therefore `2,482,084`.

The reproducible campaign builder is
`scripts/setup_dfm10_xl_epoch9_campaign.sh`. It creates
`logs/scheduler/dfm10_XL_epoch9_20260831` with alternating training and full
standard/DFM/EuroEval releases at:

```text
2150000 2200000 2250000 2300000
2350000 2400000 2450000 2482084
```

The 50K evaluations and exact endpoint are logged to W&B project `DFM5`, run
ID `dfm8-xl-from-dfm6-dfm7-epoch5-clean-full`, with fractional x-axis values
from epoch 8.0 to 9.0. Each evaluation release uses EMA HF export, persistent
vLLM, the Gemma-native chat template/BFCL parser path, utilization 0.9 for
ordinary jobs, utilization 0.65 plus the established E4B judge for judged
jobs, and six total attempts per shard. The 4K DFM10 checkpoint omits the 8K
long-context suite by capability gate.

The training path is the measured fastest compatible single-node setup:

```text
data=dfm10
arch/size@arch=XL
global_batch_size=262144
gradient_accumulation_steps=2
epochs=9
training_total_steps=2482084
distributed_strategy=fsdp
fsdp_params_precision=fp32
fsdp_shard_degree=null
fsdp_reshard_after_forward=false
fsdp_accumulation_sync_mode=no_sync
fwd_bwd_dtype=bfloat16
activation_checkpointing=none
compile_train_batch=true
```

The campaign launched on 2026-08-31. All ranks restored step 2,127,489 with
`start_epoch=9`, `skip_batches=0`, and no row cursor. After the one-time
compile, training stabilized around 1.0--1.1 seconds per optimizer step. W&B
rejected only the already-backfilled points through step 2,127,541; new points
became monotonic afterward. No OOM, NCCL error, traceback, or NaN appeared in
the startup log.

## DFM10 XXL-Wide Follow-On

The same scheduler plan started a fresh one-epoch `XXL_wide` run only after the
exact XL endpoint evaluation and its vLLM teardown completed. It writes to
`checkpoints/dfm10/XXL-wide` and logs to the separate W&B run
`dfm10-XXL-wide` (`dfm10-xxl-wide`) in project `DFM5`.

The selected settings are:

```text
data=dfm10
arch/size@arch=XXL_wide
lr=4e-4
global_batch_size=262144
gradient_accumulation_steps=4
epochs=1
arch.bp_min_steps=2
arch.bp_max_steps=5
arch.bp_warmup_ratio=0.2
distributed_strategy=fsdp
fsdp_params_precision=fp32
fsdp_shard_degree=null
fsdp_reshard_after_forward=false
fsdp_accumulation_sync_mode=no_sync
fwd_bwd_dtype=bfloat16
activation_checkpointing=none
compile_train_batch=true
```

**Superseded 2026-09-06:** the initial scheduler row used a conservative upper
stop target of step `360000` and would have trained uninterrupted. Before the
first evaluation boundary, the plan was converted to alternating full
standard/DFM/EuroEval releases and training segments at:

```text
50000 100000 150000 200000 250000 300000 350000 353465
```

Each release has 244 GPU evaluation jobs, an evaluation barrier, persistent
vLLM teardown, and a dependent resume segment. Evaluations log directly to the
new `dfm10-xxl-wide` W&B run using fractional epoch values `step / 353465`.
The exact endpoint segment also accepts the fully written `epoch_1` checkpoint
as its completion boundary.

Because the original process had already launched with `stop_after_step=360000`,
the scheduler was stop-requested at step approximately `48870`. The detached
`handoff_xxl_at_50000.sh` watcher waits for the `step_50000` sidecar, DCP
metadata, and all eight rank shards; it then terminates only the recorded
XXL-wide process group, retires the superseded monolithic row, clears the stop
request, and restarts the same scheduler into the 50K evaluation. This may
discard only post-checkpoint work performed during the brief detection delay.

The `4e-4` learning rate is an explicit experimental choice despite the wider
hidden dimension; monitor early loss and gradient behavior against the
established XL trajectory.

The run started on 2026-09-06 after the XL endpoint evaluation. At step
approximately `16870`, the full `4e-4` learning rate had been active since the
2K-step warmup, all eight ranks remained healthy, and no NaN, overflow, OOM,
NCCL failure, or traceback had occurred. Mean loss in successive 2K windows
from steps 2K through 16K decreased from `2.3056` to `1.5975`; the partial
16K--18K window was `1.5629`. This is positive early evidence, not yet a full
stability result: BP remained at 2, so the later BP-depth transitions and the
region around the prior deep-XXL excursion have not been tested.

### First Evaluation Handoff

The detached handoff completed successfully on 2026-09-07. It verified the
fully written eight-rank `step_50000` checkpoint, stopped only the superseded
monolithic training process group, and restarted the scheduler. The complete
50K release finished with no failed rows: all 244 GPU jobs, shard merges,
checkpoint averages, W&B reporting, the terminal barrier, and persistent-vLLM
teardown completed before `xxlw-train-100000` started. The resumed segment
restored `step_50000`, advanced past step 50,090, and stabilized near 1.9
seconds/step with all eight GPUs active.

W&B finalization had advanced the run's internal step to 50,052. Consequently,
training log calls for steps 50,025 through 50,050 were rejected as
non-monotonic; training points from 50,055 onward logged normally. Future
handoffs should avoid writing post-checkpoint evaluation data at a larger
internal W&B step than the checkpoint unless this short overlap is accepted.

The 50K DFM DROP configuration exposed a sharding defect: `inspect_evals/drop`
does not accept `num_shards` or `shard_index`, so both nominal shards evaluated
the full 9,535-example filtered validation set. This duplicated compute but did
not change the equal-weight aggregate. The single-task config now uses the
local `dfm_evals/drop` wrapper, which preserves the upstream prompt and scorer
while applying deterministic disjoint sharding. An eight-way validation test
produced seven 1,192-example shards and one 1,191-example shard, totaling 9,535
with zero overlap. Existing future plan rows therefore become real shards
without altering their plan metadata.

### BP4 to BP5 Memory Transition

The warmup schedule changed the XXL-wide run from BP4 to BP5 between the W&B
samples at steps `70,690` and `70,695` on 2026-09-07. The first logged BP5
sample was step `70,695` at `12:33:12+02:00`. A one-second `nvidia-smi` sampler
captured a stable 15-minute window on each side of the allocator transition.

GPU0 increased from a BP4 peak and median of `110,866 MiB` to a BP5 peak and
median of `120,344 MiB`. GPUs1--7 each increased from `108,562 MiB` to
`118,040 MiB`. The measured increase was therefore exactly `9,478 MiB`
(`9.26 GiB`) per GPU, for both peak and median allocated device memory. BP5
left `62,276 MiB` free on GPU0 and `64,580 MiB` free on each other rank.

The displayed rolling step time rose from approximately `1.88 s/step` under
BP4 to `2.13 s/step` after 500 BP5 steps, an increase of about 13%. At step
`71,195`, all GPUs remained fully utilized and the recent training log
contained no NaN, OOM, traceback, or runtime error.

On 2026-09-07, the recurrence warmup was extended proportionally through BP8.
The scheduler was soft-stopped, and training was terminated only after
`ephemeral_step_78500` had a complete sidecar, DCP metadata, and all eight rank
shards. The active row resumed from that exact checkpoint with:

```text
arch.bp_min_steps=2
arch.bp_max_steps=8
arch.bp_warmup_ratio=0.4
```

These settings preserve the original BP2--BP5 slope and produce exact internal
transition steps BP3 `23,565`, BP4 `47,129`, BP5 `70,693`, BP6 `94,258`, BP7
`117,822`, and BP8 `141,386`. All seven remaining segmented XXL-wide training
rows use the extended settings. The resumed process restored
`skip_batches=314000`, remained at BP5 as intended, and stabilized near
`2.13 s/step`; both W&B config and checkpoint `all_config.yaml` report BP max 8
and warmup ratio 0.4. No NaN, OOM, traceback, or runtime error appeared in the
new attempt through step `78,610`.

The fresh resumed process reserved about 5.3 GiB/GPU more than the prior
long-lived BP5 process: `125,744 MiB` on GPU0 and `123,440--123,442 MiB` on
GPUs1--7. Conservatively applying the measured `9,478 MiB` marginal BP cost to
this higher baseline projects BP8 at about `154,178 MiB` on GPU0 and
`151,874--151,876 MiB` on the other ranks, retaining approximately 28--30 GiB
of physical device headroom without activation checkpointing.

### Early Wide-versus-Deep XXL Training Metrics

An early comparison against W&B run `40j5y877` (`dfm8-XXL-1epoch`) used raw
training rows at equal optimizer-step ranges. The old model is the deeper
`72x1792` XXL trained on DFM8; the current model is the wider `32x2560`
XXL-wide trained on DFM10. Both use 262,144 tokens/step, GAS 4, and `4e-4`, but
the datasets and BP schedules differ.

| Step window | Model | Mean loss | Mean token accuracy | Mean exact accuracy |
|---|---|---:|---:|---:|
| 0--70K | deep XXL | 1.43678 | 70.1433% | 16.4173% |
| 0--70K | XXL-wide | 1.47905 | 69.8181% | 15.9939% |
| 50--70K | deep XXL | 1.15279 | 74.1269% | 21.2637% |
| 50--70K | XXL-wide | 1.21417 | 73.5123% | 20.4469% |

The equal-step result modestly favors deep XXL. It is not an architecture-only
comparison: the old 268,857-step DFM8 epoch reached BP5 at approximately step
53,772, while the 353,465-step DFM10 epoch reached BP5 at step 70,695. In
matched late-BP windows, XXL-wide was competitive: its late-BP2 loss differed
by only `+0.00149`, while token and exact accuracy were higher by 0.40 and 0.48
percentage points; in late BP3, token accuracy was equal within 0.05 points
and exact accuracy was 0.66 points higher despite `+0.02161` loss. The current
evidence therefore shows a small raw training-metric deficit, but does not show
that the wider architecture is intrinsically harder to optimize.

#### Refreshed comparison through step 88K

On 2026-09-07, remote W&B history was compared through the last common complete
boundary at step `88,000`. At equal optimizer steps, deep XXL remained ahead:

| Step window | Model | Mean loss | Mean token accuracy | Mean exact accuracy |
|---|---|---:|---:|---:|
| 0--88K | deep XXL | 1.36700 | 71.1355% | 17.7209% |
| 0--88K | XXL-wide | 1.41823 | 70.6838% | 17.1365% |
| 50--88K | deep XXL | 1.13707 | 74.3834% | 21.8311% |
| 50--88K | XXL-wide | 1.19884 | 73.7666% | 20.9826% |
| 80--88K | deep XXL | 1.12113 | 74.6486% | 22.4545% |
| 80--88K | XXL-wide | 1.17574 | 74.1429% | 21.7714% |

The equal-step comparison gives deep XXL a late 80--88K advantage of `0.05462`
loss, `0.51` percentage points token accuracy, and `0.68` percentage points
exact accuracy. However, deep XXL entered BP5 around step `53,772`, while
XXL-wide entered it at `70,693`. Comparing each model's first approximately
17.3K BP5 steps reduces the apparent optimization difference: deep/wide loss
is `1.14645`/`1.18108`, token accuracy is `74.2237%`/`74.0604%`, and exact
accuracy is `21.4826%`/`21.6005%`. The wide model is therefore nearly tied on
the two accuracy measures at matched BP5 exposure, although its mean loss
remains higher. Loss and training accuracy are also conditioned on different
DFM8 and DFM10 sample mixes, so this is not an architecture-only or
downstream-quality comparison.

### XXL-Wide 50K/100K Evaluation Comparison

The complete 100K XXL-wide evaluation release finished on 2026-09-08 with no
failed scheduler rows. A comparison with the deep DFM8 XXL run `40j5y877` was
computed from remote W&B checkpoint-aligned history. Because XXL-wide runs 20
newer DFM/FlexOLMo metrics absent from the old campaign, suite comparisons below
use only the 35 headline metrics present at both 50K and 100K for both models.
This avoids penalizing XXL-wide merely for evaluating additional difficult
tasks.

| Common-metric average | Deep XXL 50K | Deep XXL 100K | XXL-wide 50K | XXL-wide 100K |
|---|---:|---:|---:|---:|
| Danish (16 metrics) | 0.4461 | 0.5355 | 0.3966 | 0.4914 |
| English (15 metrics) | 0.4596 | 0.5432 | 0.4387 | 0.5192 |
| Math/code (4 metrics) | 0.4344 | 0.4878 | 0.2575 | 0.3977 |
| Standard (8 metrics) | 0.4148 | 0.5300 | 0.3700 | 0.4841 |
| DFM (11 metrics) | 0.4923 | 0.5866 | 0.4335 | 0.5285 |
| EuroEval (16 metrics) | 0.4397 | 0.4985 | 0.3892 | 0.4721 |

XXL-wide remains behind at 100K, but its 50K-to-100K math/code gain is `+0.1402`
versus `+0.0535` for deep XXL, reducing that gap from `0.1768` to `0.0902`.
Its EuroEval gain is also larger (`+0.0829` versus `+0.0588`). Standard and DFM
common-suite gains are nearly equal between runs, leaving gaps of approximately
`0.046` and `0.058` at 100K.

At 100K, XXL-wide is already ahead on standard DROP F1 (`0.6717` versus
`0.6033`) and EuroEval BFCL-v2 tool calling (`0.6552` versus `0.6328`), and is
close on MMLU (`0.4136` versus `0.4195`) and BoolQ (`0.7440` versus `0.7609`).
Its largest selected deficits remain GSM8K (`0.4966` versus `0.7134`), MATH
(`0.2072` versus `0.3002`), and HumanEval (`0.2317` versus `0.3049`). The
comparison is equal-step/equal-token, but not architecture-only: it contrasts
DFM10 with DFM8 and different recurrence schedules.

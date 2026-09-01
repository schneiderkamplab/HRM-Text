---
type: Operational Record
title: DFM10 XL Epoch-9 Continuation
description: Exact checkpoint, data-index, training, and 50K evaluation campaign for the DFM9 XL to DFM10 transition.
tags: [dfm10, training, xl, evaluation, resume]
status: stable
last_updated: 2026-08-31
confidence: high
---
# DFM10 XL Epoch-9 Continuation

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

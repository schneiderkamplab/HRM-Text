---
type: Plan
title: DFM8 XXL to DFM10 Multi-Node Transition
description: Planned epoch-boundary transition from the one-node DFM8 XXL run to a four- or eight-node DFM10 continuation.
tags: [dfm8, dfm10, xxl, multi-node, hsdp, training]
status: stable
last_updated: 2026-08-31
confidence: high
---
# DFM8 XXL to DFM10 Multi-Node Transition

The intended transition point is the fully written DFM8 XXL `epoch_1`
checkpoint. Changing both dataset and topology at this exact epoch boundary is
safer than an in-epoch change: there is no old-dataset row cursor to repartition,
and the DFM10 epoch index can begin from a clean boundary. Preserve model,
optimizer, and EMA state and continue the global optimizer-step counter.

## Batch Geometry

Keep global batch size 262144 and 4K context:

| Topology | World size | GAS | Tokens per GPU per microbatch | Comment |
|---|---:|---:|---:|---|
| Current one node | 8 | 4 | 8192 | Established production path |
| Four nodes | 32 | 1 | 8192 | Same local geometry; removes accumulation |
| Eight nodes | 64 | 1 | 4096 | One full context block per rank; more memory headroom |

Use native FSDP2 HSDP with `fsdp_shard_degree=8`: shard parameters within each
NVLink-connected node and replicate across nodes. Start with
`fsdp_reshard_after_forward=false` for speed, but measure memory before
production. Four nodes retain the current very tight 8192-token local memory
geometry, and HSDP replica communication may add buffers. Eight nodes halve
local tokens and should have more activation headroom, at the cost of a larger
cross-node replica group and lower per-GPU kernel occupancy.

Do not scale LR with node count because GBS is unchanged. The dataset boundary
is a reasonable point to reduce the aggressive constant LR from `4e-4` to
`3e-4`; `pretrain.py` reapplies the configured LR after loading optimizer
state. Do not restart warmup, optimizer moments, or EMA.

## Readiness Gates

**Superseded on 2026-08-31:** DFM10 has been transferred to this node and is
now launchable. `data/sampled_dfm10` contains ten sampled epoch index sets and
`92,658,813,451` tokens per epoch. The transferred metadata's stale
`/work/dfm/...` tokenizer path was replaced with the repository-relative
`../brainsurgery/models/gemma4_31b/tokenizer.json` contract; token and index
arrays were not modified.

The earlier source-quality gates were addressed before this sampled artifact
was transferred. The remaining operational gates are the fully written DFM8
epoch-one checkpoint and its full standard, DFM, and EuroEval campaign.

**Superseded on 2026-08-28:** the launcher and HSDP implementation are now
validated for a two-node, 16-rank checkpoint resume and short training run.
HSDP with shard degree 8 achieved 4.227 seconds per step versus 13.424 seconds
for full-world FSDP, but both used NCCL sockets because `/dev/infiniband` was
missing. This validates correctness, not production scaling. Before the
transition:

1. Require an allocation where NCCL selects its RDMA transport, then repeat
   the SSH/software/path preflight and NCCL all-reduce bandwidth gate.
2. Load a copy of the DFM8 epoch checkpoint on 16 ranks and save a disposable
   HSDP checkpoint without W&B logging. Loading and stepping from an in-epoch
   checkpoint is verified; the changed-topology save still needs validation.
3. Verify optimizer, EMA, global step, no-carry policy, and DCP completeness.
4. Repeat on four nodes, including a forced agent failure and exact coordinated
   teardown.
5. Benchmark at least 200 steady steps on four and eight nodes, comparing
   tokens/second, peak memory, NCCL time, and input stalls.
6. Export and run one evaluation smoke from a multi-node-produced checkpoint.

Use the [fixed-membership SSH launcher](multinode-ssh-launcher.md). Prefer the
four-node topology as the closest numerical/per-rank control. Prefer eight
nodes for production only if its measured throughput is materially higher and
the shared filesystem and cross-node replica all-reduce remain healthy.

## Optional In-Epoch DFM8 Acceleration

As of 2026-08-27, the active one-node DFM8 XXL run was at step 162495 of an
estimated 268857, at about 3.56 seconds per optimizer step. Approximately 105
hours of one-node compute therefore remained before accounting for evaluation
pauses. A topology change can repay its validation cost, but must not jump
directly from the established 8-rank path to an untested 64-rank production
job.

The new checkpoint sidecars record an exact `global_row_cursor_in_epoch`, and
this model records `carry_policy=none`. These make a mid-epoch world-size
change tractable. They do not prove that an 8-rank DCP checkpoint expands
correctly onto 16, 32, or 64 real ranks, or that multi-node HSDP, NCCL, SSH
orchestration, and shared-filesystem checkpointing are production-ready.

Use the following staged gate without changing global batch size or LR:

1. Keep the one-node production process running while provisioning nodes and
   passing SSH/NCCL preflight.
2. From a fully written ephemeral checkpoint copy, run a W&B-disabled two-node
   smoke with `fsdp_shard_degree=8`, GAS 2, and 5--20 optimizer steps. Save a
   disposable checkpoint and verify model, optimizer, EMA, step, exact row
   cursor, and DCP completeness.
3. If that passes, switch production only at a subsequent fully written
   ephemeral checkpoint. Benchmark the two-node steady-state rate first.
4. Validate four nodes with GAS 1 before choosing it for production. This is
   the preferred speed/risk compromise because it preserves 8192 local tokens
   per GPU while removing accumulation.
5. Treat eight nodes as a later benchmark, not the first production switch. It
   reduces local tokens to 4096 per GPU but introduces a larger replica group,
   lower per-GPU work, and 64-rank checkpoint/filesystem pressure.

The unmeasured planning ranges are roughly 1.6--1.9x for two nodes, 2.5--3.3x
for four nodes, and 3--5x for eight nodes. Replace these estimates with measured
end-to-end rates including checkpoint stalls. Adjust ephemeral checkpoint
intervals after measurement to retain a roughly 30--60 minute wall-clock
cadence rather than retaining the one-node 500-step cadence automatically.

## Checkpoint Cadence

Step time should fall substantially, so retaining a 500-step ephemeral cadence
would produce large checkpoints too frequently. Target roughly 30--60 minutes
between ephemerals based on measured steady-state time. Keep regular semantic
checkpoints at evaluation boundaries. DCP writes from 32 or 64 ranks must be
tested against the shared filesystem before selecting exact intervals.

## Evaluation Attribution

Run and preserve a full DFM8 epoch-one evaluation before the switch. Evaluate
DFM10 every 50K global steps afterward. W&B and reports must label the dataset
transition explicitly so later gains are not attributed solely to XXL scale or
multi-node execution.

## Scheduled Single-Node Transition

On 2026-08-31, the transition was appended under the lock of the existing
scheduler plan:

```text
logs/scheduler/dfm8_XXL_1epoch_steps50k_100k_persistent_vllm_20260725/plan.tsv
```

The current DFM8 row targets step `268857`. Because a `stop_after_step`
boundary exits before epoch-checkpoint saving, a guarded finalization row
resumes `step_268857`, exhausts any residual DFM8 batches, and accepts the
natural `epoch_1` checkpoint. If the active row naturally exhausts first, the
same `epoch_1` completion tag makes the finalizer a no-op.

The scheduler then exports and fully evaluates DFM8 `epoch_1`, including
standard, DFM, and EuroEval suites, atomic v3 averages, and W&B synchronization
to `DFM5/40j5y877`. Only its terminal eval barrier and persistent-server
teardown release the first DFM10 training row.

DFM10 resumes model, optimizer, EMA, and global optimizer step from DFM8
`epoch_1`, while writing new checkpoints under:

```text
checkpoints/dfm10/XXL-from-dfm8-epoch1
```

The continuation preserves the established single-node performance geometry:
eight B200 GPUs, global batch `262144`, GAS `4`, FP32 FSDP parameters, BF16
forward/backward compute, `fsdp_reshard_after_forward=false`, FSDP accumulation
`no_sync`, compiled batches, LR `2.5e-4`, and norm-1 gradient clipping. It uses
`epochs=2` so resuming `epoch_1` selects zero-based DFM10 index set `epoch_1`.
The progress denominator is conservatively set to global step `622400`; natural
dataset exhaustion and `completion_checkpoint_tag=epoch_2` are authoritative.

Full evaluations are interleaved at global steps 300K, 350K, 400K, 450K,
500K, 550K, and 600K. The natural DFM10 `epoch_2` checkpoint receives a final
full evaluation. Eval terminal barriers release subsequent training without
waiting for CPU-side merges and averages, while those jobs continue and sync
independently. All nine newly queued exports explicitly use the Gemma 4
tokenizer directory on `/work/mimir`.

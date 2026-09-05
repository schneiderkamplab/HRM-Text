---
type: Plan
title: DFM8 XXL to DFM10 Multi-Node Transition
description: Planned epoch-boundary transition from the one-node DFM8 XXL run to a four- or eight-node DFM10 continuation.
tags: [dfm8, dfm10, xxl, multi-node, hsdp, training]
status: stable
last_updated: 2026-09-05
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

**Superseded 2026-09-01:** the metadata-derived DFM8 target `268857` and the
first guarded target `268900` were both below the real sampled epoch boundary.
The corrected finalizer resumed `step_268900` with an explicit safe upper bound
and naturally wrote `epoch_1` at global step **270584**. See the
[DFM8 XXL epoch-one recovery record](/pages/dfm8-plan/dfm8-xxl-epoch1-resume-2026-08-26.md).

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
**Superseded 2026-09-01:** global step `622400` was not a safe upper bound. The
current DFM10 metadata alone predicts approximately step `624049` before
packing overhead, and DFM8 metadata had understated its real packed boundary.
All pending DFM10 segments therefore use `training_total_steps=630000`; the
final row resumes `step_600000`, uses `stop_after_step=630000` only as an upper
guard, and requires `completion_checkpoint_tag=epoch_2`. Natural `epoch_2`
exhaustion remains authoritative.

Full evaluations are interleaved at global steps 300K, 350K, 400K, 450K,
500K, 550K, and 600K. The natural DFM10 `epoch_2` checkpoint receives a final
full evaluation. Eval terminal barriers release subsequent training without
waiting for CPU-side merges and averages, while those jobs continue and sync
independently. All nine newly queued exports explicitly use the Gemma 4
tokenizer directory on `/work/mimir`.

## 2026-09-01 Scheduler Recovery

A cluster soft-stop created at `07:23` was cleared while the already-running
DFM10-to-300K segment continued. The stopped checkpoint wait rows returned to
pending/running state. A complete graph audit found 3,695 unique job IDs, no
missing dependencies, no remaining `/work/dfm` paths in plan metadata, and the
intended chain at every DFM10 checkpoint:

```text
training -> checkpoint wait -> HF export -> GPU eval terminal barrier
         -> persistent-server teardown -> next training segment
```

The terminal barrier deliberately uses terminal rather than success semantics,
so an exhausted eval retry does not waste GPUs by blocking later training.
Merges, averages, reports, and W&B synchronization remain independent of the
training-release path.

The agreement-supplied Andersen validation file
`pairs_chunked_val.jsonl` was not transferred to this `/work/mimir` node. Its
epoch-one eval exhausted retries on the stale `/work/dfm/andersen` path. To
avoid repeating that deterministic failure and blocking checkpoint averages,
the nine Andersen eval rows and their nine merge rows were marked skipped, and
their merge dependencies were removed from the corresponding averages. Restore
and re-enable those rows only after placing the exact 119-row validation
artifact on this node and updating `config/dfm_evals_hrm_single_tasks.yaml`.

Operational follow-up, 2026-09-02: a cluster soft stop terminates the worker
loop but does not terminate an already detached training subprocess. Clearing
`stop.request` reopens plan dispatch but does **not** recreate that worker. In
this incident training reached step 300000 and wrote a complete checkpoint at
23:47, then export/evaluation remained idle for about 90 minutes because only
the coordinator and monitor survived. Recovery reused the existing coordinator
and plan and relaunched the local worker with `--environment hrm` and
`--persistent-vllm`; the 300K export completed and EuroEval dispatch began.
After clearing a cluster stop, always verify both a fresh worker heartbeat and
an `eval_scheduler cluster worker` process rather than relying on coordinator
health alone.

## 2026-09-02 Checkpoint-Safe LR Reduction

The active DFM10 continuation was soft-stopped at the first strictly newer
ephemeral checkpoint, `ephemeral_step_313000`. Both its sidecar and DCP
`.metadata` were verified before terminating the exact training process group.
The sidecar records global step `313000`, epoch `2`, exact in-epoch cursor
`26650411`, global batch `262144`, GAS `4`, world size `8`, and carry policy
`none`.

The interrupted 313K-to-350K scheduler row now resumes from that exact DFM10
checkpoint with `lr=2e-4`. All subsequent DFM10 training rows through natural
`epoch_2` completion also use `lr=2e-4`. Model, optimizer, EMA, data cursor, and
global-step state are preserved; `reset_ema_on_resume=false` and optimizer-state
upcasting remains disabled. The continuation stays on the existing W&B run
`DFM5/40j5y877`. After clearing the cluster stop, both coordinator and local
worker were relaunched; the resumed job passed step `313000` successfully.

Early stability evidence does not support claiming that the lower LR removed
the instability immediately. At `2e-4`, steps approximately `313600--313795`
formed a severe but finite burst (maximum logged loss `16.39`, maximum logged
gradient norm about `3.53e5`, and essentially continuous norm-1 clipping).
Metrics recovered sharply by step `313800`. The longer `314120--314605`
follow-up remained clean: mean loss `1.056`, median loss `1.055`, maximum loss
`1.293`, mean accuracy `0.762`, median gradient norm about `0.23`, four clipped
updates among 98 logged points (all before step `314500`), and no non-finite
loss. A subsequent check through step `316195` added roughly 1,600 clean
steps: 500-step mean losses stayed between `1.018` and `1.044`, the maximum
single logged loss was `1.282`, median gradient norms stayed near
`0.21--0.23`, only five of 320 logged updates clipped, and none were
non-finite. That initial conclusion was superseded by the next observation:
a second transient event occurred around `318595--318700`. Maximum logged loss
was `7.87`, one isolated pre-clipping gradient norm reached about `9.57e7`,
and clipping engaged throughout the affected updates. The run recovered by
step `319000`; the subsequent roughly 1,000 steps again had mean loss near
`1.02`, median gradient norm near `0.21`, and only one clipped logged update.
Thus `2e-4` preserves rapid recovery and a clean baseline but has not
eliminated recurring episodic instability.

By step `329215`, another gradient-spike cluster had appeared near `328500`.
Its maximum pre-clipping gradient norm was about `3.54e5`, but maximum loss was
only `1.61`; loss returned below `1.16` in the following logged window. Across
the surrounding `323610--329215` interval, 1K-step mean losses stayed near
`0.99--1.02`, apart from that modest excursion, with no non-finite loss. This
supports retaining `lr=2e-4`: clipping and the reduced LR are containing the
observable loss impact, although the recurring gradient trigger remains.

**Superseded 2026-09-03:** evidence through step `333930` no longer supports
retaining `2e-4` unchanged. A larger event began near step `329760` (maximum
loss `9.87`, maximum logged gradient norm about `1.37e6`) and was followed by
several thousand unusually unstable steps. Per-1K clipping rates were about
`73.5%`, `30%`, `52%`, and `28.5%` from 330K through 334K, while mean loss and
exact accuracy had not fully returned to the earlier clean baseline. There
were still no non-finite losses, but norm-1 clipping alone did not contain the
trajectory quickly enough. The conservative next intervention is a
checkpoint-safe reduction to `1.5e-4`; deciding whether to rewind before the
329.76K event requires comparing available checkpoint state and the cost of
discarding subsequent work.

The intervention was applied on 2026-09-03. Scheduler dispatch was stopped,
the fully written `ephemeral_step_334000` sidecar and DCP metadata were
verified, and only the active training process group was terminated. The
current and all subsequent DFM10 training rows now use `lr=1.5e-4`; the current
row resumes the exact 334K checkpoint without resetting EMA or optimizer
state. Because the old process had reached step 334080 after writing the 334K
ephemeral, W&B correctly rejected duplicate logs through step 334075. The new
regime first became visible at step 334080: loss `0.957`, gradient norm `0.199`,
no clipping, and finite metrics.

The first longer `1.5e-4` review through step `336360` was clean across 457
new-regime logged points: no clipping and no non-finite loss, maximum loss
`1.216`, 1K-window mean loss near `0.99` and then `0.965`, median gradient norm
near `0.21`, and improving mean accuracy/exact accuracy. This supports holding
`1.5e-4` rather than reducing it further.

Subsequent event-onset analysis found no stable period. Grouping sustained
clipping/loss excursions into major late-run episodes gives approximate onset
gaps of `5,015`, `11,145`, and `6,745` optimizer steps; earlier at `2.5e-4`,
clusters were both more frequent and often merged into long unstable regions.
The wide spread and nested sub-events do not support a clock-like optimizer or
checkpoint cadence. A deterministic data-position trigger or data/model-state
interaction remains more plausible than a fixed temporal period.

**Superseded 2026-09-03:** the longer observation through step `340835` shows
that `1.5e-4` is not reliably stable. Clipping affected roughly 44--47% of
logged updates over 336K--339K, with a severe loss event around
`338255--338405` (maximum loss `7.68`, maximum gradient norm in its 1K window
about `6.78e6`). The run recovered by 339K; 339K--340.8K again showed mean loss
around `0.98--0.99`, median gradient norm about `0.21`, and almost no clipping.
The recurrence at progressively lower LR indicates an underlying episodic
trigger rather than a pure LR-threshold failure. If optimizing conservatively,
`1e-4` is the next reasonable containment setting, but the trigger should also
be investigated rather than repeatedly treating LR as the sole cause.

## XXL-Wide 200K Runtime Estimate

For a possible fresh `XXL_wide` comparison, the checked-in geometry uses 32
configured layers at width 2560, versus XXL's 72 layers at width 1792. With
`half_layers=true`, these become 16 versus 36 layers in each H/L stack.
Recurrence-aware major-operation accounting at 4K context gives XXL-wide about
`85.6--86.7%` of XXL's dominant work per token across BP steps 2--5, although
XXL-wide has roughly 3% more stored parameters because of its wider embedding
and untied vocabulary head. Applying that ratio to the current optimized XXL
BP-5 rate near 2.8 seconds/step and accounting for BP warmup gives a provisional
**5--6 days of uninterrupted training to 200K steps** at global batch 262144
and GAS 4. Four full 50K-boundary evaluations would likely bring elapsed
walltime to roughly 6--7 days. This remains an estimate until a short B200
XXL-wide throughput and memory benchmark is run; GAS 2 may fit and improve it.

## Stability Through Step 362K

The 2026-09-04 review supersedes the early clean assessment of `lr=1.5e-4`.
Between approximately 341K and 360K, the run experienced several substantial
events: maximum logged losses included `4.57`, `11.45`, `12.75`, `9.24`, and
`10.30`; the largest logged gradient norm was about `1.98e11`. Multiple 2K
windows clipped 28--58% of logged updates, and the 346K--348K window had mean
loss `2.05` with marked accuracy collapse. No non-finite loss occurred, and
the run recovered again after 360K to mean loss about `0.99` and median
gradient norm about `0.22`, but repeated recovery does not make the trajectory
acceptably stable. `1.5e-4` therefore failed as a sufficient containment LR;
the conservative next setting is `1e-4` at a verified ephemeral checkpoint,
alongside investigation of the recurring data/model-state trigger.

## Stability Through Step 377K

The next observation window, steps `362570--375330`, was mostly healthy but
contained another concentrated gradient event. Loss stayed bounded throughout:
the ordinary 1K-window mean losses were `0.953--0.970`, the largest logged loss
was `1.239`, and accuracy/exact accuracy remained near `0.778--0.780` and
`0.290--0.297`. At steps `372610--372875`, however, 30 consecutive logged
points clipped at norm 1 and the largest pre-clipping gradient norm reached
about `467`. The event did not produce the loss and accuracy collapse seen in
earlier episodes. By 373K the median gradient norm had returned near `0.216`,
and no updates clipped from 373K through step 377100.

This is evidence that norm-1 clipping successfully contained this particular
event, not that the underlying instability has disappeared. The recurrence
still supports treating `1.5e-4` as episodically unstable and retaining `1e-4`
as the conservative next LR if another material loss excursion occurs.

A second, shorter gradient burst appeared at steps `377105--377160`. All 12
logged updates in that interval clipped, with maximum pre-clipping gradient
norm about `3830`, but loss remained bounded at or below `1.132` and
accuracy showed no sustained decline. Gradient norm was back below 1 by step
`377165` and remained near its ordinary `0.21--0.23` range through the
latest logged step `377220` (local progress approximately `377225`). Thus
clipping again contained the observable model-metric impact, while the short
gap since the prior event confirms that the underlying trigger remains active.

From step `377225` through approximately `379190`, the run was substantially
calmer. There was only one isolated clipped point, at step `378720`, with a
modest pre-clipping gradient norm of `1.55`; its loss was `1.081`. All other
logged gradients remained below the clipping threshold, no loss was non-finite,
and 1K-window mean loss improved from `0.971` to `0.956` and then `0.940`
in the partial 379K window. This extends the currently healthy trajectory but
does not yet erase the longer-run evidence of intermittent gradient bursts.

### Interruption and recovery at step 386500

The subsequent interval was not stable throughout. Steps `379190--382999`
were mostly clean, with one isolated clipped point at step `380575`. A major
event then ran from approximately `383080--386005`: 474 logged points clipped,
maximum pre-clipping gradient norm reached about `1.51e5`, maximum loss was
`6.489`, and the 384K window's mean accuracy/exact accuracy fell to
`0.704/0.184`. There was a brief recovery after 386K, followed by another
active burst from `386555` through the last pre-interruption metric at
`386740`; its maximum gradient norm was about `3.98e4` and maximum loss
`2.488`. No non-finite loss was recorded.

After the 2026-09-05 machine interruption, the newest fully written checkpoint
was verified as `ephemeral_step_386500`: its sidecar, DCP metadata, and eight
nonempty rank files were present. The existing scheduler row
`campaign-dfm10-train-400000` was atomically retargeted from its older resume
source to that exact checkpoint, all seven stale running rows were reset, and
the existing one-node coordinator/worker campaign was restarted. Training
resumed on all eight GPUs with the same optimizer, EMA, data cursor,
`lr=1.5e-4`, and norm-1 clipping. Because the interrupted process had logged
through step 386740 after writing the 386500 checkpoint, resumed W&B metrics
through that small overlap are expected to be rejected as non-monotonic; this
does not alter training state.

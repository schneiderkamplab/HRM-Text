---
type: Plan Record
title: DFM8 XXL Epoch 1 Resume
description: Verified scheduler continuation from the latest complete ephemeral through the first DFM8 epoch.
tags: [dfm8, xxl, training, evaluation, scheduler]
status: stable
last_updated: 2026-08-29
confidence: high
part_of: /pages/dfm8-plan.md
---
# DFM8 XXL Epoch 1 Resume

The stopped DFM8 XXL campaign is resumed in its existing plan:

```text
logs/scheduler/dfm8_XXL_1epoch_steps50k_100k_persistent_vllm_20260725
```

The source is the fully written eight-rank checkpoint
`checkpoints/dfm8/XXL-1epoch/fsdp2_ephemeral_step_151000`, with all eight carry
files and an exact state sidecar. Training continues in the existing W&B run
`peter-sk-sdu/DFM5/40j5y877`, named `dfm8-XXL-1epoch`; the remote history was
at step 151175 before resume, so repeated points through 151175 may be rejected
as non-monotonic before normal logging resumes.

The remaining chain is:

```text
151K -> train to 200K -> short-context 200K eval -> train to 250K
     -> short-context 250K eval -> train until epoch_1
```

Each evaluation graph has 188 GPU rows across standard, DFM, DFM IFEval-DA,
and EuroEval. Every row uses a 4096-token server ceiling; no RULER, LongAlign,
LongBench, Marathon, or other long-context task is present. EMA checkpoints are
exported before evaluation. Non-judged servers retain utilization `0.95`;
generative Talemaader retains batch 16, utilization `0.85`, and the separate
`unsloth/gemma-4-E4B-it` SDPA judge.

Training uses the same environment and precision path as the successful 151K
lineage: explicit `hrm` TorchRun, DFM8 data, XXL architecture, LR `4e-4`, global
batch `262144`, GAS 4, FP32 FSDP parameters, BF16 forward/backward, EMA
`0.9999`, BP 2-to-5 with warmup ratio `0.2`, and sharded checkpoints. The
command also mirrors the latest successful 8K training envelope by explicitly
setting GCC, G++, assembler, compiler path, and `hrm/bin` on `PATH`.

The final numeric target `268857` remains a conservative metadata-derived
upper bound. The scheduler now accepts the fully verified `epoch_1` checkpoint
when the data loader exhausts before that estimate, preventing the historical
false failure caused by demanding a nonexistent estimated step checkpoint.

The runner uses the verified `hrm` environment, `CUDA_HOME=/usr/local/cuda`,
persistent vLLM, FA4 attention, and `VLLM_USE_FLASHINFER_SAMPLER=0`. A detached
watcher records to `start-watch.log`; it waits until every GPU has at least
178000 MiB free, waits another two minutes, then checks scheduler state, the
training process, and forward/backward progress. While the independent DFM10
audit owns the GPUs, only the plan's CPU-side checkpoint waits run.

## Intentional pause at step 152500

On 2026-08-26 the scheduler received a soft stop request. A detached watcher
then waited for `ephemeral_step_152500` to become complete before terminating
the active TorchRun process. The checkpoint has a readable state sidecar,
FSDP/DCP metadata, and all eight rank carry files. No training or scheduler
runner process remains active, and the plan's `stop.request` remains present.

The scheduler consequently records `campaign-train-200000` as failed with
status `-15`; this is the expected result of the intentional SIGTERM, not a
training failure. Before continuing, update that row to resume from
`ephemeral_step_152500`, reset it to pending, and clear the stop request only
when training should actually restart.

## Checkpointed continuation from step 152500

The pause description above was superseded later on 2026-08-26. The scheduler
was resumed from the verified `ephemeral_step_152500` checkpoint with:

```text
activation_checkpointing=full
compile_train_batch=false
memory_log_interval=1
```

The first functional-checkpoint implementations failed before advancing the
optimizer because FSDP2 recomputation produced FP32 tensors where the original
forward saved BF16 tensors. Those failed starts did not alter checkpoint state.
The working implementation applies PyTorch composable checkpoint wrappers to
Transformer blocks before FSDP2 wrapping. It passed step 152500 and continued
normally in the existing W&B run and scheduler campaign.

The matched no-checkpoint control peaked at 143027 MiB allocated and 165168 MiB
reserved per GPU. Full checkpointing peaked at 41984 MiB allocated and 49970
MiB reserved, reductions of 70.6% and 69.7%, respectively. The current
checkpointed path runs at approximately 6.4 seconds per optimizer step after
warmup, versus 3.53 seconds for the compiled control. The throughput comparison
includes the current requirement to disable whole-batch compile.

## Selective checkpoint smoke and normal continuation

Training was soft-stopped again after the fully written
`ephemeral_step_153500` checkpoint. A W&B-disabled eight-step smoke from that
exact state tested `activation_checkpointing=l_only` with compile disabled and
no checkpoint writes. It measured 90228 MiB peak allocated, 105344 MiB peak
reserved, and a 5.59-second median optimizer step. The production campaign is
then resumed from step 153500 with `activation_checkpointing=none`,
`compile_train_batch=true`, and normal W&B logging, as requested.

On 2026-08-27 the scheduler was soft-stopped again and the exact production
TorchRun was terminated at approximately step 161115. The newest authoritative
resume point is the fully written `ephemeral_step_161000`, with DCP metadata,
state JSON, and all eight carry files. The 115-step unsaved tail is intentionally
discarded. All carries contain `None`, confirming that this HRM variant has no
cross-batch recurrent state to redistribute when changing world size.

## Production resume from step 161000

On 2026-08-27 the existing scheduler plan was repaired under its advisory lock
and resumed from `ephemeral_step_161000`. The plan repair utility now accepts an
explicit `--resume-tag`; this avoids embedding an obsolete ephemeral in future
recoveries. The failed 200K training row was reset to pending, its log directory
was changed to `logs/training/dfm8_XXL_1epoch/step_161000_to_200000`, and the
same evaluation and continuation graph was retained.

The resumed command explicitly selects the measured fastest compatible
single-node path:

```text
activation_checkpointing=none
compile_train_batch=true
fsdp_shard_degree=null
fsdp_reshard_after_forward=false
fsdp_accumulation_sync_mode=no_sync
```

It retains eight GPUs, GBS 262144, GAS 4, FP32 FSDP parameters, BF16 compute,
FA4, and W&B run `DFM5/40j5y877`. All eight ranks restored `step=161000`,
`start_epoch=1`, and `skip_batches=644000`. The run advanced past step 161015;
post-compilation five-step intervals were approximately 18 seconds. W&B warns
about non-monotonic points until the resumed process passes the previously
logged unsaved tail at step 161111; those warnings are expected and do not
alter checkpoint correctness.

## Capacity crossover interpretation

The configured XXL model has `3,978,299,136` parameters, versus
`1,786,773,504` for XL. At GBS 262144, the 50K, 100K, and 150K checkpoints
represent 13.11B, 26.21B, and 39.32B tokens, or only 3.3, 6.6, and 9.9 tokens
per XXL parameter. The estimated end of epoch one at step 268857 is 70.48B
tokens, or 17.7 tokens per parameter. A mature XL checkpoint from the long
DFM6/DFM7/DFM8 lineage has seen hundreds of billions of tokens, so comparing
it directly with the current sub-epoch XXL checkpoint conflates capacity with
training maturity.

The first three XXL headline/suite points are:

| Metric | 50K | 100K | 150K |
|---|---:|---:|---:|
| Danish headline | 0.442 | 0.517 | 0.539 |
| English headline | 0.460 | 0.543 | 0.542 |
| Math/code headline | 0.434 | 0.488 | 0.438 |
| Standard suite | 0.415 | 0.530 | 0.559 |
| DFM suite | 0.492 | 0.587 | 0.614 |
| EuroEval suite | 0.436 | 0.484 | 0.464 |

This is not a broad plateau: standard and DFM continue to improve from 100K
to 150K, while English is flat and math/code and EuroEval are volatile. Expect
the first credible capacity separation on difficult benchmarks near the end
of epoch one or during epoch two. A defensible ceiling comparison needs at
least roughly 80--160B tokens (20--40 tokens per XXL parameter), corresponding
to about 305K--610K optimizer steps at the current GBS. This range is an
engineering forecast, not a scaling-law guarantee; the custom recurrent depth,
data changes, and aggressive constant LR can move the crossover.

## Intentional pause at step 175000

Update 2026-08-27: the step-161000 resume point above is superseded for future
continuations. Scheduler dispatch was soft-stopped, and the exact production
TorchRun process group was terminated only after
`fsdp2_ephemeral_step_175000/.metadata` and
`checkpoint_state_ephemeral_step_175000.json` were fully published. The
sidecar records step 175000, epoch 1, exact global row cursor 141196506,
world size 8, local batch size 8192, GAS 4, and `carry_policy=none`. All eight
GPUs were free after termination.

The existing scheduler plan remains stop-requested. Its
`campaign-train-200000` row has been reset to pending with attempt zero,
`resume_from_tag=ephemeral_step_175000`, and log directory
`logs/training/dfm8_XXL_1epoch/step_175000_to_200000`. No scheduler process is
running. To continue the established one-node path, clear the stop request and
restart the existing plan; do not create a replacement campaign.

The training row requests all eight GPUs and requires 178000 MiB effective free
memory on every GPU, so it will not collide with active DFM10 audit vLLM
servers. This is a headroom gate, not an audit-completion dependency: an audit
worker deliberately releases its GPU between retry attempts. Do not rely on
the gate to order audit finalization before training. For strict ordering,
start the scheduler only after the audit launcher exits successfully and
`logs/dfm10_folketing_audit_8gpu_vllm/final_summary.json` exists, or add an
explicit external-completion guard.

Update 2026-08-28: after the DFM10 audit released the GPUs, the scheduler
started the prepared continuation. It was intentionally stopped again during
startup/compilation before producing a newer checkpoint. The scheduler is
stop-requested with no running process, and `campaign-train-200000` is pending
at attempt zero, still resuming from authoritative
`ephemeral_step_175000`.
## Mimir resume from step 175000

Update 2026-08-28: the authoritative checkpoint is the fully written
`ephemeral_step_175000`, with eight DCP shards, checkpoint metadata, exact
batch state, and `carry_policy=none`. The repository and scheduler artifacts
were transferred from `/work/dfm/HRM-Text` to `/work/mimir/HRM-Text`. The
existing plan remains:

```text
logs/scheduler/dfm8_XXL_1epoch_steps50k_100k_persistent_vllm_20260725
```

Its structured TSV/JSON path fields were migrated under the plan lock from the
old repository root to the new root. The pre-migration backup is
`plan.tsv.before_mimir_root_migration_20260828`. Job IDs, dependency state,
attempts, and training commands were otherwise preserved.

A direct TorchRun probe from step 175000 reached only step 175025 and was
stopped after discovering that the transferred scheduler plan had become
available. W&B rejected those points because the existing run already had
history through step 175026, so the probe added no accepted training history
and produced no checkpoint.

The existing scheduler was then resumed with persistent vLLM. Its
`campaign-train-200000` row loads `ephemeral_step_175000`, stops cleanly at
step 200000, and retains the downstream 200K evaluation, 250K continuation and
evaluation, and epoch-one completion graph. The Rich scheduler monitor runs in
tmux window `hrm-0:eval-monitor`.

## Main Performance Update At The 200K Boundary

On 2026-08-29, `origin/main` through commit `7bf17c8` was merged into the
active `multinode` branch without stopping the old-code 178K-to-200K process.
That process had already loaded and compiled its modules, so it remains on the
established implementation through the 200K checkpoint. The pending
200K-to-250K command does not override the new PrefixLM implementation fields;
its fresh Python process will therefore inherit main's optimized FA4 defaults:
`seqused` routing, Triton gradient masking, and Triton output combination. It
also inherits `fsdp_wrap_policy=transformer_block`, preserving the production
FSDP topology. This creates an intentional implementation boundary at 200K;
compare post-resume step time only after compilation warmup.

## Learning-rate stability review at 200K

On 2026-08-29, W&B history for `DFM5/40j5y877` confirmed two distinct
instability episodes while both `bp_steps=5` and the learning rate remained
fixed at `4e-4`. The first contained 20 logged losses above 2.0 from steps
150665--150760 and peaked at 7.286. The second contained 96 such points from
steps 171080--171715 and peaked at 10.631; training accuracy briefly approached
zero during the event. The run subsequently recovered: over steps
190000--200000, mean loss was 1.090 and mean token accuracy was 0.751, close to
the pre-spike 140000--150000 windows.

Checkpoint evaluations are mixed rather than globally collapsing. HumanEval,
PIQA, the Danish citizen test, and English IFEval improve through 200K, while
BFCL tool calling, English HellaSwag, Life-in-the-UK, GEC-DaLA, and several
EuroEval metrics regress or remain volatile. This does not prove that learning
rate alone causes every evaluation regression, but the repeated transient
training instabilities make constant `4e-4` unnecessarily aggressive for XXL
at global batch 262144. The conservative continuation recommendation is to
lower LR to `3e-4` at a fully written checkpoint, retaining optimizer and EMA
state. Do not reset either state, and do not treat the LR change as a substitute
for resolving data-format or task-interference issues. No running job was
altered as part of this review.

The recommended recovery point is the latest fully written, healthy checkpoint,
not step 150000. Both instability episodes recovered, the 190000--200000
training window returned to its pre-spike loss and accuracy range, and several
200K evaluations improved. Replaying from 150K would discard useful training
without evidence of persistent state corruption. Resume the latest checkpoint
at `3e-4` with optimizer and EMA state intact. A separate 150K-to-200K replay at
`3e-4` is useful only as a controlled diagnostic fork, not as the production
continuation. Stabilize the current epoch now rather than relying on later
epochs to repair avoidable high-LR excursions.

## Production LR reduction from step 201500

On 2026-08-29, the scheduler and active `4e-4` training segment were stopped.
The newest complete source was `ephemeral_step_201500`; it contains all eight
DCP shards, metadata, and exact batch state with `carry_policy=none`. The
unsaved tail through approximately step 201565 was intentionally discarded.

The existing plan was updated under its advisory lock. The 201500-to-250000
segment and the remaining epoch-one segment now use `lr=3e-4`; completed
historical rows retain `4e-4`. Training resumed from step 201500 with optimizer
and EMA state preserved, `start_epoch=1`, and `skip_batches=806000`. W&B run
`DFM5/40j5y877` accepted the first post-tail point at step 201565 with
`train/lr=0.0003`, loss 1.1168, and token accuracy 0.7414. This verifies that
`update_lr` overrides the LR restored inside the optimizer state. The
coordinator, worker, Rich monitor, and training-log tail remain in separate
tmux windows.

Follow-up through step 214110 covers 2522 logged points after the LR change.
There are no non-finite metrics and no losses above 2.0. Mean loss is 1.0350,
mean token accuracy is 0.7611, and mean exact accuracy is 0.2585; over the most
recent 2000 steps these are 1.0282, 0.7623, and 0.2613, respectively. The
largest post-change loss is 1.2700. All eight GPUs remain fully utilized, no
CUDA/NCCL/runtime errors appear in the training log, the scheduler has no
failed rows, and `ephemeral_step_214000` is fully written. The longer window
supports retaining `3e-4` rather than reducing it again preemptively.

Follow-up on 2026-08-30 supersedes the implication that the post-change window
remained entirely excursion-free. A short event began at step 215165, peaked at
loss 7.319 and token accuracy 0.112 at step 215170, and included six logged
losses above 2.0 through step 215240. Metrics were still elevated through
roughly 215340, then recovered. No further loss above 2.0 occurred through step
223245. Over the latest 5000 steps, mean loss is 1.0306, mean token accuracy is
0.7618, and mean exact accuracy is 0.2598; there are no non-finite values.
Thus the run is currently healthy, but the LR reduction mitigated rather than
eliminated transient excursions. The event is much shorter than the 171K
episode and does not by itself justify another immediate LR reduction; retain
`3e-4` while treating any further comparable event as evidence for additional
stabilization, including consideration of conservative gradient clipping.

## Intentional pause at step 223500

On 2026-08-30, a scheduler stop request was placed just before step 223500.
Training was terminated only after `fsdp2_ephemeral_step_223500` contained all
eight DCP shards and its exact state sidecar reported `step=223500`,
`batch_in_epoch=894000`, and `carry_policy=none`. TorchRun and the cluster
coordinator exited, and all eight GPUs released their memory.

The existing `campaign-train-250000` row was reset under the plan lock to
resume from `ephemeral_step_223500` at `lr=3e-4`, with optimizer and EMA state
preserved. Its new log directory is
`logs/training/dfm8_XXL_1epoch/step_223500_to_250000_lr3e4`. The scheduler stop
request intentionally remains in place, so this pending row cannot launch
until an explicit clear-stop and coordinator restart.

## Gradient clipping from step 223500

On 2026-08-30, the two pending production training rows, targeting steps
250000 and 268857, were updated under the scheduler plan lock to set
`gradient_clip_norm=1.0`. Completed historical rows were left unchanged. The
pre-edit plan backup is
`plan.tsv.before_gradient_clip_1_20260830_065226` in the campaign directory.

On 2026-08-30, skip-before-moments protection was implemented after FSDP2
clipping itself was ruled out as malfunctioning. The active step-223500 to
step-250000 process was not interrupted and cannot acquire newly loaded code.
The pending step-250000 to epoch-1 segment was updated under the scheduler plan
lock with `gradient_skip_norm=1.0` and
`gradient_skip_max_consecutive=3`. A triggered step consumes its data cursor
but leaves parameters, optimizer moments/step, weight decay, and EMA untouched;
three consecutive triggers force a regular checkpoint and clean exit.

The stop request was cleared and the single-node cluster coordinator, local
worker, and Rich monitor were restarted. Training resumed from the complete
`ephemeral_step_223500` checkpoint with optimizer and EMA state preserved,
`lr=3e-4`, and clipping enabled. The live TorchRun command was inspected to
verify the override. By step 223505, all eight GPUs were at full utilization,
using approximately 156--159 GiB each, with no runtime, OOM, or non-finite
errors. The scheduler, monitor, and training log are visible in tmux windows
`hrm-6:3`, `hrm-6:4`, and `hrm-6:5`, respectively.

Threshold interpretation and the preceding non-W&B parity measurement are
documented in [Optional Global Gradient Clipping](/pages/model-architecture/gradient-clipping.md).

Follow-up through step 225455 covers 1,951 production steps and 391 W&B
measurements after clipping was enabled. Mean gradient norm is 0.1824, with
p95 0.2054, p99 0.3018, and maximum 0.4902. No measurement clipped and every
reported coefficient remained 1.0. Mean loss is 1.0284, maximum loss is
1.2319, and no logged loss exceeded 1.5. Mean token accuracy is 0.7618 and
mean exact accuracy is 0.2618. Training remains stable at approximately 2.79
seconds per step with no runtime, OOM, NCCL, or non-finite errors. This window
confirms that threshold 1.0 leaves ordinary updates untouched while retaining
headroom to constrain a substantially larger excursion.

On 2026-08-30, the run was deliberately rolled back from the small unsaved
tail to complete `ephemeral_step_229500` and clipping was disabled in favor of
`gradient_skip_norm=1.0`. The guard encountered a sustained high-norm region,
saved protected regular checkpoints at steps 229505, 229508, and 229528, and
stopped. The final diagnostic stretch skipped twenty consecutive batches with
norms ranging from 8.50684 to 1375.56. No automatic production retry remains;
the current boundary and policy implications are documented in
[Optional Global Gradient Clipping](/pages/model-architecture/gradient-clipping.md).

The production fallback then resumed from the untouched step-229500 state at
LR `2.5e-4`, norm-1 clipping, and no skip guard. Through step 229730, 41
five-step W&B samples have median loss 1.0726 and median gradient norm 0.2088.
Four sampled steps clipped (229695--229710), including raw norms 7752 and
117107, but the latest norm returned to 0.2131 and throughput remained about
2.8 seconds per step. This is contained but not fully quiet: continue watching
clipping frequency and the rolling loss rather than the outlier-dominated mean
gradient norm.

Follow-up through step 228045 supersedes the implication that the longer run
remained uniformly stable. A severe instability began near step 226230 and the
last clipped measurement occurred at step 227450. Across 910 post-resume W&B
measurements, 150 clipped (16.5%). During steps 226001--226500, mean loss was
3.565 and maximum loss 9.879; during 226501--227000, mean loss was 3.133 and
91% of logged updates clipped. The largest reported pre-clip norm was
3,659,649.75, for which the coefficient was approximately 2.73e-7. Clipping
therefore operated as configured and strongly bounded exceptional updates, but
did not prevent the model's loss and accuracy from collapsing during the
episode.

The run subsequently recovered without intervention. From 227501--228000,
mean loss was 1.053, mean token accuracy 0.758, maximum norm below 0.4, and no
updates clipped. The latest measurements through 228045 remain in that normal
range, and there are no runtime, OOM, NCCL, or non-finite errors. Do not infer
from recovery that clipping solved the underlying instability; it constrained
the gradients while the event ran its course. Further investigation should
correlate the onset with batches/data and recurrent execution state before
changing the threshold.

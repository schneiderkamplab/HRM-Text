---
type: Experiment
title: Transformer48 DFM11 causal baseline preparation
description: Compute-matched non-recurrent baseline recipe and preparation status.
status: draft
last_updated: 2026-11-09
confidence: high
---
# Transformer48 DFM11 causal baseline

The user selected one MTC v1.5 / DFM11 epoch, causal attention and
`data.target_only=false`, with LR 3e-4. The prepared recipe retains a 5,000-step
warmup followed by flat LR. Production has not been launched.

## Configuration

`scripts/run_transformer48_dfm11.py` composes the existing
`models/baselines/transformer_wrapper.py` implementation with the new
`config/arch/size/B_compute48.yaml`: 48 independent layers, hidden size 1024,
eight heads, SwiGLU intermediate size 2816. Backbone parameters are
666,894,336; with separate 262144-token embedding and output head the total is
1,203,765,248. This matches the 48 block applications in B H=2, L=3, not B's
number of independent parameters. Causal attention and full-token loss also
change the objective relative to B's PrefixLM/response-only setup.

The run uses eight B200 GPUs, FSDP, bf16 compute, fp32 parameter storage,
262144 tokens per global batch, accumulation 1, and `lr_auto=false` (the
module-specific automatic rates are HRM-only). It saves checkpoints every
50K steps and at epoch end; no automatic evaluation pauses are scheduled.
Existing HRM HF export must not be assumed compatible with TransformerWrapper.

The immutable sampled dataset is `data/sampled_dfm11`, with Gemma4 tokenizer,
4096 effective context and metadata total length 103,214,604,702. The displayed
393,732-step count is an estimate; dataset exhaustion defines epoch completion.
See [DFM11 portability](../dfm11-portability.md) for provenance constraints.

## Verification and launch status

Artifacts are under `logs/training/transformer48_dfm11_causal_20261109`.
Hydra resolved the production configuration successfully. A real ten-step
smoke was launched through the single recovery supervisor with W&B disabled,
separate checkpoint directory and all eight GPUs. At the latest inspection,
all ranks initialized; data workers and the independent sampled-index
preflight were blocked in shared-filesystem page reads. No optimizer step or
GPU memory/throughput result is claimed yet. Production launch requires a
`smoke-verified.json` receipt and a fresh production checkpoint directory.

Commands (from repository root, HRM environment):

```bash
python scripts/run_transformer48_dfm11.py config
python scripts/run_transformer48_dfm11.py smoke
# Only after successful verification and a request to launch:
python scripts/run_transformer48_dfm11.py train
```

## Related B final publication repair

B epoch 3 completed at step 1,538,766. The earlier final-checkpoint repair
correctly selected `epoch_3` for checkpoint loading, but incorrectly used that
same tag for saved inference artifact lookup. IFEval archives and EuroEval
results are under `step_1538766`. This supersedes the implication that changing
all tags to `epoch_3` completed publication preparation.

With the scheduler stopped and no claimed jobs, 11 remaining CPU publication
rows were corrected to `ckpt_tag=step_1538766`, retaining
`checkpoint_tag=epoch_3`. Database backup and before/after receipt are under
`logs/scheduler/B_dfm15_gemma4_epoch1_20261103/final-epoch3-repair-20261109`.
Runner14 resumed publication; the previously failed IFEval merge succeeded.
All 2,203 final-block jobs subsequently reached `done`; the administrative lock
is clear. Runner14 completed all remaining merges, averages and publication rows.
No inference was regenerated.

## User stop, 2026-11-09

The user requested stopping the smoke. Wrote `smoke-control/stop.request` and
terminated its resource-owning launcher, preventing automatic recovery. GPU
processes exited and GPU compute allocations cleared. Smoke verification is
incomplete; no production training was launched. Any residual data workers
blocked in kernel storage reads have termination pending.

## Production launch authorized, 2026-11-09

Superseding the preparation-only status above, the user requested that training
start once GPUs become free. The CPU preflight completed successfully (1,000
sampled index rows checked). The canceled GPU smoke remains unverified; it is
not restarted. The explicit `--allow-unverified-smoke` launch option records
this limitation rather than fabricating a verification receipt.

The detached command is `python scripts/run_transformer48_dfm11.py train
--wait-for-gpus --allow-unverified-smoke`; log:
`logs/training/transformer48_dfm11_causal_20261109/train.log`. A nonblocking
production-launch lock prevents duplicate arming. Before handing off, the
launcher resolves Hydra and matches the preflight configuration hash, checks
data/tokenizer/tool paths, and refuses an existing production checkpoint.
The existing recovery supervisor waits for no compute processes and at least
178000 MiB free on each of GPUs 0–7, then launches exactly one trainer.
Production uses a separate `control` directory; the canceled smoke's
`smoke-control/stop.request` remains intact. There is no second watcher or
recovery supervisor. Automatic evaluation pauses are still not configured.

The GPUs were already free: the supervisor launched production immediately.
All eight ranks entered epoch 1 and W&B connected to
`peter-sk-sdu/DFM5/transformer48-dfm11-causal-alltokens-epoch1`. Initial
optimizer-step/throughput verification remains pending.

## Step 100 suspension requested, 2026-11-09

The user requested suspension after 100 steps. Published `[100]` through
`training_suspend.controller request` to the active launch directory and set
production `control/hold` to prevent automatic resume. This is a cooperative
checkpoint-and-pause request, not termination. At request time the log still
showed zero completed steps and data workers waiting in shared-storage reads;
there was no valid measured per-step time to report. A hold does not itself
offload CUDA allocations; offloading requires a verified suspend-ready receipt.

## Startup stall diagnosis, 2026-11-09

Superseding the earlier startup interpretation: no optimizer progress was
reported after roughly twenty minutes, and the log stopped advancing at
13:34 CET. GPUs mostly reported 100% activity but zero memory activity and
about 200 W; ranks 6 and later 5 reported zero activity. Each rank retained
about 95696 MiB. Active ranks spent about one CPU core in autograd, while idle
ranks' autograd threads slept on futexes. Compile workers slept and no recent
Inductor cache output was found. These observations suggest a distributed
backward/communication stall, not sustained useful GPU compute. All data
workers also waited in `folio_wait_bit_common`, but this alone does not prove
storage is the cause of the active autograd stall. Python/kernel stack
inspection was denied by host permissions, including the sudo attempt, so
the exact blocked operation remains unconfirmed. No trainer restart or
configuration change was performed during this diagnosis; step-100 request
and hold remain in place. Evidence: `stall-diagnosis.json` in the run logs.

## User-requested restart, suspension canceled (2026-11-09)

The user requested stop/restart and explicitly revoked the step-100 suspension.
The old launcher and all its owned processes exited; GPU compute allocations
cleared before restart. There were no saved training checkpoints, only three
configuration/source metadata files, archived under `stalled-attempt-1`.
Restart uses the same training settings and W&B ID (`wandb_resume=allow`),
with `resume_trace=true` and NCCL diagnostic dump pipes for diagnosis.

The active supervisor root is now
`logs/training/transformer48_dfm11_causal_20261109/control-restart-1`, and the
log is `train-restart-1.log` in the parent directory. Its initial suspension
queue is empty and it has no hold. The old control directory retains its stop
request and historical step-100 request, but has no live supervisor.
`restart-command.json` and `restart-receipt.json` preserve the launch details.

At restart verification, another job occupied all eight GPUs (~68132 MiB
each). The new supervisor is waiting for GPU availability; new training ranks
have not launched yet. No other job was interrupted.

## Shared-GPU restart and progress monitoring (2026-11-09)

The user authorized use of available memory alongside the other GPU job.
The exclusive waiting launcher was stopped and replaced using an isolated
settings file with `allow_existing_peers=true`, `min_free_mib=110000`;
training geometry is unchanged. Active control is `control-shared-1`, log is
`train-shared-1.log`. The shared launch completed nine optimizer steps.
At 13:57 CET, seven ranks waited at step 10's supervised-count all-reduce,
while rank 2 had completed step 9 but not entered step 10 and its data worker
was in filesystem disk sleep. This is direct evidence of a data-feed straggler
for this pause, unlike the less conclusive earlier startup stall.

The user subsequently requested 50K CUDA suspend/eval/resume cycles. Boundaries
50000 through 350000 were included in the shared launch; no step-100 request
or hold exists. **Evaluation orchestration is still being prepared**, not yet
active: the current export assumes HRM recurrence and the vLLM adapter forces
PrefixLM prefill. Causal TransformerWrapper compatibility must be verified
before those evals can be run. A twenty-minute read-only sampler writes
`monitor-progress.jsonl` and `monitor-status.json` in the training log directory.

## DFM11 bulk cache warm (2026-11-09)

Following the user's request, launched `scripts/warm_sampled_dataset.py` on
`data/sampled_dfm11`, epoch 0. It reads four 1.8-GiB index files first, then
the shared 833-GiB token file sequentially through a reusable 16-MiB buffer.
Host MemAvailable was about 2.7 TiB, enough for these pages. No source files
are changed and training keeps its existing mmaps. This warms the reclaimable
filesystem page cache, not a pinned guarantee of residency. The shared token
file contains more than just epoch-0 references; the full pass avoids expensive
235-million-row range collection/sorting.

Progress and failures are in `cache-warm/status.json` and `reader.log` under
the run logs. `cache-warm/stop.request` requests a clean stop between reads.
Reads already blocked in the kernel may take time to return. Improvement in
training throughput is not yet verified.

## Step 40 pause for cache warming (2026-11-09)

The user requested a pause after step 40 so bulk reading can catch up.
Published step 40 to the active `control-shared-1` launch and set its root
hold, preventing automatic resume. At 14:22 CET all ranks completed optimizer
step 40, but `suspend_ready.json` was not yet present: final checkpoint/pause
completion remained pending. The bulk reader had read 5.44 GiB of token data
plus all four epoch-0 index files, and continues independently.

## Epoch-indexed cache warming (2026-11-09)

The user requested reading only epoch-0 references. Superseding the full-file
pass, stopped the original reader cleanly after 132,791,664,640 token-file
bytes (123.7 GiB). `scripts/warm_indexed_epoch.py` now validates and combines
instruction and response token ranges from all 235,520,711 epoch rows into
a union of 4096-byte file pages. This includes the NumPy header offset and
actual token dtype size, merges overlapping/adjacent pages, and reads selected
ranges in file order. It skips the completed prefix from the stopped reader.
Page alignment can include small unreferenced portions of selected pages; it
does not promise byte-exact sparse I/O or retained cache residency.

Range union logic passed 100 randomized brute-force comparisons and invalid
bounds checks. Planning and reading status is in `cache-warm-epoch0/status.json`
and `reader.log`; selected ranges are saved as `ranges.npy`. Source data is
unchanged. The step-40 suspension-ready receipt is now present and the user
hold remains active.

Indexed planning completed: epoch 0 references 399,740,091,068 bytes
(372.29 GiB) in 9,206,219 merged page ranges, versus
832.96 GiB for the full token file. The previous prefix covered
61.70 GiB of selected pages, leaving
310.59 GiB at indexed-read start. Selected-range reads
are now advancing. End-to-end synthetic verification also passed for sparse
reading, overlap deduplication and prior-prefix accounting.

## Resume from step 40 (2026-11-09)

The user requested resume while indexed warming continues. Removed the root
hold and published a generation-bound `restore.request`. This was the wrong
resume path for a quiescent-only pause: CUDA had not been offloaded, so the
controller failed on missing `generation_000001/offload.json`. The supervisor
verified the regular step-40 checkpoint, stopped only its owned workers and
performed disk fallback. New ranks loaded step 40 and entered batch/step 41;
optimizer, EMA and data-cursor resume settings were preserved. The old
step-40 suspension was consumed; future 50K boundaries remain.

Do not equate a suspend-ready receipt with a CUDA-offload receipt or request
CUDA restoration for a quiescent-only pause. For such a pause, use a validated
in-place resume-token path; current controller restore assumes offload.
Indexed cache warming was not interrupted.

## Visible I/O contenders, 2026-11-09

Read-only process sampling found the SmartEval analysis-only worker PID
348710 performing about 10,101 read syscalls/s and 39.44 MiB/s of logical
reads across a 20-second sample, matching a prior five-second sample. Its
open data files were `/work/dfm/smarteval/kineticeval.db` and
`kineticeval.definitions.db`. The SmartEval CPU-only worker was nearly idle.
The indexed cache reader managed only 0.3 MiB/s in that same interval, and
a training data worker remained in disk sleep on DFM11 mappings.

These are process logical I/O counters, not measured WEKA backend traffic:
`read_bytes` was zero even for the active bulk reader. They identify a busy
local reader but do not establish that it causes the DFM11 stalls. Other
WEKA clients are outside this process sample. No SmartEval process or file
was changed; the user's restriction against SmartEval changes remains.

Follow-up read-only SmartEval inspection found zero active runs and zero
running jobs, with 5,054 pending inspector jobs and five pending investigation
jobs attached to inactive runs. Its dispatcher log was empty. The on-disk
worker polls scheduling/claims even when no active work exists; thus the
observed read load appears to be idle queue polling, not executing an analysis.
Exact live stack was not obtained, and source may have changed since launch.

## Explicit host-memory suspension at step 6360 (2026-11-09)

User requested suspension to memory until an explicit resume command.
Set `control-shared-1/hold`, requested the next cooperative boundary, and
verified suspension at step 6360. CUDA checkpointing then completed for all
eight owned ranks; `offloaded.json` reports zero remaining owned GPU MiB.
The explicit hold remains and overrides the offload lease expiry. Resume must
remove the hold and restore this generation; do not launch another trainer.
The competing EuroEval job was not changed.

On the subsequent explicit user resume command, released the hold and
requested generation-bound CUDA restore. The same launch acknowledged resume
from step 6360 and progressed through step 6386, confirming in-place recovery
from host memory. No competing job was changed.

## Scheduler-first launch rule and completed eval schedule (2026-11-09)

The baseline was initially launched through the CUDA recovery supervisor
without an evaluation scheduler. The user explicitly identified this as an
operational error. **Production training must be launched through the eval
scheduler with the evaluation/offload/resume plan prepared first, unless the
user explicitly authorizes a scheduler bypass.** Permission to start training,
resume, or use shared GPU headroom is not that override. This rule is now in
`AGENTS.md`; the standalone recipe requires `--explicit-standalone-override`.

Superseding the earlier incomplete-eval status: the active plan is
`logs/scheduler/transformer48_dfm11_causal_epoch1_20261109`, authoritative DB
`/var/tmp/dfm-transformer48-evals/jobs.sqlite` (durable local overlay; tmpfs is
rejected by the store). It contains 17,632 jobs: seven 50K boundaries through
350K and the final `epoch_1` checkpoint, each with the 2,203-job B/DFM15
1.5M evaluation coverage plus a training boundary. The 393,732 final training
row target is an estimate; actual epoch completion is accepted via `epoch_1`
and its recorded step is bound to final evaluation metrics before dispatch.

The runner adopted the existing identity-checked launcher under
`control-shared-1/launcher.json`, rather than creating a second trainer. The
first row `transformer48-step_50000-train` is running. Boundaries save a disk
checkpoint, use cuda-checkpoint to offload the live trainer, run evaluations
and publication, then restore in place. Terminal-mode aggregate dependencies
release training even on evaluation failures. Future train rows have explicit
resume checkpoint tags. User holds are distinguished from scheduler-owned
eval holds and must not be cleared by the boundary handler. Shared-GPU eval
servers use 0.45 memory utilization; the competing EuroEval run is untouched.

### Causal serving verification

`conversion/convert_to_hf.py` now supports the prenorm/RoPE/causal wrapper as
a mathematically equivalent single H pass, zero L passes and zero initial L
state. The declared but unused L weights are zero-filled. Other transformer
variants are rejected. An isolated vLLM plugin constructs ordinary causal
attention instead of the installed HRM adapter's forced PrefixLM prefill;
only baseline jobs opt into this plugin. Global installed libraries are unchanged.

Verification: native-versus-HF logits, causal future-token invariance and
cached decoding passed; a real step-6360 EMA export loaded and generated
eight tokens through the vLLM adapter. The canary server was then stopped.
Nine scheduler/headroom/export regression checks passed (the initial SQLite
test on tmpfs failed the existing durable-storage rule; rerun on `/var/tmp`
passed). All 17,632 rows passed scripts/path preflight. Historical unavailable
data limitations of the B evaluation suite still apply; a path preflight is
not a certification of dataset content or benchmark success.

### Monitor

`hrm-20:8` now monitors the baseline SQLite plan, not the old B plan or standalone
EuroEval. An adopted train row had no scheduler log directory, so the monitor
initially displayed unknown progress. The monitor now reads the explicit
cooperative `training.log` in that case, never the implicit working directory.
Future rows have distinct log directories. Verified live display: step
13365/50000, 26.7%, with ETA. Training and external EuroEval processes were
not restarted to fix the display.

### 2026-11-09 CUDA crash and scheduler recovery

The live-status observation above was superseded at 17:19 UTC: workers aborted
with `CUDA error: unspecified launch failure` during step 13658. The log does
not identify the underlying kernel or cause. Latest saved recovery state is
`ephemeral_step_13500`, limiting rollback to about 158 steps. External EuroEval
workers were left untouched.

Recovery exposed missing `ckpt_tag` metadata on train rows (adoption of an
already-running trainer had bypassed that check). Added target checkpoint tags
to the database and plan builder, and explicit first-row resume from 13500.
The dead-launch guard now supports explicitly recorded, identity-validated
peer processes; unknown GPU workers still block a duplicate launch. The
launcher retains its configured free-memory gate. Backed up the SQLite DB
before resetting failed train rows and prematurely completed administrative
rows. Cooperative-training tests: 2 passed using `PYTHONPATH=eval_scheduler:.`.
A repository-root invocation without that path failed collection, not a test.
The CUDA root cause remains unresolved; restart success must be verified from
new optimizer progress, not merely a running scheduler process.

Recovery verified: all eight ranks loaded step 13500 and completed new optimizer
steps; the trainer advanced through 13558 into 13559. The scheduler owns the
50K training row, with 17,631 later rows pending. This confirms restart, not a
root-cause fix for the unspecified CUDA failure. Scheduled 50K evaluation and
CUDA offload/resume remain enabled.

### First 50K evaluation: execution completed, publication failed

Subsequent status inspection found all 1,045 evaluation execution rows marked
`done` (667 DFM, 32 DFM IFEval, 259 EuroEval, 2 batched IFEval, 85 standard).
This does not establish complete metric publication: 699 DFM result exports,
261 EuroEval merges and 8 standard merges failed. Nine averages and the report
remain pending. A sampled standard merge failed with FileNotFoundError for
`logs/eval/transformer48_dfm11_causal/step_50000/standard_shards/MATH/MATH_shard_0_of_64.log`.
Full 50K W&B sync is therefore not confirmed and must not be reported as
successful. Training continuity worked: the 100K training row is running and
optimizer progress was observed at 53,646. Publication requires separate repair;
no training interruption was performed during this status inspection.

### Publication-path repair

Root cause: assigning a distinct scheduler receipt directory to every cloned
row broke the existing artifact contract. DFM inference/export and EuroEval
inference/merge must share their result directory; standard shard merges also
resolve a common benchmark directory. The plan builder now preserves the
source plan's mapped artifact directories. Additional multilingual, extension,
Andersen and wave34 roots are explicitly namespaced to this baseline, avoiding
inherited experiment paths.

`scripts/repair_transformer48_publication_paths.py` backs up SQLite, briefly
fences dispatch, preserves the running training claim, links existing outputs
into the intended directories, repairs future row paths, retries failed 50K
publication, and releases the fence in `finally`. Completed inference is not
rerun. Validation checked 7,680 inference/publication directory relationships
and all 85 first-boundary standard input logs. First EuroEval publication logs
show successful W&B sync; aggregate completion is checked separately below.

Publication recovery outcome: all evaluation, export, merge, nine average and
report rows completed (2,203 rows done); only the redundant GPU teardown is
pending while training owns GPUs. Concurrent per-task W&B uploads initially
hit per-run HTTP 429 limits. Stopped only the 124 baseline publication commands,
completed 50K merges locally, then used
`scripts/publish_transformer48_checkpoint.py` to publish 3,441 numeric metrics
from 441 validated merged artifacts in one transaction. Future checkpoint
publication remains enabled; the four task-merge/publication scripts now use
the existing per-run writer lock to serialize W&B resume/log/finish sections.

All nine average logs contain successful sync receipts. The bulk receipt and
remote verification are under the plan directory as
`publication-step_50000.json` and
`publication-step_50000-remote-verification.json`. The active trainer overwrites
the W&B summary view with training keys; verify evaluation history instead.
Unfiltered history scans returned only a subset of columns; explicit-key
history queries are necessary to verify every uploaded metric. Targeted tests:
5 existing merge/compatibility/root tests and 3 new bulk-publication tests pass,
including rejection of unfinished merges and mismatched checkpoint tags.
Training continued throughout and was observed beyond step 55,874.

Remote explicit-key verification passed: all 3,441 metrics match at W&B
history step 55,854, with zero missing or differing values.

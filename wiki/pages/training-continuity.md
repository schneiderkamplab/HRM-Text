---
type: Policy
title: Training Continuity Across Evaluations
description: Evaluation and administrative failures must not strand the next training segment.
status: stable
confidence: high
last_updated: 2026-11-10
tags: [training, scheduler, operations, recovery]
---
# Training Continuity Across Evaluations

## Evaluation Memory and Stall Prevention (2026-11-10)

The DFM11 B run lost roughly 3½ hours at its first 50K evaluation because a
blanket utilization increase reserved 95% of GPU memory for the generator
while judged tasks additionally required 16,384 MiB. On a 183,359 MiB GPU,
that combination cannot fit. Repeated transient-capacity deferrals hid the
configuration error, left GPUs idle, and held training at its checkpoint.
The earlier ETA assumed a normal evaluation pause and was invalidated.
See the [incident and verified recovery](current-state/2026-11-10-dfm11-architecture-comparison.md#50k-evaluation-stall-incompatible-target-plus-judge-budget).

Mandatory operating rules:

- Budget all co-resident models before dispatch. Check
  `ceil(total_MiB * generator_utilization) + judge_reserve_MiB` against total
  capacity, then check available memory including other resident allocations
  and safety headroom. Recalculate when hardware or judge models change.
- On this B200 setup, use 0.95 for generator-only evaluation and 0.85 for the
  generator when a local judge reserves 16 GiB. Preserve calibrated task
  batches. Temporary co-tenancy overrides must not become plan defaults.
- Reject impossible total budgets as configuration errors. Reserve transient
  retries for genuinely temporary occupancy; repeated deferrals with idle GPUs
  require investigation, not another indefinite wait. Keep failure evidence
  and use bounded failure/recovery paths so evaluation errors do not strand
  training. Never classify missing evaluation results as successful.
- After a handoff or resource change, verify actual inference requests or
  completed-example progress and live GPU activity. A healthy HTTP endpoint,
  running job status, or launched PID alone does not establish useful progress.
- Five minutes without useful progress while runnable work exists is an
  operational investigation threshold. Check startup logs, memory accounting,
  repeated deferrals, administrative locks and dependency failures immediately.
  An explicit user pause is not a stall. A documented long compilation still
  requires inspection and a truthful status update.
- Update the ETA when a pause exceeds its allowance; do not carry forward an
  estimate based on normal evaluation duration after observing a stall.
- Drain affected requests before replacing persistent servers, edit only
  unclaimed definitions, release administrative fences, and verify work starts
  again. Resume training only after GPU/checkpoint safety checks and in
  accordance with the user's requested schedule.

Implementation status: `shared_pool.py` now raises a configuration error when
the required combined allocation exceeds total capacity; the regression test
and ten existing shared-pool tests pass. The running scheduler received repaired
job metadata; the new code guard loads on its next launch. The five-minute
threshold is an agent operating rule, not a claim that an automated watchdog
has been installed.

## DFM14 Final Evaluation and Archive Check (2026-10-17)

The final DFM14 checkpoint is step 3,768,319 (`epoch_1`). Direct SSH checks
found neither its DCP directory/state nor its HF export in the destination
`/work/dfm/HRM-Text/incoming/mimir-xl-20261015` archive. The archive watcher
remains active in its earlier log-copy phase; final catch-up waits for DFM15
step 3,800,000. Do not claim the final checkpoint has already transferred.

Final inference has completed, but the Talemaader successor average failed
with `Talemaader v2 sidecar checkpoint mismatch`; eight downstream jobs are
pending. Training proceeded independently. A read-only computation
of the complete final 50-language population gives 0.7831327538598646.

Final HumanEval's logged 16/164 (9.76%) is not a reliable capability comparison:
the saved Inspect logs contain 138 verification timeouts, nine assertion
failures and one other failure. At 3750K the same logs show 129/164 correct,
33 assertion failures and two other failures, with no verification timeouts.
Reverification of the saved final responses is needed before interpreting its
code and aggregate scores. No evaluation or W&B results were changed by this
read-only comparison.

### HumanEval Recovery (2026-10-17)

The timeout-dominated result above is superseded by CPU-only reverification:
**126/164 = 76.829268%**, zero timeouts, versus 129/164 at 3750K. All 164
saved model outputs were preserved exactly; extraction, tests and the 30-second
verification timeout were unchanged. Corrected Inspect archives and EEE exports
were published, and the existing merge/sync command updated the original XL run.
Original archives, source SHA256s and per-shard receipts are retained under
`logs/repairs/humaneval-dfm14-final-20261017`.

`dfm-evals/dfm_evals/tasks/code.py::verify_sanitized` now limits simultaneous
verifications to two per scorer instance, separately from model request
concurrency. Waiting for a slot occurs before the execution timeout. The replay
utility is `scripts/reverify_humaneval_saved.py`, run with `dfm-evals/.venv/bin/python`
and that environment's `bin` prepended to PATH. It intentionally uses the same
previously approved local execution backend, not a security-isolated sandbox.
No model server or inference requests are involved. Original local verification
can still be affected by filesystem stalls or genuinely looping generated code;
the concurrency guard is a mitigation, not proof all timeout causes are removed.

Transfer inspection found the archive rsync in `logs/dfm_evals`, about 9.15GB
sent after 5.5 hours, intermittently in uninterruptible filesystem-read wait.
The eight parallel checkpoint streams had already finished their initial pass;
the current log-copy phase is one rsync process. This is not an active bandwidth
cap. Remote checkpoint state markers were present through step 3,750,000.

## XL Archive Before Machine Pause (2026-10-15)

### Recovery Update (2026-10-17)

The final-average blockage described above is superseded: all nine final DFM14
average jobs completed after the Talemaader merge was regenerated with explicit
step 3,768,319. The merge writer previously omitted `step`, making a local
`epoch_1` tag impossible to bind to fractional epoch 11.812711203938841.
The writer now retains `--step`; the checkpoint-validation guard remains intact.
Corrected HumanEval feeds Math & Code 0.747481091527765 and the legacy DFM suite
0.7321229144548059. Remote history was checked and stale average-only summary
values submitted for repair; training keys were not intentionally changed. A
fresh API read still returned older summary values after successful updates,
consistent with concurrent writers restoring stale summary state. Treat history,
not the run-summary sidebar, as authoritative while training remains active.
Do not claim the summary repair persisted. The attempted repair receipt is
`logs/repairs/humaneval-dfm14-final-20261017/average-summary-repair.json`.

Deferred rebuild is scheduled with `scripts/rebuild_xl_summary_after_training.py`.
It waits for the complete 3.8M checkpoint, absence of same-run command-line
writers, and two minutes of unchanged remote history. It reconstructs evaluation
summary values from recent history plus the correction receipt, writes no history,
and verifies the remote summary after another minute. Log and verified receipt:
`logs/repairs/humaneval-dfm14-final-20261017/deferred-summary-rebuild.{log,json}`.
This is a detached watcher and must be relaunched after a machine reboot.

The 3.8M EMA campaign is appended to the same SQLite plan by
`scripts/schedule_dfm15_xl_evaluation.py`: 2,203 rows, including all 50 languages,
standard/DFM/EuroEval, Andersen, exports, merges, and nine average jobs. Existing
batch sizes, judge settings, and no-Mistral-fix tokenizer policy are retained.
Every inference job explicitly depends on the new EMA export; the complete
checkpoint wait depends on the existing 3.8M training job. The export wrapper
finalizes downstream fractional epochs as the final DFM14 epoch plus the actual
DFM15 checkpoint row cursor divided by epoch-0 source row count. No new W&B run.
The deferred summary watcher now also waits for this campaign to become terminal.

Early DFM15 training check (through 3,770,075): at base LR 1e-5 the first
roughly 1,750 steps are stable but not evidence of an evaluation improvement.
DFM14 3.760M-to-end mean loss/accuracy/exact accuracy: 0.7290/82.72%/48.46%.
DFM15 3.769M-3.770M: 0.7341/82.70%/48.23%. These use different data mixtures;
use the scheduled 3.8M evaluation to judge the extension's capability benefit.

Archive priority now puts current XL checkpoints and resume data ahead of bulk
logs and evaluation exports. With `--watch-final`, both the initial and final
resume-only passes precede the full archive pass. Data rsync uses
`--link-dest=/work/dfm/HRM-Text` to reuse identical destination files without
duplicating their storage. Never combine this with `--inplace`. The remote
DFM14 token store matches local size and mtime (1,023,554,655,344 bytes).
Remote DFM15 under `data/dfm15/native-reasoning-v2/sampled_dfm15` is an older,
smaller mixture (134,359,356,757 tokens/epoch); it is NOT interchangeable with
the current 134,516,139,170-token DFM15 sample and must not be silently reused.

`scripts/archive_xl_to_sdu.py --watch-final` runs detached and archives to
`ucloud@ssh.cloud.sdu.dk:6781:/work/dfm/HRM-Text/incoming/mimir-xl-20261015/`.
Port 6768 was superseded by 6781 on October 17 after reconnection. The new
endpoint's ED25519 key matches the previously trusted key; the transfer uses
`HostKeyAlias=[ssh.cloud.sdu.dk]:6768` to retain strict verification.
It never deletes destination files or modifies either host's training plan.
The receiver owns continuation planning and absolute-path remapping.

The initial pass transfers code/submodule working files, a Git bundle and diff,
a consistent SQLite scheduler backup, local standard/DFM/EuroEval results,
training/scheduler logs, HF exports, the DFM14 sample including its token store,
tokenizer, manifests and published regular/epoch checkpoint payloads. Rotating
ephemerals, live SQLite files, sockets and locks are excluded. Sharded checkpoint
selection requires the state marker and DCP `.metadata`. Archive files are not
ready to use until the corresponding phase receipt is present; rsync verifies
transferred bytes but no independent full-archive hash is claimed.

Superseded on October 16: the original single stream was capped at 200 MiB/s.
The owner requested faster XL checkpoint transfer. The archive now uses eight
disjoint checkpoint-file streams capped at 1 GiB/s each, prioritizing current
DFM14 XL, then other XL checkpoints, then evaluation/data artifacts before
historical non-XL checkpoints. Actual throughput remains storage/network-bound;
the old measured single-stream rate was only 8.5 MiB/s. No checkpoint payload is
assigned to two streams. Failed transfers retry after five minutes.
Later on October 16, at the owner's request, removed the bandwidth cap
entirely for both initial and final passes. Restarted with eight concurrent
checkpoint streams, distributing outstanding bytes across 32 disjoint work
units so finished streams pick up later units. Remote size/mtime checks guide
balancing only; rsync still performs its own checks and transfer validation.
Existing completed files and partial-transfer data are retained.
The initial October 15 copy reached about 25 GB of evaluation files but spent
hours reading historical vLLM compiler caches. The revised transfer prioritizes
checkpoint payloads before logs and excludes vLLM/Triton/Inductor caches.
Historical log symlinks are preserved rather than dereferenced; dangling links
do not represent locally available results and may need receiver-side remapping.
After the initial pass, the watcher waits for the final DFM14 epoch checkpoint
at step 3768319 and terminal final-checkpoint evaluation/postprocessing rows,
then repeats the transfer. Failed or pending final evaluation rows deliberately
prevent a final-complete receipt. The DFM14 epoch starts at step 3250000.

Progress: `logs/transfers/xl-20261015/transfer.log`; PID in the neighboring
`pid` file. A host reboot requires relaunching the command. To explicitly run
another catch-up pass after all work completes, use
`python scripts/archive_xl_to_sdu.py --final` (exclusive transfer lock prevents
two writers). This is an archive, not an automatically runnable remote plan;
in particular sampled metadata references a tokenizer outside the source repo,
also copied to `transfer-state/tokenizer.json` for remapping.

## Contract Checks, Not Whole-Code Locks (2026-10-15)

### Rearm Terminal Gates After Recovery

On October 15, terminal barriers for future XL evaluations were already `done`
because an earlier failed training ancestor had made those evaluations
unreachable. Resetting the ancestor made evaluations runnable again without
invalidating cached barrier completion. `SQLiteJobStore.update_jobs()` now
rearms completed terminal barriers whose dependencies are no longer terminal
or unreachable, including downstream barriers, in the same transaction.
This affects administrative edits, not every request or scheduler poll.

`scripts/repair_xl_continuation_gates.py` repaired the live 3750K and final-epoch
continuations under a short administrative lock, with a database backup.
Each gate now directly covers all 1046 preceding-checkpoint inference jobs,
not CPU merges/publication. Eleven stale barriers (including judge-ordering
barriers) were rearmed. Current training was not restarted.

A disposable database simulation confirmed: pending inference blocks the next
training segment; terminal failed inference permits the gate and continuation;
unfinished publication is not required. The launch preflight passed for all
three remaining training rows. Focused store/cooperative/safeguard tests passed
(56), as did runner/continuation/suspension tests (66). The active scheduler
reads repaired dependencies directly from SQLite; the new administrative reset
code is picked up by newly invoked maintenance processes, without restarting
the current coordinator. GPU release, completed resume checkpoints, original
W&B identity and explicit pause requests remain mandatory.

**Supersedes mandatory Python/shell hash matching in the DFM12/13/14 XL
continuation wrappers.** Two routine code updates caused unattended training
outages. `utils/training_safety.py` now treats `.py`/`.sh` hashes as provenance:
print the changed paths and append old/new hashes to `code-provenance.jsonl`,
without rewriting the approved hashes or blocking training. Audit-log write
failure is also warning-only. Non-code pins (configuration/data), prepared
budget contracts, checkpoint completeness, resume selection and GPU safety
remain hard checks. This policy does not weaken dataset/audit release gates.

The DFM14 launch checks the generated command's dataset, architecture selection,
batch/GAS, epoch budget, checkpoint destination, W&B identity and approved LR
schedule. Equivalent numeric LR spellings are accepted. This validates the
launch contract, not arbitrary code's numerical equivalence; tests remain
necessary when changing training mathematics.

After changing future training rows or launch code, run this CPU-only preflight:

```bash
python scripts/schedule_dfm14_xl_handoff.py preflight \
  --plan-dir logs/scheduler/dfm12_XL_epoch11_noidentity
```

It validates active/pending commands, including the frozen cooperative-launch
commands, without requiring not-yet-created checkpoints or starting workers.
It passed for 3700K, 3750K and epoch end on 2026-10-15. The 97 targeted tests
covered benign code changes, real contract failures and suspension recovery.
Running training was not restarted. Do not auto-reset arbitrary failed jobs or
silently alter LR/data/GAS to get past a genuine contract error. The existing
suspension supervisor's bounded, verified disk fallback remains in place.

## Optimizer Step Versus W&B History Cursor (2026-10-14)

For the XL DFM14 continuation toward 3650K, the live log and monitor agree.
A simultaneous W&B API check reported `train/step=3632735` but
`_step=3635238`: the history cursor is 2503 ahead of the optimizer.
`utils/training_wandb.py` intentionally preserves append-only history with an
offset on resume; this offset never enters training state. Use `train/step`,
not W&B's generic Step axis, for optimizer-step comparisons. Do not change
checkpoint boundaries or advance training to reconcile these two counters.

Superseded later on 2026-10-14: the DFM5 workspace `3fvncok3gjh` used `train/step` for its five explicit
history-step panels and its history-step defaults. Explicit epoch axes and run
selections were preserved. Reapply idempotently with
`python scripts/patch_workspace_optimizer_axes.py`; it backs up the live view,
checks for concurrent edits and verifies the saved specification.

The axis-only migration was reverted after the user reported a historical gap.
API samples confirmed `train/step` exists at 1.2M, is null at 2M and 3M, and
exists again at 3.2M. Training metrics themselves remain present. The previous
`_step` axes were restored without changing other workspace settings. Do not
reapply the axis script until historical optimizer-step coverage is repaired;
the current history-counter offset remains a display limitation, not a change
to the optimizer or checkpoint schedule.

### XL Historical Axis Repair Prepared (2026-10-14)

`scripts/repair_xl_training_axis.py` prepares missing-axis observations without
sampling. `logs/wandb_axis_repair/xl-20261014/prepared.json` records 227559 rows:
201309 each for loss, accuracy, exact accuracy and LR, and 207429 BP observations.
Existing explicit axes are left alone. The old logger used
`wandb.log(..., step=train_state.step)`; missing historical coordinates recover
from `_step`, not a constant offset. Unexpected missing coordinates at or beyond
3.2M abort preparation.

Publication is scheduled after the active 3650K segment exits via a scheduler
soft stop; it must not compete with the live training writer. The watcher
preserves subsequent user stop requests and restarts the same SQLite scheduler
after publication, even if verification fails (axes stay unchanged on failure).
It appends corrected observations to the same run, restores the latest training
values, verifies per-metric coverage, and only then switches axes. Original rows
and evaluation metrics are not deleted. This is queued work, not completed
publication. Watcher log: `logs/wandb_axis_repair/xl-20261014/watcher.log`.

## Mandatory Rule

### XL 3700K Recovery (2026-10-15)

The 3650K evaluations completed, but the 3700K training row failed the handoff
pin check: extracting the suspension finalizer changed the script without
refreshing its approved hash. The prepared suspension metadata had also not
been applied. After inspecting the sole changed pin, backed up the receipt,
refreshed that script's hash, reset only the failed training row, and applied
`scripts/prepare_checkpointable_xl.py --after-step 3650000`. Three future rows
now use the managed launcher with suspensions at 3700000 and 3750000, retaining
the original LR schedule, checkpoint directory and W&B run. Local two-GPU
normal and injected-failure smoke tests passed exact model/optimizer/EMA parity
in `/work/mimir/tmp/suspend-xl-local-validation-20261014/result.json`.
The new log is `logs/training/dfm14_XL/cooperative-after3650k/training.log`.

Separately, the axis repair uploaded but its coverage check returned exactly
30000 rows per metric instead of the expected totals. It did not switch axes;
the watcher correctly resumed evaluation anyway. Investigate pagination before
retrying publication: do not blindly upload duplicate historical observations.

2026-10-12 resume: after the isolated full-size suspension experiment,
restarted the existing SQLite scheduler plan
`logs/scheduler/dfm10_XL_epoch9_20260831` (database
`/tmp/dfm14-xxl-wide-production/jobs.sqlite`). Row
`xxlw-dfm14-train-1000000` resumes `ephemeral_step_991000` from
`checkpoints/dfm14/XXL-wide-from-dfm13-step870000`, stopping at 1M.
The original production environment, BP8, LR settings and W&B
`DFM5/dfm10-xxl-wide` are retained; experimental NCCL preload/library overrides
are absent. New log, preserving the previous attempt:
`logs/training/dfm14_XXL_wide/to_1000000_from_991000/train_until_step_1000000.log`.
Checkpoint loading and progress beyond 991000 were verified. The experimental
suspend path is not enabled in production.

User instruction, 2026-10-11: training must remain able to resume regardless
of evaluation failures or unfinished merges, averages, reports and W&B syncs.
Those CPU/publication operations must not be success dependencies of training.
Retain their work for later completion; never fabricate successful results.

Explicit user pauses still take precedence. Resume only from a valid completed
checkpoint, with the required GPUs safely available. Do not overlap training
with incompatible inference processes or terminate unrelated GPU workloads.

## Handoff Requirements

Operational pause 2026-10-12: user stopped DFM14 XXL-wide at 991K. The complete
`ephemeral_step_991000` in
`checkpoints/dfm14/XXL-wide-from-dfm13-step870000` was verified and hard-link
preserved under `/work/dfm/tmp/dfm14-xxl-wide-stop-991000-20261012` before the
training process group was interrupted. A few steps beyond 991K had already
run; those unsaved steps are not part of the resume checkpoint. Scheduler
`logs/scheduler/dfm10_XL_epoch9_20260831` has `stop.request`; no automatic
resume is authorized. On the next requested resume, update the interrupted
1000K segment's source from step_950000 to ephemeral_step_991000 before reset.

- Gate training on safe completion/termination of GPU evaluation activity and
  release of owned servers, not successful benchmark scores or publication.
- Failed, cancelled or retry-exhausted inference must have a recovery path
  that releases resources and permits training; blocked descendants must not
  make the training dependency graph permanently unsatisfiable.
- Merges, averages, synchronization and reports may finish later on CPU.
- Administrative locks are short-lived editing tools, not unattended pauses.
  Release them in failure cleanup as well as on success. Never end a turn or
  leave monitoring with a lock held unless the user explicitly requested it.
- After editing a live plan, verify lock/stop state, the next training row's
  dependencies, teardown, and actual training progress. A pending row or a
  live scheduler process is not proof that the handoff works.
- Future scheduler safeguards should include owned, expiring edit leases and
  an independent stale-handoff alarm/recovery path. These are requirements,
  not claims that the current implementation already provides them. Never
  blindly override an explicit user pause or an active edit transaction.

## Incident and Supersession

On 2026-10-10 the final scheduled 950K inference finished at 22:31:40 CEST.
An administrative lock left enabled during cross-machine reconciliation
prevented pending publication, teardown and the next training segment from
being claimed. At 05:41 CEST on 2026-10-11, eight GPUs had been idle for about
7 hours 10 minutes, approximately 57 GPU-hours. This was an operational error,
not a requirement to wait for more evaluation results.

This policy supersedes any interpretation of earlier campaign-wide barriers
that requires merges, averages or syncs to complete before training can resume.
Documentation alone does not repair existing dependencies or implement leases;
live plans and scheduler behavior must be verified separately.

Related: [evaluation baseline](dfm14-evaluation-baseline.md) and
[SQLite scheduler runbook](model-architecture/request-shared-eval-scheduler.md).

## GPU State Offload Candidate (2026-10-11)

Update 2026-10-12: an isolated [cooperative suspension prototype](cooperative-cuda-suspension.md)
now exists. Short-context XXS tests passed on one GPU and on two/eight GPUs
with test-only NCCL compatibility flags, including compiled eight-rank exact
parity. Default two-rank NCCL offload stalled. This does not establish safety
for the production workload or authorize migration. Further 2026-10-12 tests
narrowed the workaround to disabling device cuMem and NVLS only; compiled
eight-rank XXS passed two 15-minute offloaded pauses with exact parity and
zero owned GPU memory throughout. Default NCCL, full-size and multi-hour
production suspension are not validated by this result.

Local B200 driver verified as 610.57.04. NVIDIA's
[cuda-checkpoint documentation](https://github.com/NVIDIA/cuda-checkpoint)
describes device-memory offload to driver-managed host RAM, release of CUDA
GPU resources, and restoration into the same running process. Driver 610
adds cuIpcGetMemHandle IPC support with job-aware launch setup; this does not
prove our eight-rank NCCL/FSDP workload can be suspended safely.
Neither cuda-checkpoint nor criu was found on the inspected shell PATH.
At the original 2026-10-11 inspection no suspend/restore experiment had been
performed; the isolated 2026-10-12 results above supersede that observation.
Production was not altered.
Before adopting it, test collective quiescence, rank coordination, watchdog
timeouts, memory capacity, numerical continuity and recovery on a disposable
multi-GPU workload. CPU threads are not suspended by cuda-checkpoint itself.

### Isolated test installation (2026-10-12)

The earlier PATH observation is superseded for the newly created test env:
`/home/ucloud/miniforge3/envs/cuda-checkpoint-test`.
Activate with `conda activate cuda-checkpoint-test`.

- NVIDIA cuda-checkpoint 610.57.04, official x86_64 binary pinned to upstream
  commit `00d5cce84c628088d6caa203fc4af40c1538b6f7`.
- CRIU 4.2.1, source tag v4.2.1, commit
  `9539417f3e3cfa4eb84c319cd71f4d52f1f08645`, built with eight CPU jobs.
- CRIU CUDA plugin installed at `$CONDA_PREFIX/lib/criu/cuda_plugin.so`.
- Neither CRIU nor libnet was available from conda-forge. Conda supplies
  Python 3.12, make, pkg-config, c-compiler, protobuf-c, libnl and libcap.
  libnet 1.3 was built from its official release into the same prefix.
- CRIU build source: `/work/dfm/tmp/criu-checkpoint-test-src`; libnet source:
  `/work/dfm/tmp/libnet-1.3`. The CRIU protobuf descriptor generation rule
  was patched to use `pkg-config protobuf --variable=includedir` instead of
  `/usr/include`. A prefix-local `include/google/protobuf-c -> ../protobuf-c`
  compatibility symlink supplies the old header path CRIU expects.
- Build/install targets: `make -j8 criu cuda_plugin`, then
  `make install-criu install-cuda_plugin`, both with
  `PREFIX=/home/ucloud/miniforge3/envs/cuda-checkpoint-test` and
  `SBINDIR=/home/ucloud/miniforge3/envs/cuda-checkpoint-test/bin` inside the env.
- Optional setproctitle, AMD plugin, GnuTLS and nftables support were not built.
  No system package, driver, training environment or scheduler change was made.

Verified `cuda-checkpoint --help`, `criu --version`, and dynamic dependencies
for CRIU and its CUDA plugin (no missing libraries). This verifies installation,
not kernel/container permissions or actual process restore. No CRIU kernel
probe, process dump, GPU suspension or NCCL round-trip was attempted.

## Plan-Store Backup Policy (2026-11-04)

- **Cadence**: the database runner backups the authoritative SQLite store every
  ≤60 s (`DatabaseRunner._backup`, rate-limited; forced at clean drain) to
  `plan_dir/state.backup.sqlite`. The plan directory lives on `/work`
  (persistent wekafs), so even though the live store sits under `/tmp`
  (ephemeral overlay, see `database.json`), a container death loses at most
  ~60 s of state.
- **TSV mirror**: since 2026-11-04 `_backup` also atomically exports
  `plan.snapshot.tsv` on the same cadence (`store.export_tsv`; failure is
  logged as `TSV_EXPORT_FAILED`, never fatal). Before this, the TSV was only
  refreshed on idle runner cycles and drifted during training legs. Applies
  from the next runner start; refresh manually with
  `python -m eval_scheduler database export --database <db> --output <path>`.
- **Manual backups belong on /work**: pre-surgery backups (e.g. the epoch-2
  flip's `jobs_flip_*`) and historical snapshots live under
  `logs/scheduler/<PLAN>/backups/`. `/tmp` copies are scratch only.
- `plan.tsv` is the frozen import source, not a backup; never regenerate it.

### GPU-only training gates (2026-11-10)

Supersedes the older requirement to wait on terminal publication aggregates:
training depends only on completion/terminal failure of the preceding block's
GPU inference and HF-export work (plus its checkpoint wait). CPU result
exports, merges, averages, report generation and W&B sync must proceed
concurrently with the next training interval. They keep their own correctness
dependencies; removing them from the training gate does not mark them done or
waive publication verification. The runner drains persistent GPU servers before
claiming training, and can dispatch CPU publication while the training lease is
active. Never use teardown/barrier rows as gate anchors.

The DFM11 comparison originally gated training on almost the entire prior
block. After all 1,045 B50K inference jobs completed, that unnecessarily held
GPUs idle during publication. Repaired all 12 pending continuation gates in
the live database and both plan builders; preserved the active CPU claims and
publication dependencies. A durable SQLite backup precedes the edit.

A second dispatch issue surfaced during that repair: the first ready exclusive
row was a redundant teardown, so the runner waited for CPU publication rather
than selecting ready training. Ready training now takes priority over teardown;
its existing `shared_pool.close_all()` drains/releases persistent GPU servers
before the training claim. The live plan's pending train positions were moved
ahead of teardown rows without changing active claims. Verified `VLLM_STOP`
events followed by the B100K training start. The cooperative regression test now
includes an earlier ready teardown while publication waits for training;
all four tests pass. GPU-idle utilization alone does not mean memory is free:
verify server exit and memory release at handoff.

### Teardown must wait for all block inference

At B100K, an inherited campaign teardown became ready after only one subset of
the block: 868/1,045 inference jobs were done while 177 remained pending. As an
exclusive action it prevented more inference dispatch while waiting for CPU
publication, leaving loaded GPU servers idle. Repaired all 24 pending teardown
rows in the combined DB to depend on every inference row in their own block,
in terminal mode, and made both builders enforce that invariant. Teardown
must never preempt still-runnable inference from another suite in the block.
Ready training continues to take priority once all GPU work is terminal.

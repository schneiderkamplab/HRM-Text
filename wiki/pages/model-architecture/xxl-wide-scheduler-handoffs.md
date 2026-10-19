---
type: Operational History
title: Local XXL-wide Scheduler Handoffs
description: Verified local SQLite migration, evaluation repairs, and cooperative CUDA suspension handoffs.
tags: [evaluation, scheduler, training, suspension]
status: stable
last_updated: 2026-10-17
confidence: high
---
# Local XXL-wide Scheduler Handoffs

Runtime guidance is in the [request-shared scheduler runbook](request-shared-eval-scheduler.md).

### 2026-10-18: Storage interruption recovery at 1,141,000

The October 17 23:41 failure again contains missing-directory and permission
errors for `/work/dfm/HRM-Text`, not an established model numerical failure.
On the replacement session all GPUs were empty and the local `/tmp` SQLite
authority was absent. Restored `state.backup.sqlite` into the original local
database path, verified SQLite integrity and the complete
`ephemeral_step_1141000`, and reset only the dead running training lease.
The resume tag now points to that ephemeral. The 1.15M evaluation/full-stop,
XL 3.8M handoff, 3.85M/3.9M evaluation and training definitions are retained.
Runner log: `logs/scheduler/dfm10_XL_epoch9_20260831/runner-recovery-1141000.log`.
The restart loaded the checkpoint but failed at `wandb.init`: no W&B login
survived in the new home directory. Requested scheduler stop to avoid wasting
retries. Reauthenticate before clearing that stop and retrying the training
row; this entry does not establish a successful training restart.
After the user's reauthentication, cleared the stop and relaunched the same
SQLite runner (PID 348654). Verified training reached 1,141,020, W&B resumed
`dfm10-xxl-wide`, and all eight GPUs reached 100% utilization at roughly
164,350-166,654 MiB memory usage. Recent five-step intervals took
13-15 seconds after compilation. This supersedes the authentication blocker.
The user will start the monitor manually with `--rich --interval 30` against
the same plan directory; no new tmux session or monitor was created.

### 2026-10-17: Requested XXL-to-XL handoff after 1.15M

Supersedes the pending XXL-wide continuation beyond 1.15M: the user requested
a full stop after its evaluation and continuation of XL from 3.8M at base
LR 1e-5. The current training boundary and all 1.15M evaluations are retained.
11,019 future XXL rows (including five already-terminal teardown controls)
were archived to `paused-xxl-after-1150k-*.tsv` in the existing plan directory,
with a complete SQLite backup before editing. They are no longer active.

New row `xl-dfm15-resume-3800000-to-3850000` depends on the completed 1.15M
training boundary and its existing terminal inference barrier (historically
named `xxlw-dfm14-train-1200000-evals-terminal`). Failed inference or blocked
CPU publication does not indefinitely prevent the handoff. The script
`scripts/resume_xl_after_xxl_1150k.py` requests the existing supervisor's full
identity-checked shutdown, waits for its launcher to exit, then starts XL.
XXL may remain offloaded during evaluation but is not restored afterward.
The supervisor stop request remains as an explicit stop for this run.

The verified transferred XL checkpoint and DFM15 dataset live under
`incoming/mimir-xl-20261015/`. Continue `step_3800000` with its exact epoch-1
row cursor, optimizer and EMA; do not reset the dataset cursor. Settings:
XL/BP8, GBS262144, GAS2, FSDP2 FP32/BF16, no reshard-after-forward,
no-sync accumulation, automatic LR dividers, constant base LR 1e-5.
The first queued segment ends at 3.85M; no later XL blocks were added by this
change. Outputs go to `checkpoints/dfm15/XL-from-dfm14-epoch1`; W&B remains
DFM5 / `dfm8-xl-from-dfm6-dfm7-epoch5-clean-full`.
Log: `logs/training/dfm15_XL_resume_3800000/train_until_step_3850000.log`.

CPU preflight verified the transfer receipt, complete checkpoint, sampled
index shapes/cursor and token mmap; Hydra composition and two handoff tests
passed. This is a scheduled handoff, not yet evidence of a successful XL launch.

Follow-up request: extended the same SQLite plan through 3.9M with full EMA
evaluations at 3.85M and 3.9M. Each campaign clones the current local 1.15M
task coverage and judge/capacity settings, including nine average jobs and
per-task merging/publication. `scripts/schedule_xl_3850k_3900k.py` installed
4,409 rows including the intervening GAS2/BP8 training segment at unchanged
base LR 1e-5 and auto dividers. The 3.9M training row depends on a terminal
barrier over 3.85M inference only, never on successful merges or averages.
All eight GPUs remain scheduler-managed with persistent inference servers.

`scripts/export_xl_local_continuation.sh` finalizes downstream fractional
epoch axes before export unlocks inference: preceding DFM14 end epoch
11.812711203938841 plus the checkpoint's exact DFM15 row cursor divided by
the full DFM15 epoch row count. This matches the transferred XL campaign,
not the XXL-wide epoch axis. New logs/exports use `dfm15_XL_local` and unique
step tags. This supersedes the first-segment-only scheduling scope above.

### 2026-10-17: Historical XXL-wide optimizer-axis coverage

Completed after reauthentication and before restart from 1,133,500: published
85,916 initially prepared rows plus 85,780 omitted historical rows, totaling
171,696 unique optimizer-step points. Both publications have verification
receipts under `logs/wandb_axis_repair/xxl-wide-1150k/` (second in `supplement/`).
Evaluation metrics and workspace panels were not changed. Latest training
summary values were restored after each publication. Supersedes the original
85,916-row completeness claim below.

Important W&B API pitfall: `scan_history(keys=...)` uses sampledHistory; large
pages omitted observations and dense pages could repeat boundary rows. Use
keyless history scans for lossless preparation/verification, deduplicate by
optimizer step and reject conflicting values. The repair now appends explicitly
after `lastHistoryStep`, not solely the SDK's local counter. Initial publication
reported a false coverage mismatch; its 85,916 values were independently verified
without republishing. The supplemental 85,780-row publication passed verification.

The old watcher is dead. Its owned stop request was archived, the existing SQLite
plan restarted (PID 477101), and the complete 1,133,500 checkpoint loaded with the
original BP8/GAS4/LR/run settings. Passed CLI suspension boundaries were removed
before launch. Rich monitor runs in existing tmux session `hrm-3`, window 4.

Later outage supersedes the watcher-running status below: storage disappeared
before 1.15M, killing training and the watcher. With storage restored, the latest
complete ephemeral is 1,133,500. Restored the existing SQLite backup, reset only
the interrupted 1,150K training row, and pruned already-passed suspension steps
from its fresh-launch command. Checkpoint readiness passed. Publishing the
prepared history failed before any remote writes because the new session again
lacked W&B credentials. The existing repair stop request remains until login
and publication; the SQLite administrative lock is released. No new plan was
created and no evaluation results were reset.

Read-only W&B API checks on `DFM5/dfm10-xxl-wide` confirm that earlier training
history exists but lacks `train/step`. History windows 0-10K, 150-160K and
500-510K contained respectively 2,004, 1,995 and 1,994 loss rows, none with the
explicit axis. The 850-860K window had 1,993 loss rows but only 100 with the axis
(first sampled explicit row at 859,505). All sampled loss rows in 870-880K and
900-910K had it. Thus selecting `train/step` hides old observations; this is not
loss of the pre-DFM14 history. These are window samples, not exhaustive counts.

Repair should append preserved historical metric values with verified optimizer
steps during a writer-free handoff, then restore current summary values. Do not
infer post-migration optimizer steps from `_step`: offset logging makes them
different. The XL-specific axis repair script is precedent, not directly usable
for this run without changing its run ID, cutoff and scheduling assumptions.
No remote history or workspace was modified during diagnosis.

User authorized publication after 1.15M. Prepared
`logs/wandb_axis_repair/xxl-wide-1150k/payload.jsonl`: 85,916 unique missing-axis
rows at steps 5-859,490, each carrying loss, accuracy, exact accuracy, LR and BP
steps. API scans repeated four identical observations; preparation deduplicates
these and rejects conflicting values. No evaluations are included in the payload.
The reusable XL repair script now accepts explicit run/cutoff parameters and an
option to leave workspace panels unchanged.

`scripts/relog_xxl_axis_at_1150k.py` is running detached (initial PID 136765),
logging to that directory's `watch.log`. It owns the scheduler's drain request;
the current training segment continues until its verified 1.15M offload. It then
closes the old supervised writer, publishes with a 30-minute deadline, and
restarts the same scheduler even on repair failure, unless the stop request was
changed by the user. Evaluation proceeds normally; the next training segment
reloads step_1150000 so W&B reads the appended history cursor afresh. Five future
cooperative launch definitions have passed <=1.15M CLI suspension boundaries
removed. This is scheduled work, not a claim that publication has completed.
All SQLite edit locks were released. No training was interrupted for preparation.

### 2026-10-17: Submodule publication blocker

Resolved on recheck the same day: the remote now supplies `d7605ea`, and
`git submodule update --init --recursive dfm-evals` completed successfully.
The unavailable-pin status below is superseded; the installed evaluator now
matches main's pin.

Pulling main through `36c5584` succeeded without conflicts using
`git -c fetch.recurseSubmodules=false pull --no-rebase` after recursive fetch
failed. That revision pins `dfm-evals` to `d7605ea5efb4f30f2e442a2c639b3e59dbc41602`,
which the configured schneiderkamplab remote rejects with `not our ref`.
`git submodule update --init --recursive` also fails on that pin. The local
submodule remains at `1789d64`; do not stage it as a rollback. Publish the
missing commit from its originating repository, then repeat submodule update.
Main and the installed evaluator are not yet fully synchronized.

### 2026-10-17: Repair of the 1.1M path failures

Later verification supersedes the pending-restoration status below: repair
finalization completed and generation 6 restored successfully. Training reached
1,120,850 before filesystem access failed (`PermissionError` on
`/work/dfm/HRM-Text`) at 05:55. The scheduler failed on the same path. A new
machine session lacked the local `/tmp` database; its 05:54 shared backup passed
SQLite integrity checking and was restored to the same local database path.
Only the interrupted 1,150K training row was reset, with resume tag
`ephemeral_step_1120500` (sidecar, DCP metadata and eight shards present).
All its recovery dependencies were already done. The attempted fresh launch
then failed before checkpoint loading because W&B credentials were absent in
the new session. Reauthenticate before retrying; do not disable logging or
rerun completed evaluations.

After user reauthentication, the same row was retried. The original CLI still
contained passed suspension boundaries (1.05M and 1.1M), causing a ready-only
pause at 1,120,501. Requesting supervisor restoration without an offload receipt
triggered its disk fallback, not an in-memory resume. The fallback checkpoint
loaded successfully with consumed boundaries removed; progress beyond 1,120,501
was verified. For future fresh launches, prune already-passed CLI suspension
boundaries before launching; do not request an offload restore for a ready-only
pause. Rich monitoring was recreated in `hrm-0:4` with a 30-second refresh.

The missing-path issue below was repaired without changing shared held-out pins.
`python -m scripts.localize_dfm14_eval` generates machine-local configuration
under `data/dfm14/evaluation/local-config`, verifying each selected/input file's
SHA256 before substituting paths. Shared configuration had pointed at the other
machine's `/work/mimir/HRM-Text` tree. Future pending rows now use the localized
configuration too.

Training cooperatively suspended at 1,118,800 (generation 6), wrote its fallback
checkpoint, and offloaded all eight workers. All 128 failed inference shards
then completed successfully, as did their task merges. Final averaging was
still running at verification; training restoration was not yet confirmed.
All nine checkpoint average jobs were reset to depend on the repaired merges,
avoiding publication of premature incomplete averages. The terminal recovery
gate permits training continuation even if finalization fails.

`scripts/repair_1100k_eval_handoff.py` records the one-off machine-specific
recovery, not a reusable resume command. Do not replay it against the live plan;
it requires explicit `--execute`. SQLite is authoritative, with plan.tsv exported
as a snapshot after edits. Use the cooperative supervisor, not a second torchrun.

### 2026-10-16: 1.1M evaluation handoff

Verified automatic generation-5 restoration at step 1,100,000, followed by
training progress through 1,100,020 on all eight GPUs. The
`xxlw-dfm14-train-1150000-evals-terminal` gate completed with 919 successful
and 128 failed inference dependencies; the 1,150K training boundary is running.
Failed DFM shards (an inspected DaLA shard references missing
`/work/mimir/HRM-Text/evaluation`) and blocked publication rows did not prevent
training continuation. These failures still need separate repair; the checkpoint
evaluation is not complete. No manual restore or plan change was necessary.
Post-resume step deltas were about 2.9 seconds/step; tqdm's smoothed rate includes
the suspension and is not a valid immediate training-speed estimate.

### 2026-10-12: Early 1M supplement handoff

The requested suspension at 1,001,250 arrived after that step; the training
hook accepted it at **1,001,270**. All eight ranks published readiness after
writing `checkpoint_state_step_1001270.json`, then CUDA checkpointing offloaded
their GPU state. The existing launcher/supervisor and worker processes survive.

For `logs/scheduler/dfm10_XL_epoch9_20260831`, the SQLite plan now places the
403 missing 1M inference jobs before resuming toward 1,050,000. The prior
644 inference results are preserved. An explicit completed boundary
`xxlw-dfm14-train-early-1001270` records the verified offload; the existing
1050K training row remains pending, not falsely completed.
`xxlw-dfm14-1000000-supplement-evals-terminal` waits only for those 403
inference jobs to become terminal, including exhausted failures. Merges,
averages, and publication do not block restoration. The existing training row
drains owned evaluation servers and requests the sole supervisor to restore;
its disk fallback now starts from `step_1001270` if the launcher is lost.

The old coordinator alone was stopped by verified PID after offloading; no
training workers or supervisor were killed. The replacement uses the same
environment and request-shared SQLite settings. Administrative receipt:
`early-1001270-handoff.json`; backup: `before-early-1001270.sqlite`; runner log:
`runner-early-1001270.log`, all in that plan directory. The Rich monitor follows
the same plan. Restoration after these evaluations is scheduled, not yet
observed at the time of this entry.

Follow-up verification (2026-10-13): restoration succeeded in the same eight
worker PIDs (397377, 397378, 397381, 397383, 397387, 397394, 397396, 397397),
with matching generation-1 `resumed.json`. Training passed step 1,002,120 at
approximately 2.85 seconds/step and wrote the 1,002,000 ephemeral. No evaluation
GPU processes remained; no disk fallback was needed. This verifies operational
resume, not numerical parity. The evaluation interval was only partially
successful: 160 supplemental DFM inference jobs completed, while all 243
supplemental EuroEval jobs failed with `KeyError: 'hf_export_dir'`. Those jobs
still need configuration repair and rerunning; training correctly resumed
despite their terminal failures. Do not describe the 1M supplements as complete.

The subsequent repair adds `hf_export_dir` from the local model path to all
4,374 pending/failed supplemental EuroEval inference/merge definitions across
the nine checkpoints. The proxy now also resolves the existing
`hrm_hf_export_dir`/`standard_hf_export_dir` keys, and the harmonization builder
supplies the explicit field. Eight focused regression tests pass. Training
suspended at 1,002,170 (generation 2), with verified disk checkpoint and GPU
offload. Only the 243 failed EuroEval inference jobs were reset; the successful
160 DFM jobs remain done. The new `xxlw-dfm14-1000000-euro-repair-terminal`
gate is inference-only, and the existing 1050K training row resumes from the
same process or `step_1002170` disk fallback. Receipt and runner log:
`euroeval-repair-1002170.json`, `runner-euro-repair-1002170.log`. This retry's
eventual restoration remains to be verified; do not infer success from dispatch.

Verified outcome on 2026-10-13: all 243 EuroEval retries succeeded, completing
all **1,047** 1M inference jobs. The scheduler drained its eight vLLM servers
and the supervisor restored generation 2 into the same eight training PIDs.
`resumed.json` matches step 1,002,170; no disk fallback was used. After roughly
103 minutes suspended, training passed 1,002,200. Log timestamps show 25 steps
in 72 seconds (2.88 s/step), consistent with the prior rate. The immediate tqdm
smoothed ETA includes the suspension and is misleading until it settles.
Seven post-processing rows remained pending at this verification; inference
completion does not imply that all publication/averaging is finished.

Performance follow-up: direct-mode startup admitted many clients onto the
first ready replica while the other seven were provisioning. At one point
57 clients resided on GPU0 and one on each other GPU; the eventual tail had
41 clients on GPU0 alone. They continued progressing and were not restarted.
Review startup admission balance before the next campaign; this is separate
from the repaired tokenizer-path failure and from successful CUDA restoration.

Later user-requested short pause (2026-10-13): training suspended at
**1,015,800**, saved its regular fallback checkpoint, and successfully offloaded
all eight ranks (no compute processes listed by nvidia-smi). The supervisor-root
`hold` and SQLite administrative dispatch lock remain set pending explicit user
resume. The existing 1050K boundary row remains running/waiting, not completed.
To resume this manual pause, use the current active control directory's matching
generation restore request through the existing supervisor, remove the hold,
and clear the SQLite admin lock; do not start a second training launcher.

The user subsequently requested resume: generation 3 restored successfully
into the same eight worker PIDs and training passed 1,015,810. The supervisor
hold and dispatch lock are cleared. No disk fallback or second launcher was
needed; five post-resume steps took 14 seconds.

### 2026-10-10: XXL-wide /work/dfm migration at 950K

This is the other machine's XXL-wide campaign, **not** the XL campaign below.
The five scheduler commits are already in local `main` at `089550e`.
Existing plan: `logs/scheduler/dfm10_XL_epoch9_20260831`.
Legacy runner PID 103759 has a soft stop request; the active
`xxlw-dfm14-train-950000` segment continues normally. Do not clear that request
or start a second runner while migration is waiting.

`scripts/migrate_xxl_wide_sqlite.py` is detached (initial PID 3074897), waiting
for that runner to drain. It refuses running rows, failed boundary training,
an incomplete checkpoint, or an existing database requiring recovery. It backs
up the current TSV, rechecks preflight, imports the same campaign, backs up
SQLite, clears the stop, and launches the new runner. Completed rows are not
replayed. Migration is **scheduled, not yet observed complete**; verify
`sqlite-migration.json`, `runtime.json`, and logs before reporting it completed.

- Authority: `/tmp/dfm14-xxl-wide-production/jobs.sqlite` (local overlay).
  `/work/dfm` is WekaFS and must only hold snapshots/backups, not SQLite WAL.
- Runner: `hrm`, `--backend sqlite --persistent-vllm --max-clients 64
  --server-concurrency 1024 --cpu-cores 256 --reserve-cores 8`, GPUs 0-7.
- CUDA 13.2 compiler verified under
  `/home/ucloud/miniforge3/envs/hrm/lib/python3.13/site-packages/nvidia/cu13`;
  set `CUDA_HOME` there and prepend its `bin` plus `hrm/bin` to PATH.
- Preserve local target allocations: 0.9 normal, 0.65 judged; retain
  `unsloth/gemma-4-E4B-it` and its existing judge engine/settings. The other
  machine's XL allocations are not automatically appropriate for XXL-wide.
- Ten judge-first phase gates and nine failed-eval-tolerant training handoffs
  were explicitly applied to pending DFM14 rows. Model, scorer, batch sizes,
  W&B IDs, training commands and historical runtime states were preserved.
  Revised preflight: 4,538 pending rows, zero failures.
- The XXL-wide wrapper `dfm14.continue_training.finalize_boundary` now publishes
  exact cursor-derived `eval_epoch` **and** `eval_step` in a SQLite transaction.
  It preserves running wait tokens, refuses active inference, and retains the
  TSV path. Focused wrapper/store/grouping/runner tests: 77 passed.
- Rich monitor: existing tmux pane `%2` (shared window 4), refresh 30 seconds.
  The migration only replaces it if it is still an eval monitor.

Watch `logs/scheduler/dfm10_XL_epoch9_20260831/sqlite-migration.log` for handoff;
then `runner-sqlite.log` in that directory. The authoritative database is
periodically backed up to `state.backup.sqlite` there. After migration use
database editing/recovery commands, not direct writes to the old `plan.tsv`.
DFM14 data and the DFM15 native-reasoning staging remain unchanged.

**Observed completion later on 2026-10-10:** the 950K training segment and
export completed. Migration finished at 21:58 local time; SQLite runner PID
3393903 started with 64 clients and split 2,850 publication phases from
inference. All eight judged shards completed and merged before non-judged
work began. The Rich monitor is live in window 4. This supersedes the
"not yet observed complete" status above.

The user's subsequent coverage check found a pre-existing plan omission:
only Danish/English legacy tasks and the 16 DFM14 languages were scheduled,
not the earlier 34 languages' accepted-v2 tasks. At the user's request,
`scripts/prepare_xxl_all_language_evals.py` recovered all 34 selections from
`schneiderkamplab/dfm13-dala-v2-{language}-compact` test-representative files.
Both published input hashes and the reconstructed 1,000-pair selected-file
hash must match the original committed manifests exactly. No train rows or
new test selections are substituted. Remote build receipt references remain
in recovery provenance; runtime pins use the verified published test files.
Ports 2850 and 6768 were unreachable during this recovery.

Local inputs/configs and `ready.json` are under
`data/dfm14/evaluation/all50`. Recovery uses `hrm`; constructor verification
uses `dfm-evals/.venv/bin/python` with `PYTHONPATH=.:dfm-evals`, because
`inspect_ai` is installed in the eval venv, not base `hrm`:

```bash
PYTHONPATH=.:dfm-evals dfm-evals/.venv/bin/python \
  scripts/prepare_xxl_all_language_evals.py --verify-only
```

`scripts/extend_xxl_all_language_evals.py` applies the verified registry under
the database admin claim lock, preserving running tokens/completions. The
2026-10-10 install added 6,120 rows over ten checkpoints (950K through final
1,391,204): 68 tasks/checkpoint, four inference shards and four CPU export
rows plus one merge per task. DaLA and GEC now each cover all 50 languages,
2,000 examples per task. Existing Danish/English benchmarks remain unchanged;
this is **not** a claim of EuroEval coverage in every language. Multilingual
averages wait for the additional merges, and terminal training barriers also
wait for them while retaining failure-tolerant continuation. The prior
multilingual manifests still report coverage gaps for unrun legacy/EuroEval
metric slots rather than inventing values. Four migration/extension tests
passed; all 272 new shard constructors passed. The extension unlocked claims
and new-language clients started successfully.

Comparison with the live remote plan on SSH port **2103** (its pending 3450K
checkpoint, excluding superseded/skipped rows) confirms that language coverage
is not full campaign parity. Local/remote unique task counts: standard 8/8,
DFM excluding IFEval 131/170, EuroEval including IFEval 20/261; averages 2/9.
The local plan lacks 243 remote EuroEval tasks and 40 historical DaLA/GEC tasks
that the remote retains alongside v2. Local-only tasks are Andersen
modernization and VALEU-da/en. Common inference shard counts agree. Both log
to DFM5, local `dfm10-xxl-wide` versus remote
`dfm8-xl-from-dfm6-dfm7-epoch5-clean-full`; model-specific capacity settings
must not be copied blindly. Read-only snapshots:
`logs/diagnostics/scheduler-parity-20261010/{local-950k,remote-3450k}.json`.

**2026-10-12 update:** The local 1M-and-later campaign gap above is now
reconciled against port 2546, including nine average jobs. See the
[deployment receipt and deferred 1M supplementation](../dfm14-evaluation-baseline.md#2026-10-12-local-xxl-campaign-reconciliation-installed).
Historical 950K and completed dependency versions are not retroactively changed.

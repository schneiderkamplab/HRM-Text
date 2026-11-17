---
type: Concept
title: 2026-11-04 Epoch-2 WSD Extension For B-dfm15-gemma4
description: Plan surgery to extend the B-dfm15-gemma4-epoch1 run to two epochs with a delayed cosine decay, staged and applied mid-flight at the 450K boundary.
tags:
- training
- eval-scheduler
- wsd-schedule
- plan-surgery
status: draft
confidence: high
last_updated: '2026-11-05'
---
# 2026-11-04 Epoch-2 WSD Extension For B-dfm15-gemma4

**Latest approved schedule, 2026-11-04:** cosine decay 900,000–1,000,000, then flat base LR 1e-5 through 1,025,846. Staged database repaired and automatic switch armed for the verified 450K pause; see the final section. Earlier 962,923-start schedule and broad-kill flip script below are superseded.

The B-dfm15-gemma4 run trains with a **windowed cosine (WSD) schedule**, not a
full-horizon decay. Discovered from `/proc/<rank>/cmdline`:

```
epochs=1 lr=3e-4 lr_warmup_steps=5000 lr_decay_start_step=450000
lr_decay_end_step=512923 lr_min_ratio=0.0333 training_total_steps=512923
```

LR is constant 3e-4 until step 450,000, then cosine to 1e-5 by 512,923. Because
decay is decoupled from the horizon, **extending training to a second epoch is
a pure LR-schedule change with zero discontinuity**: keep the constant LR and
move the decay window to the new end.

## Target schedule

| Parameter | Epoch 1 (current) | Epoch 2 (new) |
|---|---|---|
| training_total_steps | 512,923 | 1,025,846 |
| lr_decay_start_step | 450,000 | 962,923 |
| lr_decay_end_step | 512,923 | 1,025,846 |
| epochs | 1 | 2 |
| Eval cadence | every 50K | every 50K |

The 62,923-step decay length is preserved. Eval scores through 250K improve
monotonically and accelerate (dfm13 multilingual 0.635→0.682), motivating the
extension.

## Mechanics (verified)

- **All LR/schedule args live in each train row's `metadata_json.command`**
  (58-token hydra string). The runner rebuilds the spawn from
  `job.metadata["command"]` (`eval_scheduler/eval_scheduler/runtime.py:601`)
  with `target_step = job.metadata["stop_after_step"]` (`runtime.py:573`) and
  resume-tag substitutions. Editing the YAML config is NOT enough — the row
  commands win.
- `pretrain.py:533` prefers `training_total_steps` over `epochs×steps`;
  `pretrain.py:1587` hard-errors if a checkpoint step exceeds the horizon, so
  `training_total_steps=1025846` must be set in every epoch-2 train row.
- **`suspend_after_steps` is carried in every train row's command**
  (`pretrain.py:163`, `training_suspend.protocol.steps`). Epoch-2 rows append
  550000…1000000 (the final leg 1M→1,025,846 carries none, mirroring epoch 1
  where the 500K→512,923 leg relies on `final_boundary`).
- **`steps()` sorts and dedupes** (`training_suspend/protocol.py:64`) — queue
  token rewrites that duplicate a step self-heal. The hook also consumes every
  queued step ≤ current step on first fire (`training_suspend/runtime.py:96-100`),
  so stale (past) entries never cause insta-suspend at resume.
- Checkpoints are written every 10,000 steps, so `step_550000` etc. will exist
  when epoch-2 rows need them.
- The eval block is the same shape at every boundary; the **250K block is a
  valid template** for epoch-2 blocks (2,203 rows each).

## Surgery (staged, not yet applied)

Script: `.tmp_vocab_probe/epoch2_stage.py` — operates on a DB copy by default,
`--apply --db /tmp/dfm15-B-production/jobs.sqlite` for the live flip.

1. **Rewrite** train rows (staging mode: all pending 300000…512923;
   apply mode: only train-500000 and train-512923): `epochs=1→2`,
   `training_total_steps→1025846`, `lr_decay_start_step 450000→962923`,
   `lr_decay_end_step→1025846`, append suspend steps. Conservative apply means
   a crash-respawn before the flip keeps the epoch-1 schedule.
2. **Clone** train rows train-550000…train-1000000 + final train-1025846
   (`ckpt_tag=step_N`, `resume_from_tag=step_(N−50000)`,
   `completion_checkpoint_tag=epoch_2` on the final, `eval_epoch=2.0`,
   deps rewritten prev→prev).
3. **Clone** eval blocks from the 250K template for 550K…1M + 1,025,846 with
   the digit-boundary regex `(?<![0-9])250000(?![0-9])` — and **also remap the
   prior-boundary token 200000→prior(N)** (prior(N)=N−50000, but
   prior(1025846)=1000000). Missing the prior remap chains new wait rows to
   stale block terminals.
4. **Insert dependency edges** for every new row (`dependencies` table is the
   live graph the runner's READY_SQL reads; the `deps` string inside the
   definition is not enough).

Validation on the staging copy passed: 48,489 jobs / 156,749 edges,
0 unresolved deps, cycle-clean, 0 leftover template tokens, correct effective
suspension queues per leg.

## Offline dry sweep

`python -m eval_scheduler database preflight --database <db>` (new `--database`
mode; legacy `--plan-dir` TSV mode still works; `--all` includes non-pending
rows) validates every pending row offline, without claiming, running scripts,
or querying GPUs:

- definition-level checks (`DatabaseRunner._validate`, graph validation);
- availability checks (`eval_scheduler/eval_scheduler/preflight.py`):
  required-now metadata paths (`ckpt_path`, `standard_config`,
  `dfm_single_tasks_config`, `dfm_ifeval_config`, `dfm_evals_dir`,
  `export_tokenizer_path`, `source_hf_export_dir`, `resume_ckpt_path`,
  `workdir`), anchored paths (artifacts produced by earlier rows — only an
  existing non-root ancestor is required so future boundary subdirectories do
  not false-fail), executables (`python_bin`, `vllm_python`, `euroeval_bin`,
  train `command` binaries with leading KEY=VALUE env tokens skipped, mirroring
  `split_command_environment`), per-action repo scripts, and cooperative
  training settings (`control_root` anchored, `launcher_settings`,
  shim/nccl libraries). `multilingual_manifest` is required only for the
  multilingual average variant — on expanded-dala rows it is dead weight (the
  script never reads `--manifest`).

Results: live DB 13,223 pending / 0 failures; staged epoch-2 plan 37,467
pending / 0 failures. The sweep caught two real staging bugs before launch:
cloned train rows kept the template's inner `definition.job_id`
(`store._job` resolves by the inner id, so 11 rows collapsed onto
`b-dfm15-train-500000` → "Duplicate or empty job IDs"); the fix is to set
`definition['job_id']` on every clone (own-boundary tokens, prior-boundary
remap, inner job_id). Dataset availability inside training configs remains
out of scope.

## Flip procedure

Script: `.tmp_vocab_probe/epoch2_apply.sh` — run once at the 450K boundary:

1. Gate on the 450K checkpoint + fresh `suspend_ready.json`.
2. Wait until 450K eval rows are running (boundary processing done; trainer
   suspended/drained).
3. Kill the trainer tree (launcher/supervisor/torchrun/ranks). Killing after
   `suspend_ready` is safe: the checkpoint is on disk; killing frees VRAM
   whether or not the CUDA-checkpoint offload succeeded (the
   fallback.request → disk-resume path is proven). The eval watchdog touches
   eval rows only — no trainer resurrection.
4. Pre-flip DB backup, then the apply-mode surgery, then postflight checks
   (including the offline dry sweep on the flipped live DB).

train-500000 (deps = 450K terminals) then respawns the trainer from
`step_450000` with the epoch-2 schedule.

Known cosmetic issue: cloned queue strings can contain a duplicate step token;
`steps()` dedupes, so this is harmless. Sandbox-tested staging and apply modes
both validate clean.

## Progress-based assessment at approximately 432K, 2026-11-04

Recommendation: favor continuing at the full LR into a second epoch, with moderate
confidence. This is advice only; neither database nor the trainer was changed.
Supersedes the earlier motivation based only on scores through 250K: improvements
continue through 400K but are not uniformly accelerating. The earlier phrase
“pure LR-schedule change” refers only to continuity of LR at 450K; another epoch
also changes exposure to repeated data, and its benefit is not yet measured.

| Complete evaluation group | 300K | 350K | 400K |
| --- | ---: | ---: | ---: |
| English v2 | 0.55124 | 0.56400 | 0.57495 |
| Original 19-language multilingual v1 | 0.46656 | 0.46861 | 0.47948 |
| DFM13 13 new languages | 0.46933 | 0.46730 | 0.47303 |
| DFM14 16 new languages | 0.72106 | 0.72672 | 0.73063 |

All four groups have complete declared task coverage and unchanged definition
hashes across the compared checkpoints. Across the 48 non-English language
aggregates, 35 improve and 13 decline from 300K to 400K. Larger combined population
metrics report incomplete coverage and are not used as complete multilingual evidence.

Sampled W&B training-loss means: 200–250K 1.2226; 250–300K 1.1987; 300–350K
1.1814; 350–400K 1.1796; 400K–current 1.1770. These are sampled, heterogeneous
training batches, not a held-out loss curve. The flattening warrants watching
second-epoch generalization but does not erase the continued evaluation gains.
The run has not yet supplied a cooled-checkpoint comparison or second-epoch results.

Read-only inspection confirms the live DB still decays 450000–512923 and the
staged DB decays 962923–1025846. The latter preserves the original 62,923-step
cooldown. If the desired rule is literally the last globally aligned 50K segment
plus the remaining sub-50K tail, the interval is **950000–1025846** (75,846 steps).
Resolve that difference when implementing a switch; it is not a reason to decay now.
At about 3.4 steps/sec, an extra 512,923 steps costs about 42 hours of training
alone, plus evaluation overhead. Reassess improvement at the existing 600–650K
evaluations; bring cooldown forward if broad evaluations consistently stop improving.

Evidence and caveats: [assessment JSON](../../../docs/reports/b-dfm15-epoch2-assessment-20261104.json).
[WSD research](https://arxiv.org/abs/2410.05192) supports separating stable-phase
progress from final cooldown; [repeated-data research](https://arxiv.org/abs/2305.16264)
supports the plausibility of useful second-epoch training, without proving the
optimal duration for this recurrent model or this data mixture.

## Approved 900K–1M cooldown and armed 450K switch

User explicitly authorized changing the staged database and switching during the
450K pause. The repaired `/tmp/dfm15-B-production/jobs_epoch2_stage.sqlite` has:

- Base LR 3e-4 through step 900,000.
- Cosine decay to 1e-5 from 900,000 to 1,000,000.
- Flat 1e-5 for the remaining 25,846 steps, ending at 1,025,846.

`windowed_cosine_lr` clamps its progress at one after the decay end, so the flat
tail needs no second scheduler. Both metadata.command and cooperative_training.command
are updated, including epochs=2, the full training horizon and stop_after_step.

The review also found and repaired continuation problems in the older staged copy:
512923 was still marked final with completion tag epoch_2; 550000 resumed from
500000, skipping the intervening boundary in its dependency chain; cooperative
commands retained the old epoch horizon; and cloned eval log directories could
point at their 250K template. The new plan suspends explicitly at 512923, treats
it as non-final, resumes 550K from that checkpoint, fixes future eval coordinates,
and gives new eval jobs their own log directories.

The old `.tmp_vocab_probe/epoch2_apply.sh` is **superseded; do not run it**.
[New switch controller](../../../scripts/b_dfm15_epoch2_switch.py) uses a verified
450K disk checkpoint, matching pause, completed 450K training row and scheduler
hold. It then fences new claims with the database admin lock, backs up live state,
changes only the pending continuation definitions and adds the new rows. Existing
running eval definitions, tokens and runtime state are preserved. A postflight
runs before the identity-checked launcher receives SIGTERM for scoped cleanup.
This one disk-checkpoint restart is necessary to change the already-loaded trainer
configuration; subsequent epoch-two boundaries use continuous cooperative suspension.

The new trainer uses a separate `cooperative_epoch2_from450k_20261104` control root
and resumes step_450000 with optimizer/EMA state. No broad pkill is used. A failed
transaction/postflight restores only affected definitions and clears the dispatch
fence; running eval completions are not overwritten. The watcher releases its
admin lock in finally and then verifies the new supervisor command and a saved
checkpoint beyond 450K before declaring the handoff complete.

Verification: **40 tests passed** for LR endpoints/midpoint/flat tail and continuation
commands. Scheduler offline preflight: **37,467 staged pending rows, zero failures**.
A simulated live merge changed/added 24,246 rows, preserved the active claim exactly,
and passed preflight for **30,855 pending rows, zero failures**. Rollback simulation
restored the original 24,245-row plan without changing the running claim. A first
simulation preflight correctly refused WekaFS as authoritative SQLite storage;
the check was rerun on a local `/tmp/dfm15-B-production` copy. These are availability
and graph checks, not live executions of all evaluations.

Detached switch watcher PID at arming: **124981**. Runtime state, backups, hashes,
preflight results and log are under
`logs/scheduler/B_dfm15_gemma4_epoch1_20261103/epoch2-switch-900k-1m/`.
`status.json` distinguishes waiting, applied-awaiting-resume and verified progress;
`handoff-verified.json` is written only after actual continuation evidence. At arming
the live trainer was still below 450K and retained its original schedule.

### Live switch applied; 450K evaluations progressing

The switch controller has now applied 24,246 updated/new rows during the 450K
pause. Live postflight checked 30,852 pending rows with zero failures; the dispatch
lock is cleared. The 500K continuation remains pending behind evaluations, with
epochs=2, base LR=3e-4, decay_start=900000, decay_end=1000000 and floor ratio 1/30
verified in its cooperative command. `status.json` reports
`applied_waiting_for_evaluations_and_resume`; actual post-450K training progress
is not yet verified.

At the status check, the 450K block advanced from 228 to 255 completed jobs during
the inspection, with 123 running, 1,825 pending and zero failed jobs across the
live database. All eight GPUs were active (77–100% sampled utilization). This
confirms operational progress, not the quality of unfinished benchmark results.

### Continuation verified through epoch-one end, 2026-11-05

The switch watcher wrote `handoff-verified.json`: the new supervisor resumed with
the authorized epoch-two LR schedule and a checkpoint beyond 450K. Subsequent
training reached 512,923. Both the 450K and 500K evaluation blocks completed all
2,203 rows. At the next inspection, the 512,923 block had 705 completed and 124
running jobs, zero failed jobs across the database, and an unlocked dispatcher.
The monitor and GPU activity showed ongoing evaluation work. Training's next
boundary is 550K, resuming from 512,923 after this block. This supersedes the
earlier applied-but-awaiting-resume status.


## 2026-11-05: Danish decline through 500K

The complete published `headline_avg_dala_v2/danish` (20/20 tasks at each
checkpoint) is 52.320% at 350K, 52.294% at 400K, 52.265% at 450K,
and 49.063% at 500K. The latest decrease is dominated by a concrete output
format regression in `gec_dala`, not evidence of uniformly worsening Danish.
Official grammar-correction exact matches fall from 847/1024 at 450K to
6/1024 at 500K. Direct inspection of all archived samples finds 978/1024
500K outputs start with the unwanted `Sætning:` label (26/1024 at 450K).
Diagnostic removal of that leading label and a trailing newline plus `Svar:`
recovers 833/1024 exact matches at 500K, versus 872/1024 at 450K.
This diagnostic does not change official scoring: extra text violates the
explicit instruction to return only the sentence.

The official GEC fall contributes -4.106 percentage points to the equal-weight
20-task headline; the actual headline falls -3.201 points, so the other 19
tasks collectively offset some of the loss. Danish IFEval, NER, sentiment,
and translation improve from 450K to 500K, while acceptability and reading
comprehension decline. Underlying correction quality also slips under the
same diagnostic stripping, so the format finding does not explain every
regression. These observations do not establish that deferred LR decay caused
the change. Training/scheduler and official metrics were not changed.

Evidence: [task values, published aggregates and complete GEC sample counts](../../../docs/reports/b-dfm15-danish-diagnosis-20261105.json).


### Follow-up: 550K results not yet available

At the subsequent 550K check, its training row was done but its eval block
had 1,062 done and 1,141 pending rows. The stored expanded Danish aggregate
had zero of 20 inputs and no score, despite its job being marked done; do
not interpret that artifact as a completed evaluation. Danish GEC scoring
rows remained pending and no merged GEC result was available.
The intervening complete 512,923-step checkpoint scored 48.768% Danish
(20/20), with GEC 11/1,024 exact matches, 1,008 label-prefixed outputs,
and 885/1,024 exact matches after diagnostic label stripping. Thus the
format regression persisted through epoch end; 550K recovery was not yet
established. These are read-only observations, not scheduler changes.


### Correction: 550K inference exists; publication is pending

Further inspection supersedes the implication above that GEC scoring had not
run. Both 550K GEC inference rows have complete Inspect archives in their
scheduler row directories, not the final merged task directory. Across those
archives, 116/1024 exact matches (11.328%) and 776/1024 `Sætning:` prefixes
show partial format recovery. These are archived task scores, not a completed
Danish headline. The prior check looked only in the final task output roots.

The separate `export_dfm_results` rows remain pending despite their inference
dependencies being done. The active runner writes `runner7.log`; `runner.log`
is historical and its stale-token traceback is not the current runner state.
`database_runner.py` dispatches only under `not exclusive_active`, so it does
not start pending CPU publication jobs while the 600K training job is active.
The 550K average already ran with zero Danish inputs. Also, GEC publication
row log directories differ from their inference row directories, while
`run_export_dfm_results` reads Inspect logs/context from its own log directory;
this is a separate path mismatch to repair before publication. The exact
historical transition that released training with unfinished publications has
not yet been established. No live claims or training processes were changed.


### Publication repair applied (2026-11-05)

Root cause confirmed in `scripts/b_dfm15_epoch2_switch.py::stage`: the
previous repair assigned every new eval row a separate scheduler row directory.
This broke the existing shared inference/publication directory contract and
canonical shard paths consumed by mergers. Staging now derives each new path
from the corresponding working 500K row, substituting only the checkpoint
number. A regression test checks shared GEC inference/export paths.

`scripts/repair_b_dfm15_publication.py --repair` backed up the live database,
briefly fenced dispatch, restored 24,046 eval row paths/states for 550K and
later, and created 1,045 canonical links to saved 550K artifacts. Original
inference archives were neither moved nor regenerated. Existing empty average
artifacts were archived separately. All publication/inference path pairs now
match. The 600K training definition, status and claim token match the backup
exactly; the administrative lock was released in `finally`.

CPU-only replay workers use the existing SQLite dependency admission and
attempt-token fencing. They run exports, task mergers, averages and reports;
they cannot run GPU inference, checkpoint export, teardown, or training.
Receipts and backups: `logs/scheduler/B_dfm15_gemma4_epoch1_20261103/publication-repair-20261105/`.
The runner source also now dispatches CPU publication while a training action
is active. That change is tested but loads into the existing coordinator only
on its next normal restart; the bounded replay handles the current backlog
without restarting the trainer or coordinator. Repaired future canonical
paths are already live in the database.

Validation: 51 scheduler/postprocessing tests plus nine schedule/path-repair
tests passed. Repository OKF validation retains the pre-existing oversized
`request-shared-eval-scheduler.md` error and 14 unresolved-link warnings.


The repair also keeps EuroEval task directories real: `Path.glob('**/...')`
does not traverse directory symlinks. Saved result files are linked individually,
including outputs of already-running merge writers. A regression test verifies
recursive metric discovery. All 960 DFM/EuroEval inference artifacts were
checked with `os.path.samefile` at the canonical and original paths; no model
outputs were replaced. Standard shard logs are also linked into their shared
task directories. See `artifact-verification.json` in the repair directory.


### Final verification: 550K fully republished

Superseding the intermediate linked-summary layout above, strict aggregate
provenance also rejects metric-file symlinks escaping the declared source root.
The repair materialized 263 generated EuroEval summary files as identical
regular files inside their canonical roots, preserving the original summaries
and all raw inference. SHA256 receipts are in `materialized-metrics.json`.
All ten average/report jobs were rerun after this correction; intermediate
incomplete reports are retained under `superseded-linked-metric-averages`.
The path-repair test now covers both recursive discovery and root containment.

Final live DB verification: **2,203/2,203 550K jobs done**, no failures or
pending rows. The 600K training definition/status/token are unchanged and the
administrative lock is zero. All 60 targeted tests passed. The latest W&B
history row independently confirms **Danish 0.5172422547044256, count 20,
complete true**, with the same definition hash as 500K. This supersedes the
intermediate 11/20-input history row, which remains identifiable by its
incomplete coverage; history was not deleted. Remote receipt:
`publication-repair-20261105/wandb-danish-verification.json`.

Danish therefore recovers from 49.063% at 500K / 48.768% at 512,923 to
**51.724% at 550K**, still below 52.265% at 450K. GEC is 116/1024 (11.328%)
officially, 776/1024 label-prefixed, and 886/1024 (86.523%) after diagnostic
label stripping. Diagnostic stripping has not changed the official scorer.
The [diagnostic report](../../../docs/reports/b-dfm15-danish-diagnosis-20261105.json)
now includes the repaired 550K result. No changes were made to smarteval.


### 2026-11-05 16:12 CET: runtime absent after 600K

A fresh live status check on host `j-12448162-job-0` found no trainer,
cooperative supervisor, or scheduler process; all eight GPUs reported zero
utilization and zero allocated memory. `/tmp/dfm15-B-production/jobs.sqlite`
is absent. The persisted runner heartbeat ends at 13:44:20 CET during 600K
evaluation. Its SQLite backup records train-600000 done, train-650000 pending,
and the 600K eval block at 331 done / 124 running / 1748 pending. Those running
rows are stale backup state, not evidence of live workers. The training log
ends at the cooperative 600K suspension and `fsdp2_step_600000` is present.
Cause of process/runtime disappearance is not established by this read-only
check. Prior claims of ongoing training and the decay ETA are superseded by
this interruption; no recovery or new launch was performed in this check.


### 2026-11-05: 600K recovery prepared; waiting for foreign GPU work

Supersedes the missing-database status above. On explicit user authorization,
restored `/tmp/dfm15-B-production/jobs.sqlite` from the persisted SQLite backup
under a lifetime runner flock. Integrity check passed. Preserved copies of
interrupted artifacts and token-fenced 124 stale claims before requeuing them;
26,780 completed rows were retained. The 600K checkpoint's DCP storage ranges
were checked against every referenced shard extent and passed. Its exact
cursor is epoch 2 / batch 87,077 / global row 69,331,268.

Nine pending training rows now share a fresh control root
`logs/training/B-dfm15-gemma4-epoch1/cooperative_recovered600k_20261105`;
650K resumes `step_600000`. Removed already-passed suspension boundaries from
both command representations, retaining 650K through 1M. The full LR and
900K–1M decay / final 1e-5 tail remain unchanged. Preflight checked all 21,708
pending jobs with zero availability/definition failures.

The first restart (`runner8.log`) collided with independently starting
smarteval GPU workers after the idle-GPU check. This caused 1,199 startup and
downstream failures, not benchmark-defect findings. Requested a soft stop,
let the B-owned clients finish, and verified its owned servers exited. Saved
`after-gpu-conflict.sqlite` and the failure/reset journal, then requeued those
known recovery-incident failures and invalidated premature averages. No
smarteval process was signalled and no smarteval file was changed. The recovered
store then had 26,784 done / 21,704 pending / 1 skipped, zero running/failed,
and the administrative lock was zero.

`shared_pool.py` now treats insufficient GPU startup headroom as
`ServerCapacityTimeout` (deferred admission without consuming attempts), while
invalid memory utilization remains a configuration error. Shared-pool and
runner regression suites: 43 tests passed.

Automatic recovery is armed in
`recovery-600k-20261105/resume_when_free.py`. It waits for absence of foreign
`kineticeval.local_worker` processes and all eight GPUs at >=178,000 MiB free
for 20 seconds. It never signals foreign work. It cancels if the stop-file
contents or modification time change, or if another administrative/running
state takes ownership. On admission it clears its own stop request, launches
one detached SQLite/persistent-vLLM coordinator (`runner9.log`), and watches
for actual training progress beyond 600K. Current phase is
`waiting_for_all_gpus`, **not resumed training**. Runtime receipt:
`logs/scheduler/B_dfm15_gemma4_epoch1_20261103/recovery-600k-20261105/resume-status.json`.
The user was asked to pause smarteval GPU work in its own thread.


### 2026-11-05 follow-up: private temporary directory and offline logging

After the foreign GPU workers stopped, the armed watcher launched coordinator
117527 (`runner9.log`). This exposed two additional new-job problems: the
current home had no W&B credentials, and `/tmp` directory operations hung.
The persisted historical W&B login was rejected (HTTP 401); no credential
was printed. The user was asked to authenticate in the current job.

The `/tmp` issue was reproduced with a minimal directory probe. Over 100
B-owned clients were in disk-sleep, many in `do_rmdir`; proxy startup timed out.
Setting `TMPDIR=/dev/shm/hrm-b-recovery` made W&B import complete in 0.45 seconds
and Torch in 0.92 seconds. The tmpfs has about 2.8 TiB capacity. No claim is
made about the underlying kernel/container cause.

Stopped the B coordinator and identity-scoped descendants. Reconciled eight
B server processes subsequently found orphaned using their server ownership
receipts and exact process start ticks; all exited and GPU memory was released.
No unrelated process was signalled. Preserved the pre-retry database and
requeued 273 known infrastructure-interrupted/failed jobs.

Coordinator 231010 (`runner10.log`) runs with the same SQLite/persistent-vLLM,
8-GPU and 128-client settings, plus `TMPDIR=/dev/shm/hrm-b-recovery` and
`WANDB_MODE=offline`. Thus metrics are retained locally and are **not currently
published to W&B**; authentication and later sync remain outstanding. Neither
the checkpoint/cursor nor the LR schedule changed. At the first healthy check,
600K had 382 completed / 124 running / 1697 pending and zero failures, with
actual GPU request activity. `recovery-600k-20261105/verify_resume.py` monitors
this coordinator and writes actual >600K training progress to `resume-status.json`.
This supersedes the earlier watcher status and runner9 process information.


### 2026-11-05 follow-up: credentials restored and online transition

The user reauthenticated W&B in the current job. A read-only API request to
`peter-sk-sdu/DFM5/B-dfm15-gemma4-epoch1` now succeeds. This supersedes the
missing/rejected-credential blocker above; no key was printed or recorded.

Requested a graceful stop of offline coordinator 231010 so its active clients
can finish before the online restart. `recovery-600k-20261105/transition_online.py`
is detached and checks the old process identity, unchanged stop-file fingerprint,
absence of foreign GPU work, all-eight-GPU headroom, no running claims and no
administrative lock before launching `runner11.log` with `WANDB_MODE=online` and
`TMPDIR=/dev/shm/hrm-b-recovery`. It then monitors actual training progress beyond
600K. Receipt: `online-transition-status.json`. A changed user stop cancels the
transition. The earlier offline monitor remains historical; this transition
receipt governs the next launch.

At this check 600K has 445 done / 124 running / 1634 pending and zero failures.
The clients are still importing cold EuroEval dependencies: repeated open-file
inspection shows movement through Transformers, OpenAI and LiteLLM files despite
`folio_wait_bit_common` waits. A read-only warmup read 45,112,569 bytes of
Transformers Python files in 223 seconds. This is distinct from the earlier
`/tmp` directory-operation hang; no root filesystem cause is established.
Training has **not yet advanced beyond 600K**.

W&B `sync --append` reported success for the offline records but cloud-history
verification found their step-zero metrics absent after the existing history
counter (600337). Summary fields were also replaced. Therefore CLI sync success
is insufficient for this recovery. `replay_offline_metrics.py` prepares the saved
rows, preserves their explicit 600K checkpoint axes, registers each metric, and
publishes at a fresh internal history step. It reconstructs latest summary values
from preserved history since 550K. Prepared data and verification receipts stay
under the recovery directory; verification must pass before claiming publication.

Publication verification now passed: all **358 fields from 33 offline records**
are present and exactly match at W&B internal history step **600338**, with
checkpoint axes **600000**. `offline-replay-verified.json` records zero mismatches.
The replay also restored 4,050 summary fields from preserved history before
applying the recovered metrics. Original offline files and sync receipts remain
intact. Do not repeat the publication blindly; inspect the verified receipt.


### 2026-11-05 online publication resumed

The transition completed: coordinator **313221**, `runner11.log`, is running
with `WANDB_MODE=online`. This supersedes the earlier draining state. Finished
EuroEval inference now feeds its queued merge/publication jobs; W&B writers
serialize through the existing per-run lock. Do not start competing unguarded
writers or reset claimed jobs. The Rich monitor is verified in tmux `hrm-3:7`
(`B-eval`, five-second refresh).

At the user's request to ensure finished evaluations sync, captured 124 local
merged-result files (1,212 fields). A detached, read-only cloud verifier
`recovery-600k-20261105/verify_finished_sync.py` checks that fixed snapshot while
scheduler publication continues. Its progress and mismatches are saved in
`finished-eval-sync-verification.json`; **only `verified: true` means the whole
snapshot is confirmed**. The prior 358-field offline replay remains separately
verified. First subsequent cloud-summary check matched 433/1,212 fields; the
remaining publication queue was still running, not declared complete. Raw results
and failed-check receipts are preserved. No inference was regenerated for sync.

### 2026-11-05 health check: benchmark-name failures

A later live check found 1,674 done / 124 running / 371 pending / 34 failed
600K jobs. All 17 failed inference logs report a dataset absent from the current
EuroEval registry: 15 `multi-ifeval-*` datasets (nl, nb, nn, sv, fo, pl, de, it,
cs, pt, fi, ro, uk, is, fr), `faroese-semantic-relations`, and `alba-mcq-pt`.
Their 17 merge jobs failed for missing result files. These are configuration /
dependency compatibility failures, not measured model failures. No registry
mapping or version fix has yet been verified. This supersedes the earlier
zero-failure health report. The runner heartbeat remains live and work advances;
several model servers were restarting during the GPU-utilization snapshot.
Cloud verification of the fixed 124-file snapshot remained incomplete at
563/1,212 fields. Do not claim full evaluation health or complete publication.

### 2026-11-05 fix: pin the multilingual EuroEval runtime

The recovered unpinned `uv --with euroeval` launcher resolved **17.3.0**, while
the multilingual registry was authored and previously preflighted for **18.1.0**.
All 259 remaining distinct benchmark names exist in the 18.1 registry. The drain
ultimately exposed 21 missing-name inference failures and 21 failed merges.
These supersede the initial 17+17 failure count above.

Installed/cached EuroEval 18.1.0, recorded its dependency versions, and passed the
actual guarded CLI `--help` smoke test. First imports required filesystem cache
warming (5.5 GB across dependencies); no benchmark rename or dataset substitution
was made. After coordinator 313221 exited and all claims drained, acquired the
runner lock, backed up SQLite to `before-euroeval-pin.sqlite`, and applied
`recovery-600k-20261105/repair_euroeval_runtime.py` under a short administrative
lock (released in `finally`). Pinned 2,393 pending/failed EuroEval definitions,
requeued all 42 registry-related failures with original logs/attempts preserved,
and reset six completed averages/reports for recomputation. No claimed definition
was edited. Definition/path preflight: **20,183 pending, zero failures**.
Receipt: `euroeval-runtime-repair.json`.

Coordinator **488907** (`runner12.log`) is running with online W&B and private
TMPDIR. `verify_pinned_resume.py` monitors actual training progress beyond 600K;
`resume-status.json` now refers to this coordinator. The previous online-transition
watcher belongs to runner11 and is superseded. Checkpoint/cursor, LR and 900K decay
start are unchanged. Completed inference is preserved; the 600K block therefore
contains already-completed 17.3 results plus repaired 18.1 results, not a claim of
one homogeneous dependency version. Future unstarted EuroEval jobs are pinned.

Also resolved the finished-results publication snapshot: `publish_finished_snapshot.py`
used the shared writer lock and a fresh explicit history step. Cloud history
verification passed for **all 1,212 fields in 124 files**, zero mismatches; receipt
`finished-snapshot-published.json`. This supersedes the earlier incomplete snapshot
check, without asserting that later unfinished evaluations are already published.

Live verification after restart: pinned 18.1 clients are present, Dutch
`multi-ifeval-nl` now loads the correct dataset and processes examples, and
`alba-mcq-pt` likewise proceeds through benchmark iterations instead of registry
failure. At this check 600K had **2,105 done / 44 running / 54 pending / zero
failed**. The retries are running, not all complete. OKF validation still reports
only the previously known oversized `request-shared-eval-scheduler.md` concept
and 14 pre-existing unresolved-link warnings; no new wiki validation category.

### 2026-11-05 18:37 CET: recovery completed, training advancing

Live SQLite confirms **all 2,203 jobs in the 600K evaluation block are done**,
with zero failed/pending/running eval rows. This includes the publication and
aggregate jobs. Coordinator runner12 has dispatched `b-dfm15-train-650000`;
the live monitor shows actual progress at **603,845/650,000**, all eight GPUs
at 99–100% utilization, and an estimated 3h57m to the next boundary. This
supersedes the earlier waiting/retry status and establishes actual recovery
beyond the 600K checkpoint. ETA is a live throughput estimate, not a deadline.

### 600K score comparison against 550K

Compared the complete `headline_avg_dala_v2` populations with identical definition
hash `a822b2a990f88b125c0acd05594729131be5e2e5aa4d7f01db66b95437e6bf96`:
Danish 51.7242% → 51.1219% (-0.6024 pp; 20/20 tasks), English 58.3317% →
58.9658% (+0.6341 pp; 17/17), and overall 38.2265% → 39.0369% (+0.8104 pp;
61/61 tasks, eight sections). These are descriptive movements, not significance
claims. W&B summary confirms the 600K expanded headline values.

Notable Danish task changes: strict DALA 65.12% → 46.23%, strict GEC 11.33% →
2.64%, ScaLA 56.97% → 47.64%; offset partly by PIQA 48.15% → 71.30%, sentiment
59.24% → 65.09%, and both instruction-following metrics gaining about 2.7 pp.
Strict GEC is exact-match and previously showed formatting sensitivity; a new
output-level diagnosis is needed before interpreting its full decline as grammar
ability loss. The checkpoint is better overall but does not establish Danish
recovery. Preserve the mixed EuroEval runtime caveat from the repair above.
Comparison artifact: `docs/reports/b-dfm15-600k-comparison-20261105.json`.
Legacy v3 averages in that artifact have a different population and must not be
substituted for the expanded headline comparison.

### 2026-11-05 prepared only: full third-epoch cosine alternative

The user requested a **copy**, not activation: no cosine decay in epoch two,
then cosine from the start to the end of epoch three. Implemented
`scripts/stage_b_dfm15_epoch3.py` and staged an online-backup snapshot without
stopping or editing the live coordinator/trainer. Schedule: LR **3e-4** through
**1,025,846**, cosine to **1e-5** at **1,538,769**, with no flat tail. Epoch length
remains 512,923 steps. Optimizer/data/EMA settings and run identity are retained.

- Local staged database: `/tmp/dfm15-B-production/jobs_epoch3_stage.sqlite`.
- Persistent snapshot: `logs/scheduler/B_dfm15_gemma4_epoch1_20261103/epoch3-stage-20261105/jobs.sqlite`.
- Review receipts: `manifest.json`, `validation.json`, `preflight.json`, and
  `resolved-training-config.yaml` in that same directory.

The copy contains 72,733 jobs, adding 24,244 rows across eleven training/eval
blocks: 1,050K through 1,500K at 50K intervals, then 1,538,769. Each new eval
block has 2,203 jobs, cloned with canonical shared result paths and the pinned
EuroEval 18.1 launcher. Epoch-two end becomes an intermediate suspension; only
epoch-three end is final (`epoch_3`). Both training command representations use
the full new horizon. Pending training/checkpoint gates expand administrative
barrier/teardown references to real work, with terminal-mode train gates and
success-mode checkpoint gates. Existing completed records remain preserved.

The staged database is deliberately admin-locked and has no live claim tokens.
The copied active training claim was normalized to pending **in the copy only**;
its old token/attempt are recorded. A new cooperative control root is staged.
Source definition hashes matched before and after preparation; live admin lock
stayed zero. Never replace the live DB directly with this aging snapshot: reconcile
current statuses at a selected checkpoint pause. The active trainer loaded the
old LR schedule at launch, so later activation requires a controlled checkpoint
restart preserving exact cursor, optimizer and EMA, with one recovery supervisor.
No activation watcher was armed and the current 900K–1M decay remains live.

Verification: graph/cycle and dependency-target checks passed; all **44,080
pending jobs** passed definition/path preflight; real Hydra `--cfg job --resolve`
dry run passed with exact new schedule; **nine focused tests passed**, including
cosine endpoints/midpoint, no epoch-two decay, command parity, final-boundary
handling, path cloning and barrier expansion. The scheduler rejects authoritative
SQLite on WekaFS, so run preflight against the local staged copy, not its persistent
snapshot. This is preparation validation, not an executed epoch-three resume.

### 2026-11-05 authorization: activate epoch-three schedule at 650K

The user subsequently instructed **“change at the next eval.”** This supersedes
the prior preparation-only authorization. `scripts/activate_b_dfm15_epoch3.py` is
armed at the upcoming **650,000** pause; detached controller PID **874765**.
Receipts are under `epoch3-stage-20261105/activation-650k/` (`armed.json`,
`status.json`, `controller.log`, then `applied.json` and `handoff-verified.json`).
At arming, training was still at approximately 649,045; no switch claimed yet.

The controller verifies the 650K checkpoint and scheduler hold, checks old
launcher/supervisor identities, and takes a short live dispatch fence. It merges
only pending definitions and absent new rows from the staged copy, preserving
current completion states and active claim tokens. Passed suspension boundaries
are removed. It backs up live SQLite, runs live preflight, stops the identity-
verified old launcher for one checkpoint restart, verifies its supervisor also
exits, and releases the fence in `finally`. Evaluations continue; the 700K train
row resumes `step_650000` under the fresh staged control root and full third-epoch
schedule. A live-supervisor command check plus observed step >650K is required
for `handoff-verified.json`; `armed` or `applied` is not proof of resumed training.

Seven focused staging/activation tests passed, including preserving active
claims/completed rows, pending-only reconciliation, rollback of definitions, and
removal of the already-passed suspension. Do not arm a second controller or
replace the live database wholesale with the staged snapshot.

### 2026-11-05 22:30 CET: third-epoch schedule applied at 650K

`activation-650k/applied.json` confirms the verified 650K handoff: 16 existing
pending definitions updated, 24,244 extension rows added, and the old launcher /
supervisor exited. Live administrative lock is zero. The 650K eval block is now
running (three done, nine running at this check); the 700K continuation remains
pending, so actual resumed training under the new schedule is **not yet verified**.
No `failure.json` was present. New continuation commands explicitly contain
`epochs=3`, total 1,538,769, decay 1,025,846–1,538,769 and suspensions from 700K
onward. All future training rows retain the cooperative CUDA-checkpoint launcher
and shared fresh control root; the 650K disk restart is the intentional schedule
change, not a replacement of later offload/eval/in-place-resume cycles.

### 2026-11-06: third-epoch handoff and CUDA resume verified

`activation-650k/handoff-verified.json` records the new supervisor 1694457 and
actual progress at 650,010 under the authorized three-epoch schedule. At 06:45
CET training had reached 736,295. Recent progress from 731,400 at elapsed
7:20:24 to 736,295 at 7:44:53 gives 0.3001 seconds/step including routine
checkpoint overhead; instantaneous progress is about 3.44 steps/s (0.291 s/step).

The 700K CUDA suspension completed successfully: checkpoint-ready at
03:11:03.814 CET, offloaded at 03:11:28.764, restored at 03:44:31.184 and resumed
at 03:44:34.845. Total checkpoint-ready to resume: **33m31s**. Restored rank
identities match the original suspended ranks; this was in-place CUDA restoration,
not a disk-checkpoint relaunch. Timing uses protocol event `ready_at` and atomic
receipt file timestamps. This supersedes the earlier unverified-resume status.

### 2026-11-07 08:26 CET assessment before epoch-three decay

Training reached approximately 1,003,680, with actual logged LR still 3e-4.
The active supervisor retains decay 1,025,846–1,538,769. All 2,203 evaluation
jobs at each boundary through 1M are done. Expanded-headline coverage is complete
and the definition hash is unchanged at 700K, 800K, 900K and 1M. Respective
Danish/English/overall percentages are 52.81/57.10/41.13,
51.45/57.58/41.85, 53.50/56.28/42.25 and 53.79/57.36/42.57.
Overall progress continues with smaller recent increments; English is broadly
flat/noisy, while Danish at 1M exceeds the 550K score.

Local training W&B records, using the final 10K steps before each boundary
(2,000 observations/window), give mean loss 1.14353, 1.13382, 1.13525, 1.12712
and mean accuracy 75.669%, 75.840%, 75.813%, 75.968%, respectively. These are
descriptive windows over changing training batches, not significance tests or
held-out validation losses. Assessment: keep the already authorized gradual
third-epoch cosine start; no evidence here warrants postponing it or emergency
cooldown. At the observed 0.30s/step, the boundary is roughly 1h51m away plus the
usual 30–33m evaluation pause before epoch-three training resumes. No schedule
change was made by this assessment.

### 2026-11-09 epoch three finished; final-evaluation checkpoint repair

Training completed epoch three at **actual step 1,538,766**, with
`checkpoint_state_epoch_3.json` written at 12:14:19 CET. The planned endpoint
1,538,769 exceeded actual epoch completion by three updates. At 12:39 the train
row was done, but final evaluation was stranded waiting for nonexistent
`step_1538769`. Do not report that evaluation was running during this wait.

Verified the complete `fsdp2_epoch_3` DCP using metadata storage offsets and shard
sizes. Gracefully stopped runner12 (its checkpoint waiter returned pending),
acquired the runner lock, backed up SQLite, and changed all 2,202 pending final
eval definitions to read `epoch_3` and label outputs at actual step **1,538,766**,
epoch **3.0**. Output paths likewise use the actual step; stable job IDs retain
the planned endpoint for lineage. No completed results, training state or
checkpoint contents were rewritten. Administrative lock cleared in `finally`.

Repair script/backup/receipt: `final-epoch3-repair-20261109/` beneath the B plan.
Pending-job path/definition preflight passed: 2,202 checked, zero failures.
Restarted the online SQLite/persistent-vLLM coordinator in `runner13.log` with
private TMPDIR. Training is finished; only final evaluation/publication remains.
Future staging must not assume the estimated epoch budget exactly equals the
actual final optimizer step; resolve final evaluation from the completed epoch
checkpoint rather than waiting indefinitely for a planned step tag.

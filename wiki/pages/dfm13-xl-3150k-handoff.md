---
type: Plan
title: DFM13 XL Handoff at 3150K
description: Readiness-gated preparation for switching the original XL run from DFM12 to DFM13 after its 3150K evaluation.
status: stable
confidence: high
last_updated: 2026-10-06
tags: [dfm13, training, xl, handoff]
---
# DFM13 XL Handoff at 3150K

## Authorized Pause at3154500 (2026-10-06)

**Resumed 2026-10-06 10:35 CEST; supersedes the paused prelaunch state below.**
Cleared the stop request and restarted the existing scheduler with persistent
vLLM in the `hrm` environment. The existing training row resumed the complete
`ephemeral_step_3154500`, preserving optimizer/data state and the original
`dfm8-xl-from-dfm6-dfm7-epoch5-clean-full` W&B run. Verified actual progress
through3154525 with all eight GPUs at100% utilization. Recent five-step
intervals take approximately6seconds after compilation. Target remains3200000.
Log: `logs/training/dfm13_XL/step_3200000/resume-3154500/train_until_step_3200000.log`.
The readiness receipt's `not_launched=true` describes prelaunch only.

**Final prelaunch state: READY, NOT LAUNCHED, user pause retained.** All plan
pipelines are installed:42 additive tasks at11 checkpoints,10 future
Talemaader-only averages,11 atomic expanded averages, and serialized deferred
workspace updates for34 population panels plus four expanded panels. The latter
depend on their actual3150 successor averages and gate3200 startup. Historical
sync/panel work is not replayed. No pending VALEU rows.
Forty-nine combined focused tests passed. Actual segment epoch-update predicate
was checked against10,760 pending future rows with epoch metadata: all match
the `dfm13-xl-` prefix and correct checkpoint tag. Provisional epochs are replaced
by actual fractional consumed-row epochs after their checkpoint completes;
no fixed10.609 value is treated as final future output. No training source edit
was needed for this coverage. All pending source pins and training pins verify.
`runner-resume-ready.json` now says `ready=true`, `not_launched=true`, with
pause reason user request; obsolete logging-spacing blocker removed. Exact
optimizer3154500 checkpoint/cursor retained, scheduler stop marker present.

Expanded averages now INSTALLED:11 native AVERAGE rows with headline prefix
`headline_avg_dala_v2` plus extra `[suite_avg_dala_v2]`, one atomic writer after
every other checkpoint averager. All actual runtime argv were captured without
execution: direct `/home/ucloud/miniforge3/envs/hrm/bin/python`, expanded logger,
both namespaces (no `--metric-prefix`), all additional roots, no training or
Talemaader wrapper. Fifteen focused tests pass, including real argv construction.
Receipts: `data/dfm13/expanded-dala-v2-average-plan-20261006/{installed,verified}.json`.
Await Boole's deferred four-panel expanded mapping; no history was rewritten.
Scheduler remains stopped.

Expanded traditional averages: scoped REPORT installer
`scripts/schedule_expanded_dala_v2_averages.py` prepared11 rows,3150K through
final3641017. CLI uses standalone `log_expanded_dala_v2_averages.py` with all
standard/DFM/Euro roots, legacy plus wave34/v2, no `--metric-prefix` (both
namespaces atomic). Dependencies include all non-skipped checkpoint eval/merge
and average rows; baseline report gates WAIT3200, later reports gate following
training. Thirteen focused tests passed. Preview is under
`data/dfm13/expanded-dala-v2-average-plan-20261006/`; await Harvey's frozen
implementation before installation. Scheduler remains stopped.

Superseding expanded scheduling design: parent requested native AVERAGE, one
row per checkpoint with `average_prefix=headline_avg_dala_v2` and
`extra_average_prefixes=[suite_avg_dala_v2]`. Preview now uses this exact shape,
all extra roots, and dependencies on every existing checkpoint averager in
addition to eval/merge producers. Thirteen focused tests pass. Installation
explicitly refuses the older one-prefix-only runtime until Harvey's atomic
both-prefix dispatch lands. No expanded row installed yet; still paused.

Logging-spacing gate resolved locally: frozen helper hash
`0803f49bfa4b031ff362276a6b09e8db57c75b4def8d9b1d0e64c7ae4aa72dfe`
installed as the ONLY changed source pin. Existing `pretrain.py` and every
other pin verified unchanged; full readback passed. Old receipt archived and
`logging-spacing-pin-refresh.json` records the delta. Thirteen focused logger
and workspace scheduler tests passed. Still stopped pending all average plans.

Actually installed CPU workspace row `dfm13-xl-v2-population-workspace` depends
on `dfm13-xl-dala-v2-step_3150000-average`, NOT the earlier v1 average. WAIT3200
depends on this workspace row. It runs remote complete3150 verification, fresh
prepare and apply for `population-v2-mapping.json`, with the explicit v2
population config on all commands. No historical mapping/history writer.
Receipt: `data/dfm13/v2-population-workspace-plan-20261006/installed.json`.
Parent reports42 raw panels and five historical panels already applied; this
row only adds the15 deferred v2 population panels after real baseline results.

**Current launch gate: logging-spacing fix pending.** Parent found training
panels use internal `_step`; automatic cursor appends compress five-step log
spacing. No launch is authorized until Poincare freezes the monotonic logging
offset fix and helper tests/pins are refreshed. Optimizer remains3154500.
The prior runner readiness receipt is archived and current `runner-resume-ready.json`
now has `ready=false`. Stop marker and absent original training/scheduler PIDs
were reverified. Do not treat earlier readiness statements below as authorization.

While paused, installed42 additive accepted-v2 DaLA/GEC tasks at3150K and every
future evaluation boundary (11 checkpoints):2,321 new rows including separate
v2 population averages. Receipts: `data/dfm13/dala-v2-plan-20261006/installed.json`
and `verified.json`;24 scheduler tests passed. Legacy datasets/averages remain.
Baseline3150 successor average gates WAIT3200; later successor averages gate
next training. Terminal cleanup barriers include all new GPU work without
success dependencies on teardown. Exact3154500 resume row is unchanged.

Authorized logging-only source pin refresh is archived in
`logs/dfm13/pause-3154500-20261006/logging-pin-refresh.json`, with the old
`scheduler-installed.json` preserved alongside it. Only frozen `pretrain.py`
hash changed and `utils/training_wandb.py` was added; other pins validated.
Parent completed raw67 and average67 sync (next internal step3154630), while
optimizer checkpoint remains3154500. No historical-average writer was installed
in the plan. Existing raw sync row is idempotent against `synced.json`.
Scheduler remains stopped, awaiting parent authorization after panel completion.
Final prelaunch recheck: all source pins valid, raw67 and average67 sync receipts
present,26 combined training-logger/scheduler tests pass. Exact existing-runner
launch argv/environment are recorded in
`logs/dfm13/pause-3154500-20261006/runner-resume-ready.json`; not launched.

TODO5 future correction: separately installed10 Talemaader-only successor
AVERAGE rows (3200K through3641017) using
`scripts/schedule_todo5_future_averages.py`. Receipt:
`data/dfm13/todo5-future-averages-20261006/installed.json`. Each depends on the
checkpoint's native Talemaader merge; following training depends on the new
average. Opt-in keys are `headline_avg_talemaader_v2` and
`suite_avg_talemaader_v2`; strict-DaLA guard uses a dedicated executable wrapper.
Legacy rows are unchanged. No historical backfill writer was installed.
Twenty scheduler tests passed. Expanded Danish/English/DFM-suite definitions
including new DaLA-v2 tasks remain a separate Poincare handoff, not yet installed.
Parent confirms five historical panels applied. Plan remains paused.

**Resume prepared, not launched:** under PlanLock the interrupted train3200
row was set PENDING/attempt0 with `resume_from_tag=ephemeral_step_3154500` and
`resume_ckpt_path=checkpoints/dfm13/XL-from-dfm12-step3150000` (absolute in plan).
Existing base command, implementation pins, optimizer/global step and all
other rows are unchanged. New log subdirectory `resume-3154500` preserves
interruption logs. Scheduler's own checkpoint-ready check passed. Stop marker
remains; no scheduler/training restart. Authoritative exact runtime argv and
cursor receipt: `logs/dfm13/pause-3154500-20261006/resume-plan-prepared.json`.
This supersedes the earlier proposal: resume arguments are injected by scheduler
metadata, not present in the base command. Await parent sync/logging completion.

**Completed:** full DCP checkpoint preserved and exact torchrun signaled only
after completeness validation. Torchrun2095661, segment2095541 and scheduler
2095427 exited; stop marker remains. `stopped.json` and `verified.json` confirm
step3154500, exact batch9000 and global row cursor3358016. Resume proposal is
`logs/dfm13/pause-3154500-20261006/resume-proposed.json`, not executed. It uses
the original checkpoint output root and exact ephemeral tag accepted by the
existing segment wrapper; preserved hardlinks remain the independent backup.
No optimizer step offset, no automatic resume, no extra evaluation plan edits.

User authorized a temporary stop at fully written `ephemeral_step_3154500`
for synchronization work. Scheduler `stop.request` is set. Checkpoint-safe
watcher2148878 (`scripts/pause_dfm13_3154500.py`) is armed against exact
torchrun2095661, using pidfd identity, existing DCP byte-extent completeness
validation and preservation helpers. It waits before signaling; no premature
checkpoint or optimizer-step adjustment. Preservation target:
`checkpoints/preserved/dfm13-pause-3154500`; receipts:
`logs/dfm13/pause-3154500-20261006/`. No automatic resume, no other plan edits
until stop secured. Check `stopped.json` before claiming actual completion.
The existing segment wrapper accepts continuation from its original output
root, so an eventual resume command should use that root and the exact ephemeral
tag, with the preserved hardlinks retained as backup. Do not resume until parent
synchronization is complete and the explicit-step logging decision is resolved.

## Deferred Wave3/Wave4 Baseline Preparation (2026-10-06)

**TODO5 logging-decision hold:** parent stopped installation of historical
writers pending user choice on W&B high-water handling. No TODO5 rows installed.
Final compatible payload pins now validate. Local-only sidecar publisher is
implemented/tested, ready to substitute for the pending TODO3 sync executable
if history appends are deferred. Parent requested waiting briefly before plan
edits; current training is untouched. See the TODO5 handoff for exact state.

TODO5 scheduling interface is prepared in
[the deferred average-sync handoff](../../docs/reports/dfm13-todo5-scheduler-interface-20261006.md).
Await Poincare's versioned-average artifacts/CLI before installing an additional
CPU sync after Talemaader and before baseline GPU work. Historical67-point
backfill must use available metrics only; the new34-language populations apply
at the new3150 baseline onward. No TODO5 plan or W&B changes made yet.
Follow-up CPU check: average-preparation module exists and27 combined tests
pass; deferred W&B sync CLI and future-average version mapping remain pending.
Training row verified identical to the v2 installation backup; all2,388 new
evaluation rows remain pending.
Subsequent TODO5 update: `--sync-prepared <payload> --paused-step 3200000` now
exists;35 combined tests pass and rejudge completion receipt exists. Awaiting
final payload/hash and future-version mapping only; missing-sync-CLI claim
above is superseded. No history writes or further plan edits performed.
TODO5 adapter is now implemented with20 scheduler tests passing, but installation
is blocked by a stale payload input hash for `scripts/log_dfm5_headline_averages.py`.
Await Poincare's regenerated payload; never bypass source hashes. Future logger
wiring and paused-sync W&B high-water handling remain pending. Training unchanged.

**Current: corrected v2 installed on 2026-10-06.** This supersedes the withdrawal
below. Tesla's refreshed semantic coverage pins verified; 60 combined semantic,
registry and scheduler tests passed. Installed2,388 rows under PlanLock using
`data/dfm13/wave34-eval-baseline-20261006-v2/`; see `installed.json` and
`post-install-validation.json`. Current training3200 remained RUNNING and
unchanged, new rows PENDING. Old teardown dependencies are unchanged; only
pending terminal barriers gain GPU dependencies. Matching family/category
templates preserve calibrated runtime settings. Ordering remains train3200 ->
Talemaader sync -> baseline3150 complete averages/cleanup ->3200 evaluations,
with new coverage through final3641017. Existing21 datasets were not replaced.

**Latest state: withdrawn pending semantic fix.** Parent identified new13 merge
incompatibility after installation. All2,388 pending/unattempted additions were
withdrawn under PlanLock and ten dependency extensions restored, preserving
live training/statuses. Tesla is correcting semantic aliases, end-to-end tests
and population bindings. Await a final corrected manifest before reinstalling;
the installed-state paragraph below is superseded. Durable withdrawal receipt:
`data/dfm13/wave34-eval-baseline-20261006/withdrawn-pending-semantic-fix.json`.

Scheduler review fixes (CPU only, not reinstalled): extend pending old terminal
barriers, never add GPU success dependencies directly to old teardown. Fresh
cleanup remains required even when historical cleanup rows are already DONE.
DFM templates now match DaLA versus GEC families; EuroEval templates match
category across languages. Preserve their batch, concurrency and server args,
recording inherited capacity rather than claiming calibration of new tasks.
Regression tests cover failed GPU work allowing cleanup while blocking averages
and future training, plus cleanup completion before training can resume.

TODO3 prepares new3150K coverage to run ONLY after current training reaches3200K,
immediately before3200K evaluations. No baseline starts now. Proposed order:
train3200 -> CPU Talemaader v2 `sync --wait` -> new3150K evals/complete averages
and teardown ->3200K export/evals/averages -> next training. New coverage also
extends every planned later boundary. Original run/project retained; no VALEU.
`scripts/schedule_dfm13_wave34_baseline.py` provides prepare/install under PlanLock.
Preparation-only state superseded on 2026-10-06: installed 2,388 new rows under
PlanLock after Tesla's completed coverage receipt. Training3200 remains RUNNING
and its entire row is unchanged. All new rows were verified PENDING. The existing
REPORT `python_bin` hook dispatches the isolated `talemaader_v2_scheduler_sync`
executable; no scheduler runtime reload or training script change was needed.
The sync bridge validates completed3200 training and absence of a running
training writer, then executes `sync --wait`. Fatal rejudge failure cannot unlock
the baseline. Missing historical checkpoints are exclusions in the owner's
locally-available rejudge manifest, not manufactured completions.
Coverage is 26 DaLA tasks and 84 EuroEval datasets at 11 checkpoints, including
3150K and final3641017. Fourteen focused tests passed. Installation backup,
receipt and post-install proof are under
`data/dfm13/wave34-eval-baseline-20261006/`. No GPU or W&B call was made.
See [interface and safe dependency handoff](../../docs/reports/dfm13-wave34-baseline-scheduler-handoff-20261006.md).

## Optional Eval Gate Recovery (2026-10-06)

The first training launch then failed before its first update: the BP schedule
divided by `bp_warmup_ratio=0`. The model now explicitly treats zero as disabled
warmup, returning `bp_max_steps` immediately. Positive-warmup behavior is
unchanged; both cases have regression tests in `tests/test_bp_warmup_zero.py`.
Only the failed first DFM13 training row was reset and the same scheduler resumed.

**Superseded later on 2026-10-06:** the owner removed VALEU entirely from
future evaluations. Default EuroEval catalog entries were removed; unattempted
`valeu-*` rows were removed from the active plan under lock, with a backup and
ID receipt (`removed-valeu-20261006.json`). Historical results remain intact.
Do not reintroduce VALEU when cloning historical campaigns. Scheduler dependency
evaluation also ignores VALEU edges in legacy plans for every job status;
required non-VALEU dependencies retain their normal semantics. VALEU remains
excluded from averages. Training was not restarted by this policy change.

Supersedes the blanket success requirement below for optional `valeu-*` tasks.
The 3150K campaign ended at 02:14 with GPU servers cleaned up, but a failed
`valeu-no` blocked the DFM13 readiness/training gates. Under the owner's prior
policy, failed valeu tasks must not block training and are excluded from averages.
The locked plan repair removed dependencies on failed/retired valeu rows and
skipped future `valeu-no`, `valeu-nl`, and `valeu-pl` tasks. Historical failures
remain recorded; required evaluation, merge, and average dependencies remain.
Backup and detailed 41-row repair receipt are in the campaign directory as
`plan.before-valeu-unblock-20261006.tsv` and `valeu-unblock-20261006.json`.
The same persistent scheduler was restarted from the hrm environment.
Future handoff generation must preserve this optional-task exception; the
existing generator's blanket non-skipped dependency rule is not sufficient.

Following the [DFM12 progress assessment](dfm12-xl-epoch11-noidentity.md),
the owner requested preparation conditional on verification finishing.
This prepares the successor; it does not silently change the live campaign.

## Authorized Automatic Handoff (2026-10-05)

**Supersedes the preparation-only status below.** The user authorized the switch
after all3150K evaluations and averages. `scripts/schedule_dfm13_xl_handoff.py`
now owns the scheduler transition, without changing the running3150K segment or
the sample validator. Under `PlanLock`, it archived the original plan at
`data/dfm13/xl-from-dfm12-step3150000/plan-before-handoff.tsv` and retired2,660
unattempted post3150K DFM12 rows (four training segments and their evaluations).
All4,405 earlier/current rows, including the665-job3150K block, were retained.
`scheduler-armed.json` binds the backup and removed IDs.

The plan also has `dfm13-handoff-resume-ready`, a normal CPU `wait_checkpoint`
row depending on every non-skipped3150K job. It waits for the **real isolated
resume checkpoint**, not a fabricated completion marker. This keeps the existing
persistent scheduler alive if the sample arrives after3150K evaluations finish.
No second scheduler or GPU process is launched by the finalizer.

Detached CPU finalizer PID797327 runs:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m scripts.schedule_dfm13_xl_handoff watch
```

Log: `logs/dfm13-xl-handoff-scheduler.log`. The control directory above contains
`scheduler-launch.json`, `scheduler-progress.json`, and eventually
`scheduler-installed.json`; installation failures produce
`scheduler-failure.json`. The prior CPU finalizer796851 was stopped solely for
a small lock-dispatch correction; its launch receipt is preserved. The existing
packing watcher715684 and sampler791900 were not stopped or duplicated.

Once the existing watcher publishes `prepared.json`, the installer rechecks the
sample contract/current provenance and appends a clone of the **current expanded
3150K evaluation block**, including multilingual extensions, semantic averages,
judge settings and native no-Mistral-fix tokenizer configuration. It does not use
the historical290-job template. Every non-skipped preceding evaluation, merge,
report, teardown and average must succeed before the next training segment;
failed work blocks progression rather than being treated as successful.

The isolated resume uses unchanged hard-linked DCP payloads (weights, optimizer,
EMA) and atomically replaced private metadata. Source3150K remains untouched.
Global step stays3,150,000; trainer epoch1 selects dataset `epoch_0`, with exact
batch0 and row0, carry policy `none`. Arguments select `data=dfm13`, target-only,
one epoch, GAS2, BP8 with **BP warmup0**, FSDP fp32/bf16, original W&B run, base
LR3e-4 with `lr_auto`, no rewarm, and final50K cosine decay to1e-5. All eight GPUs
must satisfy the retained178000MiB headroom gate; no process is killed for space.

Evaluations occur at3200K,3250K,... and natural `epoch_1` end. The exact end step
comes only from the existing packing count. The final stop bound is end+1 so
natural exhaustion writes `epoch_1`. Each segment updates its evaluation display
epoch from **actual**3150K DFM12 row fraction plus actual DFM13 consumed-row
fraction, before dependent evaluations can start. No approximate step fraction
or assertion of a completed DFM12 epoch is used.

Validation:34 combined tests passed (14 upstream Torch deprecation warnings),
including the real expanded plan, Hydra composition, explicit stop bound,
the actual `resolve_resume_state` loader, cursor reset, source-metadata
preservation checks, readiness dependencies and display epoch mapping.
Tests: `tests/test_schedule_dfm13_xl_handoff.py`,
`tests/test_prepare_dfm13_xl_handoff.py`, `tests/test_schedule_dfm12_xl_epoch11.py`.
At handoff setup, DFM13 training has **not** started; sample scans and exact
packing are still prerequisites, not bypassed by this scheduler authorization.

## Verification and Sampling

### Monitor dependency traversal (2026-10-05)

Window4 froze at19:18 despite continued training. A timed read-only traceback
located repeated recursive `_cannot_succeed` traversal of shared campaign
ancestors, not stale training logs. Replaced that traversal with iterative
reachability visiting each job at most once per query, retaining terminal,
running, completed, failed and skipped semantics. All27 campaign tests passed;
the expanded11,056-job snapshot rendered in5.855s. Restored the Rich monitor
in `hrm-1:4` with30s interval, showing current step3138840 at20:06. Neither
training nor the running scheduler was restarted. The already-loaded scheduler
process does not pick up this runtime code change until a safe restart.

On 2026-10-05 the active verifier was processing source 523 of 606,
Dutch baseline DaLA acceptability, followed by another 83 registry entries.
Approximately 24 GB of source JSONL remained at the initial handoff check.
This is not 83 missing downloads; these are pending verification entries.
Checksums, the Setur/fo-instruct repeat-10 successor, composition reconciliation,
sampling and full token/index scans remain necessary. The existing verifier,
composition watcher, reconciliation watcher, Faroese successor and sampler
were all running. They must not be restarted just to prepare this transition.

Verification should finish if no new failures arise, but completion before
3150K is not guaranteed. At step 3126085 and about 1.22 seconds/step, training
alone needs another 8.1 hours to reach 3150K, then its evaluation takes time.
Source JSONL throughput alone cannot predict checksum and sampling I/O tails.

The sequential verification snapshot above was superseded later on 2026-10-05
by the owner-authorized [32-worker restart](dfm13-parallel-verification.md).
The restarted registry includes Faroese directly and contains 607 entries;
135 need verification beyond the published predecessor. Consult the parallel
progress JSON rather than the old sequential source ordinal.

## CPU Preparation

`scripts/prepare_dfm13_xl_handoff.py --watch` waits for
`data/dfm13/sampling-20261005-v1/completion.json`. It checks complete vocabulary
and index scans, 4K metadata, current assembly/composition/reconciliation pins,
and inclusion of Setur/fo-instruct at repeat 10. Only then it calculates exact
packed optimizer steps using the training sampler: 8 ranks, 16384 tokens per
rank per microbatch, GAS2, drop-last semantics.

Outputs are under `data/dfm13/xl-from-dfm12-step3150000/`:

- `progress.json`: waiting, packing, or prepared status.
- `packing.json`: exact budget and sampled-input signatures.
- `prepared.json`: proposed start/end, evaluation boundaries and continuity policy.
- `failure.json`: fail-closed preparation error, if any.

This CPU watcher never launches training, touches W&B, modifies checkpoints,
or edits the active scheduler plan. Log: `logs/dfm13-xl-handoff-prepare.log`.

## Proposed Continuation

- Parent is the original XL `step_3150000`, not an identity-trained checkpoint.
- Reuse DFM5 run `dfm8-xl-from-dfm6-dfm7-epoch5-clean-full`.
- Preserve weights, optimizer and EMA; use XL/GAS2/GBS262144 as currently.
- One full DFM13 pass from its row zero; do not reuse the DFM12 batch/row cursor.
- Separate output: `checkpoints/dfm13/XL-from-dfm12-step3150000`.
- Proposed base LR 3e-4 with `lr_auto`; no automatic cooldown/rewarm at handoff.
  Proposed cosine cooldown over the last 50K DFM13 steps to 1e-5.
- Keep evaluations at clean 50K boundaries, starting 3200K, plus final endpoint.

Before activation, inspect the completed 3150K evaluation and averages, validate
isolated resume metadata with carry policy `none`, and install scheduler rows
under the plan lock. The original checkpoint must remain untouched. Fractional
evaluation epochs must continue from the actual consumed DFM12 fraction, not
claim the truncated DFM12 pass was a completed epoch. Internal loader epoch
mapping and display epoch mapping must be explicit and tested before launch.
Historical preparation-only state (superseded above): the active plan still
contained DFM12 continuations beyond3150K and no automatic handoff.

---
type: Experiment
title: DFM11 recurrent B versus Transformer48 alternating training
description: Full-backprop causal B preparation and disk-backed 50K alternation after both models reach 150K.
status: draft
last_updated: 2026-11-12
confidence: high
---
# DFM11 architecture comparison

The user requested stopping Transformer48 after its 150K evaluations, retaining
a complete disk restart checkpoint, then preparing a recurrent B model on the
same DFM11 epoch. Once B reaches 150K, alternate models every 50K. The user
explicitly selected full backpropagation for compute matching.

B uses `models/baselines/hrm_nocarry_bp_warmup.py` through `arch/net=hrm` and
`arch/size=B`: 12 independent layers, split into six-layer H and L stacks,
width 1024, eight heads, H=2/L=3. `bp_min_steps=bp_max_steps=8` and
`bp_warmup_ratio=0` retain gradients through all eight stack calls from step 1.
That gives 48 forward and backward block applications, matching Transformer48's
block compute; optimizer costs and recurrent additions still differ. Verified
parameter counts: 703,594,496 total, 166,723,584 excluding embedding and LM head.

Both use immutable `data/sampled_dfm11`, seed 0, causal attention, full-token
loss (`data.target_only=false`), 262,144-token global batches, LR 3e-4 after
5K warmup, flat thereafter, and one epoch ending at actual data exhaustion.
The approximate endpoint remains 393,732 steps. FSDP/bf16 settings, regular
50K/epoch checkpoints, ephemeral 500-step checkpoints and eval coverage match.

## Transformer stop

The active transformer DB remains `/var/tmp/dfm-transformer48-evals/jobs.sqlite`.
Pending work after 150K was archived in
`logs/scheduler/transformer48_dfm11_causal_epoch1_20261109/future-rows-before-alternation.json`
and removed transactionally; its active training claim was unchanged. A full
SQLite backup precedes that edit. The detached watcher
`scripts/stop_transformer48_after_150k.py` waits for the 150K block to finish,
checks checkpoint completeness and suspension identity, and requests supervisor
shutdown without restoring CUDA. Stop receipts live under that plan's
`stop-after-150k/`. It is armed, not evidence that 150K already finished.

## Prepared alternating plan

- Plan: `logs/scheduler/dfm11_architecture_comparison_20261110`.
- Durable database: `/var/tmp/dfm11-architecture-comparison/jobs.sqlite`.
- B run: `B-dfm11-causal-fullbp-alltokens-epoch1`.
- B artifacts: `logs/training/B_dfm11_causal_fullbp_20261110`.
- B checkpoints: `checkpoints/hrm/B-dfm11-causal-fullbp-alltokens-epoch1`.

Order is B50K, B100K, B150K, T200K, B200K, T250K, B250K, T300K, B300K,
T350K, B350K, T epoch end, B epoch end. Every boundary includes full evals.
B's first three intervals use in-memory CUDA suspend/eval/resume. Model switches
verify offloaded predecessor state, stop its owned supervisor/workers, and
resume the other model from its stored checkpoint. There is one recovery
supervisor per active model; unknown GPU workers are never killed. Existing
peer identities and the shared-headroom gate are retained.

All 28,652 jobs are prepared and pending; no new training runner was launched.
`prepare_dfm11_architecture_comparison.py` refuses to overwrite its database.
The launch helper defaults to a dry run and requires the old 150K stop receipt,
a dead transformer launcher and a complete 150K checkpoint before execution:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python scripts/launch_dfm11_architecture_comparison.py
# When starting the prepared comparison:
/home/ucloud/miniforge3/envs/hrm/bin/python scripts/launch_dfm11_architecture_comparison.py --execute
```

## Validation and limits

The 28,652-row script/path preflight passed. The resolved B config is hashed in
the plan manifest. Tiny CPU native/HF parity, future-token causality and full
gradient flow through all eight calls pass. The isolated vLLM plugin now
registers causal recurrent HRM as well as Transformer48, and HF export derives
PrefixLM mode from the actual architecture attention setting. Ordinary PrefixLM
exports retain their default. Final-epoch metric binding now filters by model
checkpoint root, avoiding cross-model rewrites in the shared database.

Four cooperative-training tests pass, including refusal to stop a resumed or
unverified predecessor. The two native/export tests pass. Full-sized GPU memory,
throughput and recurrent vLLM generation have not yet been smoke-tested; current
training was left untouched for CPU preparation. Existing dependency deprecation
warnings are unrelated to these changes.

See [Transformer48 history](2026-11-09-transformer48-dfm11-causal.md) and
[training continuity](../training-continuity.md).

Launch dry run verified all 28,652 jobs and the dataset/index paths; its only
blockers were the expected in-progress Transformer150K checkpoint and stop.
Wiki validation still reports the existing oversized scheduler page and broken
historical links; it reported no errors for this new comparison page.

The user clarified that the expected full-size B GPU footprint is 90–100 GB
per GPU, comparable to the current Transformer48 and previous B training.
Treat this user-provided operational estimate as sufficient for preparation
and the existing shared-headroom policy, not as a reason to block launch for
a separate memory smoke test. Actual full-backprop B memory remains to be
measured during startup; the estimate is not a new measured result.

The user clarified that evaluation memory utilization 0.45 was a one-off
co-tenancy setting, not the standard. Restored 0.95 in the prepared comparison
DB and both plan builders. Preserve the previous calibrated task batches
(32–512), EuroEval concurrency, and vLLM limits of 1,024 sequences / 16,384
batched tokens. The active Transformer150K block drains its existing jobs
before changing pending server keys, avoiding replacement during live requests.
GPU process inspection showed only eight evaluation server workers before
raising the cap. Completed rows retain their historical 0.45 configuration.

The active block drain completed, 1,931 pending rows were updated, and the
administrative dispatch fence was released. All eight replacement servers
launched with utilization 0.95 / max sequences 1,024 / batched tokens 16,384;
successful completion HTTP responses were observed on every GPU. Prepared
comparison validation found all 13,585 inference rows at 0.95. Calibrated
client batches include one 1,024-size task per block as well as 32–512.

## Combined scheduler launch

The prepared-only status above is superseded: the user asked why B had not
started and explicitly requested using one scheduler for both. The missing
handoff was operational, not a GPU or checkpoint failure: the new runner had
been left unlaunched. The Transformer150K stop receipt reports zero failed
jobs, and launch preflight confirmed its complete disk checkpoint and dead
launcher. Started the combined scheduler through
`launch_dfm11_architecture_comparison.py --execute`; runner PID at launch was
1593633. Updated `hrm-20:8` to monitor this combined plan (`dfm11-comparison`).
The prepared order and disk-backed switching policy are unchanged.

Startup verified: B completed at least 80 optimizer steps under the combined
scheduler, with the first 50K training row running. Early progress settled to
roughly 0.30 seconds/step after compilation; this is an initial observation,
not a sustained throughput benchmark. No startup memory failure occurred.

## 50K evaluation stall: incompatible target-plus-judge budget

B reached step 50,000 and suspended at 10:52 UTC. At 14:13 UTC inspection
found only seven completed scheduler rows, eight repeatedly deferred judged
inference rows, and no GPU compute processes. The cause was the blanket 0.95
memory update: managed judge tasks request another 16,384 MiB on the same GPU,
so 0.95 * 183,359 + 16,384 exceeds total capacity. The previous claim that
0.95 should apply to every inference row is superseded for paired judge tasks.

Paused dispatch, drained the eight retrying claims, backed up SQLite and
restored 0.85 generator utilization for all 208 pending judge-bearing rows in
the combined plan; then released the fence. Generator-only tasks retain 0.95.
Both plan builders and AGENTS now preserve this distinction. Added an explicit
impossible-total-budget error in shared-pool provisioning so a future runner
fails such a configuration instead of endlessly treating it as transient
occupancy. Eleven shared-pool tests pass, including that regression test.
The live runner picked up repaired metadata without being restarted; the new
code guard takes effect on its next launch.

Eight replacement recurrent causal servers passed health checks, each with
796,384 KV-cache tokens. The co-located Gemma judge also reached healthy state
on GPU0. Training remains safely offloaded at 50K until evaluation completes.
The earlier 100K ETA is invalid because of this multi-hour scheduler stall.

Recovery confirmed beyond health checks: all eight generative_talemaader judged
inference shards completed. The pool then replaced the pairs with generator-only
0.95 servers, producing a brief empty-GPU interval noticed by the user.
Subsequent live inspection showed 174,518 MiB allocated on every GPU,
85–100% utilization, and successful completion requests on all eight servers.

After B50K inference finished, removed CPU publication from all 12 pending
training dependency gates. Fixed teardown priority hiding ready training;
live pending train positions now precede redundant teardown rows, and the
runner code prioritizes training directly on future launches. Server-stop
receipts appeared and the B100K training row started while merges continued.

## Matched 50K and 100K comparison

Recomputed the existing `headline_avg_v3` aggregates from local merged artifacts
for both models, using the same definitions. All four headline jobs are done;
component counts match (Danish 17, English 15, math/code 4, gen5 5, code4 4, math2 2).
Values below are normalized aggregate scores multiplied by 100, not a single accuracy.

| Metric | T50K | B50K | T100K | B100K |
|---|---:|---:|---:|---:|
| overall | 20.68 | 19.86 | 24.66 | 22.65 |
| danish | 31.27 | 31.75 | 33.10 | 30.54 |
| english | 34.75 | 34.05 | 39.59 | 34.59 |
| math_code | 17.92 | 15.95 | 25.48 | 22.93 |
| gen5 | 20.64 | 16.70 | 20.53 | 21.69 |
| code4 | 4.45 | 3.71 | 8.28 | 9.15 |
| math2 | 7.12 | 5.15 | 13.80 | 11.38 |

B trails overall by 0.81 points at 50K and 2.01 at 100K. Its overall gain is
2.78 points versus 3.98 for Transformer48. B100K leads gen5 and code4 but lags
Danish, English and math2. These are observed single-run comparisons, not
significance-tested architecture conclusions. The matched budget is block
compute/data exposure, not parameter count (B 703.6M vs Transformer 1,203.8M).
Full values and input-root metadata:
`logs/scheduler/dfm11_architecture_comparison_20261110/comparison-50k-100k.json`.

## LR and full-backprop diagnostic

Inspection of the actual saved configs found new B uses `lr_auto=false` with
all module overrides unset, inherited from Transformer48. Previous DFM15 B
used `lr_auto=true`. At H=2/L=3 and bp_steps=8, the existing module-rate rule
would set H=1.5e-4 and L=5e-5, retaining embeddings/head=3e-4. New B instead
uses 3e-4 for every module: 2x/6x the previous scaled H/L rates. This is a
plausible optimization confound, not proof that LR caused the eval deficit.
Matching the scalar transformer LR does not reproduce the previous B recipe.

BP is configured as explicitly requested: min=max=8, warmup ratio=0; all
recurrent calls receive gradients from the start. Previous B had a BP warmup.
Changing back to truncated BP would alter the agreed compute comparison.

Read-only W&B history sampling (1,500 points per model; median within ±2,500
steps) found B versus Transformer loss 1.8068/1.6583 at 10K,
1.3593/1.2660 at 50K, and 1.2780/1.1737 at 100K. B loss is still decreasing;
no recent NaN/nonfinite markers were found in the inspected log tail. Different
parameter counts and sampling noise prevent attributing the gap solely to LR.
Raw sample: `lr-diagnosis-training-history.json` in the comparison plan.

Recommended next diagnostic is a separately identified checkpoint branch
with `lr_auto=true`, retaining full BP, alongside the unchanged LR control.
No live LR, BP settings or scheduler definitions were changed by this diagnosis.

## Fresh LR-auto/BP-warmup B inserted before Transformer200K

The user requested leaving current full-BP B unchanged through 150K, then
first scheduling 150K with `lr_auto=true` and the previous BP warmup. Inserted
a fresh, separately identified run into the live combined scheduler:
`B-dfm11-causal-lrauto-bpwarmup-alltokens-epoch1` (job prefix `bauto-dfm11`).
The original B launch runbook specifies BP2→8 over the first 50K steps, not the
expanded 3-epoch horizon in its final saved config. On DFM11 this is
`bp_min_steps=2`, `bp_max_steps=8`, `bp_warmup_ratio=50000/393732`.

There are 6,612 new pending jobs for 50K/100K/150K, including the same evaluation
coverage and repaired GPU-only training gates. New B50K waits for current
B150K inference and disk-stops that predecessor before starting from scratch.
Transformer200K now waits for the new B150K inference and disk-stops the new
variant before resuming its own 150K checkpoint. Original subsequent alternating
continuations remain in place. Active B definitions/processes were not changed.
No fresh launch command is needed: the existing scheduler owns the new stages.

The new variant retains causal attention, full-token loss, seed/data order,
batch size, base LR3e-4 with 5K LR warmup and flat remainder. Its BP warmup
intentionally uses less early backward compute than the full-BP control.
At full BP, auto-scaled H/L rates are 1.5e-4/5e-5; embedding/head remain 3e-4.

Preparation script: `scripts/insert_dfm11_b_lr_auto_warmup.py`; it refuses duplicate
insertion and backs up SQLite before editing. Config, hash, and schedule checks
are in `logs/training/B_dfm11_causal_lrauto_bpwarmup_20261110`.
All 6,612 new job path preflights passed, the complete dependency graph validates,
and shared publication paths were checked. Native schedule checks confirm
BP2 at step0, BP7 at49,999 and BP8 at50,000 and150,000. A first verification used
exact floating-point equality for 3e-4/6 and failed only on representation;
corrected to tolerance-based comparison. The live full-BP B150K row remained
running throughout insertion.

## Persistent transition monitoring

At the user's request, started `scripts/watch_dfm11_b_transition.py` detached,
polling every 30 seconds. Status is in the combined plan's
`transition-watch/status.json`; logs are `transition-watch/watcher.log`.
It follows full-BP B150K inference, the old launcher's exit, and fresh LR-auto B
startup. `completed.json` is written only when the new trainer has completed at
least 100 steps, its launcher is live, the previous launcher is gone, and its
actual supervisor command confirms LR-auto, BP2→8/50K and no resume checkpoint.
It writes `attention.json` after five minutes without stage-level progress or
on inspection error. This is a local persistent watcher, not a notification
service or automatic repair daemon; coarse inference progress alerts require
inspection of live request logs. No process or scheduler mutations are made.
At activation the old B run was around 134K; the transition had not occurred.

## DFM15 versus DFM11 B50K: objective differences remain

Compared saved configs for old DFM15 B, DFM11 full-BP B and the new DFM11
LR-auto/warmup B. The old model defaults to PrefixLM (`TransformerConfig`),
confirmed by its HF export `prefix_lm=true`; both DFM11 runs explicitly use
causal attention and export `prefix_lm=false`. Old DFM15 has
`data.target_only=true`, while both DFM11 variants have `false`. The new
LR-auto/warmup run therefore reproduces the old optimization rule, not the
old attention/loss objective. These settings were selected earlier to match
the causal/all-token transformer comparison, not accidental runtime drift.

Dataset loader code masks prompt labels only with target_only=true. A bounded
read of the first 200,000 sampled DFM11 index rows found 65.12% of predicted
positions in prompt text (mean prompt length 284.80, response151.998). Thus
roughly two-thirds of those all-token loss positions train prompt continuation,
whereas the old objective trains only responses. This is a scoped sample, not
a full-epoch supervision statistic. PrefixLM also permits bidirectional prompt
attention, unlike causal attention.

Matched `headline_avg_v3` at 50K, scores multiplied by100:

| Run | Overall | Danish | English | Math/code |
|---|---:|---:|---:|---:|
| Previous DFM15 B, PrefixLM/response-only | 20.73 | 30.83 | 35.26 | 7.47 |
| DFM11 full-BP, causal/all-token | 19.86 | 31.75 | 34.05 | 15.95 |
| DFM11 LR-auto/BP-warmup, causal/all-token | 15.78 | 27.19 | 27.94 | 11.93 |

Counts match for all four sections. The fresh variant is worse than the
full-BP DFM11 control at50K, so the earlier LR concern is not a demonstrated
cause of that control's deficit. Actual new-run W&B module metrics confirm
H=1.5e-4 and L=5e-5 once BP8 is reached. Train-loss medians around50K are
1.3852 for old DFM15 and1.3685 for new DFM11-auto, but these are NOT comparable
quality measures because the supervised token populations differ.

Architecture dimensions, optimizer, seed, base LR3e-4, 5K LR warmup and
262,144-token batch agree. Exported tokenizer.json hashes agree exactly
(12bac982b793c44b03d52a250a9f0d0b666813da566b910c24a6da0695fd11e6).
DFM15 metadata also records native-reasoning repairs and limited numeric-answer
conditioning, so it is not merely DFM11 plus multilingual rows. Epoch metadata
sizes are103.21B versus134.52B tokens; at50K, equal batch size matches processed
token budget, not mixture composition or fraction of an epoch.

Next controlled replication would use DFM11 with PrefixLM/response-only loss,
keeping LR-auto and the50K BP warmup; this would isolate data differences much
better. No running settings changed during comparison. Local comparison and
loss-sampling receipts are in the combined plan under
`dfm15-vs-dfm11-50k.json` and `dfm15-vs-dfm11-loss-samples.json`.


## 2026-11-11: PrefixLM replication scheduled after causal-auto100K

Supersedes the queued causal LR-auto150K continuation: the user requested
finishing100K and then a fresh DFM11 PrefixLM/response-only B experiment.
`scripts/insert_dfm11_b_prefixlm.py` inserted6,612 preflight-checked rows for
50K/100K/150K into the live combined SQLite scheduler. The pending causal150K
block was archived and removed; active causal100K definitions/tokens were not
changed. A durable SQLite backup was made before insertion.

New run: `B-dfm11-prefixlm-lrauto-bpwarmup-targetonly-epoch1`.
Control/config receipts: `logs/training/B_dfm11_prefixlm_lrauto_bpwarmup_20261111/`.
Resolved configuration verifies PrefixLM, target_only=true, lr_auto=true,
BP2→8 over exactly50,000 steps (ratio50000/393732), B/H2/L3, one DFM11 epoch,
base LR3e-4 and5K LR warmup. New eval rows omit the causal vLLM plugin flag.
Fresh50K train waits on causal100K GPU inference in terminal mode, then the
scheduler disk-handoff stops the offloaded causal trainer at100K and launches
fresh weights. Publication/averaging/W&B continue independently of training.
Existing Transformer200K is now gated on PrefixLM150K GPU evaluation, preserving
the subsequent comparison queue. The full-epoch training configuration remains;
only the initial150K comparison interval is currently dispatched for this variant.

Graph validation and every new row's path/dependency preflight passed; no claimed
rows were edited. `schedule-verification.json` records the checks. This verifies
the schedule, not a completed future transition: causal training was around67.5K
at scheduling. Detached `scripts/watch_dfm11_prefixlm_transition.py` polls every
30seconds and writes `prefixlm-transition-watch/status.json` under the combined
plan. It verifies old launcher exit, new launcher liveness, actual PrefixLM and
response-only command, fresh initialization, and100 completed new steps before
writing `completed.json`. Five minutes without progress writes `attention.json`;
this watcher observes and records, while the existing scheduler owns the handoff.

### PrefixLM handoff verified, 2026-11-11

The transition watcher completed at08:52:18 UTC: causal-auto stopped at100000,
all1045 GPU inference rows finished successfully, old launcher exited, and
fresh PrefixLM/target-only/LR-auto/BP-warmup training passed200 steps with
its actual command verified. Receipt: combined plan
`prefixlm-transition-watch/completed.json`. Subsequent live inspection found
step2590, all eight GPUs at98–100%, about0.175s/step at this early BP stage.
CPU merges/averages were still running concurrently; publication completion
is not implied by successful GPU evaluation. The old supervisor explicit-stop
trace is the scheduled disk handoff, not an unexpected training crash.


### 2026-11-11 PrefixLM50K evaluation incident: reused causal artifact paths

The earlier path preflight claim was insufficient: it verified availability,
not isolation between model variants. The PrefixLM insertion replaced the dated
training directory but missed shorter artifact stems used by HF exports and
suite result roots. At50K, export_hf reused the existing causal50K export;
its config reports RecurrentCausalForCausalLM and prefix_lm=false. PrefixLM
rows correctly omitted the causal plugin, so vLLM failed during startup and
all eight GPUs idled. No PrefixLM50K inference had succeeded at diagnosis.
The saved training checkpoint is PrefixLM and was not the wrong model.

Recovery uses a clean scheduler drain, durable DB backup, and
`scripts/repair_dfm11_prefixlm_paths.py`: isolate all three PrefixLM blocks'
artifact/result paths, reset50K non-training rows, regenerate the export and
retry evaluation. Previous causal exports/results are preserved. The insertion
script now replaces both dated control paths and undated artifact stems.
Export validation now rejects a prefix_lm mismatch against the checkpoint
attention configuration; regression coverage includes both mismatch directions.
Do not consider a path-only preflight a model-identity verification.


Recovery applied:6,609 evaluation/publication definitions remapped and2,203
50K non-training rows reset after clean drain. Artifact-isolation assertions,
full graph validation and39,672-row launch preflight passed. New runner
PID1868521 launched with the standard persistent-vLLM options. Fresh50K export
has HrmTextForCausalLM and prefix_lm=true; all eight servers loaded its weights.
Eight focused tests passed (four export-validation and four cooperative-training).
OKF validation retains the pre-existing1oversize-page error and14link warnings.
`scripts/watch_dfm11_prefixlm_resume.py` monitors the recovered block under
`prefixlm-resume-watch/`; completed.json requires live training beyond50100.
At this update evaluation startup had recovered, but actual training continuation
was still pending. No completion claim follows merely from server health.


Recurrence prevention: `check_artifact_isolation` checks producer and consumer
HF paths plus inference log directories against canonical checkpoint path/tag.
Same-checkpoint shards may share; different checkpoints may not. It is enforced
by SQLite graph validation (imports/definition edits), the SQLite launch CLI,
the comparison launcher and PrefixLM insertion before mutation. Full live-plan
scan reports zero remaining collisions. Newly generated exports also receive
`scheduler_export_source.json` recording checkpoint path/tag and EMA choice;
reuse validates any existing receipt, and `require_export_source` supports strict
receipt-required plans. Legacy exports without receipts remain supported unless
that flag is set; attention mismatch checks still apply. These new runner-code
guards load on the next runner start; current live definitions were independently
checked and repaired without another interruption. Do not claim that receipts
retroactively certify historical exports lacking them.

Verification:52 focused artifact/export/runner/cooperative tests passed. Real
chat-completion responses succeeded after repair; over200 inference tasks
completed without failure while training remained safely offloaded at50K.

Additional store/CLI regression coverage:56 tests passed (108 total across
the focused suites). No new OKF validation errors; historical1error/14warnings
remain.

Recovery completed: `prefixlm-resume-watch/completed.json` records all1045
50K inference tasks done and live training at50105 at2026-11-11T13:57:14Z.
Subsequent check reached51200. This supersedes the pending-continuation status
above. Current queue remains PrefixLM100K/150K, then Transformer200K and
original full-BP causal B200K, alternating those two through epoch end.
PrefixLM beyond150K and causal-auto beyond100K are not currently scheduled.


## 2026-11-11: PrefixLM replaces full-BP B in the remaining alternation

Supersedes the previous future queue: user explicitly replaced the original
full-BP causal B continuation with the current PrefixLM/target-only/LR-auto/BP
warmup run. `scripts/alternate_dfm11_prefixlm.py --execute` replaced five pending
B blocks (200K,250K,300K,350K,epoch_1) and updated four Transformer successor
handoffs:11,024 rows total. Existing full-BP results through150K remain intact;
that run has no pending training/eval continuation. Active PrefixLM100K was
untouched. No dispatch lock, runner restart or training interruption was needed.

Order: PrefixLM100K, PrefixLM150K, Transformer200K, PrefixLM200K,
Transformer250K, PrefixLM250K, Transformer300K, PrefixLM300K,
Transformer350K, PrefixLM350K, Transformer epoch end, PrefixLM epoch end.
Each boundary keeps all1,045 inference tasks plus publication. One epoch is
estimated393,732steps; actual exhaustion determines final metric step.
Switches use saved checkpoints, preserving optimizer/data cursor/global step;
BP warmup is not restarted. PrefixLM continuation commands retain BP2→8/50K,
lr_auto=true, target_only=true, PrefixLM, and suspension points through350K.

The complete candidate graph, artifact isolation, changed-row availability and
Hydra configuration resolution passed before the pending-only transaction.
A durable SQLite backup, previous rows, resolved continuation config and receipt
are under the combined plan's `prefixlm-alternation/`; verified-live-order.json
records the post-update queue. The insertion validates every edited row remains
unchanged and pending at commit, preserving live claim tokens.


### PrefixLM100K results, 2026-11-11 evening

All1045 inference tasks succeeded; training resumed past100.6K while CPU
publication continued. Atomic headline average job completed and its log reports
W&B sync. Its local run snapshot explicitly binds headline train_step=100000.
Headline scores (x100), PrefixLM50K→100K: overall21.47→26.98,
Danish33.78→36.49, English36.46→42.05, math/code9.24→14.36.
At100K Transformer48 scores24.66/33.10/39.59/25.48 respectively;
original full-BP causal B scores22.65/30.54/34.59/22.93. PrefixLM is ahead
on overall and language aggregates but behind on math/code. This is a recipe
comparison, not an isolated architecture effect: attention, supervision and BP/LR
settings differ. Snapshot artifact: `prefixlm-50k-100k-headline.json` in the
combined scheduler plan. Some multilingual aggregates were still publishing.

### 2026-11-12: PrefixLM150K complete

All2204 rows completed, including publication. Atomic W&B logging receipt and
local summary explicitly bind headline metrics to150000. Scores (x100):
PrefixLM: overall=31.06, danish=43.45, english=43.76, math_code=23.56.
Transformer: overall=26.18, danish=34.94, english=41.06, math_code=29.01.
Snapshot: `prefixlm-vs-transformer-150k.json` in the combined plan.
At04:51 CET Transformer had reached200K and was evaluating; PrefixLM200K
remains next in the verified alternation.


## 2026-11-12: User-requested training pause after200K evaluations

User explicitly requested no further training after current evaluations finish.
Both models are at200K. Eight future train rows (250K through epoch end for
each model) have metadata.user_training_pause=true; existing pending definitions
and checkpoints are preserved. Both control-root hold files explicitly record
user intent. Do not clear either pause mechanism without an explicit resume.

SQLite readiness and atomic claim queries now exclude train_until_step rows
with user_training_pause=true, while evaluation/publication rows remain eligible.
72 store/runner tests pass, including refusal of direct claims on paused training
and continued publication dispatch. During implementation a terminal-barrier
query regression was caught and fixed;38 prior completed administrative barriers
were restored from the pre-change DB snapshot while dispatch was fenced.
No training or evaluation result was changed by that correction.

A temporary global dispatch fence and soft stop allow active attempts to drain;
the replacement runner loads the training-only guard, then the global fence is
released so remaining200K evaluations and publication can finish. Pause receipt
and pre-change backup: combined plan `user-training-pause/`. Resume requires
removing the explicit holds and setting user_training_pause=false on those eight
rows; do not reset completed results or optimizer state. Restart the runner if
it has exited as blocked after all remaining eligible work finishes.

Pause activation verified: old runner drained; replacement PID3653436 passed
39,672-row launch preflight. Global dispatch fence and stop request cleared.
All eight future training rows retain the user pause; remaining evaluation and
publication are eligible. Both control-root explicit holds remain in place.


### 2026-11-12: Next segment released behind three-Mimir semantic evaluation

User explicitly authorized automatic continuation of the next training segment
after the new seven-task evaluations of Mimir v1, v1.5 and v1.8. Supersedes the
pause only for Transformer48 200K→250K; seven later training rows remain paused.
Added24 scheduler rows (21 inference,3 headline publications). Transformer250K
has the three new terminal headline dependencies and user_training_pause=false.
Current200K inference precedes the new campaign; per-model evaluation groups run
in order v1→v1.5→v1.8. No independent GPU runner is started. Dedicated campaign
manifest, model/data/software hashes, backup, insertion and gate-verification
receipts are in `danish-semantic-mimir-20261112/` under the combined plan.
See [semantic headline protocol](../danish-semantic-reasoning-evaluation.md).
The separate average-dispatch test passed in addition to23 task/publisher tests.


## Transformer headline sync investigation — 2026-11-12

User reported missing150K/200K headlines. Read-only remote W&B inspection of
`peter-sk-sdu/DFM5/transformer48-dfm11-causal-alltokens-epoch1` confirms both
checkpoints are present in history, not merely in the current summary. All four
main `headline_avg_v3` metrics have numeric schema entries and five history
points (50K,100K,150K,200K,250K). Remote150K/200K values match saved local
publisher summaries; both publication logs report successful sync.

| Checkpoint | Overall | Danish | English | Math/code |
|---|---:|---:|---:|---:|
|150K|26.1774|34.9421|41.0563|29.0060|
|200K|27.5395|36.7276|42.8771|31.2306|
|250K|28.6627|37.5555|41.4365|32.3072|

Scores above are normalized metrics multiplied by100. Evaluation train_step
and epoch are logged atomically. Internal W&B `_step` is150410 at150K,
201042 at200K, and251487 at250K; it is not the training checkpoint coordinate.
Use `headline_avg_v3/train_step` or `headline_avg_v3/epoch` as the chart axis.
The default metric registration uses the latter. Missing points in an
unspecified workspace are not evidence of a sync failure: the user's exact
panel/filter configuration remains unverified. No duplicate backfill or workspace
mutation was performed. Evidence: `logs/diagnostics/transformer-headline-sync-20261112/`
contains remote headline-history.json and history-keys.json.


Workspace follow-up: user identified `mkrhf1q0gcj` (DFM5 Multilingual
Headlines, Forge URL). Remote spec inspection confirmed all seven headline
panels select headline_avg_v3 metrics against headline_avg_v3/epoch. Run
selection is subtractive and does not exclude the Transformer. No filters,
smoothing, or chart range limits explain absent150K/200K points. Exact
per-panel metric/axis sampled-history queries returned all five checkpoints.
The workspace uses bucketing-gorilla; as a reversible display workaround,
only the seven headline panels were overridden to pointVisualizationMethod=
sampling, preserving all metrics, axes, selection and other panels. Optimistic
concurrency check and remote exact-spec verification protect user edits.
Before/intended/after snapshots and sampled-series evidence are in the diagnostic
directory above. A bucketing/rendering issue is a hypothesis, not a reproduced
root cause: authenticated browser rendering was unavailable. No history was
rewritten. User refresh/visual confirmation remains required to establish that
the reported display symptom is resolved.


## User-authorized remaining training continuation — 2026-11-12

User explicitly requested continuation of the following training segments,
superseding the earlier seven-row pause. Cleared user_training_pause on all
seven pending training rows, preserving their commands, resume checkpoints,
dependencies and50K eval boundaries. Order: PrefixLM B200→250K,
Transformer250→300K, B250→300K, Transformer300→350K, B300→350K,
Transformer350K→epoch end, B350K→epoch end. Each boundary retains scheduled
evaluations/cooperative suspension and planned model-switch disk handoffs.
The existing scheduler had exited blocked; all GPUs were idle before restart.
Backup and authorization receipt are saved in the combined plan directory.
Scheduled handoff hold/stop files are handled by the existing cooperative
launcher, not manually removed from a potentially live trainer.


Continuation preflight:39,760 paths passed. The original launch helper's
initial-run check rejected the still-live Transformer launcher, although it was
correctly offloaded at250K. Verified its suspend_ready, regular checkpoint state,
matching generation offloaded receipt, and the next B row's explicit250K
 disk_handoff_from. Started the helper's exact standard SQLite runner command
with persistent-vLLM and required PATH/TMPDIR, PID425954, allowing the existing
cooperative scheduler to stop the predecessor safely. The helper's unconditional
"Transformer launcher still alive" guard is suitable for initial launch only;
subsequent scheduler restart must validate the scheduled offloaded handoff rather
than kill the trainer or incorrectly treat a legitimate suspension as a blocker.


Live startup exposed a second resume defect: static suspension boundaries at or
below the disk checkpoint were replayed on the first optimizer step (200001).
Scheduler requested release below its250K target, but Controller.restore tried
to read offload.json although CUDA offload had never happened. Supervisor safely
restarted from the new200001 checkpoint. Fixed pretrain resume initialization to
mark past static boundaries consumed and keep only future ones. Controller.restore
now releases an unoffloaded handshake only after verifying every CUDA rank is
running, under the same controller lock and existing hold/process checks; it
records cancelled.json and issues rank-bound release tokens without CUDA actions.
A new regression test and existing suspension/fallback tests pass (26 total).
The currently restarting trainer can recover the old handshake through the
fresh controller subprocess; future disk resumes also receive boundary filtering.

Continuation verified beyond launch: PrefixLM B advanced from200005 to200080;
all eight GPUs show98–100% utilization and94–96GiB allocated (nvidia-smi
reports MiB). Scheduler owns the250K training row; all seven user pause flags
are cleared. Normal50K evaluations and subsequent alternation remain scheduled.


## Explicit user memory pause at259K — 2026-11-12

User requested Transformer suspension at259000 and preparation for later
in-memory resume. Published an explicit user root hold before submitting259000
to the active suspension hook. Verified exact259000 readiness, successful
cuda-checkpoint offload, matching generation receipt, original live launcher and
all eight original ranks. The root hold remains; no automatic restoration or
subsequent training is authorized until the user requests resume. Main scheduler
continues to own the300K training row and waits on the hold. Receipt:
`logs/training/transformer48_dfm11_causal_20261109/control-shared-1/user-pause-259000.json`.
For authorized resume, verify this active generation, remove the explicit root
hold and let the existing supervisor/main scheduler perform restoration; do not
launch another trainer or recovery supervisor.


### Authorized idle-triggered memory resume

User subsequently authorized automatic resume once all GPUs are idle for more
than five minutes, superseding the manual-only259K hold. Started detached
`scripts/watch_transformer_259k_idle_resume.py`, PID796999. Polls every10seconds;
requires all eight GPU utilization readings0, <=128MiB each and no compute
processes for >300 continuous seconds. Occupancy, activity or query errors reset
the timer. This deliberately does not treat a resident idle server as free
capacity for restoring the trainer. It neither kills nor changes other workloads.
It pins259K generation2 and original launcher/ranks; changed hold, launch or
explicit cancel.request prevents overriding newer instructions. After a fresh
idle check it removes only the expected hold and signals the existing supervisor;
then verifies original-process memory restoration. No new trainer/recovery
supervisor is launched. Logs/status/launch receipt live under control-shared-1/
idle-resume-259000. Initial probe found other compute processes on all GPUs,
so timer=0 and trainer remains suspended. Syntax check and live read-only GPU
probe passed; trigger/resume is not yet claimed.


## B296K suspension and automatic idle resume — 2026-11-13

User requested suspension at296K with resume after five minutes of all-GPU idle.
Live inspection found Transformer already completed300K; active row was
bprefix-dfm11-step_300000-train at295820. Applied request to active PrefixLM B,
not the completed Transformer segment. Verified exact296000 handshake, matching
CUDA offload receipt and original live launcher/eight ranks. Explicit hold is
retained until detached watcher `scripts/watch_bprefix_296k_idle_resume.py`
(PID1114012) observes >300continuous seconds with all eight utilization readings0,
<=128MiB/GPU and no compute processes. It resets on activity/occupancy/query
errors and uses existing supervised memory restore with generation/identity
checks. Receipt and watcher status reside in B control/user-pause-296000.json
and control/idle-resume-296000. No unrelated GPU workloads were modified.


### B299K pause — 2026-11-13

The296K idle watcher successfully restored the original B trainer from memory.
User then requested299K suspension with the same five-minute idle-resume rule.
Observed B at298920, placed a new explicit hold and submitted299000. Verified
exact299000 readiness, matching CUDA offload receipt and original live ranks.
Started detached `scripts/watch_bprefix_299k_idle_resume.py`, PID1176021;
receipt/status under B control/user-pause-299000.json and idle-resume-299000.
Same >300continuous-second all-eight-GPU idle/free checks and guarded supervised
memory restoration apply. No other GPU process was modified.


### Pause all training beyond300K — 2026-11-13

User requested that300K evaluations finish, then GPUs remain free. Both trainers
have reached300K; B300K eval block is active. Backed up the DB and set
user_training_pause=true on the four pending training rows (Transformer350K,
B350K, Transformer epoch end, B epoch end). Added explicit user hold to the B
control root after verifying its current suspension is300000. This supersedes
prior idle-triggered permissions for further training; earlier299K watcher had
already resumed that generation. No eval/publication rows were paused and no
running definition was changed. Verified four pending train pauses and B300K
counts1389done/124running/691pending at observation. DatabaseRunner exits blocked
when no eligible rows remain and closes all owned servers in finally, releasing
its GPU allocations. Other users' workloads are not stopped. Backup/authorization
receipt: combined-plan pause-after-300k.json and before-pause-after-300k SQLite.


### Memory-headroom-triggered continuation — 2026-11-13

User superseded the post300K pause: resume training segments once at least100GB
is free. Armed detached `scripts/watch_dfm11_100gib_continue.py` PID1745821,
interpreting headroom conservatively as100GiB (102400MiB) on EACH of all eight
GPUs. It polls10seconds with no five-minute idle requirement. Current headroom
is~16GiB each, so four train rows remain paused. On threshold it backs up DB,
records exact co-resident process identities, clears the four user pause flags,
sets scheduler minimum and both launcher settings to102400MiB, and starts the
existing scheduler via its preflight launcher. Other workloads are never stopped.
Existing model-switch handoff handles B's300K root hold. Normal alternating350K
and epoch-end training/evaluation schedule remains. Receipt/status/log under
combined-plan continue-100gib-20261113. Initial live probe and syntax check passed;
training launch has not yet been claimed. New cancel.request cancels the watcher.


### Stale monitor and failed headroom continuation recovery — 2026-11-13

User reported stale monitor. It was reading the correct combined plan, but
runner had exited blocked: Transformer350K failed `GPU workers remain; refusing
duplicate cooperative launch`, then future train rows failed handoff checks.
The100GiB watcher had only recorded scheduler_launched, not training progress;
its earlier peer identity snapshot did not cover the processes seen at launch.
Current probe found GPUs free and no compute peers. Refreshed peer identities,
reset the four unstarted train rows to pending (which rearms terminal barriers),
and reran full preflight:39,760 jobs, zero path errors/blockers. Scheduler1882950
launched Transformer300K→350K. Restarted the shared tmux monitor pane at
hrm-82:8.1; linked window8 in the other hrm sessions is the same pane. Verified
live lanes now show the350K training row rather than snapshot stale/unknown.
Monitor refresh interval5seconds. Trainer restored300K and entered batch300001;
GPU peer identity changes remain a guard that requires fresh admission evidence,
not proof the earlier watcher completed the requested training continuation.

Recovery progress verified: Transformer advanced through300015 into300016 after
initial data/compilation warm-up. Shared monitor window8 has a fresh timestamp
and shows the active350K training row; no stale-snapshot warning.


### Transformer370K pause — 2026-11-14

User requested370K suspension and automatic resume after five minutes of all-GPU
idle. Active model was Transformer epoch1 segment at369273. Published explicit
hold before submitting370000. Verified exact370000 readiness, generation-matched
CUDA offload and original live launcher/eight ranks. Started detached watcher
`scripts/watch_transformer_370k_idle_resume.py` PID2420294. Same >300continuous
seconds of zero utilization, <=128MiB per GPU and no compute processes across
eight GPUs applies; activity/query errors reset timer. Original trainer restores
through existing supervisor with generation/process identity checks, not disk
restart. Receipt/status under Transformer control-shared-1/user-pause-370000.json
and idle-resume-370000. The epoch-end scheduler row remains claimed throughout.

370K resume verified: by the user resume request, the idle watcher had already
requested restoration after309.5seconds of free GPUs. Original launcher/ranks
restored from memory successfully; receipt records resumed_from_memory and live
training advanced to370002. No duplicate restoration or disk launch performed.


### Transformer381K pause — 2026-11-14

User requested381K suspension with automatic resume after five minutes of all-GPU
idle. Verified exact381000 suspension, generation-matched CUDA offload and original
live launcher/eight ranks. Detached watcher `scripts/watch_transformer_381k_idle_resume.py`
PID2483140 is active; same >300continuous-second idle/free condition and guarded
supervised memory restore apply. Receipt/status: Transformer control-shared-1/
user-pause-381000.json and idle-resume-381000. Any GPU activity, occupied memory
or probe error resets timer. No disk restart or other workload changes performed.

381K manual resume: explicit user resume superseded the idle timer. Verified
all GPUs free, cancelled the381K idle watcher, removed only its expected hold
and requested supervised restore. Matching resumed receipt and original launcher/
eight rank identities verified with no disk fallback. Receipt manual-resume-381000.json.

### Transformer387K pause — 2026-11-14

User requested387K suspension and automatic resume after five minutes all-GPU
idle. Verified exact387000 suspension, matching CUDA offload receipt and original
live launcher/eight ranks. Detached watcher scripts/watch_transformer_387k_idle_resume.py
PID2724295 is active. Same >300continuous-second idle/free checks, resets and
supervised memory restore apply. Receipt/status under Transformer control-shared-1/
user-pause-387000.json and idle-resume-387000. No disk restart performed.

387K manual resume request: user superseded the idle timer. Other workloads
occupied~133000MiB/GPU with~49000MiB free. Verified original trainer alive,
cancelled387K idle watcher, removed only matching user hold and published
generation-bound restore.request. Existing supervisor defers restoration while
new GPU occupants remain (RestoreDeferred, no disk fallback). No peer processes
were changed. Resume is requested, not yet confirmed; no five-minute idle wait
remains. Receipt manual-resume-387000.json.

User explicitly authorized stopping competing GPU jobs to resume387K. Identified
Embla JAX validation launcher2722670 and its eight servers2724423–2724430.
Sent graceful launcher stop; recorded descendant identities were then terminated,
with surviving processes force-stopped after20seconds (PID-reuse checked).
No broad process-name kill used. Receipt stop-competing-embla-387k.json in combined
plan. GPU allocations cleared, existing supervisor restored original Transformer
launcher/ranks from memory; matching387K resumed receipt and no disk fallback
verified. manual-resume-387000.json now records resumed_from_memory.

392K suspension requested (2026-11-14): user authorized automatic memory resume
after all eight GPUs are idle for more than five continuous minutes. Submitted
392000 to the live Transformer control queue and installed its explicit hold.
Detached offload helper PID3108543 waits for the exact boundary, verifies CUDA
offload and original process identities, then starts
`scripts/watch_transformer_392k_idle_resume.py`. Watcher uses the established
zero-utilization, <=128MiB/GPU, no-compute-process checks; any activity resets
the timer. Existing supervisor owns restoration. Receipts are under
`control-shared-1/user-pause-392000.json` and `idle-resume-392000/`.

392K verified: exact392000 CUDA offload completed, original launcher and all eight
ranks retained. Watcher PID3109254 is active; initial probe found all GPUs at
0% utilization/4MiB with no compute processes. Five-minute idle timer started.

### Epoch-end finalization and subsequent ablations — 2026-11-14

Moved to [objective ablations and final-evaluation repair](2026-11-14-dfm11-objective-ablation.md).

# Current State

Last updated: 2026-06-16
Confidence: high
Scope: Local repo state and verified commands from this session.

## 2026-06-16 DFM5 L 300K Full Eval

Confidence: high for local checkpoint state, scheduler launch, and tmux
process inspection; medium for final metrics until all jobs finish and the
post-eval watcher logs averages/regenerates docs.

The DFM5 L `step_300000` checkpoint exists under `checkpoints/dfm5/L` with
`checkpoint_state_step_300000.json`, `fsdp2_step_300000/.metadata`, eight
FSDP shard files, and eight carry files. The checkpoint state says
`epoch=2`, `batch_in_epoch=118714`, `global_batch_size=196608`, and
`checkpoint_format=sharded`.

The eval x-axis value follows the same fractional-epoch convention used for
the earlier DFM5-L points:

```text
300000 / (35605979095 / 196608) = 1.6565307709311847
```

The full eval was launched on 2026-06-16 in tmux window `hrm-0:8` with
EuroEval-first ordering, W&B sync enabled, and incremental merge enabled by
the scheduler default:

```bash
cd /work/dfm/HRM-Text
CKPT_PATH=checkpoints/dfm5/L \
CKPT_TAG=step_300000 \
EVAL_EPOCH=1.6565307709311847 \
GPUS=0,1,2,3,4,5,6,7 \
LOG_ROOT=logs/eval/dfm5_L_step300000_full_20260616_eurofirst_guard \
DFM_LOG_ROOT=logs/dfm_evals/dfm5_L_step300000_full_20260616_eurofirst_guard \
EUROEVAL_LOG_ROOT=logs/euroeval/dfm5_L_step300000_full_20260616_eurofirst_guard \
WANDB_SYNC=1 \
WANDB_PROJECT=DFM5 \
WANDB_RUN_ID=oti1lisg \
WANDB_RUN_NAME=dfm5-L \
MODEL_PREFIX=hrm-dfm5-L \
RUN_EUROEVAL=1 \
QUEUE_ORDER=euroeval_first \
STANDARD_BATCH_SIZE=128 \
STANDARD_BATCH_SIZE_GSM8K=64 \
STANDARD_BATCH_SIZE_MATH=64 \
STANDARD_BATCH_SIZE_DROP=32 \
DFM_BATCH_SIZE=32 \
DFM_BATCH_SIZE_GOVREPORT=32 \
DFM_BATCH_SIZE_NORDJYLLANDNEWS=32 \
DFM_BATCH_SIZE_WMT24PP_EN_DA=32 \
DFM_BATCH_SIZE_HUMANEVAL=16 \
DFM_BATCH_SIZE_GENERATIVE_TALEMAADER=16 \
IFEVAL_BATCH_SIZE=64 \
EUROEVAL_BATCH_SIZE=16 \
EUROEVAL_BATCH_SIZE_IFEVAL=32 \
EUROEVAL_BATCH_SIZE_IFEVAL_DA=32 \
MAX_RETRIES=5 \
EUROEVAL_BIN=/work/dfm/HRM-Text/scripts/euroeval_api_no_flash_attn_guard.py \
scripts/schedule_checkpoint_evals.sh \
  2>&1 | tee logs/dfm5_L_step300000_full_eval_20260616.log
```

The IFEval-specific batch sizes were intentionally set one step higher than
the previous full-eval command: DFM IFEval-DA uses `IFEVAL_BATCH_SIZE=64`,
while EuroEval `ifeval` and `ifeval-da` use task-specific overrides of `32`
instead of the base EuroEval batch size `16`.

Runtime finding, 2026-06-16. Confidence: high for local logs and process/GPU
inspection. The DFM IFEval-DA bump to `IFEVAL_BATCH_SIZE=64` was too high
while the DFM5-L training process was still resident on each GPU. Server logs
for shards 0-4 show CUDA OOMs after attempting an additional `640 MiB`
allocation with only about `92-602 MiB` free. Each DFM IFEval-DA job starts
`scripts/hrm_openai_server.py` with both `--batch-size 64` and the dfm-evals
client uses `--max-connections 64`, so the setting increases both server batch
capacity and request concurrency. With the training process using roughly
`104-107 GiB` and the eval server using roughly `71-76 GiB`, this leaves almost
no GPU memory headroom. The long shard runtime is therefore not normal IFEval
slowness; it is OOM/retry/stalled-client behavior from over-aggressive
concurrency. Future concurrent-with-training DFM IFEval-DA evals should use
`IFEVAL_BATCH_SIZE=32` unless telemetry proves a larger value is safe.

Scheduler fix and active-run intervention, 2026-06-16. Confidence: high for
code inspection, `bash -n`, process list, and scheduler status. The scheduler
scripts were patched so future DFM and EuroEval jobs monitor their local
OpenAI shim server while the eval client is running. If the server exits or
logs an OOM, the client is killed and the job returns nonzero, allowing the
existing retry path to halve the batch size. Patched files:

```text
scripts/schedule_checkpoint_evals.sh
scripts/run_euroeval_on_checkpoint.sh
```

The currently running `step_300000` scheduler had already loaded the old shell
functions, so the stuck DFM IFEval-DA batch-64 clients/servers were manually
terminated for shards 0-5. The scheduler observed nonzero exits and retried
those shards at batch `32`:

```text
2026-06-16T07:33:35+02:00 RETRY dfm_ifeval ... next_attempt_2
2026-06-16T07:33:45+02:00 START dfm_ifeval ... attempt_2_of_6 batch_32
```

The training processes were not targeted by the intervention.

Follow-up in the same active run: shards 0-5 completed successfully at batch
`32`, but the old in-memory scheduler then launched shards 6-11 at batch `64`
because batch selection is keyed by task/shard id. Synthetic OOM telemetry rows
were appended for DFM IFEval-DA shard ids 6-31 at batch `64`, and the stuck
batch-64 processes for shards 6-11 were terminated. The scheduler then retried
shards 6-11 at batch `32`. This telemetry seeding is an active-run workaround
only; future scheduler launches should rely on the patched server-monitor
behavior and a conservative `IFEVAL_BATCH_SIZE=32`.

Initial scheduler status:

```text
2026-06-16T06:23:48+02:00 QUEUED 188 jobs
2026-06-16T06:23:48+02:00 CHECKPOINT_READY step_300000 path_checkpoints/dfm5/L
2026-06-16T06:23:48+02:00 WORKERS 1985476 1985477 1985478 1985479 1985480 1985481 1985482 1985483
2026-06-16T06:23:49+02:00 START euroeval angry-tweets shard_0_of_20 gpu_0 attempt_1_of_6 batch_16 mem_free_before_72785
2026-06-16T06:23:58+02:00 START euroeval scala-da shard_1_of_20 gpu_1 attempt_1_of_6 batch_16 mem_free_before_75699
```

The post-eval watcher is running in tmux window `hrm-0:9`. It waits for
`FINAL_MERGE_END`, then logs the 300K headline averages under `avg/*` and
regenerates `docs/dfm5.md`:

```bash
python scripts/log_dfm5_headline_averages.py \
  --project DFM5 \
  --run-id oti1lisg \
  --run-name dfm5-L \
  --item 300000:1.6565307709311847:logs/eval/dfm5_L_step300000_full_20260616_eurofirst_guard:logs/dfm_evals/dfm5_L_step300000_full_20260616_eurofirst_guard:logs/euroeval/dfm5_L_step300000_full_20260616_eurofirst_guard/step_300000 \
  2>&1 | tee logs/dfm5_L_step300000_headline_averages_20260616.log

python scripts/generate_dfm5_l_eval_comparison_report.py \
  2>&1 | tee logs/dfm5_L_step300000_generate_docs_20260616.log
```

The progress monitor is running in tmux window `hrm-0:10`:

```bash
python scripts/watch_eval_progress.py \
  --log-root logs/eval/dfm5_L_step300000_full_20260616_eurofirst_guard \
  --dfm-log-root logs/dfm_evals/dfm5_L_step300000_full_20260616_eurofirst_guard \
  --euroeval-log-root logs/euroeval/dfm5_L_step300000_full_20260616_eurofirst_guard \
  --ckpt-tag step_300000 \
  --interval 10
```

`scripts/generate_dfm5_l_eval_comparison_report.py` now includes a
`DFM5-L 300K` column sourced from the 2026-06-16 eval roots above. Until the
300K eval finishes, the generated docs table may show missing 300K values.

## 2026-06-15 Original Sapient L Backfill Into DFM5

Confidence: high for local source artifacts, successful W&B sync, and remote
run metadata/summary verification.

The original Sapient L reproduction run was backfilled into a new W&B run in
project `DFM5`:

```text
project: DFM5
run id:  original-sapient-L-dfm5-backfill-20260615
name:    original Sapient L backfilled
url:     https://wandb.ai/peter-sk-sdu/DFM5/runs/original-sapient-L-dfm5-backfill-20260615
```

The backfill script is:

```text
scripts/backfill_original_sapient_l_to_dfm5.py
```

It replays scalar training rows from:

```text
wandb/merged-20260524-76sygh18-clean/history.jsonl
```

and rebuilds evaluation rows from local artifacts:

```text
logs/eval/original_sapient_L/epoch_{1,2,3,4}.log
logs/dfm_evals/original_sapient_L_lite_all_checkpoints_20260603T213010/epoch_{1,2,3,4}
logs/euroeval/original_sapient_L/epoch_{1,2,3,4}/euroeval_benchmark_results.jsonl
```

The true original Sapient L epoch-step mapping used for eval rows is:

```text
epoch 1 -> step 81478
epoch 2 -> step 162961
epoch 3 -> step 244443
epoch 4 -> step 325928
```

Command used:

```bash
cd /work/dfm/HRM-Text
python scripts/backfill_original_sapient_l_to_dfm5.py \
  2>&1 | tee logs/wandb_backfill_original_sapient_l_to_dfm5_20260615.log
```

The dry run and final manifest are in:

```text
logs/wandb_backfill_original_sapient_l_to_dfm5_dryrun_20260615.log
logs/wandb_backfill_original_sapient_l_to_dfm5_20260615.log
logs/wandb_backfill_original_sapient_l_to_dfm5_manifest.json
```

Final manifest:

```text
training_rows: 65186
total_rows:    65190
eval_steps:    [81478, 162961, 244443, 325928]
metric counts: epoch 1=460, epoch 2=455, epoch 3=460, epoch 4=460
```

Representative verified summary keys include `train/loss`, `eval/MMLU/acc`,
`eval/BoolQ/acc`, `eval/GSM8k/acc`,
`dfm_eval/nordjyllandnews/rouge2/mean`,
`dfm_eval/humaneval/verify_sanitized/accuracy`,
`euroeval/da/summarization/nordjylland-news/chr_f3pp`, and
`headline_avg/{danish,english,math_code,overall}`.

## 2026-06-15 GSM8k Smoke Error Analysis

Confidence: high for local runs and saved artifacts; medium for manual failure
bucket labels because many wrong completions are bare numeric answers with no
trace.

The same `100` randomly sampled GSM8k test rows were run with seed
`20260615` through DFM5-L `step_200000` and the locally trained original
Sapient L `epoch_4`, both with EMA/default weights, `condition=direct`, and
`temperature=0.0`.

Raw eval-style prompt scores:

```text
DFM5-L step_200000:        22/100
original Sapient L epoch4: 41/100
```

Show-work prompt scores, used for interpretable buckets:

```text
DFM5-L step_200000:        31/100
original Sapient L epoch4: 41/100
```

Manual bucket counts from the show-work run:

```text
bucket                                  DFM5-L  original Sapient L
correct                                    31                  41
bare_wrong_number_no_trace                 62                  58
correct_reasoning_unparseable_format        2                   0
wrong_setup_in_worked_solution              2                   0
incomplete_or_truncated_reasoning           1                   0
invalid_non_numeric_final                   1                   0
dataset_gold_ambiguity                      1                   1
```

Main interpretation: the observed DFM5-L GSM8k lag is mostly not exposed as
long faulty reasoning; even when asked to show work, both models often emit only
bare numbers. Original Sapient L gets more of those bare-number cases right.
DFM5-L also shows a few format/scoring and worked-solution setup failures that
did not appear in this original Sapient L sample.

Artifacts:

```text
scripts/smoke_gsm8k_error_analysis.py
logs/analysis/gsm8k_smoke_dfm5_L_step200000_seed20260615.json
logs/analysis/gsm8k_smoke_dfm5_L_step200000_seed20260615_show_work.json
logs/analysis/gsm8k_smoke_original_sapient_L_epoch4_seed20260615.json
logs/analysis/gsm8k_smoke_original_sapient_L_epoch4_seed20260615_show_work.json
logs/analysis/gsm8k_smoke_dfm5_vs_original_sapient_L_seed20260615.md
logs/analysis/gsm8k_smoke_dfm5_vs_original_sapient_L_seed20260615_counts.json
```

## 2026-06-15 DFM5 L 250K Full Eval

Confidence: high for local checkpoint state, scheduler completion, merged
artifacts, W&B average sync, and regenerated Markdown report.

The DFM5 L `step_250000` checkpoint exists under `checkpoints/dfm5/L` with
`checkpoint_state_step_250000.json`, `fsdp2_step_250000/`, and eight carry
files. Its eval epoch x-value is:

```text
1.3831660928989149
```

The full eval was launched in tmux window `hrm-0:8` with EuroEval-first
ordering while DFM5 L training continued:

```bash
cd /work/dfm/HRM-Text
CKPT_PATH=checkpoints/dfm5/L \
CKPT_TAG=step_250000 \
EVAL_EPOCH=1.3831660928989149 \
GPUS=0,1,2,3,4,5,6,7 \
LOG_ROOT=logs/eval/dfm5_L_step250000_full_20260615_eurofirst_guard \
DFM_LOG_ROOT=logs/dfm_evals/dfm5_L_step250000_full_20260615_eurofirst_guard \
EUROEVAL_LOG_ROOT=logs/euroeval/dfm5_L_step250000_full_20260615_eurofirst_guard \
WANDB_SYNC=1 \
WANDB_PROJECT=DFM5 \
WANDB_RUN_ID=oti1lisg \
WANDB_RUN_NAME=dfm5-L \
MODEL_PREFIX=hrm-dfm5-L \
RUN_EUROEVAL=1 \
QUEUE_ORDER=euroeval_first \
STANDARD_BATCH_SIZE=128 \
STANDARD_BATCH_SIZE_GSM8K=64 \
STANDARD_BATCH_SIZE_MATH=64 \
STANDARD_BATCH_SIZE_DROP=32 \
DFM_BATCH_SIZE=32 \
DFM_BATCH_SIZE_GOVREPORT=32 \
DFM_BATCH_SIZE_NORDJYLLANDNEWS=32 \
DFM_BATCH_SIZE_WMT24PP_EN_DA=32 \
DFM_BATCH_SIZE_HUMANEVAL=16 \
DFM_BATCH_SIZE_GENERATIVE_TALEMAADER=16 \
IFEVAL_BATCH_SIZE=32 \
EUROEVAL_BATCH_SIZE=16 \
MAX_RETRIES=5 \
EUROEVAL_BIN=/work/dfm/HRM-Text/scripts/euroeval_api_no_flash_attn_guard.py \
scripts/schedule_checkpoint_evals.sh \
  2>&1 | tee logs/dfm5_L_step250000_full_eval_20260615.log
```

Initial scheduler status:

```text
2026-06-15T18:49:55+02:00 QUEUED 188 jobs
2026-06-15T18:49:55+02:00 CHECKPOINT_READY step_250000 path_checkpoints/dfm5/L
2026-06-15T18:49:55+02:00 WORKERS 344695 344696 344697 344698 344700 344701 344702 344703
2026-06-15T18:49:55+02:00 START euroeval angry-tweets shard_0_of_20 gpu_0 attempt_1_of_6 batch_16 mem_free_before_72785
2026-06-15T18:50:05+02:00 START euroeval scala-da shard_1_of_20 gpu_1 attempt_1_of_6 batch_16 mem_free_before_75699
```

A post-eval watcher runs in tmux window `hrm-0:9`; it waits for
`FINAL_MERGE_END`, then logs headline averages to W&B and regenerates the
comparison table:

```bash
python scripts/log_dfm5_headline_averages.py \
  --project DFM5 \
  --run-id oti1lisg \
  --run-name dfm5-L \
  --item 250000:1.3831660928989149:logs/eval/dfm5_L_step250000_full_20260615_eurofirst_guard:logs/dfm_evals/dfm5_L_step250000_full_20260615_eurofirst_guard:logs/euroeval/dfm5_L_step250000_full_20260615_eurofirst_guard/step_250000

python scripts/generate_dfm5_l_eval_comparison_report.py
```

The eval-progress monitor was updated on 2026-06-15 to show per-GPU active
task status plus total completed/active/queued/visible shards and an overall
ETA from the observed completion rate. The running monitor for this eval is in
tmux window `hrm-0:10`:

```bash
cd /work/dfm/HRM-Text
python scripts/watch_eval_progress.py \
  --log-root logs/eval/dfm5_L_step250000_full_20260615_eurofirst_guard \
  --dfm-log-root logs/dfm_evals/dfm5_L_step250000_full_20260615_eurofirst_guard \
  --euroeval-log-root logs/euroeval/dfm5_L_step250000_full_20260615_eurofirst_guard \
  --ckpt-tag step_250000 \
  --interval 10
```

Example fields now shown:

```text
jobs: completed=<n> active=<n> queued=<n> total=<n> ETA <...>
GPU0: euroeval:<task> shard x/y a/b elapsed <...> ETA <...> | <gpu memory/util>
```

Scheduler incremental merge update, 2026-06-15. Confidence: high for local
code inspection and `bash -n`; applies to scheduler processes launched after
this edit. `scripts/schedule_checkpoint_evals.sh` now defaults
`INCREMENTAL_MERGE=1`. After each successful shard, the worker checks whether
the full shard set for that standard or DFM task has completed. If yes, it
merges and syncs that task immediately under a merge lock, then writes a marker
file. The final merge phase skips marker-present tasks and only merges any
remaining complete task sets. EuroEval already merged/synced each one-dataset
group as its job finished.

Important active-run caveat: the already-running `step_250000` eval was
launched before this edit, so its Bash process has the old final-merge-only
standard/DFM functions loaded. Starting a sidecar incremental sync for the
current run would duplicate W&B points when the old final merge runs. For this
250K run, EuroEval remains incremental, while standard/DFM will sync in the
final merge. Future eval launches will use incremental standard/DFM merge by
default.

Completion update, 2026-06-15. Confidence: high for local scheduler status,
post-eval watcher log, and regenerated report artifact. The 250K eval reached
`FINAL_MERGE_END` at `2026-06-15T22:02:01+02:00`. The post-eval watcher then
logged the 250K headline averages to W&B run `DFM5/oti1lisg` under the new
`avg/*` prefix and regenerated the DFM5-L comparison Markdown table.

250K averages synced by
`logs/dfm5_L_step250000_headline_averages_20260615.log`:

```text
avg/danish=0.47466145094826273      count=18
avg/english=0.5565590118947327      count=15
avg/math_code=0.2507825859769966    count=4
avg/overall=0.427334349606664
avg/epoch=1.383166092898915
avg/train_step=250000
```

`scripts/generate_dfm5_l_eval_comparison_report.py` now includes the
`DFM5-L 250K` column, sourced from:

```text
logs/eval/dfm5_L_step250000_full_20260615_eurofirst_guard
logs/dfm_evals/dfm5_L_step250000_full_20260615_eurofirst_guard
logs/euroeval/dfm5_L_step250000_full_20260615_eurofirst_guard/step_250000
```

The regenerated Markdown report is:

```text
docs/dfm5.md
logs/reports/dfm5_l_eval_comparison_50k_250k_vs_original_ema_and_card.md
logs/reports/dfm5_l_eval_comparison_50k_100k_150k_vs_original_ema_and_card.md
```

`docs/dfm5.md` is the canonical human-facing copy. The two files under
`logs/reports/` are compatibility/report artifacts written with identical
content by `scripts/generate_dfm5_l_eval_comparison_report.py`.

Its section averages for `DFM5-L 250K` are Danish `47.5`, English `55.7`,
and Math & Code `25.1` in percent-style display.

## 2026-06-14 DFM5 L 50K Full Eval

Confidence: high for local checkpoint, scheduler, process, and GPU inspection;
medium until all shards finish and W&B sync is verified.

The DFM5 L step-50K checkpoint was present and launched for full evaluation on
all 8 GPUs while the DFM5 L training run remained active:

```text
checkpoint path: checkpoints/dfm5/L
checkpoint tag:  step_50000
state file:      checkpoints/dfm5/L/checkpoint_state_step_50000.json
wandb project:   DFM5
wandb run id:    oti1lisg
wandb run name:  dfm5-L
tmux session:    dfm5_L_step50000_full_eval
queued jobs:     188
```

The checkpoint state says `epoch=1`, `step=50000`,
`batch_in_epoch=50000`, `global_batch_size=196608`,
`data_path=data/sampled_dfm5`, and `checkpoint_format=sharded`.

Launch command:

```bash
cd /work/dfm/HRM-Text
tmux new-session -d -s dfm5_L_step50000_full_eval \
  'bash /tmp/dfm5_L_step50000_full_eval.sh'
```

The script in `/tmp/dfm5_L_step50000_full_eval.sh` runs:

```bash
cd /work/dfm/HRM-Text
CKPT_PATH=checkpoints/dfm5/L \
CKPT_TAG=step_50000 \
EVAL_EPOCH=0.27608846182186414 \
GPUS=0,1,2,3,4,5,6,7 \
LOG_ROOT=logs/eval/dfm5_L_step50000_full_20260614_dfm5_L_step50000_full \
DFM_LOG_ROOT=logs/dfm_evals/dfm5_L_step50000_full_20260614_dfm5_L_step50000_full \
EUROEVAL_LOG_ROOT=logs/euroeval/dfm5_L_step50000_full_20260614_dfm5_L_step50000_full \
WANDB_SYNC=1 \
WANDB_PROJECT=DFM5 \
WANDB_RUN_ID=oti1lisg \
WANDB_RUN_NAME=dfm5-L \
MODEL_PREFIX=hrm-dfm5-L \
RUN_EUROEVAL=1 \
STANDARD_BATCH_SIZE=8 \
DFM_BATCH_SIZE=8 \
DFM_BATCH_SIZE_GOVREPORT=4 \
DFM_BATCH_SIZE_NORDJYLLANDNEWS=8 \
DFM_BATCH_SIZE_WMT24PP_EN_DA=8 \
DFM_BATCH_SIZE_GENERATIVE_TALEMAADER=8 \
IFEVAL_BATCH_SIZE=16 \
MAX_RETRIES=4 \
EUROEVAL_BIN=/work/dfm/HRM-Text/scripts/euroeval_api_no_flash_attn_guard.py \
scripts/schedule_checkpoint_evals.sh 2>&1 | tee logs/dfm5_L_step50000_full_eval_20260614.log
```

Initial status:

```text
2026-06-14T11:38:54+02:00 QUEUED 188 jobs
2026-06-14T11:38:54+02:00 CHECKPOINT_READY step_50000 path_checkpoints/dfm5/L
2026-06-14T11:38:54+02:00 WORKERS 3046228 3046229 3046230 3046231 3046232 3046233 3046234 3046235
```

At about `2026-06-14T11:42+02:00`, all eight GPUs showed 100% utilization.
The first eight GSM8k shards finished quickly, and the scheduler had moved the
workers onto DROP and MMLU shards. This confirms that the queue can start
later tasks as soon as individual GPUs free up.

Update at `2026-06-14T13:19+02:00`: the initial launch used batch sizes that
were too conservative for the available B200 headroom. A restart with higher
configured batch sizes initially still selected `batch_8` for MATH because
`scripts/schedule_checkpoint_evals.sh` treated the highest previously
successful low-batch telemetry row as a ceiling. The selector was patched so a
prior low-batch success no longer prevents trying a higher configured batch
size; only recorded OOM telemetry lowers the candidate batch size. The eval
queue was restarted with:

```text
STANDARD_BATCH_SIZE=128
STANDARD_BATCH_SIZE_GSM8K=64
STANDARD_BATCH_SIZE_MATH=64
STANDARD_BATCH_SIZE_DROP=32
DFM_BATCH_SIZE=32
DFM_BATCH_SIZE_GOVREPORT=32
DFM_BATCH_SIZE_NORDJYLLANDNEWS=32
DFM_BATCH_SIZE_WMT24PP_EN_DA=32
DFM_BATCH_SIZE_HUMANEVAL=16
DFM_BATCH_SIZE_GENERATIVE_TALEMAADER=16
IFEVAL_BATCH_SIZE=32
EUROEVAL_BATCH_SIZE=16
MAX_RETRIES=5
```

The live process command lines after the second restart showed MATH shards
running with `generation_config.batch_size=64`. Confidence: high.

## 2026-06-12 HRM DFM Headline Workspace

Confidence: high for saved W&B view creation and local manifest.

Superseded: the first saved view used `eval/train_step` as x-axis. A second
view used `eval/epoch` but could still appear to show only the newest 10 panel
runs. A third view set panel `max_runs_to_show=50` but the run sidebar still
used the hidden W&B `runFeed.pageSize=10`, so only 10 run names were visible at
a time. The final corrected saved W&B project view uses three sections:
Danish, English, and Math & Code. It uses the common relogged `eval/epoch`
x-axis, sets `max_runs_to_show=50` on every panel, sets
`runFeed.pageSize=50`, and orders runs by ascending creation time.

```text
name: HRM DFM headline metrics
url:  https://wandb.ai/peter-sk-sdu/HRM%20DFM?nw=dzjdkrcni52
x:    eval/epoch
max:  50 runs per panel
feed: 50 runs in sidebar page
order: CreatedTimestamp ascending
```

The workspace is intentionally grouped by task/language area rather than by
old `standard` versus `dfm_eval` origin. GovReport is treated as an English
summarization metric. DROP is treated as English reading comprehension.
HumanEval, GSM8k, and MATH are placed in the Math & Code section. HumanEval uses the compatibility alias
`eval/humaneval/verify/accuracy`; local HumanEval scoring also had a canonical
`verify_sanitized` key before aliasing.

Sections:

```text
Danish Headline Metrics:
  eval/dala/linguistic-acceptability/dfm_evals_macro_f1
  eval/danish-citizen-tests/knowledge/accuracy
  eval/gec_dala/exact_match/mean
  eval/generative-talemaader/model_graded_fact/accuracy
  eval/ifeval-da/instruction_following/final_acc
  eval/multi_wiki_qa/f1/mean
  eval/nordjyllandnews/rouge2/mean
  eval/piqa/piqa_scorer/accuracy
  eval/wmt24pp-en-da/chrf3pp/mean

English Headline Metrics:
  eval/ARC/acc
  eval/BoolQ/acc
  eval/DROP/f1
  eval/HellaSwag/acc
  eval/MMLU/acc
  eval/Winogrande/acc
  eval/govreport/rouge2/mean

Math & Code Headline Metrics:
  eval/GSM8k/acc
  eval/MATH/acc
  eval/humaneval/verify/accuracy
```

Script and manifest:

```text
scripts/create_hrm_dfm_headline_workspace.py
logs/wandb_workspace_specs/hrm_dfm_headline_metrics_by_language.json
logs/wandb_create_hrm_dfm_headline_workspace_20260612.log
logs/wandb_create_hrm_dfm_headline_workspace_epoch_axis_20260612.log
logs/wandb_create_hrm_dfm_headline_workspace_all_runs_20260612.log
logs/wandb_create_hrm_dfm_headline_workspace_pagesize_20260612.log
logs/wandb_create_hrm_dfm_headline_workspace_three_sections_20260612.log
logs/wandb_create_hrm_dfm_headline_workspace_two_sections_20260612.log
logs/wandb_create_hrm_dfm_headline_workspace_three_sections_final_20260612.log
logs/wandb_create_hrm_dfm_headline_workspace_drop_english_20260612.log
```

Visibility note verified on `2026-06-12`: W&B API lists
`original-sapient-L-full-ema` in project `HRM DFM` even if the saved
workspace run sidebar does not always show it clearly:

```text
run id:   original-sapient-L-full-ema
name:     original Sapient L full EMA
url:      https://wandb.ai/peter-sk-sdu/HRM%20DFM/runs/original-sapient-L-full-ema
state:    finished
created:  2026-06-12T09:22:52Z
```

The source is the old standard full-eval log root
`logs/eval/original_sapient_L/epoch_{1,2,3,4}.log`; the clean relog manifest
contains four checkpoints with 195 parsed metrics each. This run covers the
older English standard suite (`ARC`, `BoolQ`, `DROP`, `GSM8k`, `HellaSwag`,
`MATH`, `MMLU`, `Winogrande`). It does not populate GovReport, HumanEval, or
Danish headline panels. Separate original Sapient L Danish Inspect artifacts
exist under `logs/dfm_evals/original_sapient_L*`, but they were not ingested
into `HRM DFM` because those roots lack `merged*_metrics.json` files.

## 2026-06-12 Original Sapient L EuroEval

Confidence: high for launch and process/log inspection; medium until all
EuroEval jobs finish and W&B sync is verified.

EuroEval was launched for the original Sapient L epoch checkpoints:

```text
checkpoints/original_sapient/L/fsdp2_epoch_{1,2,3,4}
checkpoints/original_sapient/L/carry_epoch_{1,2,3,4}.{0..7}.pt
```

Each checkpoint runs on one GPU:

```text
epoch_1 -> GPU4, port 9741
epoch_2 -> GPU5, port 9742
epoch_3 -> GPU6, port 9743
epoch_4 -> GPU7, port 9744
```

Command:

```bash
cd /work/dfm/HRM-Text
tmux new-session -d -s orig_sapient_l_euroeval \
  'cd /work/dfm/HRM-Text && scripts/run_original_sapient_l_euroeval_epochs.sh'
```

The run uses all Danish and English EuroEval tasks via
`EUROEVAL_LANGUAGES=da,en` and logs to W&B project
`Original Plus Mixed Danish Instruction Rich L`, run id `origLclean`, run name
`original-sapient-L-clean-history`. The x-axis metric is `euroeval/epoch`, with
values `1`, `2`, `3`, and `4`.

Important standard-settings note: the launch does not set
`EUROEVAL_FEW_SHOT`, `EUROEVAL_NUM_ITERATIONS`, or
`EUROEVAL_GENERATIVE_TYPE`; EuroEval therefore uses its upstream defaults.
Initial logs showed `Few-shot benchmarking` and `1/20 benchmarks`.

Operational note: EuroEval 17.3.0 refuses to import when top-level
`flash_attn` is discoverable. Because FA4 is installed for this repo,
`scripts/euroeval_api_no_flash_attn_guard.py` is used as `EUROEVAL_BIN` for
the EuroEval process only. The HRM OpenAI server process still sees FA4.

Primary local logs:

```text
logs/euroeval/original_sapient_L/launcher/status.log
logs/euroeval/original_sapient_L/epoch_{1,2,3,4}/server.log
logs/euroeval/original_sapient_L/epoch_{1,2,3,4}/euroeval.log
```

Status at about `2026-06-12T10:10+02:00`: all four EuroEval processes were
alive and GPUs 4-7 were active. Result rows written so far:

```text
epoch_1 -> 0 rows; still on AngryTweets (1/20)
epoch_2 -> 2 rows; last finished ScaLA-da
epoch_3 -> 2 rows; last finished ScaLA-da
epoch_4 -> 4 rows; last finished MultiWikiQA-da, then started Nordjylland News
```

Epoch 1 is behaving pathologically compared with later checkpoints. The
`epoch_1/euroeval.log` shows repeated batches where the first completion takes
about 80-90 seconds, and one AngryTweets validation pass reached only `145/157`
after about 28 minutes. The local server does not log generated text, so this
does not prove the content is meaningless, but it is strong evidence that
epoch 1 often fails to terminate with the expected short answer and runs near
the generation cap/EOA fallback. Confidence: high for timing/log state, medium
for the interpretation.

Superseded on `2026-06-12T10:22+02:00`: the initial EuroEval run was stopped
and all partial rows were invalidated because `scripts/hrm_openai_server.py`
ignored EuroEval/LiteLLM's `max_completion_tokens` request field. At stop time
the partial result row counts were:

```text
epoch_1 -> 1 row
epoch_2 -> 2 rows
epoch_3 -> 2 rows
epoch_4 -> 4 rows
```

Those rows may have been affected by over-long generations, so the full log
root was archived to avoid reusing old result files or generation caches:

```text
logs/euroeval/original_sapient_L_pre_max_completion_tokens_fix_20260612T102214+0200
```

EuroEval was restarted in tmux session `orig_sapient_l_euroeval` after the
server patch. Initial restarted logs show epoch 1 AngryTweets batches running
at roughly tens of examples per second instead of 80-90 second stalls, which is
consistent with EuroEval's per-task generation caps being honored. Confidence:
high for local process/log inspection.

Second restart on `2026-06-12T10:25+02:00`: the prior post-fix session had
already exited with status `143` for all four epochs and wrote zero corrected
result rows. Its log/cache root was archived before relaunch:

```text
logs/euroeval/original_sapient_L_aborted_restart_20260612T102521+0200
```

Fresh relaunch command used the existing epoch/GPU mapping in
`scripts/run_original_sapient_l_euroeval_epochs.sh`:

```text
epoch_1 -> GPU4, port 9741
epoch_2 -> GPU5, port 9742
epoch_3 -> GPU6, port 9743
epoch_4 -> GPU7, port 9744
```

Launcher status after restart:

```text
2026-06-12T10:25:29+02:00 START epoch_1 gpu_4 port_9741
2026-06-12T10:25:34+02:00 START epoch_2 gpu_5 port_9742
2026-06-12T10:25:39+02:00 START epoch_3 gpu_6 port_9743
2026-06-12T10:25:44+02:00 START epoch_4 gpu_7 port_9744
```

Local inspection confirmed all four `hrm_openai_server.py` processes were
running and serving requests; all four EuroEval client processes were also
alive. Result rows were still `0` for all epochs immediately after relaunch,
as expected during the first benchmark. Confidence: high.

Batch/concurrency restart on `2026-06-12T10:45+02:00`: the corrected bs4 run
had reached two result rows per epoch (`AngryTweets` and `ScaLA-da`) and was
archived before relaunching with larger local batching:

```text
logs/euroeval/original_sapient_L_corrected_bs4_partial_20260612T104523+0200
```

Relaunch environment:

```bash
EUROEVAL_BATCH_SIZE=32 EUROEVAL_MAX_CONCURRENT_CALLS=32
```

Launcher status:

```text
2026-06-12T10:45:23+02:00 START epoch_1 gpu_4 port_9741
2026-06-12T10:45:28+02:00 START epoch_2 gpu_5 port_9742
2026-06-12T10:45:33+02:00 START epoch_3 gpu_6 port_9743
2026-06-12T10:45:38+02:00 START epoch_4 gpu_7 port_9744
```

Local inspection confirmed all four HRM servers were launched with
`--batch-size 32`, and server logs showed `generation: 0/32` batches. GPU
memory increased from about 17-18 GB to about 71-72 GB per GPU, still well
within the 180 GB devices. Confidence: high.

Follow-up EuroEval queue launched on `2026-06-12T11:11+02:00` in tmux session
`queued_dfm_euroevals`. Confidence: high for local launch and status file.

## 2026-06-14 EuroEval Scheduling Fix

Confidence: high for local script inspection and dry-run queue validation.

The single-checkpoint scheduler `scripts/schedule_checkpoint_evals.sh` used to
enqueue EuroEval as one monolithic job:

```text
euroeval  euroeval  0  1
```

This was inconsistent with `scripts/schedule_multiple_checkpoint_evals.sh`,
which already split default Danish+English EuroEval into dataset-level groups.
The practical consequence was that a full single-checkpoint eval could leave
one GPU serially running all 20 EuroEval datasets while the other GPUs were
idle.

As of `2026-06-14`, `scripts/schedule_checkpoint_evals.sh` now defaults to one
EuroEval job per dataset when:

```text
RUN_EUROEVAL=1
EUROEVAL_LANGUAGES=da,en
EUROEVAL_DATASETS is unset
EUROEVAL_TASKS is unset
EUROEVAL_DATASET_GROUPS is unset
```

The default groups are:

```text
angry-tweets
scala-da
dansk
multi-wiki-qa-da
nordjylland-news
danske-talemaader
danish-citizen-tests
hellaswag-da
ifeval-da
valeu-da
sst5
scala-en
conll-en
squad
cnn-dailymail
life-in-the-uk
hellaswag
ifeval
bfcl-v2
valeu-en
```

Dry-run validation:

```bash
cd /work/dfm/HRM-Text
tmp=$(mktemp -d)
RUN_EUROEVAL=1 DRY_RUN=1 \
  LOG_ROOT="$tmp/eval" \
  DFM_LOG_ROOT="$tmp/dfm" \
  EUROEVAL_LOG_ROOT="$tmp/euro" \
  CKPT_PATH=checkpoints/dfm5/XXS-ddp \
  CKPT_TAG=step_50000 \
  WANDB_SYNC=0 \
  scripts/schedule_checkpoint_evals.sh
rg '^euroeval' "$tmp/eval/jobs.tsv"
rm -rf "$tmp"
```

This produced 20 EuroEval jobs alongside the existing standard/dfm-evals jobs:

```text
85 standard
51 dfm
32 dfm_ifeval
20 euroeval
```

Explicit `EUROEVAL_DATASETS` or `EUROEVAL_TASKS` still forces a single EuroEval
invocation over that explicit selection. `EUROEVAL_DATASET_GROUPS` can be used
to define custom semicolon-separated groups.

Operational follow-up for the DFM5 XXS-DDP `step_50000` full eval:
the first full single-checkpoint launch had already started EuroEval as one
monolithic `--language da --language en` job before the scheduler fix. After
Danish IFEval-da finished and wrote its result row, the monolithic EuroEval
process and its parent scheduler were stopped. The completed partial rows
through `ifeval-da` were logged to W&B run `DFM5/pqc9g81u`.

The missing EuroEval datasets were then queued as 11 independent dataset jobs:

```text
valeu-da
sst5
scala-en
conll-en
squad
cnn-dailymail
life-in-the-uk
hellaswag
ifeval
bfcl-v2
valeu-en
```

Launch details:

```text
tmux session: dfm5_xxs_ddp_step50000_euroeval_remaining
status root:  logs/eval/dfm5_XXS_ddp_step50000_full_euroeval_remaining_20260614
result root:  logs/euroeval/dfm5_XXS_ddp_step50000_full_euroeval_remaining_20260614
checkpoint:   checkpoints/dfm5/XXS-ddp step_50000
W&B project:  DFM5
W&B run id:   pqc9g81u
```

The replacement queue finished successfully:

```text
started=11
finished=11
active=0
queued=0
```

Verified result/sync state: each of the 11 replacement dataset directories has
one `euroeval_benchmark_results.jsonl` row, a `merged_metrics.json`, and a
`merge_and_wandb_sync.log` that reports a W&B sync. No matching
`schedule_checkpoint_evals.sh`, `run_euroeval_on_checkpoint.sh`,
`hrm_openai_server.py --ckpt-path checkpoints/dfm5/XXS-ddp --ckpt-tag
step_50000`, or `euroeval_api_no_flash_attn_guard.py` process remained after
completion.

Follow-up repair: because the first scheduler was intentionally stopped after
Danish IFEval-da, its standard/dfm final merge never ran. Local inspection
showed zero `merged_metrics.json` files under the DDP `step_50000`
standard/dfm roots even though all shard logs existed. The fix was to run
merge-only mode:

```bash
cd /work/dfm/HRM-Text
FINAL_MERGE_ONLY=1 \
  LOG_ROOT=logs/eval/dfm5_XXS_ddp_step50000_full_20260614_ddp_step50000_full \
  DFM_LOG_ROOT=logs/dfm_evals/dfm5_XXS_ddp_step50000_full_20260614_ddp_step50000_full \
  EUROEVAL_LOG_ROOT=logs/euroeval/dfm5_XXS_ddp_step50000_full_20260614_ddp_step50000_full \
  CKPT_PATH=checkpoints/dfm5/XXS-ddp \
  CKPT_TAG=step_50000 \
  EVAL_EPOCH=0.27608846182186416 \
  WANDB_SYNC=1 \
  WANDB_PROJECT=DFM5 \
  WANDB_RUN_ID=pqc9g81u \
  WANDB_RUN_NAME=dfm5-XXS-ddp \
  MODEL_PREFIX=hrm-dfm5-XXS-ddp \
  DFM_IFEVAL_SHARDS=32 \
  scripts/schedule_checkpoint_evals.sh 2>&1 | \
  tee logs/eval/dfm5_XXS_ddp_step50000_full_20260614_ddp_step50000_full/final_merge_only_20260614.log
```

This produced `8` standard merged metric files and `11` dfm merged metric
files and synced them to W&B run `DFM5/pqc9g81u`.

The EuroEval metrics for the same checkpoint were split across the original
partial monolithic run and the replacement one-dataset jobs, so a combined
local EuroEval metrics root was created:

```text
logs/euroeval/dfm5_XXS_ddp_step50000_full_combined_20260614/step_50000
```

It contains the partial-through-IFEval-da metrics plus all 11 replacement
dataset metrics. DDP `step_50000` headline averages were then logged with:

```bash
cd /work/dfm/HRM-Text
python scripts/log_dfm5_headline_averages.py \
  --project DFM5 \
  --run-id pqc9g81u \
  --run-name dfm5-XXS-ddp \
  --item 50000:0.27608846182186416:logs/eval/dfm5_XXS_ddp_step50000_full_20260614_ddp_step50000_full:logs/dfm_evals/dfm5_XXS_ddp_step50000_full_20260614_ddp_step50000_full:logs/euroeval/dfm5_XXS_ddp_step50000_full_combined_20260614/step_50000
```

Logged average values:

```text
headline_avg/danish      0.18259303961504936  count=18
headline_avg/english     0.20026344557162082  count=15
headline_avg/math_code   0.01244432180439727  count=4
headline_avg/overall     0.13176693566368916
headline_avg/epoch       0.27608846182186414
headline_avg/train_step  50000
```

Direct W&B API checks confirmed the previously missing headline panel keys are
present on run `DFM5/pqc9g81u` with the expected x-axis values:

```text
eval/ARC/acc                                                   eval/epoch=0.27608846182186414
eval/MATH/acc                                                  eval/epoch=0.27608846182186414
dfm_eval/humaneval/verify_sanitized/accuracy                   dfm_eval/epoch=0.27608846182186414
euroeval/en/reading-comprehension/squad/f1                     euroeval/epoch=0.27608846182186414
euroeval/en/tool-calling/bfcl-v2/tool_calling_accuracy         euroeval/epoch=0.27608846182186414
headline_avg/danish                                            headline_avg/epoch=0.27608846182186414
headline_avg/english                                           headline_avg/epoch=0.27608846182186414
headline_avg/math_code                                         headline_avg/epoch=0.27608846182186414
headline_avg/overall                                           headline_avg/epoch=0.27608846182186414
```

Note: these rows were logged into the active W&B run after training had moved
past 50K, so their internal W&B `_step` values are later than 50K. The DFM5
workspace panels use task-specific epoch x-axes (`eval/epoch`,
`dfm_eval/epoch`, `euroeval/epoch`, `headline_avg/epoch`), so they should plot
at epoch `0.276088...` rather than internal `_step=50000`.

Workspace display follow-up: the average metrics existed in W&B history, but
the DFM5 workspace did not make them obvious enough. On `2026-06-14`, the
workspace creation script was changed to add an explicit first section:

```text
Headline Averages
  headline_avg/overall
  headline_avg/danish
  headline_avg/english
  headline_avg/math_code
```

All four panels use `headline_avg/epoch` as their x-axis. The refreshed view is:

```text
https://wandb.ai/peter-sk-sdu/DFM5?nw=yl894iibtp5
```

Direct W&B API checks after the refresh still found the DDP `step_50000`
average rows:

```text
headline_avg/danish     0.18259303961504936  headline_avg/epoch=0.27608846182186414  headline_avg/train_step=50000
headline_avg/english    0.20026344557162082  headline_avg/epoch=0.27608846182186414  headline_avg/train_step=50000
headline_avg/math_code  0.01244432180439727  headline_avg/epoch=0.27608846182186414  headline_avg/train_step=50000
headline_avg/overall    0.13176693566368916  headline_avg/epoch=0.27608846182186414  headline_avg/train_step=50000
```

Command:

```bash
cd /work/dfm/HRM-Text
tmux new-session -d -s queued_dfm_euroevals \
  'cd /work/dfm/HRM-Text && scripts/queue_epoch_euroevals_on_free_gpus.sh'
```

Queue root:

```text
logs/euroeval/queued_epoch_euroevals_20260612T111142
```

The queue is waiting for any of GPUs 4-7 to become free. At launch all four
were occupied by the active original Sapient L EuroEval servers. Queued jobs
are:

```text
checkpoints/dfm/L epoch_1..epoch_4
checkpoints/dfm4/XL-ddp epoch_1..epoch_2
```

The queue uses `EUROEVAL_BATCH_SIZE=32` and
`EUROEVAL_MAX_CONCURRENT_CALLS=32`. DFM L sync target is W&B project `DFM L`,
run id `kgnbdmwf`; DFM4 XL sync target is project
`Original Plus Mixed Danish Instruction Rich L`, run id
`dfm4xlddpcleanfixed2`.

Superseded on `2026-06-12T13:05+02:00` for the final follow-up queue.
Confidence: high for local process and log inspection. The original
`queued_dfm_euroevals` watcher was stopped after DFM L epoch jobs finished and
GPUs 4-7 became idle, because original Sapient L `epoch_2` had completed only
19/20 EuroEval datasets. The missing dataset was `valeu-da`.

Replacement priority queue launched in tmux session
`priority_valeu_da_then_dfm4`:

```bash
cd /work/dfm/HRM-Text
tmux new-session -d -s priority_valeu_da_then_dfm4 \
  'cd /work/dfm/HRM-Text && scripts/queue_valeu_da_rerun_then_dfm4.sh'
```

Queue root:

```text
logs/euroeval/priority_valeu_da_then_dfm4_20260612T130516
```

Initial starts:

```text
2026-06-12T13:05:16+02:00 START job_0 orig_epoch2_valeu_da/epoch_2 gpu_4 port_9951
2026-06-12T13:05:16+02:00 START job_1 dfm4_XL/epoch_1 gpu_5 port_9952
2026-06-12T13:05:16+02:00 START job_2 dfm4_XL/epoch_2 gpu_6 port_9953
```

The `valeu-da` rerun writes to
`logs/euroeval/original_sapient_L/epoch_2_valeu_da_rerun` and intentionally
does not modify the original epoch-2 JSONL. It should be merged after the row is
verified.

Update at `2026-06-12T13:07+02:00`. Confidence: high for local logs. The
`valeu-da` rerun did not produce a result row. EuroEval aborted with:

```text
No candidate labels found for the predicted label in 4/53 of the samples.
Since this task does not allow invalid model outputs, we have to abort the evaluation.
```

The same priority queue attempt also failed the initial DFM4 starts because the
script used empty TSV fields for optional dataset/extra-arg values, which Bash
collapsed during `read`. `scripts/queue_valeu_da_rerun_then_dfm4.sh` was fixed
to use `-` placeholders and a `SKIP_VAL_RERUN=1` switch. DFM4 XL EuroEval was
relaunched without repeating the known-failing `valeu-da` job:

```text
tmux session: dfm4_xl_euroeval_after_valeuda
queue root:   logs/euroeval/dfm4_xl_after_valeuda_20260612T130752
2026-06-12T13:07:52+02:00 START job_0 dfm4_XL/epoch_1 gpu_4 port_9951
2026-06-12T13:07:52+02:00 START job_1 dfm4_XL/epoch_2 gpu_5 port_9952
```

Constraint update at `2026-06-12T13:14+02:00`. Confidence: high for local
process inspection and script syntax check. The active DFM4 XL jobs are only on
GPU 4 and GPU 5. The running watcher was originally launched with
`gpus_4,5,6,7`, but it has no pending jobs beyond the two already-started DFM4
jobs, so it cannot schedule anything onto GPU 6 or 7. The script default was
changed to `GPUS=4,5` so future launches encode the constraint explicitly.
The queue status file also contains a manual note:

```text
MANUAL_NOTE gpu_constraint current_dfm4_jobs_only_on_4_5 no_pending_jobs_for_6_7 script_default_now_GPUS_4_5
```

## 2026-06-12 DFM4 XL-DDP Corrected W&B History

Confidence: high for local W&B datastore inspection, script output, and W&B API
summary readback.

The original `dfm4xlddpclean` W&B run was made unsafe for continued logging
when full epoch-2 EMA aliases were backfilled at `_step=900000`. The training
resume from `ephemeral_step_865000` then produced valid training locally, but
W&B core ignored rows below its internal current step:

```text
handler: ignoring partial history record, step=865530, current=900001
```

The checkpoint itself was valid and should be resumed with the ephemeral tag,
not the regular-step tag:

```text
resume_checkpoint_tag=ephemeral_step_865000
```

`scripts/clone_dfm4_xl_ddp_clean_wandb.py` now supports a corrected-history
replay. It reads local `.wandb` datastores for `dfm4xlddpclean`, drops the
artificial `_step=900000` row, drops old full-eval alias rows, and re-adds full
EMA `eval/*` and `dfm_eval/*` aliases at the real checkpoint steps:

```text
epoch_1 -> step 367247
epoch_2 -> step 734484
```

The script also supports `--repair-lite-history`. In that mode it drops old
`lite_eval_noema/*`, `lite_dfm_eval_noema/*`, `lite_eval_ema/*`, and
`lite_dfm_eval_ema/*` rows from the source history and rebuilds them from local
merged lite eval artifacts at the actual checkpoint steps. This avoids plotting
lite evals at sync-time W&B steps.

Corrected run created on 2026-06-12:

```text
project: Original Plus Mixed Danish Instruction Rich L
run id:  dfm4xlddpcleanfixed2
name:    dfm4-XL-ddp clean corrected history v2
url:     https://wandb.ai/peter-sk-sdu/Original%20Plus%20Mixed%20Danish%20Instruction%20Rich%20L/runs/dfm4xlddpcleanfixed2
```

Command:

```bash
cd /work/dfm/HRM-Text
python scripts/clone_dfm4_xl_ddp_clean_wandb.py \
  --repair-lite-history \
  --target-run-id dfm4xlddpcleanfixed2 \
  --target-run-name 'dfm4-XL-ddp clean corrected history v2' \
  2>&1 | tee logs/wandb_clone_dfm4_xl_ddp_clean_fixed2_20260612.log
```

Replay summary:

```text
rows replayed: 173158
max step: 865110
dropped old lite rows: 1066
repaired lite checkpoint rows: 34
contains step 900000: false
train rows after 865000: 23
```

Local readback confirmed `lite_eval_*` and `lite_dfm_eval_*` rows at checkpoint
steps such as `50000`, `100000`, `300000`, `367247`, `700000`, `734484`, and
`750000`, with no row at `900000`. W&B API summary readback showed:

```text
clean_history/max_step = 865110
clean_history/replayed_rows = 173158
clean_history/dropped_lite_eval_rows = 1066
clean_history/lite_repair_row_count = 34
train/loss = 0.985303521156311
eval/epoch = 2
dfm_eval/epoch = 2
lite_eval_noema/epoch = 2.0478039350600414
lite_eval_ema/epoch = 2.0478039350600414
```

Use `dfm4xlddpcleanfixed2` as the corrected comparison/backfill run. Do not
continue training into `dfm4xlddpclean`; its local/remote W&B history contains
the bad high-step alias state.

Additional coverage check on 2026-06-12: the corrected local W&B datastore has
EMA and no-EMA lite rows for every complete local 50K checkpoint from
`step_50000` through `step_750000`, plus `epoch_1` at step `367247` and
`epoch_2` at step `734484`. Each of those rows contains all four epoch keys:
`lite_eval_noema/epoch`, `lite_dfm_eval_noema/epoch`,
`lite_eval_ema/epoch`, and `lite_dfm_eval_ema/epoch`. Local merged lite eval
artifacts were not found for `step_800000`, `step_850000`, or
`ephemeral_step_865000`, so those points cannot be backfilled without running
and merging those lite evals first. Confidence: high for local artifact and
W&B-datastore inspection.

## 2026-06-10 DFM4 XL-DDP Step 700K EMA Lite Eval Grooming

Confidence: high for local artifacts and process state; high for W&B API checks.

The `step_700000` EMA lite eval for `checkpoints/dfm4/XL-ddp` completed
locally under:

```text
logs/eval/dfm4_XL_ddp_ema_lite_700k_20260609_lowbs/step_700000
logs/dfm_evals/dfm4_XL_ddp_ema_lite_700k_20260609_lowbs/step_700000
```

Strict local audit passed for all standard lite tasks:

```text
GSM8k, DROP, MMLU, HellaSwag, ARC, Winogrande, BoolQ, MATH
```

Strict local audit passed for all DFM lite tasks:

```text
danish_citizen_tests, dala, gec_dala, wmt24pp_en_da, multi_wiki_qa,
piqa, generative_talemaader, govreport, nordjyllandnews, humaneval,
ifeval_da
```

The last missing tasks were rerun on GPU3 in the foreground queue
`manual_gpu3_gec_multi_fg_20260610T005636`. `gec_dala` completed `512/512`
samples at `2026-06-10T01:40:08+02:00`; `multi_wiki_qa` completed `1024`
samples at `2026-06-10T01:57:06+02:00`. `gec_dala` was slow at batch size 1
under concurrent training, taking about 44 minutes. The earlier detached GPU2
rerun failed because it was launched as a plain background child from a
short-lived shell; use foreground, tmux, or `nohup`/`setsid` for detached
manual queues.

Final local merge command:

```bash
cd /work/dfm/HRM-Text
FINAL_MERGE_ONLY=1 \
CKPT_TAG=step_700000 \
EVAL_EPOCH=1.9112836727227056 \
CKPT_PATH=checkpoints/dfm4/XL-ddp \
LOG_ROOT=logs/eval/dfm4_XL_ddp_ema_lite_700k_20260609_lowbs/step_700000 \
DFM_LOG_ROOT=logs/dfm_evals/dfm4_XL_ddp_ema_lite_700k_20260609_lowbs/step_700000 \
WANDB_SYNC=1 \
WANDB_PROJECT='Original Plus Mixed Danish Instruction Rich L' \
WANDB_RUN_ID=dfm4xlddpclean \
WANDB_RUN_NAME='dfm4-XL-ddp clean lite history' \
EVAL_PREFIX=lite_eval_ema \
DFM_EVAL_PREFIX=lite_dfm_eval_ema \
LITE_EVAL=1 \
LITE_SHARD_INDEX=0 \
NO_EMA=0 \
bash scripts/schedule_checkpoint_evals.sh
```

The final local merge ended with `FINAL_MERGE_END` at
`2026-06-10T02:00:01+02:00`. Per-task merged JSON files were written under each
task directory, for example:

```text
standard_shards/BoolQ/merged_metrics.json
gec_dala/merged_metrics.json
multi_wiki_qa/merged_metrics.json
merged_ifeval_da_metrics.json
```

Important W&B caveat, 2026-06-10. The target run
`peter-sk-sdu/Original Plus Mixed Danish Instruction Rich L/dfm4xlddpclean` was
actively training while the eval backfill was attempted. Separate W&B SDK and
CLI append attempts created correct local `.wandb` history rows, but the rows
did not become visible through the W&B API while the active training process
owned the run. Verified examples:

```text
local backfill .wandb row 1: _step=717690, lite_eval_ema/epoch=1.9112836727227056,
  lite_eval_ema/BoolQ/acc=0.4443, lite_eval_ema/MATH/acc=0.1646
local backfill .wandb row 2: _step=717691, lite_dfm_eval_ema/epoch=1.9112836727227056,
  lite_dfm_eval_ema/multi_wiki_qa/f1/mean=0.823548559665865,
  lite_dfm_eval_ema/gec_dala/exact_match/mean=0.3515625
```

The remote API still showed the previous EMA lite point at
`lite_eval_ema/epoch = 1.638238688802462` and
`lite_dfm_eval_ema/epoch = 1.638238688802462`. Conclusion: the evals are fully
run and merged locally, but remote W&B history sync for the live
`dfm4xlddpclean` run remains pending until the training run is paused/stopped or
the metrics are logged by the active training process itself. Do not treat the
absence of `epoch_1p9112836727227056` keys in W&B as missing local evals.

## 2026-06-08 DFM4 XL-DDP BoolQ/PIQA EMA Gap

Confidence: high for local merged eval artifacts.

Comparing lite no-EMA and EMA metrics from local `merged_metrics.json` files
shows that the recent BoolQ and Danish PIQA gaps are not closing. BoolQ no-EMA
continues improving while EMA stays around `0.44-0.45` after `step_300000`;
the absolute gap grows from `0.1110` at `step_450000` to `0.1459` at
`step_500000`, `0.1618` at `step_550000`, `0.2226` at `step_600000`, and
`0.2764` at `step_650000`.

Danish PIQA is noisier, but EMA is almost flat around `0.1481` while no-EMA
varies widely; the gap is `0.2593` at `step_450000`, `0.2963` at
`step_500000`, `0.0185` at `step_550000`, `0.1481` at `step_600000`, and
`0.3889` at `step_650000`. Interpretation: for BoolQ and PIQA specifically,
EMA is not catching up yet; the recent apparent trend favors no-EMA.

## 2026-06-08 DFM4 XL-DDP Full Eval W&B Prefixes

Confidence: high for local merged metrics and W&B sync output.

The full epoch-1 DFM4 XL-DDP eval backlog first logged full DFM evals under
explicit split prefixes: `dfm_eval_noema/*` and `dfm_eval_ema/*`. Existing
full-eval panels that look for plain `dfm_eval/*` therefore did not show these
values. The EMA full epoch-1 metrics were later aliased to plain `dfm_eval/*`
on W&B run `dfm4xlddpclean` in project
`Original Plus Mixed Danish Instruction Rich L`. Example synced alias:
`dfm_eval/nordjyllandnews/chrf3pp/mean = 36.61799648303162`. The explicit
`dfm_eval_ema/*` and `dfm_eval_noema/*` metrics remain present.

The same prefix issue applied to standard full evals. They were initially
logged as `eval_ema/*` and `eval_noema/*`, while existing panels look for plain
`eval/*`. The EMA full epoch-1 standard metrics were aliased to plain `eval/*`
on the same run. Example synced aliases: `eval/MATH/acc = 0.2840029`,
`eval/BoolQ/acc = 0.4523`, `eval/MMLU/acc = 0.36845`, and
`eval/GSM8k/acc = 0.1258516300227445`. The explicit split-prefix metrics remain
present.

HumanEval uses the local scorer key `verify_sanitized`, so the canonical full
metric is `dfm_eval/humaneval/verify_sanitized/accuracy`. For compatibility
with panels expecting the older `verify` scorer name, EMA full epoch-1 aliases
were also logged as `dfm_eval/humaneval/verify/*` and
`dfm_eval_ema/humaneval/verify/*`. Example:
`dfm_eval/humaneval/verify/accuracy = 0.06097560975609756`.

Epoch-2 repair, 2026-06-11. Confidence: high for local merged metrics, W&B
client output, and W&B API readback. The 2026-06-10 eval campaign completed
epoch-2 full EMA/no-EMA locally and logged explicit split prefixes, but the
plain-panel aliases such as `dfm_eval/nordjyllandnews/chrf3pp/mean` were still
showing the epoch-1 value. `scripts/backfill_dfm4_full_epoch2_plain_alias_wandb.py`
was added to read the already-merged epoch-2 EMA JSON files and log aliases
`dfm_eval_ema/* -> dfm_eval/*` and `eval_ema/* -> eval/*`, plus the HumanEval
compatibility alias `dfm_eval/humaneval/verify/*`.

The first alias attempt logged at W&B history step `163273`, below the run's
current `_step`, so it did not update the latest plain metric values. A second
attempt at explicit `--wandb-step 812076` was ignored because W&B had already
advanced to `812121`. The successful relog used `--wandb-step 900000`.

Command:

```bash
cd /work/dfm/HRM-Text
python scripts/backfill_dfm4_full_epoch2_plain_alias_wandb.py \
  --standard-root logs/eval/dfm4_XL_ddp_eval_campaign_20260610/full_ema/epoch_2 \
  --dfm-root logs/dfm_evals/dfm4_XL_ddp_eval_campaign_20260610/full_ema/epoch_2 \
  --wandb-step 900000
```

API readback after the successful relog:

```text
_step = 900000
dfm_eval/epoch = 2
dfm_eval/nordjyllandnews/chrf3pp/mean = 36.57873558881677
dfm_eval/nordjyllandnews/chrf3pp/stderr = 0.350586469648215
dfm_eval/humaneval/verify/accuracy = 0.054878048780487805
eval/epoch = 2
eval/MATH/acc = 0.28720693999999997
```

No-EMA comparison run, 2026-06-11. Confidence: high for local merged metrics,
W&B client output, and W&B API readback. A new W&B run was created for comparing
full no-EMA evals separately from the EMA/full run:

```text
project: Original Plus Mixed Danish Instruction Rich L
run id:  dfm4xlddpnoema
name:    dfm4-XL-ddp-noema
```

The run was backfilled from stored merged metrics only; no inference was rerun.
It aliases `eval_noema/* -> eval/*` and `dfm_eval_noema/* -> dfm_eval/*` for
epoch 1 and epoch 2, plus the HumanEval compatibility alias
`dfm_eval/humaneval/verify/*`.

Command:

```bash
cd /work/dfm/HRM-Text
python scripts/backfill_dfm4_full_noema_new_run_wandb.py \
  --eval 1:logs/eval/dfm4_XL_ddp_noema_full_epoch1_20260608/epoch_1:logs/dfm_evals/dfm4_XL_ddp_noema_full_epoch1_20260608/epoch_1 \
  --eval 2:logs/eval/dfm4_XL_ddp_eval_campaign_20260610/full_noema/epoch_2:logs/dfm_evals/dfm4_XL_ddp_eval_campaign_20260610/full_noema/epoch_2 \
  --project "Original Plus Mixed Danish Instruction Rich L" \
  --run-id dfm4xlddpnoema \
  --run-name dfm4-XL-ddp-noema
```

API readback:

```text
epoch 1:
  eval/MATH/acc = 0.23919526000000002
  dfm_eval/nordjyllandnews/chrf3pp/mean = 36.57039389543406
  dfm_eval/humaneval/verify/accuracy = 0.018292682926829267
epoch 2:
  eval/MATH/acc = 0.30840231999999995
  dfm_eval/nordjyllandnews/chrf3pp/mean = 36.634404429441005
  dfm_eval/humaneval/verify/accuracy = 0.17682926829268292
```

## 2026-06-09 Posttrain Generated Dataset Size

Confidence: high for local byte counts; medium for final-size extrapolation.

During the post-training transform/refine generation-to-1M run,
`data/generated_posttrain_transform_refine` contained `938` JSONL files totaling
`4,715,088,900` bytes (`4.391 GiB`) at about `934,065` generated rows counted by
the progress script. Scaling linearly gives an expected final generated JSONL
size around `5.0e9` bytes (`4.7 GiB`) for one million rows, before any separate
regeneration output. The missing-request shard tree
`data/synthetic_request_shards_posttrain_transform_refine_v3_missing` was about
`2.4G` on disk.

Token estimate, 2026-06-09. Confidence: medium-high for sampled tokenizer
measurement; medium for final extrapolation. A random sample of `20,001`
generated JSONL rows (`19,029` accepted) tokenized with
`data_io/trained_tokenizers/bpe/tokenizer.json`, using only the fields that
`convert-generated` keeps (`instruction` and `response`) plus a small special
token overhead, averaged `823` tokens per accepted row. That implies about
`0.45B` tokens for a `550k` accepted-row tranche and about `0.82B` tokens for a
`1M` accepted-row generated set before sampling repeats. The current
`prefix_config_posttrain_transform_refine.yaml` repeats synthetic prefixes
`20x`, so sampled per-epoch synthetic token contribution can be much larger
than the raw unique-token count unless caps/repeats are adjusted.

Generation wrapper bug, 2026-06-09. Confidence: high for local process
inspection. `scripts/run_posttrain_synthetic_generation_vllm.sh` originally
used a bare `wait` after launching both vLLM servers and shard workers. With
`STOP_SERVERS_ON_EXIT=0`, phase 1 of
`scripts/run_posttrain_transform_refine_to_1m_vllm.sh` finished all `550/550`
missing shards but remained stuck because the bare `wait` also waited for the
long-lived vLLM server processes. The script was patched to collect worker PIDs
and wait only for those worker PIDs. Existing already-running instances that
entered the old bare `wait` remain stuck until manually advanced or restarted.

Recovery action, 2026-06-09. Confidence: high for local launch output. The
stale phase-1 wrapper PIDs were stopped after confirming all `550/550` missing
generation shards were complete and failed count was zero. The eight existing
vLLM teacher servers on ports `8100`-`8107` were kept alive. A recovery script
was added at `scripts/resume_posttrain_transform_refine_to_1m_after_generation.sh`
to run phases 2-4 directly against the completed generated root. It was launched
in tmux window `posttrain_to_1m:3`, log
`logs/posttrain_transform_refine_to_1m_resume_20260609T083026.log`, and started
eight `audit-generated` processes under audit root
`logs/posttrain_transform_refine_generation/audits_to_1m_resume_20260609T083026`.

Recovery monitor, 2026-06-09. Confidence: high for local tmux and monitor
output. A clean per-GPU monitor was added at
`scripts/monitor_posttrain_to_1m_recovery.py` and launched in tmux window
`hrm-1:7`. It tracks the active audit root, per-GPU audited rows/current file,
aggregate row rate, audit ETA, and GPU memory/utilization. The English-source
audit denominator is `500,000` generated rows: GPU row targets are
`65000, 64000, 62000, 60000, 61000, 61000, 63000, 64000` for GPUs 0-7. At
`2026-06-09 08:34:01 CEST`, the audit had written `19,866/500,000` rows
(`3.97%`) at about `92.7` rows/s, with an audit ETA of about `86.3` minutes.

Posttrain 1M recovery completion, 2026-06-09. Confidence: high for local queue
and process inspection. The recovery completed the final regeneration phase:
`318/318` regeneration shards were done, `0` failed, and regenerated outputs
were written to `data/generated_posttrain_transform_refine_regen_from_audit`.
The final phase had `3,829` regeneration rows. After completion, the eight
Gemma/vLLM teacher servers on ports `8100`-`8107` were terminated with
`SIGTERM`; `nvidia-smi` then reported `0 MiB` used on GPUs 0-7.

DFM4 XL-DDP step 700K lite eval launch, 2026-06-09. Confidence: high for local
tmux and scheduler logs. `scripts/run_dfm4_xl_ddp_lite_eval_700k.sh` launches
the `step_700000` no-EMA lite eval followed by the EMA lite eval, both syncing
to W&B run `dfm4xlddpclean` in project
`Original Plus Mixed Danish Instruction Rich L`. The x-axis value is
`1.9112836727227056`, computed from `700000 / (1831230 / 5)`. The active tmux
session is `dfm4_lite_eval_700k`; pane 1 runs the launcher and pane 2 runs
`scripts/watch_multi_checkpoint_eval_progress.py` for the no-EMA log roots.
Initial no-EMA telemetry showed `GSM8k` at batch size `128` OOMed with
`peak_used_mib=181576`, then succeeded at batch size `64` with
`peak_used_mib=151090`.

Follow-up status, 2026-06-09. Confidence: high for local tmux/status logs. The
`step_700000` no-EMA lite eval completed successfully and final merge ended
with `status_0` at `2026-06-09T21:01:12+02:00`. The five HRM server-backed DFM
tasks that OOM-looped at batch size `64` were retried at batch size `32` and
finished successfully: `piqa`, `danish_citizen_tests`, `gec_dala`,
`multi_wiki_qa`, and `dala`. The EMA half did not start in that tmux run: after
the no-EMA finish, the launcher exited with `unexpected EOF while looking for
matching '"'`, likely because the script was edited while the shell was still
reading it. The on-disk launcher validates with `bash -n` after the edit. At
inspection time, the DFM4 XL-DDP training run had resumed from `step_700000`
and was occupying all eight GPUs; no EMA lite eval scheduler/status file existed
under `logs/eval/dfm4_XL_ddp_ema_lite_700k_20260609`.

EMA low-headroom launch, 2026-06-09. Confidence: high for local command and
initial monitor output. After explicit no-EMA final merge/resync completed with
`FINAL_MERGE_END`, the `step_700000` EMA lite eval was launched while training
was active, using the earlier low-headroom pattern:

```text
LOG_ROOT_BASE=logs/eval/dfm4_XL_ddp_ema_lite_700k_20260609_lowbs
DFM_LOG_ROOT_BASE=logs/dfm_evals/dfm4_XL_ddp_ema_lite_700k_20260609_lowbs
GPUS=0,3,2
STANDARD_BATCH_SIZE=1
DFM_BATCH_SIZE=1
IFEVAL_BATCH_SIZE=1
NO_EMA=0
EVAL_PREFIX=lite_eval_ema
DFM_EVAL_PREFIX=lite_dfm_eval_ema
```

The run is in tmux session `dfm4_lite_eval_700k_ema_lowbs`. Initial active
jobs were IFEval-DA on GPU0, MATH on GPU3, and GSM8k on GPU2. At
`2026-06-09T21:58:59`, GSM8k had progressed to `71/165`, MATH had loaded, and
IFEval-DA had started; GPU2 had only about `123 MiB` free, so this remains a
tight low-headroom run.

## 2026-06-08 Ephemeral Training Checkpoints

Confidence: high for local code inspection and validation.

`pretrain.py` now supports opt-in ephemeral resumability checkpoints:

```text
ephemeral_checkpoint_step_interval: null
```

Set this to an integer `N` to save a resumability checkpoint every `N`
optimizer steps. Ephemeral checkpoints use the tag `ephemeral_step_<step>` and
the same checkpoint format as the run (`fsdp2_ephemeral_step_<step>` for
sharded, `unsharded_ephemeral_step_<step>.pt` for unsharded). After a
successful ephemeral save, older `ephemeral_step_*` artifacts are deleted. If
the same step also writes a regular `checkpoint_step_interval` checkpoint, the
regular `step_<step>` checkpoint is kept and older ephemeral checkpoints are
deleted instead of writing a duplicate ephemeral copy.

Resume accepts the same checkpoint path plus:

```text
resume_checkpoint_tag=ephemeral_step_<step>
```

The inference loader also accepts `ckpt_tag=ephemeral_step_<step>` for smoke
tests or evals. Validation run locally:

```bash
cd /work/dfm/HRM-Text
python -m py_compile pretrain.py simple_inference_engine.py
```

## 2026-06-08 DFM4 XL-DDP Step 650K Lite Eval Launch

Confidence: high for local code changes and launch logs.

Before launching the `step_650000` lite eval while all GPUs were free, two eval
scheduler safeguards were added:

- `scripts/merge_dfm_eval_shards.py` now raises on zero DFM samples instead of
  writing/logging zero-sample metrics. This prevents the final merge path from
  overwriting correct incremental metrics when expected `.eval` artifacts are
  missing or incomplete.
- `scripts/schedule_checkpoint_evals.sh` now supports per-task batch-size
  overrides via environment variables such as `STANDARD_BATCH_SIZE_MATH=32` or
  `DFM_BATCH_SIZE_GOVREPORT=8`. The existing retry behavior still halves the
  selected per-task batch size after failures/OOMs.

Validation:

```bash
cd /work/dfm/HRM-Text
python -m py_compile scripts/merge_dfm_eval_shards.py
bash -n scripts/schedule_checkpoint_evals.sh
bash -n scripts/schedule_multiple_checkpoint_evals.sh
bash -n scripts/run_talemaader_split_gpu_eval.sh
```

The `step_650000` no-EMA lite eval was launched in tmux session
`dfm4_lite_eval_650k` with all eight GPUs free. Exact epoch x-coordinate:
`1.7747585795360006`.

```bash
cd /work/dfm/HRM-Text
env PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  LOG_ROOT_BASE=logs/eval/dfm4_XL_ddp_noema_lite_650k_20260608_freegpus \
  DFM_LOG_ROOT_BASE=logs/dfm_evals/dfm4_XL_ddp_noema_lite_650k_20260608_freegpus \
  CKPT_TAGS=step_650000 \
  EVAL_EPOCHS=1.7747585795360006 \
  CKPT_PATH=checkpoints/dfm4/XL-ddp \
  GPUS=0,1,2,3,4,5,6,7 \
  JUDGE_GPU=0 \
  LITE_EVAL=1 \
  LITE_SHARD_INDEX=0 \
  QUEUE_ORDER=heavy_first \
  MAX_RETRIES=5 \
  NO_EMA=1 \
  WANDB_SYNC=1 \
  WANDB_PROJECT='Original Plus Mixed Danish Instruction Rich L' \
  WANDB_RUN_ID=dfm4xlddpclean \
  WANDB_RUN_NAME='dfm4-XL-ddp clean lite history' \
  EVAL_PREFIX=lite_eval_noema \
  DFM_EVAL_PREFIX=lite_dfm_eval_noema \
  MODEL_PREFIX=hrm-dfm4-XL-ddp-noema \
  STANDARD_BATCH_SIZE=64 \
  DFM_BATCH_SIZE=32 \
  IFEVAL_BATCH_SIZE=16 \
  STANDARD_BATCH_SIZE_MATH=32 \
  STANDARD_BATCH_SIZE_DROP=16 \
  DFM_BATCH_SIZE_GOVREPORT=8 \
  DFM_BATCH_SIZE_NORDJYLLANDNEWS=16 \
  DFM_BATCH_SIZE_WMT24PP_EN_DA=16 \
  DFM_BATCH_SIZE_HUMANEVAL=8 \
  DFM_BATCH_SIZE_GENERATIVE_TALEMAADER=8 \
  bash scripts/schedule_multiple_checkpoint_evals.sh
```

Early status: the scheduler started eight workers and assigned the first eight
jobs across GPUs 0-7. `GSM8k` completed successfully at batch size `64` with no
OOM and synced incrementally.

Headroom observation during the same launch, 2026-06-08. Confidence: high for
the live `nvidia-smi` snapshot; medium for future batch-size recommendations.

While the first wave of `step_650000` lite evals was running, observed GPU
memory left substantial headroom:

```text
IFEval-DA:        batch 16, ~52.4 GiB used, ~130.2 GiB free
MATH:             batch 32, ~77.1 GiB used, ~105.6 GiB free
DROP:             batch 16, ~40.4 GiB used, ~142.2 GiB free
MMLU:             batch 64, ~6.5 GiB used, ~176.1 GiB free
HellaSwag:        batch 64, ~6.4 GiB used, ~176.2 GiB free
WMT24++ en-da:    batch 16, ~52.4 GiB used, ~130.2 GiB free
```

Safe completed tasks from telemetry:

```text
GSM8k:      batch 64, status 0, no OOM
Winogrande: batch 64, status 0, no OOM
ARC:        batch 64, status 0, no OOM
GovReport:  batch 8,  status 0, no OOM
```

For the next all-GPU/no-training lite eval, reasonable starting candidates are
`STANDARD_BATCH_SIZE=128`, `STANDARD_BATCH_SIZE_MATH=64`,
`STANDARD_BATCH_SIZE_DROP=32`, `DFM_BATCH_SIZE=64`,
`DFM_BATCH_SIZE_GOVREPORT=16`, `DFM_BATCH_SIZE_WMT24PP_EN_DA=32`,
`DFM_BATCH_SIZE_NORDJYLLANDNEWS=32`, `DFM_BATCH_SIZE_HUMANEVAL=16`,
`DFM_BATCH_SIZE_GENERATIVE_TALEMAADER=16`, and `IFEVAL_BATCH_SIZE=32`, while
keeping `MAX_RETRIES>=5` so the scheduler halves on OOM/failure.

Future eval telemetry update, 2026-06-08. Confidence: high for local dry-run
validation. `scripts/schedule_checkpoint_evals.sh` now records
`peak_used_mib` in `eval_attempts.tsv` for each eval attempt. The value is
sampled with `nvidia-smi` around each worker job and stored beside task, shard,
GPU, batch size, status, OOM flag, before-memory, and after-memory. Existing
telemetry files without this column are migrated on scheduler startup; old rows
receive `peak_used_mib=NA`, while new rows receive measured values. Sampling
interval defaults to `GPU_MEM_PEAK_POLL_SECONDS=2`.

EMA high-batch follow-up for `step_650000`, 2026-06-08. Confidence: high for
local logs and telemetry. The EMA lite eval was run locally under:

```text
logs/eval/dfm4_XL_ddp_ema_lite_650k_20260608_highbs_retry/step_650000
logs/dfm_evals/dfm4_XL_ddp_ema_lite_650k_20260608_highbs_retry/step_650000
```

No W&B sync was performed for this run (`WANDB_SYNC=0`). Local final merge
completed successfully. During this run two scheduler issues were found and
fixed in `scripts/schedule_checkpoint_evals.sh`:

- the peak-memory sampler originally kept command substitution open when
  launched in the background; it now redirects stdout/stderr to `/dev/null`;
- failed standard eval jobs returned while `set -e` was still disabled, so a
  child scheduler could exit before retrying/logging telemetry; this path now
  preserves retry/telemetry behavior.

Batch-size findings from `peak_used_mib`:

```text
GSM8k batch 128: OOMed; batch 64 succeeded, peak ~151090 MiB
MATH batch 64: succeeded, peak ~151092 MiB
DROP batch 32: succeeded, peak ~77404 MiB
ARC/BoolQ/HellaSwag/MMLU/Winogrande batch 128: succeeded, peak only ~6-7 GiB
DFM server tasks batch 64: OOMed for gec_dala, multi_wiki_qa,
  danish_citizen_tests, dala, and piqa
DFM server tasks batch 32: succeeded, peak ~101748-101756 MiB
GovReport batch 16: succeeded, peak ~52886 MiB
HumanEval batch 16: succeeded, peak ~52394 MiB
Generative Talemaader batch 16: succeeded, peak ~68462 MiB
IFEval-DA batch 32: succeeded, peak ~101748 MiB
```

Recommended next no-training lite eval defaults from this run:

```text
STANDARD_BATCH_SIZE=128
STANDARD_BATCH_SIZE_GSM8K=64
STANDARD_BATCH_SIZE_MATH=64
STANDARD_BATCH_SIZE_DROP=32
DFM_BATCH_SIZE=32
DFM_BATCH_SIZE_GOVREPORT=16
DFM_BATCH_SIZE_HUMANEVAL=16
DFM_BATCH_SIZE_GENERATIVE_TALEMAADER=16
IFEVAL_BATCH_SIZE=32
```

Do not use generic `STANDARD_BATCH_SIZE=128` without overriding `GSM8k` to 64;
do not use generic `DFM_BATCH_SIZE=64` for HRM server-backed DFM tasks on this
checkpoint/model because it leaves less than 1 GiB free and causes cache
allocation OOMs.

DFM4 XL-DDP eval backlog launch, 2026-06-08. Confidence: high for local launch
logs; medium for runtime estimates. A sequential tmux driver was launched in
session `dfm4_xl_ddp_eval_backlog_20260608`:

```text
logs/eval/dfm4_XL_ddp_eval_backlog_20260608/driver.log
```

The driver first runs missing EMA lite evals, then full epoch-1 no-EMA evals,
then full epoch-1 EMA evals. All sync to W&B run `dfm4xlddpclean` in project
`Original Plus Mixed Danish Instruction Rich L`.

Missing EMA lite checkpoints queued:

```text
step_50000, step_100000, step_150000, step_300000, step_350000,
epoch_1, step_400000, step_450000, step_500000, step_550000, step_600000
```

Corresponding x-axis epoch values:

```text
0.1365198907335385, 0.273039781467077, 0.4095596722006155,
0.819119344401231, 0.9556392351347696, 1,
1.092159125868308, 1.2286790166018464, 1.365198907335385,
1.5017187980689235, 1.638238688802462
```

Log roots and metric prefixes:

```text
EMA lite:
  logs/eval/dfm4_XL_ddp_ema_lite_missing_20260608
  logs/dfm_evals/dfm4_XL_ddp_ema_lite_missing_20260608
  lite_eval_ema/* and lite_dfm_eval_ema/*

Full epoch_1 no-EMA:
  logs/eval/dfm4_XL_ddp_noema_full_epoch1_20260608
  logs/dfm_evals/dfm4_XL_ddp_noema_full_epoch1_20260608
  eval_noema/* and dfm_eval_noema/*

Full epoch_1 EMA:
  logs/eval/dfm4_XL_ddp_ema_full_epoch1_20260608
  logs/dfm_evals/dfm4_XL_ddp_ema_full_epoch1_20260608
  eval_ema/* and dfm_eval_ema/*
```

Batch-size policy:

```text
STANDARD_BATCH_SIZE=128
STANDARD_BATCH_SIZE_GSM8K=64
STANDARD_BATCH_SIZE_MATH=64
STANDARD_BATCH_SIZE_DROP=32
DFM_BATCH_SIZE=32
DFM_BATCH_SIZE_GOVREPORT=16
DFM_BATCH_SIZE_HUMANEVAL=16
DFM_BATCH_SIZE_GENERATIVE_TALEMAADER=16
IFEVAL_BATCH_SIZE=32
MAX_RETRIES=5
```

Observed start: the first EMA lite checkpoint (`step_50000`) spent about four
minutes in checkpoint/EMA load with eight concurrent workers before tasks began
to complete. This makes the missing-lite sweep likely slower than the warm
single-checkpoint `step_650000` run. Runtime estimate: missing EMA lite sweep
roughly `2.5-3.5h`; full epoch-1 no-EMA roughly `1.5-2.0h`; full epoch-1 EMA
roughly `1.5-2.5h`; full sequential backlog roughly `5.5-8h` depending on
checkpoint-load pressure and W&B sync latency.

DFM4 XL-DDP EMA vs no-EMA lite comparison through `step_500000`, 2026-06-08.
Confidence: high for local merged metric files; medium for interpretation
because lite evals use one shard per task and equal-weighting heterogeneous
metrics is only a rough summary. Comparing 98 higher-is-better score metrics at
each 50K checkpoint:

```text
checkpoint  EMA better  EMA worse  same  mean delta  median delta
50K         35          61         2     -0.4332     -0.0165
100K        22          73         3     -0.5193     -0.0438
150K        23          73         2     -0.4637     -0.0410
200K        60          28         10    +0.0387     +0.0230
250K        43          42         13    -0.0013     +0.0000
300K        64          30         4     +0.0249     +0.0261
350K        65          25         8     +0.0331     +0.0261
400K        57          31         10    +0.0244     +0.0025
450K        39          49         10    -0.0080     -0.0001
500K        42          47         9     -0.0044     +0.0000
```

Interpretation: before and through 150K, EMA is badly damaged, matching the
known EMA precision bug period. After the 150K reset, EMA is no longer
catastrophic and is broadly competitive: 200K, 300K, 350K, and 400K are net
positive on this equal-weighted lite comparison. By 450K-500K it becomes mixed
to slightly negative. Task-level pattern is also mixed: EMA often helps
MATH/DROP/IFEval-Da/DALA-like metrics, while no-EMA remains better on several
binary/classification or exact-choice tasks such as BoolQ, PIQA, ARC, and
Danish citizen tests.

## 2026-06-08 DFM4 XL-DDP Lite Eval Step 600K Talemaader Rerun

Confidence: high for local logs/processes.

For `checkpoints/dfm4/XL-ddp` `step_600000` no-EMA lite eval, the original
scheduler failed to produce `generative_talemaader` artifacts. The child job
retried four times and ended with `status_1`, while the parent aggregate status
misleadingly recorded a successful end for that task. Rerunning with the Gemma
judge colocated on GPU0 also failed: the judge used about `15.4 GiB`, leaving
only `22 MiB` free, and `scripts/hrm_openai_server.py` OOMed during model
construction.

The active workaround is to run the Gemma judge CPU-only and the HRM server on
GPU0:

```bash
cd /work/dfm/HRM-Text
CUDA_VISIBLE_DEVICES='' /home/ucloud/miniforge3/envs/hrm/bin/python \
  scripts/transformers_openai_server.py unsloth/gemma-4-E4B-it \
  --served-model-name gemma-4-e4b-judge-cpu \
  --host 127.0.0.1 --port 9799

env CKPT_PATH=checkpoints/dfm4/XL-ddp \
  CKPT_TAG=step_600000 \
  EVAL_EPOCH=1.6337778116635397 \
  LOG_ROOT=logs/dfm_evals/dfm4_XL_ddp_noema_lite_600k_talemaader_cpujudge_rerun_20260608T074615 \
  MODEL_GPU=0 \
  MODEL_PORT=9788 \
  MODEL_NAME=hrm-dfm4-XL-ddp-noema-generative_talemaader-step_600000 \
  JUDGE_SERVED_NAME=gemma-4-e4b-judge-cpu \
  EXISTING_JUDGE_BASE_URL=http://127.0.0.1:9799/v1 \
  SHARD_INDEX=0 \
  NUM_SHARDS=8 \
  NO_EMA=1 \
  PREFIX=lite_dfm_eval_noema \
  WANDB_SYNC=1 \
  WANDB_PROJECT='Original Plus Mixed Danish Instruction Rich L' \
  WANDB_RUN_ID=dfm4xlddpclean \
  WANDB_RUN_NAME='dfm4-XL-ddp clean lite history' \
  WAIT_FOR_MODEL_GPU_FREE_MB=10000 \
  BATCH_SIZE=1 \
  BATCH_TIMEOUT_MS=25 \
  bash scripts/run_talemaader_split_gpu_eval.sh
```

At launch, both servers reached health, the HRM server served completions, and
the CPU judge served judged requests. This workaround is slower than GPU judge
serving but avoids disturbing the active DFM4 XL-DDP training.

Completion/repair update, 2026-06-08. Confidence: high. The `step_600000`
no-EMA lite eval finished, including `MATH`. Standard evals synced correctly.
Several DFM evals had correct incremental syncs, but the later final merge path
rewrote local merged files and W&B rows with zero-sample DFM metrics at the
same epoch. The correct metrics were repaired by re-merging directly from the
`.eval` artifacts and re-syncing to W&B run `dfm4xlddpclean` under
`lite_dfm_eval_noema/*`.

Repair output root:

```text
logs/dfm_evals/dfm4_XL_ddp_noema_lite_600k_repair_sync_20260608T092912
```

All repair logs reported successful W&B sync. Correct repaired sample counts:

```text
dala:                 2048
danish_citizen_tests: 545
gec_dala:             512
generative_talemaader:101
govreport:            61
humaneval:            41
ifeval-da:            17
multi_wiki_qa:        1024
nordjyllandnews:      125
piqa:                 108
wmt24pp_en_da:        120
```

Known risk: because W&B history is append-only, the earlier zero-sample rows
may still exist at the same `lite_dfm_eval_noema/epoch` x-coordinate. The
latest repaired rows are correct, but plots may need filtering or a clean
history clone if duplicate same-x rows are visually confusing.

## 2026-06-04 Post-Training Transformation Refine Dataset

Confidence: high for local artifacts and command results; medium for downstream
effect until fine-tuning/eval.

A separate post-training dataset family was added for refining final
checkpoints on controlled transformations:

```text
config/data/posttrain_transform_refine.yaml
data_io/prefix_config_posttrain_transform_refine.yaml
scripts/prepare_posttrain_transform_refine.py
scripts/prepare_posttrain_transform_refine.sh
scripts/build_tokenized_posttrain_transform_refine_tree.py
```

Completed locally:

- Downloaded `grammarly/coedit`, `Muennighoff/natural-instructions`, and
  `facebook/asset` into `data/downloads/datasets/posttrain_*`.
- Converted `70,783` CoEdIT rows and `500,000` filtered Super-NI rows to
  `data/converted_sources_posttrain_transform_refine`.
- Created `500,000` synthetic request records under
  `data/synthetic_requests_posttrain_transform_refine`, split across five task
  families and Danish/English.
- Installed/configured Rust stable locally with `rustup default stable` because
  the shell had no Rust toolchain.
- Tokenized existing post-training rows to
  `data/tokenized_posttrain_transform_refine_existing`.
- Built `data/tokenized_posttrain_transform_refine`, linking `4,117` selected
  tokenized tasks.
- Sampled `data/sampled_posttrain_transform_refine` with `EPOCHS=1`; metadata
  reports `total_length=29,131,369,710` tokens.

Synthetic responses have not yet been generated. Later steps:

```bash
cd /work/dfm/HRM-Text
GEMMA_OPENAI_BASE_URL=http://127.0.0.1:8000/v1 \
GEMMA_TEACHER_MODEL=gemma-4-31b \
scripts/prepare_posttrain_transform_refine.sh generate-synthetic
scripts/prepare_posttrain_transform_refine.sh convert-synthetic
WORKERS=2 scripts/prepare_posttrain_transform_refine.sh tokenize-synthetic
scripts/prepare_posttrain_transform_refine.sh build-tokenized-tree
CONCAT_WORKERS=2 EPOCHS=1 scripts/prepare_posttrain_transform_refine.sh sample
```

While sampling, `data_io/sample_tokenized.py` was fixed to size its epoch buffer
by repeated sampled rows, not unique rows. This fixed the repeat-heavy
post-training config failure.

Teacher model selection, 2026-06-04. Confidence: high for local file
inspection.

The intended synthetic-data teacher is the local instruction-tuned Gemma 4 31B:

```text
GEMMA_MODEL_PATH=/work/dfm/brainsurgery/models/google/gemma-4-31B-it
```

Local inspection found both base and instruction-tuned 31B directories:

```text
/work/dfm/brainsurgery/models/gemma4_31b
/work/dfm/brainsurgery/models/google/gemma-4-31B
/work/dfm/brainsurgery/models/google/gemma-4-31B-it
```

`gemma4_31b` and `google/gemma-4-31B` have identical `config.json` files and
represent the base model. `google/gemma-4-31B-it` has a different config and
generation config, and is the better default for generating instruction-style
synthetic responses. Empty-looking alias dirs such as
`/work/dfm/brainsurgery/models/gemma4-31b` should not be used.

Synthetic generation launch update, 2026-06-04. Confidence: high for local
commands/logs; low-to-medium for output quality until prompts/validators are
fixed.

The 8x single-GPU vLLM generation run for `posttrain_transform_refine` required
several environment fixes:

- `deep-gemm==2.5.0+88965b0` was installed from a recursive local clone at
  `external/DeepGEMM` because the PyPI sdist lacked CUTLASS submodule files.
- A CUDA 13.2 shim was created at `external/cuda-13.2-shim` with `bin`,
  `include`, and `lib64` symlinks into the local CUDA toolkit layout. The build
  also needed CUDA 13 headers/libs from
  `/home/ucloud/miniforge3/envs/hrm/lib/python3.13/site-packages/nvidia/cu13`.
- vLLM 0.20.2 with FlashAttention 4 needed a local site-packages patch so
  `flash_attn.ops.triton.rotary` import failure falls back instead of crashing.
- The local Gemma 4 31B IT checkpoint has weights/tokenizer/config but no
  processor files. For text-only synthetic generation, vLLM must be launched
  with `--hf-overrides '{"architectures":["Gemma4ForCausalLM"]}'`.
- That text-only override exposes no chat template, so
  `scripts/prepare_posttrain_transform_refine.py generate-synthetic` was changed
  to call `/v1/completions` with an explicit prompt wrapper rather than
  `/v1/chat/completions`.
- `scripts/run_posttrain_synthetic_generation_vllm.sh` now exports `CUDA_HOME`,
  `DG_JIT_NVCC_COMPILER`, and `LD_LIBRARY_PATH` for DeepGEMM/vLLM, and its
  shard-claim loop retries after `mv` races so all workers can claim shards.

The active launch command in tmux session `posttrain_gen:runner` is:

```bash
cd /work/dfm/HRM-Text
env VLLM_PYTHON=/home/ucloud/miniforge3/envs/hrm/bin/python \
  CLIENT_PYTHON=/home/ucloud/miniforge3/envs/hrm/bin/python \
  GEMMA_MODEL_PATH=/work/dfm/brainsurgery/models/google/gemma-4-31B-it \
  SERVED_MODEL_NAME=posttrain-gemma-teacher \
  GPU_LIST=0,1,2,3,4,5,6,7 \
  REQUESTS_PER_SHARD=1000 \
  CLIENT_CONCURRENCY=8 \
  scripts/run_posttrain_synthetic_generation_vllm.sh
```

Observed live behavior at 22:26-22:28 CEST:

```text
Memory:      ~165,870 MiB / 183,359 MiB per B200
Utilization: ~96-100%, usually 100%
Power:       ~722-754 W in one snapshot
Throughput:  359 rows in 74 s ~= 4.85 rows/s globally, ~=0.61 rows/s/GPU
ETA:         500,000 rows / 4.85 rows/s ~= 28.6 h if this speed holds
```

Important quality warning: the first sampled completion output after switching
to `/v1/completions` was non-empty but degenerate (`"l l l ..."`) and passed
the current weak validators. Do not treat synthetic output from the old
text-only/completions run as usable.

Superseding update, 2026-06-04. Confidence: high. A fresh copy of
`google/gemma-4-31B-it` was downloaded inside this checkout and must be used
instead of the older incomplete local copy:

```text
/work/dfm/HRM-Text/data/models/google/gemma-4-31B-it-fresh-20260604
```

This fresh snapshot includes `chat_template.jinja` and `processor_config.json`.
Both `AutoTokenizer` and `AutoProcessor` load the Gemma 4 chat template locally.
The older `/work/dfm/brainsurgery/models/google/gemma-4-31B-it` copy lacked the
processor/template files and should not be used for instruction serving.

`scripts/prepare_posttrain_transform_refine.py generate-synthetic` now supports
`--endpoint chat|completions` and defaults to the chat endpoint. The vLLM runner
`scripts/run_posttrain_synthetic_generation_vllm.sh` now defaults to:

```text
CLIENT_CONCURRENCY=32
GENERATION_ENDPOINT=chat
```

The text-only `--hf-overrides '{"architectures":["Gemma4ForCausalLM"]}'`
workaround is now only used if `VLLM_FORCE_TEXT_ONLY=1` is explicitly set.

Fresh-model smoke tests through `/v1/chat/completions` on port `8100` produced
coherent Danish factual answers, exact English tense rewriting, and clean
summarization. Real synthetic-request smoke tests produced a valid five-item
English fact list and a coherent Danish paraphrase. The old bad partial queue
was reset: `500` shards are pending, `0` running, and stale generated JSONL
files from the text-only run were removed.

Current generation launch, 2026-06-04. Confidence: high for local command and
early outputs. The full 8-GPU generation run was relaunched in tmux session
`posttrain_gen:runner` with:

```bash
cd /work/dfm/HRM-Text
env VLLM_PYTHON=/home/ucloud/miniforge3/envs/hrm/bin/python \
  CLIENT_PYTHON=/home/ucloud/miniforge3/envs/hrm/bin/python \
  GEMMA_MODEL_PATH=/work/dfm/HRM-Text/data/models/google/gemma-4-31B-it-fresh-20260604 \
  SERVED_MODEL_NAME=posttrain-gemma-teacher \
  GPU_LIST=0,1,2,3,4,5,6,7 \
  REQUESTS_PER_SHARD=1000 \
  CLIENT_CONCURRENCY=32 \
  GENERATION_ENDPOINT=chat \
  scripts/run_posttrain_synthetic_generation_vllm.sh
```

All eight servers reached readiness and workers started on eight shards. Early
GPU behavior is about `165,840 MiB` used per GPU with `100%` utilization. Early
disk samples are coherent Danish child-friendly simplifications; they often use
natural prefaces such as `Her er...`, so stricter style would require prompt or
validator tightening rather than another serving-path change.

Superseding prompt update, 2026-06-04. Confidence: high. The synthetic request
generator was tightened before the final full run:

- Request variant is now `teacher_v2_strict_prompt_variants`.
- Each task/language record stores `prompt_template` and `task_prompt`.
- Four prompt-frame templates are used per language (`plain_text`,
  `instruction_passage`, `source_block`, `compact`) and are distributed roughly
  evenly across each task-language file.
- Task-specific strict output rules tell the teacher to return only the answer,
  avoid introductions, and respect exact sentence/list constraints.
- The chat system prompt now forbids meta-commentary, titles, markdown fences,
  and prefaces such as `Here is`, `Her er`, `Sure`, or `Of course`.
- The validator now rejects common preambles with `reject_reason=preamble`.

The strict v2 requests were rebuilt from scratch:

```bash
cd /work/dfm/HRM-Text
/home/ucloud/miniforge3/envs/hrm/bin/python scripts/prepare_posttrain_transform_refine.py make-synthetic-requests --force
/home/ucloud/miniforge3/envs/hrm/bin/python scripts/prepare_posttrain_transform_refine.py shard-synthetic-requests --force --requests-per-shard 1000
rm -f data/generated_posttrain_transform_refine/*.jsonl
```

The rebuilt queue contains `500` pending shards for `500,000` requests.

The full run was restarted in `posttrain_gen:runner` with the same fresh Gemma
4 31B IT model, chat endpoint, and `CLIENT_CONCURRENCY=32`. After startup, a
60-second active-generation window wrote `3,792` rows, or `63.2 rows/s`
globally. At that rate, the initial full-run ETA was about `2.18 h` for all
`500,000` rows. Early sampled strict-v2 outputs are cleaner: accepted rows no
longer include `Her er...` prefaces, and the observed rejected rows are rejected
for `preamble` as intended. Early acceptance snapshot: `6,211/6,503` rows
accepted (`95.5%`), with `292` preamble rejections.

Completion and quality probe, 2026-06-05. Confidence: high for local counts and
sample inspection. The strict-v2 synthetic generation completed all `500,000`
rows and all `500` shards. vLLM/generation processes were stopped afterward and
all GPUs were freed.

A deterministic three-example-per-dataset probe was written to:

```text
logs/posttrain_transform_refine_generation/quality_probe_20260605.md
```

Counts by task-language dataset:

```text
child_friendly_simplification_da: 47,771 accepted / 50,000
child_friendly_simplification_en: 49,997 accepted / 50,000
exact_sentence_summary_da:        49,384 accepted / 50,000
exact_sentence_summary_en:        49,389 accepted / 50,000
non_copy_rewrite_da:              49,988 accepted / 50,000
non_copy_rewrite_en:              49,994 accepted / 50,000
numbered_fact_extraction_da:      49,998 accepted / 50,000
numbered_fact_extraction_en:      50,000 accepted / 50,000
past_tense_rewrite_da:            49,924 accepted / 50,000
past_tense_rewrite_en:            49,924 accepted / 50,000
```

Quality decision from the probe:

- `include`: `child_friendly_simplification_da`,
  `child_friendly_simplification_en`, `exact_sentence_summary_da`,
  `exact_sentence_summary_en`, `non_copy_rewrite_da`, `non_copy_rewrite_en`,
  `numbered_fact_extraction_da`, `numbered_fact_extraction_en`,
  `past_tense_rewrite_en`.
- `exclude or regenerate`: `past_tense_rewrite_da`. The Danish instruction asks
  for Danish output, but many accepted rows preserve English source headers or
  English body text while only changing tense. Heuristics found
  `Executive Summary` in `46,949/49,924` accepted rows and English-heavy wording
  in `38,957/49,924` accepted rows. This is likely harmful for Danish
  instruction following unless regenerated with a clearer Danish translation
  objective or stronger language validation.

Root cause for `past_tense_rewrite_da`, 2026-06-05. Confidence: high from local
code inspection. `scripts/prepare_posttrain_transform_refine.py` builds one
shared `seed_texts` list from ASSET, `data/converted_sources/*`, and
`data/converted_sources_dfm4_summarization/*`, then passes the same source text
pool to both English and Danish request generation. The `language` field only
controls the prompt wording and requested answer language; it does not filter
source texts by language. This is acceptable for summarization/extraction and
for Danish simplification when the desired skill includes Danish explanation of
English content, but it is the wrong design for `past_tense_rewrite_da`: the
task should use Danish source texts if the intended skill is Danish tense
rewriting. Regenerate this dataset from Danish-only sources, or rename/change
the task to an explicit translate-and-rewrite operation and validate output
language.

Source-target revamp, 2026-06-05. Confidence: high from local file operations
and script output. The synthetic dataset naming scheme was changed from
`task_en` / `task_da` to `task_source_target`, e.g. `task_en_en`,
`task_en_da`, `task_da_da`, `task_da_en`.

Completed usable generated JSONL files were renamed:

- old `*_en__shard_*.jsonl` -> `*_en_en__shard_*.jsonl`
- old `*_da__shard_*.jsonl` -> `*_en_da__shard_*.jsonl`

The bad old `past_tense_rewrite_da` output was removed after renaming, so
`past_tense_rewrite_en_da` can be regenerated with explicit instructions:
translate the English source to Danish and rewrite in past tense. Current local
state:

```text
data/synthetic_requests_posttrain_transform_refine: 20 request files
data/generated_posttrain_transform_refine:          450 completed shard files
data/synthetic_request_shards_posttrain_transform_refine_v3_missing: 550 pending shards
```

`scripts/prepare_posttrain_transform_refine.py` now:

- stores `source_language`, `target_language`, and `language_pair` on new
  request records;
- defaults to all four pairs: `en:en`, `en:da`, `da:da`, `da:en`;
- has separate default English and Danish source roots;
- supports repeatable `--language-pair`, `--task`, and shard
  `--request-glob`;
- adds special cross-lingual past-tense prompts for `en:da` and `da:en`;
- rejects Danish past-tense outputs with obvious English leakage as
  `reject_reason=language_leak`.

Danish-source request files were generated from already converted Danish
sources, including `lexdk`, `danish_dynaword`, `laerebogen_with_followups`,
`synquid_wiki_instruct_da`, and selected Oliver Kinch Danish/BT sources. The
prepared missing queue covers:

```text
*_da_da.jsonl:                    5 tasks x 50 shards = 250 shards
*_da_en.jsonl:                    5 tasks x 50 shards = 250 shards
past_tense_rewrite_en_da.jsonl:   1 task  x 50 shards =  50 shards
total:                                                 550 shards / 550,000 rows
```

The launch script for the later GPU run is:

```bash
cd /work/dfm/HRM-Text
scripts/run_posttrain_transform_refine_v3_missing_generation.sh
```

That script uses the fresh Gemma 4 31B IT model, the chat endpoint,
`CLIENT_CONCURRENCY=32`, the new v3-missing shard root, and
`data/generated_posttrain_transform_refine` as the output directory.

The underlying vLLM runner was also hardened: servers are launched under
`setsid`, and cleanup now terminates the process group and escalates to
`SIGKILL` if needed. With `STOP_SERVERS_ON_EXIT=1`, vLLM servers should be
taken down automatically when generation finishes.

Self-judged generation option, 2026-06-05. Confidence: high from local code and
syntax checks; low-to-medium for final quality impact until a smoke run is
inspected. The generator can now ask the same OpenAI-compatible Gemma endpoint
to judge candidate outputs before accepting them:

```text
scripts/prepare_posttrain_transform_refine.py generate-synthetic --judge-quality --judge-retries 2
```

The judge prompt requires compact JSON and checks:

- declared source language is plausible for the source text;
- response language matches the target language;
- the task was solved;
- exact formatting/count constraints were followed.

If the judge reports a serious issue, the generator retries the response. If
all attempts fail, the row is written with `accepted=false`,
`reject_reason=judge_quality`, and a `judge_quality` JSON object containing the
complaint. This does not mutate the request/instruction itself; it regenerates
a replacement response for the same request during the attempt budget. If the
instruction itself is flawed, it remains rejected and should be replaced by
future request generation.

The generic vLLM runner supports:

```text
JUDGE_QUALITY=1
JUDGE_RETRIES=2
```

The prepared v3-missing launch helper defaults to `JUDGE_QUALITY=1` and
`JUDGE_RETRIES=2`. This will reduce throughput because each accepted candidate
requires an additional judge call, plus extra generation calls for judge
failures. Run a small smoke shard first if walltime matters.

Minor caveats:

- Danish child-friendly simplification has useful pedagogical responses but a
  higher preamble rejection rate (`2,229`) than the other datasets; accepted
  examples looked clean.
- Danish non-copy rewrite and numbered fact extraction looked useful in sampled
  examples, but a handful of accepted rows triggered English-heavy heuristics;
  consider adding a stricter Danish-language validator before final conversion.
- Exact two-sentence summaries mostly satisfy the intended format; rejected rows
  were primarily sentence-count failures.

## 2026-06-04 DFM4 XL-DDP Step 250K Lite Eval

Confidence: high for launch command and checkpoint presence; completion pending.

The `checkpoints/dfm4/XL-ddp` `step_250000` checkpoint is present as an
unsharded DDP checkpoint:

```text
unsharded_step_250000.pt
checkpoint_state_step_250000.json
carry_step_250000.{0..7}.pt
```

The checkpoint state reports `step=250000`, `batch_in_epoch=250000`,
`epoch=1`, `global_batch_size=196608`, and `data_path=data/sampled_dfm4`.

A no-EMA lite eval was launched on 2026-06-04 in tmux window
`hrm-1:lite250k`, using all 8 GPUs and W&B run `4chqwd3w` in project
`Original Plus Mixed Danish Instruction Rich L`. It logs to the same Lite
section metric prefixes as the previous no-EMA lite runs:

```text
lite_eval_noema/*
lite_dfm_eval_noema/*
```

Command:

```bash
cd /work/dfm/HRM-Text
CKPT_TAGS=step_250000 \
EVAL_EPOCHS=0.6826013116866806 \
CKPT_PATH=checkpoints/dfm4/XL-ddp \
GPUS=0,1,2,3,4,5,6,7 \
LITE_EVAL=1 \
LITE_SHARD_INDEX=0 \
QUEUE_ORDER=heavy_first \
NO_EMA=1 \
WANDB_SYNC=1 \
WANDB_PROJECT="Original Plus Mixed Danish Instruction Rich L" \
WANDB_RUN_ID=4chqwd3w \
WANDB_RUN_NAME=dfm4-XL-ddp \
EVAL_PREFIX=lite_eval_noema \
DFM_EVAL_PREFIX=lite_dfm_eval_noema \
STANDARD_CONFIG=evaluation/config/hrm_benchmarking_lite.yaml \
STANDARD_BATCH_SIZE=16 \
DFM_BATCH_SIZE=16 \
IFEVAL_BATCH_SIZE=16 \
MAX_RETRIES=3 \
LOG_ROOT_BASE=logs/eval/dfm4_XL_ddp_noema_lite_probe_20260604_250k \
DFM_LOG_ROOT_BASE=logs/dfm_evals/dfm4_XL_ddp_noema_lite_probe_20260604_250k \
scripts/schedule_multiple_checkpoint_evals.sh
```

Initial status:

Update, 2026-06-13. Confidence: high for telemetry from
`logs/eval/dfm5_XXS_100k_150k_full_20260613_100k_150k/step_100000/eval_attempts.tsv`;
medium for next-run recommendations. The `step_100000`/`step_150000` DFM5 XXS
full eval campaign was launched conservatively with
`STANDARD_BATCH_SIZE=16`, `DFM_BATCH_SIZE=16`, `IFEVAL_BATCH_SIZE=16`, and
`EUROEVAL_BATCH_SIZE=8`. Completed `step_100000` telemetry showed these batch
sizes are too small for the available B200 headroom: standard tasks at batch 16
peaked around 12-18 GiB, IFEval-DA batch 16 peaked around 13-16 GiB, GovReport
batch 16 peaked around 14-17 GiB, and EuroEval batch 8 peaked around 13-19 GiB.
For the next DFM5 XXS eval round, start closer to the known DFM4 high-batch
recipe and keep retry-halving enabled:

```text
STANDARD_BATCH_SIZE=128
STANDARD_BATCH_SIZE_GSM8K=64
STANDARD_BATCH_SIZE_MATH=64
STANDARD_BATCH_SIZE_DROP=32
DFM_BATCH_SIZE=32
DFM_BATCH_SIZE_GOVREPORT=32
DFM_BATCH_SIZE_NORDJYLLANDNEWS=32
DFM_BATCH_SIZE_WMT24PP_EN_DA=32
DFM_BATCH_SIZE_HUMANEVAL=16
DFM_BATCH_SIZE_GENERATIVE_TALEMAADER=16
IFEVAL_BATCH_SIZE=32
EUROEVAL_BATCH_SIZE=16
MAX_RETRIES=5
```

EuroEval may benefit more from one-dataset grouping than from very high batch
size, because the current eight grouped jobs had two long-tail groups.

```text
QUEUED 19 jobs for 1 checkpoints
START step_250000 dfm_ifeval shard 0/32 on GPU0
START step_250000 MATH shard 0/64 on GPU1
START step_250000 GSM8k shard 0/8 on GPU2
START step_250000 DROP shard 0/4 on GPU3
START step_250000 MMLU shard 0/4 on GPU4
START step_250000 HellaSwag shard 0/2 on GPU5
START step_250000 ARC shard 0/1 on GPU6
START step_250000 Winogrande shard 0/1 on GPU7
```

Update, 2026-06-04. Confidence: high. The first `step_250000` lite run with
batch size `16` was stopped because dfm-evals servers repeatedly OOMed while
the DFM4 XL-DDP training run was still occupying about `140-150G` per GPU.
Only the eval scheduler/server process tree was killed; the training PIDs
remained active.

The retry is running in tmux window `hrm-1:7` (`lite250b8`) with monitor
window `hrm-1:8` (`mon250b8`). It uses fresh log roots and halves the eval
batch sizes:

```text
STANDARD_BATCH_SIZE=8
DFM_BATCH_SIZE=8
IFEVAL_BATCH_SIZE=8
LOG_ROOT_BASE=logs/eval/dfm4_XL_ddp_noema_lite_probe_20260604_250k_bs8
DFM_LOG_ROOT_BASE=logs/dfm_evals/dfm4_XL_ddp_noema_lite_probe_20260604_250k_bs8
```

Initial monitor output after model load showed active progress on all eight
GPUs rather than immediate OOM, but memory remains tight because training is
still active.

Trend snapshot, 2026-06-04. Confidence: high for local merged metrics. The
DFM4 XL-DDP lite metrics at `step_250000` are **non-EMA** metrics because the
run was launched with `NO_EMA=1` and logs under `lite_eval_noema/*` and
`lite_dfm_eval_noema/*`. After IFEval-DA finished and exact metric keys were
checked, 14 metrics improved from 200K to 250K and 4 real metrics regressed.
Improvements include ARC, DROP, GSM8k, HellaSwag, MMLU, DALA, GEC-DALA,
Danish Citizen Tests, HumanEval, WMT chrF++, MultiWikiQA, PIQA-da,
NordjyllandNews R2, and IFEval-DA. Regressions include BoolQ, MATH,
Winogrande, and GovReport R2. Treat BoolQ and MATH cautiously because the lite
setup uses small shards and prior probes showed binary-choice option-prior
instability. Generative-talemaader produced a merged metric with `n=0` and
accuracy `0.0`, so treat that checkpoint/task as failed or missing rather than
as a meaningful regression. The corresponding server log shows a CUDA OOM while
loading the HRM checkpoint on GPU0; no Inspect `.eval` file was produced, and
the merge input was the unmatched glob `inspect/*.eval`.

Follow-up, 2026-06-04. Confidence: high. Retrying Talemaader with
`DFM_BATCH_SIZE=1` on one GPU still OOMed while training was active, because
the memory pressure comes primarily from co-locating the HRM server and the
Gemma judge on the same GPU, not from eval batch size. A split-GPU helper was
added at `scripts/run_talemaader_split_gpu_eval.sh`; it waits for enough free
memory on both GPUs, starts the judge and HRM server on separate GPUs, runs
`hrm_danish_generative_talemaader`, exports EEE logs, and merges/syncs only
the Talemaader metrics. A 250K no-EMA split retry is queued in tmux window
`hrm-1:tal250split` with HRM on GPU4 and judge waiting for GPU1.

A local-only 250K EMA lite eval was launched in tmux window `hrm-1:ema250lite`
with `WANDB_SYNC=0`, `NO_EMA=0`, prefixes `lite_eval_ema/*` and
`lite_dfm_eval_ema/*`, batch size `4`, and logs under
`logs/eval/dfm4_XL_ddp_ema_lite_probe_20260604_250k` plus
`logs/dfm_evals/dfm4_XL_ddp_ema_lite_probe_20260604_250k`.

Follow-up results, 2026-06-04. Confidence: high for local merged metrics. The
corrected 250K no-EMA Talemaader split run completed and synced
`lite_dfm_eval_noema/generative-talemaader/model_graded_fact/accuracy =
0.054455445544554455` with `n=101`. The local-only 250K EMA split Talemaader
run completed with `lite_dfm_eval_ema/generative-talemaader/model_graded_fact/
accuracy = 0.034653465346534656` with `n=101`.

At the comparison snapshot after EMA Talemaader completed, 250K EMA was better
than 250K no-EMA on 9 available lite metrics, worse on 8, equal on 1, with
NordjyllandNews still missing. EMA improved ARC, DROP, GSM8k, MATH, DALA,
GEC-DALA, Danish Citizen Tests, WMT chrF++, and GovReport R2; it regressed
BoolQ, HellaSwag, MMLU, Winogrande, MultiWikiQA F1, PIQA-da, IFEval-DA, and
Talemaader. HumanEval was unchanged.

EMA-vs-noEMA trend update, 2026-06-04. Confidence: high for local merged
metrics. After NordjyllandNews became available in the 250K EMA comparison,
EMA's relative advantage had shrunk from 200K to 250K: EMA-minus-noEMA was
positive on 15/19 metrics at 200K but only 10/19 at 250K, equal on 1, and
negative on 8. The mean EMA-minus-noEMA delta across these lite metrics moved
from about `+0.0148` at 200K to about `-0.0019` at 250K. The largest
deteriorations were MultiWikiQA F1, IFEval-DA, GEC-DALA, HumanEval, and PIQA-da;
the biggest relative improvement was BoolQ, but BoolQ remains known to be
option-prior unstable.

Interpretation note. Confidence: medium. The DFM4 XL-DDP EMA was reset at
`step_150000`, so the 200K and 250K comparisons are both post-reset EMA
comparisons, not contaminated by the earlier EMA state. With `ema=0.9999`, the
EMA half-life is roughly `6.9k` optimizer steps and the effective averaging
window is roughly `10k` steps; the reset snapshot contributes only about
`0.67%` at 200K and about `0.005%` at 250K. Thus the shrinking EMA advantage
from 200K to 250K is best read as the current/raw weights catching or surpassing
the post-reset smoothed weights on several lite tasks, rather than as old EMA
state lingering.

## 2026-06-06 DFM4 XL-DDP Step 400K No-EMA Lite Eval

Confidence: high for checkpoint presence, checkpoint metadata, and launch
command; completion pending.

The `checkpoints/dfm4/XL-ddp` `step_400000` unsharded checkpoint is present:

```text
unsharded_step_400000.pt
checkpoint_state_step_400000.json
carry_step_400000.{0..7}.pt
```

`checkpoint_state_step_400000.json` reports `step=400000`,
`batch_in_epoch=32753`, `epoch=2`, `global_batch_size=196608`, and
`data_path=data/sampled_dfm4`. The `epoch_1` checkpoint was saved at
`step=367247`, so the fractional eval x-value for W&B is:

```text
1 + (400000 - 367247) / 367247 = 1.0891852077756932
```

A no-EMA lite eval was launched in tmux session/window
`dfm4_lite_eval:noema_400k`, syncing to W&B project
`Original Plus Mixed Danish Instruction Rich L`, run id `dfm4xlddpclean`, under
the usual clean-history Lite prefixes:

```text
lite_eval_noema/*
lite_dfm_eval_noema/*
```

Command:

```bash
cd /work/dfm/HRM-Text
env PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  LOG_ROOT_BASE=logs/eval/dfm4_XL_ddp_noema_lite_400k_20260606_tmux \
  DFM_LOG_ROOT_BASE=logs/dfm_evals/dfm4_XL_ddp_noema_lite_400k_20260606_tmux \
  CKPT_TAGS=step_400000 \
  EVAL_EPOCHS=1.0891852077756932 \
  CKPT_PATH=checkpoints/dfm4/XL-ddp \
  GPUS=2,3,7 \
  JUDGE_GPU=0 \
  LITE_EVAL=1 \
  LITE_SHARD_INDEX=0 \
  QUEUE_ORDER=heavy_first \
  MAX_RETRIES=3 \
  NO_EMA=1 \
  WANDB_SYNC=1 \
  WANDB_PROJECT="Original Plus Mixed Danish Instruction Rich L" \
  WANDB_RUN_ID=dfm4xlddpclean \
  WANDB_RUN_NAME="dfm4-XL-ddp clean lite history" \
  EVAL_PREFIX=lite_eval_noema \
  DFM_EVAL_PREFIX=lite_dfm_eval_noema \
  MODEL_PREFIX=hrm-dfm4-XL-ddp-noema \
  STANDARD_BATCH_SIZE=1 \
  DFM_BATCH_SIZE=1 \
  IFEVAL_BATCH_SIZE=1 \
  bash scripts/schedule_multiple_checkpoint_evals.sh
```

Initial monitor output at `2026-06-06T08:29:07`:

```text
started=3 finished=0 active=3 queued=16
GPU2: step_400000 dfm_ifeval:0 shard 0/32
GPU3: step_400000 standard:MATH shard 0/64
GPU7: step_400000 standard:GSM8k shard 0/8
```

Completion update, 2026-06-06. Confidence: high. The `step_400000` no-EMA lite
eval completed with `DONE status_0`. The final scheduler status was
`started=19 finished=19 active=0 queued=0`, with final merge ending at
`2026-06-06T11:25:53+02:00`.

## 2026-06-06 DFM4 XL-DDP Step 450K No-EMA Lite Eval

Confidence: high for checkpoint presence, checkpoint metadata, and launch
command; completion pending.

The `checkpoints/dfm4/XL-ddp` `step_450000` unsharded checkpoint is present:

```text
unsharded_step_450000.pt
checkpoint_state_step_450000.json
carry_step_450000.{0..7}.pt
```

`checkpoint_state_step_450000.json` reports `step=450000`,
`batch_in_epoch=82753`, `epoch=2`, `global_batch_size=196608`, and
`data_path=data/sampled_dfm4`. With `epoch_1` saved at `step=367247`, the
fractional eval x-value for W&B is:

```text
1 + (450000 - 367247) / 367247 = 1.225333358747655
```

A no-EMA lite eval was launched in tmux session/window
`dfm4_lite_eval:noema_450k`, syncing to W&B project
`Original Plus Mixed Danish Instruction Rich L`, run id `dfm4xlddpclean`, under
the usual clean-history Lite prefixes:

```text
lite_eval_noema/*
lite_dfm_eval_noema/*
```

Command:

```bash
cd /work/dfm/HRM-Text
env PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  LOG_ROOT_BASE=logs/eval/dfm4_XL_ddp_noema_lite_450k_20260606_tmux \
  DFM_LOG_ROOT_BASE=logs/dfm_evals/dfm4_XL_ddp_noema_lite_450k_20260606_tmux \
  CKPT_TAGS=step_450000 \
  EVAL_EPOCHS=1.225333358747655 \
  CKPT_PATH=checkpoints/dfm4/XL-ddp \
  GPUS=2,3,7 \
  JUDGE_GPU=0 \
  LITE_EVAL=1 \
  LITE_SHARD_INDEX=0 \
  QUEUE_ORDER=heavy_first \
  MAX_RETRIES=3 \
  NO_EMA=1 \
  WANDB_SYNC=1 \
  WANDB_PROJECT="Original Plus Mixed Danish Instruction Rich L" \
  WANDB_RUN_ID=dfm4xlddpclean \
  WANDB_RUN_NAME="dfm4-XL-ddp clean lite history" \
  EVAL_PREFIX=lite_eval_noema \
  DFM_EVAL_PREFIX=lite_dfm_eval_noema \
  MODEL_PREFIX=hrm-dfm4-XL-ddp-noema \
  STANDARD_BATCH_SIZE=1 \
  DFM_BATCH_SIZE=1 \
  IFEVAL_BATCH_SIZE=1 \
  bash scripts/schedule_multiple_checkpoint_evals.sh
```

Initial monitor output at `2026-06-06T16:39:34`:

```text
started=3 finished=0 active=3 queued=16
GPU2: step_450000 dfm_ifeval:0 shard 0/32
GPU3: step_450000 standard:MATH shard 0/64
GPU7: step_450000 standard:GSM8k shard 0/8
```

## 2026-06-04 DFM4 XL-DDP Step 300K No-EMA Lite Eval

Confidence: high.

The `checkpoints/dfm4/XL-ddp` `step_300000` checkpoint was present as an
unsharded DDP checkpoint with checkpoint state and carry files:

```text
unsharded_step_300000.pt
checkpoint_state_step_300000.json
carry_step_300000.{0..7}.pt
```

A true no-EMA lite eval was launched on all 8 GPUs and synced directly to the
usual Lite-section W&B run/prefixes:

- W&B project: `Original Plus Mixed Danish Instruction Rich L`
- W&B run id: `4chqwd3w`
- W&B run name: `dfm4-XL-ddp`
- Metric prefixes: `lite_eval_noema/*` and `lite_dfm_eval_noema/*`
- Scheduler tmux window: `hrm:7` (`dfm4-300k-noema`)
- Monitor tmux window: `hrm:8` (`dfm4-300k-mon`)
- Logs: `logs/eval/dfm4_XL_ddp_noema_lite_probe_20260604_300k`
- DFM logs: `logs/dfm_evals/dfm4_XL_ddp_noema_lite_probe_20260604_300k`

The launch used default eval batch sizes from `scripts/schedule_checkpoint_evals.sh`:
`STANDARD_BATCH_SIZE=8`, `DFM_BATCH_SIZE=8`, and `IFEVAL_BATCH_SIZE=16`.
The run completed with `FINAL_MERGE_END step_300000 status_0` and
`DONE status_0`. HumanEval traceback strings in `inspect/logs.json` are normal
wrong-answer scoring explanations, not infrastructure failures.

## 2026-06-04 DFM4 XL-DDP Step 200K Diagnostics

- Binary-choice option-order diagnostics were run for `checkpoints/dfm4/XL-ddp`
  `step_200000` using both raw non-EMA and EMA weights. Confidence: high. The
  command was:

```bash
CUDA_VISIBLE_DEVICES=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python scripts/diagnose_binary_choice_priors.py
```

  The report was written to
  `logs/eval/dfm4_XL_ddp_binary_choice_order_200k.json`. The diagnostic shows
  that BoolQ and PIQA scores at this checkpoint are strongly affected by answer
  letter/order priors rather than content understanding. For PIQA, flipping the
  options changes EMA accuracy from `0.1481` to `0.7963`; randomizing options
  brings it back near chance at `0.4167`. For BoolQ, non-EMA moves from a
  strong `A` prior on the original prompt to a strong `B` prior when the fixed
  option order is flipped, while EMA is dominated by a `B` prior in the flipped
  and randomized variants.
- IFEval-DA generation examples for `step_200000` were extracted from local
  Inspect `.eval` archives and summarized in
  `logs/eval/dfm4_XL_ddp_ifeval_da_generations_200k.md`. Confidence: high.
  In shard `0`, non-EMA has `2/17` strict passes, `1/17` loose-only pass, and
  `14/17` loose failures; EMA has `4/17` strict passes and `13/17` loose
  failures. The completions are usually readable Danish/English but often fail
  exact instruction constraints through repetition, missing length/format
  requirements, or shallow keyword/end-string compliance.
- Original+Mixed L CP4 was compared against DFM4 XL-DDP `step_200000` using the
  same BoolQ/PIQA original/flipped/randomized option-order diagnostic. Confidence:
  high. The CP4 command was:

```bash
CUDA_VISIBLE_DEVICES=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python scripts/diagnose_binary_choice_priors.py \
  --ckpt-path checkpoints/original_plus_mixed_danish_instruction_rich/L \
  --ckpt-tag epoch_4 \
  --output logs/eval/original_plus_mixed_L_cp4_binary_choice_order.json
```

  The combined comparison report is
  `logs/eval/original_plus_mixed_cp4_vs_dfm4_200k_choice_ifeval_comparison.md`.
  Original+Mixed CP4 EMA is much more stable under option-order changes than
  DFM4 200K EMA: BoolQ is `0.8164/0.8125/0.8164` for
  original/flipped/randomized, and PIQA is `0.4907/0.5185/0.5370` with only
  `0.0093` invalid rate. DFM4 200K EMA has a strong `B` prior: BoolQ is
  `0.4062/0.6133/0.5117`, and PIQA swings from `0.1481` original to `0.7963`
  flipped. CP4 non-EMA BoolQ is stable, but CP4 non-EMA PIQA is not a clean
  comparison because about `60%` of PIQA outputs are invalid.
  Original+Mixed CP4 full IFEval-DA has `final_acc=0.3664` over `541` samples;
  its 17-sample lite shard has `final_acc=0.2588`, while DFM4 200K lite is
  `0.2069` no-EMA and `0.3176` EMA on the corresponding lite setup.
- Original+Mixed L CP1 was compared against DFM4 XL-DDP `step_200000` using
  only EMA weights for CP1, per the user request. Confidence: high. The CP1
  command was:

```bash
CUDA_VISIBLE_DEVICES=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python scripts/diagnose_binary_choice_priors.py \
  --ckpt-path checkpoints/original_plus_mixed_danish_instruction_rich/L \
  --ckpt-tag epoch_1 \
  --models ema \
  --output logs/eval/original_plus_mixed_L_cp1_ema_binary_choice_order.json
```

  The comparison report is
  `logs/eval/original_plus_mixed_cp1_ema_vs_dfm4_200k_choice_ifeval_comparison.md`.
  Original+Mixed CP1 EMA already has stable BoolQ behavior across
  original/flipped/randomized options (`0.7344/0.7422/0.7383`) with balanced
  randomized predictions. PIQA is not yet stable at CP1: it mostly predicts
  `B`, giving `0.1667` original, `0.7685` flipped, and `0.4259` randomized.
  This resembles DFM4 200K EMA for PIQA. The full CP1 IFEval-DA score is
  `final_acc=0.3186` over `541` samples, rising to `0.3664` by CP4; the
  17-sample lite CP1 shard is noisy and reports only `0.1833`.
- Lite-vs-full eval comparison was generated on 2026-06-04 for checkpoints
  where local merged JSONs contain both versions. Confidence: high for the
  file inventory and metric pairing, medium for interpreting sparse overlaps.
  The score-only report is
  `logs/eval/lite_vs_full_eval_comparison_scores_only.md`, with raw paired data
  in `logs/eval/lite_vs_full_eval_comparison_scores_only.json`; the unfiltered
  raw comparison is `logs/eval/lite_vs_full_eval_comparison.md/json`. The
  overlap is broad for `dfm_L` epochs `1..4` (`96` score metrics each), but
  sparse for `original_plus_mixed` (`3` IFEval-DA metrics for epochs `1..2`;
  plus MATH for epochs `3..4`). Score-only median absolute lite-full deltas:
  DFM L `epoch_1=0.0451`, `epoch_2=0.0750`, `epoch_3=0.1652`,
  `epoch_4=0.1679`; original+mixed `epoch_1=0.1352`, `epoch_2=0.1541`,
  `epoch_3=0.0679`, `epoch_4=0.0990`. Large systematic differences include
  DFM L lite underestimating GSM8K and MATH, overestimating many MMLU
  per-domain scores, and noisy IFEval-DA lite estimates from single 17-sample
  shards.
- English smoke generations were run on 2026-06-04 for original Sapient L
  reproduction CP4 at `checkpoints/original_sapient/L`, `epoch_4`, EMA weights.
  Confidence: high. The local JSON output is
  `logs/eval/original_sapient_L_epoch4_english_smoke_generations.json`. Command
  used `SimpleEngine`, `condition=direct`, `temperature=0.0`,
  `max_context=2048`, and `max_tokens=220`. The model produced coherent but
  often very terse completions for simple English prompts; a polite-email prompt
  degenerated into repeated meeting-request sentences when allowed a longer
  decode.
- A second English smoke run for the same original Sapient L CP4 checkpoint used
  longer prompts around a roughly 1000-character photosynthesis text. Confidence:
  high. Output is
  `logs/eval/original_sapient_L_epoch4_english_long_smoke_generations.json`.
  With `max_context=4096`, `max_tokens=360`, `temperature=0.0`, and
  `condition=direct`, the model mostly copied or extracted input sentences
  rather than performing requested transformations. It gave a one-sentence
  continuation and a useful facts extraction, but failed exact two-sentence
  summarization, past-tense rewriting, and child-friendly rewriting.
- The same 10 English smoke prompts were run on DFM4 XL-DDP `step_200000` with
  EMA weights. Confidence: high. Output is
  `logs/eval/dfm4_XL_ddp_step200k_ema_english_smoke_generations.json`.
  Compared with original Sapient L CP4, DFM4 200K EMA is more responsive on
  simple English summarization/explanation prompts and gives a more informative
  low-light continuation, but still fails exact transformation constraints:
  the two-sentence summary is too long, past-tense and child-friendly rewrites
  mostly copy the source text, and the five-facts extraction collapses to one
  unnumbered sentence.
- The five-prompt long English smoke probe was rerun on 2026-06-06 for DFM4
  XL-DDP `step_400000` no-EMA, DFM4 XL-DDP `step_400000` EMA, and DFM L CP4
  EMA, using the same prompt file, `SimpleEngine`, `condition=direct`,
  `temperature=0.0`, `max_context=4096`, `max_tokens=360`, and `batch_size=1`.
  Confidence: high. Outputs:
  - `logs/eval/dfm4_XL_ddp_step400k_noema_english_long_smoke_generations.json`
  - `logs/eval/dfm4_XL_ddp_step400k_ema_english_long_smoke_generations.json`
  - `logs/eval/dfm_L_epoch4_ema_english_long_smoke_generations.json`

  Qualitative result: DFM4 400K no-EMA and EMA both give short, relevant
  low-light continuations and pass the numbered-list format better than the
  original Sapient long smoke, but they still mostly copy the source text for
  past-tense and child-friendly rewrite prompts. DFM4 no-EMA partially changes
  tense in the past-tense prompt (`happened`, etc.) but leaves much of the
  source unchanged. DFM4 EMA is cleaner on the low-light continuation and
  numbered facts but is still mostly extractive/copying. DFM L CP4 EMA is the
  strongest of these long-smoke probes: it gives a correct exact two-sentence
  summary and a substantially better past-tense rewrite, but it still mostly
  copies the child-friendly rewrite prompt rather than simplifying it.
- A few-shot version of the same long English probe was added at
  `scripts/run_english_long_fewshot_probe.py` and run on 2026-06-06. The script
  prepends three task-matched prompt/response examples before each final target
  prompt, then calls `SimpleEngine` with the same generation settings as the
  zero-shot long probe. Confidence: high. Outputs:
  - `logs/eval/dfm4_XL_ddp_step400k_noema_english_long_fewshot_smoke_generations.json`
  - `logs/eval/dfm4_XL_ddp_step400k_ema_english_long_fewshot_smoke_generations.json`
  - `logs/eval/dfm_L_epoch4_ema_english_long_fewshot_smoke_generations.json`

  Qualitative result: the few-shot examples did not reliably fix the controlled
  transformation behavior. DFM4 400K no-EMA kept the low-light continuation
  short and made the numbered-list format explicit, but the summary/past-tense
  outputs introduced irrelevant herbicide/pesticide content and the
  child-friendly rewrite still mostly copied the source. DFM4 400K EMA became
  worse under this few-shot wrapper, mostly copying the source for the first
  four prompts. DFM L CP4 EMA remained the strongest on past-tense rewriting
  and low-light continuation, but the few-shot summary became too long and the
  child-friendly rewrite still mostly copied. Few-shot prompting alone is not a
  substitute for targeted post-training data on these transformations.

## Environment

- Repo: `/work/dfm/HRM-Text`
- Active Python env observed earlier: `/home/ucloud/miniforge3/envs/hrm`
- GPU target: NVIDIA B200 / Blackwell
- CUDA toolkit: `/usr/local/cuda-13.2` installed by the user
- `uv`: upgraded in env to `0.11.15`

## Dependency State

- FlashAttention 3 was attempted but rejected for B200 because the Hopper FA3 path did not produce a viable Blackwell runtime.
- FlashAttention 4 from `Dao-AILab/flash-attention`, subdirectory `flash_attn/cute`, is installed and smoke-tested.
- `requirements.txt`, `docker/requirements/torch_extensions.txt`, `pyproject.toml`, and `uv.lock` were updated for FA4.

## Code Adaptation State

- `models/flash_attention_prefixlm_v2.py` now uses FA4 varlen APIs.
- `models/layers.py` now uses PyTorch SDPA for cache attention instead of FA3 kvcache.
- Py-compile and CUDA smoke tests passed earlier for PrefixLM attention and cache attention.

## Data State

Update on 2026-05-31:

- DFM3 data-prep scaffolding was added for English evaluation recovery. DFM3
  is DFM2 plus selected Common Pile raw-text objectives and raised caps for
  approved English/multilingual instruction data.
- New files:
  - `scripts/generate_dfm3_common_pile_tasks.py`
  - `scripts/build_tokenized_dfm3_tree.py`
  - `scripts/prepare_dfm3_english_recovery.sh`
  - `data_io/prefix_config_dfm3.yaml`
  - `config/data/dfm3.yaml`
- `scripts/download_training_datasets.py` now has an explicit `common_pile`
  group with selected filtered/public/open Common Pile components. A dry-run
  inventory resolved `480` selected files and `275.1 GB` compressed/download
  size.
- `scripts/convert_filtered_sources.py` now converts selected Common Pile
  `.json.gz`, `.jsonl.gz`, and Parquet rows with a `text` field into raw
  continuation rows.
- Validation passed:
  - `python -m py_compile` for modified/new Python scripts.
  - `bash -n scripts/prepare_dfm3_english_recovery.sh`.
  - `data_io/prefix_config_dfm3.yaml` parses as YAML with `84` rules.
- Later on 2026-05-31, the selected Common Pile download/filter/convert
  stages completed and DFM3 task generation finished. The generator wrote
  `2,862` Parquet task files under
  `data/converted_sources_dfm3_common_pile_tasks`, with approximately
  `19,043,38x` rows in each of the six DFM3 objective families:
  direct continuation, prefix continuation, denoising, and three span-fill
  variants. Confidence: high.
- DFM3 Common Pile tokenization was launched with one worker:

```bash
ionice -c2 -n7 nice -n 10 ./data_io/tokenizer/target/release/tokenizer \
  data/converted_sources_dfm3_common_pile_tasks \
  --tokenizer-path /work/dfm/HRM-Text/data_io/trained_tokenizers/bpe/tokenizer.json \
  --workers 1 \
  -o data/tokenized_dfm3_common_pile_tasks
```

  At `2026-05-31 12:07 CEST`, the reliable progress signal was `484 / 2862`
  completed tokenized task directories, measured by top-level output dirs or
  `metadata.json` files, and about `100G` written. Do not estimate tokenizer
  completion from raw file count under the output tree, because each completed
  tokenized task directory contains multiple array files. Confidence: high.

Update on 2026-06-01:

- DFM3 Common Pile tokenization completed: `2862 / 2862` generated task dirs
  have `metadata.json`, matching the `2862` generated Parquet inputs.
  `data/tokenized_dfm3_common_pile_tasks` is `448G`. Confidence: high.
- The DFM3 tokenized union was built at `data/tokenized_dfm3` with `4690`
  top-level symlinks. Confidence: high.
- DFM3 sampling completed at `data/sampled_dfm3`; it contains `metadata.json`
  and `tokens.npy` and is `1.2T`. `data/sampled_dfm3/metadata.json` reports
  `max_seq_len=4097` and `total_length=174,204,067,350`. The analytics file
  `data/show_analytics_dfm3.md` reports `192,508,795,135` unique sampled tokens
  out of `214,239,617,633` available unique tokens (`89.86%`). Confidence: high.
- DFM4 source downloads completed. No DFM4 downloader process remains. Local
  sizes are `436M` for `govreport_summarization`, `5.5G` for `wiki_cat_sum`,
  and `143G` for `laion_scientific_summaries`. The selected LAION arXiv slice
  has `4006` Parquet files plus selected repository docs, matching the `4008`
  selected-file inventory. GovReport has `2` train Parquet shards plus README;
  WikiCatSum has `3` train JSONL files plus README. Confidence: high.
- Superseded: the first DFM4 sample used four epochs and the original
  paragraph-reorder tokenization.
- Current DFM4 generation, tokenization, union build, and five-epoch sampling
  completed. The current union keeps the full DFM3 tree, regenerated DynaWord
  paragraph-window tasks, the previously complete Common Pile paragraph tasks,
  and DFM4 summarization tasks. `data/tokenized_dfm4/union_manifest.json`
  reports roots of `4689` DFM3 tasks, `25` regenerated DynaWord paragraph
  tasks, `425` Common Pile paragraph tasks, `4019` summarization tasks, and
  `9158` total tasks. Confidence: high.
- Current DFM4 sampling completed at `data/sampled_dfm4` with `epochs=5`.
  `metadata.json` reports `max_seq_len=4097` and
  `total_length=72,007,089,569` tokens per epoch. `tokens.npy` is
  `1,225,441,020,536` bytes. Per-epoch arrays exist under `epoch_0` through
  `epoch_4`; all epoch array files were rewritten at `20:32-20:33 CEST` on
  2026-06-01. `data/show_analytics_dfm4.md` reports
  `360,035,447,845` covered tokens across five epochs. Confidence: high.
- Superseded: before pulling `origin/main` on 2026-06-02, the local
  `global_batch_size` path had no gradient accumulation.
- Pull/merge update on 2026-06-02. Confidence: high. `main` was
  fast-forwarded to `origin/main` after a dry run in
  `/work/dfm/HRM-Text-pull-sim`. Local tracked changes were stashed,
  reapplied, and conflicts were resolved using the same resolutions as the temp
  worktree. Conflicted files were `config/cfg_pretrain.yaml`, `pretrain.py`,
  `wiki/pages/download-convert-tokenize.md`, and `wiki/pages/open-issues.md`.
  Validation passed with `python scripts/check_goldfish_loss.py`,
  `python -m py_compile pretrain.py models/lm_head.py models/goldfish_loss.py
  scripts/check_goldfish_loss.py`, and `git diff --check`.
- Current batch-size implementation after the pull, verified from
  `pretrain.py`, `dataset_new.py`, and `multipack_sampler.py` on 2026-06-02.
  Confidence: high. `global_batch_size` is now the effective optimizer token
  batch and `gradient_accumulation_steps` controls the physical microbatch:
  `local_batch_size = global_batch_size / (world_size *
  gradient_accumulation_steps)`. Each optimizer step accumulates that many
  microbatches before `optim.step()`, with loss scaled by supervised-token
  counts across the accumulated microbatches.

Update on 2026-05-30:

- DFM2 data preparation completed. `scripts/generate_dfm2_dynaword_tasks.py`
  produced DynaWord-derived self-supervised tasks, tokenized with one tokenizer
  worker into `data/tokenized_dfm2_dynaword_tasks`.
- `scripts/build_tokenized_dfm2_tree.py --force` built `data/tokenized_dfm2`
  as a symlink union with `1377` base mixed tasks plus `450` generated DFM2
  tasks, for `1827` total task dirs.
- DFM2 sampling completed at `data/sampled_dfm2`; `config/data/dfm2.yaml`
  points training at this sample.
- `data/sampled_dfm2/metadata.json` reports `total_length=42,317,252,803`
  tokens per epoch and `max_seq_len=4097`.
- `data/show_analytics_dfm2.md` reports generated DynaWord self-supervised
  additions of `56,253,792,196` covered tokens across four epochs, or
  `14,063,448,049` per epoch. The retained direct DynaWord slice is
  `2,813,942,923` covered tokens per epoch, so the generated additions are
  `4.998X`.
- DFM2 generated tasks do not use sampler `repeat: 2`; the generator creates
  unique variants instead.

Update on 2026-05-27:

- New DFM gated additions downloaded and converted:
  `laerebogen_with_followups`, `synquid_wiki_instruct_da`,
  `oliverkinch_instruct_bt`, `synquid_mt_da_deepseek`, and
  `synquid_wildchat_100k_qwen_messages`.
- `data_io/prefix_config_dfm.yaml` defines the DFM sampling policy and
  `config/data/dfm.yaml` points training at `data/sampled_dfm`.
- A subset tokenizer run against `data/converted_sources_dfm_new` pruned
  existing `data/tokenized_mixed` outputs because the Rust tokenizer removes
  output directories not present in its current input root. Recovery was started
  by running the tokenizer against the full `data/converted_sources` tree with
  one low-priority worker. A watcher will sample `data/sampled_dfm` only after
  the tokenizer log reports `Done.`.

Superseded context from earlier sessions:

- `data_io` is cloned under `/work/dfm/HRM-Text/data_io`.
- Downloads were run with:

```bash
python scripts/download_training_datasets.py --groups all --exclude-gated --download
```

- Because `--exclude-gated` was used, gated sources such as Laerebogen, Wiki Instruct DA, Instruct BT, and gated Synquid WildChat variants are not part of that run.
- `data/filtered_sources` was built with:

```bash
python scripts/build_filtered_source_tree.py --force
```

- The user reported the final filtered tree build:

```text
Allowed files:      1,525
Denied files:       4,073
Allowed bytes:      248,502,793,134
```

## Active Work

Update on 2026-06-03:

- Lite evals for `checkpoints/dfm4/XL-ddp` checkpoints `step_50000` and
  `step_100000` were restarted for the affected DROP and IFEval jobs after the
  original launch used overly conservative or invalid settings. Confidence:
  high.
- `scripts/schedule_checkpoint_evals.sh` now defaults
  `IFEVAL_BATCH_SIZE=16`. This is used both for the HRM OpenAI shim
  `--batch-size` and Inspect `--max-connections`, replacing the earlier
  conservative default of `1`. Confidence: high.
- DROP standard eval must preserve the YAML benchmark config via
  `run_only=[DROP]` and `shard_overrides.DROP.*`; replacing the whole
  `benchmarks=[...]` entry loses per-task generation settings. The current
  DROP lite restart uses `condition=direct`, `max_tokens=64`, and
  `generation_config.batch_size=16`. The attempted `stop: "\n\n"` setting was
  removed because `SimpleEngine.generate()` does not accept `stop`.
  Confidence: high.
- GSM8K lite eval initially inherited the global `condition=synth,cot` setting
  from `evaluation/config/hrm_benchmarking.yaml`, producing unusable
  `invalid=1.0` behavior for `step_50000` and likely the same for
  `step_100000`. On 2026-06-03 the GSM8K benchmark entry was patched to
  explicitly use `condition=direct` and `max_tokens=512`; a foreground smoke
  test verified the effective config as `batch_size=16`, `condition=direct`,
  `max_context=3072`, `max_tokens=512`. The clean reruns were launched in tmux
  window `gsm8k_direct_20260603_094627`, writing to the normal shard logs under
  `logs/eval/dfm4_XL_ddp_lite_probe/{step_50000,step_100000}/standard_shards/GSM8k/`.
  Confidence: high.
- The GSM8K direct reruns completed but still produced `invalid=1.0` for both
  lite checkpoints. The likely cause is the GSM8K scorer, not necessarily the
  model: `_extract_answer()` only accepts a boxed answer or an entire generation
  string parseable as a single number, so natural-language final answers are
  marked invalid. GSM8K was deliberately not synced to W&B after this result.
  Confidence: high for the local result, medium for the root-cause inference.
- A 3-sample GSM8K smoke generation probe for `checkpoints/dfm4/XL-ddp`
  `step_50000` and `step_100000` with `condition=direct`, `max_context=3072`,
  `max_tokens=128`, and `batch_size=3` produced incoherent token-salad rather
  than natural-language math answers. The current `_extract_answer()` returned
  `None` for all six samples. This supersedes the earlier parser-only
  hypothesis for these two early XL checkpoints; the parser is still strict,
  but the sampled generations themselves were unusable. Confidence: high.
- Follow-up probe on `step_100000` isolated the incoherence to EMA inference:
  `ckpt_use_ema=True` produced token-salad for `direct`, `synth,cot`, `cot`,
  and `synth`, while `ckpt_use_ema=False` produced coherent outputs (`direct`
  emitted the parseable bare number `128`; `synth,cot`/`cot` emitted readable
  step-by-step reasoning, though still wrong on the sampled GSM8K item). The
  unsharded checkpoint's model keys match the loader, and optimizer EMA tensors
  map correctly to named parameters. The likely operational fix for early
  DFM4 XL lite evals is to rerun with non-EMA weights by passing
  `ckpt_use_ema=false` into `evaluation.main` / the HRM OpenAI server
  `--no-ema`. Confidence: high.
- A compact 6-prompt comparison across GSM8K, ARC, and BoolQ for DFM4 XL
  `step_50000` and `step_100000` confirmed the same pattern: EMA generations
  are token-salad at both checkpoints; non-EMA generations are short,
  parseable answers. Sample non-EMA direct results: GSM8K emitted `12`/`120` at
  `step_50000` and `128`/`120` at `step_100000`; ARC/BoolQ answers moved from
  `A,C,A,A` to `C,C,B,B` on the sampled prompts. Confidence: high.
- The likely root cause is numerical, not save/load key mapping: model
  parameters and `param_ema` are bfloat16, and `ema=0.9999` means each update
  uses alpha `1e-4`. A local scalar check showed bfloat16 `lerp_` often rounds
  these updates to zero, e.g. `0.02 -> 0.03` with alpha `1e-4` leaves the EMA
  value unchanged in bfloat16 while fp32 would update to `0.020001`. Therefore
  EMA can remain close to initialization even after many steps. Future EMA
  should store/update shadow weights in fp32 or use a much less aggressive EMA
  decay if kept in bf16. Confidence: high.
- DDP mixed precision was patched on 2026-06-03 to mirror the FSDP2 path more
  closely. The DDP branch no longer casts trainable parameters with
  `model.to(dtype=fwd_bwd_dtype)` before optimizer creation; instead,
  `TrainState.use_cuda_autocast` enables CUDA autocast during the forward/backward
  step when `distributed_strategy=ddp` and `fwd_bwd_dtype != float32`. This keeps
  DDP optimizer state and EMA shadow parameters in fp32 while preserving bf16
  compute. `python -m py_compile pretrain.py` passed. Existing bf16-DDP
  checkpoints retain their old bf16 optimizer/EMA state; the clean fix applies
  to new DDP checkpoints. Confidence: high.
- Non-EMA lite eval support was added on 2026-06-03. Confidence: high.
  `scripts/schedule_checkpoint_evals.sh` accepts `NO_EMA=1`, passing
  `ckpt_use_ema=false` to `evaluation.main` and `--no-ema` to
  `scripts/hrm_openai_server.py`; `scripts/schedule_multiple_checkpoint_evals.sh`
  propagates `NO_EMA` into per-job child schedulers and final merge invocations.
  `evaluation/config/hrm_benchmarking_lite.yaml` is the isolated standard-eval
  lite config: direct mode by default, standard batch size `16`, `GSM8k`
  `max_tokens=256`, `MATH` `max_tokens=512`, `DROP` `max_tokens=64`, and no
  per-MCQ `batch_size: 1` overrides. Validation passed with `bash -n` for both
  scheduler scripts and YAML parsing for the lite config.
- Non-EMA lite evals for DFM4 XL-DDP `step_50000` and `step_100000` were
  launched on all 8 GPUs on 2026-06-03. Confidence: high. The checkpoint state
  files report `global_batch_size=196608`, so W&B epoch x-axis values are
  `0.1365202623373361` and `0.2730405246746722`. Logs are under
  `logs/eval/dfm4_XL_ddp_noema_lite_probe_20260603_1125` and
  `logs/dfm_evals/dfm4_XL_ddp_noema_lite_probe_20260603_1125`; the tmux window
  is `hrm-1:noema-lite`. Metrics are written to the existing W&B run
  `dfm4-XL-ddp` in project `Original Plus Mixed Danish Instruction Rich L`
  under prefixes `lite_eval_noema/` and `lite_dfm_eval_noema/`.

```bash
NO_EMA=1 \
LITE_EVAL=1 \
QUEUE_ORDER=heavy_first \
CKPT_TAGS=step_50000,step_100000 \
EVAL_EPOCHS=0.1365202623373361,0.2730405246746722 \
CKPT_PATH=checkpoints/dfm4/XL-ddp \
GPUS=0,1,2,3,4,5,6,7 \
STANDARD_CONFIG=evaluation/config/hrm_benchmarking_lite.yaml \
STANDARD_BATCH_SIZE=16 \
DFM_BATCH_SIZE=16 \
IFEVAL_BATCH_SIZE=16 \
EVAL_PREFIX=lite_eval_noema \
DFM_EVAL_PREFIX=lite_dfm_eval_noema \
WANDB_PROJECT="Original Plus Mixed Danish Instruction Rich L" \
WANDB_RUN_ID=4chqwd3w \
WANDB_RUN_NAME=dfm4-XL-ddp \
MAX_RETRIES=3 \
LOG_ROOT_BASE=logs/eval/dfm4_XL_ddp_noema_lite_probe_20260603_1125 \
DFM_LOG_ROOT_BASE=logs/dfm_evals/dfm4_XL_ddp_noema_lite_probe_20260603_1125 \
scripts/schedule_multiple_checkpoint_evals.sh
```
  to new runs, or to resumed runs only insofar as state loading casts/restores
  into the new fp32 optimizer objects. Confidence: high.
- Resume/upcycling support was added for legacy bf16 DDP checkpoints:
  `upcast_optimizer_state_on_resume` upcasts floating optimizer state tensors to
  fp32 after checkpoint load, and `reset_ema_on_resume` resets any optimizer
  `param_ema` buffers from the loaded current parameters in fp32. These flags
  are present in `PretrainConfig` and `config/cfg_pretrain.yaml`. Use both when
  resuming the DFM4 XL DDP run from `step_100000` or `step_150000` so future EMA
  is rebuilt from the coherent raw model instead of carrying forward the broken
  bf16 EMA shadow. `python -m py_compile pretrain.py` and a config key smoke
  check passed. Confidence: high.
- A no-EMA PIQA-only probe was run locally for DFM4 XL DDP checkpoints
  `step_50000` and `step_100000` without W&B sync. Command used two local
  `scripts/hrm_openai_server.py` instances with `--no-ema`, `--batch-size 16`,
  and `condition=direct`, then `uv run --project dfm-evals evals suite
  hrm_danish_piqa`. Results under
  `logs/dfm_evals/dfm4_XL_ddp_noema_piqa_20260603_110551`: `step_50000`
  `lite_dfm_eval_noema/piqa/piqa_scorer/accuracy=0.18518518518518517`
  (`n=108`), `step_100000`
  `lite_dfm_eval_noema/piqa/piqa_scorer/accuracy=0.4722222222222222`
  (`n=108`). This shows clear non-EMA improvement from 50k to 100k, unlike the
  EMA lite evals. Confidence: high.
- W&B workspace update on 2026-06-03. Confidence: high for API readback. The
  package `gql==4.0.0` was installed in the `hrm` environment, which also
  installed `graphql-core==3.2.8` and `backoff==2.2.1`. The W&B Python
  client's AST type check was still incompatible with these objects, so the
  actual view mutation used direct GraphQL HTTP requests with the existing
  W&B credentials. The API showed that saved view `nw-boh5wwabbfc7-v`
  (`manual workspace`) has no Lite sections, while the default project view
  `nw-nwuserpetersk-w` (`Peter-sk's workspace`) contained auto sections
  `lite_eval` and `lite_dfm_eval`. Those two auto sections were repointed to
  `lite_eval_noema` and `lite_dfm_eval_noema` by changing their `name` and
  `defaultName` fields. Backups were written to
  `logs/wandb_workspace_specs/20260603T103845Z_before_lite_noema_nw-nwuserpetersk-w.json`
  and
  `logs/wandb_workspace_specs/20260603T103845Z_after_lite_noema_nw-nwuserpetersk-w.json`.
- DFM4 XL-DDP non-EMA lite checkpoint comparison on 2026-06-03. Confidence:
  high for local merged JSON values; medium for interpreting lite-shard results
  against full DFM L evals. At `step_50000` and `step_100000`, the raw
  non-EMA XL checkpoints show coherent learning but remain under DFM L epoch 1
  on most standard tasks. Examples at `step_100000`: `MMLU=0.3015` vs DFM L
  epoch 1 `0.3860`, `GSM8k=0.0364` vs `0.6892`, `DROP/f1=0.1066` vs `0.2419`,
  `WMT24++ chrf3pp=0.4052` vs `0.4907`, and `MultiWikiQA f1=0.5106` vs
  `0.8412`. PIQA is the main exception: `step_100000` reaches
  `0.4722`, slightly above DFM L epoch 1 `0.4630` but below later DFM L
  epochs. Improvements from `50k` to `100k` include `MMLU 0.2443 -> 0.3015`,
  `DROP/f1 0.0641 -> 0.1066`, `GSM8k 0.0242 -> 0.0364`,
  `GEC-DaLA 0.0996 -> 0.2148`, `WMT24++ 0.3616 -> 0.4052`,
  `MultiWikiQA f1 0.4289 -> 0.5106`, and `PIQA 0.1852 -> 0.4722`.
- Non-GSM lite metrics for `checkpoints/dfm4/XL-ddp` checkpoints `step_50000`
  and `step_100000` were merged and synced to W&B run `4chqwd3w` under
  `lite_eval/*` and `lite_dfm_eval/*`. This includes standard tasks
  `DROP`, `MMLU`, `ARC`, `HellaSwag`, `Winogrande`, `BoolQ`, and `MATH`, plus
  DFM tasks `danish_citizen_tests`, `dala`, `gec_dala`, `wmt24pp_en_da`,
  `multi_wiki_qa`, `piqa`, `generative_talemaader`, `govreport`,
  `nordjyllandnews`, `humaneval`, and `ifeval-da`. Confidence: high.
- `scripts/merge_ifeval_da_shards.py` now honors `--prefix`, so lite IFEval-DA
  metrics can be logged under `lite_dfm_eval/ifeval-da/...` rather than the
  full-eval `dfm_eval/...` namespace. Confidence: high.
- Manual restart wrappers were launched under
  `logs/eval/dfm4_XL_ddp_lite_probe/manual_restarts_20260603_083305/` for
  `step500_ifeval`, `step500_drop`, and `step100_ifeval`; their status is
  appended to `logs/eval/dfm4_XL_ddp_lite_probe/status.tsv`. Confidence: high.
- PIQA dfm-evals was slow because the task had no task-local generation cap and
  therefore used the HRM model-info fallback of `output_tokens=512`. This made
  8-sample batches take about seven minutes when one request ran to the cap.
  `dfm-evals/dfm_evals/tasks/piqa.py` now accepts `max_gen_toks`, and
  `config/dfm_evals_hrm_single_tasks.yaml` sets `max_gen_toks=8` for
  `hrm_danish_piqa`. Restarting the `step_50000` PIQA shard with batch 16
  completed the full `108/108` samples in under a minute. Confidence: high.
- `scripts/watch_multi_checkpoint_eval_progress.py` now supports `--once`,
  parses manual scheduler `START/END` lines, and uses `nvidia-smi`
  compute-app PID-to-GPU mapping to recover live manually restarted HRM eval
  jobs. Confidence: high.
- After the manual IFEval and PIQA restarts, GPUs 0, 6, and 7 became idle
  because their replacement wrappers used one-job queues and did not return to
  the main multi-checkpoint queue. The remaining main queue still had `16`
  jobs. Replacement queue consumers were launched from
  `logs/eval/dfm4_XL_ddp_lite_probe/manual_queue_workers_20260603_085141/`
  for GPUs 0, 6, and 7; they append to the shared status file and started
  `step_100000` DROP, MMLU, and HellaSwag. Confidence: high.
- WMT24++ en-da has `960` usable samples after filtering, so shard `0/8` has
  `120` samples. `scripts/watch_multi_checkpoint_eval_progress.py` now includes
  this known total and shows server-batch progress for DFM eval tasks before
  completed HTTP requests are available. Confidence: high.
- Additional DFM eval totals added to the monitor on 2026-06-03:
  `generative-talemaader` test split has `808` samples (`101` in shard `0/8`),
  `nordjyllandnews` is capped at `1000` samples (`125` in shard `0/8`), and
  GovReport test has `973` samples (`61` in shard `0/16`). The tmux monitor in
  `hrm-1:7.2` was restarted after the patch so it uses the updated totals.
  Confidence: high.
- HumanEval local-sandbox scoring failed when generated code contained embedded
  NUL bytes, because the upstream scorer passed the code to `python -c` and
  Python's subprocess layer raises `ValueError: embedded null byte`. The local
  `dfm-evals/dfm_evals/tasks/code.py` wrapper now uses a sanitized verifier:
  completions with NUL bytes are marked incorrect without execution, and other
  pre-exec `ValueError`s are counted as incorrect instead of crashing the task.
  The `step_50000` and `step_100000` HumanEval shard `0/4` runs were restarted
  cleanly on GPUs 5 and 4 with batch size 16. Confidence: high.

Update on 2026-06-01:

- W&B native `_step` history cannot be repaired in-place after later eval/log
  rows have advanced the run step. An attempted same-run backfill of DFM L train
  rows into `Original Plus Mixed Danish Instruction Rich L/kgnbdmwf` was
  rejected by W&B for old `_step` values; a later custom-step replay polluted
  the visible train curves and should not be used as the clean comparison run.
  Confidence: high.
- A clean comparison run was created at
  `Original Plus Mixed Danish Instruction Rich L/dfmlfull0601`
  (`dfm-L-full-train-backfill`). It backfilled DFM L train history from
  `DFM L/kgnbdmwf` before adding eval metrics, preserving native train `_step`
  values. The train backfill logged `118,775` rows, source steps `5` through
  `592,395`; W&B summary verifies `train/source_step=592395`,
  `train/loss=1.1001414060592651`, and
  `train/accuracy=0.7316066026687622`. Confidence: high.
- The same clean run now has standard `eval/*` and Danish `dfm_eval/*` metrics
  for DFM L epochs `1`, `2`, and `3`, replayed from local merged metric JSONs.
  Each epoch logged `195` standard metrics and `74` DFM metrics using
  `eval/epoch` and `dfm_eval/epoch` as the W&B plot axes. Spot-checked summary
  values include `eval/MATH/acc/epoch_1=0.3854`,
  `eval/MATH/acc/epoch_2=0.45380217999999994`,
  `eval/MATH/acc/epoch_3=0.47639826`,
  `dfm_eval/ifeval-da/instruction_following/final_acc/epoch_1=0.393870787633715`,
  `dfm_eval/ifeval-da/instruction_following/final_acc/epoch_2=0.41204577082020327`,
  and
  `dfm_eval/ifeval-da/instruction_following/final_acc/epoch_3=0.4760777566757044`.
  Confidence: high.

Update on 2026-05-31:

- Superseded: earlier on 2026-05-31, `pretrain.py` only saved checkpoints at
  epoch boundaries via `checkpoint_interval`.
- Step-based checkpointing is now implemented. `config/cfg_pretrain.yaml` has
  `checkpoint_step_interval: null` by default; setting it to a positive integer
  saves additional checkpoints during training at `fsdp2_step_{step}` and
  `carry_step_{step}.{rank}.pt`. Epoch checkpoints are still saved as
  `fsdp2_epoch_{epoch}` and `carry_epoch_{epoch}.{rank}.pt`. Confidence: high.
- Checkpoint loading now supports explicit tags. Standard/eval code can pass
  `ckpt_tag=step_10000` or `ckpt_tag=epoch_1`; the OpenAI shim accepts
  `--ckpt-tag step_10000`, and HF conversion accepts `--ckpt_tag step_10000`.
  Existing `ckpt_epoch=...` and `--ckpt-epoch ...` paths still work, and when no
  epoch/tag is passed, loading still defaults to the latest epoch checkpoint.
  Confidence: high.
- `scripts/schedule_checkpoint_evals.sh` now accepts `CKPT_TAG`, defaulting to
  `epoch_${EPOCH}`. For intra-epoch evals use, for example,
  `EPOCH=1 CKPT_TAG=step_10000 ... scripts/schedule_checkpoint_evals.sh`; the
  `EPOCH` value remains the W&B x-axis/merge epoch unless those logging scripts
  are extended separately. Confidence: high.
- Fractional eval epochs are now supported for intra-epoch checkpoints.
  `scripts/schedule_checkpoint_evals.sh` accepts `EVAL_EPOCH`, defaulting to
  `EPOCH`, and passes it to the standard/DFM/IFEval merge scripts. The merge
  and incremental DFM logging scripts parse `--epoch` as `float`, so W&B rows
  can use values such as `eval/epoch=1.234` and `dfm_eval/epoch=1.234`.
  Per-checkpoint summary aliases sanitize fractional labels with `p`, for
  example `epoch_1p234`, while integer epochs keep `epoch_1`. Confidence: high.
- Superseded: training resume was previously not implemented in `pretrain.py`.
  It is now implemented for current epoch checkpoints and new metadata-backed
  step checkpoints. `config/cfg_pretrain.yaml` exposes
  `wandb_run_id`, `wandb_resume`, `resume_checkpoint_path`,
  `resume_checkpoint_tag`, `resume_epoch`, `resume_step`, and
  `resume_batch_in_epoch`. `pretrain.py` loads DCP model and optimizer state
  from `fsdp2_{tag}`, loads rank-local carry from `carry_{tag}.{rank}.pt`,
  restores `train_state.step`, and calls `V1Dataset.set_epoch(...)` so epoch
  checkpoints continue on the next dataset epoch instead of replaying epoch 0.
  On resume, `num_params` is written to W&B summary rather than logged at step
  `0`, so a backfilled run can continue without violating W&B monotonic step
  ordering. Confidence: high.
- New checkpoints write sidecar metadata files named
  `checkpoint_state_{tag}.json` with `tag`, `step`, `epoch`,
  `batch_in_epoch`, `global_batch_size`, `data_path`, and `seed`. Step
  checkpoints such as `step_500000` use this metadata to resume inside an epoch
  by replay-skipping already completed batches. Existing old epoch checkpoints
  do not have sidecars; for them resume infers the step as
  `completed_epoch * total_steps // config.epochs`. Confidence: high.
- Example resume from an existing DFM epoch checkpoint:

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 torchrun --nproc_per_node=8 pretrain.py \
  data=dfm \
  arch/size@arch=L \
  lr=2.5e-4 \
  global_batch_size=172032 \
  project_name="DFM L" \
  run_name=dfm-L-resume-epoch3 \
  checkpoint_path=checkpoints/dfm/L-resume \
  resume_checkpoint_path=checkpoints/dfm/L \
  resume_checkpoint_tag=epoch_3
```

  For new step checkpoints, use `resume_checkpoint_tag=step_500000`; if the
  sidecar JSON is missing, also provide `resume_epoch`, `resume_step`, and
  `resume_batch_in_epoch`. Confidence: high.
- The original DFM L epoch checkpoints were reconstructed with exact step
  sidecars by comparing raw local W&B train history timestamps from
  `wandb/run-20260528_234406-kgnbdmwf/run-kgnbdmwf.wandb` against checkpoint
  mtimes. The verified last logged train steps before checkpoint writes are:
  `epoch_1=164670`, `epoch_2=329380`, and `epoch_3=494080`. Sidecars
  `checkpoints/dfm/L/checkpoint_state_epoch_{1,2,3}.json` were written with
  those steps, so `resume_checkpoint_tag=epoch_3` now resolves to
  `step=494080`, `start_epoch=4`, and `skip_batches=0`. Confidence: high.
  The terminal progress-bar lines around `20840` at epoch transitions are not a
  reliable global W&B step boundary by themselves.
- W&B run `Original Plus Mixed Danish Instruction Rich L/dfm-l-resume-epoch3`
  was prepared for resuming DFM L from `epoch_3`. It contains `98,816` train
  rows backfilled from local DFM L history through step `494080`, plus standard
  `eval/*` and Danish `dfm_eval/*` metrics for epochs `1`, `2`, and `3`.
  Verified summary values include `resume_prepared_max_train_step=494080`,
  `train/loss=1.1266595125198364`, `train/accuracy=0.7248556613922119`,
  `eval/MATH/acc/epoch_3=0.47639826`, and
  `dfm_eval/ifeval-da/instruction_following/final_acc/epoch_3=0.4760777566757044`.
  Resume training should use `wandb_run_id=dfm-l-resume-epoch3` and
  `wandb_resume=allow` so it appends step `494085+` train metrics to the
  prepared run. Confidence: high.
- Caveat observed after launching the resumed run: because eval and dfm_eval
  rows were logged after the train backfill, W&B advanced the internal run step
  a few steps beyond `494080` before training resumed. The first resumed train
  log at step `494085` was warned/dropped because W&B's current internal step
  was `494087`. Subsequent train logs above that point are accepted; W&B API
  showed the run as `running` and train summary values updating. For future
  prepared resume runs, either log eval rows with explicit non-advancing/merged
  steps or expect the first one or two train logs after resume to be skipped.
  Confidence: high.
- The first DFM L epoch-3 resume attempt failed at `step_500000` while saving
  the step checkpoint because `save_train_checkpoint()` still referenced an
  old global `RANK` variable. `pretrain.py` was fixed to pass `rank` explicitly
  into checkpoint save helpers. The DCP model/optimizer checkpoint
  `checkpoints/dfm/L/fsdp2_step_500000` had already been written before the
  crash. Because `baselines.hrm_nocarry_bp_warmup` has `initial_carry() -> None`,
  the missing carry files were safely recovered as `torch.save(None, ...)` for
  ranks `0..7`, and `checkpoint_state_step_500000.json` was written with
  `step=500000`, `epoch=4`, and `batch_in_epoch=5920`. Resume now resolves
  `step_500000` to `ResumeState(tag='step_500000', step=500000, start_epoch=4,
  skip_batches=5920)`. Confidence: high.
- Goldfish loss integration assessment, 2026-06-01. Goldfish loss is a
  label-masking modification to next-token cross entropy: drop a deterministic
  or randomized subset of target tokens from loss computation by setting labels
  to the ignore index before CE. In this repo the correct integration point is
  `models/lm_head.py`, immediately before `F.cross_entropy(...)`, because
  `dataset_new.py` already emits packed `labels` with `IGNORE_LABEL_ID` and
  `LMHead` already computes masks, CE, and metrics centrally. A minimal optional
  implementation needs config fields on `LMHeadConfig`/arch config such as
  `goldfish_strategy`, `goldfish_k`, `goldfish_start_position`, and
  `goldfish_context_width`; default `goldfish_strategy: null` preserves current
  behavior. Confidence: high for integration point; medium for preferred
  strategy defaults.
- Goldfish loss is now implemented behind an explicit opt-in. Main code lives
  in `models/goldfish_loss.py`; `models/lm_head.py` applies it only when
  `arch.goldfish_strategy` is set. `config/arch/net/hrm.yaml` defaults to
  `goldfish_strategy: null`, `goldfish_k: 50`, `goldfish_context_width: 50`,
  and `goldfish_seed: 0`, so existing runs are unchanged unless the option is
  enabled. Enable Apertus-style settings with
  `arch.goldfish_strategy=hash arch.goldfish_k=50 arch.goldfish_context_width=50`.
  Validation passed with `python scripts/check_goldfish_loss.py`,
  `python -m py_compile`, and Hydra composition of the Goldfish overrides.
  Confidence: high.
- Hydra override compatibility for the resume command was fixed on 2026-06-01.
  `config/cfg_pretrain.yaml` now declares `project_name`, `run_name`,
  `checkpoint_path`, `seed`, `log_interval`, `fwd_bwd_dtype`,
  `checkpoint_step_interval`, W&B resume fields, and checkpoint resume fields.
  `config/data/dfm.yaml` now declares `target_only: true`. The DFM L
  epoch-3 resume command was checked with `python pretrain.py --cfg job ...`
  and composes without `Could not override ...` errors. Confidence: high.

Update on 2026-05-27 20:45 Europe/Berlin:

- CP4 evaluation for `original_plus_mixed_danish_instruction_rich/L` completed.
  The queued scheduler reached `FINAL_MERGE_END`, with standard evals, MATH
  shards, DFM tasks, and IFEval-DA shards all finishing with status 0 and
  writing/syncing W&B logs under
  `logs/eval/original_plus_mixed_danish_instruction_rich_L_epoch4_queued_all`
  and
  `logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_epoch4_queued_all`.
  Confidence: high.
- DFM data prep is not complete. The full-tree tokenizer recovery is still
  running as PID `1128417` with one low-priority worker against
  `data/converted_sources`; it has begun rebuilding `data/tokenized_mixed`.
  The sampling watcher PID `1135056` is still waiting and `data/sampled_dfm`
  has not been produced yet. Confidence: high.

Superseded by 2026-05-28 00:00 Europe/Berlin:

- The one-worker tokenizer PID `1128417` and watcher PID `1135056` were stopped
  deliberately and replaced by a two-worker full-tree tokenizer run. New
  tokenizer PID: `1941931`; new watcher PID: `1942797`. Command:

```bash
ionice -c2 -n7 nice -n 10 ./data_io/tokenizer/target/release/tokenizer \
  data/converted_sources \
  --tokenizer-path /work/dfm/HRM-Text/data_io/trained_tokenizers/bpe/tokenizer.json \
  --workers 2 \
  -o data/tokenized_mixed
```

- The restarted tokenizer recognized `33` already completed tokenized dirs and
  reported `Processing 1344 files on 2 threads...`. The watcher now waits for
  PID `1941931` and samples `data/sampled_dfm` only if the tokenizer log
  contains `Done.` and more than 1000 tokenized dirs are present. Confidence:
  high.

Update on 2026-05-28 08:35 Europe/Berlin:

- CP4 metrics for `original_plus_mixed_danish_instruction_rich/L` were manually
  re-synced to W&B run `es1od1in` in project
  `Original Plus Mixed Danish Instruction Rich L`. The sync used the CP4
  standard logs, merged MATH metrics, DFM EEE exports, and merged IFEval-DA
  metrics, and reported `231` metrics synced. Log:
  `logs/eval/original_plus_mixed_danish_instruction_rich_L_epoch4_queued_all/wandb_sync_all_cp4_rerun.log`.
  Confidence: high.

Later update on 2026-05-28:

- GovReport and NordjyllandNews were removed from the standard original+mixed
  eval queues in `scripts/schedule_original_plus_mixed_cp3_evals.sh` and
  `scripts/evaluate_original_plus_mixed_standard_split.sh`; future runs should
  treat these as DFM summarization evals instead of standard `eval/*` tasks.
  Confidence: high.
- Original+mixed CP4 was evaluated on the DFM summarization tasks
  `dfm_evals/govreport` and `dfm_evals/nordjyllandnews`. Both tasks completed
  with status 0 and synced 10 metrics each to W&B run `es1od1in` under
  `dfm_eval/govreport/*` and `dfm_eval/nordjyllandnews/*`. Logs:
  `logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_epoch4_summarization_dfm_eval`.
  Confidence: high.
- `scripts/schedule_dfm_summarization_bertscore_all_checkpoints.sh` now supports
  `SKIP_ORIGINAL=1` and `SKIP_ORIGINAL_PLUS_MIXED=1`, and its server cleanup
  guard tolerates an unset `server_pid`. This avoids accidental old-family jobs
  and spurious final status 1 after successful task completion. Confidence:
  high.
- A code-generation DFM eval was added as `dfm_evals/humaneval`, wrapping
  `inspect-evals` HumanEval with Docker sandbox execution by default. The HRM
  suite entry is `hrm_code_humaneval` in
  `config/dfm_evals_hrm_single_tasks.yaml`. A zero-sample CLI probe resolved the
  task and loaded the HumanEval dataset successfully:

```bash
OPENAI_API_KEY=inspectai uv run --project dfm-evals evals suite hrm_code_humaneval \
  --file config/dfm_evals_hrm_single_tasks.yaml \
  --target-model openai/dummy \
  --target-base-url http://127.0.0.1:9/v1 \
  --mode set -- --limit 0 --log-dir /tmp/hrm_humaneval_probe --log-dir-allow-dirty
```

  Confidence: high for registration; medium for full execution because a real
  run requires a working code sandbox.
- HumanEval was run on 2026-05-28 for all 8 available L checkpoints using GPUs
  `0,1,2,3` and the local sandbox fallback because Docker was not installed on
  the node. Logs are under
  `logs/dfm_evals/humaneval_all_checkpoints_20260528`. All eight W&B sync logs
  report successful sync of `dfm_eval/humaneval/verify/accuracy`.

  Results:

  - Original Sapient epochs 1-4: accuracy `0.000`, `0.000`, `0.000`, `0.000`.
  - Original+mixed Danish-rich epochs 1-4: accuracy `0.146`, `0.238`, `0.256`,
    `0.226`.

  Confidence: high.
- Tokenization was restarted again on 2026-05-28 after two-worker resume attempts
  exited without `Done.`. The active stable fallback is one worker:
  tokenizer PID `3661868`, watcher PID `3662969`, log
  `logs/tokenize/dfm_full_recovery_tokenizer_workers1_resume5.log`. It reported
  `Processing 930 files on 1 threads...` after recognizing `447` completed
  tokenized dirs. Confidence: high.
- The one-worker tokenizer finished rebuilding the expected `1377` tokenized
  dirs, but its log did not contain `Done.`, so the strict watcher refused to
  start sampling. The one unmatched source file was
  `data/converted_sources/nemotron_swe/data/swe.parquet.unsplit`, the parked
  unsplit SWE file, not an expected tokenizer output. DFM sampling was started
  manually with `data_io/sample_tokenized.py` and is writing
  `data/sampled_dfm`. Confidence: high.

- Mixed-corpus tokenization is active at `data/tokenized_mixed`; it was previously at `1316/1317` files with the final tail in `nemotron_swe/data/swe.parquet`.
- Original Sapient-only tokenization for the L reproduction run has been launched into `data/tokenized_original_sapient`.
- The original Sapient tokenization command scans `5212` source files from:

```text
data/downloads/datasets/sapient_cleaned/data_clustered
data/downloads/datasets/sapient_cleaned/data
```

See [[original-l-reproduction]] for the run plan.

MPS branch update on 2026-05-25:

- Repo path: `/Users/petersk/Nobackup/HRM-Text-mps`.
- After stopping a still-running background Sapient downloader, the partial Sapient download has `490` completed `.parquet`/`.jsonl` inputs under `data/downloads/datasets/sapient_cleaned` and `1` incomplete cache file.
- Completed local inputs were tokenized into `data/tokenized_original_sapient_partial`.
- Verification: `490` tokenized `metadata.json` files, about `83G`; a final tokenizer validation scan reported `Processing 0 files`.
- A small symlinked tokenized view was built at `data/tokenized_original_sapient_partial_smoke`.
- Sampling produced `data/sampled_original_sapient_partial_smoke`, about `519M`, with `metadata.total_length=21,359,878`.
- Two MPS debug training steps against this smoke sample passed with finite loss, metrics, gradients, parameters, and post-optimizer parameters.
- Gradient accumulation is implemented with `global_batch_size` as the effective optimizer token batch. Verified B-size MPS diagnostic: `global_batch_size=131072`, `gradient_accumulation_steps=8`, derived `local_microbatch_size=16384`, one optimizer step finite. Because epochs drop their own partial final effective batch, the smoke sample runs `162` optimizer steps per epoch, or `648` steps for `epochs=4`.

See [[original-l-reproduction]] and [[download-convert-tokenize]] for commands. Confidence: high.

Update on 2026-05-24:

- The active L run uses `data=original_plus_mixed_danish_instruction_rich`.
- `config/data/original_plus_mixed_danish_instruction_rich.yaml` points to `data/sampled_original_plus_mixed_danish_instruction_rich`.
- This sample preserves the original Sapient covered-token budget essentially exactly:
  - Original Sapient sample: `56,140,714,711` covered tokens across 4 epochs.
  - Original portion inside Danish-rich sample: `56,140,181,363` covered tokens across 4 epochs.
  - Difference: `-533,348` tokens, about `0.00095%`.
- All `5212 / 5212` original Sapient tokenized tasks are present; no original tasks are missing.
- The Danish-rich sample adds mixed/Danish content on top, with `110,736,199,356` global covered tokens across 4 epochs.

See [[data-mix-policy]] for the per-category and task-level comparison.

Later update on 2026-05-24:

- Mixed-only filtered sampling with the default prefix config completed at `data/sampled_mixed_english_danish_filtered`, but it was too large: `70,644,435,216` tokens per epoch.
- Cause: the default prefix caps did not match `sapient_cleaned__...` task names in `data/tokenized_mixed`.
- A capped config was added at `data_io/prefix_config_mixed_2x_original.yaml`.
- Dry-run estimate with PrefixLM truncation/filtering: `24,630,898,966` tokens per epoch, about `1.755x` the original Sapient per-epoch size and below the requested `2x` ceiling.
- The capped sampling run completed. Final `metadata.total_length` is `24,630,436,020` tokens per epoch, also about `1.755x` original and below the requested `2x` ceiling.
- Outputs:
  - `data/sampled_mixed_english_danish_filtered_2x_original`
  - `data/show_analytics_mixed_english_danish_filtered_2x_original.md`
  - `logs/sample_mixed_english_danish_filtered_2x_original.err`
- Hydra data config: `config/data/mixed_english_danish_filtered_2x_original.yaml`
- Note: the output directory is still about `625G` because `sample_tokenized.py` copies the full source token bank into `tokens.npy`; only the epoch indices are capped.

Update on 2026-05-21:

- The mixed corpus now has `1326` converted source files after splitting `nemotron_swe/data/swe.parquet` into `swe_part_00.parquet` through `swe_part_09.parquet`.
- A detached `tmux` tokenizer session `hrm_tok_mixed` is running one effective worker on the full `data/converted_sources` tree. It reported `Processing 10 files on 1 threads...`, corresponding to the missing split SWE shards.
- A detached `tmux` tokenizer session `hrm_tok_original` is running one effective worker on the original Sapient roots. It reported `Processing 77 files on 1 threads...`.
- Logs:
  - `logs/tokenizer_mixed_swe_resume.log`
  - `logs/tokenizer_original_resume.log`

Monitor commands:

```bash
tmux capture-pane -pt hrm_tok_mixed -S -40
tmux capture-pane -pt hrm_tok_original -S -40
find /work/dfm/HRM-Text/data/tokenized_mixed -name metadata.json | wc -l
find /work/dfm/HRM-Text/data/tokenized_original_sapient -name metadata.json | wc -l
```

Later update on 2026-05-21:

- `hrm_tok_mixed` was stopped and restarted after incremental conversion added new mixed sources.
- At restart, `data/converted_sources` had `1340` tokenizable files and `data/tokenized_mixed` had `1317` completed metadata files.
- The restarted mixed tokenizer reported `Processing 23 files on 1 threads...`.
- `hrm_tok_original` was left running.

Later update on 2026-05-21:

- The mixed tokenizer began reading the accidentally restored unsplit `data/converted_sources/nemotron_swe/data/swe.parquet`.
- `hrm_tok_mixed` was stopped, `swe.parquet` and its stale `swe.parquet.convert_meta.json` sidecar were removed, and the mixed tokenizer was restarted.
- After cleanup, `data/converted_sources` had `1339` tokenizable files, `data/tokenized_mixed` had `1318` completed metadata files, and the restarted mixed tokenizer reported `Processing 21 files on 1 threads...`.

## Filesystem / Scratch State

Verified on 2026-05-21:

- `/work` and `/work/dfm` are WEKA (`wekafs`) mounts.
- `/tmp`, `/var/tmp`, `/mnt`, `/opt`, and `/var/lib` resolve to the container root overlay, not to a separate clean local scratch mount.
- `/dev/shm` is tmpfs with about `2.8T` available; avoid using it for this pipeline unless explicitly chosen, because it consumes RAM-backed memory.
- `/etc/ucloud` and `/opt/ucloud` are local XFS empty-dir mounts but only about `46G`, too small for the tokenizer staging experiments.
- The node exposes NVMe block devices (`nvme0n1` and `nvme1n1`), but no large directly mounted writable NVMe scratch path is visible inside the container.

Operational consequence: the failed `/tmp/tokenize` staging attempt was not a good test of a clean local disk. Until a real local NVMe scratch mount is provided by UCloud/admin, run tokenization from `/work/dfm/HRM-Text` with a small worker count and `nice`/`ionice`.

## Possible `data_io` Relocation

Verified on 2026-05-24. Confidence: high.

`data_io` is currently an untracked nested git checkout at `/work/dfm/HRM-Text/data_io`. Moving it to `/work/dfm/HRM-Text/external/data_io` is mostly a path refactor. Required updates include:

- root docs and agent notes that say `data_io/tokenizer` must be run from `data_io/tokenizer`;
- runnable scripts with hard-coded `REPO_ROOT / "data_io"` or `${REPO_ROOT}/data_io`, especially `scripts/prepare_40b_sapient_plus_danish.py` and `scripts/reproduce_original_sapient_l.sh`;
- cleanup safety guards in `scripts/cleanup_failed_training_run.sh`;
- wiki commands under `wiki/pages/*` and `wiki/entities/*`;
- any shell commands copied from prior notes that reference `data_io/trained_tokenizers/bpe/tokenizer.json`, `data_io/tokenizer`, or `data_io/sample_tokenized.py`.

Prefer adding one canonical variable such as `DATA_IO_DIR=${DATA_IO_DIR:-${REPO_ROOT}/external/data_io}` in scripts rather than scattering the new path.

## `dfm-evals` Location

Verified on 2026-05-24. Confidence: high.

`dfm-evals` is an untracked nested git checkout at `/work/dfm/HRM-Text/dfm-evals`. It was moved from `/work/dfm/HRM-Text/external/dfm-evals` with its local `.venv` intact. The nested checkout's git status remained unchanged by the move; it still has local task patches in `dfm_evals/tasks/danish_citizen_tests.py` and `dfm_evals/tasks/talemaader/task.py`.

The main runnable reference is `scripts/run_dfm_evals_on_checkpoints.sh`, whose default is:

```bash
DFM_EVALS_DIR="${DFM_EVALS_DIR:-${REPO_ROOT}/dfm-evals}"
```

No model training configs depend on the path directly. Existing logs under `logs/dfm_evals/...` remain where they are.

## Mixed Corpus Next Commands

Convert filtered sources:

```bash
cd /work/dfm/HRM-Text
python scripts/convert_filtered_sources.py --force --copy-ready --workers 32
```

Tokenize converted sources:

```bash
cd /work/dfm/HRM-Text/data_io/tokenizer
cargo run --release --bin tokenizer -- \
  /work/dfm/HRM-Text/data/converted_sources \
  --tokenizer-path /work/dfm/HRM-Text/data_io/trained_tokenizers/bpe/tokenizer.json \
  -o /work/dfm/HRM-Text/data/tokenized_mixed
```

Sample tokenized data:

```bash
cd /work/dfm/HRM-Text/data_io
python sample_tokenized.py \
  tokenized_path=../data/tokenized_mixed \
  output_path=../data/sampled \
  epochs=4 \
  > ../data/show_analytics.md
```

## DFM Mix Sampling

Updated on 2026-05-28. Confidence: high.

The DFM mix was sampled successfully from `data/tokenized_mixed` into `data/sampled_dfm` using `data_io/sample_tokenized.py`. The manual sampler process finished after writing tokens, generating four epoch index directories, and generating the analytics report.

Command used from the repo root:

```bash
setsid bash -c 'cd /work/dfm/HRM-Text/data_io && ionice -c2 -n7 nice -n 10 python sample_tokenized.py tokenized_path=../data/tokenized_mixed output_path=../data/sampled_dfm epochs=4 concat_workers=4 prefix_config_path=prefix_config_dfm.yaml > ../data/show_analytics_dfm.md 2> ../logs/tokenize/dfm_sample_stderr.log' > logs/tokenize/dfm_sample_stdout.log 2>&1 &
```

Verified outputs:

- `data/sampled_dfm/tokens.npy`: about `630G`.
- `data/sampled_dfm/epoch_0` through `data/sampled_dfm/epoch_3`.
- `data/sampled_dfm/metadata.json`.
- `data/show_analytics_dfm.md`: analytics report.
- Metadata reports `total_length=28254014835`, `max_seq_len=4097`, and tokenizer path `/work/dfm/HRM-Text/data_io/trained_tokenizers/bpe/tokenizer.json`.

## DFM L Training

Updated on 2026-05-29. Confidence: high.

The active DFM L training run was launched with:

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 torchrun --nproc_per_node=8 pretrain.py data=dfm arch/size@arch=L lr=2.5e-4 global_batch_size=172032 +project_name="DFM L" +run_name=dfm-L +checkpoint_path=checkpoints/dfm/L
```

The local W&B run directory is `wandb/run-20260528_234406-kgnbdmwf`. While the run was still active, it was manually synced into the original+mixed W&B project as a second project view with:

```bash
wandb sync --include-online --no-mark-synced --project "Original Plus Mixed Danish Instruction Rich L" wandb/run-20260528_234406-kgnbdmwf
```

W&B reported the target as `peter-sk-sdu/Original Plus Mixed Danish Instruction Rich L/runs/kgnbdmwf` and completed with `done.`.

## DFM L CP1 Evaluation Queue

Updated on 2026-05-29. Confidence: high.

`scripts/schedule_checkpoint_evals.sh` is a generic 8-GPU checkpoint eval
scheduler derived from the original+mixed CP3/CP4 scheduler. For DFM L CP1 it
targets:

- `CKPT_PATH=checkpoints/dfm/L`
- `EPOCH=1`
- `WANDB_PROJECT="DFM L"`
- `WANDB_RUN_ID=kgnbdmwf`
- `WANDB_RUN_NAME=dfm-L`

Superseded on 2026-05-29: the initial dry-run used 16 MATH shards and 16
IFEval-DA shards.

Current sharding policy on 2026-05-29. Confidence: high for implemented
standard and DFM behavior.

Runtime buckets:

- `<10m`: 1 shard.
- `10-20m`: 2 shards.
- `20-40m`: 4 shards.
- `40-80m`: 8 shards.
- `80-160m`: 16 shards.
- `160-320m`: 32 shards.

Implemented in `scripts/schedule_checkpoint_evals.sh`:

- Standard evals are generically shardable through `evaluation/main.py`, which
  now accepts `num_shards` and `shard_index` in each benchmark config and slices
  prompts/targets after benchmark construction.
- Standard shard metrics are merged with `scripts/merge_standard_eval_shards.py`
  before W&B logging.
- IFEval-DA defaults to 32 shards via
  `config/dfm_evals_hrm_ifeval_da_32_shards.yaml`.
- DFM eval tasks now accept `num_shards` and `shard_index` through a shared
  `dfm-evals/dfm_evals/tasks/_sharding.py` helper.
- Sharded DFM task metrics are merged from Inspect `.eval` sample records with
  `scripts/merge_dfm_eval_shards.py` before W&B logging. Shards do not log
  partial metrics as full metrics.

Superseded on 2026-05-29: the DFM CP1 dry-run queue had `112` jobs with
`MATH` split into `8` shards. Observed CP1 MATH shard runtime was about an hour
or more for `625` samples, which violates the target of roughly ten minutes per
shard.

Current future-run queue policy on 2026-05-29. Confidence: high.

- `GSM8k`: 8 shards.
- `DROP`: 4 shards.
- `MMLU`: 4 shards.
- `ARC`: 1 shard.
- `HellaSwag`: 2 shards.
- `Winogrande`: 1 shard.
- `BoolQ`: 1 shard.
- `MATH`: 64 shards.
- `danish_citizen_tests`: 1 shard.
- `dala`: 1 shard.
- `gec_dala`: 2 shards.
- `wmt24pp_en_da`: 8 shards.
- `multi_wiki_qa`: 2 shards.
- `piqa`: 1 shard.
- `generative_talemaader`: 8 shards.
- `govreport`: 16 shards.
- `nordjyllandnews`: 8 shards.
- `humaneval`: 4 shards.
- `ifeval-da`: 32 shards.

Prior status logs show the longest tails were IFEval-DA, MATH, GSM8k,
WMT24++ en-da, generative-talemaader, and summarization tasks with BERTScore.

Validation:

- `python -m py_compile` passed for the scheduler helpers and patched eval
  task files.
- `bash -n scripts/schedule_checkpoint_evals.sh` passed.
- `DRY_RUN=1 ... scripts/schedule_checkpoint_evals.sh` produced the 112-job
  CP1 queue.
- A zero-sample Inspect probe for `hrm_danish_multi_wiki_qa` with
  `-T num_shards=2 -T shard_index=0` resolved to
  `dataset: MultiWikiQA-da-shard-0-of-2`.
- A zero-sample Inspect probe for `hrm_code_humaneval_local` with
  `-T num_shards=4 -T shard_index=0` resolved to
  `dataset: humaneval-shard-0-of-4`.
- A dry run after the MATH adjustment confirmed that
  `scripts/schedule_checkpoint_evals.sh` queues `64` standard `MATH` shards.

Launch state on 2026-05-29. Confidence: high.

Superseded: the DFM L CP1 112-job eval scheduler was initially queued behind a
watcher because the active DFM L training run still occupied all 8 GPUs with
high utilization.

Updated later on 2026-05-29: the user confirmed the GPUs had enough headroom,
so the watcher was stopped and the scheduler was launched immediately while the
DFM L training run was still active. Command:

```bash
EPOCH=1 CKPT_PATH=checkpoints/dfm/L GPUS=0,1,2,3,4,5,6,7 \
LOG_ROOT=logs/eval/dfm_L_epoch1_queued_all \
DFM_LOG_ROOT=logs/dfm_evals/dfm_L_epoch1_queued_all \
WANDB_PROJECT="DFM L" WANDB_RUN_ID=kgnbdmwf WANDB_RUN_NAME=dfm-L \
MODEL_PREFIX=hrm-dfm-L scripts/schedule_checkpoint_evals.sh
```

Files:

- Scheduler PID file: `logs/eval/dfm_L_epoch1_queued_all/scheduler.pid`
- Launcher log: `logs/eval/dfm_L_epoch1_queued_all.launcher.log`
- Status log: `logs/eval/dfm_L_epoch1_queued_all/status.tsv`
- Queue file: `logs/eval/dfm_L_epoch1_queued_all/jobs.tsv`

Verified immediately after launch:

- Scheduler PID: `2285914`.
- Queue: `112` jobs.
- Checkpoint readiness passed for `checkpoints/dfm/L` epoch 1.
- Workers started, with staggered first jobs beginning on `GSM8k` shards.

Completion inspection on 2026-05-29. Confidence: high.

The DFM L CP1 scheduler exited after all `112` queued jobs reached `END`
status, but final aggregation reported two failures:

```text
FINAL_MERGE_STANDARD_MATH_FAILED
FINAL_MERGE_DFM_generative_talemaader_FAILED
FINAL_MERGE_END
```

Successful synced aggregates include standard `ARC`, `BoolQ`, `DROP`,
`GSM8k`, `HellaSwag`, `MMLU`, and `Winogrande`, plus DFM `dala`,
`danish_citizen_tests`, `gec_dala`, `govreport`, `humaneval`,
`multi_wiki_qa`, `nordjyllandnews`, `piqa`, `wmt24pp_en_da`, and merged
`ifeval-da`. The merged IFEval-DA file is
`logs/dfm_evals/dfm_L_epoch1_queued_all/merged_ifeval_da_metrics.json` and
contains `541` samples with
`dfm_eval/ifeval-da/instruction_following/final_acc=0.393870787633715`.

`MATH` failed only for shard `4` of `8`. Its log is
`logs/eval/dfm_L_epoch1_queued_all/standard_shards/MATH/MATH_shard_4_of_8.log`
and shows an HF Hub `504 Gateway Time-out` while loading
`EleutherAI/hendrycks_math` `precalculus`; the scheduler correctly recorded
`END standard MATH shard_4_of_8 gpu_0 status_1`. The other seven MATH shards
have summaries and do not need to be rerun.

`generative_talemaader` failed at merge time because the wrapper task did not
forward `num_shards` and `shard_index`; each of the eight launched jobs ran the
full `808` samples and therefore produced duplicate sample IDs such as `dtm_0`.
`dfm-evals/dfm_evals/tasks/talemaader/task.py` was patched so
`generative_talemaader()` accepts and forwards `num_shards` and `shard_index`.
`python -m py_compile` passes, and a zero-sample probe now resolves to
`dataset: generative-talemaader-shard-0-of-8` without unused-parameter
warnings:

```bash
OPENAI_API_KEY=inspectai uv run --project dfm-evals evals suite hrm_danish_generative_talemaader \
  --file config/dfm_evals_hrm_single_tasks.yaml \
  --target-model openai/dummy \
  --target-base-url http://127.0.0.1:9/v1 \
  --judge-model openai/dummy \
  --judge-base-url http://127.0.0.1:9/v1 \
  --mode set -- -T num_shards=8 -T shard_index=0 --limit 0 \
  --log-dir /tmp/hrm_talemaader_shard_probe --log-dir-allow-dirty
```

The already completed `generative_talemaader` shard `0` is actually a full run
over all `808` samples, so it can be logged as the full CP1 talemaader result
without rerunning judge inference. Verified local merge from only that `.eval`
produces
`dfm_eval/generative-talemaader/model_graded_fact/accuracy=0.07920792079207921`,
`accuracy_stderr=0.008161235917216217`, and `n=808`.

Repair update on 2026-05-29. Confidence: high.

The complete `generative_talemaader` shard `0` `.eval` was merged and synced to
W&B run `kgnbdmwf` in project `DFM L` using:

```bash
python scripts/merge_dfm_eval_shards.py \
  logs/dfm_evals/dfm_L_epoch1_queued_all/generative_talemaader/shard_0_of_8/epoch_1/inspect/*.eval \
  --task generative_talemaader \
  --epoch 1 \
  --output logs/dfm_evals/dfm_L_epoch1_queued_all/generative_talemaader/merged_metrics.json \
  --log-wandb \
  --project "DFM L" \
  --run-id kgnbdmwf \
  --run-name dfm-L
```

Future scheduler runs are guarded against the same talemaader failure mode:
`scripts/schedule_checkpoint_evals.sh` now checks each dfm-evals shard log for
Inspect warnings that `num_shards` or `shard_index` were not used and fails that
job instead of treating it as valid shard output. The scheduler also defaults to
`MAX_RETRIES=3`, meaning each failed job can be attempted four total times, and
DFM/IFEval shard output directories are cleared before each attempt so partial
failed `.eval` files do not contaminate the final merge.

`MATH` shard `4` of `8` was restarted manually on GPU `0` with:

```bash
CUDA_VISIBLE_DEVICES=0 PYTHONUNBUFFERED=1 python -u -m evaluation.main \
  config=evaluation/config/hrm_benchmarking.yaml \
  ckpt_path=checkpoints/dfm/L \
  ckpt_epoch=1 \
  "benchmarks=[{name: MATH, num_shards: 8, shard_index: 4}]" \
  generation_config.batch_size=8 \
  > logs/eval/dfm_L_epoch1_queued_all/standard_shards/MATH/MATH_shard_4_of_8.log 2>&1
```

For this already-started CP1 repair, keep the running `shard_4_of_8` and merge
it with the seven completed `of_8` shard logs. Switching CP1 repair to `64`
shards would require either rerunning all MATH under the new layout or adding a
one-off range slicer for only the missing eighth.

Final CP1 eval repair result on 2026-05-29. Confidence: high.

The restarted `MATH` shard `4` finished successfully with `n=625`,
`acc=0.3952`, and `invalid=0.1200`. All eight `MATH` shards were then merged
and synced to W&B run `kgnbdmwf` in project `DFM L`:

```text
eval/MATH/acc: 0.3854
eval/MATH/invalid: 0.1106
eval/MATH/n: 5000
```

The final local aggregate is
`logs/eval/dfm_L_epoch1_queued_all/standard_shards/MATH/merged_metrics.json`.
The sync log is
`logs/eval/dfm_L_epoch1_queued_all/standard_shards/MATH/merge_and_wandb_sync.log`.

A final scan of CP1 merge logs showed `OK` for all standard merge/sync logs,
all DFM task merge/sync logs, and `merge_ifeval_da_wandb.log`; no remaining
failed aggregate logs were found.

Cross-project W&B sync note, 2026-05-29. Confidence: high.

Syncing only the original active training directory does not include all later
manual eval metrics:

```bash
wandb sync --include-online --no-mark-synced \
  --project "Original Plus Mixed Danish Instruction Rich L" \
  wandb/run-20260528_234406-kgnbdmwf
```

The eval merge scripts resumed run id `kgnbdmwf` and created separate local
W&B directories such as `wandb/run-20260529_221506-kgnbdmwf` and
`wandb/run-20260529_233116-kgnbdmwf`. A multi-directory `wandb sync` reported
success, but the target project summary still lacked the new keys when checked
through the W&B API. The reliable repair was to backfill the merged aggregate
JSON/logs directly into the target project run with `wandb.init(project=...,
id="kgnbdmwf", resume="allow")` by rerunning the local merge scripts with:

```bash
--project "Original Plus Mixed Danish Instruction Rich L" \
--run-id kgnbdmwf \
--run-name dfm-L \
--log-wandb
```

The backfill log is
`logs/wandb_backfill_kgnbdmwf_to_original_plus_mixed_20260529T234727.log`.
W&B API verification after the backfill showed the target project run contains
representative new metrics:

```text
eval/MATH/acc: 0.3854
eval/MATH/invalid: 0.1106
eval/MATH/n: 5000
dfm_eval/generative-talemaader/model_graded_fact/accuracy: 0.07920792079207921
dfm_eval/generative-talemaader/model_graded_fact/n: 808
dfm_eval/nordjyllandnews/rougeL/mean: 0.22148837256342324
dfm_eval/ifeval-da/instruction_following/final_acc: 0.393870787633715
```

DALA metric-name compatibility note, 2026-05-30. Confidence: high.

Earlier DALA runs logged the linguistic-acceptability macro-F1 and MCC metrics
with flattened scorer names:

```text
dfm_eval/dala/linguistic-acceptability/dfm_evals_macro_f1
dfm_eval/dala/linguistic-acceptability/dfm_evals_mcc
```

The first DFM L CP1 merge emitted slash-form keys
`dfm_eval/dala/linguistic-acceptability/dfm_evals/macro_f1` and
`dfm_eval/dala/linguistic-acceptability/dfm_evals/mcc`, which did not line up
with older W&B panels. The target run `kgnbdmwf` in project
`Original Plus Mixed Danish Instruction Rich L` was backfilled with the
flattened aliases:

```text
dfm_eval/dala/linguistic-acceptability/dfm_evals_macro_f1: 0.4906548270682793
dfm_eval/dala/linguistic-acceptability/dfm_evals_mcc: 0.03368421246821112
dfm_eval/dala/linguistic-acceptability/n: 2048
```

`scripts/merge_dfm_eval_shards.py` now emits the flattened DALA key names for
future runs. A local probe against the CP1 DALA `.eval` confirmed the updated
merge output.

## DFM L CP2 Evaluation Queue

Updated on 2026-05-30. Confidence: high.

CP2 exists locally under `checkpoints/dfm/L`: `fsdp2_epoch_2/.metadata` and all
eight `carry_epoch_2.{0..7}.pt` files were present before scheduling.

The CP2 all-evals scheduler was launched on all eight GPUs with:

```bash
EPOCH=2 CKPT_PATH=checkpoints/dfm/L GPUS=0,1,2,3,4,5,6,7 \
LOG_ROOT=logs/eval/dfm_L_epoch2_queued_all \
DFM_LOG_ROOT=logs/dfm_evals/dfm_L_epoch2_queued_all \
WANDB_PROJECT="DFM L" WANDB_RUN_ID=kgnbdmwf WANDB_RUN_NAME=dfm-L \
MODEL_PREFIX=hrm-dfm-L MAX_RETRIES=3 scripts/schedule_checkpoint_evals.sh
```

Launcher PID:

```text
3530318
```

Files:

- Scheduler PID file: `logs/eval/dfm_L_epoch2_queued_all/scheduler.pid`
- Launcher log: `logs/eval/dfm_L_epoch2_queued_all.launcher.log`
- Status log: `logs/eval/dfm_L_epoch2_queued_all/status.tsv`
- Queue file: `logs/eval/dfm_L_epoch2_queued_all/jobs.tsv`

Dry run and launch both reported `168` jobs. Current future-run sharding is in
effect, including `MATH=64` shards and `IFEval-DA=32` shards. The scheduler
started with all eight `GSM8k` shards across GPUs `0..7`.

`scripts/report_eval_progress.py` was patched on 2026-05-30 so CP2 progress
reports infer the epoch from `--log-root` and scale the MATH ETA from the old
8-shard measurement to the current 64-shard schedule. Use:

```bash
python scripts/report_eval_progress.py \
  --log-root logs/eval/dfm_L_epoch2_queued_all \
  --dfm-log-root logs/dfm_evals/dfm_L_epoch2_queued_all
```

Initial progress report at `2026-05-30T15:04:23+02:00` showed
`completed=0`, `active=8`, `queued=160`, `total_visible=168`, with an early
full ETA of about `3h03m`.

CP2 partial sync and cross-project backfill, 2026-05-30. Confidence: high.

While CP2 IFEval-DA was still running, all completed CP2 standard evals and
non-IFEval DFM tasks were merged and synced. The first direct backfill into
`DFM L` wrote local W&B summaries, but the remote `DFM L` run did not expose the
new keys through the API while the active training writer was still online. A
second explicit backfill from the merged JSON files fixed this; W&B API
verification showed representative keys in `DFM L`:

```text
eval/MATH/acc: 0.45380217999999994
dfm_eval/dala/linguistic-acceptability/dfm_evals_macro_f1: 0.3776531672364676
dfm_eval/humaneval/verify/accuracy: 0.14634146341463414
dfm_eval/ifeval-da/instruction_following/final_acc: 0.393870787633715
```

The IFEval-DA value above is the already-completed CP1 value; CP2 IFEval-DA was
not yet complete at the time of this sync. The CP2 backfill log explicitly
reported:

```text
epoch 2 project DFM L dfm ifeval-da skipped: 16/32 eval files available
epoch 2 project Original Plus Mixed Danish Instruction Rich L dfm ifeval-da skipped: 16/32 eval files available
```

CP2 was also backfilled to project
`Original Plus Mixed Danish Instruction Rich L`. W&B API verification showed:

```text
eval/MATH/acc: 0.45380217999999994
dfm_eval/dala/linguistic-acceptability/dfm_evals_macro_f1: 0.3776531672364676
dfm_eval/humaneval/verify/accuracy: 0.14634146341463414
dfm_eval/ifeval-da/instruction_following/final_acc: None
```

Backfill log:

```text
logs/eval/dfm_L_backfill_cp1_cp2_to_projects_20260530T181143.log
```

The second DFM-L visibility repair read merged JSON files and logged CP1/CP2
aggregate rows in one W&B run session. It skipped
`logs/dfm_evals/dfm_L_epoch2_queued_all/merged_ifeval_da_metrics.json` because
that file did not exist yet.

Final CP2 completion/sync, 2026-05-30. Confidence: high.

CP2 IFEval-DA finished all `32/32` shards and the scheduler reached
`FINAL_MERGE_END` at `2026-05-30T20:05:50+02:00`. All CP2 merge/sync logs under
`logs/eval/dfm_L_epoch2_queued_all` and
`logs/dfm_evals/dfm_L_epoch2_queued_all` were scanned and reported `OK`.

Merged CP2 IFEval-DA metrics:

```text
dfm_eval/ifeval-da/instruction_following/final_acc: 0.41158366361133086
dfm_eval/ifeval-da/instruction_following/final_stderr: 0.017495304869788196
dfm_eval/ifeval-da/instruction_following/inst_loose_acc: 0.5045766590389016
dfm_eval/ifeval-da/instruction_following/inst_strict_acc: 0.4874141876430206
dfm_eval/ifeval-da/instruction_following/prompt_loose_acc: 0.3345656192236599
dfm_eval/ifeval-da/instruction_following/prompt_strict_acc: 0.3197781885397412
```

The final merged file is
`logs/dfm_evals/dfm_L_epoch2_queued_all/merged_ifeval_da_metrics.json`.
The scheduler's merge log is
`logs/dfm_evals/dfm_L_epoch2_queued_all/merge_ifeval_da_wandb.log`.

The CP2 IFEval-DA aggregate was backfilled to both W&B projects:
`DFM L` and `Original Plus Mixed Danish Instruction Rich L`, run id
`kgnbdmwf`. The `Original Plus Mixed Danish Instruction Rich L` project exposed
the values through the normal W&B API immediately. For `DFM L`, the active
training writer again hid/overwrote the summary keys, so the run summary was
patched directly through the W&B API. Verification after the direct summary
patch showed:

```text
DFM L :: dfm_eval/ifeval-da/instruction_following/final_acc = 0.41158366361133086
DFM L :: dfm_eval/ifeval-da/instruction_following/inst_strict_acc = 0.4874141876430206
DFM L :: dfm_eval/ifeval-da/instruction_following/prompt_strict_acc = 0.3197781885397412
```

CP2 heavy-first rerun, 2026-05-31. Confidence: high.

`scripts/schedule_checkpoint_evals.sh` now supports `QUEUE_ORDER=heavy_first`.
That queue order starts with IFEval-DA shards, then MATH shards, then the other
longer shard groups before the short single-shard tasks. A dry run with
`QUEUE_ORDER=heavy_first` queued `168` jobs and showed the expected leading
tasks.

The first CP2 heavy-first background launch at
`logs/eval/dfm_L_epoch2_heavy_first_20260531T1059` exited before workers
started, leaving an empty status log and a partial queue. It was superseded by a
detached `setsid` launch.

Active launch:

```bash
EPOCH=2 EVAL_EPOCH=2 CKPT_TAG=epoch_2 CKPT_PATH=checkpoints/dfm/L \
GPUS=0,1,2,3,4,5,6,7 QUEUE_ORDER=heavy_first \
LOG_ROOT=logs/eval/dfm_L_epoch2_heavy_first_20260531T1102 \
DFM_LOG_ROOT=logs/dfm_evals/dfm_L_epoch2_heavy_first_20260531T1102 \
WANDB_PROJECT="DFM L" WANDB_RUN_ID=kgnbdmwf WANDB_RUN_NAME=dfm-L \
MODEL_PREFIX=hrm-dfm-L MAX_RETRIES=3 scripts/schedule_checkpoint_evals.sh
```

Scheduler PID: `2557293`.

Files:

- Scheduler PID file:
  `logs/eval/dfm_L_epoch2_heavy_first_20260531T1102/scheduler.pid`
- Launcher log:
  `logs/eval/dfm_L_epoch2_heavy_first_20260531T1102.launcher.log`
- Status log:
  `logs/eval/dfm_L_epoch2_heavy_first_20260531T1102/status.tsv`
- DFM log root:
  `logs/dfm_evals/dfm_L_epoch2_heavy_first_20260531T1102`

Initial verification showed checkpoint readiness for `epoch_2`, all eight
workers started on IFEval-DA shards `0..7`, and `nvidia-smi` reported all eight
GPUs at `100%` utilization with roughly `101-125 GB` memory in use. Confidence:
high.

Final heavy-first CP2 sync, 2026-05-31. Confidence: high.

The heavy-first CP2 scheduler completed all `168/168` jobs and reached
`FINAL_MERGE_END` at `2026-05-31T15:52:04+02:00`. The built-in final merge
synced the aggregates to project `DFM L`, run id `kgnbdmwf`.

The same merged aggregates were then backfilled to project
`Original Plus Mixed Danish Instruction Rich L`, run id `kgnbdmwf`, run name
`dfm-L`. The successful backfill log is:

```text
logs/eval/dfm_L_epoch2_heavy_first_backfill_to_original_plus_mixed_20260531T174752.log
```

It logged `195` standard `eval/*` metrics from `8` merged standard files and
`74` `dfm_eval/*` metrics from `11` merged DFM files. W&B API verification
against
`https://wandb.ai/peter-sk-sdu/Original%20Plus%20Mixed%20Danish%20Instruction%20Rich%20L/runs/kgnbdmwf`
returned representative values:

```text
eval/MATH/acc = 0.45380217999999994
eval/GSM8k/acc = 0.7665051554207735
eval/MMLU/acc = 0.33975000000000005
dfm_eval/ifeval-da/instruction_following/final_acc = 0.41204577082020327
dfm_eval/generative-talemaader/model_graded_fact/accuracy = 0.13923267326732677
dfm_eval/humaneval/verify/accuracy = 0.14634146341463414
dfm_eval/nordjyllandnews/rougeL/mean = 0.20810562203119595
```

Follow-up visibility check on 2026-05-31. Confidence: high.

The CP2 heavy-first metrics are present in W&B history, not only in summary.
API checks with one metric family at a time returned history rows for run
`kgnbdmwf` in project `Original Plus Mixed Danish Instruction Rich L`,
including:

```text
eval/MATH/acc at _step 900103 with eval/epoch = 2
dfm_eval/ifeval-da/instruction_following/final_acc at _step 900104 with dfm_eval/epoch = 2
```

If the W&B UI does not show them, likely causes are workspace/run filters that
exclude the `dfm-L` run, stale panel state, or plots using `_step` as x-axis.
For standard eval panels use `eval/epoch` as x-axis; for DFM eval panels use
`dfm_eval/epoch`.

DFM L CP3 full eval launch, 2026-05-31. Confidence: high.

Before scheduling CP3, W&B history for run `kgnbdmwf` in project
`Original Plus Mixed Danish Instruction Rich L` was checked for
`eval/MATH/acc` and contained only DFM CP1/CP2 rows. The local DFM CP3
checkpoint was complete under `checkpoints/dfm/L` with `fsdp2_epoch_3` and all
eight `carry_epoch_3.{0..7}.pt` files.

CP3 full evals were launched with heavy-first ordering:

```bash
EPOCH=3 EVAL_EPOCH=3 CKPT_TAG=epoch_3 CKPT_PATH=checkpoints/dfm/L \
GPUS=0,1,2,3,4,5,6,7 QUEUE_ORDER=heavy_first \
LOG_ROOT=logs/eval/dfm_L_epoch3_heavy_first_20260531T2227 \
DFM_LOG_ROOT=logs/dfm_evals/dfm_L_epoch3_heavy_first_20260531T2227 \
WANDB_PROJECT="DFM L" WANDB_RUN_ID=kgnbdmwf WANDB_RUN_NAME=dfm-L \
MODEL_PREFIX=hrm-dfm-L MAX_RETRIES=3 scripts/schedule_checkpoint_evals.sh
```

Scheduler PID: `3527439`.

Files:

- Scheduler PID file:
  `logs/eval/dfm_L_epoch3_heavy_first_20260531T2227/scheduler.pid`
- Launcher log:
  `logs/eval/dfm_L_epoch3_heavy_first_20260531T2227.launcher.log`
- Status log:
  `logs/eval/dfm_L_epoch3_heavy_first_20260531T2227/status.tsv`
- DFM log root:
  `logs/dfm_evals/dfm_L_epoch3_heavy_first_20260531T2227`

Initial verification showed `168` jobs queued, checkpoint readiness for
`epoch_3`, workers started on IFEval-DA shards, and all eight GPUs active.

DFM L CP3 eval resume/GovReport recovery, 2026-06-01. Confidence: high.

The CP3 scheduler was later stopped and resumed from
`logs/eval/dfm_L_epoch3_heavy_first_20260531T2227` with
`RESUME_EXISTING_QUEUE=1`. The resumed queue reached the GovReport shards after
finishing the standard eval shards. GovReport initially left all GPUs idle
because `scripts/hrm_openai_server.py` model-server processes were crashing
before serving `/health`, while dfm-evals clients waited on localhost ports.
Two import issues were fixed:

- `scripts/hrm_openai_server.py` now inserts the repo root into `sys.path`
  before importing repo modules.
- `utils/__init__.py` was added so `from utils.functions import ...` resolves
  to the repo-local utility package instead of colliding with other `utils`
  namespace/package paths.

A scheduler cleanup bug was also fixed in `scripts/schedule_checkpoint_evals.sh`:
the DFM and IFEval `RETURN` cleanup traps now read `${server_pid:-}` and
`${judge_pid:-}` into local temporaries before testing/killing them. Without
this, `set -u` could terminate a worker later with an unbound local variable
after a DFM task returned.

When launching a long resume from Codex/tool-managed shells, use `setsid -f`
rather than plain background `nohup`; plain background launches were observed
to be torn down after the launcher command returned. The working detached
resume pattern was:

```bash
setsid -f bash -c 'exec env \
  EPOCH=3 EVAL_EPOCH=3 CKPT_TAG=epoch_3 CKPT_PATH=checkpoints/dfm/L \
  GPUS=0,1,2,3,4,5,6,7 QUEUE_ORDER=heavy_first RESUME_EXISTING_QUEUE=1 \
  LOG_ROOT="logs/eval/dfm_L_epoch3_heavy_first_20260531T2227" \
  DFM_LOG_ROOT="logs/dfm_evals/dfm_L_epoch3_heavy_first_20260531T2227" \
  WANDB_PROJECT="DFM L" WANDB_RUN_ID=kgnbdmwf WANDB_RUN_NAME=dfm-L \
  MODEL_PREFIX=hrm-dfm-L MAX_RETRIES=3 STARTUP_STAGGER_SECONDS=10 \
  scripts/schedule_checkpoint_evals.sh \
  >> "logs/eval/dfm_L_epoch3_heavy_first_20260531T2227.resume6.setsid.log" 2>&1' \
  </dev/null
```

After the `setsid` relaunch, GovReport shards resumed successfully: status
showed shards `0..7` starting, several ending with status `0`, later shards
starting, `11` GovReport shard eval files written, and the remaining queue
down to `38` jobs. Confidence: high.

Final CP3 eval status update, 2026-06-01. Confidence: high.

The resumed CP3 scheduler consumed the full queue: `jobs.tsv` reached `0`
lines, all eval workers/server processes exited, and the last eval job
(`dfm humaneval shard_3_of_4`) ended with status `0` at
`2026-06-01T13:35:39+02:00`. The scheduler then entered `FINAL_MERGE_START`
and reached `FINAL_MERGE_END` at `2026-06-01T13:35:56+02:00`.

However, every final merge-and-W&B-sync command logged `FAILED` because W&B was
not authenticated in the detached scheduler environment:

```text
wandb.errors.errors.UsageError: No API key configured. Use `wandb login` to log in.
```

The eval artifacts are present locally, including HumanEval shard inspect and
EEE outputs. The next operational step is to rerun merge/sync with a valid W&B
login or `WANDB_API_KEY` in the environment; the eval computations themselves
do not need to be rerun for this failure.

Superseded by later 2026-06-01 update: W&B was authenticated and all CP3
merge/sync commands were rerun successfully. Confidence: high.

After `wandb login`, the standard eval, IFEval-DA, and DFM eval merge/sync
commands were rerun manually against:

- `logs/eval/dfm_L_epoch3_heavy_first_20260531T2227`
- `logs/dfm_evals/dfm_L_epoch3_heavy_first_20260531T2227`

The rerun wrote `*.rerun.log` merge logs and printed successful sync completion
for all standard eval tasks, IFEval-DA, and DFM tasks through HumanEval.
W&B API summary verification for project `DFM L`, run id `kgnbdmwf`, found
representative CP3 metrics including:

```text
eval/MATH/acc/epoch_3 = 0.47639826
eval/GSM8k/acc/epoch_3 = 0.793018726307809
dfm_eval/ifeval-da/instruction_following/final_acc/epoch_3 = 0.4760777566757044
dfm_eval/govreport/rougeL/mean/epoch_3 = 0.019145910006355467
dfm_eval/nordjyllandnews/rougeL/mean/epoch_3 = 0.18987313066472783
dfm_eval/humaneval/verify/accuracy/epoch_3 = 0.2195121951219512
```

Later correction on 2026-06-01. Confidence: high.

The initial verification above was for project `DFM L`. The same CP3 merged
metrics were then explicitly backfilled to project
`Original Plus Mixed Danish Instruction Rich L`, run id `kgnbdmwf`, because
that project initially showed only CP1 and CP2. Backfill log:

```text
logs/eval/dfm_L_epoch3_heavy_first_20260531T2227/backfill_cp3_to_original_plus_mixed_20260601T134813.log
```

W&B API summary verification against
`peter-sk-sdu/Original Plus Mixed Danish Instruction Rich L/kgnbdmwf` found:

```text
eval/MATH/acc/epoch_3 = 0.47639826
eval/GSM8k/acc/epoch_3 = 0.793018726307809
dfm_eval/ifeval-da/instruction_following/final_acc/epoch_3 = 0.4760777566757044
dfm_eval/govreport/rougeL/mean/epoch_3 = 0.019145910006355467
dfm_eval/nordjyllandnews/rougeL/mean/epoch_3 = 0.18987313066472783
dfm_eval/humaneval/verify/accuracy/epoch_3 = 0.2195121951219512
```

DFM L train-history backfill to Original Plus Mixed project, 2026-06-01.
Confidence: high.

The target project `Original Plus Mixed Danish Instruction Rich L`, run
`kgnbdmwf`, initially had only partial DFM L `train/*` history when sampled via
the W&B API: visible train rows reached about step `302575`, while the source
project `DFM L`, run `kgnbdmwf`, reached about step `592395`.

Attempted direct full-file sync from the local full run:

```bash
wandb sync --include-online --no-mark-synced \
  --project "Original Plus Mixed Danish Instruction Rich L" \
  wandb/run-20260528_234406-kgnbdmwf
```

This completed and updated summary state, but the target run still lacked
high-step `train/*` history above `500k`.

A direct API replay with `wandb.log(..., step=<source_step>)` was also attempted
and then stopped. It failed conceptually because eval backfills had already
advanced W&B's internal `_step` to about `900124`; W&B rejected later train
rows at `_step` values `302k..592k` as non-monotonic.

Superseded by the clean-run solution recorded above on 2026-06-01: replay the full DFM L train history into the target run using
W&B's monotonic internal step, while storing the original training step in
`train/source_step` and defining it as the step metric for train curves. The
successful replay logged `118,775` source train points from source step `5` to
`592395` into `Original Plus Mixed Danish Instruction Rich L/kgnbdmwf`.

Verification after replay:

```text
train/source_step = 592395
train/loss = 1.1001414060592651
train/accuracy = 0.7316066026687622
train/exact_accuracy = 0.1923076957464218
train/lr = 0.00025
train/dfm_loss = 1.1001414060592651
train/dfm_accuracy = 0.7316066026687622
train/dfm_exact_accuracy = 0.1923076957464218
train/dfm_lr = 0.00025
```

This same-run replay polluted the original target run and should not be used
for clean train plots. For the clean comparison, use
`Original Plus Mixed Danish Instruction Rich L/dfmlfull0601`; it has native
train `_step` values plus eval and dfm_eval metrics. The
`train/dfm_*` metrics are duplicated aliases intended to make the DFM L
backfilled train curves easy to distinguish from any older partial `train/*`
history in the target project.

Checkpoint format update on 2026-06-02. Confidence: high.

`pretrain.py` now has an explicit `checkpoint_format` config field with
default `sharded`. The default path is intentionally the existing FSDP2/PyTorch
DCP checkpointing path and writes model/optimizer state under `fsdp2_{tag}` plus
rank-local carry files named `carry_{tag}.{rank}.pt`. This is the path to use
for current FSDP training unless a specific experiment needs otherwise.

An opt-in `checkpoint_format=unsharded` path was added. It writes a full
model/optimizer checkpoint from global rank 0 to `unsharded_{tag}.pt`, while
still writing rank-local carry files for every rank. In distributed/FSDP runs it
uses `StateDictOptions(full_state_dict=True, cpu_offload=True)` when saving and
`broadcast_from_rank0=True` when loading, so it is multi-node aware in the sense
that only global rank 0 owns the serialized full checkpoint and all ranks load
through the distributed state-dict API. This path is not the default and may
have much higher CPU RAM and filesystem pressure than the sharded DCP path.

Checkpoint sidecar metadata now records `checkpoint_format` alongside `tag`,
`step`, `epoch`, `batch_in_epoch`, `global_batch_size`, `data_path`, and
`seed`. Validation performed after the change: `python -m py_compile
pretrain.py`, `git diff --check`, and loading `config/cfg_pretrain.yaml` to
verify that the default is `sharded`.

DDP benchmark path update on 2026-06-02. Confidence: high.

`pretrain.py` now has `distributed_strategy` with default `fsdp`. The default
FSDP behavior is unchanged. An opt-in `distributed_strategy=ddp` wraps the model
in `torch.nn.parallel.DistributedDataParallel` after construction and before
optimizer creation. This path is intended for memory/speed experiments on
large-memory GPUs, not as the default training path. Custom model methods used
by the loop are called through a small unwrap helper so DDP-wrapped models can
still provide `compute_train_extra_args`.

For a DDP L-size DFM4 memory/speed probe, use `data=dfm4`,
`arch/size@arch=L`, `distributed_strategy=ddp`, and strongly consider
`checkpoint_format=unsharded` with a separate checkpoint directory. DDP keeps a
full model, gradients, optimizer state, and EMA state on every GPU, so it is
expected to use far more memory than the FSDP sharded path. Validation performed
after the change: `python -m py_compile pretrain.py` and loading
`config/cfg_pretrain.yaml` verified defaults of `distributed_strategy=fsdp` and
`checkpoint_format=sharded`.

DDP benchmark failure/fix on 2026-06-02. Confidence: high.

The first `dfm4-L-ddp` launch failed before completing the first step with FA4:

```text
AssertionError: inputs must be float16, bfloat16, fp8 e4m3fn, or fp8 e5m2
```

The cause was that the new DDP path left the model in fp32. The FSDP path uses
FSDP mixed precision to provide bf16 parameters/activations, but DDP has no such
policy here. The DDP branch in `create_model_and_carry` now casts the model to
`fwd_bwd_dtype` before wrapping it in `DistributedDataParallel` and before
creating AdamATan2. Validation after the fix: `python -m py_compile
pretrain.py` and `git diff --check`.

Second DDP benchmark failure/fix on 2026-06-02. Confidence: high.

After the dtype fix, DDP failed with:

```text
RuntimeError: Expected to have finished reduction in the prior iteration before starting a new one.
Parameter indices which did not receive grad for rank 0: 96
```

This is expected for HRM BP warmup/control flow: early steps deliberately run
only a subset of H/L cycles under grad, so some parameters are unused on a given
iteration. `pretrain.py` now exposes `ddp_find_unused_parameters`, defaulting to
`true`, and passes it to `DistributedDataParallel(...)`. The flag only affects
`distributed_strategy=ddp`; FSDP remains the default and is unchanged.
Validation after the fix: `python -m py_compile pretrain.py`, `git diff
--check`, and loading `config/cfg_pretrain.yaml` showed
`ddp_find_unused_parameters: true`.

DDP XL memory observation on 2026-06-02. Confidence: high.

The user reported, and local `nvidia-smi` confirmed, that an HRM XL DDP run on
DFM4 fits on 8 B200 GPUs at roughly `78-81GB` used per GPU with active GPU
utilization around `89-91%`. This is after the DDP bf16 cast and
`find_unused_parameters=True` fixes. The observed memory is much lower than the
earlier worst-case expectation for full DDP state, so DDP is a viable benchmark
path for at least XL on these 180GB GPUs. Current live query showed:

```text
GPU0 77696 MiB, GPU1 78348 MiB, GPU2 80778 MiB, GPU3 81224 MiB,
GPU4 81030 MiB, GPU5 81358 MiB, GPU6 79026 MiB, GPU7 81364 MiB
```

This observation is hardware/config specific and should not be generalized to
H100-80 without a separate run.

DFM L epoch 4 eval queue on 2026-06-02. Confidence: high.

The completed DFM L checkpoint `checkpoints/dfm/L/fsdp2_epoch_4` plus
`carry_epoch_4.{0..7}.pt` is present locally. A full eval queue for epoch 4 was
prepared with `scripts/schedule_checkpoint_evals.sh` using all 8 GPUs,
`QUEUE_ORDER=heavy_first`, `MAX_RETRIES=3`, project `DFM L`, and run id
`kgnbdmwf`. The dry-run queue contained `168` jobs:

- `32` DFM IFEval-DA shards
- `64` MATH shards
- sharded GSM8k, DROP, MMLU, HellaSwag, GovReport, WMT24++ EN-DA,
  generative-talemaader, NordjyllandNews, HumanEval, GEC-DALA, Multi Wiki QA
- single ARC, Winogrande, BoolQ, Danish citizen tests, DALA, and PIQA jobs

Superseded: Because all GPUs were occupied by the DDP XL run at launch time, a
tmux watcher was started in `hrm-1:7` (`dfmL-cp4-evals`) to wait until all GPUs
dropped below `20GB` used.

The user then requested immediate launch despite GPU occupancy. A fresh tmux
window `hrm-1:7` (`dfmL-cp4-evals-now`) launched the scheduler immediately at
`2026-06-02T13:27:03+02:00`. It queued `168` jobs, confirmed checkpoint
readiness for `epoch_4`, and started 8 worker processes:
`3767743 3767744 3767745 3767746 3767747 3767748 3767749 3767750`.
The command was:

```bash
EPOCH=4 CKPT_TAG=epoch_4 CKPT_PATH=checkpoints/dfm/L \
GPUS=0,1,2,3,4,5,6,7 \
WANDB_PROJECT="DFM L" WANDB_RUN_ID=kgnbdmwf WANDB_RUN_NAME=dfm-L \
LOG_ROOT=logs/eval/dfm_L_epoch4_queued_all \
DFM_LOG_ROOT=logs/dfm_evals/dfm_L_epoch4_queued_all \
QUEUE_ORDER=heavy_first MAX_RETRIES=3 \
scripts/schedule_checkpoint_evals.sh
```

A live progress monitor was added at `scripts/watch_eval_progress.py`.
Confidence: high. It periodically scans scheduler status plus standard/DFM eval
logs, normalizes tqdm carriage-return output, prints aggregate scheduler counts,
GPU memory/utilization, recent scheduler events, and the latest progress-like
lines from active logs. It intentionally ignores binary Inspect `.eval` archives.

The monitor was launched as a split pane in the scheduler window:

```text
hrm-1:7.1  scheduler
hrm-1:7.2  python scripts/watch_eval_progress.py ...
```

Command:

```bash
python scripts/watch_eval_progress.py \
  --log-root logs/eval/dfm_L_epoch4_queued_all \
  --dfm-log-root logs/dfm_evals/dfm_L_epoch4_queued_all \
  --interval 10 \
  --max-logs 24
```

Monitor refinement on 2026-06-02. Confidence: high. The first monitor version
showed misleading IFEval lines such as `generation: 0% ... 0/1` because the HRM
OpenAI shim emits a fresh one-request tqdm bar for each request. The monitor now
suppresses reset-only `generation: 0/1` lines and, for `server.log`, reports
compact completion counters by counting chat-completion HTTP responses. For
IFEval-DA it verifies the HF train split length as `541` and combines that with
the shard args in `inspect/eval-set.json`, so 32-way shards show counters like
`completion=11/17 failed=0` instead of raw tqdm output.

Later refinement on 2026-06-02. Confidence: high. The monitor now parses
`START`/`END` scheduler status lines to infer the active job per GPU and prints
a GPU-ordered table such as `GPU0: ifeval-da shard 0 13/17 ETA 4.6m`. ETA is
estimated from elapsed wall time since the job's scheduler `START` and the
current completed/total request count when a denominator is known.

DFM L epoch 4 eval completion/sync on 2026-06-02. Confidence: high.

All `168` CP4 eval jobs completed. One `generative_talemaader` shard initially
stalled after a port collision (`127.0.0.1:9602` already in use), was forced
through the scheduler retry path, and then completed successfully:

```text
2026-06-02T20:58:33+02:00 RETRY dfm generative_talemaader shard_4_of_8 gpu_1 status_2 next_attempt_2
2026-06-02T20:58:43+02:00 START dfm generative_talemaader shard_4_of_8 gpu_1 attempt_2_of_4
2026-06-02T21:05:38+02:00 END dfm generative_talemaader shard_4_of_8 gpu_1 status_0
```

The user asked to stop scheduler/monitor processes just as final merge started.
The eval computation itself was already complete. The final merge/W&B sync was
then rerun with `RESUME_EXISTING_QUEUE=1`, reaching:

```text
2026-06-02T21:09:37+02:00 FINAL_MERGE_START
2026-06-02T21:11:28+02:00 FINAL_MERGE_END
```

Local merged metrics were present for representative standard/DFM tasks,
including MATH, IFEval-DA, and generative-talemaader. W&B API verification for
`peter-sk-sdu/DFM L/kgnbdmwf` found representative CP4 metrics:

```text
eval/MATH/acc/epoch_4 = 0.48119616
eval/GSM8k/acc/epoch_4 = 0.7998448066717211
dfm_eval/ifeval-da/instruction_following/final_acc/epoch_4 = 0.46285377109091136
dfm_eval/generative-talemaader/model_graded_fact/accuracy/epoch_4 = 0.08168316831683169
dfm_eval/wmt24pp-en-da/chrf3pp/mean/epoch_4 = 0.5068738652893814
```

Superseded: the CP4 metrics above were synced to the wrong W&B target for the
comparison view. The intended target is
`peter-sk-sdu/Original Plus Mixed Danish Instruction Rich L/dfm-l-resume-epoch3`.
Confidence: high.

Corrected CP4 eval sync on 2026-06-02. Confidence: high.

The same local merged CP4 artifacts under
`logs/eval/dfm_L_epoch4_queued_all` and
`logs/dfm_evals/dfm_L_epoch4_queued_all` were resynced with:

```bash
EPOCH=4 CKPT_TAG=epoch_4 CKPT_PATH=checkpoints/dfm/L \
GPUS=0,1,2,3,4,5,6,7 \
WANDB_PROJECT="Original Plus Mixed Danish Instruction Rich L" \
WANDB_RUN_ID=dfm-l-resume-epoch3 \
WANDB_RUN_NAME=dfm-L-resume-epoch3 \
LOG_ROOT=logs/eval/dfm_L_epoch4_queued_all \
DFM_LOG_ROOT=logs/dfm_evals/dfm_L_epoch4_queued_all \
QUEUE_ORDER=heavy_first MAX_RETRIES=3 RESUME_EXISTING_QUEUE=1 \
scripts/schedule_checkpoint_evals.sh
```

This reached:

```text
2026-06-02T21:19:46+02:00 FINAL_MERGE_START
2026-06-02T21:24:52+02:00 FINAL_MERGE_END
```

W&B API verification for
`peter-sk-sdu/Original Plus Mixed Danish Instruction Rich L/dfm-l-resume-epoch3`
found representative CP4 metrics:

```text
eval/MATH/acc/epoch_4 = 0.48119616
eval/GSM8k/acc/epoch_4 = 0.7998448066717211
eval/MMLU/acc/epoch_4 = 0.28052499999999997
dfm_eval/ifeval-da/instruction_following/final_acc/epoch_4 = 0.46285377109091136
dfm_eval/generative-talemaader/model_graded_fact/accuracy/epoch_4 = 0.08168316831683169
dfm_eval/wmt24pp-en-da/chrf3pp/mean/epoch_4 = 0.5068738652893814
dfm_eval/humaneval/verify/accuracy/epoch_4 = 0.2195121951219512
```

Lite intra-epoch eval convention, 2026-06-03. Confidence: high.

`scripts/schedule_checkpoint_evals.sh` now supports `LITE_EVAL=1` for
intra-epoch checkpoint probes. In lite mode, the scheduler queues at most one
deterministic shard per task using `LITE_SHARD_INDEX` (default `0`). A dry run
for `CKPT_TAG=step_50000` queued `19` jobs: one shard for each of the eight
standard tasks, one shard for each of the ten non-IFEval DFM tasks, and one
IFEval-DA shard. Full single-shard tasks still run on their complete task set;
multi-shard tasks run only `shard_0` by default.

Lite metrics deliberately use separate W&B prefixes so they do not pollute full
eval curves:

- standard evals: `lite_eval/*`, x-axis `lite_eval/epoch`
- DFM evals: `lite_dfm_eval/*`, x-axis `lite_dfm_eval/epoch`

For DFM4, `data/sampled_dfm4` has `418,567` optimizer steps per epoch at
`global_batch_size=172032`, so intra-epoch checkpoint x-axis values are:

```text
step_50000:  lite epoch 0.11945518877503482
step_150000: lite epoch 0.35836556632510447
```

Use `QUEUE_ORDER=heavy_first` for these probes so the single long IFEval-DA,
MATH, DROP, and GSM8k shards start early. CP4 timing evidence suggests each
checkpoint's lite probe should be on the order of tens of minutes rather than a
full multi-hour evaluation, with IFEval-DA shard 0 and DROP shard 0 as likely
tails. Confidence: medium for runtime.

Superseded: the first `scripts/schedule_multiple_checkpoint_evals.sh` wrapper
ran checkpoints sequentially. That was the wrong design for multi-checkpoint
evals, because it could not fill idle GPUs from checkpoint N+1 while checkpoint
N still had a few long tail jobs running. Confidence: high.

Current `scripts/schedule_multiple_checkpoint_evals.sh` behavior, 2026-06-03.
Confidence: high.

The wrapper now builds one shared queue across all requested checkpoints, with
one worker per configured GPU. Each queued job carries its checkpoint tag,
fractional x-axis value, task, shard, and output roots. Workers only pop jobs
whose checkpoint files are complete; unavailable future checkpoint jobs stay in
the queue rather than occupying a GPU while waiting. After all jobs finish, the
wrapper runs final merge/W&B sync once per checkpoint.

For lite checkpoint probes, the command form remains:

```bash
CKPT_TAGS=step_50000,step_150000 \
EVAL_EPOCHS=0.11945518877503482,0.35836556632510447 \
LITE_EVAL=1 QUEUE_ORDER=heavy_first \
CKPT_PATH=checkpoints/dfm/L \
LOG_ROOT_BASE=logs/eval/dfm_L_lite_probe \
DFM_LOG_ROOT_BASE=logs/dfm_evals/dfm_L_lite_probe \
WANDB_PROJECT="Original Plus Mixed Danish Instruction Rich L" \
WANDB_RUN_ID=dfm-l-resume-epoch3 \
WANDB_RUN_NAME=dfm-L-resume-epoch3 \
scripts/schedule_multiple_checkpoint_evals.sh
```

Validation on 2026-06-03: `bash -n` passed for both scheduler scripts. A dry
run with locally present checkpoints `step_500000,step_550000` queued `38` jobs:
`19` lite jobs for each checkpoint in one shared queue. Confidence: high.

At that validation point, `step_50000` and `step_150000` were not present under
`checkpoints/dfm/L`; local step checkpoints present included `step_500000`,
`step_550000`, `step_600000`, and `step_650000`. Confidence: high.

XL DDP lite eval launch correction, 2026-06-03. Confidence: high.

The intended intra-epoch lite eval target is not `checkpoints/dfm/L`; it is
`checkpoints/dfm4/XL-ddp`. That checkpoint directory contains unsharded DDP
checkpoints:

- `unsharded_step_50000.pt` plus `carry_step_50000.{0..7}.pt`
- `unsharded_step_100000.pt` plus `carry_step_100000.{0..7}.pt`

`step_150000` was not present at inspection time. The active W&B training run
for this XL DDP run is `Original Plus Mixed Danish Instruction Rich L/4chqwd3w`
with run name `dfm4-XL-ddp`; the earlier `dbap7xai` run was crashed.

The shared-queue lite eval was launched in tmux window `hrm-1:xl-lite-eval`
with two panes: one scheduler pane and one per-GPU monitor pane. The monitor is
`scripts/watch_multi_checkpoint_eval_progress.py`, which parses the
multi-checkpoint status file and displays one line per GPU. Launch target:

```bash
CKPT_TAGS=step_50000,step_100000 \
EVAL_EPOCHS=0.11945518877503482,0.23891037755006964 \
LITE_EVAL=1 QUEUE_ORDER=heavy_first \
CKPT_PATH=checkpoints/dfm4/XL-ddp \
LOG_ROOT_BASE=logs/eval/dfm4_XL_ddp_lite_probe \
DFM_LOG_ROOT_BASE=logs/dfm_evals/dfm4_XL_ddp_lite_probe \
WANDB_PROJECT="Original Plus Mixed Danish Instruction Rich L" \
WANDB_RUN_ID=4chqwd3w \
WANDB_RUN_NAME=dfm4-XL-ddp \
GPUS=0,1,2,3,4,5,6,7 \
MAX_RETRIES=3 \
CHECKPOINT_POLL_SECONDS=60 \
scripts/schedule_multiple_checkpoint_evals.sh
```

At launch, the scheduler queued `38` jobs for two checkpoints and started the
first eight `step_50000` jobs across GPUs `0..7`. Confidence: high.

Superseded: the first tmux launch of the XL DDP lite eval used the tmux base
environment, so standard evals failed immediately with
`ModuleNotFoundError: No module named 'pydantic'` and DFM server logs failed
with `ModuleNotFoundError: No module named 'uvicorn'`. Because the scheduler
ran job bodies under `set +e`, failed `wait_for_server` calls did not stop DFM
jobs before launching `dfm-evals`, leaving eval processes waiting on dead local
OpenAI endpoints. Confidence: high.

Fix on 2026-06-03. Confidence: high. `scripts/schedule_checkpoint_evals.sh`
now defaults `PYTHON_BIN` to `/home/ucloud/miniforge3/envs/hrm/bin/python` and
uses it for standard evals, HRM OpenAI server launches, judge server launches,
merge scripts, and health checks. DFM server and judge health checks now use
`wait_for_server ... || return 1`, so a failed server cannot fall through into
`dfm-evals`. The broken eval processes were stopped, and the tmux run was
relaunched with explicit `PYTHON_BIN=/home/ucloud/miniforge3/envs/hrm/bin/python`.
After relaunch, `pgrep` showed real `hrm_openai_server.py` and
`evaluation.main` processes, and per-GPU memory rose to roughly `102-104GB`,
confirming eval models were loaded alongside the active XL training job.

XL DDP lite eval activity check and future incremental sync, 2026-06-03.
Confidence: high.

At `07:30 CEST`, the active tmux run `hrm-1:xl-lite-eval` showed all eight
GPUs at `100%` utilization, with the monitor reporting `started=16`,
`finished=8`, `active=8`, and `queued=22`. Completed step-50000 lite jobs at
that snapshot included `ARC`, `BoolQ`, `HellaSwag`, `MMLU`, `Winogrande`,
`govreport`, `generative_talemaader`, and `nordjyllandnews`. Active jobs were
`dfm_ifeval` shard 0, `MATH`, `GSM8k`, `DROP`, `gec_dala`, `humaneval`,
`wmt24pp_en_da`, and `multi_wiki_qa`. Process inspection confirmed matching
`evaluation.main`, `dfm-evals`, and `hrm_openai_server.py` processes. The
current running scheduler was launched before the incremental merge/sync patch
below, so it will not automatically sync each completed task unless manually
merged during the run. Confidence: high.

Future `scripts/schedule_multiple_checkpoint_evals.sh` launches now perform
incremental merge and W&B sync per task. After every successful shard job,
`maybe_merge_task()` checks whether all expected shards for that task and
checkpoint are ready; if yes, it immediately runs the relevant merge script with
the configured prefix and W&B project/run:

- standard evals: `scripts/merge_standard_eval_shards.py`
- IFEval-DA: `scripts/merge_ifeval_da_shards.py`
- other DFM evals: `scripts/merge_dfm_eval_shards.py`

The implementation uses per-task lock and marker files under the checkpoint log
root to avoid duplicate merges when several workers finish near the same time.
In `LITE_EVAL=1`, readiness means the configured lite shard is done; in full
mode, readiness means all configured shards for that task are done. Final merge
at scheduler end remains in place as a second pass. Confidence: high.

Monitor update on 2026-06-03. Confidence: high.
`scripts/watch_multi_checkpoint_eval_progress.py` now parses standard eval tqdm
lines from each shard log and appends per-shard sample progress such as
`progress 58/79` for MATH, `progress 60/165` for GSM8k, and `progress
109/2384` for DROP. DFM tasks report HTTP completion counts from the local
OpenAI server logs. The monitor now also infers DFM shard totals from Inspect
`inspect/logs.json` when available and from known static totals for
`dfm_evals/ifeval-da` (`541` total) and `dfm_evals/piqa` (`108` total). After
the update, active lines showed `dfm_ifeval` as `completion 6/17`,
`humaneval` as `completion 15/41`, and `piqa` as `completion 16/108`.
The current eval batch-size defaults in `scripts/schedule_checkpoint_evals.sh`
are `STANDARD_BATCH_SIZE=8`, `DFM_BATCH_SIZE=8`, and `IFEVAL_BATCH_SIZE=1`.

DROP standard-eval slowness diagnosis, 2026-06-03. Confidence: high.
The active lite DROP shard is large because the EleutherAI DROP validation set
contains about `9536` examples after `lm_eval.tasks.drop.utils.process_docs`;
with the current `DROP` shard count of `4`, shard 0 has `2384` prompts. It is
also slow because each prompt is few-shot reading comprehension with long
passages, and `SimpleEngine.generate()` defaults `max_tokens` to
`max_context` when no explicit `max_tokens` is set. The active DROP log shows
it is running with `max_context: 3072`, `batch_size: 8`, and no explicit
`max_tokens`, so each short-answer DROP item can decode up to `3072` new
tokens. Confidence: high.

There is also a scheduler/config interaction to fix for future standard evals.
`evaluation/config/hrm_benchmarking.yaml` intends DROP to use
`generation_config.condition: direct`, but `scripts/schedule_checkpoint_evals.sh`
launches single-task shards by overriding Hydra/OmegaConf with
`benchmarks=[{name: TASK, num_shards: ..., shard_index: ...}]`. That replaces
the YAML benchmark entry and loses per-benchmark generation overrides. The
active DROP log confirms it used the global `condition: synth,cot` rather than
the intended `direct`. Confidence: high.

At `08:00 CEST`, active DROP shard 0 had processed `120 / 2384` samples in
`3067s`, or about `141 samples/hour`. A linear estimate from that point was
about `16.1h` remaining for that single shard, not multiple days. This is still
too slow for a lite probe. Future lite probes should either omit DROP, use a
much smaller DROP shard/sample cap, or run DROP with a short-answer
`max_tokens` cap and preserved `direct` condition. Confidence: high for the
measured rate; medium for the recommended cap until validated.

DROP and standard-eval config preservation fix, 2026-06-03. Confidence: high.
Full standard evals run DROP as four shards via `standard_shards_for_task()`,
so the full DROP validation set of about `9536` processed examples is split
into roughly `2384` prompts per shard. `scripts/schedule_checkpoint_evals.sh`
previously launched a single task by replacing the whole `benchmarks:` list with
a minimal one-entry list. That lost YAML per-benchmark generation config and
settings such as MMLU `special_shots`.

`evaluation/main.py` now supports `shard_overrides`, allowing the scheduler to
use `run_only=[TASK]` while preserving the original YAML benchmark entry. The
standard scheduler now launches standard shards with:

```bash
run_only=[DROP] \
shard_overrides.DROP.num_shards=4 \
shard_overrides.DROP.shard_index=0
```

`evaluation/config/hrm_benchmarking.yaml` now makes DROP short-answer behavior
explicit:

```yaml
- name: DROP
  generation_config:
    condition: "direct"
    max_tokens: 64
    stop: "\n\n"
```

Validation on 2026-06-03 passed with `python -m py_compile evaluation/main.py`,
`bash -n scripts/schedule_checkpoint_evals.sh`, and a config-only OmegaConf
check showing `run_only ['DROP']`, preserved DROP generation config
`condition=direct`, `max_tokens=64`, `stop="\n\n"`, and shard override
`num_shards=4`, `shard_index=0`. Confidence: high.

MATH/GSM8k standard-eval limits, 2026-06-03. Confidence: high.
MATH is intentionally a CoT eval in the standard HRM config, using the global
`condition: synth,cot` and `max_context: 3072`. Full MATH has `5000` examples
and is sharded into `64` shards, so shard 0 has `79` prompts. Active lite
timing showed shard 0 taking roughly one hour; the runtime comes from long CoT
generation, not from a huge shard count like DROP. To make the intended limit
explicit rather than relying on `SimpleEngine.generate()` defaulting
`max_tokens` to `max_context`, `evaluation/config/hrm_benchmarking.yaml` now
sets `max_tokens: 3072` for both `GSM8k` and `MATH`. A config-only check showed
future MATH/GSM8k launches resolve to `condition=synth,cot`,
`max_context=3072`, `max_tokens=3072`, and `batch_size=8` with the correct
shard override. Confidence: high.

Original-code comparison for MATH/GSM8k, 2026-06-03. Confidence: high.
The upstream/original `evaluation/config/hrm_benchmarking.yaml` used global
generation settings `batch_size: 33`, `max_context: 3072`, `temperature: 0.0`,
and `condition: "synth,cot"` for both `GSM8k` and `MATH`, with no explicit
`max_tokens`. The original `SimpleEngine.generate()` set `max_tokens =
max_context` when `max_tokens` was omitted, so the effective original
MATH/GSM8k output cap was `3072`. The local `max_tokens: 3072` entries are
therefore behavior-preserving for output length. Differences from the original
single-process config are operational: the scheduler shards MATH/GSM8k and
forces `generation_config.batch_size=8` for memory/scheduling stability rather
than using the config default `batch_size: 33`. Confidence: high.

IFEval port-collision fix, 2026-06-03. Confidence: high.
The shared multi-checkpoint scheduler launches one child
`scripts/schedule_checkpoint_evals.sh` per job/GPU. Inside those child
schedulers, `worker_id` is always `0`. The old IFEval port formula used
`PORT_BASE + 1000 + worker_id * 100 + shard`, so `step_50000` and
`step_100000` IFEval shard 0 both tried port `10500`. The `step_100000` server
failed to bind with `address already in use`, but the health check passed
against the already-running `step_50000` server. The `step_100000` client then
sent requests for model `hrm-dfm-L-ifeval-da-shard-0-step_100000` to the
`step_50000` server, producing HTTP 404 `Unknown model` entries that the
monitor counted as failed requests on the `step_50000` server.

`scripts/schedule_checkpoint_evals.sh` now derives DFM server ports from the
actual GPU id rather than the child worker id:

- normal DFM tasks: `PORT_BASE + gpu * 100 + random_offset`
- IFEval-DA: `PORT_BASE + 1000 + gpu * 100 + shard`
- judge server: `JUDGE_PORT + gpu`

The HRM `/health` wait now optionally checks that the health response reports
the expected model name, so a stale server on the requested port cannot satisfy
readiness for a different checkpoint/model. The doomed `step_100000` IFEval
child was stopped and relaunched manually on GPU6 with the patched script; the
replacement server used port `11100`. Confidence: high.

Superseded: Unsharded checkpoint compatibility check on 2026-06-02. Confidence: high.

The current eval/export path does not yet load `checkpoint_format=unsharded`
checkpoints. `evaluation/engines.py`, `scripts/hrm_openai_server.py`, and
`conversion/convert_to_hf.py` all go through `simple_inference_engine.py`.
That loader currently resolves latest checkpoints by scanning
`fsdp2_epoch_*`, checks for `fsdp2_{tag}` plus `carry_{tag}.0.pt`, and calls
`torch.distributed.checkpoint.load(...)` on `fsdp2_{tag}`. Therefore standard
evals and HF export currently require sharded `fsdp2_{tag}` checkpoints unless
`simple_inference_engine.py` is extended to detect/load `unsharded_{tag}.pt`.

Unsharded eval/export support update on 2026-06-02. Confidence: high.

`simple_inference_engine.py` now supports both checkpoint layouts:

- sharded: `fsdp2_{tag}` plus `carry_{tag}.0.pt`
- unsharded: `unsharded_{tag}.pt` plus `carry_{tag}.0.pt`

This shared loader is used by standard evals (`evaluation/engines.py`), the
OpenAI-compatible HRM server (`scripts/hrm_openai_server.py`), and HF export
(`conversion/convert_to_hf.py`), so those paths can now load unsharded
checkpoints. Latest-checkpoint auto-detection scans both `fsdp2_epoch_*` and
`unsharded_epoch_*.pt`; explicit tags may be passed as `epoch_1`,
`fsdp2_epoch_1`, `unsharded_epoch_1`, or `unsharded_epoch_1.pt`.

The generic eval scheduler `scripts/schedule_checkpoint_evals.sh` now also
accepts either `fsdp2_${CKPT_TAG}` or `unsharded_${CKPT_TAG}.pt` when waiting
for a checkpoint. It still requires `carry_${CKPT_TAG}.{0..7}.pt` because the
training code stores carry state rank-locally. Validation performed after the
change: `python -m py_compile simple_inference_engine.py
conversion/convert_to_hf.py evaluation/engines.py`, `bash -n
scripts/schedule_checkpoint_evals.sh`, `git diff --check`, and a toy
state-dict smoke test confirming that model weights and AdamATan2 EMA optimizer
state restore through the unsharded `set_state_dict` path.

Carry state with FSDP vs DDP, 2026-06-02. Confidence: high.

Carry is not managed by FSDP or DDP. It is explicit `TrainState.carry` owned by
each process. The model receives it on every forward pass and returns the next
carry via `train_state.carry, loss, metrics = model(...)`. Checkpointing saves
it separately as `carry_{tag}.{rank}.pt` on every rank and resume reloads the
file matching the current global rank. This is the same mechanism for FSDP and
DDP; only the model/optimizer checkpoint format differs.

For current L-size HRM runs using `baselines.hrm_nocarry_bp_warmup`,
`initial_carry(...)` returns `None`, so the carry files are effectively saved
`None` placeholders. For any future carryful model, resuming should preserve
the same world-size/rank mapping and physical local batch shape unless the carry
implementation is explicitly made reshapeable or reinitializable.

OLMo 3 optimizer/precision comparison, 2026-06-03. Confidence: high.

The local clone at `/tmp/OLMo-core` was inspected for the official OLMo 3
training scripts and optimizer initialization. Official OLMo 3 pretrain and
midtrain configs use `SkipStepAdamWConfig(...)` without passing an optimizer
`dtype` override, and configure data parallelism as HSDP/FSDP2 with
`param_dtype=DType.bfloat16` and `reduce_dtype=DType.float32`. Examples:
`src/scripts/official/OLMo3/OLMo-3-1025-7B-pretrain-1.py` and
`OLMo-3-1025-32B-pretrain.py`.

Superseded clarification: the initial note said OLMo 3 optimizer moments were
"not explicitly forced to fp32." The more precise reading of PyTorch FSDP2 is
that the optimizer parameters are fp32 in this setup. `SkipStepAdamW`
initializes `state["step"]` as `torch.float32`, while `state["exp_avg"]` and
`state["exp_avg_sq"]` are created with `torch.zeros_like(p, dtype=self.dtype)`.
Since the official OLMo 3 configs do not set `SkipStepAdamWConfig(dtype=...)`,
the Adam moment dtype follows the optimizer parameter tensor dtype at state
creation. OLMo-core applies FSDP2 before weight initialization and optimizer
construction; the model constructor default dtype is fp32, and PyTorch FSDP2
documents that `MixedPrecisionPolicy(param_dtype=bf16)` controls the unsharded
forward/backward parameter while "the optimizer step uses the sharded parameter
in the original dtype." Therefore, for the inspected OLMo 3 FSDP2 path, the
optimizer parameter dtype and Adam moments are fp32, forward/backward
materialization is bf16, gradient reduction is fp32, and step counters are fp32.

No EMA path was found in the official OLMo 3 scripts during this inspection.
This is relevant to HRM-Text because the DDP bf16-EMA issue here is specifically
an EMA shadow-weight precision problem, not simply an AdamW moment precision
question.

DDP parameter precision modes, 2026-06-03. Confidence: high.

`pretrain.py` now exposes `ddp_params_precision` for DDP-only precision
experiments. The default is `fp32`, which keeps persistent DDP parameters,
optimizer state, and EMA in fp32 while using CUDA autocast with `fwd_bwd_dtype`
for forward/backward compute. This mirrors the important precision property of
the FSDP2 path: low-precision compute without converting the optimizer-updated
weights to bf16. The FSDP path remains the default `distributed_strategy` and
was not changed by this option.

The second mode is `bf16`. In this mode DDP casts the model to `fwd_bwd_dtype`
before wrapping, so persistent parameters and Adam moments follow that
low-precision dtype, while `AdamATan2` is asked to store only `param_ema` in
fp32. A local optimizer smoke check with bf16 parameters confirmed `exp_avg`
and `exp_avg_sq` are bf16 while `param_ema` remains fp32 before and after an
optimizer step. This mode is intended to isolate whether the bad DDP checkpoints
were caused specifically by bf16 EMA, without paying the full memory cost of
fp32 DDP weights and optimizer state.

DDP fp32-EMA resume failure/fix, 2026-06-03. Confidence: high.

The first attempt to resume DFM4 XL-DDP from `checkpoints/dfm4/XL-ddp`
`step_150000` with `ddp_params_precision=bf16` and `reset_ema_on_resume=true`
failed before loading the checkpoint. PyTorch DCP raised
`ValueError: Unexpected value type <class 'torch.dtype'>` while traversing the
new optimizer state dict in `set_state_dict(...)`. The cause was the new
`AdamATan2(ema_dtype=torch.float32)` argument being stored directly in optimizer
param groups; DCP accepts tensor/primitive-like state-dict values but not raw
`torch.dtype` objects. `AdamATan2` now serializes `ema_dtype` as a string such
as `"float32"` in param groups and resolves it internally when allocating
`param_ema`. A local smoke check confirmed bf16 params, bf16 Adam moments, fp32
EMA, and a serialized optimizer param group with string `ema_dtype`.

DFM4 XL-DDP 150K lite eval scheduling, 2026-06-03. Confidence: high.

`step_150000` exists under `checkpoints/dfm4/XL-ddp` as an unsharded checkpoint
with all eight carry files. Its checkpoint metadata reports `step=150000`,
`epoch=1`, `batch_in_epoch=150000`, and `global_batch_size=196608`. Given
`data/sampled_dfm4` `total_length=72007089569`, the run has `366246` full
optimizer steps per epoch, so the lite eval x-axis value for this checkpoint is
`0.4095607870120083`.

A no-EMA lite eval for `step_150000` was queued in tmux window
`hrm-1:dfm4-150k-lite`. It is intentionally waiting for the active DFM4 XL-DDP
training process using all eight GPUs to exit before starting eval workers. The
queued scheduler uses:

```bash
CKPT_TAGS=step_150000 \
EVAL_EPOCHS=0.4095607870120083 \
CKPT_PATH=checkpoints/dfm4/XL-ddp \
GPUS=0,1,2,3,4,5,6,7 \
LITE_EVAL=1 \
LITE_SHARD_INDEX=0 \
QUEUE_ORDER=heavy_first \
NO_EMA=1 \
STANDARD_CONFIG=evaluation/config/hrm_benchmarking_lite.yaml \
STANDARD_BATCH_SIZE=16 \
DFM_BATCH_SIZE=16 \
IFEVAL_BATCH_SIZE=16 \
EVAL_PREFIX=lite_eval_noema \
DFM_EVAL_PREFIX=lite_dfm_eval_noema \
WANDB_PROJECT="Original Plus Mixed Danish Instruction Rich L" \
WANDB_RUN_ID=4chqwd3w \
WANDB_RUN_NAME=dfm4-XL-ddp \
LOG_ROOT_BASE=logs/eval/dfm4_XL_ddp_noema_lite_probe_20260603_150k \
DFM_LOG_ROOT_BASE=logs/dfm_evals/dfm4_XL_ddp_noema_lite_probe_20260603_150k \
bash scripts/schedule_multiple_checkpoint_evals.sh
```

DFM4 XL-DDP resume skip timeout, 2026-06-03. Confidence: high.

The attempt to resume DFM4 XL-DDP from `step_150000` with
`ddp_params_precision=bf16` and reset fp32 EMA failed after the checkpoint load
with a NCCL watchdog timeout. The stack traces showed ranks stuck in different
collective sequence numbers: several ranks timed out in
`_supervised_token_count()` at a one-scalar `all_reduce`, while rank 0 had a
later DDP `BROADCAST`. This is a distributed desync caused by the resume path
materializing and discarding `batch_in_epoch=150000` batches per rank:

```python
for batch_in_epoch, (batch, batch_info) in enumerate(train_loader, start=1):
    if skip_batches > 0 and batch_in_epoch <= skip_batches:
        continue
```

Because the `continue` happened after `DataLoader` yielded, every skipped batch
still loaded mmap slices, built tensors, computed PrefixLM aux tensors, and in
CUDA runs used the worker/datapipe machinery. Different ranks could therefore
finish the huge skip at different wall-clock times; ranks that entered the first
post-skip collective waited until NCCL's 600s timeout for slower ranks.

`dataset_new.py` now supports `V1Dataset.set_start_batch(start_batch)`.
`__iter__()` advances the deterministic multipack sampler to that batch index
before calling `_load_batch(...)`, so skipped batches are not materialized.
`pretrain.py` calls this on resume and starts the loop enumeration at
`skip_batches + 1`, preserving future `checkpoint_state_step_*.json`
`batch_in_epoch` values. Validation passed with
`python -m py_compile pretrain.py dataset_new.py models/adam_atan2.py`,
`git diff --check`, and a local temporary-dataset smoke test showing
`set_start_batch(1)` skips the only batch.

DFM4 XL-DDP resume trace instrumentation, 2026-06-03. Confidence: high.

After the optimized skip path still produced a first-step NCCL timeout, targeted
per-rank tracing was added behind `resume_trace`. This flag prints flushed
messages around resume load, EMA reset, carry load, dataset epoch/start-batch
setup, first dataloader yield, first batch device move, supervised-token
all-reduce begin/end, forward/backward begin/end, optimizer step begin/end,
metric reduction, and W&B logging. Default config keeps `resume_trace: false`.
Use `resume_trace=true` and preferably `log_interval=1` for the next diagnostic
resume from `step_150000`.

DFM4 XL-DDP unsharded resume collective mismatch, 2026-06-03. Confidence: high.

The traced `step_150000` DDP resume crash is specific to the unsharded resume
path, not to ordinary fresh training. Rank 0 times out inside
`torch.distributed.checkpoint.set_state_dict()` while running a DCP
`BROADCAST`, whereas ranks 1-7 have already left checkpoint restore and entered
the first training `_supervised_token_count()` `ALLREDUCE`. This mismatched
collective ordering causes the NCCL watchdog timeout. Fresh starts avoid this
because they do not call `load_unsharded_train_state()`. The likely fix is to
replace the DDP unsharded distributed DCP restore path with a DDP-safe loader,
for example all ranks loading the rank-0 unsharded checkpoint locally and then
using ordinary local model/optimizer `load_state_dict`, or saving future DDP
checkpoints in a per-rank/sharded format.

DFM4 XL-DDP all-ranks unsharded restore patch, 2026-06-03. Confidence: high.

`pretrain.py` now avoids the rank-0-only broadcast restore for
`distributed_strategy=ddp` and `checkpoint_format=unsharded`. In distributed DDP
jobs, every rank loads `unsharded_{tag}.pt` from CPU and then calls
`torch.distributed.checkpoint.set_state_dict()` with `full_state_dict=True`,
`cpu_offload=True`, and `broadcast_from_rank0=False`. This keeps the FQN-keyed
DCP optimizer state mapping while avoiding the bad collective ordering where
rank 0 was still broadcasting checkpoint tensors after other ranks had entered
training. Non-DDP distributed unsharded restores keep the previous rank-0
broadcast path. Validation passed with `python -m py_compile pretrain.py
dataset_new.py models/adam_atan2.py` and `git diff --check`.

DFM L all-checkpoint lite eval queue, 2026-06-03. Confidence: high.

A shared multi-checkpoint lite eval queue was launched for all local DFM L
checkpoints in `checkpoints/dfm/L`: `epoch_1`, `epoch_2`, `epoch_3`,
`epoch_4`, `step_500000`, `step_550000`, `step_600000`, and `step_650000`.
The epoch x-axis values are `1,2,3,4`; the step checkpoints use fractional
epoch values derived from checkpoint metadata as `3.03594610513`,
`3.339544966027`, `3.643143826924`, and `3.946742687821`. Results are targeted
at W&B project `Original Plus Mixed Danish Instruction Rich L`, run id
`dfm-l-resume-epoch3` / run name `dfm-L-resume-epoch3`.

```bash
CKPT_TAGS=epoch_1,epoch_2,epoch_3,epoch_4,step_500000,step_550000,step_600000,step_650000 \
EVAL_EPOCHS=1,2,3,4,3.03594610513,3.339544966027,3.643143826924,3.946742687821 \
CKPT_PATH=checkpoints/dfm/L \
GPUS=0,1,2,3,4,5,6,7 \
LITE_EVAL=1 \
QUEUE_ORDER=heavy_first \
MAX_RETRIES=3 \
WANDB_PROJECT="Original Plus Mixed Danish Instruction Rich L" \
WANDB_RUN_ID=dfm-l-resume-epoch3 \
WANDB_RUN_NAME=dfm-L-resume-epoch3 \
MODEL_PREFIX=hrm-dfm-L \
LOG_ROOT_BASE=logs/eval/dfm_L_lite_all_checkpoints_20260603T181543 \
DFM_LOG_ROOT_BASE=logs/dfm_evals/dfm_L_lite_all_checkpoints_20260603T181543 \
bash scripts/schedule_multiple_checkpoint_evals.sh
```

The scheduler started in tmux window `hrm-1:dfmL-lite`, queued `152` jobs for
the eight checkpoints, and initially started one job per GPU.

DFM L lite no-EMA prefix relog, 2026-06-03. Confidence: high.

The completed DFM L lite metrics from
`logs/eval/dfm_L_lite_all_checkpoints_20260603T181930` and
`logs/dfm_evals/dfm_L_lite_all_checkpoints_20260603T181930` were resynced to
W&B project `Original Plus Mixed Danish Instruction Rich L`, run id
`dfm-l-resume-epoch3`, under `lite_eval_noema/*` and
`lite_dfm_eval_noema/*`. This relog did not rerun inference; it read the stored
`merged_metrics.json` and `merged_ifeval_da_metrics.json` files. W&B reported
syncing history steps `132079-132094`. For each of the eight checkpoints
(`epoch_1`, `epoch_2`, `epoch_3`, `epoch_4`, `step_500000`, `step_550000`,
`step_600000`, `step_650000`), the relog wrote `195` `lite_eval_noema` metrics
and `74` `lite_dfm_eval_noema` metrics, preserving the stored fractional epoch
values for step checkpoints.

DFM4 XL-DDP step 200K lite eval queue, 2026-06-04. Confidence: high.

`checkpoints/dfm4/XL-ddp/step_200000` is complete as an unsharded DDP checkpoint:
`unsharded_step_200000.pt`, `checkpoint_state_step_200000.json`, and
`carry_step_200000.{0..7}.pt` exist. The checkpoint metadata reports
`epoch=1`, `batch_in_epoch=200000`, `global_batch_size=196608`, and
`data_path=data/sampled_dfm4`. With `data/sampled_dfm4/metadata.json`
`total_length=72,007,089,569`, there are `366246` full optimizer steps per
epoch, so the W&B x-axis value is `0.546081049349`.

The no-EMA lite eval was launched in tmux window `hrm-1:dfm4-200k-lite` with
status/progress in the second pane. It targets W&B project
`Original Plus Mixed Danish Instruction Rich L`, run id `4chqwd3w`, run name
`dfm4-XL-ddp`, and logs under `lite_eval_noema/*` and
`lite_dfm_eval_noema/*`.

```bash
CKPT_TAGS=step_200000 \
EVAL_EPOCHS=0.546081049349 \
CKPT_PATH=checkpoints/dfm4/XL-ddp \
GPUS=0,1,2,3,4,5,6,7 \
LITE_EVAL=1 \
QUEUE_ORDER=heavy_first \
MAX_RETRIES=3 \
NO_EMA=1 \
EVAL_PREFIX=lite_eval_noema \
DFM_EVAL_PREFIX=lite_dfm_eval_noema \
WANDB_PROJECT="Original Plus Mixed Danish Instruction Rich L" \
WANDB_RUN_ID=4chqwd3w \
WANDB_RUN_NAME=dfm4-XL-ddp \
MODEL_PREFIX=hrm-dfm4-XL-ddp \
LOG_ROOT_BASE=logs/eval/dfm4_XL_ddp_noema_lite_probe_20260604T035517_200k \
DFM_LOG_ROOT_BASE=logs/dfm_evals/dfm4_XL_ddp_noema_lite_probe_20260604T035517_200k \
bash scripts/schedule_multiple_checkpoint_evals.sh
```

Initial status queued `19` jobs for `step_200000` and started the first eight
jobs across GPUs 0-7.

DFM4 XL-DDP step 200K EMA smoke generation, 2026-06-04. Confidence: high.

The `step_200000` checkpoint was smoke-tested locally with the normal eval
loader and EMA enabled:

```bash
CUDA_VISIBLE_DEVICES=7 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python - <<'PY'
from evaluation.engines import SimpleEngine

prompts = [
    "Answer with only the letter. Which is larger? A. 3 B. 7",
    "Translate to Danish: The book is on the table.",
    "Solve the arithmetic problem and answer with only the number: 17 + 25 =",
    "Svar kort på dansk: Hvad er hovedstaden i Danmark?",
]

engine = SimpleEngine(
    ckpt_path="checkpoints/dfm4/XL-ddp",
    ckpt_tag="step_200000",
    ckpt_use_ema=True,
)
outputs = engine.generate(
    prompts,
    batch_size=2,
    max_context=512,
    max_tokens=96,
    temperature=0.0,
    condition="direct",
)
for prompt, output in zip(prompts, outputs):
    print(prompt, repr(output))
PY
```

The checkpoint loaded successfully and generated coherent text with EMA:
translation produced `Bogen er på bordet.`, arithmetic produced `42`, and the
Danish capital prompt produced `København`. The simple multiple-choice prompt
answered `A.` even though the correct option was `B`, so the result verifies
that EMA is no longer token-salad at 200K, but it is not evidence of benchmark
quality. This supersedes the earlier 50K/100K observation only for the 200K
checkpoint after the DDP EMA reset/resume changes.

DFM eval progress monitor totals, 2026-06-04. Confidence: high.

`scripts/watch_multi_checkpoint_eval_progress.py` now has known dataset totals
for DALA, GEC-DALA, and MultiWikiQA, so active dfm-evals jobs show
`completion x/y` instead of `completion x/?` for those tasks. Verified dataset
sizes are:

- `dfm_evals/dala`: `2048` samples for `giannor/dala`, split `test`.
- `dfm_evals/gec_dala`: `1024` samples for `giannor/dala_gen_v3`, split
  `test`.
- `dfm_evals/multi_wiki_qa`: `2048` samples for the default public
  MultiWikiQA test mini split; shard `0/2` therefore has `1024` samples.

The 200K EMA lite eval monitor snapshot after the patch showed DALA
`1506/2048`, GEC-DALA `212/512`, and MultiWikiQA `906/1024`.

DFM4 XL-DDP step 200K EMA vs no-EMA lite eval, 2026-06-04. Confidence: high.

The `step_200000` EMA lite eval completed locally with `WANDB_SYNC=0`, so it
did not sync to W&B. EMA logs are under
`logs/eval/dfm4_XL_ddp_ema_lite_probe_20260604T064428_200k` and
`logs/dfm_evals/dfm4_XL_ddp_ema_lite_probe_20260604T064428_200k`; no-EMA logs
are under `logs/eval/dfm4_XL_ddp_noema_lite_probe_20260604T035517_200k` and
`logs/dfm_evals/dfm4_XL_ddp_noema_lite_probe_20260604T035517_200k`. A local
comparison report was written to
`logs/eval/dfm4_XL_ddp_ema_vs_noema_200k.md`.

Headline aggregate metrics: EMA improved ARC, DROP, GSM8k, HellaSwag, MATH,
MMLU, Winogrande, Danish citizen tests, DALA, GEC-DALA, WMT24++ EN-DA,
MultiWikiQA, NordjyllandNews, and HumanEval in this lite slice. EMA regressed
BoolQ, PIQA, generative Talemaader, and GovReport. This is a lite one-shard
comparison only, not a full benchmark result.

DFM4 XL-DDP step 200K BoolQ/PIQA regression diagnosis, 2026-06-04.
Confidence: high for PIQA sample logs and BoolQ probe mechanics; medium for
generalizing the BoolQ probe to the full BoolQ run.

PIQA sample-level Inspect logs from the 200K lite eval show that the PIQA
regression is not a formatting/parser issue. No-EMA produced parseable `A`/`B`
answers for `107/108` samples and EMA also produced parseable `A`/`B` answers
for `107/108` samples. The regression is due to answer choice/content: no-EMA
had prediction distribution `A=23`, `B=84`, `<none>=1` on a target distribution
`A=95`, `B=13`; EMA shifted even harder to `B=102`, `A=5`, `<none>=1`. Paired
PIQA changes were `C->W=18`, `C->C=16`, `W->W=74`, and no `W->C`; the observed
loss is mostly no-EMA-correct `A` samples switching to EMA `B`.

BoolQ standard eval does not persist per-sample generations, so a deterministic
256-sample probe was run with the same benchmark class and generation settings
as the lite eval (`condition=direct`, `max_context=4096`, `max_tokens=1`,
`batch_size=1`). The probe wrote
`logs/eval/dfm4_XL_ddp_boolq_ema_vs_noema_200k_probe.json`. Both no-EMA and EMA
outputs were structurally valid on `256/256` samples. The target distribution
was `A=154`, `B=102`; no-EMA predicted `A=232`, `B=24` and scored `146/256`,
while EMA predicted `B=234`, `A=22` and scored `104/256`. Thus the BoolQ
regression is also an answer-prior/content shift rather than invalid output
format.

DFM4 XL-DDP 300K no-EMA lite W&B x-axis repair, 2026-06-04. Confidence: high.

The `step_300000` no-EMA lite eval for W&B run `4chqwd3w` in project
`Original Plus Mixed Danish Instruction Rich L` was initially logged with
`lite_eval_noema/epoch=300000` and `lite_dfm_eval_noema/epoch=300000`, which
made the Lite section plots autoscale to an unusable x-axis. W&B rewind was
tested through GraphQL but is not enabled for this account, and history rows are
append-only through the available API, so the bad original rows remain in the
run history.

The non-destructive repair is a clean parallel metric namespace:
`lite_eval_noema_epochfix/*` and `lite_dfm_eval_noema_epochfix/*`. Script
`scripts/backfill_dfm4_lite_noema_epochfix_wandb.py` reads the completed local
merged JSONs for DFM4 XL-DDP no-EMA lite checkpoints `step_50000`,
`step_100000`, `step_150000`, `step_200000`, `step_250000`, and `step_300000`,
rewrites the prefixes, and computes fractional epochs as
`step * 196608 / 72007089569`. Verified logged epoch values are:

- `step_50000`: `0.1365198907335385`
- `step_100000`: `0.273039781467077`
- `step_150000`: `0.4095596722006155`
- `step_200000`: `0.546079562934154`
- `step_250000`: `0.6825994536676925`
- `step_300000`: `0.819119344401231`

W&B API readback showed `lite_eval_noema_epochfix/epoch` at history steps
`300049..300054` and `lite_dfm_eval_noema_epochfix/epoch` at history steps
`300055..300060`, with the correct six fractional epoch values above. The
default workspace view `nw-nwuserpetersk-w` (`Peter-sk's workspace`) was updated
so its two auto Lite sections are named `lite_eval_noema_epochfix` and
`lite_dfm_eval_noema_epochfix`. Backup specs were written to
`logs/wandb_workspace_specs/20260604T201124Z_before_lite_epochfix_nw-nwuserpetersk-w.json`
and
`logs/wandb_workspace_specs/20260604T201124Z_after_lite_epochfix_nw-nwuserpetersk-w.json`.

Follow-up repair in the same turn. Confidence: high. The W&B UI still surfaced
the old `300000` x-axis through auto-generated Lite plots. The same default
workspace view was therefore changed from auto Lite sections to explicit
non-auto Lite sections: `Lite standard no-EMA epochfixed` with `9` standard
panels and `Lite DFM no-EMA epochfixed` with `14` DFM panels. Each panel uses
only `lite_eval_noema_epochfix/*` or `lite_dfm_eval_noema_epochfix/*` metrics,
with x-axis `lite_eval_noema_epochfix/epoch` or
`lite_dfm_eval_noema_epochfix/epoch`. API readback showed zero occurrences of
`lite_eval_noema/` and `lite_dfm_eval_noema/` in the live view spec. Backup
specs were written to
`logs/wandb_workspace_specs/20260604T201558Z_before_lite_explicit_epochfix_nw-nwuserpetersk-w.json`
and
`logs/wandb_workspace_specs/20260604T201558Z_after_lite_explicit_epochfix_nw-nwuserpetersk-w.json`.

Clean-run clone, 2026-06-04. Confidence: high. Because the user works in the
saved W&B `manual workspace` view (`nw=boh5wwabbfc7`) and the old append-only
history could still affect plots, a new clean W&B run was created instead of
continuing to mutate workspace panels. Script
`scripts/clone_wandb_run_without_bad_lite_300k.py` parses local
`wandb/run-*-4chqwd3w/run-4chqwd3w.wandb` datastores, skips one interrupted
datastore with invalid padding, deduplicates and coalesces history rows by
`_step`, omits rows where `lite_eval_noema/epoch` or
`lite_dfm_eval_noema/epoch` equals `300000`, and replays the rest into run
`dfm4xlddpclean` in project `Original Plus Mixed Danish Instruction Rich L`.

Dry-run and live replay both reported `38` omitted bad rows, `60,333`
deduplicated rows before coalescing, and `60,331` replayed coalesced rows. W&B
API verification of the new run showed:

- `lite_eval_noema/epoch` unique values:
  `0.1365202623373361`, `0.2730405246746722`, `0.4095607870120083`,
  `0.546081049349`, `0.6826013116866806`
- `lite_dfm_eval_noema/epoch` unique values: same five values above
- `lite_eval_noema_epochfix/epoch` unique values:
  `0.1365198907335385`, `0.273039781467077`, `0.4095596722006155`,
  `0.546079562934154`, `0.6825994536676925`, `0.819119344401231`
- `lite_dfm_eval_noema_epochfix/epoch` unique values: same six corrected
  epoch-fixed values above

The clean run URL is:
`https://wandb.ai/peter-sk-sdu/Original%20Plus%20Mixed%20Danish%20Instruction%20Rich%20L/runs/dfm4xlddpclean`.
The replay log is
`logs/wandb_clone_dfm4_xl_ddp_clean_lite_history_20260604.log`.

Follow-up 300K replacement in the clean run. Confidence: high. After creating
the clean run, the ordinary no-EMA lite prefixes intentionally stopped at 250K
because the original 300K ordinary-prefix rows were omitted. The completed 300K
eval shards were then re-merged and logged to `dfm4xlddpclean` under the
ordinary prefixes `lite_eval_noema/*` and `lite_dfm_eval_noema/*`, using
`EVAL_EPOCH=0.819119344401231`. Command log:
`logs/wandb_backfill_dfm4_clean_300k_usual_prefixes_20260604.log`.

W&B API readback after this backfill showed:

- `lite_eval_noema/epoch` unique values now include `0.819119344401231`, with
  the latest 300K rows at history steps `300061..300068`.
- `lite_dfm_eval_noema/epoch` unique values now include `0.819119344401231`,
  with latest 300K rows at history steps `300072..300079`.
- Example 300K ordinary-prefix values are
  `lite_eval_noema/MMLU/acc=0.3557` at history step `300063` and
  `lite_dfm_eval_noema/piqa/piqa_scorer/accuracy=0.1388888888888889` at
  history step `300075`.

DFM4 XL-DDP lite eval coverage, 2026-06-06. Confidence: high for local merged
artifacts and path naming; medium for older unlabelled `dfm4_XL_ddp_lite_probe`
being EMA because that follows scheduler defaults rather than an explicit path
marker.

Local merged eval artifacts show EMA lite evals for:

- `step_50000` and `step_100000` under `logs/eval/dfm4_XL_ddp_lite_probe` and
  `logs/dfm_evals/dfm4_XL_ddp_lite_probe`; these paths are unlabelled but the
  scheduler default is EMA unless `NO_EMA=1`.
- `step_200000` under
  `logs/eval/dfm4_XL_ddp_ema_lite_probe_20260604T064428_200k` and matching
  `logs/dfm_evals/...`.
- `step_250000` under
  `logs/eval/dfm4_XL_ddp_ema_lite_probe_20260604_250k` and matching
  `logs/dfm_evals/...`.

Explicit no-EMA lite eval artifacts exist for `step_50000`, `step_100000`,
`step_150000`, `step_200000`, `step_250000`, `step_300000`, `step_350000`,
`step_400000`, and `step_450000`.

Update, 2026-06-07. Confidence: high. For the current DFM4 XL-DDP run
(`checkpoints/dfm4/XL-ddp`), no local no-EMA lite-eval roots exist for
`step_500000` or `step_550000` as of this check. Local `step_500000` and
`step_550000` lite-eval directories found under
`logs/eval/dfm_L_lite_all_checkpoints_20260603T181930` belong to the older
DFM L run, not to DFM4 XL-DDP. The DFM4 XL-DDP `step_450000` no-EMA lite eval
is complete locally and merged under:

```text
logs/eval/dfm4_XL_ddp_noema_lite_450k_20260606_tmux
logs/dfm_evals/dfm4_XL_ddp_noema_lite_450k_20260606_tmux
```

Superseding launch update, 2026-06-07. Confidence: high for local command and
initial status. A no-EMA lite eval for the current DFM4 XL-DDP `step_500000`
and `step_550000` checkpoints was launched in tmux window
`dfm4_lite_eval:noema_500_550`, syncing to W&B run `dfm4xlddpclean` under
`lite_eval_noema/*` and `lite_dfm_eval_noema/*`. It uses three eval lanes
around the active training memory:

```text
GPUS=0,2,7
JUDGE_GPU=0
STANDARD_BATCH_SIZE=1
DFM_BATCH_SIZE=1
IFEVAL_BATCH_SIZE=1
```

The W&B epoch x-values are:

```text
step_500000 -> 1.3614815097196165
step_550000 -> 1.4976296606915782
```

Log roots:

```text
logs/eval/dfm4_XL_ddp_noema_lite_500k_550k_20260607_tmux
logs/dfm_evals/dfm4_XL_ddp_noema_lite_500k_550k_20260607_tmux
```

Initial status at launch:

```text
QUEUED 38 jobs for 2 checkpoints
START step_500000 dfm_ifeval 0 shard_0_of_32 gpu_0
START step_500000 standard MATH shard_0_of_64 gpu_2
START step_500000 standard GSM8k shard_0_of_8 gpu_7
```

Early check: `step_500000` GSM8k shard completed and merged at
`2026-06-07T15:03:40+02:00`; `MATH` and `IFEval-DA` were still running.

Completion update, 2026-06-07. Confidence: high. The DFM4 XL-DDP no-EMA lite
eval for `step_500000` and `step_550000` completed with final status:

```text
2026-06-07T19:45:45+02:00 FINAL_MERGE_END step_500000 status_0
2026-06-07T19:47:06+02:00 FINAL_MERGE_END step_550000 status_0
2026-06-07T19:47:06+02:00 DONE status_0
```

For both checkpoints, all standard lite tasks and all DFM-lite tasks were
merged locally and synced under `lite_eval_noema/*` and
`lite_dfm_eval_noema/*`. Sample counts matched the lite shard expectations:
MATH `79`, DROP `2384`, GSM8k `165`, MMLU `3511`, HellaSwag `5021`, ARC
`1172`, Winogrande `1267`, BoolQ `3270`, GovReport `61`, WMT24++ en-da `120`,
NordjyllandNews `125`, HumanEval `41`, GEC-DALA `512`, Multi-Wiki-QA `1024`,
Danish citizen tests `545`, DALA `2048`, PIQA `108`, and IFEval-DA `17`.

DFM4 XL-DDP `step_600000` no-EMA lite eval launch, 2026-06-08. Confidence:
high for local checkpoint state and launch status. The checkpoint exists as an
unsharded checkpoint with carry files, and `checkpoint_state_step_600000.json`
reports `step=600000`, `epoch=2`, `batch_in_epoch=232753`,
`global_batch_size=196608`, and `data_path=data/sampled_dfm4`.

The W&B epoch x-value uses the same epoch-1 boundary (`367247`) as the earlier
DFM4 XL-DDP lite points:

```text
step_600000 -> 1.6337778116635397
```

Launched in tmux window `dfm4_lite_eval:noema_600k`, syncing to W&B run
`dfm4xlddpclean` under `lite_eval_noema/*` and `lite_dfm_eval_noema/*`, with
the same conservative lanes used for the successful `500K/550K` run:

```text
LOG_ROOT_BASE=logs/eval/dfm4_XL_ddp_noema_lite_600k_20260608_tmux
DFM_LOG_ROOT_BASE=logs/dfm_evals/dfm4_XL_ddp_noema_lite_600k_20260608_tmux
CKPT_TAGS=step_600000
EVAL_EPOCHS=1.6337778116635397
GPUS=0,2,7
JUDGE_GPU=0
NO_EMA=1
STANDARD_BATCH_SIZE=1
DFM_BATCH_SIZE=1
IFEVAL_BATCH_SIZE=1
```

Initial status:

```text
QUEUED 19 jobs for 1 checkpoints
START step_600000 dfm_ifeval 0 shard_0_of_32 gpu_0
START step_600000 standard MATH shard_0_of_64 gpu_7
START step_600000 standard GSM8k shard_0_of_8 gpu_2
```

Extra-worker update, 2026-06-08. Confidence: high. GPU1 and GPU4 had enough
headroom to run additional batch-1 standard evals, so two workers were attached
to the existing shared queue with:

```text
RESUME_EXISTING_QUEUE=1
SKIP_FINAL_MERGE=1
GPUS=1,4
```

This preserved the existing `jobs.tsv` and left final merge to the original
scheduler. Initial extra-worker status:

```text
RESUME_QUEUED 15 jobs
START step_600000 standard MMLU shard_0_of_4 gpu_1
START step_600000 standard HellaSwag shard_0_of_2 gpu_4
```

Memory note: after loading these jobs, GPU1 had about `857 MiB` free and GPU4
only about `43 MiB` free. GPU4 is therefore useful but risky for large or
server-backed eval jobs while training is active.

Update, 2026-06-07. Confidence: high. The remaining no-EMA `step_450000`
standard tasks that had finished after the first final merge were manually
merged and synced to W&B run `dfm4xlddpclean` under `lite_eval_noema/*`:
`MMLU`, `ARC`, `HellaSwag`, `Winogrande`, and `MATH`. The local merged files
are under:

```text
logs/eval/dfm4_XL_ddp_noema_lite_450k_20260606_tmux/step_450000/standard_shards/*/merged_metrics.json
```

As of 2026-06-07 09:15 CEST, there are no local `step_450000` EMA lite-eval
artifacts and no active `step_450000` EMA eval processes. The active EMA eval
work at that time is for `step_400000`, not `step_450000`.

DFM4 XL-DDP `step_400000` EMA vs no-EMA partial comparison, 2026-06-07.
Confidence: high for standard eval log parsing and local no-EMA merged files;
medium for overall conclusion because EMA dfm-evals were still running/not
merged. On standard lite evals, EMA was better on `DROP`, `MMLU`, and
`HellaSwag`, and worse on `GSM8k`, `ARC`, `Winogrande`, `BoolQ`, and `MATH`.
The largest regression was `BoolQ` (`0.4498` EMA vs `0.6930` no-EMA). Standard
metric table:

```text
task        EMA       no-EMA    delta
GSM8k       0.1273    0.1515   -0.0242
DROP        0.2708    0.2667   +0.0041
MMLU        0.3845    0.3692   +0.0153
ARC         0.3148    0.3524   -0.0376
HellaSwag   0.3071    0.3037   +0.0034
Winogrande  0.4980    0.5233   -0.0253
BoolQ       0.4498    0.6930   -0.2432
MATH        0.1519    0.1772   -0.0253
```

EMA dfm-eval retry status, 2026-06-07. Confidence: high for local process logs,
telemetry, local merged JSON, and W&B sync logs. Three `step_400000` EMA dfm-evals OOMed and were manually
recorded in:

```text
logs/eval/dfm4_XL_ddp_ema_lite_400k_20260606_tmux/step_400000/eval_attempts.tsv
```

Recorded OOM attempts:

```text
IFEval-DA        batch 8, GPU0, free-before 16557 MiB, OOM
GovReport        batch 4, GPU2, free-before  8999 MiB, OOM
WMT24++ en-da    batch 4, GPU7, free-before  7399 MiB, OOM
GovReport        batch 2, GPU2, free-before  8999 MiB, OOM
WMT24++ en-da    batch 2, GPU7, free-before  7399 MiB, OOM
WMT24++ en-da    batch 2, GPU2, free-before  8999 MiB, OOM
```

Final successful retries:

```text
IFEval-DA        batch 4 on GPU0
GovReport        batch 2 on GPU0
WMT24++ en-da    batch 1 on GPU2
```

GovReport batch 2 succeeded on GPU0 because it had about `16.6 GiB` free above
training at launch. WMT24++ en-da was forced to batch 1 for the final pass after
batch 2 had failed on low-headroom GPUs; that retry completed at
`2026-06-07T12:47:40+02:00`. The three EMA DFM-lite shard outputs were merged
and synced to W&B run `dfm4xlddpclean` under `lite_dfm_eval_ema/*` at
`lite_dfm_eval_ema/epoch = 1.092162098698`:

```text
IFEval-DA        17 samples
GovReport        61 samples
WMT24++ en-da   120 samples
```

Merged outputs:

```text
logs/dfm_evals/dfm4_XL_ddp_ema_lite_400k_20260606_tmux/step_400000/merged_ifeval_da_metrics.json
logs/dfm_evals/dfm4_XL_ddp_ema_lite_400k_20260606_tmux/step_400000/govreport/merged_metrics.json
logs/dfm_evals/dfm4_XL_ddp_ema_lite_400k_20260606_tmux/step_400000/wmt24pp_en_da/merged_metrics.json
```

## 2026-06-06 Posttrain Synthetic Audit Plan

Confidence: high for local code paths and seed export counts; medium for final
quality impact until the first judged audit has been inspected.

Decision: when generating the remaining `550,000`
`posttrain_transform_refine` synthetic samples, do not blindly regenerate the
already usable `450,000` old samples. Instead:

1. Generate the remaining `550,000` rows with `--judge-quality` enabled.
2. Run a standalone judge audit over the existing `450,000` generated rows.
3. Always drop and regenerate any row for which the judge is unhappy. A whole
   slice may still be regenerated for efficiency if the audit shows many
   failures, but no judge-failed row should be kept.

The code now supports this as separate commands in
`scripts/prepare_posttrain_transform_refine.py`:

```bash
cd /work/dfm/HRM-Text
python scripts/prepare_posttrain_transform_refine.py export-seed-texts --force
python scripts/prepare_posttrain_transform_refine.py audit-generated \
  --generated-root data/generated_posttrain_transform_refine \
  --audit-root logs/posttrain_transform_refine_generation/audits \
  --base-url http://127.0.0.1:8100/v1 \
  --model posttrain-gemma-teacher \
  --concurrency 32
```

`audit-generated` reads accepted generated JSONL rows, reruns the local
heuristic validator, asks the OpenAI-compatible judge model for quality
judgment, writes per-record audit JSONL files, and writes
`summary.json` grouped by generated file. It does not mutate generated training
rows; downstream conversion/regeneration must treat every `judge_ok=false` row
as excluded.

Seed pools for future request generation were materialized locally:

```text
data/posttrain_transform_refine_seed_texts/en.jsonl: 1,119,746 rows, 1.7G
data/posttrain_transform_refine_seed_texts/da.jsonl:    99,538 rows, 187M
data/posttrain_transform_refine_seed_texts/manifest.json
```

The manifest records the exact source roots, seed value, and source traversal
limits used for the export. The English pool comes from ASSET plus
`data/converted_sources_dfm4_summarization`; the Danish pool comes from
`lexdk`, `danish_dynaword`, `laerebogen_with_followups`,
`synquid_wiki_instruct_da`, and selected Oliver Kinch Danish/BT converted
sources.

Follow-up launch, 2026-06-08. Confidence: high for local commands and observed
process state.

Added orchestration script:

```text
scripts/run_posttrain_transform_refine_to_1m_vllm.sh
```

It runs toward the `1,000,000` synthetic instruction target on all eight GPUs:

1. start one vLLM Gemma 4 31B IT server per GPU;
2. generate the pending `550,000` rows with `JUDGE_QUALITY=1`;
3. audit English-source generated rows (`en_en`, `en_da`) with one judge per
   GPU;
4. build regeneration requests for every row where the judge is unhappy;
5. generate judged replacements for those failures.

The script uses the fresh local teacher model:

```text
data/models/google/gemma-4-31B-it-fresh-20260604
```

The run was launched in tmux:

```bash
cd /work/dfm/HRM-Text
tmux attach -t posttrain_to_1m
```

At launch, all eight vLLM servers became ready on ports `8100..8107`, each GPU
allocated about `165,840 MiB`, and eight shard workers started processing the
missing queue. Initial queue state after worker start:

```text
data/synthetic_request_shards_posttrain_transform_refine_v3_missing/pending: 542
data/synthetic_request_shards_posttrain_transform_refine_v3_missing/running:   8
```

## 2026-06-10 Expert Dataset Export Package

Confidence: high for local file layout and validation commands.

Created a self-contained export package under:

```text
expert/
```

Superseded: the first export had `13` folders and copied internal Parquet/JSONL
files as hardlinked ordinary files. On 2026-06-10 it was rebuilt into the
standard post-training format below.

It now contains `12` upload-ready dataset subfolders. Each subfolder has:

- actual local data files under `data/*.jsonl.gz`;
- one JSON object per line with a chat-template-ready `messages` field:
  `{"messages":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}`;
- a `README.md` dataset card with provenance links and generation summary;
- a standalone `recreate_dataset.py` that does not import repo code or depend
  on another expert subfolder.

The top-level expert folders are:

```text
common-pile-denoising
common-pile-paragraph-reordering
common-pile-prefix-continuation
common-pile-span-filling
danish-dynaword-paragraph-reordering
danish-dynaword-denoising
danish-dynaword-prefix-continuation
danish-dynaword-span-filling
transformations-danish-danish
transformations-danish-english
transformations-english-danish
transformations-english-english
```

`govreport-summarization`, `wikicatsum-summarization`, and
`scientific-summaries-summarization` were removed because they were essentially
repackaged versions of existing HF datasets rather than locally distinctive
expert datasets. `arxiv-paper-summarization` was also removed because HF has
standard arXiv summarization datasets such as `ccdv/arxiv-summarization`, so
the local Common Pile arXiv-derived summarization export was too close to an
existing HF task.

Superseded internal variants were grouped by objective instead of exported as
separate top-level datasets. For example, DynaWord span filling includes all
six generated variants in one folder, and Common Pile span filling includes
all three generated variants in one folder. The DynaWord paragraph-reordering
export uses the later windowed version and does not include the earlier
superseded DynaWord paragraph tree. `common-pile-direct-continuation` was
removed on 2026-06-10 because direct continuation is not a post-training style
expert task.

The synthetic exports include only accepted examples. Rows with
`accepted != true` are dropped. Base generated rows whose `id` appears as a
regenerated `original_id` are also dropped; accepted regeneration rows are used
as replacements when available. The previous combined
`transformation-refinement-synthetic` folder was split into four source/target
language-pair folders:

```text
transformations-danish-danish:   208,117
transformations-danish-english:  211,401
transformations-english-danish:  246,288
transformations-english-english: 248,474
```

Together these contain `914,280` accepted chat rows.

Rows written by the 2026-06-10 rebuild:

```text
danish-dynaword-prefix-continuation:     3,268,392
danish-dynaword-denoising:               1,854,932
danish-dynaword-span-filling:            5,567,226
common-pile-prefix-continuation:        19,043,384
common-pile-denoising:                  19,043,379
common-pile-span-filling:               57,130,149
danish-dynaword-paragraph-reordering:      939,361
common-pile-paragraph-reordering:          277,029
transformations-danish-danish:             208,117
transformations-danish-english:            211,401
transformations-english-danish:            246,288
transformations-english-english:           248,474
```

Export sizes after rebuilding:

```text
common-pile-paragraph-reordering:          151M
transformations-english-english:           180M
transformations-danish-danish:             204M
transformations-english-danish:            217M
transformations-danish-english:            232M
danish-dynaword-paragraph-reordering:      434M
danish-dynaword-denoising:                 1.9G
danish-dynaword-prefix-continuation:       2.5G
danish-dynaword-span-filling:              5.0G
common-pile-prefix-continuation:           13G
common-pile-denoising:                     19G
common-pile-span-filling:                  49G
```

Validation performed:

```bash
find expert -type l | wc -l
find expert -type f \( -name '*.parquet' -o -name '*.jsonl' \) | head
find expert -type f -name '*.jsonl.gz' | wc -l
python -m py_compile scripts/build_expert_exports.py $(find expert -mindepth 2 -maxdepth 2 -name recreate_dataset.py | sort)
```

The symlink count was `0`; no raw `.parquet` or plain `.jsonl` files remained
under `expert/`; the compressed shard count was `4,187`; all recreation scripts
compiled successfully. A first-row smoke test for each dataset showed exactly
the top-level key `messages` with roles `user` and `assistant`.

## 2026-06-10 Reordering Expert Audit Plan

Confidence: high for local row counts and script syntax; medium for judge
quality until the first audit sample is reviewed. Prompt audit updated on
2026-06-11.

The transformation synthetic exports look comparatively strong, but the
paragraph-reordering exports need a judge quality pass because sampled rows can
include list/index/catalog-like fragments where "restore the original paragraph
order" is not a meaningful learnable task. A non-mutating judge audit script was
added:

```bash
python scripts/audit_reordering_datasets.py \
  --base-url http://127.0.0.1:8100/v1 \
  --model posttrain-gemma-teacher \
  --sample-rate 0.01 \
  --concurrency 8 \
  --audit-root logs/expert_reordering_audit/sample_1pct \
  --force
```

The script writes one audit JSONL row per judged example and a summary with
keep/drop counts. It asks the judge to keep only rows with coherent
paragraph-like passages, a meaningful/inferable order, non-catalog content, and
a response that restores the source content. Local row counts:

```text
expert/danish-dynaword-paragraph-reordering: 939,361 rows
expert/common-pile-paragraph-reordering:     277,029 rows
```

Prompt audit, 2026-06-11: the reordering judge prompt was tightened to reject
arbitrary order, alphabetical/name lists, catalog/index/table-of-contents
fragments, bibliography-like rows, metadata boilerplate, OCR corruption,
response omissions/additions, and rows that are not natural discourse ordering
examples. It now requests `primary_failure_type` for diagnostics.

## 2026-06-11 DBC Author/Article Audit Plan

Confidence: high for local schema inspection and script syntax; medium until
judge results are reviewed.

Added a non-mutating audit script for the DBC author/article converted datasets:

```bash
python scripts/audit_dbc_article_datasets.py \
  --base-url http://127.0.0.1:8100/v1 \
  --model posttrain-gemma-teacher \
  --sample-rate 0.1 \
  --concurrency 8 \
  --audit-root logs/dbc_article_audit/sample_10pct \
  --force
```

Default audited files:

```text
data/converted_sources/dbc/dbc-farfatterweb.parquet: 2,831 rows
data/converted_sources/dbc/dbc-faktalink.parquet:    5,991 rows
```

The judge prompt is dataset-aware: Forfatterweb rows must be plausible Danish
author-article sections matching the requested author/heading, while Faktalink
rows must be plausible Danish explanatory article sections matching the
requested topic/heading. The prompt rejects wrong-language, empty,
metadata-only, boilerplate, OCR-corrupted, unrelated, reference/URL-dump, and
too-fragmentary rows, but explicitly does not reject just because the judge
cannot externally verify every factual claim.

## 2026-06-11 Export Dataset Audit/Recreation Setup

Confidence: high for local script validation and file inspection; medium until
the full vLLM judge audit completes.

The first eight non-synthetic export datasets are not pre-audited:

```text
common-pile-denoising
common-pile-paragraph-reordering
common-pile-prefix-continuation
common-pile-span-filling
danish-dynaword-denoising
danish-dynaword-paragraph-reordering
danish-dynaword-prefix-continuation
danish-dynaword-span-filling
```

Each of these eight folders now has a self-contained `recreate_dataset.py` with
three roles:

1. recreate similar raw-text-derived rows from source Parquet;
2. audit the current folder's `data/*.jsonl.gz` rows with an OpenAI-compatible
   judge via `python recreate_dataset.py audit ...`;
3. create a filtered copy via `python recreate_dataset.py filter ...`.

No separate per-folder audit helper is required. Filtering keeps only
`keep=true` rows from the audit JSONL. Negatively judged rows, judge errors, and
unaudited rows are excluded, so final upload filtering should use a full audit,
not a sample audit.

The 8-GPU runner is:

```bash
SAMPLE_RATE=1.0 CONCURRENCY=8 bash scripts/run_export_audits_8gpu_vllm.sh
```

It starts one vLLM Gemma 4 31B IT judge server per GPU/dataset and writes
`audit_full/audit.jsonl` plus `audit_full/summary.json` inside each export
folder. The default model path is
`data/models/google/gemma-4-31B-it-fresh-20260604`, falling back to
`/work/dfm/brainsurgery/models/google/gemma-4-31B-it`.

Validation performed:

```bash
bash -n scripts/run_export_audits_8gpu_vllm.sh
python -m py_compile $(find export -maxdepth 2 -name recreate_dataset.py | sort) scripts/build_expert_exports.py scripts/audit_export_datasets.py
```

Both passed locally. `__pycache__` directories created by validation were
removed from `export/`.

## 2026-06-11 Transformation Export Self-Contained Assessment

Confidence: high for local file inspection.

Superseded by the update immediately below: the transformation folders now
include local seed files, generation configs, and accepted-selection summaries.

The four transformation export folders are:

```text
transformations-danish-danish
transformations-danish-english
transformations-english-danish
transformations-english-english
```

Each contains `README.md`, `data/*.jsonl.gz`, and a standalone
`recreate_dataset.py`, but the recreation script is only partially
self-contained in the reproducibility sense:

- It has no repo-code dependency and uses only Python standard-library modules.
- It requires an external seed-text JSONL passed via `--seed-texts`.
- It requires an OpenAI-compatible teacher endpoint via `--base-url` and
  `--model`.
- It currently generates fresh rows from seed texts; it does not reproduce the
  exact accepted-only split/export because the original accepted/regenerated
  audit provenance files are not embedded in each transformation folder.

Therefore the transformation folders are uploadable and self-contained as data
artifacts, but not exact-reproducible without external seed text, teacher model,
and judge/audit provenance. To make them fully reproducible before upload, add
the seed manifest and generation/audit configuration to each folder, or include
the accepted-audit provenance JSONL used to select the rows.

## 2026-06-11 Transformation Export Reproducibility Update

Confidence: high for local file inspection, script compilation, and row-count
scan.

The four transformation export folders under `export/` now carry practical
reproducibility metadata and seed material:

```text
export/transformations-danish-danish
export/transformations-danish-english
export/transformations-english-danish
export/transformations-english-english
```

Each folder contains:

- `data/*.jsonl.gz`: accepted-only chat `messages` rows.
- `seeds/source_texts.jsonl.gz`: the local source-text pool for that language
  side.
- `seeds/source_manifest.json`: the seed-pool manifest copied from
  `data/posttrain_transform_refine_seed_texts/manifest.json`.
- `generation_config.json`: source/target language, seed count, teacher-model
  family, task families, and selection policy.
- `accepted_selection_summary.json`: row count and accepted-only export rule.
- `recreate_dataset.py`: a standalone Python standard-library script that
  defaults to the local seed file and local language-pair config.

The shipped transformation data is accepted-only by construction:
`scripts/build_expert_exports.py` writes rows only when `accepted is True`,
drops base generated rows whose `id` appears as a regenerated `original_id`,
and includes accepted regeneration rows when present. The resulting exported
row counts are:

```text
transformations-danish-danish:   208,117
transformations-danish-english:  211,401
transformations-english-danish:  246,288
transformations-english-english: 248,474
```

Together these contain `914,280` accepted chat rows. The exported row schema is
uniform:

```json
{"messages":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}
```

The recreation scripts now judge generated candidates by default using the same
OpenAI-compatible endpoint/model unless `--no-judge` is explicitly passed. Only
judge-accepted rows are written in the default path. Exact byte-for-byte
recreation remains impossible in practice because teacher sampling, vLLM
scheduling, and judge decisions can vary; the scripts instead make seed
selection, task order, prompt templates, and local provenance reproducible.

The seed archives are ordinary files, not symbolic links. Locally, matching
language-pair folders share the same inode via hard links to avoid duplicate
disk use, but each uploaded folder still presents a normal
`seeds/source_texts.jsonl.gz` file.

## 2026-06-11 Export Audit Rebalance Plan

Confidence: high for local scripts and active tmux sessions; medium until the
first rebalance round completes.

The eight non-synthetic export audits are running in tmux session
`export_audits_8gpu`. The initial full-everything estimate was too long for
full audit of all rows with Gemma 4 31B, so the working target was changed to
`100M` accepted tokens per dataset. Average token estimates used by the
controller are:

```text
common-pile-denoising:                    398.1 tokens/accepted row
common-pile-paragraph-reordering:         818.3
common-pile-prefix-continuation:          207.5
common-pile-span-filling:                 397.8
danish-dynaword-denoising:               1898.4
danish-dynaword-paragraph-reordering:     916.5
danish-dynaword-prefix-continuation:      954.3
danish-dynaword-span-filling:            1845.7
```

The active rebalance watcher is tmux session `export_audit_rebalance_watch`:

```bash
cd /work/dfm/HRM-Text
python scripts/rebalance_export_audits.py watch \
  --target-tokens 100000000 \
  --interval-seconds 300 \
  --gpus 0,1,2,3,4,5,6,7
```

When at least one dataset reaches the target and at least one remains below
target, the watcher stops the current monolithic audit session and relaunches
only unfinished datasets as stable hash shards with `--skip-audit` pointing at
previous audit files. This avoids the unsafe pattern of killing one child
worker under `scripts/run_export_audits_8gpu_vllm.sh`, whose cleanup trap owns
all vLLM servers.

The older `export_audit_filter_watch` was stopped because it only filters
`audit_full`. After rebalance shards exist, final filtering should use all
audit roots:

```bash
cd /work/dfm/HRM-Text
python scripts/filter_all_export_audits.py
```

## 2026-06-12 Exact Epoch Checkpoint Steps For Relogging

Confidence: high for local sampler reconstruction and checkpoint-state file
inspection.

For W&B history cleanup/relogging, epoch evaluation rows should be logged at
the real training step where the checkpoint was saved, not at artificial
backfill-adjacent steps. Newer checkpoints have `checkpoint_state_*.json`;
older FSDP2 checkpoints were reconstructed by re-running the same
`MultipackDistributedBatchSampler` over each sampled epoch with the original
`global_batch_size` and world size.

Original Sapient L has no `checkpoint_state_*.json`. Reconstructed from
`data/sampled_original_sapient`, `global_batch_size=172032`, world size `8`,
and local `batch_max_length=21504`:

```text
epoch_1:  81478
epoch_2: 162961
epoch_3: 244443
epoch_4: 325928
```

This matches the W&B train history and checkpoint mtimes: train logging was
every five steps, so the last logged step was `325925` even though the
`epoch_4` checkpoint was saved after step `325928`.

Original Plus Mixed Danish Instruction Rich L also lacks checkpoint-state JSON.
Reconstructed from `data/sampled_original_plus_mixed_danish_instruction_rich`
with the same batch geometry:

```text
epoch_1: 161311
epoch_2: 322628
epoch_3: 483939
epoch_4: 645263
```

DFM L checkpoint-state JSON already records exact steps:

```text
epoch_1: 164670
epoch_2: 329380
epoch_3: 494080
epoch_4: 658771
```

DFM4 XL-DDP checkpoint-state JSON records:

```text
epoch_1: 367247
epoch_2: 734484
```

Use these steps when splitting full/lite EMA/no-EMA metrics into separate
clean runs under a new comparison project.

## 2026-06-12 HRM DFM Clean W&B Relog Project

Confidence: high for local script execution, W&B sync output, local run
summaries, and live manifest; medium for remote UI state until manually
inspected in the browser.

Created `scripts/relog_hrm_dfm_project.py` to relog local merged eval artifacts
into a new W&B project named `HRM DFM`. The script normalizes all source eval
prefixes (`eval`, `dfm_eval`, `lite_eval`, `lite_dfm_eval`, and EMA/no-EMA
variants) to `eval/*`, logs rows at the exact checkpoint training step via
W&B `_step`, and also logs `eval/train_step`, `eval/epoch`, and
`eval/checkpoint`.

Executed:

```bash
cd /work/dfm/HRM-Text
python scripts/relog_hrm_dfm_project.py \
  --manifest logs/wandb_relog_hrm_dfm_manifest_live_20260612.json \
  2>&1 | tee logs/wandb_relog_hrm_dfm_live_20260612.log
```

The project URL reported by W&B is:

```text
https://wandb.ai/peter-sk-sdu/HRM%20DFM
```

Created/synced run IDs:

```text
original-sapient-L-full-ema
original-sapient-L-lite-ema
original-sapient-L-lite-noema
original-plus-mixed-L-full-ema
original-plus-mixed-L-lite-ema
dfm-L-full-ema
dfm-L-lite-ema
dfm4-XL-ddp-full-ema
dfm4-XL-ddp-full-noema
dfm4-XL-ddp-lite-ema
dfm4-XL-ddp-lite-noema
```

Local W&B summaries confirm the last logged train steps:

```text
original-sapient-L-*:       325928
original-plus-mixed-L-*:    645263
dfm-L-*:                    658771
dfm4-XL-ddp-full-*:         734484
dfm4-XL-ddp-lite-*:         750000
```

Known caveats from the live manifest:

- `original-plus-mixed-L-full-ema` epoch 1 has only `3` recovered metrics
  from the local full-eval artifacts; epoch 2 has `202`, epoch 3 has `205`,
  and epoch 4 has `221`. The separate
  `original-plus-mixed-L-lite-ema` run has complete `269`-metric rows for all
  four epochs.
- `dfm4-XL-ddp-lite-noema` step `600000` has `221` metrics; the other logged
  DFM4 lite rows have `269`.

The live manifest is the audit source for exactly which checkpoints and metric
counts were relogged:

```text
logs/wandb_relog_hrm_dfm_manifest_live_20260612.json
```

## 2026-06-12 Export Audit Generation Status

Confidence: high for local status command output and live process inspection.

At `2026-06-12 14:16 +0200`, the accepted-token audit status for the
post-training export datasets was:

```text
common-pile-denoising:                   100.1M / 100.0M done
common-pile-prefix-continuation:          76.9M / 100.0M open
common-pile-span-filling:                 92.0M / 100.0M open
danish-dynaword-paragraph-reordering:     50.7M /  50.0M done
```

The manual GPU layout at that point was:

```text
GPU0: common-pile-span-filling shard 1/2
GPU1: common-pile-denoising shard 0/3
GPU2: common-pile-span-filling shard 0/2
GPU3: common-pile-prefix-continuation shard 0/1
GPU6: common-pile-denoising shard 1/3
GPU7: common-pile-denoising shard 2/3
```

`common-pile-denoising` had crossed the cap, but the three manual audit clients
were still live at inspection time. The user explicitly reserved GPUs 4 and 5
for another thread; this thread should not manage those processes.

Update at `2026-06-12 14:24 +0200`: the denoising audit clients on GPUs 1, 6,
and 7 were stopped after denoising reached `101.3M / 100.0M` accepted tokens.
`common-pile-span-filling` was restarted under tmux session
`export_span_gpus01267` as five shards using the partial prior span audits as
skip inputs:

```text
GPU0: common-pile-span-filling shard 0/5, port 8903
GPU1: common-pile-span-filling shard 1/5, port 8900
GPU2: common-pile-span-filling shard 2/5, port 8902
GPU6: common-pile-span-filling shard 3/5, port 8916
GPU7: common-pile-span-filling shard 4/5, port 8917
```

`common-pile-prefix-continuation` continued on GPU3.

Update at `2026-06-12 14:47 +0200`: after
`common-pile-span-filling` crossed the cap (`100.9M / 100.0M`), the five span
audit clients and the old single prefix client were stopped. Prefix was
restarted under tmux session `export_prefix_gpus012367` as six shards:

```text
GPU0: common-pile-prefix-continuation shard 0/6, port 8903
GPU1: common-pile-prefix-continuation shard 1/6, port 8900
GPU2: common-pile-prefix-continuation shard 2/6, port 8902
GPU3: common-pile-prefix-continuation shard 3/6, port 8901
GPU6: common-pile-prefix-continuation shard 4/6, port 8916
GPU7: common-pile-prefix-continuation shard 5/6, port 8917
```

The prefix aggregate was `78.2M / 100.0M` accepted tokens immediately after the
reassignment. GPUs 4 and 5 remained reserved for other work and were not
managed by this thread.

Final stop at `2026-06-12 18:05 +0200`: the six prefix audit clients were
stopped after `common-pile-prefix-continuation` reached
`128.6M / 100.0M` accepted tokens. The aggregate accepted-token total across
the eight audited export datasets was `778.6M`. The tmux launcher session
`export_prefix_gpus012367` had exited after the clients were killed.
## DFM5 XXS Runtime Observation

Last updated: 2026-06-13
Confidence: high
Scope: Active `dfm5-XXS` 8-GPU training run diagnostics.

The active DFM5 XXS command was observed running at about `22` optimizer
steps/s after compilation, or roughly `4.3M` tokens/s at
`global_batch_size=196,608`. `nvidia-smi dmon` showed B200 SM utilization
around `60-72%` with power draw about `450-480 W/GPU` and only `~8-10 GiB`
GPU memory used. `vmstat` showed no meaningful I/O wait and very low block
input, while `/proc/<pid>/io` for the data workers showed essentially no disk
`read_bytes` during the sample window. This does not look like classic
filesystem/data-loader starvation; it is more likely dominated by the tiny XXS
model size on B200s, per-rank Python/loader overhead, FSDP overhead relative to
the model, and pauses from frequent checkpointing/ephemeral checkpoint cleanup.

Possible future tests: compare FSDP vs DDP for XXS, reduce ephemeral checkpoint
frequency, and test larger per-rank token batches if changing the effective
batch size is acceptable.

## DFM5 XXS Step-50K Full Eval

Last updated: 2026-06-13
Confidence: high
Scope: Active full evaluation of `checkpoints/dfm5/XXS` checkpoint
`step_50000`.

The full standard + dfm-evals + EuroEval campaign for the DFM5 XXS 50K
checkpoint was launched in tmux session `dfm5_xxs_step50000_full_eval`.
It intentionally runs on the remaining GPU headroom while the 8-GPU XXS
training run continues.

W&B target:

```text
project: DFM5
run_id:  2tv9u438
run:     dfm5-XXS
```

The epoch x-axis value is the fractional epoch implied by the DFM5 sample size
and batch size:

```text
EVAL_EPOCH = 50000 / (35,605,979,095 / 196,608) = 0.276088
```

Launch command:

```bash
cd /work/dfm/HRM-Text
RUN_EUROEVAL=1 \
CKPT_PATH=checkpoints/dfm5/XXS \
CKPT_TAG=step_50000 \
EVAL_EPOCH=0.276088 \
GPUS=0,1,2,3,4,5,6,7 \
LOG_ROOT=logs/eval/dfm5_XXS_step50000_full_20260613 \
DFM_LOG_ROOT=logs/dfm_evals/dfm5_XXS_step50000_full_20260613 \
EUROEVAL_LOG_ROOT=logs/euroeval/dfm5_XXS_step50000_full_20260613 \
WANDB_PROJECT=DFM5 \
WANDB_RUN_ID=2tv9u438 \
WANDB_RUN_NAME=dfm5-XXS \
WANDB_SYNC=1 \
MODEL_PREFIX=hrm-dfm5-XXS \
QUEUE_ORDER=heavy_first \
MAX_RETRIES=3 \
STANDARD_BATCH_SIZE=16 \
DFM_BATCH_SIZE=16 \
IFEVAL_BATCH_SIZE=16 \
EUROEVAL_BATCH_SIZE=8 \
EUROEVAL_BIN=./scripts/euroeval_api_no_flash_attn_guard.py \
EUROEVAL_MAX_CONCURRENT_CALLS=20 \
STARTUP_STAGGER_SECONDS=5 \
scripts/schedule_checkpoint_evals.sh
```

Initial status at launch: `169` queued jobs. After about four minutes,
`12` IFEval-DA shards had completed successfully, `8` were active, and
telemetry showed no OOMs. The eval servers used only a few GiB of additional
GPU memory on top of the training process.

Update, 2026-06-13. Confidence: high. The first EuroEval retry was launched as
one monolithic EuroEval job on GPU0 because `scripts/schedule_checkpoint_evals.sh`
enqueues only a single `euroeval` job and `scripts/run_euroeval_on_checkpoint.sh`
runs one EuroEval client/server pair. That underused the available GPU
headroom. The single-GPU run was stopped and replaced with eight explicit
dataset groups, one per GPU, using `EUROEVAL_DATASETS`.

Default EuroEval `--language da --language en` resolves to these 20 datasets:

```text
angry-tweets, scala-da, dansk, multi-wiki-qa-da, nordjylland-news,
danske-talemaader, danish-citizen-tests, hellaswag-da, ifeval-da, valeu-da,
sst5, scala-en, conll-en, squad, cnn-dailymail, life-in-the-uk, hellaswag,
ifeval, bfcl-v2, valeu-en
```

Parallel groups launched under:

```text
logs/euroeval/dfm5_XXS_step50000_parallel_20260613/
```

Group map:

```text
GPU0: angry-tweets, scala-da, dansk
GPU1: multi-wiki-qa-da, nordjylland-news
GPU2: danske-talemaader, danish-citizen-tests, hellaswag-da
GPU3: ifeval-da, valeu-da
GPU4: sst5, scala-en, conll-en
GPU5: squad, cnn-dailymail
GPU6: life-in-the-uk, hellaswag, ifeval
GPU7: bfcl-v2, valeu-en
```

Each group uses a separate local HRM OpenAI server and syncs metrics directly
to W&B project `DFM5`, run id `2tv9u438`, at `EVAL_EPOCH=0.276088`. This
works, but the scheduler should be generalized later so EuroEval dataset
groups are first-class queued jobs rather than one monolithic job.

Update, 2026-06-13. Confidence: high. The completed EuroEval groups initially
failed during W&B merge with:

```text
RuntimeError: No numeric EuroEval metrics found in .../euroeval_benchmark_results.jsonl
```

The result files were valid. EuroEval 17.3.0 writes the current benchmark
schema under `evaluation_results` with `score_details.score`, while
`scripts/log_euroeval_to_wandb.py` only parsed the older flat `results` field.
The logger was patched to support both schemas, parse languages/dataset/task
from `eval_library.additional_details`, skip blank JSONL lines, and log score,
confidence interval, sample count, and failed-instance count under
`euroeval/{lang}/{task}/{dataset}/{metric}`.

Manual sync after the patch succeeded for completed groups:

```bash
cd /work/dfm/HRM-Text
for g in 2 4 7; do
  /home/ucloud/miniforge3/envs/hrm/bin/python scripts/log_euroeval_to_wandb.py \
    --results logs/euroeval/dfm5_XXS_step50000_parallel_20260613/gpu${g}/euroeval_benchmark_results.jsonl \
    --epoch 0.276088 \
    --output logs/euroeval/dfm5_XXS_step50000_parallel_20260613/gpu${g}/merged_metrics.json \
    --prefix euroeval \
    --language da \
    --language en \
    --log-wandb \
    --project DFM5 \
    --run-id 2tv9u438 \
    --run-name dfm5-XXS
done
```

The still-running groups will use the patched logger when their wrapper exits.

Update, 2026-06-13. Confidence: high. The DFM5 XXS step-50K full evaluation
campaign is synced to W&B run `2tv9u438` in project `DFM5`. Local status for
the eight EuroEval groups:

```text
GPU0 done json_objects=3 metrics=yes
GPU1 done json_objects=2 metrics=yes
GPU2 done json_objects=3 metrics=yes
GPU3 done json_objects=2 metrics=yes
GPU4 done json_objects=3 metrics=yes
GPU5 done json_objects=2 metrics=yes
GPU6 done json_objects=3 metrics=yes
GPU7 done json_objects=2 metrics=yes
```

The W&B summary API did not list eval keys, but a full remote history scan of
`peter-sk-sdu/DFM5/2tv9u438` found `382` keys starting with `eval/`,
`dfm_eval/`, or `euroeval/`, confirming that the sidecar eval logs reached the
remote run history. This matches previous W&B behavior where summary keys can
lag or omit sidecar-logged eval rows on an active training run.

A saved DFM5 workspace view was created for the 19 headline eval metrics plus
training/parameter panels:

```text
name: DFM5 headline metrics
url:  https://wandb.ai/peter-sk-sdu/DFM5?nw=2q3uq7mqioe
```

The view has four sections:

```text
Danish Headline Metrics:
  dfm_eval/dala/linguistic-acceptability/dfm_evals_macro_f1
  dfm_eval/danish-citizen-tests/knowledge/accuracy
  dfm_eval/gec_dala/exact_match/mean
  dfm_eval/generative-talemaader/model_graded_fact/accuracy
  dfm_eval/ifeval-da/instruction_following/final_acc
  dfm_eval/multi_wiki_qa/f1/mean
  dfm_eval/nordjyllandnews/rouge2/mean
  dfm_eval/piqa/piqa_scorer/accuracy
  dfm_eval/wmt24pp-en-da/chrf3pp/mean

English Headline Metrics:
  eval/ARC/acc
  eval/BoolQ/acc
  eval/DROP/f1
  eval/HellaSwag/acc
  eval/MMLU/acc
  eval/Winogrande/acc
  dfm_eval/govreport/rouge2/mean

Math & Code Headline Metrics:
  eval/GSM8k/acc
  eval/MATH/acc
  dfm_eval/humaneval/verify_sanitized/accuracy

Training Metrics & Params:
  train/loss
  train/accuracy
  train/exact_accuracy
  train/lr
  bp_steps
  scalar cards for config lr/global batch/epochs/layers
```

Standard eval panels use `eval/epoch`; DFM-eval panels use
`dfm_eval/epoch`; training panels use `_step`. Script and manifest:

```text
scripts/create_dfm5_headline_workspace.py
logs/wandb_workspace_specs/dfm5_headline_metrics.json
logs/wandb_create_dfm5_headline_workspace_20260613.log
```

Update, 2026-06-13. Confidence: high for local script execution and W&B sync
logs. The DFM5 headline workspace now includes derived section-average panels
at the top of Danish, English, and Math & Code. The averages are logged as
real W&B metrics rather than workspace-only expressions, because the source
metrics are split across `eval/*`, `dfm_eval/*`, and `euroeval/*` rows. Script:

```text
scripts/log_dfm5_headline_averages.py
```

Metric keys:

```text
headline_avg/epoch
headline_avg/train_step
headline_avg/danish
headline_avg/danish/count
headline_avg/english
headline_avg/english/count
headline_avg/math_code
headline_avg/math_code/count
headline_avg/overall
```

Values are unweighted arithmetic means of the section's headline metrics,
including EuroEval panels, after normalizing each metric to 0-1. Values already
in `[0, 1]` are kept; values in `(1, 100]` are divided by 100; negative values
are clamped to 0; non-finite or larger-than-100 values are skipped. The `count`
metrics record how many source metrics were present.

Superseded: the first backfill excluded EuroEval and produced:

```text
step_50000  epoch=0.276088            danish=0.076141 english=0.255659 math_code=0.016349 overall=0.116050
step_100000 epoch=0.5521769236437283  danish=0.082365 english=0.244336 math_code=0.022722 overall=0.116475
```

Superseded: the second backfill included EuroEval including VaLEU where
available. That made counts differ across checkpoints because VaLEU can abort
without writing a result record:

```text
step_50000  epoch=0.276088            danish=0.147101 count=19 english=0.191901 count=16 math_code=0.012262 count=4 overall=0.117088
step_100000 epoch=0.5521769236437283  danish=0.156194 count=18 english=0.230057 count=15 math_code=0.017042 count=4 overall=0.134431
```

The `step_100000` counts are lower than `step_50000` because the local
EuroEval merged files present at backfill time were missing one Danish and one
English primary EuroEval metric. Follow-up inspection showed the missing
metrics are `euroeval/da/european-values/valeu-da/european_values` and
`euroeval/en/european-values/valeu-en/european_values`. EuroEval did start
both VaLEU tasks, but aborted them because the model produced labels outside
the allowed candidate set and the task does not allow invalid outputs:

```text
ValEU-da: No candidate labels found ... 8/53 samples ... abort the evaluation.
VaLEU-en: No candidate labels found ... 3/53 samples ... abort the evaluation.
```

Because no VaLEU result records were written to
`euroeval_benchmark_results.jsonl`, the merged EuroEval metric files contain
only the other dataset from each group (`ifeval-da` for group 3 and `bfcl-v2`
for group 7). The headline-average script currently skips missing metrics
rather than treating aborted tasks as zero.

Current policy as of `2026-06-13`: VaLEU metrics are kept as workspace panels
but excluded from the section averages. This keeps average counts stable across
checkpoints while preserving the raw VaLEU panel for inspection.

The no-VaLEU average rows were synced to W&B project `DFM5`, run id
`2tv9u438`, by:

```bash
cd /work/dfm/HRM-Text
python scripts/log_dfm5_headline_averages.py \
  --item '50000:0.276088:logs/eval/dfm5_XXS_step50000_full_20260613:logs/dfm_evals/dfm5_XXS_step50000_full_20260613:logs/euroeval/dfm5_XXS_step50000_parallel_20260613' \
  --item '100000:0.5521769236437283:logs/eval/dfm5_XXS_100k_150k_full_20260613_100k_150k/step_100000:logs/dfm_evals/dfm5_XXS_100k_150k_full_20260613_100k_150k/step_100000:logs/euroeval/dfm5_XXS_100k_150k_full_20260613_100k_150k/step_100000' \
  --item '150000:0.8282653854655924:logs/eval/dfm5_XXS_step150000_full_highbs_20260613_step150_highbs/step_150000:logs/dfm_evals/dfm5_XXS_step150000_full_highbs_20260613_step150_highbs/step_150000:logs/euroeval/dfm5_XXS_step150000_full_highbs_20260613_step150_highbs/step_150000'
```

The synced no-VaLEU values are:

```text
step_50000  epoch=0.276088            danish=0.153509 count=18 english=0.203071 count=15 math_code=0.012262 count=4 overall=0.122947
step_100000 epoch=0.5521769236437283  danish=0.156194 count=18 english=0.230057 count=15 math_code=0.017042 count=4 overall=0.134431
step_150000 epoch=0.8282653854655924  danish=0.179091 count=18 english=0.220028 count=15 math_code=0.012290 count=4 overall=0.137136
```

W&B client output confirmed upload and summary update for
`headline_avg/{danish,english,math_code,overall}`. A W&B API `scan_history`
probe was too slow and was terminated; the sync log is
`logs/wandb_log_dfm5_headline_averages_no_valeu_50k_100k_150k_20260613.log`.
```

The saved workspace URL after adding the average panels is:

```text
https://wandb.ai/peter-sk-sdu/DFM5?nw=ggywzrf0fxl
```

Update, 2026-06-13. Confidence: high. `scripts/schedule_multiple_checkpoint_evals.sh`
supports opportunistic multi-checkpoint scheduling: one shared `jobs.tsv` is
consumed by one worker per GPU, and each worker pops the next checkpoint job
whose checkpoint files are ready. This lets checkpoint N+1 start on free GPUs
while long-running shards for checkpoint N are still active. Standard and
DFM-eval tasks already used this pattern.

The script now also supports grouped EuroEval jobs with
`EUROEVAL_DATASET_GROUPS`. When set, each semicolon-separated dataset group is
queued as a separate `euroeval` job instead of one monolithic EuroEval job.
This matches the DFM5 step-50K manual split and prevents one GPU from owning
all EuroEval work.

Dry-run verification:

```bash
cd /work/dfm/HRM-Text
CKPT_TAGS=step_a,step_b \
EVAL_EPOCHS=0.1,0.2 \
CKPT_PATH=checkpoints/dfm5/XXS \
LOG_ROOT_BASE=logs/eval/dryrun_multi_ckpt_opportunistic2 \
DFM_LOG_ROOT_BASE=logs/dfm_evals/dryrun_multi_ckpt_opportunistic2 \
EUROEVAL_LOG_ROOT_BASE=logs/euroeval/dryrun_multi_ckpt_opportunistic2 \
RUN_EUROEVAL=1 \
LITE_EVAL=1 \
WANDB_PROJECT=DFM5 \
WANDB_RUN_ID=2tv9u438 \
WANDB_RUN_NAME=dfm5-XXS \
EUROEVAL_DATASET_GROUPS='angry-tweets,scala-da,dansk;multi-wiki-qa-da,nordjylland-news;danske-talemaader,danish-citizen-tests,hellaswag-da;ifeval-da,valeu-da;sst5,scala-en,conll-en;squad,cnn-dailymail;life-in-the-uk,hellaswag,ifeval;bfcl-v2,valeu-en' \
DRY_RUN=1 \
scripts/schedule_multiple_checkpoint_evals.sh
```

The dry run queued `54` jobs for two lite checkpoints, including eight
EuroEval dataset-group jobs per checkpoint. `bash -n` passed for both
`scripts/schedule_multiple_checkpoint_evals.sh` and
`scripts/schedule_checkpoint_evals.sh`.

Update, 2026-06-13. Confidence: high. For future multi-checkpoint scheduler
runs, EuroEval defaults to one dataset per queue job when all of the following
are true: `RUN_EUROEVAL=1`, `EUROEVAL_LANGUAGES=da,en`,
`EUROEVAL_DATASET_GROUPS` is unset, `EUROEVAL_DATASETS` is unset, and
`EUROEVAL_TASKS` is unset. Explicit dataset groups, dataset lists, or task
lists still override this default. A dry run verified 20 EuroEval jobs for one
checkpoint:

```text
angry-tweets
scala-da
dansk
multi-wiki-qa-da
nordjylland-news
danske-talemaader
danish-citizen-tests
hellaswag-da
ifeval-da
valeu-da
sst5
scala-en
conll-en
squad
cnn-dailymail
life-in-the-uk
hellaswag
ifeval
bfcl-v2
valeu-en
```

Update, 2026-06-13. Confidence: high. Full standard, DFM, and EuroEval evals
were launched for DFM5 XXS checkpoints `step_100000` and `step_150000` in tmux
session `dfm5_xxs_eval_100k_150k`. Both checkpoints had
`fsdp2_step_*` metadata and all eight carry files before launch. Epoch-axis
values were computed from `total_length=35,605,979,095` and
`global_batch_size=196,608`:

```text
step_100000 -> 0.5521769236437283
step_150000 -> 0.8282653854655924
```

Launch command:

```bash
cd /work/dfm/HRM-Text
ROOT_TS=20260613_100k_150k
tmux new-session -d -s dfm5_xxs_eval_100k_150k \
  "cd /work/dfm/HRM-Text && \
   CKPT_TAGS=step_100000,step_150000 \
   EVAL_EPOCHS=0.5521769236437283,0.8282653854655924 \
   CKPT_PATH=checkpoints/dfm5/XXS \
   GPUS=0,1,2,3,4,5,6,7 \
   LOG_ROOT_BASE=logs/eval/dfm5_XXS_100k_150k_full_${ROOT_TS} \
   DFM_LOG_ROOT_BASE=logs/dfm_evals/dfm5_XXS_100k_150k_full_${ROOT_TS} \
   EUROEVAL_LOG_ROOT_BASE=logs/euroeval/dfm5_XXS_100k_150k_full_${ROOT_TS} \
   RUN_EUROEVAL=1 \
   LITE_EVAL=0 \
   QUEUE_ORDER=heavy_first \
   MAX_RETRIES=3 \
   WANDB_SYNC=1 \
   WANDB_PROJECT=DFM5 \
   WANDB_RUN_ID=2tv9u438 \
   WANDB_RUN_NAME=dfm5-XXS \
   MODEL_PREFIX=hrm-dfm5-XXS \
   STANDARD_BATCH_SIZE=16 \
   DFM_BATCH_SIZE=16 \
   IFEVAL_BATCH_SIZE=16 \
   EUROEVAL_BATCH_SIZE=8 \
   EUROEVAL_BATCH_TIMEOUT_MS=25 \
   EUROEVAL_BIN=/work/dfm/HRM-Text/scripts/euroeval_api_no_flash_attn_guard.py \
   EUROEVAL_DATASET_GROUPS='angry-tweets,scala-da,dansk;multi-wiki-qa-da,nordjylland-news;danske-talemaader,danish-citizen-tests,hellaswag-da;ifeval-da,valeu-da;sst5,scala-en,conll-en;squad,cnn-dailymail;life-in-the-uk,hellaswag,ifeval;bfcl-v2,valeu-en' \
   scripts/schedule_multiple_checkpoint_evals.sh 2>&1 | \
   tee logs/dfm5_xxs_eval_100k_150k_${ROOT_TS}.log"
```

Initial status:

```text
QUEUED 352 jobs for 2 checkpoints
WORKERS 2473337 2473338 2473339 2473340 2473341 2473342 2473343 2473344
```

The first eight jobs were IFEval-DA shards for `step_100000`, one per GPU.
Server logs under
`logs/dfm_evals/dfm5_XXS_100k_150k_full_20260613_100k_150k/step_100000/ifeval_shard_*/step_100000/server.log`
showed live generation progress, and `nvidia-smi` showed 100% GPU utilization
on all eight devices shortly after launch.

Update, 2026-06-14. Confidence: high. The DFM5 XXS `step_250000` and
`step_300000` full standard + DFM + EuroEval campaign completed and synced
headline averages to W&B project `DFM5`, run id `2tv9u438`.

Checkpoint epoch-axis values:

```text
step_250000 -> 1.3804423091093208
step_300000 -> 1.6565307709311847
```

Launch wrapper:

```bash
cd /work/dfm/HRM-Text
ROOT_TS=20260613_step250_300_highbs
cat > /tmp/dfm5_step250_300_highbs_run_and_avg.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail
cd /work/dfm/HRM-Text
ROOT_TS=20260613_step250_300_highbs
CKPT_TAGS=step_250000,step_300000 \
EVAL_EPOCHS=1.3804423091093208,1.6565307709311847 \
CKPT_PATH=checkpoints/dfm5/XXS \
GPUS=0,1,2,3,4,5,6,7 \
LOG_ROOT_BASE=logs/eval/dfm5_XXS_step250_300_full_highbs_${ROOT_TS} \
DFM_LOG_ROOT_BASE=logs/dfm_evals/dfm5_XXS_step250_300_full_highbs_${ROOT_TS} \
EUROEVAL_LOG_ROOT_BASE=logs/euroeval/dfm5_XXS_step250_300_full_highbs_${ROOT_TS} \
RUN_EUROEVAL=1 \
LITE_EVAL=0 \
QUEUE_ORDER=heavy_first \
MAX_RETRIES=5 \
WANDB_SYNC=1 \
WANDB_PROJECT=DFM5 \
WANDB_RUN_ID=2tv9u438 \
WANDB_RUN_NAME=dfm5-XXS \
MODEL_PREFIX=hrm-dfm5-XXS \
STANDARD_BATCH_SIZE=128 \
STANDARD_BATCH_SIZE_GSM8K=64 \
STANDARD_BATCH_SIZE_MATH=64 \
STANDARD_BATCH_SIZE_DROP=32 \
DFM_BATCH_SIZE=32 \
DFM_BATCH_SIZE_GOVREPORT=32 \
DFM_BATCH_SIZE_NORDJYLLANDNEWS=32 \
DFM_BATCH_SIZE_WMT24PP_EN_DA=32 \
DFM_BATCH_SIZE_HUMANEVAL=16 \
DFM_BATCH_SIZE_GENERATIVE_TALEMAADER=16 \
IFEVAL_BATCH_SIZE=32 \
EUROEVAL_BATCH_SIZE=16 \
EUROEVAL_BATCH_TIMEOUT_MS=25 \
EUROEVAL_BIN=/work/dfm/HRM-Text/scripts/euroeval_api_no_flash_attn_guard.py \
scripts/schedule_multiple_checkpoint_evals.sh 2>&1 | tee logs/dfm5_xxs_eval_step250_300_highbs_${ROOT_TS}.log
python scripts/log_dfm5_headline_averages.py \
  --item '250000:1.3804423091093208:logs/eval/dfm5_XXS_step250_300_full_highbs_20260613_step250_300_highbs/step_250000:logs/dfm_evals/dfm5_XXS_step250_300_full_highbs_20260613_step250_300_highbs/step_250000:logs/euroeval/dfm5_XXS_step250_300_full_highbs_20260613_step250_300_highbs/step_250000' \
  --item '300000:1.6565307709311847:logs/eval/dfm5_XXS_step250_300_full_highbs_20260613_step250_300_highbs/step_300000:logs/dfm_evals/dfm5_XXS_step250_300_full_highbs_20260613_step250_300_highbs/step_300000:logs/euroeval/dfm5_XXS_step250_300_full_highbs_20260613_step250_300_highbs/step_300000' \
  2>&1 | tee logs/wandb_log_dfm5_headline_averages_no_valeu_250k_300k_20260613.log
SH
chmod +x /tmp/dfm5_step250_300_highbs_run_and_avg.sh
tmux new-session -d -s dfm5_xxs_eval_250k_300k_highbs /tmp/dfm5_step250_300_highbs_run_and_avg.sh
```

Completion evidence:

```text
2026-06-14T00:45:20+02:00 FINAL_MERGE_START step_250000
2026-06-14T00:46:36+02:00 FINAL_MERGE_END step_250000 status_0
2026-06-14T00:46:36+02:00 FINAL_MERGE_START step_300000
2026-06-14T00:47:51+02:00 FINAL_MERGE_END step_300000 status_0
2026-06-14T00:47:51+02:00 DONE status_0
```

No nonzero `END` statuses were found in the scheduler status file. The W&B
client confirmed sync to `https://wandb.ai/peter-sk-sdu/DFM5/runs/2tv9u438`.

Current no-VaLEU headline-average series:

```text
step_50000  epoch=0.276088            danish=0.153509 english=0.203071 math_code=0.012262 overall=0.122947
step_100000 epoch=0.5521769236437283  danish=0.156194 english=0.230057 math_code=0.017042 overall=0.134431
step_150000 epoch=0.8282653854655924  danish=0.179091 english=0.220028 math_code=0.012290 overall=0.137136
step_200000 epoch=1.1043538472874566  danish=0.148592 english=0.237147 math_code=0.010827 overall=0.132189
step_250000 epoch=1.3804423091093208  danish=0.188638 english=0.225618 math_code=0.013740 overall=0.142665
step_300000 epoch=1.6565307709311847  danish=0.159041 english=0.232286 math_code=0.014552 overall=0.135293
```

Interpretation as of 300K: this is not yet strong evidence of a pure XXS
capacity ceiling. English and Math/Code are mostly flat/noisy and Math/Code is
near zero, which is consistent with an XXS-capacity and/or training-objective
limit. Danish has clear upward spikes at 150K and 250K but regresses at 200K
and 300K, so the trend still looks noisy rather than converged. More evidence
from later checkpoints is needed before calling a hard capacity wall, but the
current results suggest XXS is already too small for robust math/code and
general English benchmark gains.

Update, 2026-06-14. Confidence: high for inspected config fields; medium until
the command is run. A comparable DDP variant of the DFM5 XXS training command
should keep the same data, architecture, LR, global batch, epoch count, and
checkpoint cadence, but switch to `distributed_strategy=ddp`, use
`checkpoint_format=unsharded`, and write to a separate checkpoint directory.
For precision comparability with the FSDP2 path, use
`ddp_params_precision=fp32` with `fwd_bwd_dtype=bfloat16`; the alternative
`ddp_params_precision=bf16` is lower-memory/higher-throughput but changes
persistent parameter precision.

```bash
cd /work/dfm/HRM-Text
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
torchrun --nproc_per_node=8 pretrain.py \
  data=dfm5 \
  arch/size@arch=XXS \
  lr=2.5e-4 \
  global_batch_size=196608 \
  gradient_accumulation_steps=1 \
  epochs=5 \
  distributed_strategy=ddp \
  ddp_params_precision=fp32 \
  ddp_find_unused_parameters=true \
  checkpoint_format=unsharded \
  fwd_bwd_dtype=bfloat16 \
  accelerator_type=sm100 \
  checkpoint_interval=1 \
  checkpoint_step_interval=10000 \
  ephemeral_checkpoint_step_interval=1000 \
  checkpoint_path=checkpoints/dfm5/XXS-ddp \
  project_name="DFM5" \
  run_name=dfm5-XXS-ddp
```

Initialization determinism note, 2026-06-14. Confidence: high for inspected
code and local Python signatures; medium for the FSDP2 global-initialization
equivalence implication. `pretrain.py` seeds once before model construction:

```python
torch.random.manual_seed(config.seed + RANK)
```

The model uses PyTorch RNG-consuming initializers such as
`trunc_normal_init_(tensor.normal_())` in `models/common.py`, `LinearInit`,
`ScaledEmbeddingInit`, and `zL_init`. Therefore initialization is deterministic
for a fixed command, seed, world size, rank mapping, PyTorch/CUDA stack, and
model construction order. It is not guaranteed to be bit-identical if world
size or distributed strategy changes.

DDP wraps the model with PyTorch `DistributedDataParallel(..., init_sync=True)`
by default, so DDP should broadcast rank-0 initialized parameters and buffers
to all ranks at construction. In contrast, the current FSDP2 call path uses
`fully_shard(...)`, whose inspected signature has no `sync_module_states`
argument, and the code only explicitly broadcasts buffers before sharding.
That means the current FSDP2 global initial parameter tensor may be assembled
from rank-local initializations seeded with `seed + RANK`, while DDP starts
from rank 0's initialization. Both are deterministic, but they are not
necessarily the same initial model.

FSDP parameter dtype clarification, 2026-06-14. Confidence: high for inspected
code and local PyTorch `MixedPrecisionPolicy` docstring. In the current FSDP
path, `fwd_bwd_dtype=bfloat16` is passed as `MixedPrecisionPolicy.param_dtype`.
This controls the unsharded/all-gathered parameter dtype used for
forward/backward computation. It does **not** mean the optimizer/master
sharded parameters are bf16. PyTorch's local docstring says FSDP keeps
high-precision sharded parameters in memory and the optimizer step uses the
sharded parameter in the original dtype. Since HRM model parameters are
constructed without a bf16 default dtype override, the original trainable
parameter dtype is fp32. Therefore current FSDP training uses fp32 sharded
weights/optimizer parameters with bf16 compute parameters. This is conceptually
closest to DDP with `ddp_params_precision=fp32` plus bf16 autocast, not DDP
with persistent bf16 parameters.

Update, 2026-06-14. Confidence: high. `pretrain.py` and
`config/cfg_pretrain.yaml` now expose `fsdp_params_precision` with values
`fp32` and `bf16`. The default is `fp32`, preserving the previous FSDP
behavior: fp32 persistent sharded parameters/optimizer state with bf16
FSDP compute materialization when `fwd_bwd_dtype=bfloat16`.

When `fsdp_params_precision=bf16`, the model is cast to bf16 before FSDP
wrapping and optimizer construction, so the original/persistent FSDP sharded
parameters and Adam moments are bf16. To avoid repeating the DDP bf16 EMA
precision issue, the optimizer EMA shadow weights are kept in fp32 for this
mode.

Validation performed:

```bash
cd /work/dfm/HRM-Text
python -m py_compile pretrain.py
python - <<'PY'
from hydra import initialize, compose
from omegaconf import OmegaConf
from pretrain import PretrainConfig
with initialize(version_base=None, config_path='config'):
    cfg = compose(config_name='cfg_pretrain', overrides=[
        'data=dfm5',
        'arch/size@arch=XXS',
        'distributed_strategy=fsdp',
        'fsdp_params_precision=bf16',
        'fwd_bwd_dtype=bfloat16',
    ])
parsed = PretrainConfig(**OmegaConf.to_container(cfg, resolve=True))
print(parsed.distributed_strategy, parsed.fsdp_params_precision, parsed.fwd_bwd_dtype)
PY
```

The compose check printed:

```text
fsdp bf16 bfloat16
```

Early DFM5 XXS FSDP-vs-DDP training comparison, 2026-06-14. Confidence:
high for W&B API history values; medium for interpretation because the DDP run
was started from step 0 rather than from a converted FSDP checkpoint, so
initialization differs.

Runs compared:

```text
FSDP: project DFM5, run_id 2tv9u438, run_name dfm5-XXS, checkpoint_path checkpoints/dfm5/XXS
DDP:  project DFM5, run_id pqc9g81u, run_name dfm5-XXS-ddp, checkpoint_path checkpoints/dfm5/XXS-ddp
```

W&B dense history scan over the overlapping early region found:

```text
bin          fsdp_loss fsdp_acc  ddp_loss ddp_acc  loss_delta  acc_delta
0-1000        7.5082   0.1587    7.4919   0.1587   -0.0164    +0.0000
1000-2000     4.7858   0.2768    4.7986   0.2735   +0.0129    -0.0034
2000-5000     3.9048   0.3658    3.9815   0.3514   +0.0767    -0.0144
5000-10000    3.3445   0.4367    3.4740   0.4160   +0.1295    -0.0207
10000-15000   3.0544   0.4736    3.1153   0.4647   +0.0609    -0.0089
15000-20000   2.9061   0.4913    2.9444   0.4862   +0.0383    -0.0051
20000-25000   2.8366   0.4992    2.8848   0.4926   +0.0483    -0.0066
25000-30000   2.7886   0.5053    2.8348   0.4990   +0.0461    -0.0063
```

Throughput from the same W&B sample tail:

```text
FSDP tail 29010->30000: about 22.6 steps/s
DDP tail  28380->29370: about 25.2 steps/s
```

Interpretation: DDP is slightly but consistently behind FSDP on early
training metrics after the first few thousand steps, with roughly `0.04-0.13`
higher loss and `0.5-2.1` percentage points lower token accuracy in the
overlap. This is not a failure pattern: no NaNs, loss is falling, accuracy is
rising, and the DDP tail reaches about `0.505` token accuracy near `29K`
steps. Because the two runs did not start from identical weights, this should
not be treated as proof that DDP trains worse. For a fair optimizer/distributed
strategy comparison, resume DDP from a converted FSDP checkpoint and compare
matched continuation windows.

Update, 2026-06-14. Confidence: high. The DFM5 XXS `step_50000` full evals
for both the FSDP run and the DDP run used the default EMA checkpoint weights.
`scripts/schedule_checkpoint_evals.sh` defaults `NO_EMA=0`; standard evals
only add `ckpt_use_ema=false` when `NO_EMA=1`, and DFM/EuroEval server launch
paths only add `--no-ema` when `NO_EMA=1`. Focused searches of the relevant
50K launch/eval logs found no `NO_EMA=1`, `ckpt_use_ema=false`, or `--no-ema`
override. Therefore the observed 50K FSDP-vs-DDP full-eval differences should
be interpreted as EMA-vs-EMA, not EMA-vs-raw or raw-vs-raw.

DFM5 XXS-DDP EMA sanity check, 2026-06-14. Confidence: high for inspected
config and checkpoint tensors; medium for metric interpretation. The DFM5
XXS-DDP W&B config for run id `pqc9g81u` records `distributed_strategy=ddp`,
`checkpoint_format=unsharded`, `ddp_params_precision=fp32`,
`fwd_bwd_dtype=bfloat16`, and `ema=0.9999`. This means it is not using the old
broken low-precision EMA-shadow setup from early DFM4 XL-DDP experiments.
Inspecting `checkpoints/dfm5/XXS-ddp/unsharded_step_50000.pt`,
`unsharded_step_100000.pt`, and `unsharded_step_150000.pt` showed all 26
optimizer `param_ema` tensors are `torch.float32`. Mean absolute
EMA-current-weight deltas were nonzero and decreased over time:
`0.00946` at 50K, `0.00677` at 100K, and `0.00465` at 150K, which is
consistent with a working EMA update. The unsharded inference loader applies
EMA directly from the optimizer state into the model state when
`ckpt_use_ema=True`. A key-coverage check for `step_50000` found 27 model
tensors and 26 EMA tensors; the only model tensor without EMA is
`model.zL_init`, which is an `nn.Buffer`, not an optimizer parameter. Current
evidence does not point to a DDP EMA storage/load bug for DFM5 XXS-DDP; a
remaining possibility is ordinary EMA lag or model/task noise, which should be
tested by paired EMA vs no-EMA evals on the same checkpoints.

DDP fp32-vs-FSDP fp32 continuation caveats, 2026-06-14. Confidence: high for
inspected code; medium for expected numerical effect until directly tested
from a converted checkpoint.

If DDP `ddp_params_precision=fp32` and FSDP `fsdp_params_precision=fp32` are
started from the same model/optimizer/EMA/carry state and the same dataset
position, the logged training loss should be directly comparable because
metrics are logged from raw summed CE and local valid-token counts, then
summed across ranks in `reduce_metrics`. The logging path is independent of
whether gradients are averaged or summed.

There are still two code-level sources of different subsequent losses:

1. Gradient reduction scaling differs. FSDP explicitly calls
   `set_gradient_divide_factor(1.0)` and `set_force_sum_reduction_for_comms`,
   while PyTorch DDP averages gradients by default. The loss divisor is the
   average valid-token count across ranks. Therefore DDP computes the
   conventional global-token mean gradient, while FSDP produces a world-size
   scaled gradient. `AdamATan2` is intended to be scale-invariant for the
   gradient update, so this should mostly cancel, but finite-precision moment
   updates can still differ slightly.

2. Mixed precision is implemented differently. FSDP uses module-level
   `MixedPrecisionPolicy(param_dtype=fwd_bwd_dtype, reduce_dtype=fp32)`.
   DDP fp32 keeps persistent parameters fp32 and enables CUDA autocast around
   the forward/backward batch. Autocast is op-level and FSDP mixed precision is
   module-boundary-level, so exact bf16/fp32 choices can differ for operations
   such as linear projections, RMSNorm, and attention. Starting from identical
   weights can still yield slightly different logits/losses and then divergent
   training trajectories.

Other inspected differences are less concerning for loss equivalence:
DDP `init_sync=True` broadcasts parameters/buffers at wrap time; checkpoint
resume through the unsharded path loads the same full checkpoint on every rank
for DDP; `find_unused_parameters=True` is needed for the HRM warmup/unused
parameter pattern and should not change gradients for used parameters; both
paths use the same dataloader seed/rank/world-size interface.

DFM5 XXS DDP health check at about 65K, 2026-06-14. Confidence: high for W&B
API history and local checkpoint inspection. The DDP run `pqc9g81u` was
`running`, with local regular checkpoints through `step_60000` and an
ephemeral checkpoint at `step_65000`. Matched W&B history against the FSDP run
`2tv9u438` over the shared early window:

```text
bin          fsdp_loss fsdp_acc  ddp_loss ddp_acc  loss_delta  acc_delta
0-1000        7.5082   0.1587    7.4919   0.1587   -0.0164    +0.0000
1000-2000     4.7824   0.2771    4.7953   0.2737   +0.0129    -0.0034
2000-5000     3.9046   0.3658    3.9813   0.3515   +0.0767    -0.0144
5000-10000    3.3444   0.4367    3.4739   0.4161   +0.1295    -0.0207
10000-20000   2.9803   0.4825    3.0299   0.4755   +0.0496    -0.0070
20000-30000   2.8124   0.5023    2.8576   0.4960   +0.0452    -0.0062
30000-40000   2.7384   0.5111    2.7687   0.5064   +0.0304    -0.0047
40000-50000   2.7032   0.5152    2.7173   0.5123   +0.0141    -0.0028
50000-60000   2.7081   0.5140    2.6557   0.5200   -0.0524    +0.0060
60000-70000   2.3528   0.5539    2.3904   0.5497   +0.0375    -0.0043
```

Latest rows in the scan:

```text
FSDP step_70000: loss=2.3034 acc=0.5591 exact=0.0496 bp_steps=3
DDP  step_64995: loss=2.3030 acc=0.5528 exact=0.0378 bp_steps=3
```

Interpretation: DDP is healthy and close to FSDP. The initial FSDP advantage
shrinks substantially after 30K; DDP is briefly ahead in the 50K-60K bin and
slightly behind again in the 60K-70K bin. This looks like ordinary trajectory
noise plus implementation differences, not a failing DDP run. Tail throughput
from the W&B scan was lower for DDP (`~7.7` steps/s vs `~13.5` for the sampled
FSDP tail), but that DDP window overlapped the full `step_50000` eval running
on the same GPUs, so it should not be read as clean training throughput.

DFM5 XXS FSDP bf16-parameter run, 2026-06-14. Confidence: high for W&B API
history; medium for causal interpretation. The run `4ch8y3e8`
(`dfm5-XXS-fsdp-bf16`, `fsdp_params_precision=bf16`) shows a substantially
worse early training curve than the fp32-parameter FSDP baseline `2tv9u438`
and the fp32-parameter DDP run `pqc9g81u`. W&B history bin means:

```text
bin          fsdp_fp32 loss/acc   ddp_fp32 loss/acc   fsdp_bf16 loss/acc
0-1000       7.5082 / 0.1587      7.4919 / 0.1587     9.4289 / 0.1010
1000-2000    4.7824 / 0.2771      4.7953 / 0.2737     5.9497 / 0.2098
2000-5000    3.9038 / 0.3659      3.9806 / 0.3515     4.7019 / 0.2916
5000-10000   3.3444 / 0.4367      3.4738 / 0.4161     4.3216 / 0.3320
10000-20000  2.9804 / 0.4825      3.0299 / 0.4755     4.2301 / 0.3438*
```

`*` The bf16 run only had 289 logged rows in the 10K-20K bin at inspection
time, through `_step=11435`. Because this run uses persistent bf16 model
parameters and bf16 AdamATan2 moment buffers (`zeros_like(p)` follows parameter
dtype), while only EMA is forced to fp32, the most likely explanation is
optimizer/update precision degradation rather than an EMA evaluation issue.
Use `fsdp_params_precision=fp32` for comparable FSDP/ DDP training curves unless
a separate fp32-master-parameter or fp32-optimizer-state path is implemented.

DFM5 XXS 50K FSDP-vs-DDP eval table, 2026-06-14. Confidence: high for local
artifact extraction. A Markdown comparison of the workspace panel metrics for
`dfm5-XXS` 50K (`2tv9u438`) and `dfm5-XXS-ddp` 50K (`pqc9g81u`) was generated
from local `merged_metrics.json` files, with training metrics pulled from the
nearest W&B history rows to step 50K. The FSDP 50K headline averages were
originally computed with fewer metrics (`9/7/3` Danish/English/Math-Code)
than the DDP 50K averages (`18/15/4`), so headline averages are not strictly
apples-to-apples even though per-panel rows are directly comparable where both
values exist.

DFM5 XXS FSDP fp32-params vs bf16-params 1K loss windows, 2026-06-14.
Confidence: high for W&B API history. Compared run `2tv9u438` (`dfm5-XXS`,
default/fp32 persistent FSDP params) with run `4ch8y3e8`
(`dfm5-XXS-fsdp-bf16`, `fsdp_params_precision=bf16`). The bf16 run had W&B
history through `_step=17140` at inspection. In every complete 1K window
through 17K, bf16-params had substantially higher training loss; the gap grew
from `+0.78` to about `+1.22` after 2K. This supports treating the bf16
persistent-parameter/optimizer-state mode as degraded for this optimizer.

DFM5 L `step_50000` full eval completion, 2026-06-14. Confidence: high for
local scheduler logs, merged artifacts, and W&B sync output. The full
standard+DFM+EuroEval run for `checkpoints/dfm5/L` `step_50000` used log roots:

```text
logs/eval/dfm5_L_step50000_full_20260614_dfm5_L_step50000_full
logs/dfm_evals/dfm5_L_step50000_full_20260614_dfm5_L_step50000_full
logs/euroeval/dfm5_L_step50000_full_20260614_dfm5_L_step50000_full
```

The scheduler recorded `188` eval attempts, all with `status=0` and `oom=0`.
Its final status lines were `FINAL_MERGE_START` at `16:54:09+02:00` and
`FINAL_MERGE_END` at `16:55:25+02:00`. Merged metrics were written for all
standard evals, all DFM evals including IFEval-DA, and all 20 one-dataset
EuroEval groups. The merged metrics were synced to W&B project `DFM5`, run
`oti1lisg` (`dfm5-L`). The derived headline averages were then logged with:

```bash
python scripts/log_dfm5_headline_averages.py \
  --project DFM5 \
  --run-id oti1lisg \
  --run-name dfm5-L \
  --item 50000:0.27608846182186414:logs/eval/dfm5_L_step50000_full_20260614_dfm5_L_step50000_full:logs/dfm_evals/dfm5_L_step50000_full_20260614_dfm5_L_step50000_full:logs/euroeval/dfm5_L_step50000_full_20260614_dfm5_L_step50000_full/step_50000
```

W&B sync output confirmed the following summary values:

```text
headline_avg/danish      0.28379788656320293  count=18
headline_avg/english     0.33401347487407673  count=15
headline_avg/math_code   0.06487754537306532  count=4
headline_avg/overall     0.22756296893678166
headline_avg/epoch       0.27608846182186414
headline_avg/train_step  50000
```

Follow-up for the same run, 2026-06-14. Confidence: high for W&B history
readback and workspace API output. As with earlier DFM5 average logging, the
remote W&B `run.summary` API did not immediately expose the `headline_avg/*`
keys even though the client sync and local `wandb-summary.json` contained them.
A remote `scan_history` check found the actual history row:

```text
_step                    75711
headline_avg/epoch       0.27608846182186414
headline_avg/train_step  50000
headline_avg/danish      0.28379788656320293
headline_avg/english     0.33401347487407673
headline_avg/math_code   0.06487754537306532
headline_avg/overall     0.22756296893678166
```

The DFM5 workspace was refreshed so the panels plot against explicit history
x-axes (`eval/epoch`, `dfm_eval/epoch`, `euroeval/epoch`,
`headline_avg/epoch`) rather than W&B `_step` or summary values:

```bash
cd /work/dfm/HRM-Text
python scripts/create_dfm5_headline_workspace.py \
  --project DFM5 \
  --name "DFM5 headline metrics"
```

The refreshed workspace URL is:

```text
https://wandb.ai/peter-sk-sdu/DFM5?nw=ein5y6vzl3l
```

Additional DFM5 L `step_50000` workspace-panel repair, 2026-06-14.
Confidence: high for local merged artifacts and W&B client sync output. The
workspace manifest already contained panels for `eval/MMLU/acc`,
`eval/BoolQ/acc`, and `dfm_eval/nordjyllandnews/rouge2/mean`, but sparse W&B
history rows can fail to render when the metric and epoch x-axis are not
co-located in the same logged row. Compact rows were therefore re-logged to
run `DFM5/oti1lisg`:

```text
eval/epoch=0.27608846182186414
eval/MMLU/acc=0.29475

eval/epoch=0.27608846182186414
eval/BoolQ/acc=0.5817

dfm_eval/epoch=0.27608846182186414
dfm_eval/nordjyllandnews/rouge2/mean=0.09118908082193376
```

The corresponding local W&B summaries are in:

```text
wandb/run-20260614_170906-oti1lisg/files/wandb-summary.json
wandb/run-20260614_171041-oti1lisg/files/wandb-summary.json
```

DFM5 L `step_100000` full eval launch, 2026-06-14. Confidence: high for local
tmux/status logs. `scripts/schedule_checkpoint_evals.sh` now supports
`QUEUE_ORDER=euroeval_first`, which enqueues the 20 one-dataset EuroEval jobs
before DFM IFEval-DA, standard evals, and the remaining DFM evals. This is meant
to avoid EuroEval becoming the long tail. The first attempted launch omitted
`EUROEVAL_BIN=/work/dfm/HRM-Text/scripts/euroeval_api_no_flash_attn_guard.py`;
EuroEval immediately failed with its top-level `flash_attn` import guard. That
bad tmux session/log family was stopped and replaced with a guarded run:

```text
tmux session: dfm5_L_step100000_full_eurofirst_guard
checkpoint:   checkpoints/dfm5/L step_100000
eval epoch:   0.5521769236437283
W&B target:   DFM5 / oti1lisg / dfm5-L
log root:     logs/eval/dfm5_L_step100000_full_20260614_eurofirst_guard
dfm root:     logs/dfm_evals/dfm5_L_step100000_full_20260614_eurofirst_guard
euro root:    logs/euroeval/dfm5_L_step100000_full_20260614_eurofirst_guard
```

The guarded launch queued `188` jobs and started with EuroEval
`angry-tweets`, `scala-da`, `dansk`, and `multi-wiki-qa-da`. At the first
status check there were no recorded failed attempts in
`eval_attempts.tsv`; the started EuroEval jobs were still running.

DFM5 L `step_100000` full eval completion, 2026-06-14. Confidence: high for
local scheduler logs, merged artifacts, and W&B client sync output. The guarded
EuroEval-first run completed all `188` attempts with `status=0` and `oom=0`:

```text
EuroEval:      20
DFM IFEval-DA: 32
Standard:      85
DFM:           51
FINAL_MERGE_START  2026-06-14T22:42:30+02:00
FINAL_MERGE_END    2026-06-14T22:43:46+02:00
```

Merge/sync logs were present and had W&B markers with no local error markers:

```text
standard merge logs: 8/8 with W&B markers
dfm merge logs:      11/11 with W&B markers
euroeval logs:       20/20 with W&B markers
```

The `step_100000` headline averages were logged to W&B project `DFM5`, run
`oti1lisg` (`dfm5-L`) with:

```bash
cd /work/dfm/HRM-Text
python scripts/log_dfm5_headline_averages.py \
  --project DFM5 \
  --run-id oti1lisg \
  --run-name dfm5-L \
  --item 100000:0.5521769236437283:logs/eval/dfm5_L_step100000_full_20260614_eurofirst_guard:logs/dfm_evals/dfm5_L_step100000_full_20260614_eurofirst_guard:logs/euroeval/dfm5_L_step100000_full_20260614_eurofirst_guard/step_100000
```

W&B client output confirmed sync and summary update for:

```text
headline_avg/danish      0.3481170617668168   count=18
headline_avg/english     0.4285458041771221   count=15
headline_avg/math_code   0.14095378072745426  count=4
headline_avg/overall     0.30587221555713107
headline_avg/epoch       0.5521769236437283
headline_avg/train_step  100000
```

DFM5 L `step_150000` full eval launch, 2026-06-15. Confidence: high for local
checkpoint state and scheduler status logs. The `checkpoints/dfm5/L`
`step_150000` checkpoint exists as an FSDP2 sharded regular checkpoint with
`batch_in_epoch=150000`, `global_batch_size=196608`, and data path
`data/sampled_dfm5`. Its eval epoch x-value is `0.8282653854655924`.

The full eval was launched with EuroEval-first ordering and the EuroEval
FlashAttention guard:

```text
tmux session/window: hrm-0:7 eval150k-scheduler
monitor window:      hrm-0:8 eval150k-monitor
checkpoint:          checkpoints/dfm5/L step_150000
W&B target:          DFM5 / oti1lisg / dfm5-L
log root:            logs/eval/dfm5_L_step150000_full_20260615_eurofirst_guard
dfm root:            logs/dfm_evals/dfm5_L_step150000_full_20260615_eurofirst_guard
euro root:           logs/euroeval/dfm5_L_step150000_full_20260615_eurofirst_guard
```

Initial scheduler status:

```text
2026-06-15T05:23:39+02:00 QUEUED 188 jobs
2026-06-15T05:23:39+02:00 CHECKPOINT_READY step_150000 path_checkpoints/dfm5/L
2026-06-15T05:23:39+02:00 START euroeval angry-tweets shard_0_of_20 gpu_0 attempt_1_of_6 batch_16
```

At the first health check, EuroEval tasks had started first on GPUs 0-5 and
`eval_attempts.tsv` still contained only the header, so no failures had been
recorded.

DFM5 L `step_150000` full eval completion and averages, 2026-06-15.
Confidence: high for local scheduler logs, merged artifacts, W&B client sync
output, and local W&B summary. The run completed all `188` scheduled jobs. The
attempt log had `191` rows because `3` attempts failed before retry; the final
completed job count was clean:

```text
EuroEval:      20
DFM IFEval-DA: 32
Standard:      85
DFM:           51
FINAL_MERGE_END 2026-06-15T08:02:10+02:00
```

Merge/sync logs were present and had W&B markers with no local error markers:

```text
standard merge logs: 8/8 with W&B markers
dfm merge logs:      11/11 with W&B markers
euroeval logs:       20/20 with W&B markers
```

The `step_150000` headline averages were logged to W&B project `DFM5`, run
`oti1lisg` (`dfm5-L`) with:

```bash
cd /work/dfm/HRM-Text
python scripts/log_dfm5_headline_averages.py \
  --project DFM5 \
  --run-id oti1lisg \
  --run-name dfm5-L \
  --item 150000:0.8282653854655924:logs/eval/dfm5_L_step150000_full_20260615_eurofirst_guard:logs/dfm_evals/dfm5_L_step150000_full_20260615_eurofirst_guard:logs/euroeval/dfm5_L_step150000_full_20260615_eurofirst_guard/step_150000
```

W&B client output confirmed sync; the local summary file
`wandb/run-20260615_081458-oti1lisg/files/wandb-summary.json` contains:

```text
headline_avg/danish      0.39596249125111194  count=18
headline_avg/english     0.4978719019178343   count=15
headline_avg/math_code   0.19459343879065813  count=4
headline_avg/overall     0.3628092773198681
headline_avg/epoch       0.8282653854655924
headline_avg/train_step  150000
```

DFM5 L comparison report, 2026-06-15. Confidence: high for local artifact
extraction. A Markdown table comparing DFM5-L `step_50000`, `step_100000`,
and `step_150000` against the earlier original Sapient L run and README
model-card L/XL values was written to:

```text
logs/reports/dfm5_l_eval_comparison_50k_100k_150k_vs_original_ema_and_card.md
```

Source policy for that report:

- DFM5-L columns use the local full eval merged artifacts under
  `logs/eval`, `logs/dfm_evals`, and `logs/euroeval` for the corresponding
  `dfm5_L_step{50000,100000,150000}_full_*` roots.
- Original Sapient L uses EMA/default sources only: the full epoch-4 standard
  eval log `logs/eval/original_sapient_L/epoch_4.log`, the original epoch-4
  EuroEval JSONL `logs/euroeval/original_sapient_L/epoch_4/euroeval_benchmark_results.jsonl`,
  and the default/EMA local DFM-evals artifacts under
  `logs/dfm_evals/original_sapient_L_lite_all_checkpoints_20260603T213010/epoch_4`.
- Explicit `*_noema_*` roots are intentionally excluded from this comparison.
- README model-card L/XL columns are populated only for the standard benchmark
  metrics shown in `README.md`.
- On 2026-06-15, section average rows were added to the Markdown report for
  Danish, English, and Math & Code. The averages are percent-style values for
  the DFM5-L and original Sapient L columns only; the model-card average cells
  remain blank because the card provides only a subset of standard benchmarks.
  Danish and English averages follow the headline-dashboard convention and
  exclude VaLEU rows.
- Later on 2026-06-15, the report was expanded from only original Sapient L
  epoch 4 to original Sapient L epochs 1, 2, 3, and 4, all using EMA/default
  sources. The original Sapient L epoch-2 EuroEval source file does not contain
  the `valeu-da` row, so that cell is reported as `—`; this does not affect the
  Danish average because VaLEU rows are excluded from section averages.

DFM5 L `step_200000` full eval launch, 2026-06-15. Confidence: high for local
checkpoint state, launch command, and scheduler logs; medium for final sync
until the post-eval watcher completes.

The `step_200000` checkpoint exists under `checkpoints/dfm5/L` with
`checkpoint_state_step_200000.json`, `fsdp2_step_200000/`, and eight
`carry_step_200000.*.pt` files. Its eval epoch x-value is:

```text
1.1043538472874566
```

The full eval was launched in tmux window `hrm-0:7` with EuroEval-first
ordering while DFM5 L training continued:

```bash
cd /work/dfm/HRM-Text
CKPT_PATH=checkpoints/dfm5/L \
CKPT_TAG=step_200000 \
EVAL_EPOCH=1.1043538472874566 \
GPUS=0,1,2,3,4,5,6,7 \
LOG_ROOT=logs/eval/dfm5_L_step200000_full_20260615_eurofirst_guard \
DFM_LOG_ROOT=logs/dfm_evals/dfm5_L_step200000_full_20260615_eurofirst_guard \
EUROEVAL_LOG_ROOT=logs/euroeval/dfm5_L_step200000_full_20260615_eurofirst_guard \
WANDB_SYNC=1 \
WANDB_PROJECT=DFM5 \
WANDB_RUN_ID=oti1lisg \
WANDB_RUN_NAME=dfm5-L \
MODEL_PREFIX=hrm-dfm5-L \
RUN_EUROEVAL=1 \
QUEUE_ORDER=euroeval_first \
STANDARD_BATCH_SIZE=128 \
STANDARD_BATCH_SIZE_GSM8K=64 \
STANDARD_BATCH_SIZE_MATH=64 \
STANDARD_BATCH_SIZE_DROP=32 \
DFM_BATCH_SIZE=32 \
DFM_BATCH_SIZE_GOVREPORT=32 \
DFM_BATCH_SIZE_NORDJYLLANDNEWS=32 \
DFM_BATCH_SIZE_WMT24PP_EN_DA=32 \
DFM_BATCH_SIZE_HUMANEVAL=16 \
DFM_BATCH_SIZE_GENERATIVE_TALEMAADER=16 \
IFEVAL_BATCH_SIZE=32 \
EUROEVAL_BATCH_SIZE=16 \
MAX_RETRIES=5 \
EUROEVAL_BIN=/work/dfm/HRM-Text/scripts/euroeval_api_no_flash_attn_guard.py \
scripts/schedule_checkpoint_evals.sh \
  2>&1 | tee logs/dfm5_L_step200000_full_eval_20260615.log
```

Monitor window: `hrm-0:8`. A post-eval watcher runs in `hrm-0:10`; it waits
for `FINAL_MERGE_END`, then logs the 200K headline averages to W&B and
regenerates the comparison table:

```bash
python scripts/log_dfm5_headline_averages.py \
  --project DFM5 \
  --run-id oti1lisg \
  --run-name dfm5-L \
  --item 200000:1.1043538472874566:logs/eval/dfm5_L_step200000_full_20260615_eurofirst_guard:logs/dfm_evals/dfm5_L_step200000_full_20260615_eurofirst_guard:logs/euroeval/dfm5_L_step200000_full_20260615_eurofirst_guard/step_200000

python scripts/generate_dfm5_l_eval_comparison_report.py
```

`scripts/generate_dfm5_l_eval_comparison_report.py` was added to regenerate
the Markdown comparison report from local artifacts. It includes DFM5-L
50K/100K/150K/200K, original Sapient L e1-e4 EMA/default, and README model-card
L/XL standard values. The script normalizes local fraction-style metrics to the
report's percent-style display and excludes VaLEU rows from section averages.

DFM5 workspace panel metrics vs headline averages, 2026-06-15. Confidence:
high for the live W&B workspace spec fetched with `wandb_workspaces`.

The live workspace `https://wandb.ai/peter-sk-sdu/DFM5?nw=yl894iibtp5`
(`DFM5 headline metrics`) was fetched to:

```text
logs/wandb_workspace_specs/dfm5_live_yl894iibtp5_20260615.json
```

The visible panels currently differ from `scripts/log_dfm5_headline_averages.py`
in these substantive places:

- Danish MultiWikiQA panel uses `dfm_eval/multi_wiki_qa/exact_match/mean`,
  while the Danish average still uses `dfm_eval/multi_wiki_qa/f1/mean`.
- Danish NordjyllandNews panel uses
  `dfm_eval/nordjyllandnews/bertscore_f1/mean`, while the Danish average still
  uses `dfm_eval/nordjyllandnews/rouge2/mean`.
- English DROP panel uses `eval/DROP/em`, while the English average still uses
  `eval/DROP/f1`.
- English GovReport panel uses `dfm_eval/govreport/bertscore_f1/mean`, while
  the English average still uses `dfm_eval/govreport/rouge2/mean`.

The workspace also shows EuroEval VaLEU panels for Danish and English
(`euroeval/da/european-values/valeu-da/european_values` and
`euroeval/en/european-values/valeu-en/european_values`), but these remain
excluded from the headline averages by the earlier VaLEU exclusion policy.

The W&B report shared via `https://api.wandb.ai/links/peter-sk-sdu/iboaiazf`
resolves to report `DFM5--VmlldzoxNzIzNTc1Nw`; its spec was fetched to:

```text
logs/wandb_workspace_specs/dfm5_report_VmlldzoxNzIzNTc1Nw_20260615.json
```

The report's panel metrics initially matched the workspace mismatches above:
MultiWikiQA exact-match vs average F1, NordjyllandNews BERTScore vs average
ROUGE-2, DROP exact-match vs average F1, GovReport BERTScore vs average
ROUGE-2, and visible VaLEU panels that remain excluded from averages.

Follow-up on 2026-06-15: the DFM5 headline-average definitions were updated in
code to match the live workspace/report panel choices. Confidence: high for
local script validation and dry-run output.

Changed files:

```text
scripts/log_dfm5_headline_averages.py
scripts/create_dfm5_headline_workspace.py
scripts/generate_dfm5_l_eval_comparison_report.py
```

Superseded in the same session for DROP: the headline averages now use:

- `dfm_eval/multi_wiki_qa/exact_match/mean` instead of
  `dfm_eval/multi_wiki_qa/f1/mean`.
- `dfm_eval/nordjyllandnews/bertscore_f1/mean` instead of
  `dfm_eval/nordjyllandnews/rouge2/mean`.
- `eval/DROP/f1`; DROP was intentionally kept on F1 so the Markdown comparison
  table remains comparable to the model-card DROP F1 values.
- `dfm_eval/govreport/bertscore_f1/mean` instead of
  `dfm_eval/govreport/rouge2/mean`.

VaLEU remains visible in the workspace/report but excluded from all headline
averages. The regenerated local Markdown report is:

```text
logs/reports/dfm5_l_eval_comparison_50k_100k_150k_vs_original_ema_and_card.md
```

Dry-run corrected DFM5-L headline averages with DROP kept on F1:

```text
50K:  Danish=0.3204938053  English=0.3394398505  MathCode=0.0648775454  Overall=0.2416037337
100K: Danish=0.3856718136  English=0.4337499937  MathCode=0.1409537807  Overall=0.3201251960
150K: Danish=0.4332904762  English=0.5028531674  MathCode=0.1945934388  Overall=0.3769123608
200K: Danish=0.4480947019  English=0.5191093860  MathCode=0.2233228181  Overall=0.3968423020
```

W&B run `DFM5/oti1lisg` currently has four old `headline_avg/*` history rows.
W&B history rows are append-only, so replacing those points cleanly requires
either a corrected/new run or new metric keys plus panel updates; appending the
corrected rows under the same keys would create duplicate points at the same
`headline_avg/epoch` x-values.

The average logger now defaults to `avg/*` and supports `--metric-prefix` for
overrides. The workspace builder now defaults to `avg/*` and supports
`--headline-avg-prefix` for overrides. This means the running 250K post-eval
watcher, which calls the average logger without an explicit prefix, will log
250K averages under `avg/*`.

The live workspace `https://wandb.ai/peter-sk-sdu/DFM5?nw=yl894iibtp5` and the
shared report `DFM5--VmlldzoxNzIzNTc1Nw` were patched in place on 2026-06-15:

- Headline average panels now use `avg/overall`, `avg/danish`, `avg/english`,
  and `avg/math_code` with x-axis `avg/epoch`.
- No `headline_avg/` panel references remain in the live workspace.
- DROP was restored to `DROP F1` using `eval/DROP/f1`.

Patch snapshots:

```text
logs/wandb_workspace_specs/dfm5_live_yl894iibtp5_after_avg_dropf1_patch_20260615.json
logs/wandb_workspace_specs/dfm5_report_VmlldzoxNzIzNTc1Nw_after_avg_dropf1_patch_20260615.json
```

Follow-up: because `avg/*` did not yet have logged history rows, W&B initially
hid the new average-only section and the average panels when
`showEmptySections=false`. The live workspace was patched in place to set panel
bank `showEmptySections=true`. Verification from the live spec showed:

```text
Headline Averages: 4 panels
Danish Headline Metrics: 20 panels
English Headline Metrics: 17 panels
Math & Code Headline Metrics: 5 panels
Training Metrics & Params: 9 panels
```

Snapshot:

```text
logs/wandb_workspace_specs/dfm5_live_yl894iibtp5_show_empty_sections_20260615.json
```

On 2026-06-15, `avg/*` headline averages were logged to W&B run
`DFM5/oti1lisg` for the completed DFM5-L checkpoints 50K, 100K, 150K, and
200K. Confidence: high; W&B `scan_history` verified exactly four `avg/*` rows.

Command:

```bash
cd /work/dfm/HRM-Text
python scripts/log_dfm5_headline_averages.py \
  --project DFM5 \
  --run-id oti1lisg \
  --run-name dfm5-L \
  --item 50000:0.27608846182186414:logs/eval/dfm5_L_step50000_full_20260614_dfm5_L_step50000_full:logs/dfm_evals/dfm5_L_step50000_full_20260614_dfm5_L_step50000_full:logs/euroeval/dfm5_L_step50000_full_20260614_dfm5_L_step50000_full/step_50000 \
  --item 100000:0.5521769236437283:logs/eval/dfm5_L_step100000_full_20260614_eurofirst_guard:logs/dfm_evals/dfm5_L_step100000_full_20260614_eurofirst_guard:logs/euroeval/dfm5_L_step100000_full_20260614_eurofirst_guard/step_100000 \
  --item 150000:0.8282653854655924:logs/eval/dfm5_L_step150000_full_20260615_eurofirst_guard:logs/dfm_evals/dfm5_L_step150000_full_20260615_eurofirst_guard:logs/euroeval/dfm5_L_step150000_full_20260615_eurofirst_guard/step_150000 \
  --item 200000:1.1043538472874566:logs/eval/dfm5_L_step200000_full_20260615_eurofirst_guard:logs/dfm_evals/dfm5_L_step200000_full_20260615_eurofirst_guard:logs/euroeval/dfm5_L_step200000_full_20260615_eurofirst_guard/step_200000 \
  2>&1 | tee logs/dfm5_L_avg_50k_200k_20260615.log
```

Verified rows:

```text
50K:  avg/danish=0.3204938053  avg/english=0.3394398505  avg/math_code=0.0648775454  avg/overall=0.2416037337
100K: avg/danish=0.3856718136  avg/english=0.4337499937  avg/math_code=0.1409537807  avg/overall=0.3201251960
150K: avg/danish=0.4332904762  avg/english=0.5028531674  avg/math_code=0.1945934388  avg/overall=0.3769123608
200K: avg/danish=0.4480947019  avg/english=0.5191093860  avg/math_code=0.2233228181  avg/overall=0.3968423020
```

Superseded in the same session: the DFM5-L 250K eval later reached
`FINAL_MERGE_END`, and its post-eval watcher logged the 250K row under
`avg/*`. See the 250K full-eval completion note near the top of this page for
the exact values.

On 2026-06-15, `avg/*` headline averages were also logged for DFM5-XXS and the
original Sapient L backfilled run. Confidence: high for W&B client sync output
and local command logs; medium for remote history verification because a later
W&B `scan_history` verification call hung and was terminated without touching
active eval jobs.

DFM5-XXS run:

```text
project: DFM5
run id:  2tv9u438
name:    dfm5-XXS
log:     logs/dfm5_XXS_avg_50k_300k_20260615.log
```

Synced rows:

```text
50K:  avg/danish=0.1973913085  avg/english=0.2084723215  avg/math_code=0.0122617477  avg/overall=0.1393751259
100K: avg/danish=0.1992734184  avg/english=0.2355164296  avg/math_code=0.0170418092  avg/overall=0.1506105524
150K: avg/danish=0.2221133424  avg/english=0.2255464438  avg/math_code=0.0122899433  avg/overall=0.1533165765
200K: avg/danish=0.1915085591  avg/english=0.2427157514  avg/math_code=0.0108271777  avg/overall=0.1483504961
250K: avg/danish=0.2311608317  avg/english=0.2312142869  avg/math_code=0.0137397351  avg/overall=0.1587049512
300K: avg/danish=0.2014285955  avg/english=0.2378867045  avg/math_code=0.0145517530  avg/overall=0.1512890176
```

Original Sapient L backfilled run:

```text
project: DFM5
run id:  original-sapient-L-dfm5-backfill-20260615
name:    original Sapient L backfilled
log:     logs/original_sapient_L_backfill_avg_20260615.log
```

Synced rows:

```text
epoch 1: avg/danish=0.1802960225  avg/english=0.4288698321  avg/math_code=0.2313500000  avg/overall=0.2801719515
epoch 2: avg/danish=0.2225090016  avg/english=0.4979667276  avg/math_code=0.2937250000  avg/overall=0.3380669097
epoch 3: avg/danish=0.2250292546  avg/english=0.5219291269  avg/math_code=0.3142750000  avg/overall=0.3537444605
epoch 4: avg/danish=0.2211987137  avg/english=0.5481151233  avg/math_code=0.3203250000  avg/overall=0.3632129457
```

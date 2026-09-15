---
type: Operational Record
title: 2026-06-14 EuroEval Scheduling Fix
description: 'Part of Current State: 2026-06-14 EuroEval Scheduling Fix.'
tags:
- operations
- training
- evaluation
- runtime
status: stable
last_updated: 2026-09-11
confidence: high
part_of: /pages/current-state.md
---
# 2026-06-14 EuroEval Scheduling Fix

Part of [Current State](/pages/current-state.md).

## EuroEval Selector Compatibility (2026-09-11)

At XXL restart520K checkpoint 550K, 17 EuroEval tasks exited with code 2:
`Only one of --language and --dataset can be specified`. The installed CLI
rejects the scheduler's redundant language selectors when a dataset ID is
already specified. This was not a GPU-memory failure. The plan uses an
unpinned `uv run --no-project --with euroeval` client environment.

The OpenAI scheduler launcher now supplies the explicit dataset without
languages. The API wrapper also normalizes redundant language arguments for
already-running scheduler processes (whose imported launcher code is old).
Language-only selections remain unchanged. Three focused normalization tests
passed. Only failed rows with this exact logged error were reset under
PlanLock; attempts/logs and a timestamped plan backup were preserved. No
running standard evals or persistent servers were interrupted.

The AngryTweets retry progressed past CLI validation into model connection
and benchmarking at 15:14 on September 11. This verifies startup recovery,
not completion of all 17 tasks. For reproducibility, future campaigns should
pin a verified EuroEval version instead of resolving the latest client.

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

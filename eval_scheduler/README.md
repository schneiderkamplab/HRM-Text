# HRM Eval Scheduler

This is a new plan-first scheduler for HRM-Text evaluations.

It is intentionally separate from `scripts/schedule_checkpoint_evals.sh`.  It
does not import that shell scheduler.  The package owns its job-plan format,
state handling, retry policy, and CLI, while still calling the repository's
evaluation entrypoints as external commands.

## Design

The scheduler writes an explicit TSV plan:

```tsv
job_id	action	family	name	shard	shards	deps	initial_batch	max_retries	gpu_policy	status	attempt	log_dir	metadata_json
```

The plan is the desired workflow, not just a list of eval shards.  It can
contain:

- `wait_checkpoint`: wait until a checkpoint is fully written.
- `eval_standard`: one standard benchmark shard.
- `eval_dfm`: one dfm-evals task shard.
- `eval_dfm_ifeval`: one Danish IFEval shard.
- `eval_euroeval`: one EuroEval dataset group.
- `merge_standard`, `merge_dfm`, `merge_ifeval`: merge and optionally sync
  finished shard sets.
- `average`: log headline averages from merged artifacts.
- `report`: regenerate documentation tables.

Every merge/sync/average/report row lists dependencies on the rows that must
complete first.  Pending rows can be edited directly, including
`initial_batch`, before the scheduler starts or while earlier dependencies are
still running.

Generated plans include a `wait_checkpoint` row by default. Eval jobs depend on
that row, so the plan can be created before the checkpoint exists. The wait row
completes only after either `fsdp2_<tag>/.metadata` or `unsharded_<tag>.pt`
exists and all `carry_<tag>.<rank>.pt` files are present.

Runtime state is append-only:

- `status.tsv`: event log (`START`, `END`, `RETRY`, `SKIP`, `BLOCKED`).
- `attempts.tsv`: per-attempt telemetry, including GPU memory and OOM status.
- `plan.tsv`: editable desired plan with current status fields.
- `plan.lock`: advisory interprocess lock used by scheduler commands.
- `plan.lock.holder.json`: metadata for a background lock holder started by
  `plan lock`.

## Examples

Create a DFM5 full-eval plan for a checkpoint:

```bash
python -m eval_scheduler plan create \
  --plan-dir logs/scheduler/dfm5_L_step300000 \
  --ckpt-path checkpoints/dfm5/L \
  --ckpt-tag step_300000 \
  --eval-epoch 1.6565307709311847 \
  --log-root logs/eval/dfm5_L_step300000_new_scheduler \
  --dfm-log-root logs/dfm_evals/dfm5_L_step300000_new_scheduler \
  --euroeval-log-root logs/euroeval/dfm5_L_step300000_new_scheduler \
  --run-euroeval \
  --queue-order euroeval-first
```

Append another upcoming checkpoint to the same plan:

```bash
python -m eval_scheduler plan create \
  --append \
  --plan-dir logs/scheduler/dfm5_L_multi \
  --ckpt-path checkpoints/dfm5/L \
  --ckpt-tag step_350000 \
  --eval-epoch 1.932619 \
  --log-root logs/eval/dfm5_L_step350000_new_scheduler \
  --dfm-log-root logs/dfm_evals/dfm5_L_step350000_new_scheduler \
  --euroeval-log-root logs/euroeval/dfm5_L_step350000_new_scheduler \
  --wandb-run-id oti1lisg \
  --wandb-run-name dfm5-L \
  --model-prefix hrm-dfm5-L \
  --run-euroeval \
  --queue-order euroeval-first
```

Checkpoint wait controls:

```bash
--include-checkpoint-wait / --no-include-checkpoint-wait
--checkpoint-carry-ranks 8
--checkpoint-wait-seconds 300
--checkpoint-wait-max-seconds 0  # 0 means wait indefinitely
```

Inspect the plan:

```bash
python -m eval_scheduler plan summary --plan-dir logs/scheduler/dfm5_L_step300000
```

Change pending batch sizes:

```bash
python -m eval_scheduler plan set-batch \
  --plan-dir logs/scheduler/dfm5_L_step300000 \
  --family dfm_ifeval \
  --batch 32
```

Edit `plan.tsv` under the scheduler lock:

```bash
python -m eval_scheduler plan edit \
  --plan-dir logs/scheduler/dfm5_L_step300000 \
  --editor "vim"
```

Alternatively, hold the lock while editing manually in another terminal:

```bash
python -m eval_scheduler plan lock \
  --plan-dir logs/scheduler/dfm5_L_step300000

vim logs/scheduler/dfm5_L_step300000/plan.tsv

python -m eval_scheduler plan unlock \
  --plan-dir logs/scheduler/dfm5_L_step300000
```

Run workers:

```bash
python -m eval_scheduler run \
  --plan-dir logs/scheduler/dfm5_L_step300000 \
  --gpus 0,1,2,3,4,5,6,7
```

Gracefully stop after currently running jobs finish:

```bash
python -m eval_scheduler stop --plan-dir logs/scheduler/dfm5_L_step300000
```

Resume later with the same command:

```bash
python -m eval_scheduler run \
  --plan-dir logs/scheduler/dfm5_L_step300000 \
  --gpus 0,1,2,3,4,5,6,7
```

If the scheduler process was killed hard, repair stale `running` rows first:

```bash
python -m eval_scheduler plan reset-running \
  --plan-dir logs/scheduler/dfm5_L_step300000
```

Monitor:

```bash
python -m eval_scheduler status --plan-dir logs/scheduler/dfm5_L_step300000
```

## Notes

- `plan.tsv` is human-editable.  Edits only affect pending jobs.
- Retry batch size is based on the row's `initial_batch`, so correcting a row
  from `64` to `32` immediately changes future attempts for that job.
- OOM detection scans the job's primary logs for common CUDA OOM strings.
- Merge jobs are normal DAG jobs, so they can run as soon as their shard
  dependencies are complete, while unrelated eval shards continue on other GPUs.
- The lock is advisory. Use `plan edit`, or `plan lock`/`plan unlock`, when
  editing `plan.tsv` while a scheduler may be active.
- `plan create --append` can add another checkpoint subgraph to an existing
  plan. Job IDs and dependencies are rebased automatically.
- `stop` creates `stop.request`. The runner observes it between launches and
  stops claiming new jobs. Active eval jobs are allowed to finish; active
  checkpoint-wait jobs return to `pending`.
- Starting `run` clears any stale `stop.request`, so rerunning the same plan
  resumes remaining `pending` jobs. Use `plan reset-running` after hard kills
  that leave rows stuck as `running`.

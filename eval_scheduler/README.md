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

Create a DFM5-L plan whose EuroEval jobs use an exported HF/vLLM checkpoint
through the native-compatible proxy:

```bash
python -m eval_scheduler plan create \
  --plan-dir logs/scheduler/dfm5_L_step550000_vllm \
  --ckpt-path checkpoints/dfm5/L \
  --ckpt-tag step_550000 \
  --eval-epoch 1.4976296606915782 \
  --log-root logs/eval/dfm5_L_step550000_vllm \
  --dfm-log-root logs/dfm_evals/dfm5_L_step550000_vllm \
  --euroeval-log-root logs/euroeval/dfm5_L_step550000_vllm \
  --wandb-run-id oti1lisg \
  --wandb-run-name dfm5-L \
  --model-prefix hrm-dfm5-L-vllm-native-proxy \
  --run-euroeval \
  --queue-order euroeval-first \
  --standard-config evaluation/config/hrm_vllm_benchmarking.yaml \
  --standard-engine-backend vllm \
  --standard-hf-export-dir /work/dfm/HRM-Text/exports/dfm5_L_step550000_ema_hf \
  --euroeval-batch 32 \
  --hrm-server-backend vllm \
  --hrm-hf-export-dir /work/dfm/HRM-Text/exports/dfm5_L_step550000_ema_hf \
  --hrm-vllm-native-proxy \
  --vllm-gpu-memory-utilization 0.22 \
  --vllm-attention-backend FLASH_ATTN \
  --vllm-extra-args "--enforce-eager --attention-backend FLASH_ATTN --chat-template /work/dfm/HRM-Text/evaluation/chat_templates/hrm_direct_chat.jinja"
```

For current DFM5-L vLLM checkpoint evals, prefer the checked-in wrapper instead
of recreating the long command manually:

```bash
scripts/create_dfm5_l_vllm_eval_plan.sh step_750000 4.141326927327961 20260619
```

That wrapper creates the full standard + DFM + DFM-IFEval + EuroEval graph with
the working settings used for the 700K run:

- standard evals: `evaluation/config/hrm_vllm_benchmarking.yaml`, vLLM/FA4,
  batch `64`.
- DFM evals: vLLM/FA4, batch `32`.
- DFM IFEval-DA: `32` shards, batch `32`.
- EuroEval: batch `32`, `EUROEVAL_MAX_CONCURRENT_CALLS=32`, native-compatible
  vLLM proxy.
- global vLLM server memory while co-running with the active DFM6 training run:
  `--vllm-gpu-memory-utilization 0.28`. This replaced the earlier `0.33`
  setting after `step_250000` hit vLLM startup failures under higher training
  memory pressure around `bp_steps == 5`.
- `generative_talemaader`: batch `16`, max-connections `16`,
  per-shard managed `unsloth/gemma-4-E4B-it` judge, and per-task vLLM memory
  utilization `0.18` so the judge fits beside training and the HRM server. Do
  not lower batch/max-connections for this failure mode; the OOM was caused by
  insufficient judge startup headroom after the HRM vLLM server reserved KV
  cache.
- `govreport`: inserts `max_report_chars=9000` into each GovReport row.

`--hrm-vllm-native-proxy` strips EuroEval/OpenAI fields that the native HRM
server ignores, such as strict `response_format`, logprobs, and seed. Use it
when comparing vLLM results to historical native-server EuroEval lines.

For internal vLLM plans, `plan create` adds an `export_hf` job by default. The
job runs after `wait_checkpoint`, writes the EMA HF export with
`conversion/convert_to_hf.py`, and all vLLM eval rows depend on it. If
`model.safetensors` already exists in the export directory, the job exits
successfully without rewriting the export. Disable this with
`--no-include-hf-export` only when the export is managed externally.

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

Rich monitor with per-GPU workload, queue counts, and task-specific progress:

```bash
python -m eval_scheduler monitor \
  --plan-dir logs/scheduler/dfm5_L_step300000 \
  --gpus 0,1,2,3,4,5,6,7
```

For a one-shot snapshot:

```bash
python -m eval_scheduler monitor \
  --plan-dir logs/scheduler/dfm5_L_step300000 \
  --gpus 0,1,2,3,4,5,6,7 \
  --once
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
- `status` is intentionally terse. `monitor` is the operator view: it reads
  `plan.tsv`, `status.tsv`, GPU memory/utilization, and active task logs. It
  reports standard tqdm progress, dfm-evals server completion counts, and
  EuroEval nested pass/sample progress such as `pass 3/10 samples 137/343`.
- Active GPU lines and the `next ready` queue include a model/checkpoint label
  such as `hrm-dfm5-L@step_400000:ema`, `hrm-dfm5-L@step_400000:noema`, or
  `qwen35-2b@qwen35_2b:ema`.
- `monitor` also shows a `blocked pending` section when pending jobs are not
  runnable yet. Each line names the job and the unmet dependency IDs with their
  current status, e.g. `blocked_by [eval-00123:running]`.
- For dfm-evals jobs, `monitor` also reads Inspect `logs.json` and the
  dfm-evals text log when available to infer sample totals, and surfaces early
  configuration failures such as missing judge placeholders. Some dfm-evals
  jobs still show `progress unknown` during model/metric setup before the task
  header or server requests exist.

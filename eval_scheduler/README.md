# HRM Eval Scheduler

This is a new plan-first scheduler for HRM-Text evaluations.

It is intentionally separate from `scripts/schedule_checkpoint_evals.sh`.  It
does not import that shell scheduler.  The package owns its job-plan format,
state handling, retry policy, and CLI, while still calling the repository's
evaluation entrypoints as external commands.

## Design

The scheduler writes an explicit TSV plan:

```tsv
job_id	action	family	name	shard	shards	deps	deps_mode	initial_batch	max_retries	gpu_policy	status	attempt	log_dir	metadata_json
```

The plan is the desired workflow, not just a list of eval shards.  It can
contain:

- `wait_checkpoint`: wait until a checkpoint is fully written.
- `prepare_hf_variant`: atomically copy an existing HF export and apply
  validated `config.json` overrides for an inference-only architecture probe.
- `train_until_step`: reserve all scheduler GPUs and train to an exact,
  verified regular checkpoint.
- `terminal_barrier`: wait until dependencies are terminal, including failed
  or permanently unreachable eval rows.
- `teardown_eval`: stop persistent evaluation servers before training resumes.
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

Dependencies default to `deps_mode=success`. Campaign release barriers opt
into `deps_mode=terminal`; merges retain success-only behavior.

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

The 8K RULER, GovReport-long, and extra long-context rows are capability
gated. They are emitted only when a local HF export declares
`max_position_embeddings >= 8192`, the checkpoint's sampled-data metadata
declares `max_seq_len >= 8192`, or an external model is explicitly configured
with `--vllm-max-model-len >= 8192`. A 4K checkpoint therefore receives the
ordinary evaluation graph without invalid 8K rows; `plan create` reports why
the long-context rows were omitted.

The current long-context headline is an engineering comparison suite, not a
clean public benchmark aggregate. In particular, Marathon's public HF test
conversion has no gold answer and is scored for answer-format compliance only;
the Danish EUR-Lex and Nordjylland summarization probes use their available
training splits; and the Danish LongAlign cache is very small. Keep these
metrics for continuity, but label them accordingly in reports and do not
interpret the headline as uncontaminated held-out accuracy.

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

Demand-driven persistent vLLM reuse is opt-in:

```bash
python -m eval_scheduler run \
  --plan-dir logs/scheduler/dfm5_L_step300000 \
  --gpus 0,1,2,3,4,5,6,7 \
  --persistent-vllm
```

Plans may gate GPU jobs on effective free memory:

```bash
python -m eval_scheduler plan create \
  ... \
  --vllm-gpu-memory-utilization 0.25 \
  --min-gpu-free-mib 52000 \
  --judged-vllm-gpu-memory-utilization 0.18 \
  --judged-min-gpu-free-mib 55000
```

The scheduler polls rather than exiting when a ready GPU job cannot meet its
gate. It selects the eligible GPU with the most effective free memory.
Effective memory includes memory that will be reclaimed when an incompatible
persistent server is replaced; a compatible resident server bypasses the gate
because its allocation is already present. HF export jobs release a resident
persistent server before loading the checkpoint. Omitting the gate, or setting
it to zero, preserves the original scheduling behavior.

With this option, each GPU starts a vLLM server only when its first compatible
job is claimed. The scheduler reuses that process for subsequent standard,
DFM, DFM-IFEval, EuroEval, and batched EuroEval IFEval jobs. It replaces the
server whenever the GPU, model/export path, checkpoint tag, EMA mode, Python
executable, host, dtype, context limit, GPU-memory utilization, attention
backend, trust-remote-code setting, extra server arguments, or CUDA root
changes. A failed health check, server exit, OOM, client/server failure, or
callback exception invalidates the lease before retry.

The scheduler stops all remaining pooled servers on normal exit, stop request,
or exception. Pool lifecycle events (`VLLM_STARTED`, `VLLM_REUSE`,
`VLLM_REPLACE`, `VLLM_INVALIDATE`, and `VLLM_STOP`) are written to
`status.tsv`; pooled server logs live under `server_pool/gpu_<id>/` in the plan
directory. The default remains one fresh server or in-process engine per job,
so existing plans are unchanged unless `--persistent-vllm` is supplied.

Internal HRM standard evaluations using `OpenAIEngine` automatically receive
the exported tokenizer, the exact vLLM chat template, and the configured model
context window. Before submitting each request, the engine counts the rendered
prompt and clamps only that request's output budget to the remaining context.
This is required for long MATH prompts: lowering batch size cannot repair an
individual `prompt_tokens + max_tokens > model_context` request. Plan authors
do not need to add an override; `run_standard_openai` supplies this contract
for both fresh and persistent vLLM server paths. External-model jobs retain
their provider-specific behavior.

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

Plain monitor:

```bash
python -m eval_scheduler status --plan-dir logs/scheduler/dfm5_L_step300000
```

Live monitor with per-GPU workload, queue counts, and task-specific progress:

```bash
python -m eval_scheduler monitor \
  --plan-dir logs/scheduler/dfm5_L_step300000 \
  --gpus 0,1,2,3,4,5,6,7
```

Optional Rich live monitor:

```bash
python -m eval_scheduler monitor \
  --plan-dir logs/scheduler/dfm5_L_step300000 \
  --gpus 0,1,2,3,4,5,6,7 \
  --rich
```

The Rich monitor adapts to the current terminal width and height on each
refresh. Its summary is a compact one-line status block, each GPU is shown on
one row, and the ready/blocked tables are truncated to fit the screen with a
final `... N more` row when needed. If one queue section is empty or short, the
unused vertical space is reassigned to the other section. GPU and non-GPU
running jobs share one `Running jobs` table; GPU rows are labeled `GPU0`,
`GPU1`, etc., while checkpoint waits, exports, merges, averages, and reports are
labeled `CPU`.

For a one-shot snapshot:

```bash
python -m eval_scheduler monitor \
  --plan-dir logs/scheduler/dfm5_L_step300000 \
  --gpus 0,1,2,3,4,5,6,7 \
  --once
```

For a one-shot Rich snapshot:

```bash
python -m eval_scheduler monitor \
  --plan-dir logs/scheduler/dfm5_L_step300000 \
  --gpus 0,1,2,3,4,5,6,7 \
  --once \
  --rich
```

## Alternating Training And Evaluation

`pretrain.py` accepts `stop_after_step=N`. After optimizer/EMA step `N`, it
forces a regular `step_N` checkpoint, writes the exact resume sidecar, crosses
the checkpoint barriers, and exits normally. A null value preserves
uninterrupted training.

Build an eval subgraph first, then add its terminal GPU-eval barrier and
teardown:

```bash
python -m eval_scheduler plan add-eval-release \
  --plan-dir "$PLAN" \
  --checkpoint-tag step_50000 \
  --barrier-job-id campaign-barrier-50000 \
  --teardown-job-id campaign-teardown-50000
```

Append the next training segment:

```bash
python -m eval_scheduler plan add-training \
  --plan-dir "$PLAN" \
  --job-id campaign-train-100000 \
  --deps campaign-teardown-50000 \
  --resume-from-tag step_50000 \
  --stop-after-step 100000 \
  --checkpoint-path checkpoints/dfm8/XXL-1epoch \
  --log-dir logs/training/dfm8_XXL_1epoch/step_50000_to_100000 \
  --min-gpu-free-mib 178000 \
  --command 'torchrun --nproc_per_node=8 pretrain.py data=dfm8 ...'
```

The scheduler parses `--command` without a shell. Leading assignments such as
`OMP_NUM_THREADS=1 MKL_NUM_THREADS=1` are accepted and applied directly to the
child environment. It atomically reserves every GPU passed to
`eval_scheduler run`, sets `CUDA_VISIBLE_DEVICES`, replaces/appends
`stop_after_step`, and, when
`--resume-from-tag` is set, verifies and injects the source checkpoint
path/tag while removing stale manual resume-step/epoch/batch overrides.

For a final segment whose exact data-loader exhaustion step is only an
estimate, pass `--completion-checkpoint-tag epoch_N`. The scheduler still
injects the estimated `stop_after_step`, but accepts a clean training exit when
the fully written epoch checkpoint verifies first. Without this option,
training segments retain strict exact-step completion.

The dependency graph deliberately forks:

```text
GPU eval rows -> ordinary success-only merges/sync/averages
             \-> terminal barrier -> server teardown -> next training segment
```

An eval that exhausts retries can leave its merge blocked for later repair
without holding training GPUs idle. The barrier also recognizes eval rows made
permanently unreachable by a failed export. It does not pass while an eval is
running or has a runnable retry. Training/checkpoint failure remains fatal to
the segment.

## Multi-Node Coordinator And Workers

Do not start one unrestricted legacy `run` process per node. Use one
coordinator and one capability-limited worker per node. The coordinator is the
only writer of plan state and the only process that runs merges, syncs,
averages, reports, and cluster training actions. Workers own their node-local
GPUs and persistent vLLM pools.

Prepare an ordered host file with one SSH host per line. Every host must expose
the same repository, environment, plan, data, export, and checkpoint paths.
Start the coordinator on a private reachable address:

```bash
cd /work/dfm/HRM-Text
PLAN=logs/scheduler/<PLAN_DIR>
PATH="/home/ucloud/miniforge3/envs/hrm/bin:$PATH" \
setsid /home/ucloud/miniforge3/envs/hrm/bin/python -m eval_scheduler cluster coordinator \
  --plan-dir "$PLAN" \
  --bind-host <CONTROL_NODE_PRIVATE_IP> \
  --port 8765 \
  --expected-nodes 4 \
  > "$PLAN/coordinator.log" 2>&1 &
```

The coordinator creates `cluster.token` with mode `0600`. On shared storage,
launch all workers from the control node:

```bash
python -m eval_scheduler cluster launch-workers \
  --hostfile config/multinode/hosts.txt \
  --coordinator-url http://<CONTROL_NODE_PRIVATE_IP>:8765 \
  --token-file "$PLAN/cluster.token" \
  --plan-dir "$PLAN" \
  --workdir /work/dfm/HRM-Text \
  --python-env /home/ucloud/miniforge3/envs/hrm \
  --gpus 0,1,2,3,4,5,6,7 \
  --persistent-vllm
```

The SSH launcher records exact worker process-group IDs under
`$PLAN/cluster-workers/launch.json`. Worker logs and manifests are grouped by
node under the same directory. Stop them gracefully, or kill only those exact
recorded process groups:

```bash
python -m eval_scheduler cluster stop --plan-dir "$PLAN"
python -m eval_scheduler cluster stop-workers --plan-dir "$PLAN"

# Emergency path
python -m eval_scheduler cluster abort --plan-dir "$PLAN"
```

Cluster status and the aggregate Rich monitor consume the coordinator's atomic
heartbeat snapshot; they do not run remote `nvidia-smi` on every refresh:

```bash
python -m eval_scheduler cluster status --plan-dir "$PLAN"
python -m eval_scheduler cluster monitor \
  --plan-dir "$PLAN" --rich --interval 30
python -m eval_scheduler cluster workers --plan-dir "$PLAN"
```

Temporarily drain or restore one worker without stopping the cluster:

```bash
python -m eval_scheduler cluster worker-drain \
  --coordinator-url http://<CONTROL_NODE_PRIVATE_IP>:8765 \
  --token-file "$PLAN/cluster.token" \
  --node-id node-02 --drain
```

Plan rows remain backward compatible. New optional TSV fields are
`execution_scope`, `required_capability`, `gpu_count`, and `node_selector`;
missing values are safely inferred from `action`. Capabilities cannot broaden
an action: evaluation workers cannot claim training or W&B-finalization rows.

For a `train_until_step` row, retain the ordinary TorchRun command and add
these values to `metadata_json`:

```json
{
  "multinode_hostfile": "config/multinode/hosts.txt",
  "multinode_python_env": "/home/ucloud/miniforge3/envs/hrm",
  "multinode_nccl_interface": "ib0",
  "multinode_nproc_per_node": 8,
  "multinode_master_port": 29500,
  "multinode_required_paths": ["/work/dfm/HRM-Text/data", "/work/dfm/HRM-Text/checkpoints"]
}
```

The coordinator wraps the TorchRun application in
`scripts/launch_multinode_torchrun.py`, drains eval assignments, obtains
worker teardown acknowledgements, verifies current workers, then launches the
fixed-membership training job. Compatible vLLM servers remain node-local and
are reused using the full checkpoint/EMA/server-configuration key.

Lease tokens include worker boot identity. Late completions from fenced
attempts cannot finalize retried rows. The atomic cluster snapshot allows a
restarted coordinator to reconcile live eval leases; training process
manifests permit adoption of a still-running launcher. This code is locally
tested, but real two-node SSH/NCCL and failure-injection validation remains a
required production gate.

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
  reports standard tqdm progress, live Inspect archive sample progress for
  dfm-evals, and EuroEval nested pass/sample progress such as
  `pass 3/10 samples 137/343`. Standard and batched-EuroEval tasks use tqdm's
  rolling ETA when it is present instead of including server startup in a
  wall-time extrapolation. DFM tasks read the exact sample total and completed
  sample members from the journaled `.eval` archive while the text log is still
  buffered; HTTP completion counts and historical totals remain fallbacks.
  For `train_until_step` rows, it reports progress from the resume checkpoint
  to the forced target and derives ETA from the latest tqdm `it/s` or `s/it`
  rate rather than from the full-epoch progress fraction.
- Active GPU lines and the `next ready` queue include a model/checkpoint label
  such as `hrm-dfm5-L@step_400000:ema`, `hrm-dfm5-L@step_400000:noema`, or
  `qwen35-2b@qwen35_2b:ema`.
- `monitor` also shows a `blocked pending` section when pending jobs are not
  runnable yet. Each line names the job and the unmet dependency IDs with their
  current status, e.g. `blocked_by [eval-00123:running]`.
- For dfm-evals jobs, `monitor` also reads Inspect `logs.json` and the
  dfm-evals text log when available to infer sample totals, and surfaces early
  configuration failures such as missing judge placeholders. Before Inspect
  creates its journal, the task correctly remains at `progress unknown`; once
  the journal exists it reports `samples X/Y`, including generation-heavy,
  judged, translation, summarization, code, and IFEval tasks. At `Y/Y`, the
  monitor says `finalizing` because scoring/export can still be active.
- Managed judge ports are deterministically folded into the valid
  `20000-59999` range. Do not construct them as an unbounded
  `port_base + GPU/shard offset`: uvicorn can silently wrap values above 65535
  while OpenAI clients reject the advertised out-of-range URL.

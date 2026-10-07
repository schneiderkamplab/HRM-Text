# Agent Operating Notes

This repo uses an Open Knowledge Format (OKF) v0.2 bundle under
[`wiki/`](wiki/index.md). Before doing substantial work, read:

1. [`wiki/index.md`](wiki/index.md) for the page map.
2. [`wiki/schema.md`](wiki/schema.md) for OKF authoring and maintenance rules.
3. The task-relevant page under [`wiki/pages/`](wiki/pages/).

## Knowledge Update Rule

When you make or discover durable project knowledge, update the OKF bundle in
the same turn. Keep this file brief; frontmatter, confidence, lifecycle,
linking, refactoring, indexing, and validation rules live in
[`wiki/schema.md`](wiki/schema.md). Durable knowledge includes:

- dataset/source policy decisions
- commands that worked or failed
- dependency/build decisions
- model architecture adaptations
- source-filter changes
- known risks or blockers

If new information contradicts an existing page, do not silently overwrite it. Mark the old claim as superseded and add the new claim with date/context.

## Current High-Level State

- FlashAttention 4 is installed/adapted for B200; FlashAttention 3 was not viable on this machine.
- Training data work is organized around `data/downloads/datasets`, `data/filtered_sources`, `data/converted_sources`, `data/tokenized_mixed`, and `data/sampled`.
- Only Danish DynaWord is intended as raw continuation data. Common Pile has been removed from the downloader manifest.
- Sapient FLAN/Tasksource are denied by default, with narrow allow overrides for selected reasoning/commonsense/science tasks.
- `data_io/tokenizer` must be run from `data_io/tokenizer`, where `Cargo.toml` lives.

## Eval Scheduler Runner Launch

- **CRITICAL**: Prepend `PATH="/home/ucloud/miniforge3/envs/hrm/bin:$PATH"` so `torchrun` and `ninja` are on PATH.
- Always use `--persistent-vllm` for efficiency (reuses vLLM servers across eval shards).
- Launch detached with `setsid` so the runner survives shell timeouts.

```bash
cd /work/dfm/HRM-Text && \
PATH="/home/ucloud/miniforge3/envs/hrm/bin:$PATH" \
setsid /home/ucloud/miniforge3/envs/hrm/bin/python -m eval_scheduler run \
  --plan-dir logs/scheduler/<PLAN_DIR> \
  --gpus 0,1,2,3,4,5,6,7 \
  --persistent-vllm \
  > logs/scheduler/<PLAN_DIR>/runner.log 2>&1 &
```

- Soft stop: `python -m eval_scheduler stop --plan-dir <PLAN_DIR>` (lets running shards finish).
- Clear stop: `python -m eval_scheduler clear-stop --plan-dir <PLAN_DIR>`.
- Status: `python -m eval_scheduler status --plan-dir <PLAN_DIR>`.
- Monitor: `python -m eval_scheduler monitor --plan-dir <PLAN_DIR>`.
- For multi-node scheduling, use [`wiki/pages/model-architecture/multinode-eval-scheduler-plan.md`](wiki/pages/model-architecture/multinode-eval-scheduler-plan.md); never start unrestricted legacy runners on multiple nodes.

## Data Audit Defaults

- Reuse `audit_pipeline` for generation/review and source audits: no request spacing, chunk-tail barriers, or blocking CPU/I/O in the event loop. Reviews return plain `accept` or `reject`, non-thinking, with no JSON/grammar constraints and at most one retry. See [the shared audit runbook](wiki/pages/shared-audit-pipeline.md).

## W&B Metric Logging Safety

- Log checkpoint averages atomically and explicitly register each metric; do not rely only on W&B prefix wildcards.
- For invisible metrics or workspace-selection edits, follow the verified diagnosis and selection semantics in [`wiki/pages/current-state.md`](wiki/pages/current-state.md) under “Atomic W&B average finalization.”

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

## Cooperative Training / Eval Scheduler Model

- **One continuous training per epoch**: per-boundary "train rows" in the
  SQLite plan are suspension/resume cycle markers, not separate training
  segments. `pretrain.py` takes the full schedule at launch
  (`suspend_after_steps: list[int]`, `pretrain.py:163`). Cycle: boundary
  checkpoint → `suspend_ready.json` → scheduler `hold` + cuda-checkpoint
  offload (GPUs drained) → eval block → `restore.request` → in-place
  resume. Killing the trainer instead of offloading discards CUDA memory
  and forces a disk-checkpoint resume. Details:
  [eval-block dependency structure](wiki/pages/model-architecture/eval-block-dependency-structure.md).
- **Eval block shape between suspensions**: wait_checkpoint head → HF
  export → eval families (dfm shards incl. judged rows, ifeval, euroeval,
  standard) → 1:1 result-export rows → per-task shard merges → chained
  averages → report → W&B sync → terminal barrier/teardown. Training waits
  only on GPU inference/export rows in **terminal** mode (failed evals release
  training). CPU exports, merges, averages, reports and W&B sync continue
  alongside training and must not gate it. Never anchor gates
  on barrier/teardown rows (vacuous-cascade poisoning).
- **Audit every row before launch**: all metadata/config paths must exist
  on this machine, data and code deps available, EOCD patch present. Known
  trap: configs authored under `/work/mimir/*` (machine gone) — everything
  lives under `/work/dfm/*` here; the DB is clean but several
  `config/*.yaml|json` files still need the rewrite.
- **Data that never transferred**: the six-language DaLA recovery data and
  the dfm13 `dala-baseline-delta`/`remaining21` groups are gone with mimir —
  those dala suites are skipped in the DB (merges/averages terminalized;
  average scripts tolerate missing inputs). dfm14-based dala suites work
  after the vendored-source remap.
- **Train rows can be cascade-failed** by killing a wrongly-dispatched
  trainer; re-verify every train row is `pending` before relying on a
  terminal gate.

## Current High-Level State

- FlashAttention 4 is installed/adapted for B200; FlashAttention 3 was not viable on this machine.
- Training data work is organized around `data/downloads/datasets`, `data/filtered_sources`, `data/converted_sources`, `data/tokenized_mixed`, and `data/sampled`.
- Only Danish DynaWord is intended as raw continuation data. Common Pile has been removed from the downloader manifest.
- Sapient FLAN/Tasksource are denied by default, with narrow allow overrides for selected reasoning/commonsense/science tasks.
- `data_io/tokenizer` must be run from `data_io/tokenizer`, where `Cargo.toml` lives.

## Eval Scheduler Runner Launch

- **Artifact identity is mandatory**: different checkpoint paths/tags must never share HF export or inference-result directories. Run `check_artifact_isolation` on the complete candidate plan before insertion; path existence alone is insufficient. Preserve `scheduler_export_source.json` receipts, verify attention objective against the checkpoint, and confirm actual inference progress after changing model variants. See [PrefixLM50K incident](wiki/pages/current-state/2026-11-10-dfm11-architecture-comparison.md).

- **Training must launch through the evaluation scheduler** with its checkpoint/evaluation/offload/resume plan prepared and verified beforehand. A CUDA recovery supervisor alone is not the evaluation scheduler. Never start production training standalone and attach evaluations later unless the user explicitly authorizes bypassing the scheduler. Permission to start/resume training or share GPU headroom is not such an override. Existing scheduler-managed in-place resumes are fine.

- **Training continuity is mandatory**: failed evals, unfinished merges/averages/syncs, and abandoned administrative locks must not strand training. Release edit locks before stepping away and verify the handoff actually starts. Respect explicit user pauses and GPU/checkpoint safety. See [training continuity](wiki/pages/training-continuity.md).
- Training code hashes are warning-only provenance, not resume gates. Preserve data/checkpoint/configuration checks and run the continuation preflight after launch changes; see [training continuity](wiki/pages/training-continuity.md).

- **CRITICAL**: Prepend `PATH="/home/ucloud/miniforge3/envs/hrm/bin:$PATH"` so `torchrun` and `ninja` are on PATH.
- Always use `--persistent-vllm` for efficiency (reuses vLLM servers across eval shards).
- Dedicated generator-only evaluation uses `vllm_gpu_memory_utilization=0.95` and calibrated task batches. Co-located judge tasks retain `0.85` for the generator plus their 16 GiB judge reserve; never allocate 0.95 plus a judge on the same GPU. Reduced utilization for temporary GPU co-tenancy is a one-off override, never a new plan default.
- **Validate the combined memory budget before dispatch**: generator allocation + judge reserve + other resident allocations must fit actual GPU capacity with headroom. Never apply a utilization override indiscriminately to paired and unpaired jobs. An impossible budget is a configuration error, not transient occupancy; do not repeatedly defer it.
- **Verify progress after every eval handoff or resource change**: server health alone is insufficient. Check live requests/completed examples, GPU activity and scheduler progress. If runnable work makes no progress for five minutes, investigate immediately; do not wait for the user or keep quoting the old ETA. Preserve explicit user pauses and never restore training onto occupied GPUs. See [stall prevention](wiki/pages/training-continuity.md#evaluation-memory-and-stall-prevention-2026-11-10).
- Launch detached with `setsid` so the runner survives shell timeouts.

```bash
cd /work/dfm/HRM-Text && \
PATH="/home/ucloud/miniforge3/envs/hrm/bin:$PATH" \
setsid /home/ucloud/miniforge3/envs/hrm/bin/python -m eval_scheduler run \
  --plan-dir logs/scheduler/<PLAN_DIR> \
  --gpus 0,1,2,3,4,5,6,7 \
  --persistent-vllm \
  --backend sqlite \
  --cpu-cores 256 --reserve-cores 8 --max-clients 128 --server-concurrency 1024 \
  > logs/scheduler/<PLAN_DIR>/runner.log 2>&1 &
```

- SQLite-imported plans refuse the legacy runner ("SQLite-managed plan requires the
  database runner"); `--backend sqlite` is mandatory for them.
- Do not edit job definitions while rows are claimed: the store invalidates the
  attempt token and the runner dies with "Stale completion token". Stop the runner
  or wait for the row to finish first.

- Soft stop: `python -m eval_scheduler stop --plan-dir <PLAN_DIR>` (lets running shards finish).
- Clear stop: `python -m eval_scheduler clear-stop --plan-dir <PLAN_DIR>`.
- Status: `python -m eval_scheduler status --plan-dir <PLAN_DIR>`.
- Monitor: `python -m eval_scheduler monitor --plan-dir <PLAN_DIR>`.
- For multi-node scheduling, use [`wiki/pages/model-architecture/multinode-eval-scheduler-plan.md`](wiki/pages/model-architecture/multinode-eval-scheduler-plan.md); never start unrestricted legacy runners on multiple nodes.

Cooperative training suspension is opt-in in `pretrain.py`; managed launches
must have exactly one recovery supervisor. See the [suspension runbook](wiki/pages/cooperative-cuda-suspension.md) before changing holds, launchers or evaluation handoffs.

## Data Audit Defaults

- Reuse `audit_pipeline` for generation/review and source audits: no request spacing, chunk-tail barriers, or blocking CPU/I/O in the event loop. Reviews return plain `accept` or `reject`, non-thinking, with no JSON/grammar constraints and at most one retry. See [the shared audit runbook](wiki/pages/shared-audit-pipeline.md).

## W&B Metric Logging Safety

- Log checkpoint averages atomically and explicitly register each metric; do not rely only on W&B prefix wildcards.
- For invisible metrics or workspace-selection edits, follow the verified diagnosis and selection semantics in [`wiki/pages/current-state.md`](wiki/pages/current-state.md) under “Atomic W&B average finalization.”

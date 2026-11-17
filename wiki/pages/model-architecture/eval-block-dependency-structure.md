---
type: Runbook
title: Eval-block dependency structure and suspension cycles
description: Conceptual model of the one-training/many-suspensions cooperative loop, the eval-block dependency shape between suspensions, and the pre-launch row audit.
tags: [training, evaluation, scheduler, cooperative-suspension, planning]
status: draft
last_updated: 2026-11-03
confidence: high
---
# Eval-block dependency structure and suspension cycles

## Conceptual model (supersedes "one train row per boundary")

There is **one continuous training run per epoch**. The per-boundary "train
rows" in the SQLite plan (`train-50000`, `train-100000`, …) are
**suspension/resume cycle markers**, not separate training segments.
`pretrain.py` accepts the whole suspension schedule at launch:
`suspend_after_steps: list[int]` (`pretrain.py:163`, requires
`suspend_control_dir`, default `config/cfg_pretrain.yaml:23`). The process
suspends itself at each listed step via the file-based protocol below.

Superseded claim (2026-11-03, earlier): the "New topology" section of
[b-dfm15-gemma4-epoch1-launch.md](b-dfm15-gemma4-epoch1-launch.md) described
train rows as independent 50K segments chained by dependency gates. The
mechanism is the same at the row level, but semantically it is one training
suspended and resumed, not many trainings.

## Suspension cycle at each boundary N

1. Trainer reaches step N → writes a **regular disk checkpoint**
   (`checkpoint_state_step_N.json` with `checkpoint_kind=regular`,
   `batch_in_epoch_exact=True`, plus `fsdp2_step_N/`) → publishes
   `suspend_ready.json` (all ranks, generation counter).
2. Scheduler row verifies `training_checkpoint_ready(job, N)` — sidecar step
   equals the row target and the checkpoint is complete — then writes
   `hold` ("scheduler owns evaluation interval") and **offloads** CUDA memory
   to host RAM: `python -m training_suspend.controller --cuda-checkpoint
   <binary> offload <active_control_dir> --lease-seconds 86400` →
   `offloaded.json`, GPUs at ~0 MiB. Lease is 24 h.
   - Killing the trainer tree instead of offloading discards the CUDA heap;
     the next resume must load the disk checkpoint (done at step 101500 on
     2026-11-03 — a few minutes of optimizer reload, no correctness risk
     because `batch_in_epoch_exact=True`).
3. Eval block (below) runs on the drained GPUs.
4. Scheduler removes `hold`, writes `restore.request` into the generation
   dir → supervisor-driven controller restore (checkpointed → locked →
   running per rank) → resume receipts consumed → `resumed.json` → training
   continues **in place** from CUDA memory with identical footprint.

State files live under the cooperative control root
(`logs/training/<run>/cooperative_<seg>/attempt-<id>/<id>/`): `active.json`
→ `control_dir`, `queue.json` (persisted `pending`/`consumed` suspension
steps — wins over the launcher's `suspend_after_steps` seed),
`holds`, `suspend_ready.json`, `restore.request`, `offloaded.json`,
`resume receipts`, `resumed.json`, `restart_pending.json`,
`fallback.request`. `run_boundary` in
`eval_scheduler/eval_scheduler/cooperative_training.py` drives the whole
cycle per train row and can be invoked outside the scheduler (it takes
`boundary.lock`, guards against orphaned GPU workers, adopts an alive
launcher).

## Eval-block dependency shape (per boundary)

Idea-level shape — construct with per-row ids/log_dirs per campaign:

1. **Head/gate row** (`wait_checkpoint`): polls for the boundary checkpoint
   (`ckpt_path` + `ckpt_tag`); every eval row transitively depends on it.
2. **HF export first**: export the checkpoint to HF format for the vLLM
   servers (`hf_export_dir` = `exports/<run>_step_N_ema_hf`; tokenizer via
   separate export paths). Eval rows depend on the export being complete.
3. **Eval families** — independent subtrees that may interleave:
   - `eval_dfm` shards (`<task>/shard_s_of_n/<ckpt_tag>` via the persistent
     vLLM pool). **Judged rows** need judge servers (per-GPU
     `transformers_openai_server` judge processes); judge-first rows gate
     their shard batch.
   - `eval_dfm_ifeval` shards (`<root>/ifeval_shard_s/<ckpt_tag>`).
   - `eval_euroeval` rows (euroeval CLI, own log root,
     `<euroeval_log_root>/<ckpt_tag>/<task>`).
   - `eval_standard` rows (`evaluation.main`; per-shard
     `<task>_shard_i_of_N.log` in a shared `<task>` dir — parallel-safe).
4. **Result exports**: 1:1 `export_dfm_results` rows pair with each
   eval row via deps (`defer_dfm_export`); they share the eval row's
   `log_dir` and run immediately after it.
5. **Merges** after all shards of a task complete: `merge_dfm`
   (reads `dfm_log_root/<task>/shard_N_of_M/<ckpt_tag>/inspect/*.eval`),
   `merge_ifeval`, `merge_euroeval` (reads
   `<log_dir>/euroeval_benchmark_results.jsonl`), `merge_standard`
   (reads the per-shard `.log` files).
6. **Averages/report**: chained averages (task-family averages → combined
   averages → one final sink average per block), a comparison `report` row,
   and W&B sync of the averaged metrics (register metrics explicitly; see
   [current-state.md](../current-state.md) "Atomic W&B average finalization").
7. **Terminal barrier + teardown rows** close the block (teardown stops
   judges/pool servers).

### Gating semantics (failure tolerance)

- The **next training cycle** depends on the previous block's terminal
  aggregate rows (final average + report) with **terminal mode**
  (`deps_mode='terminal'`: done OR failed releases) — failed evals must
  never strand training.
- Adjacent **eval blocks** sequence on the previous block's terminals with
  **success mode** so blocks cannot overlap.
- Never anchor a gate on `terminal_barrier`/`teardown_eval` rows: a failure
  cascade completes them vacuously without running (gate-poisoning incident
  2026-11-03; it double-dispatched a train row and shut the vLLM pool).
- Eval rows must never run concurrently with training (exclusive dispatch
  while an exclusive train row is active) — the GPU drain/offload window is
  the only time evals run.
- Row targeting: the train row's `metadata['stop_after_step']`;
  `complete()` = `training_checkpoint_ready` (runtime.py).

## Failure-handling incidents (2026-11-03, B_dfm15_gemma4)

- **dala data never transferred from mimir**: `DaLA/la_output/six_language_candidates_recovery_v1` (19 languages), `data/dfm13/dala-baseline-delta-finalized-20261004-v1/groups/*`, `dala-remaining21-finalized-20261004-v1`, and `dala-dutch-dynaword` do not exist here. Suites using `dfm_evals_multilingual_dala_heldout.yaml`, `dfm_evals_dfm13_dala_v2_existing21_20261006.yaml`, or `dfm_evals_dfm13_multilingual_20261006.yaml` (~432 rows per boundary) cannot run. Remediation applied in the DB: pending shard rows of those configs marked `skipped` (running ones exhaust `max_retries`), paired `export_dfm_results` rows skipped, and **all `merge_*`/`average`/`report` rows flipped to `deps_mode='terminal'`** — the average scripts tolerate missing inputs (`load_metrics` → `{}`), so averages compute over available data and blocks terminate. The dfm14-based dala suites work after the vendored-source remap (`/data/dfm14/evaluation/source/work/dfm/{DaLA,HRM-Text}/` → `/work/dfm/DaLA`, repo).
- **HF publication plan (2026-11-03, user decision)**: all dala languages will be published to HuggingFace under `schneiderkamplab` to replace the lost mimir-local trees. Already public: `dala-{de,fr,es,it,cs,pt_pt,fi,et,ca,el,ro,uk}-audited`, `dala-dutch-dynaword`, `dala-english-common-pile` (with `provenance/` trees matching the manifest pins) and `dfm12-dala-{fo,sv,nb,nn,pl,is}-{acceptability,correction}` (accepted-only training exports, NOT the pinned heldout pairs). Still missing: the 13 dfm13 languages (lt, lv, sq, be, bs, bg, hr, hu, lb, sr, sk, sl, fa) and true heldout test pairs for the six-language set. When uploads land: un-skip the rows and extend `dfm-evals/dfm_evals/tasks/dala_multilingual_heldout.py` to resolve `repo_id`+`revision` from HF, verifying sha256 against the manifest pins.
- **killed dispatches cascade-fail train rows**: killing a wrongly-dispatched trainer leaves its `train_until_step` row `failed`, which permanently blocks the boundary handoff (and the next leg, e.g. `train-250000`). **Re-verify every train row is `pending` before relying on a terminal gate**; reset with `status='pending', attempt=0, token=NULL`.
- **server churn from crash-looping rows**: rows that die within seconds of dispatch leave pool servers client-less → `shared_idle_replacement` kills → neighbors aborted (`status_pending` reverts) → boot storm. Fix the data/config first, then reset victims; euroeval ifeval rows exist under two naming variants (`multi-ifeval-XX` and `ifeval-XX`) — reset both.

## Pre-launch row audit (required)

Before launching any generated/imported plan, audit **every row**:

- All paths in row metadata and in the configs those rows reference
  (suites, manifests, task files, chat templates, binaries such as `uv`,
  `euroeval_bin`, `cuda-checkpoint`) must exist **on this machine**.
- Data availability for every task (datasets, calibration files) and code
  deps importable in `dfm-evals/.venv` and the hrm env.
- The inspect_ai EOCD patch
  (`dfm-evals/.venv/.../inspect_ai/log/_file.py`,
  `read_eval_log_headers_async` skips unparsable logs) is present.
- `queue.json` pending list matches the boundary schedule.
- Known trap: configs authored on the **mimir** machine reference
  `/work/mimir/*`; that machine is gone — everything lives under
  `/work/dfm/*` here. Verified 2026-11-03: the SQLite DB contains zero
  `/work/mimir` references, but `config/*.yaml|json`
  (`dfm_evals_multilingual_dala_heldout.yaml`, `dfm_evals_dfm14.yaml`,
  `dfm14_dala_eval_registry.json`, dala registries/manifests,
  `dfm13_sources.json`) and `dfm-evals/scripts/prepare_dala_heldout_manifest.py`
  still carry them — caused instant-crash retry loops (`FileNotFoundError`
  at task load) and pool `shared_idle_replacement` churn. Rewrite to
  `/work/dfm` before eval rows that use those configs run.

## 100K block partial-input averages and queued repair (2026-11-03, evening)

Confidence: high for origin-history findings (direct wandb.ai API scans);
medium for mirror-lag interpretation (user-reported, forge.coreweave.com view).

- Terminal-mode averages at 100K released while rows were still failed (the
  NLTK umask-0002 / missing-manifests outage window), so several average
  writers computed from partial inputs. Server-side result: 253 per-task
  subkeys missing at 100K (194 euroeval CI/count subkeys, 42 dfm_eval dala
  subkeys, 15 avg_population multilingual/english bookkeeping keys, 2 MMLU
  subkeys). All 12 aggregate epoch series and the consolidated average row
  (`headline_avg_v3/epoch=0.19494...` with values on the same history row,
  internal step 150136) ARE intact at wandb.ai origin — verified by
  `run.scan_history` key-set diffs per block epoch.
- The user's forge.coreweave.com/wandb mirror showed averages without the
  100K point despite intact origin data → mirror lag/cache suspicion. A
  direct API check of the mirror failed (API key rejected; SSO-only). Check
  the origin URL to discriminate mirror lag from viewer-side selection.
- Repair (final design, 2026-11-03 ~20:00): serialize the W&B section of the
  writer scripts with an advisory flock instead of DAG surgery. New
  `scripts/wandb_writer_lock.py` (`/tmp/wandb_writer_<run_id>.lock`, env
  `WANDB_WRITER_LOCK` overrides) wraps resume->define_metric->log->finish in
  `scripts/log_multilingual_headline_averages.py` (`log_atomic`),
  `scripts/backfill_external_eval_to_wandb.py` (main W&B section; serves the
  default + `--atomic-v3-averages` average rows), and
  `scripts/log_expanded_dala_v2_averages.py` (`log_atomic`). Verified by a
  3-process test: strict hand-off 1.5 s apart. Effective for future dispatches
  without a runner restart (average actions run as subprocesses).
- DAG-edge chaining of average rows was attempted first (72 terminal edges
  across 9 blocks) and REVERTED: the plan already contains cross-deps among
  the average family (`multiling-average` depends on `average-600575`;
  `wave34-average` depends on `multiling-*`; `dfm14-eval-average` depends on
  `dala-v2`, `todo5`, `multiling-*`, `average-600575-*`), so naive linear
  chaining created cycles and deadlocked the reset rows. Original order:
  average-600575 → multiling → wave34 → dala-v2 → dfm14-eval.
- `Action.TEARDOWN_EVAL` is a runner no-op (`server_pool.close_all();
  return 0`, runtime.py:2428) — teardown rows do NOT write W&B despite
  `log_wandb=true` metadata (that flag is plan-wide, carried by every row;
  writer identification must go by action/script, not the flag). The report
  row's `generate_dfm5_l_eval_comparison_report.py` also writes no W&B
  history. Remaining unpatched writers in other plans (not used here):
  `scripts/log_long_context_headline.py`, `scripts/relog_project_averages_v3.py`.
- 100K re-run set queued (10 rows reset to pending/attempt=0: multiling,
  multiling-semantic-v1, dala-v2, todo5, wave34, dfm14-eval, average-600575,
  average-600575-semantic-v1, wave34-teardown, report-600576). The runner
  cannot dispatch them while the exclusive training leg runs; they fire at
  the 200K boundary and re-log atomically from complete inputs under the
  new lock. Watch the dispatch order (pre-existing family deps apply).
- Operational lesson: resetting post rows mid-plan works only when no
  exclusive (training-leg) row is running; otherwise they queue until the
  next boundary. Concurrent average writers resume the same W&B run and can
  race on the next internal history step; aggregates survived the 100K race,
  but verify per-writer payloads after any batch re-run.

- Monitor training-lane progress reads
  `logs/training/.../to_<target>/train_until_step_<target>.log` →
  `cooperative_0_to_epoch1/training.log`. That was a regular file holding the
  frozen morning supervisor log (last rate-match 102850), so the TUI showed
  0.0%. Fixed 2026-11-03 ~19:45 by repointing
  `cooperative_0_to_epoch1/training.log` → `relaunch_102850.log` (the file
  the spawned launcher's ranks append to). Spawned legs keep appending to
  that same file, so the monitor tracks all later boundaries without further
  repointing.

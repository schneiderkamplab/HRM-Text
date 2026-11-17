---
type: Runbook
title: B DFM15 Gemma-4 epoch-1 production launch
description: Managed B-size Gemma-4-262k training on sampled_dfm15 via the cooperative eval-scheduler launch, with the step-count derivation, fresh-start support and reset/import cycle.
tags: [training, evaluation, scheduler, cooperative-suspension, wandb]
status: draft
last_updated: 2026-11-09
confidence: high
---
# B DFM15 Gemma-4 epoch-1 production launch

## Configuration

- Model: HRM v2 size preset **B** (`config/arch/size/B.yaml`: 1024 hidden, 12
  layers, 8 heads) + Gemma-4 262k tokenizer, single_unit FSDP, GAS=1, GBS
  262144, BP 2→8 within the first 50K-step boundary, bf16, compiled.
- Data: `sampled_dfm15` (epoch = 408,412,700 rows / 134,108,218,034 tokens).
- W&B: project DFM5 (peter-sk-sdu), fresh run id `B-dfm15-gemma4-epoch1`
  (`wandb_resume=auto`: creates the run for row 1 and resumes it for rows 2+;
  `must` would fail a fresh run). The earlier run
  `B-dfm15-gemma4-epoch1-bp2to8` contains ~1,100 steps of a mislabeled XL run
  and is abandoned.

## Step-count rule

The LPT bin capacity `c` is `batch_max_length = local_batch_size =
GBS / (world_size * gradient_accumulation_steps)` (`pretrain.py:258`,
`multipack_sampler.py:123/:164`). Changing GAS therefore changes the packing
and the step count; re-simulate with
`.tmp_vocab_probe/boundary_cursors_c32.py` (numba, ~4 min full pass) before
trusting totals or per-boundary cursors.

- GAS=1 (c=32768): **512,923 steps** per epoch (bin efficiency 0.99754).
- GAS=2 (c=16384): 1,028,575 groups → 514,287 steps.
- The 50K-step boundaries sit at the same token positions (13.1B tokens per
  50K steps) in both configurations, so BP warmup ratio is 50000/512923 =
  0.097481 and the cosine decay window is 450,000 → 512,923 (last full 50K
  block + tail).

## Plan generation

`scripts/schedule_B_dfm15_epoch1.py` derives the full managed plan
(24,244 rows: 11 boundaries × 2,203 eval rows + 11 cooperative train rows) from
the transferred `dfm15-xl-3800000-eval-*` suite in
`incoming/mimir-xl-20261015/transfer-state/final/scheduler-backup.sqlite`.

- `--resume-tag none` = fresh first row; rows 2+ always resume from
  `step_{previous boundary}` (`resume_from_tag`).
- Reset cycle when regenerating: stop the runner, `rm database.json
  stop.request` under the plan dir, run `--apply`, wipe
  `/tmp/dfm15-B-production/jobs.sqlite*`, then `eval_scheduler database
  import ... --runners-stopped`, then relaunch. The first import marks the
  plan dir SQLite-managed and `write_plan` refuses afterwards.
- Verify train-row metadata in the imported DB (definition JSON key
  `metadata_json`) before launching.

## Fresh-start cooperative rows

`eval_scheduler/eval_scheduler/cooperative_training.py` treats
`resume_from_tag` as optional now: absent → the supervisor spawns the training
command without resume overrides, enabling a continuous step-0 chain. With a
tag, the referenced checkpoint must be complete (`checkpoint_ready`) before
spawn. The launcher restores suspended workers across boundaries
(`restore.request`), so no interrupt/restart occurs after the initial spawn.

## Mislabeled-XL trap

Hydra defaults select `arch/size@arch: XL` (1536×32). A B run launched without
the size override is XL-sized at ~1.27 s/step; its checkpoints (zL_init
[1536]) cannot load into a B model ([1024]). The discarded run's checkpoints
live under `checkpoints/hrm_v2/B-dfm15-gemma4-epoch1-mislabeled-xl/`. Always
pass `arch/size@arch=B` explicitly.

## Live state 2026-11-03

- Runner launched against `logs/scheduler/B_dfm15_gemma4_epoch1_20261103`
  (SQLite backend, persistent vLLM, GPUs 0-7). Train row
  `b-dfm15-train-50000` running under the cooperative control root
  `logs/training/B-dfm15-gemma4-epoch1/cooperative_0_to_epoch1`.
- Measured 5.85 it/s (~0.171 s/step) at step ~200. The `b_g4su` bench
  median 0.3023 s/step was measured at **constant bp=8** (the bench series
  passes `bp_warmup_ratio=0.0`), with FIXED_* padding and on sampled_dfm6;
  the live run's bp2 rate is not directly comparable. Live rates across the
  bp ramp: bp2 0.171, bp4 ~0.223, bp5 ~0.244, bp6 ~0.256 s/step, with bp8
  expected around 0.27-0.28 — slightly better than the bench, which carried
  the FIXED_* overhead.
- Verified in the live `all_config.yaml`: B arch (1024/12/8), GAS=1,
  total 512923, decay 450000→512923, `wandb_resume=auto`, fresh W&B run
  `B-dfm15-gemma4-epoch1` syncing in DFM5. Ephemeral `step_3000` state JSON
  confirms GAS=1, GBS 262144, local 32768, 766 rows/260861 tokens per step;
  checkpoint totals 703,595,520 params (262144×1024 embed + untied head).
  Document lengths: max 4096 (capped), median 110, mean 328.

## Suspension mechanism notes

- Requests: write `suspend_after_steps` (plain step numbers) into the ACTIVE
  control dir (`active.json` → `control_dir`; the sanctioned CLI is
  `training_suspend.controller request <control_dir> <steps>`). The
  cooperative root file is only read by the supervisor's disk-fallback
  restart path. The hook polls every `suspend_poll_interval_steps`.
- Gap found and fixed 2026-11-03: an out-of-band suspension below the row's
  target published `suspend_ready.json` but the row's wait loop only handled
  `ready['step'] == target`, hanging the trainer until resume receipts were
  written manually. `cooperative_training.py` now restores such suspensions
  (guarded by the supervisor's `resumed.json` match) and completes the row if
  a stale-at-target suspension already resumed with a complete checkpoint.
  A live runner keeps the old module until it is restarted; the gap is only
  reachable via manual out-of-band requests, so avoid those until restart.
- The end-to-end round trip verified live at step 4300: request → checkpoint
  → suspend_ready (8 ranks) → resume receipts → resumed.json, no restart,
  identical memory footprint, full step rate.
- Full offload/restore cycle verified live at step 5060 (generation 2):
  request → regular checkpoint `step_5060` → suspend_ready → manual
  `hold` → `controller offload --lease-seconds 86400` drained all 8 GPUs to
  4 MiB (`offloaded.json`, remaining_owned_mib 0, 8 ranks) → `restore.request`
  into the generation dir + hold removal → supervisor-driven controller
  restore (checkpointed→locked→running per rank) → 8 resume receipts consumed
  → training continued in-place at step 5060 with identical memory (39.4 GiB
  reserved) and full 5.75 it/s. Host needs ~8×40 GiB for the dumps (3 TB RAM
  available). At real boundaries the scheduler performs exactly this
  sequence, with the eval block running while GPUs are drained.


## 50K boundary incident and plan rewiring (2026-11-03)

At the first real boundary the scheduler offloaded correctly, but the eval
block never ran and training resumed ~40 s later:

- **ckpt_path rewrite gap**: the generator rewrote the train command's
  `checkpoint_path` but not the eval rows' `ckpt_path`, which still pointed
  at `checkpoints/dfm15/XL-from-dfm14-epoch1` (the source campaign's dir,
  which only holds 3.83M+ checkpoints). The block's `wait_checkpoint` head
  polled that dir forever, so the whole 50K block stayed pending behind it.
  Fixed by a bulk `store.update_jobs` metadata edit (24,210 rows) after a
  `store.backup`; the already-RUNNING wait row was failed with its claim
  token, edited, and reset to pending. The generator now maps the source
  checkpoint dir to `CKPT_DIR` in `rewrite()`.
- **Instant-fire barrier starvation**: the `train-evals-terminal` barrier
  (copied from the single-segment dfm15-XL plan) depends only on the train
  row, so it completed immediately and released the next train row. With the
  database runner's exclusive dispatch (while an exclusive train job runs,
  nothing else is dispatched, and a ready exclusive job is always claimed
  first), every next train row would have been claimed before any eval row:
  eval blocks would starve forever.
- **Source mechanism** (from the dfm12→dfm15 lineage backup,
  28 train rows): layout is `train-N`, `block(N)`, `train-N+50K`, …, and each
  next train row depends on ~1,239 downstream rows (merges, averages,
  teardowns — the sinks) of the previous block with `success` mode. Barriers
  gate only epoch finals. Blocks are therefore inherently sequential and run
  in the offload window between train rows.
- **New topology** (faithful, failure-tolerant): `train-N+1` deps =
  `[train-N] + block(N) terminal rows` with `deps_mode='terminal'`
  (done/failed/skipped all release training — eval failures cannot strand
  training); `block(N+1)` head deps additionally include `block(N)`
  terminals (`success` mode) so adjacent blocks cannot overlap. Generator
  emits this natively (`block_terminals()`, `train_rows(..., terminals)`,
  head-gate injection in `clone_block`); the live plan was rewired with the
  same edits via the store.
  - **Superseded 2026-11-03 (later)**: the per-boundary train rows are
    suspension/resume cycle markers of ONE continuous training, not separate
    training segments; `pretrain.py` takes the full suspension schedule at
    launch (`suspend_after_steps: list[int]`, `pretrain.py:163`). See
    [eval-block dependency structure](eval-block-dependency-structure.md).
- User directive: eval blocks must NOT run in parallel (with training or
  each other). The topology enforces this: evals only dispatch when no
  exclusive train job is active (GPUs drained), and block N+1 waits for
  block N's terminals.

## Manual suspension surgery and eval-flow incidents (2026-11-03, later)

- **Manual out-of-band suspension at step 101500**: user paused training between
  the 100K and 150K boundaries so the delayed eval blocks could run. Sequence:
  `controller request <active> 101500` → verify
  `checkpoint_state_step_101500.json` + `fsdp2_step_101500/.metadata` → write
  `hold` into root+active → SIGKILL the whole tree (launcher, supervisor,
  torchrun, 8 ranks — ranks are separate session leaders) + the launcher's
  nccl-shim redis → row `train-150000` flips failed → flipped to `done` via
  `update_jobs`; `block(150000)` (2,203 rows) marked `skipped`;
  `train-200000` re-gated and `resume_from_tag='step_101500'`;
  `queue.json` pending list edited to drop 150000 (the hook persists consumed
  steps there and it wins over the launcher's `suspend_after_steps` seed).
  No offload/dumps needed: killing frees GPU memory.
- **Vacuous-cascade gate poisoning**: the failure cascade completes
  terminal-mode rows (barriers) and their success-mode dependents (teardowns)
  *without running them*. Any gate anchored on those rows is instantly
  satisfied — train-200000 dispatched and shut down the vLLM pool mid-block.
  Rule: anchor gates only on rows that are still `pending` and aggregate real
  work (block averages, merges, report rows). `head(100000)` kept 3 real
  anchors of 6, which was sufficient.
- **Runner crash class**: editing a claimed row's definition invalidates its
  attempt token; the runner then dies with "Stale completion token" when the
  future completes. Restarted with the full database-runner invocation
  (`--backend sqlite --cpu-cores 256 --reserve-cores 8 --max-clients 128
  --server-concurrency 1024`); the legacy runner refuses SQLite plans.
- **inspect_ai EOCD race (patched)**: each eval worker, after finishing, runs
  `write_log_dir_manifest` over the *shared* `inspect/` log dir and crashes on
  sibling workers' mid-write `.eval` zips ("EOCD not found") — the row fails
  after its eval succeeded, burning retries. Patched
  `dfm-evals/.venv/.../inspect_ai/log/_file.py`
  `read_eval_log_headers_async` to skip unparsable logs. Re-apply this patch
  if `dfm-evals` is ever re-synced.
- **Cold WekaFS venv**: first use of `dfm-evals/.venv` on this node crawls
  (~60 KB/s per worker, D-state imports). A parallel bulk read
  (`find .venv -type f | xargs -P24 cat`) warms the cache; later boots are
  fast. Keep this in mind for fresh nodes.


## Final epoch 3 full EuroEval follow-up (2026-11-09)

User authorized the full all-language zero-shot and few-shot validation campaign
for the final B checkpoint, step 1,538,769, after GPUs become free. The detached
watcher is in `/work/dfm/euroeval-runs/mimir-B-epoch3-step1538769-validation/launch-scripts/wait_for_epoch3.py`;
its current state is `queue-status.json` in that campaign directory.

The campaign **reuses** the training scheduler's
`exports/B_dfm15_gemma4_step_1538769_ema_hf` export via a symlink; no independent
conversion is scheduled. It waits for the final scheduler block to become
terminal, its HF export row to be `done`, all required export files to exist,
and all eight GPUs to be unused across three checks. It then verifies tokenizer
parity and exported weights before launching eight persistent TP=1 servers.
The configuration uses EuroEval 18.2 source captured with the earlier v1.8 run,
69 language/mode jobs, 741 expected unique records, concurrency 64, 0.95 GPU
memory utilization, FLASH_ATTN, 8,192 context, and thinking disabled. CPU scoring
releases client scheduling capacity. Servers are stopped after the campaign.
The submission label `danish-foundation-models/DFM-Mimir-B-epoch3-step1538769`
is local provenance, not a published Hugging Face repository or release version.


### Corrected final checkpoint and CPU-only tail (2026-11-09)

The planned step 1,538,769 was superseded by the actual `epoch_3` checkpoint
at step 1,538,766. The training scheduler completed its export to
`exports/B_dfm15_gemma4_step_1538766_ema_hf`. The full EuroEval watcher now
reuses that export and labels results `DFM-Mimir-B-epoch3-step1538766`.
The campaign directory retains its original planned-step name for continuity.
After all final-block GPU work becomes terminal, remaining `average` and
`report` rows do not block the full campaign; three free-GPU checks and absence
of active GPU jobs are still required. This supersedes the earlier all-rows
terminal gate, which unnecessarily waited for CPU-only reporting.


### Two-checkpoint full EuroEval queue (2026-11-09)

User additionally authorized full evaluation of the existing 1.5M EMA HF
export. Final epoch 3 passed CPU weight/tokenizer verification and its launcher
started first; `/work/dfm/euroeval-runs/mimir-B-step1500000-validation` waits
for that launcher to finish and release GPUs, then verifies and evaluates
`exports/B_dfm15_gemma4_step_1500000_ema_hf`. Both campaigns use eight persistent
TP=1 servers, 69 language/mode jobs and 741 expected unique records. No HF
conversion is scheduled. The 1.5M watcher is `launch-scripts/wait_after_epoch3.py`
under its campaign directory. Both preserve the scheduler's native Gemma chat
template as a campaign-side file because these HF exports omit a template file.

### Native tokenizer startup correction (2026-11-09)

The first full epoch-3 launch passed structured JSON generation on eight replicas but stopped before benchmarks because server token IDs differed from the raw training tokenizer. Both HF exports set `fix_mistral_regex=true` in `tokenizer_config.json`. CPU verification had explicitly overridden this to false, while default vLLM loading respected true. Both campaigns now use a separate `tokenizer-native/` directory with that flag false and an explicit `--tokenizer` argument; exported weights and tokenizer files remain unchanged. Default-loading parity was verified against the saved raw-training probe. A transformer48 training run started concurrently, so the corrected epoch-3 launcher waits for all GPUs to become free; the 1.5M watcher waits behind epoch 3. No benchmark results were produced by the rejected startup.

### Concurrent 80 GB EuroEval budget (2026-11-09)

At user request, both B checkpoint campaigns now run sequentially alongside training, beginning with epoch 3. Each of eight TP=1 servers uses an explicit 64 GiB KV cache (68.72 decimal GB), leaving over 11 decimal GB within the requested 80 GB per-GPU headroom for weights and runtime. The explicit KV allocation avoids concurrent-training changes affecting automatic memory profiling; gpu-memory-utilization is 0.39 but does not size the cache when explicit KV bytes are set. The startup gate now requires 80 decimal GB free on every GPU, permitting existing training processes. Context remains 8192 and concurrency 64. Native tokenizer override and pre-evaluation parity/JSON/long-context smoke checks remain enabled.

### User-requested drain (2026-11-09)

New dispatch was frozen with SIGSTOP on the epoch-3 scheduler; existing language/mode clients continue unchanged. The 1.5M watcher was stopped and its queue status marked paused. `launch-scripts/drain_current.py` records client completion, waits for all active clients and final submission export, then interrupts the owned evaluation launcher and terminates the frozen scheduler, releasing only evaluation servers. Queued jobs and native result files are preserved. After drain status is paused, resume by relaunching `launch-scripts/launch_when_free.py` in the epoch-3 campaign; it reads the existing scheduler state and dispatches queued jobs. Restart the 1.5M `wait_after_epoch3.py` watcher only after the predecessor launch status has been reset to running/waiting, to avoid stale terminal status. Memory budget remains 80 decimal GB per GPU with 64 GiB explicit KV allocation.

### Resume after completed drain (2026-11-09)

The drain finished cleanly: 34 language/mode jobs completed, 35 queued, and 431 unique records saved; all evaluation servers exited. On explicit user request, relaunched the epoch-3 launcher from preserved state and restarted the dependent 1.5M watcher. Both retain the concurrent-training 80 GB per-GPU budget, 64 GiB KV cache, eight persistent replicas, and native tokenizer parity checks.

### 1.5M parallel CPU scoring (2026-11-09)

User requested 64 scoring workers per call with a shared 256-core budget. The 1.5M client now replaces only the hallucination detector call with campaign-local `launch-scripts/parallel_scoring.py`. Each subprocess uses one Torch/OpenMP/MKL/BLAS thread, and global advisory lock slots cap concurrent scoring workers at 256 across languages. Independent answer shards retain the canonical detector, maximum context, token-budget skip rule, and integer hallucinated/total token aggregation. Shared EuroEval source and epoch-3 scoring were not modified. An English three-answer test produced exactly the same sequential and parallel rate (0.25925925925925924); lock checks verified 256 exclusive slots. Validation log is saved in the campaign root. Epoch 3 finished while this was being prepared; the modification was installed before 1.5M clients launched.

### Parallel scoring rate-limit recovery (2026-11-09)

The initial parallel scoring implementation caused concurrent Hugging Face metadata requests and HTTP 429 errors across language clients. Workers now resolve detector snapshots with local_files_only=True and use local paths under HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE, eliminating worker hub requests. The parent repository existence query was removed for future clients. Already-imported clients may still hit the old parent query until they exit. A detached `launch-scripts/retry_scoring_failures.py` watcher waits for the current launcher to finish and release servers, then requeues failed jobs from preserved state for up to two retry passes. Saved native records are preserved. Shared worker budget remains 256 and per-call maximum 64.

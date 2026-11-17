---
type: Runbook
title: SQLite and Request-Shared Evaluation Scheduler
description: Opt-in durable job state, CPU-bounded clients, and demand-driven shared inference without changing live TSV campaigns.
tags: [evaluation, scheduler, sqlite, vllm, performance]
status: draft
last_updated: 2026-10-19
confidence: high
---
# SQLite and Request-Shared Evaluation Scheduler

## Scope and Rollout

### 2026-10-19: Bound startup client imbalance

The gated Mimir2 campaign accumulated 57 clients on GPU5 while other replicas
were starting, leaving a single-GPU tail after the other devices drained.
Least-held placement alone did not help because it excluded loading replicas.
`SharedServerPool` now allows at most two residency holders per ready replica
while a compatible replica is provisioning (the loading replica has one
prospective holder). Additional clients wait on the condition; once startup
finishes, ordinary least-held assignment resumes. Unrelated model/judge startup
does not throttle compatible ready servers. Idle devices are still provisioned
on demand. This applies on the next scheduler launch, not to already pinned
clients; the live gated evaluation was not interrupted.

Regression tests cover delayed startup, bounded placement, balanced assignment
after startup, unrelated compatibility groups, failure fencing and safe drains.
This fixes startup pile-ups, not duration imbalance among already-running
direct clients. Per-request migration/load balancing is **not implemented**:
the broker was deliberately removed on October 10. Any future request-routing
replacement needs compatibility/judge isolation, response/model-name handling,
in-flight drain safety and scoring parity tests before production use. Actual
request queue telemetry remains unknown in the direct pool snapshot; client
counts must not be mislabeled as queued requests.

XXL-wide migration, suspension and retries are documented in
[XXL-wide handoffs](xxl-wide-scheduler-handoffs.md).

### 2026-10-13: Comparable epoch-10 backfill before 3600K

`scripts/schedule_epoch10_comparable_backfill.py` updated the existing
`logs/scheduler/dfm12_XL_epoch11_noidentity` SQLite plan without interruption:
finish training to 3600K; epoch-10 missing evaluations and publication/averages;
3600K export/evaluations; the existing 3600K-to-3650K training segment.

Uses the original XL epoch-10 **EMA** export
`exports/dfm11_XL_epoch10_multilingual_ema_hf`, checkpoint step **2877261**,
fractional epoch **10.0**, and the original XL W&B run in DFM5. It reuses 256
checkpoint-bound completed task summaries and schedules 184 missing tasks:
100 DaLA/DaLA-v2 tasks (400 inference shards) and 84 EuroEval tasks. Including
400 DFM result exports, 184 merges, eight average jobs and the completion
barrier, this adds 1077 rows. Current calibrated batch sizes, compiled persistent
vLLM configuration, and training-tokenizer behavior are inherited from the
3600K definitions. No VALEU tasks are added.

`epoch10-comparable-backfill/` contains copied summaries, source hashes,
`receipt.json`, preview TSV and the pre-edit SQLite backup.
Historical core EuroEval summaries with train-step zero are rebound in the
copies only, using their completed epoch-10 jobs and checkpoint state; original
artifacts are unchanged. The completion barrier
retains the existing terminal-failure policy so an exhausted backfill failure
does not strand all GPUs indefinitely; incomplete averages must still be repaired.

### 2026-10-12: Client environment-lock starvation

Implemented after authorization: SQLite startup synchronizes each unique pending
DFM project once under its runner lifetime lock, before any GPU dispatch. Legacy
startup also performs this preparation. Sync uses `uv sync --locked --inexact`
to preserve optional installed packages and refuse lockfile drift. All shared
runtime `uv run --project` client/publication commands add `--no-sync`; standalone
EuroEval `uv run --no-project --with ...` commands are unchanged. A failed sync
fails startup rather than silently running an unprepared environment.
During rollout, soft-stopped the coordinator and terminated only its childless
DFM uv launchers (121 exact PIDs recorded in `uv-lock-cancelled-pids.json`).
Completed work was retained; the same plan resumes remaining work with
`resume-sync-once-3500k.log`. Environment setup logs are `environment-sync-N.log`.
Scheduler tests: 206 passed.

The one-time sync also waited on the Weka environment lock.
After stopping that sync and confirming no local process had the lock file open,
preserved the old `.venv/.lock` as `.lock.recovery-*` and allowed uv to create
a fresh lock. Sync then succeeded, checking 186 packages in 11ms with no
dependency changes. Do not automatically rotate locks: establish that no
environment writer is active first. The exact cause of the stale distributed
lock was not determined. Evaluation/publication resumed in the same plan.

During 3500K, a 30-second sample showed 0 queued requests on every server,
0-4 running requests across sampled instants, and 0-0.2% KV use. Meanwhile
105 `uv run` processes had no evaluator children; several had waited minutes.
An isolated `uv -v run --project dfm-evals python -c ...` reported waiting
for the exclusive `dfm-evals/.venv/.lock` and timed out after 10 seconds.
The corresponding `uv run --no-sync` interpreter probe completed in 56ms.
Thus this observed idle period is client environment synchronization starvation,
not insufficient server memory or batch size. Prepare/synchronize the environment
once before a campaign and bypass synchronization on per-task launches; increasing
client concurrency alone adds lock waiters. No live clients were restarted for
this diagnostic. The previous ETA was not a guarantee under this bottleneck.

### 2026-10-11: Full-campaign elapsed-time comparison

Measured from checkpoint export-ready timestamps to the final 50-language
average log's last write (includes evaluation, merge, sync and averaging):

| Checkpoint | Export ready to final average | Training end to next training launch |
| --- | ---: | ---: |
| 3300K | 3h51m02s | 3h53m56s |
| 3350K | 2h53m21s | 2h54m57s |
| 3400K | 1h43m10s | 1h43m50s |
| 3450K | 1h34m49s | 1h43m14s |

Sources: `logs/scheduler/dfm14_XL_noidentity/checkpoints/step_*/export_hf_step_*.log`,
`logs/scheduler/dfm12_XL_epoch11_noidentity/dfm14-averages/step_*/multilingual_average.log`,
and `logs/training/dfm14_XL/step_*/train_until_step_*.log`.
Training-end and final-average boundaries use file modification times; next
training launch uses its explicit log timestamp. The 3400K wall window includes
the reboot/recovery and retry delays. The 3450K pause includes historical
Andersen backfill activity before export readiness. These are observed campaign
times, not isolated scheduler-speed benchmarks or GPU-active durations.

### 2026-10-11: Maintenance recovery at 3438K

Maintenance again removed the local `/tmp` SQLite authority. Restored from
`state.backup.sqlite` using SQLite backup after `quick_check=ok`, with no live
workers or GPU processes. Only `dfm14-xl-step_3450000-train` was interrupted;
fenced its old claim and reset it to pending with
`resume_from_tag=ephemeral_step_3438000`. Validated DCP metadata against all
eight shard extents. Completed evaluations and all 56 Andersen backfill rows
were retained. Recovery backup: `maintenance-recovery-3438000-before.sqlite`.

The handoff receipt had retained the previous 3650K cosine-start script hash.
Reconstructing that one old literal exactly matched its hash; refreshed only
this pin to the approved 3500K start (3750K end, 1e-5 floor), preserving the
old receipt. All other pins and the prepared-data hash matched unchanged.
W&B authentication to the original XL run was verified before launch.
Runner uses the hrm CUDA_HOME/PATH above, SQLite, persistent servers and 64
clients. Log: `resume-maintenance-3438000.log`; monitor: `hrm-0:4`.

### 2026-10-10: Broker code removed

Supersedes all historical proxy/gateway launch instructions below. The HTTP
broker, NativeGatewayHost, broker load simulations and broker-only tests were
removed. SharedServerPool supports direct connections only; it rejects the old
`gateway` constructor option. The multilingual benchmark accepts only `direct`
and `legacy`. `validate_shared` is now a direct-endpoint repeatability canary,
not evidence of transport equivalence with a separate broker.

The native-template compatibility proxy is retained: it adapts model prompts
and responses, not scheduler admission. CPU budgeting, replica ownership,
judge pairing, failed-client fencing and exclusive training drains remain.
Historical benchmark results below are retained as evidence, not runnable
instructions for the removed implementation. No running process was restarted
for this cleanup.

### 2026-10-10: Resume training despite exhausted evaluation failures

Applied `training_continuation.allow_failed_evals` to all seven remaining
transitions after the 3450K evaluation, through the final epoch segment.
Each training row now requires its previous training segment to succeed and
a terminal-mode barrier over its former evaluation/post-processing dependencies.
Thus exhausted eval/sync/average failures, and downstream work impossible because
of them, no longer prevent training. Running work still drains; queued retryable
work still runs. The runtime continues to validate the resume checkpoint and
confirm owned servers are stopped before starting training. Failed metrics are
not fabricated or marked successful. Current 3400K finalization is unchanged.

This supersedes the judge-first success-gate decision below: judged-phase gates
are terminal-mode again, allowing ordinary evals after judge failure. The new
training barriers stop failure propagation into future epochs, while explicit
previous-training success prerequisites prevent skipping actual training.
The earlier prematurely completed gates had already been reset before this edit.
Backup: `before-training-failure-policy.sqlite`. Regression tests cover failed
inference, export, sync, failed prior training, and still-running inference.

### 2026-10-10: Admission starvation and 3400K tail recovery

Talemaader shards 4/8 and 6/8 timed out before inference with `Compatible
replicas still starting`. The global startup-balancing wait blocked usable
replicas while others loaded; its generic TimeoutError became a permanent
failure. Supersedes the earlier first-ready-replica startup protection: ready
servers now accept work immediately, with least-held balancing after other
replicas load. A dedicated ServerCapacityTimeout applies only to admission
before requests are submitted. The runner returns that claim to PENDING
without consuming its attempt budget; actual startup/inference/drain failures
retain their existing handling. Verified with 37 direct-pool/runner tests,
including max_retries=0 admission deferral followed by training continuation.

At recovery, 1042/1044 inference jobs were complete. Reset only the two failed
shards and restarted the existing SQLite plan with the fix. Remaining work:
two exports, Talemaader merge, nine averages and report, then the original
3400K-to-3450K training continuation. Log: `resume-talemaader.log`.

### 2026-10-10: Judge-first future checkpoints

Applied `judge_grouping.group_judged_first` to pending evaluations at 3450K,
3500K, 3550K, 3600K, 3650K, 3700K, 3750K and 3768319. Judged inference runs
first; ordinary inference waits on a success-mode control gate. Failed judged
tasks therefore need retry before that phase opens. Terminal dependency mode
is unsuitable here: the scheduler's impossible-ancestor propagation can release
such a gate before future checkpoint work starts. Existing intermediate
TEARDOWN_EVAL rows became no-op control barriers with their original dependencies;
the SQLite runner still drains servers before exclusive training/export.
This avoids 0.95 -> 0.85 -> 0.95 churn and redundant suite-boundary shutdowns.
3400K was left unchanged. Changes were made under the administration lock,
preserving live claim/runtime state, with backup `before-judge-grouping.sqlite`.

### 2026-10-10: Reboot recovery during the 3400K evaluation

The runner lost access to `/work/mimir/HRM-Text` (FileNotFoundError followed by
PermissionError); reboot then removed `/tmp/dfm14-production-3383000/jobs.sqlite`.
Recovered that database using SQLite backup from the intact 15:55
`state.backup.sqlite`, which passed `quick_check`. No old workers remained and
all GPU memory was free. Under the administration and lifetime locks, fenced
89 interrupted claims through FAILED to PENDING; completed rows were preserved.
The saved state contained 171 completed inference jobs, 873 remaining/retried,
and nine pending averages for 3400K. It was not a completed/synced checkpoint.
Recovery snapshot: `reboot-recovery-20261010.sqlite` in the production plan.
Monitor reopened in `hrm-0:4`. Runner resumed the same plan with 64 direct clients;
the existing 3450K training row resumes from step_3400000 after its dependencies.
This host lacks `/usr/local/cuda` after reboot. The hrm environment contains
working CUDA 13.2 nvcc at `lib/python3.13/site-packages/nvidia/cu13/bin/nvcc`;
the recovery launcher sets CUDA_HOME to that cu13 directory and adds its bin
after hrm/bin on PATH. Runner log: `resume-after-reboot-20261010.log`.

W&B authentication also disappeared on reboot: MATH, GSM8k, ARC and MBPP
merge/sync jobs failed with `No API key configured`, while inference continued.
Verified login was restored using the SDK's interactive credential input and
its standard `/home/ucloud/.netrc` store (no credentials in the repository).
Reset only the four authentication-failed merge jobs, preserving inference.
Check authentication as well as CUDA and database recovery after a reboot.

### 2026-10-10: Legacy-style read-only monitor

The SQLite Rich monitor now uses the legacy presentation: compact status,
GPU memory/utilization, task-first labels with checkpoint/shard information,
training and evaluation progress/ETA, CPU jobs, next-ready and blocked queues.
Shared clients beyond the first per GPU are shown as additional running rows
when space allows; overflow counts are explicit. Width and row budgets are
recomputed from the terminal on every refresh. Database reads remain read-only
and bounded, and log progress is parsed once per job rather than per GPU.
The monitor does not alter scheduler state, ownership, training, or evals.
Verified at 100x32, 156x40 and 220x70, with bottom queue sentinels visible;
live production rendering took approximately 0.7 seconds for a 39,927-row plan.

### 2026-10-10: CPU publication split and 64-client follow-up

User priority: steady-state throughput on large campaigns, not cold startup
optimization. Startup remains included in receipts but is not the tuning target.
The SQLite runner now atomically applies the legacy inference/publication split
before dispatch. Pending DFM, DFM IFEval and EuroEval rows retain the original
job ID on CPU export/merge/sync; new `-inference` rows perform GPU-facing work.
Completed/running work is not rewritten. Existing dependent merges/averages
still wait for publication success. The inference retry budget is retained;
CPU publication starts with its own attempt counter. An idempotent transaction
prevents partial graph changes and concurrent-edit loss.

CPU publication jobs use the existing bounded CPU budget, not the inference
client cap or server residency. This does not split evaluator-internal scoring
out of the inference subprocess. Target/judge shutdown is parallel across
owned GPUs after draining, with judge-before-target order within each pair;
all shutdowns are attempted before propagating an unconfirmed-exit error.

Follow-up authorized at complete `ephemeral_step_3387500`: same 100 tasks,
64 clients, no W&B, full telemetry and automatic original-run resume.
Artifacts: `logs/scheduler/multilingual100-direct64-3387500`;
control: `logs/scheduler/multilingual100-3387500-control`.
This combines the publication split, 64 clients, and parallel shutdown; it
cannot isolate the individual contribution of each change.

Completed successfully: 100 inference + 100 CPU export jobs, 50,000 examples,
zero failed jobs, no W&B logging, and no preemptions. Compared with the previous
direct-32 run:

| Measurement | Direct 32, before split | Direct 64, with split |
| --- | ---: | ---: |
| Total wall time | 166.11s | 147.11s |
| First-to-last sampled request completion | 44.01s | 38.16s |
| Tail after final sampled request completion | 15.75s | 8.69s |
| Inference-active GPU mean utilization | 54.96% | 59.13% |
| Inference-active mean KV occupancy | 9.08% | 20.98% |
| Peak KV occupancy | 42.78% | 57.34% |
| Peak queued requests per server | 639 | 2,583 |
| Requests per whole-campaign minute | 18,061 | 20,392 |
| Generated tokens per whole-campaign second | 6,130 | 6,922 |
| Peak memory on each GPU | 174,524 MiB | 174,524 MiB |

Request completion window was 13.3% shorter; total time 11.4% shorter.
These remain short sequential runs, not a large-campaign steady-state estimate.
No retry/error markers were found in direct-64 client logs. Against legacy,
87/100 task score dictionaries matched exactly; largest primary metric delta
was 0.00401. Same-source validation and all four runs' measurements are in
`multilingual100-direct64-3387500/comparison.json`.

The controller resumed the original XL W&B run from preserved 3387500 with
the direct SQLite scheduler and `--max-clients 64`. On startup, the production
plan gained 288 CPU phase rows for previously unsplit pending tasks; existing
job IDs/dependencies and completed jobs were retained. Training parameters
are unchanged. Monitor: `hrm-1:8`. Automated checks: 288 passed; OKF validation
passed. Do not conflate new physical row counts with extra evaluation examples.

### 2026-10-10: direct-server replacement (current implementation)

The default `SharedServerPool` now assigns actual server URLs and served model
names to clients. No scheduler HTTP gateway is created and no request passes
through the scheduler. vLLM owns batching/queuing; the existing model-native
compatibility adapter, where required by the launch configuration, is unchanged.
The old gateway is retained only as explicit `gateway='proxy'` for historical
tests/comparisons (`benchmark_multilingual --modes shared`). New benchmark modes
default to `direct,legacy`; `--modes direct` runs only the direct path.

Clients spread over free GPUs, then share the least-held compatible replica.
Other replicas already starting are allowed to finish before piling all waiting
clients onto the first ready GPU. The scheduler tracks client residency only,
not individual requests. Failed client sessions fence a replica from new
assignments; existing clients finish before owned processes are replaced.
Target and judge remain a jointly owned pair. Client monitor termination
cannot signal a shared server. Request counters remain unknown in the scheduler
snapshot rather than confusing client counts with request counts; benchmark
telemetry samples vLLM directly.

Historical tradeoff (publication portion superseded by the split above): existing callbacks include client startup and some scoring/export
work. Their model-residency hold therefore outlasts inference, but does not
exclude compatible clients from using that server. Splitting these phases is
separate from removing the broker; do not claim complete CPU/GPU phase
separation has already been achieved for every suite.

The user authorized pausing after complete `ephemeral_step_3386000`, running
the same isolated 100-task benchmark without W&B, then resuming the original
training run. Controller: `scripts/benchmark_direct_3386000_and_resume.py`;
artifacts: `logs/scheduler/multilingual100-direct-3386000`;
control: `logs/scheduler/multilingual100-3386000-control`.
GPU benchmark completed successfully: all 100 tasks and 50,000 examples,
with unchanged source rows and no W&B writes. Production restarted from the
preserved 3386000 checkpoint using the direct pool and the original W&B run.
The preceding proxy benchmark below remains historical evidence.

| Measurement | Direct (no broker) | Legacy | Former broker |
| --- | ---: | ---: | ---: |
| Wall seconds, including cold startup/cleanup | 166.11 | 244.27 | 302.74 |
| Requests per wall minute | 18,061 | 12,282 | 9,909 |
| Generated tokens per wall second | 6,130 | 4,169 | 3,362 |
| GPU utilization, inference-active snapshots | 54.96% | 39.80% | 49.78% |
| GPU utilization, whole campaign | 16.53% | 18.44% | 15.91% |
| KV occupancy, inference-active mean | 9.08% | 1.56% | 2.52% |
| KV occupancy, peak | 42.78% | 18.63% | 32.33% |
| Queued requests per server, peak | 639 | 63 | 0 |
| GPU memory per GPU, peak | 174,524 MiB | 174,524 MiB | 174,524 MiB |
| Preemptions | 0 | 0 | 0 |

Direct first completions were sampled at 106.35s; all 50,000 at 150.36s.
The 44s completion window was substantially shorter than legacy's 132s and
the broker's 170s. No retry/error markers were found in direct client logs.
No continuous-saturation claim: startup dominates this short campaign, and
client/scoring gaps remain. The run is 32.0% shorter than legacy and 45.1%
shorter than the broker, but these are single ordered runs with shared host
caches, not randomized repeated trials.

87/100 score dictionaries match legacy exactly; 13 differ, with largest
primary F1/exact-match difference 0.00410. The cause of those small generation
differences was not isolated; do not call this bitwise parity.
`comparison.json` joins the three modes and records all score deltas;
`result.json` and per-second `telemetry.jsonl` preserve the direct evidence.
Automated validation: 281 tests passed; OKF validation passed.

### 2026-10-10: authorized comparison and production migration

Supersedes the development-only/no-migration state below. Training stopped
after the complete `ephemeral_step_3383000`, preserved in
`checkpoints/preserved/dfm14-shared-benchmark-3383000`. Both isolated benchmarks
used the same 3350K EMA export, 100 multilingual acceptability/correction tasks,
500 examples each, all eight GPUs, and no W&B logging.

| Measurement | Shared SQLite | Legacy persistent |
| --- | ---: | ---: |
| Completed tasks/examples | 100 / 50,000 | 100 / 50,000 |
| Cold-start-inclusive wall seconds | 302.74 | 244.27 |
| Mean GPU utilization during inference-active snapshots | 49.8% | 39.8% |
| Mean KV occupancy during inference-active snapshots | 2.52% | 1.56% |
| Peak KV occupancy | 32.33% | 18.63% |
| Peak allocated memory per GPU | 174,524 MiB | 174,524 MiB |
| Preemptions | 0 | 0 |

The shared runner succeeded but was 24% slower in this trial; it did not
saturate the GPUs continuously. This is one ordered trial, not a randomized
performance study. Scores matched exactly for 81/100 task dictionaries;
19 differed, with primary F1/exact-match differences at most approximately
0.00401. Do not claim exact numerical parity or an established speedup.

Timing diagnosis from sampled telemetry: first successful requests appeared
at 122.24s shared versus 100.83s legacy; all 50,000 were observed at 291.77s
versus 232.85s. Thus approximately 21s of the 58.47s gap preceded the first
completion and approximately 38s occurred during request completion; final
cleanup was approximately 11s in both. Shared broker counters recorded 226
recoverable ReadError/ConnectTimeout failures. These support investigating
HTTP admission/connection bursts and retry delays, not a GPU memory limit
(zero preemptions). They do not establish how much time each retry caused.
Shared launched 32 clients versus legacy's eight inference lanes; clustered
job completions suggest CPU/client phase contention as another hypothesis.
The active-inference utilization statistic excludes idle snapshots and is
not an end-to-end utilization measure. Whole-campaign GPU utilization was
approximately 15.9% shared versus 18.4% legacy. Cold process launches were
included, but the ordered trial did not clear OS/compiler caches between runs.

Artifacts: `logs/scheduler/multilingual100-comparison-3383000/`, including
per-second telemetry and `verified-comparison.json`. The raw `result.json`
retains a false legacy completion flag: its running harness expected 100
physical rows, but legacy legitimately splits into 100 inference + 100 export
rows. All 200 completed, with 100 successful 500-example score artifacts.
The harness now checks logical job IDs instead; the separate verification
receipt preserves the original evidence.

Shared clients now tolerate transient connection/timeout log messages while
their request retries recover; permanent bad requests, interrupted tasks,
process death, and OOM checks remain fatal. Scheduler tests: 229 passed.

Per the user's conditional handoff, production resumed from 3383000 using
SQLite in the existing `logs/scheduler/dfm12_XL_epoch11_noidentity` plan,
with unchanged original W&B run `dfm8-xl-from-dfm6-dfm7-epoch5-clean-full`.
Authority: `/tmp/dfm14-production-3383000/jobs.sqlite`, selected by the plan's
`database.json`, with durable `state.backup.sqlite` in the plan directory.
Control receipts: `logs/scheduler/multilingual100-3383000-control`.
The production monitor is `hrm-1:8`. Never start a TSV runner against the
pre-migration snapshot while SQLite is authoritative.

The 2026-10-09 implementation is opt-in. Existing TSV runners and the ongoing
XL training campaign are not migrated or restarted during its development.
Tests and an isolated CPU/mock-server simulation precede any GPU rollout.
Simulation validates orchestration, not numerical model equivalence or GPU
throughput. A real-model comparison remains a separate deployment gate.

### Mixed-latency CPU campaign

`eval_scheduler.gateway_latency_simulation` uses actual loopback HTTP requests
and the production gateway, with asynchronous sleeps replacing inference. With
`--scheduler`, the actual `DatabaseRunner` and an isolated `/tmp` SQLite database
claim and complete the 100 evaluation jobs and a dependent merge. Server
ownership and the task implementation are mocks: no GPU query, model load,
production plan access, W&B call, or training interruption occurs.

```bash
PYTHONPATH=eval_scheduler:. /home/ucloud/miniforge3/envs/hrm/bin/python \
  -m eval_scheduler.gateway_latency_simulation --scheduler
```

Defaults reproduce the 100-job, 500-row workload, 32 active jobs, eight
1,024-slot backends, and client concurrency 512 for acceptability / 256 for
correction. The seeded latency assumptions are lognormal (sigma 0.8), medians
1.2 / 6 seconds respectively, with 2% fourfold slow outliers capped at 90
seconds. Headers arrive before a delayed two-part body, exercising admission
leases through response completion. One percent of requests receive an injected
first-attempt `ReadError`; client retries are limited to five attempts with
exponential backoff and jitter. Gateway admission responses are retryable too.
These distributions are **not** measured vLLM latency distributions and do not
predict GPU speed, batching behaviour, or KV occupancy.

Each run writes `telemetry.jsonl` and `result.json` under its printed
`/tmp/gateway-latency-*` directory. Checks cover exact response IDs, payload
preservation, duplicate completions, all-job completion, capacity limits, and
draining. Measurements include service versus end-to-end latency, sleep
overshoot (CPU/event-loop delay), active/queued requests, backend distribution,
per-job time, request retries, and total wall time. The small regression tests
also verify coordinator completion, merge dependencies and CPU-lease release.

Verified 2026-10-10 full-size runs (unscaled sleeps):

| Mode | Jobs / responses | Wall time | Recovered injected / other transport failures |
|---|---|---|---|
| Gateway and client dispatch | 100 / 50,000 | 356.20s | 513 / 452 |
| SQLite coordinator and gateway | 100 plus merge / 50,000 | 336.66s | 513 / 431 |

Receipts: `/tmp/gateway-latency-ljq78zpi/result.json` (gateway) and
`/tmp/gateway-latency-7xwjfa31/result.json` (coordinator). Both passed without
missing, duplicate, or corrupted responses or leaked client tasks. Coordinator
state ended with all 101 rows done and all CPU leases released. Peak gateway
admission reached 8,192 active requests; the coordinator run's peak queue was
2,905. Backends completed 6,209-6,298 responses each. The non-injected loopback
transport errors recovered within the retry budget; their exception subclasses
were not captured by those runs. Subsequent runs now record subclasses.

This is a correctness/load result, not a speedup comparison: runs overlapped in
CPU time and the simulation shares one process/GIL between gateway and clients,
unlike production's separate client processes. In the coordinator run, assumed
service time averaged 5.24s; end-to-end request latency averaged 22.40s (p95
56.92s), and sleep overshoot was p95 3.82s. Startup bursts, CPU/event-loop
contention, queueing and slow-tail job slots remain important performance
factors. Sampled mean active counts are not time-weighted utilization. Do not
equate these with GPU or KV occupancy. Production training stayed running at
roughly 1.23s/step; no GPU trial was launched. All 228 scheduler tests passed.

This supersedes the TSV-as-authority assumption in the
[multi-node scheduler plan](multinode-eval-scheduler-plan.md) **only for plans
explicitly migrated to the new single-node backend**. Existing multi-node
workers are not silently switched to this backend.

## Ownership and Capacity

- SQLite on local disk is authoritative. WAL and FULL synchronization protect
  committed state. Indexed dependencies and transactional claims replace whole
  TSV rewrites. A unique persisted attempt token rejects stale completions.
- `plan.tsv` is an explicit import/export artifact. Definition imports preserve
  newer execution state. Missing dependencies, cycles, and edits/removal of
  running definitions are rejected. A `database.json` authority marker prevents
  legacy runners/writers from accidentally operating on a stale TSV.
- CPU clients retain no exclusive GPU lease. Compatible clients share async
  gateway admission; CPU preparation, inter-pass work and scoring do not count
  as active inference requests. Models are started lazily on inference, not on
  client registration or `/models` discovery.
- Default server capacity is 1,024 requests, not 8 or 32. Explicit server
  `--max-num-seqs` is respected. The gateway permits an additional queue of
  twice backend capacity. Request-byte limits are also enforced.
- Forwarding uses pooled asynchronous HTTP, no per-request SQLite writes,
  tokenization, synchronous payload logging or fixed polling sleeps. Responses
  retain capacity until completed; a disconnected client does not license
  unloading a still-busy upstream server.
- Default node CPU budget is 256 logical CPUs, bounded by process affinity,
  with eight reserved from preparation. Two CPUs per client is configurable
  through `--client-cpu-cores` or job `metadata.cpu_cores`. Affinity and native
  thread limits are inherited by children. Servers use CPUs outside the
  preparation allocation, including additional available node CPUs.
  Shared-client child processes have `CUDA_VISIBLE_DEVICES` empty; exclusive
  training/export jobs retain their allocated GPUs.
- Training and GPU export drain inference before acquiring exclusive devices.
  Soft stop preserves pending work and drains owned tasks. Unreconciled running
  attempts require explicit recovery; they are not blindly reset on startup.

CPU limits contain cooperative processes, not hostile subprocesses that reset
their own affinity. Do not daemonize work outside its supervised task lifetime.
SQLite WAL must not be placed on NFS; the TSV/log/artifact directories may remain
on shared storage. Keep a durable local-disk backup policy for the database.

## Commands

Use the documented working conda environment and `uv pip` for dependencies.
The package's `shared` extra provides FastAPI, httpx and uvicorn.

After explicitly stopping/draining the old runner:

```bash
python -m eval_scheduler database import \
  --source /path/to/plan/plan.tsv --plan-dir /path/to/plan \
  --database /local/disk/eval/jobs.sqlite --runners-stopped

python -m eval_scheduler run --plan-dir /path/to/plan \
  --backend sqlite --persistent-vllm --gpus 0,1,2,3,4,5,6,7 \
  --cpu-cores 256 --reserve-cores 8 --max-clients 128 \
  --server-concurrency 1024

python -m eval_scheduler monitor --plan-dir /path/to/plan --rich
python -m eval_scheduler stop --plan-dir /path/to/plan
```

Use `database lock` to pause new claims while permitting completions. Use
`database edit` for transactional definition edits, and `database export` for
a consistent TSV snapshot. Do not manually overwrite the authoritative
database or use legacy `plan reset`/TSV editing commands after migration.
The runner writes a separate `plan.snapshot.tsv` when idle/stopped, without
overwriting a manually edited `plan.tsv`.

## Deployment Boundaries

The shared path requires OpenAI/vLLM eval clients. It must never silently run a
local GPU engine on a placeholder GPU, replace a judge backend, change prompts,
tokenizer/template behavior, checkpoint/EMA mode, or W&B destinations. Unsupported
configurations must fail preflight before claims. Multi-node migration and
real-GPU rollout require separate validation; successful mock tests alone do
not establish production readiness.

Superseded later on 2026-10-09: the initial implementation rejected managed
judges. The production-hardening implementation now owns paired target/judge
servers, using the original transformers judge launcher and configuration.
Both routes share a placement identity but have separate request admission;
draining/replacing a GPU waits for both. Judge startup reserves 16,384 MiB by
default (`judge_memory_reserve_mib`), in addition to the target's configured
allocation. The live plan's judged target allocation remains 0.85. Judge
admission defaults to 32 (`judge_max_concurrency`); target capacity remains
unchanged. No judge engine or scoring prompt is substituted.

**Rollout still gated:** an actual target-plus-judge run with production GPU
headroom, and suite-level score/wall-time comparison, are outstanding. The
current training/legacy scheduler is not migrated merely because unit tests or
the small real-model transport check passed.

## Isolated State Simulation

On 2026-10-09, a synthetic 40,000-job DAG simulation passed without launching
tasks, querying GPUs, writing W&B, or changing the live plan. Its dependencies
include failed ancestors, terminal barriers, and optional VALEU jobs.

```bash
PYTHONPATH=eval_scheduler python -m eval_scheduler.simulation \
  --output /tmp/eval-scheduler-simulation-new --jobs 40000
```

Measured on this node: 128-job claim transaction about 43 ms; completion update
median 0.429 ms, p95 0.489 ms; bounded readiness lookup about 41 ms. The initial
simulation exposed a quadratic dependency-validation operation: its 12.2-second
import and 12.6-second preserving reimport were superseded by a linear lookup
fix, measured at 0.76 and 1.33 seconds. These are administrative operations, not
request or completion-path operations.
Full readiness enumeration matched the legacy in-memory implementation before
and after updates. Export/reload and persisted fencing-token checks passed.
Receipts: `/tmp/eval-scheduler-simulation-20261009/report.json` and
`/tmp/eval-scheduler-simulation-20261009-linear-deps-v1/report.json`.

## Isolated HTTP Simulation

```bash
PYTHONPATH=eval_scheduler python -m eval_scheduler.gateway_simulation --requests 4096
```

The 2026-10-09 run used real loopback HTTP to the gateway and eight mocked
upstreams, never model/GPU servers. It admitted all 4,096 requests concurrently,
512 per backend, with no payload mismatches after the intentional model-alias
rewrite. Sampling/tool arguments were preserved. Cancellation retained upstream
ownership until completion; a short drain timeout left the gateway alive, and
subsequent clean shutdown succeeded with zero pending client tasks.

The first run's post-load cancellation probe timed out while reusing the large
load-client connection pool. The revised probe uses a fresh TCP connection
after closing that pool, records transport timing, and retains partial receipts
on failure. Mock upstreams wait on events rather than thousands of polling
timers. The successful probe reached its upstream in 17 ms. This is a protocol
and ownership check, **not** a model-serving throughput benchmark.

Receipt: `/tmp/gateway-simulation-xg8ccthy/result.json`.

A subsequent run after making intentional disconnects log quietly also passed:
`/tmp/gateway-simulation-tgj6eave/result.json`. All eight mock backends received
512 requests; cancellation/drain checks passed and no client tasks remained.
The final scheduler, CPU-budget, monitor and proxy suite passed 255 tests at
this integration checkpoint. Tests do not claim live GPU numerical parity.

## Simplicity Refactor

On 2026-10-09, the standalone gateway and shared-pool gateway were changed to
use one `serve_gateway` HTTP startup/lifetime helper. Request admission remains
in `Gateway`; GPU placement and residency remain in `SharedServerPool`.
The runner's unused exclusive-execution argument was removed; exclusive
admission and draining are unchanged. Early server exit and cancellation cleanup
have explicit regression tests. The suite passed 257 tests, and the 4,096-request
mock simulation passed again (`/tmp/gateway-simulation-5439186n/result.json`).
No live plan, training process, or deployment settings were changed.

## Production Hardening and Evidence

Later on 2026-10-09:

- All 19,480 pending jobs in the live DFM14 campaign passed definition preflight
  without claims, GPU allocation, plan edits, or W&B writes.
- Target/judge startup failures release owned processes; unconfirmed exit
  prevents successful shutdown. Client monitors detect paired server exit and
  gateway failures. No unrelated processes are signalled.
- Spawned children have process receipts in `owners/jobs/<attempt-token>` and
  `owners/servers`: PID, boot ID, process start ticks, owner and job identity.
  This aids manual recovery, but parent exit alone does not prove descendant
  exit. Recovery remains token-fenced and requires independent process checks.
- SQLite authority rejects network and RAM filesystems. On this machine
  `/work/mimir` is **wekafs**, whereas `/tmp` is overlay-backed local storage.
  Place the authority on local disk, not beneath the repository. The runner
  atomically backs up committed state to `state.backup.sqlite` in the plan
  directory every 60 seconds and on clean exit. Use the SQLite backup API,
  never copy just the live database while WAL transactions exist. Local
  container storage may disappear with the instance; retain the plan backup.
- The DFM14 segment wrapper now finalizes cursor-derived epochs transactionally
  in SQLite. Running checkpoint-wait claims retain their tokens; already-running
  evaluation clients reject epoch rewriting. TSV behavior is unchanged. Only
  that script's hash was refreshed in the installed handoff receipt; every pin
  and the prepared-data hash was reverified. The live plan remains TSV.

The real-model transport check used `exports/dfm14_XL_step_3350000_ema_hf`,
GPU7, utilization 0.05, max sequences 4, compilation/CUDA graphs enabled and
the existing Gemma chat template. There were no W&B writes. An initial
attempt selected a stale superseded row with a nonexistent DFM13 export;
validation now checks local export existence before starting a server.

The concurrent cold-cache run matched all eight answers and token counts but
had log-probability differences on two raw completions. It **did not pass**
strict parity; receipt `/tmp/shared-real-parity-3350k-20261009-v2/result.json`.
The follow-up warmed all prompts, used concurrency 1 for comparison, and added
a direct-versus-direct control. All eight outputs, token counts, finish reasons
and log-probabilities matched exactly, including the control:
`/tmp/shared-real-parity-3350k-20261009-v3/result.json`.
Measured direct/shared times were 1.454/1.688 seconds. These small transport
measurements do not demonstrate overall eval speedup or equivalence at high
concurrency. All validation servers were shut down; training kept progressing.

The 40,000-job simulation passed again at
`/tmp/shared-state-production-20261009/report.json` (import 0.748 seconds,
128-job claim 43 ms). The 4,096-request/eight-backend simulation passed at
`/tmp/gateway-simulation-lbffphn2/result.json`.
The final scheduler/CPU-budget/monitor/proxy/DFM14-handoff suite passed 291
tests; OKF validation and `git diff --check` also passed.

## Remaining Cutover Checks

### 2026-10-10 validation and training pause

The requested 3,367,500 ephemeral was fully written before training was stopped.
The stop arrived after the loop had advanced beyond that checkpoint; those later
unsaved steps are not claimed as preserved. The legacy scheduler is stopped with
`stop.request` retained. Its DFM14 3,400,000 training row is pending with
`resume_from_tag=ephemeral_step_3367500`. No automatic training restart is intended
while validation occupies GPUs.

The paired real-model gate **passed** on idle GPU7 using XL 3,350,000 EMA,
production CUDA-graph settings/max sequences 1,024 and target utilization 0.85,
with the normal `unsloth/gemma-4-E4B-it` Transformers judge. Target direct/control/
shared answers, token counts, finish reasons and log-probabilities matched;
judge YES/NO outputs matched. Both owned processes exited. Receipt:
`/tmp/shared-judge-full-20261010/result.json`. This is transport parity, not yet
suite-score parity or a high-concurrency throughput claim. Use
`validate_shared --production-settings --allow-managed-judge` to preserve the
production server arguments instead of the small-headroom canary overrides.

`python -m eval_scheduler.validate_suites PLAN OUTPUT --job-id ID ... --gpus 0,1,2`
executes identical completed source inference rows under the legacy persistent
runner and SQLite/shared runner. It retains production prompts, tokenizer proxy,
batch sizes, EMA export and scorers, but isolates result paths, removes W&B IDs
and disables logging. It rejects occupied GPUs and training/publication rows.
Artifacts include both plans, task logs, exact score/sample-count comparisons,
and wall times including startup, scoring and shutdown. Empty metrics or failed
jobs cannot pass. This is representative-task validation, not full-suite coverage.
The comparison covers ARC, a Talemaader shard and ScaLA-da; results are below.
`--shared-first` allows a reverse-order repeat to expose cache/order bias;
`--resume` reuses only fully completed modes with identical source definitions.

The initial three-GPU comparison completed in 155 seconds (legacy) versus
277 seconds (shared). Its reverse-order control was 152 versus 279 seconds.
These are **pre-fix**, not deployment-ready timing results: the first judged
request replicated target/judge pairs onto every free GPU, held the placement
lock during loading, then launched unnecessary replacement servers for tiny tails.
The updated implementation starts one judged pair initially, fences GPU choices
while loading different configurations concurrently outside the placement lock,
and expands resident groups only when actual queued requests exceed their current
role-specific capacity. Expansion notification uses a coalesced async event, not
database writes, polling sleeps, or per-request threads.

Both initial comparisons matched ARC accuracy (0.8601, 1,172 samples). ScaLA
matched exactly in the first comparison; the legacy repeat varied by about
0.41 macro-F1 points. Talemaader varied between 32.67 and 33.17% across the
official/legacy/shared generations. Changed verdicts occurred only on changed
generated answers, not unchanged answers. Consequently the **exact suite-score
gate has not passed**; transport parity does not mean identical regenerated
scores under different batching. Receipts: `/tmp/shared-suite-full-20261010/`
and `/tmp/shared-suite-reverse-20261010/`.

A stronger judge-only check replayed all 101 frozen scorer requests from the
legacy Inspect archive, resolving its attachment references. Direct/shared
verdicts and token counts matched exactly (9.341/9.277 seconds). Receipt:
`/tmp/shared-judge-frozen-20261010/result.json`. Reproduce with
`validate_shared --judge-archive PATH.eval --allow-managed-judge --production-settings`.
The runner continues to use the existing judge engine and prompt; no score
tolerance has been loosened.

The final post-fix three-GPU run completed in **158.348 seconds**, compared with
its identical-source legacy reference of **151.768 seconds**. This removes the
large startup regression but is not a demonstrated speedup on this small workload.
ARC accuracy was 86.01% in both; Talemaader accuracy was 32.673% in both, with
different per-item scores/standard errors; ScaLA macro-F1 was 65.214% shared
versus 64.772% legacy (MCC 42.340 versus 40.813%). The strict suite comparison
therefore remains **not passed**. Do not automatically migrate production merely
because transport/frozen-judge tests pass. Retained receipt:
`/tmp/shared-suite-final-20261010/result.json`. The test harness supports
`--reference-legacy PATH/result.json` to reuse a completed identical-source,
same-GPU baseline without rerunning it. It records this reuse explicitly.

Final automated coverage: 299 tests passed (scheduler, CPU budgeting, monitor,
native proxy, DFM14 handoff and validation harnesses). Live training is still
paused and W&B was disabled throughout validation.

### 100-row multilingual comparison (2026-10-10)

`python -m eval_scheduler.benchmark_multilingual PLAN OUTPUT` selects one
completed acceptability shard and one correction shard per language from XL
3,350,000 EMA: 100 real inference rows, 50 languages, 500 samples per row
(50,000 examples per runner). It prefers DaLA v2 where available. It runs the
SQLite/shared backend first and the legacy persistent runner second, with the
same production batch sizes, export, prompts and scoring. It removes W&B IDs,
sets `log_wandb=false` and `WANDB_MODE=disabled`, and isolates all output paths.
This is a two-family saturation test, not all-suite coverage. The legacy runner
adds local CPU export rows, which also count towards end-to-end wall time.

Artifacts retain `sources.tsv`, both isolated plans, scores, per-second GPU and
vLLM telemetry, and `result.json`. Counter totals use the largest observed value
per server PID, so the last unsampled second can be omitted. Separate whole-run
and inference-active utilization summaries avoid conflating cold startup with
inference. A failed/incomplete mode stops the harness rather than producing a
speedup claim. Training is not started by this harness.

The first scale-up attempts exposed two startup port races: a probed public API
port and a vLLM internal TCPStore port were claimed by ephemeral client sockets
before binding. Public listeners now use 20,000-29,600 (modulo-eight lanes,
including scan allowance), and `VLLM_PORT=10000+128*gpu` separates internal
rendezvous starts from this machine's 32,768-60,999 ephemeral range. A separate
failure showed that a five-second broker health-read timeout must not be treated
as confirmed model death under a large request burst. The next health poll still
detects real process exits/backend errors. Failed attempts remain in
`logs/scheduler/multilingual100-comparison-20261010*`; they are not valid timing
comparisons. **Superseded 2026-10-10:** the paired rerun was cancelled at the
user's request. Production resumed from 3,367,500 using the existing TSV runner
and original W&B run; no additional GPU benchmarks may interrupt it.

The final shared attempt (`multilingual100-comparison-20261010-r5`) failed all
100 jobs in 351.4 seconds. This is a failure duration, not evaluation throughput.
The first recorded upstream `ReadError` had `exits=[]`: no confirmed server exit.
The monitor incorrectly treated any cumulative backend HTTP failure as fatal to
every client using that compatibility key. Registering subsequent jobs then
evicted failed-count servers, creating a cascading failure. The underlying
first socket disconnect is not established by the captured logs; do not label
it an OOM or a proven capacity limit.

HTTP failures now remain visible to the requesting client and in counters, but
do not mark unrelated clients dead or trigger eviction while their routes are
registered. Confirmed process exits and failed provisioning still fail clients.
Inspect's existing request retries handle transient API errors; the gateway
does not add another invisible replay layer or accept partial responses as
successful. Its default retry limit may be unbounded unless task configuration
sets one, so request retry budgets should be reviewed before production rollout.
Draining a backend with failed requests still requires confirmed owned-process
termination before reuse, preserving uncertain-upstream-work cleanup safety.
The comparison harness now refuses to launch legacy after an incomplete shared
campaign.

CPU validation: 225 scheduler tests passed, including transport-error isolation,
continued service, confirmed process death, and failed-response drain safety.
An 8,192-request loopback simulation admitted 1,024 requests on each of eight
mock backends, completed with no payload mismatches or leaked client tasks,
and passed cancellation/drain checks in 46.4 seconds. Receipt:
`/tmp/gateway-simulation-oqws8nke/result.json`. This is not GPU performance or
score-equivalence validation; another explicitly authorized GPU trial is needed.

Before stopping/migrating the legacy runner, run definition preflight:

```bash
PYTHONPATH=eval_scheduler python -m eval_scheduler database preflight \
  --plan-dir logs/scheduler/dfm12_XL_epoch11_noidentity
```

The real-model checker supports an explicit paired-judge test on an **idle**
GPU, using a completed `generative_talemaader` job ID from the existing plan:

```bash
PYTHONPATH=eval_scheduler WANDB_MODE=disabled python -m eval_scheduler.validate_shared \
  /path/to/plan.tsv COMPLETED_JUDGED_JOB_ID /new/canary/output \
  --gpu 7 --utilization 0.85 --concurrency 32 --allow-managed-judge
```

It refuses insufficient headroom before launching, preserves the original
judge engine, writes a result receipt, and cleans up only its owned servers.
It is a transport check, not a full benchmark suite. Then compare representative
standard/DFM/EuroEval task outputs and wall time under the two runners in
isolated output directories with W&B disabled. Do not reinterpret a failed
parity receipt as success by silently dropping log-probabilities.

After passing those gates, drain the legacy runner at a checkpoint boundary,
back up its TSV, reconcile running waits, import into a local SQLite authority,
and launch the new runner/monitor in the existing plan directory. Do not replay
completed evaluations. To roll back, first drain the SQLite runner, export its
**current** state to TSV, archive the authority marker, then start one legacy
runner. Never roll back to the original pre-migration TSV after new jobs finish.

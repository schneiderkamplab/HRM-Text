---
type: Runbook
title: Experimental Cooperative CUDA Suspension
description: Isolated file-controlled training pause and per-rank CUDA offload/restore prototype.
status: draft
confidence: high
last_updated: 2026-10-12
tags: [training, cuda, checkpointing, experimental]
---
# Experimental Cooperative CUDA Suspension

## Isolation and Interface

Implementation: `training_suspend/`, with usage in its repository README.
`pretrain_suspend_test.py` is a copy of production `pretrain.py` at commit
089550e with small opt-in hooks. Production pretrain, its YAML, the scheduler,
live training processes and their launch environment are unchanged.

New experimental options: `suspend_after_steps`, `suspend_control_dir`,
`suspend_poll_interval_steps` (10), `suspend_wait_poll_seconds` (2).
Use Hydra `+` overrides. Each rank maintains a deduplicated sorted queue;
rank 0 accepts additional file requests at deterministic broadcast boundaries.
The minimum is checked locally each completed optimizer step. Stop conditions
win over suspension. A late boundary suspends at receipt, not retroactively.

The hook runs after step logging/validation/checkpointing, not at the earlier
optional cache-clearing hook. It saves a regular fallback checkpoint, drains
work, publishes per-rank readiness and parks in CPU polling. Resume tokens are
bound to launch, generation, actual step and process start identity. A GPU
barrier verifies collective progress before continuing the next step.

## Controller and Recovery

Use a fresh CUDA job handle before creating GPU resources. The launch helper
materializes NVIDIA's handle so torchrun does not lose an inherited descriptor;
all ranks verify identical handle identity. Each worker, not the launcher, is
checkpointed. Lock every rank first; then checkpoint every rank sequentially.
Restore/unlock in the same order, then release CPU waits only after all ranks
are restored. This follows NVIDIA's driver-610 IPC example.

The controller journals intent and verified results under an exclusive POSIX
lock. Atomic shared control files require no database or socket service.
The implementation rejects multi-node jobs: shared files alone are not remote
process control. Runtime receipts distinguish ready, offloaded and resumed.

A separately supervised `watch` command recovers expired offload leases and
abandoned ready-only pauses. A `hold` file prevents automatic restoration.
It will not kill unrelated processes or restore while newly admitted GPU
processes remain. GPU admission/reservation still belongs to the external
controller/scheduler; free-memory queries are not a reservation mechanism.
Recovery queries actual CUDA states rather than using blind toggle. Failed
CUDA operations may still require ordinary restart from the disk checkpoint.

## Validation Evidence

CPU suite: `tests/test_training_suspend.py` and
`tests/test_training_suspend_distributed.py`. Includes a real two-rank Gloo
run through two pause/resume cycles, deduplication/late steps, stale identities,
controller interruption, partial offload/restore, memory and ownership guards.

GPU smoke is explicitly bounded: XXS backbone, reduced 256-token vocabulary,
64-token context, deterministic synthetic inputs, BP5, GAS2, FSDP2, six steps,
suspension after steps 2 and 4, no W&B. Worker PyTorch memory cap is 3%; this
does not cap NCCL/driver allocations. Only smoke-owned process groups are
terminated on a smoke failure. No production PIDs are checkpointed or signalled.

Single GPU (physical GPU 1) passed two cycles, with **exact final model,
optimizer/EMA and all per-step metrics parity** against uninterrupted training.
PyTorch peak allocated memory was about 155 MiB. Offload took 5.17/5.41s;
restore/release 7.69/7.06s (including controller checks). Receipt:
`/work/dfm/tmp/suspend-smoke-single-20261012/result.json`.

Two-GPU default NCCL validation reached quiescence and locked both ranks, but
the first CUDA checkpoint call stalled. Do not infer general NCCL support from
the single-rank pass. Logs: `/work/dfm/tmp/suspend-smoke-two-20261012/`.
Stack: driver 610.57.04, torch 2.11.0+cu130, NCCL 2.28.9.
The default two-rank call timed out after 300 seconds; only the test process
group was cleaned up. This remains a production compatibility blocker.

The harness also offers an explicit `--legacy-nccl` diagnostic mode disabling
cuMem device/host allocations and NVLS for **test children only**. Results in
that mode must be labelled separately; no production workaround is authorized.

Follow-up 2026-10-12: two ranks with `--legacy-nccl` passed both cycles with
exact model, optimizer/EMA and per-step metric parity. Eight ranks with those
same flags and `--compile` also passed both cycles with exact parity. Receipts:
`/work/dfm/tmp/suspend-smoke-two-legacy-20261012/result.json` and
`/work/dfm/tmp/suspend-smoke-eight-compiled-20261012/result.json`.
Eight-rank offload took 59.36/57.79 seconds and restore/release 63.68/70.22
seconds, including sequential controller checks. These small-model timings
are not estimates for production-size transfers. Thirteen CPU tests passed.

This supersedes the earlier pending eight-rank compiled test, not the default
NCCL failure. At this point prolonged pauses, production-size workloads, and
carry-bearing models remained unvalidated; see the follow-up below. No
production settings or scheduler were changed.

## NCCL Compatibility Follow-up (2026-10-12)

Two-rank, two-cycle allocation-path isolation on the same stack:

| Override (otherwise default NCCL) | Result |
| --- | --- |
| `NCCL_CUMEM_HOST_ENABLE=0` | First checkpoint timed out after 60s |
| `NCCL_CUMEM_ENABLE=0` | First checkpoint timed out after 60s |
| `NCCL_NVLS_ENABLE=0` | Offload succeeded; restore failed with CUDA `invalid argument` |
| `NCCL_CUMEM_ENABLE=0 NCCL_NVLS_ENABLE=0` | Both cycles passed, exact model/optimizer/EMA/metrics parity |

These isolate a usable two-flag configuration, not the driver's internal root
cause. Disabling host cuMem is not necessary for the tested two-rank workload.
The NVLS-only logs still show `P2P/CUMEM`; device-cuMem-disabled logs show
`P2P/IPC`. Default NCCL compatibility is **not fixed**. Do not silently apply
these settings to production or change its live NCCL library.
Both flags must be set on worker launch before communicator initialization,
not in the controller after training is already running. Runtime switching
from existing default communicators is not implemented or validated.

Evidence roots under `/work/dfm/tmp/`: `suspend-host-only-20261012`,
`suspend-device-only-20261012`, `suspend-nvls-only-diagnostic-20261012`, and
`suspend-device-nvls-20261012`. The diagnostic journal preserves CUDA stderr.
The upstream [host-cuMem issue](https://github.com/NVIDIA/nccl/issues/2350)
involves a different stack and is not our established cause.

### Prolonged Pause Result

Completed under `/work/dfm/tmp/suspend-eight-long-20261012/result.json`:
compiled XXS/64 tokens, eight ranks, two 900-second requested offloaded pauses,
the two-flag configuration above, otherwise unchanged NCCL/PyTorch watchdog
settings. Both cycles passed with **exact model, optimizer/EMA and every
step's metric parity** against uninterrupted training using the same flags.
This is not a cross-configuration parity comparison with default NCCL.

| Cycle | Offload | Offloaded wait including health checks | Restore/release |
| --- | ---: | ---: | ---: |
| 1 | 52.14s | 907.09s | 70.56s |
| 2 | 48.68s | 907.67s | 75.81s |

All 50 periodic checks found the eight original workers alive/checkpointed
and **0 MiB** total owned GPU allocation. No CUDA-operation errors occurred.
The intermediate step-4 checkpoint also matched exactly after the first pause.
All test processes exited. Production `pretrain.py` retained SHA-256
`6da39b654ba88d69d77e8dbb5a1394d58a4241279a50a5bdd010814355d3bf87`;
no production process or scheduler was changed and no W&B data was logged.

Reproduce with a new output directory, in the training environment:

```bash
NCCL_CUMEM_ENABLE=0 NCCL_NVLS_ENABLE=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python -m training_suspend.smoke --gpus 0,1,2,3,4,5,6,7 --compile \
  --pause-seconds 900 --timeout 2400 --output /new/path/suspend-eight-long
```

The harness records launch environment, CUDA diagnostics and pause health.
Sixteen CPU tests pass. This supersedes the pending 15-minute-pause gate only:
multi-hour pauses, production-size memory/throughput, real eval handoff,
carry-bearing models and multi-node workloads are still unvalidated. Default
NCCL still fails on this stack. Do not migrate production based on this smoke
alone; the NCCL overrides' production performance cost is not measured here.

## Upstream Research (2026-10-12)

Research only; no production environment or process changes. The local results
above remain the compatibility baseline, not superseded by upstream proposals.

- NVIDIA's [checkpoint shim README](https://github.com/NVIDIA/nccl/blob/v2.32.3-1/contrib/nccl_checkpoint/README.md)
  describes communicator destruction/recreation around CUDA checkpointing,
  preserving application-visible identities. Requires NCCL >=2.31, launch-time
  LD_PRELOAD, prepare/restore calls and temporary Redis rendezvous. Installed
  NCCL 2.28.9 is too old. CUDA graph capture is unsupported.
- Inference, not verified: releasing NCCL resources before offload may remove
  the need for our device-cuMem/NVLS disabling flags. Test in an isolated
  environment before changing production. Compilation and graph capture are
  different; verify graph usage rather than assuming torch.compile is excluded.
- [Upstream tests](https://github.com/NVIDIA/nccl/blob/v2.32.3-1/contrib/nccl_checkpoint/python/tests/README.md)
  exercise communicator reconstruction, not actual CUDA checkpoint/CRIU.
  They therefore do not replace our end-to-end parity and offload tests.
- Native communicator suspend/resume alone is not an established NVLS solution:
  [issue 2337](https://github.com/NVIDIA/nccl/issues/2337) remains open;
  [prototype PR 2340](https://github.com/NVIDIA/nccl/pull/2340) was closed unmerged.
- [CUDA checkpoint documentation](https://github.com/NVIDIA/cuda-checkpoint)
  still excludes shareable-handle VMM IPC and UVM, and requires sequential
  process operations for IPC jobs. Driver 610's legacy IPC support is not
  general support for all NCCL resource types.

Recommended next gate: isolated matching NCCL/shim, two-rank then eight-rank
XXS exact-parity tests with default allocation/NVLS settings; then multi-hour
pauses, full-size memory/throughput tests, and real evaluation handoff. Fifteen
minutes is our tested duration, not a documented maximum. Multi-node remains a
separate controller and validation project.

## Isolated NCCL Shim Validation (2026-10-12)

Installed NCCL 2.32.3 via `uv pip --no-deps` in a separate venv sharing read-only
access to the hrm environment's packages. Built the official shim from source
tag v2.32.3-1 with hiredis v1.3.0; Redis runs only as a dedicated loopback
rendezvous during tests. See `training_suspend/README.md` for exact paths and
commands. No production dependencies were replaced.

New opt-in `--nccl-shim` smoke mode calls prepare before readiness and restore
before the resume barrier. The production pretrain remains unchanged. Nineteen
CPU tests pass, including missing-preload/rendezvous and error propagation.

Initial shim-only preload failed at communicator initialization because
`RTLD_NEXT` could not resolve `ncclCommInitRankConfig`. Preloading the matching
`libnccl.so.2` immediately after the shim fixed symbol visibility. The runtime
reports 2.32.3 via `ncclGetVersion` and NCCL logs; PyTorch's version helper still
reports its build-time 2.28.9, so do not rely on that helper for this experiment.

Two-rank uncompiled XXS passed two complete cycles with exact model,
optimizer/EMA and per-step metric parity. Receipt:
`/work/dfm/tmp/suspend-shim-two-preload-20261012/result.json`.
Offload took 10-11s and restore/release about 15s. Logs show P2P/CUMEM and NVLS
enabled; no NCCL allocation/transport disabling overrides were supplied.

This supersedes the *general* inference that these transports must always be
disabled, not the recorded failures with NCCL 2.28.9 without the shim. It is
still an experimental stack, not authorization to migrate running training.

Eight-rank **compiled** XXS also passed both cycles, including exact final
model, optimizer/EMA and every step's metric parity against the uninterrupted
baseline using the same new NCCL/shim stack. Intermediate step-4 state was
independently checked and matched exactly after the first cycle. Receipt:
`/work/dfm/tmp/suspend-shim-eight-compiled-20261012/result.json`.

| Cycle | Offload | Pause including health checks | Restore/release |
| --- | ---: | ---: | ---: |
| 1 | 52.45s | 36.60s (30s requested) | 67.74s |
| 2 | 45.11s | 36.87s (30s requested) | 68.06s |

All pause checks found all eight ranks checkpointed and 0 MiB owned GPU
memory. P2P/CUMEM and NVLS were enabled before/after reconstruction. No W&B
logging. All test processes and temporary Redis exited; pre-test GPU headroom
returned (15,866 MiB GPU0, 18,170 MiB others) with production still active.
Production pretrain SHA-256 remains
`6da39b654ba88d69d77e8dbb5a1394d58a4241279a50a5bdd010814355d3bf87`.

This demonstrates default-transport compatibility for this small workload,
not parity against NCCL 2.28.9, full-size throughput, CUDA graphs, multi-node,
or multi-hour suspension. The earlier 15-minute tests used the old stack with
transport overrides; do not attribute those longer pauses to this shim test.

## Multi-hour Campaign and CUDA Graph Scope (2026-10-12)

User deferred multi-node and full-size testing. Graph testing is conditional
on actual training use. Current production worker 930353 has
`compile_train_batch=true`, no compile-mode override and no TORCHINDUCTOR or
TORCH_COMPILE environment overrides. `config/cfg_pretrain.yaml` and the Python
model default to `compile_train_batch_mode=default`; the installed Inductor
has `triton.cudagraphs=False` and default mode adds no overrides. The other
supported mode is explicitly `max-autotune-no-cudagraphs`. No explicit CUDA
graph capture calls were found in the model/training helpers. Therefore no
graph-specific experiment is needed for the current training path. This is a
code/configuration inspection, not invasive profiling of the live process.

Launched an isolated compiled eight-rank XXS campaign with two **7200-second**
offloaded pauses (roughly four hours plus overhead), default NCCL transports,
NCCL 2.32.3 shim, no W&B, five-hour per-variant deadline. It runs independently
of the CLI in tmux window `suspend-long` (hrm group window 8 at launch).

- Driver script: `/work/dfm/tmp/suspend-shim-multihour-20261012.py`.
- Root: `/work/dfm/tmp/suspend-shim-eight-multihour-20261012/`.
- Driver log: `campaign.log`; terminal status: `status.json`.
- Final parity receipt, only after completion: `test/result.json`.
- Periodic CPU liveness/CUDA-state/owned-memory checks: each generation's
  `operations.jsonl` under `test/suspended/control/`.
- Dedicated loopback Redis is owned by the campaign and terminated in its
  finalizer. The smoke only cleans up its own worker process group on failure.

Status at documentation time: **running, not yet a multi-hour pass**. The
baseline completed and first offload succeeded at about 12:47 CEST; the first
health check found all eight ranks checkpointed with 0 MiB owned GPU memory.
Production
training, its environment and scheduler are unchanged. Restore retains the
existing headroom/new-workload safety checks; it will not evict other jobs.

### User-requested Early End and Failed Handoff

Superseded campaign status: user requested early resume and separately stopped
production at 991K. The first offloaded interval lasted **6711 seconds
(1h51m51s)** with 178 health checks. The attempted manual takeover raced the
original health monitor: it detected running/locked ranks, raised
`Offloaded state changed`, and terminated its test launcher/workers. An unlock
also reported initialization error during this termination. Consequently no
final parity result exists; this is **not** a successful long-pause restore
and does not establish a driver-duration limit either. Test services exited.

Future smoke early resume uses `finish_early.request` in the smoke output
directory, checked by the owning health loop. The same harness then restores
normally and skips subsequent long waits. Never use external restore or
signal-based monitor suspension to shorten a harness-managed pause. CPU
regression coverage verifies requested early return leaves restoration to the
controller.

Related: [training continuity policy](training-continuity.md).

## Full-size Short-pause Test (2026-10-12)

Supersedes the earlier deferral of full-size testing: user authorized an
eight-GPU XXL_wide test before restarting production. Receipt directory:
`/work/dfm/tmp/suspend-shim-xxl-wide-full-20261012/`.
The smoke now accepts `--full-size`: full 262144 vocabulary, 4096 context,
GBS 262144, GAS 4, BP8, FSDP2 FP32 parameters/BF16 compute, compile default,
no activation checkpointing. It uses fresh deterministic synthetic input and
random initialization, not production checkpoint weights. No W&B logging.

Both six-step variants completed. The suspended variant offloaded after
steps 2 and 4, released all owned GPU memory, restored and continued.
Offload took 29.9/30.0 seconds; restore 41.0/40.7 seconds. Requested
10-second pauses lasted about 15 seconds including health-check overhead.
Peak allocated GPU memory was 147.37 GiB; suspended peak reserved 161.59 GiB.
Baseline/suspended elapsed times were 164.8/353.4 seconds, including large
unsharded recovery snapshots. These are not production throughput estimates.

**Exact parity failed.** Loss differed already at step 2, before the first
suspension (12.982230 vs 12.982337); final losses were 12.823511 vs 12.822463.
The final tensor comparison also failed. This establishes operational
full-size suspend/restore, not numerical equivalence. A repeat uninterrupted
baseline and pre/post-offload state comparisons are needed to separate
baseline nondeterminism from suspension effects. `progress.json` contains
both completed variants; no successful `result.json` exists. Do not promote
the shim to production on this evidence. Temporary Redis and workers exited.

Production resumed via its existing disk checkpoint and original NCCL stack,
without LD_PRELOAD, after the experiment. CPU regression suite: 21 passed.

Numerical interpretation: step-1 loss is identical. Step-2 loss differs by
0.0001068 (0.00082%), and step-6 by -0.001048 (0.0082%). The local FA4 adapter
does not pass `deterministic=True`; installed FA4 defaults to nondeterministic
backward. This supports, but does not prove, ordinary numerical nondeterminism
as the cause. BF16/FP32 precision alone does not require different results:
execution/reduction order can change rounding and subsequent optimizer updates.
Do not mistake the failed strict bitwise assertion for demonstrated instability,
or claim restoration is numerically validated without a baseline variability
control and direct pre/post-restore tensor checks.

## Main Entry Point and Scheduled Rollout (2026-10-12)

Supersedes the copied-entry-point policy above: the user requested integration
and automatic recovery. `pretrain_suspend_test.py` was deleted. `pretrain.py`
now has opt-in `suspend_control_dir`, `suspend_after_steps`,
`suspend_poll_interval_steps=10`, `suspend_wait_poll_seconds=2`; defaults disable
the hook. There is no test allocator cap or benchmark-specific behavior in the
production entry point. Queue/handshake helpers remain in `training_suspend`.

The resource-owning launcher starts a private loopback Redis and confines the
new NCCL preload to its child tree. The supervisor owns restore and disk
fallback: 900-second restore deadline, 120-second rank acknowledgement deadline,
up to three disk restarts per boundary. It verifies the complete regular DCP
checkpoint and carry=none before terminating its identity-checked process tree.
Fresh launch restores optimizer/EMA, original run settings and pending suspend
boundaries; occupied GPUs and explicit holds defer recovery without killing peers.
Normal training failures outside suspension are not silently retried forever.

The first injected failure exposed that torchrun ranks use separate sessions.
Cleanup now records actual descendants and PID/start-time/boot/host identities,
not an assumed shared session. A CPU regression verifies unrelated processes
are untouched. The installed Python lacks `os.pidfd_open`; signaling uses
psutil's PID-reuse checks plus the stronger recorded identity validation.

Verified through the real main entry point, no W&B:
- Two-GPU compiled XXS, two short pauses: exact weights, optimizer/EMA and
  per-step metric parity (`/work/dfm/tmp/suspend-main-two-20261012/result.json`).
- Scheduler XXS normal handoff and deliberately failed restore followed by
  fresh disk resume: both reached step 6 with exact model and optimizer/EMA
  equality to uninterrupted training
  (`/work/dfm/tmp/suspend-boundary-main-v2-20261012/result.json`).

Existing plan `logs/scheduler/dfm10_XL_epoch9_20260831` was edited under its
SQLite administrative lock, not replaced. Eight pending training rows now
represent one continuous process, resuming step 1M and ending epoch 3
(expected 1391204; final stop guard 1391214). It parks at 1050K, 1100K, 1150K,
1200K, 1250K, 1300K and 1350K. All existing evaluations remain. Terminal gates
depend directly on inference rows, not publication; failed inference and its
blocked descendants cannot prevent the next training lease. CPU publication
can finish alongside training. SQLite drains its inference servers first.

Control root/log: `logs/training/dfm14_XXL_wide/cooperative_1m_to_epoch3/`,
`training.log`. `active.json` identifies the current launch. Scheduler holds
offloaded training during evals; only the next training row authorizes restore.
No second watcher should operate on a supervised launch.
The current 991K-to-1M training remains unchanged. A detached reload watcher
requests scheduler drain, then reloads its code only after that row succeeds.
A changed stop request cancels the reload. Watch log:
`logs/scheduler/dfm10_XL_epoch9_20260831/cooperative-reload-watch.log`.

This is a controlled production trial with a tested disk escape path, not a
claim that full-size multi-hour in-memory parity has been proven.

## Transformer PrefixLM355K idle resume (2026-11-16)

User requested suspension at355000 and automatic in-memory resume after all
eight GPUs are idle for five continuous minutes. Armed
`scripts/watch_transformer_prefix_355k_idle_resume.py`; receipts are under
`logs/training/transformer48_dfm11_prefixlm_targetonly_20261114/control/idle-resume-355000/`.
The watcher submits355000 immediately but creates its hold only at that exact
ready boundary, preserving the350K eval handoff. It offloads using the existing
controller and delegates restoration to the existing supervisor. Idle requires
zero utilization, at most128MiB used per GPU, and no compute processes; any busy
observation resets the300-second timer. It never stops competing jobs. Status
is armed, not yet suspended.

## Sandwich B29K idle resume (2026-11-17)

Armed user-requested suspension at29000 for the current Sandwich B DFM11
PrefixLM/target-only trainer (observed at28400). Detached watcher:
`scripts/watch_sandwich_29k_idle_resume.py`; receipts under
`logs/training/sandwichB_dfm11_prefixlm_targetonly_20261115/control/idle-resume-29000/`.
It offloads at the exact boundary, then requests the existing supervisor to
resume from memory after all eight GPUs show zero utilization, at most128MiB
used each, and no compute processes for more than300 continuous seconds. Busy
observations reset the timer. Handles the first suspension without requiring
prior ready/resume receipts. Status: armed, not yet suspended.

---
type: Runbook
title: Bounded TP2 Multilingual Diagnostic Server
description: Exact-process-owned diagnostic Gemma server sharing physical GPUs 6 and 7 without interrupting XXL training.
tags: [dfm12, multilingual, diagnostic, gpu, operations]
status: draft
last_updated: 2026-09-26
confidence: high
---
# Bounded Diagnostic Server

Explicit user authorization on 2026-09-26 permits a small TP2 Gemma diagnostic
server in available GPU headroom, **never interrupting XXL**. This supersedes
the earlier single-GPU headroom restriction only for this bounded two-GPU
diagnostic resource plan, not for unrestricted teacher launches. Related:
[reviewer calibration](dfm12-multilingual-calibration.md).

Implementation: `dfm12/diagnostic_server.py`; tests:
`tests/test_dfm12_diagnostic_server.py`. The fixed default lifecycle directory
is `data/dfm12/multilingual-diagnostic-20260926/server/`. Existing roots are
refused, not overwritten. Existing pilot roots are unchanged.

## Commands

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.diagnostic_server launch
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.diagnostic_server status
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.diagnostic_server stop
```

Launch detaches a supervisor. Stop writes a cooperative request; the supervisor
cleans up only its own server processes. If the supervisor has exited, stop
acquires its released lock and applies the same exact-ownership cleanup.
Maximum lifetime is two hours (7,200 seconds), including startup. Startup is
bounded to 1,200 seconds. A runtime headroom floor of 4 GiB triggers cleanup of
the diagnostic processes only, protecting training. This floor is a precaution,
not a guarantee against all resource-contention effects.

Before launch, both HTTP port 8590 and internal port 29000 must be unused and
physical GPUs 6 and 7 must each have at least 40 GiB free. Device UUIDs bind the
server to the inspected physical devices independently of CUDA device order.
Initial observed free memory was **46,108 MiB (45.03 GiB)** on each device.

Resource contention is expected; this is **not zero-impact coexistence**.
During server autotuning, the coordinating agent observed XXL still advancing
at step 660925, with smoothed step time 7.49 seconds versus roughly 5.3 seconds
previously. No OOM was observed at that check. Avoiding interruption means not
stopping or mutating training, not guaranteeing unchanged training throughput.
Transient autotune allocations reduced observed free memory to 9,204 MiB on
each selected GPU, still above the diagnostic-only cleanup floor.

## Configuration

Endpoint: `http://127.0.0.1:8590/v1`.
Served model: `google/gemma-4-26B-A4B-it` from the existing cached revision
`4d7ae4984b7db7de8f8457170b3f1a419ee76d52`. Audit conda/CUDA include and library
paths match `dfm12/multilingual_run.py`; no dependency changes or downloads.

- Tensor parallelism 2; GPU utilization 0.18 per device.
- Maximum sequences 8; batched tokens 4,096; context 8,192.
- Eager execution; image/video/audio limits all zero.
- `--generation-config vllm`; `VLLM_USE_FLASHINFER_SAMPLER=0`.
- Internal `VLLM_PORT=29000`; localhost-only API binding.
- No diagnostic clients launched; readiness probes only request `/v1/models`.
- No W&B use; `WANDB_MODE=disabled` in the server environment.

## Ownership and Evidence

`ownership.json` persists supervisor and server-descendant identities: exact
PID, creation time, Linux process-start ticks, session ID and command line.
Every server process inherits a unique ownership token. Cleanup requires a
matching token, server session, creation time and start ticks. It never signals
a process group or a port owner. Linux pidfds bind TERM/KILL to the checked
process and prevent accidental signaling after numeric PID reuse. The audit
conda Python lacks Python pidfd bindings; the installed libc provides
`pidfd_open` and `pidfd_send_signal`, which the helper calls directly.

Shutdown gives TERM 35 seconds and then KILL 15 seconds, only to verified owned
processes. Descendant discovery also covers orphaned workers in the same server
session. `cleanup.json` records every signal, any survivors and post-cleanup
headroom. A hard-killed supervisor cannot enforce its own deadline; the stop
command provides exact-owned cleanup recovery in that case.

Other lifecycle records: `launch.json`, `status.json`, `headroom-before.json`,
`headroom-current.json`, `ready.json`, `server.log`, `supervisor.log`, and the
read-only `training-observation.json`. Read `ready.json` and current status;
a launch receipt alone does not establish readiness.

The first supervisor PID is **2642899**, API server PID **2642902**. The server
log confirmed all requested non-default settings and text-only mode. Seven
tests passed, including an actual isolated child-process cleanup test proving
that an unrelated process in the supplied inventory is not signaled. No XXL
or unrelated processes are owned or changed by this helper.

Readiness confirmed: `/health` and `/v1/models` returned HTTP 200 with the
requested model. At that check, physical GPUs 6 and 7 each had **8,454 MiB
(8.26 GiB) free**. All 18 training-related process identities recorded during
startup were still present with unchanged creation times/start ticks. This is
process continuity evidence, not a claim of unchanged training throughput.
The TP worker reported model weights of 23.96 GiB and 7.33 GiB available KV
cache, with 69,743 tokens of GPU KV capacity. No generation request was sent
by this worker. The parent/Poincare handoff is `handoff-ready.json` in the server
directory; direct agent messaging was unavailable, so readiness was relayed
through the coordinating parent.

Automatic cleanup deadline: **2026-09-26 09:25:53 UTC / 11:25:53 Europe/Berlin**.
Leave the server available for the diagnostic/calibration owner until its stop
request or that deadline; no need to keep the launching agent turn open.

The coordinating user authorized the shared page-index link for this run.

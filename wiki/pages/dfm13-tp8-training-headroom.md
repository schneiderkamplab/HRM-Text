---
type: Runbook
title: DFM13 TP8 Beside XL Training
description: Owned TP8 Gemma service with a training-priority memory guard.
tags: [dfm13, inference, operations]
status: stable
last_updated: 2026-10-01
confidence: high
---
# DFM13 TP8 Beside XL Training

Launcher: `scripts/serve_dfm13_tp8_headroom.py`. One TP8 server uses GPUs 0-7,
port 8810, alias `dfm13-gemma4`, eager execution, 16 sequences, a 2048-token
batch budget and 32768-token context. It does not own training.

The initial 0.05 utilization launch exceeded the 3 GiB free-memory reserve
during FlashInfer autotuning. It was stopped. The old inherited-token cleanup
missed vLLM workers whose environment changed; those exact owned processes
were removed using verified launch-session/start identities and pidfds.
The new launcher tracks its private session and verifies process start ticks
before signaling. A CPU-only owned-session cleanup check passed.

Superseding configuration: utilization 0.045 with
`--no-enable-flashinfer-autotune`, supported by installed vLLM 0.27.1.
The v2 attempt failed a transient port-bind preflight; v3 reached readiness.
Receipts: `logs/dfm13/shared-gemma4-tp8-headroom-20261001-v3/`.
Server PID 2992527, supervisor PID 2992508 at launch. Always check current
ownership/status rather than treating these historical PIDs as authority.

Measured KV capacity: 83005 tokens, 1.10 GiB per rank, 2.53 full-32K
requests. One short non-thinking smoke returned `OK` with a normal stop.
After smoke, GPU0 had 3096 MiB free and others 5400 MiB: GPU0 is only
24 MiB above the unchanged 3072 MiB guard. No load stress was performed.

Start with at most four total client requests when prompt-plus-output budgets
are at most 15K each; two for full-32K requests. Eight at 15K each exceeds
the measured capacity. Reduce concurrency on preemptions. The original memory
guard policy is superseded below.
An owned `stop.request` file in the server root requests shutdown.

Training remained live and progressed through step 2977365 at about 1.24s
per step after the retry. Initial autotuning temporarily slowed training,
so process survival must not be described as zero performance impact.

## Superseding No-Reserve Policy

2026-10-01, explicit user authorization: no artificial training free-memory
reserve is required. Removed the 3 GiB runtime shutdown threshold and the
extra 4 GiB startup margin. Startup still requires space for the configured
server budget; low free memory alone does not trigger auxiliary shutdown.
The fitting 0.045 utilization / 1.10 GiB-per-rank KV configuration is retained,
with autotuning disabled and 32K context. Ownership-specific cleanup remains
for actual process failure, supervisor failure, or an explicit stop request.

The original CPU supervisor was replaced by supervisor 2996200 using exact
PID/start-time verification; ready server PID 2992527 and TP workers were
adopted without restart. `no-reserve-handoff.json` records the transition in
the v3 root. Current status explicitly reports `free_memory_guard: false`.
Training was not modified or signaled. Tests cover exact-budget admission,
continuing at 1 MiB free, and retained explicit-stop cleanup.

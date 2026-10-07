---
type: Runbook
title: DFM13 XXL-wide 859500 Shared Gemma Handoff
description: User-requested checkpoint-safe pause and eight owned shared Gemma 4 26B-A4B replicas on the local B200 node.
status: stable
confidence: high
last_updated: 2026-10-06
tags: [dfm13, training, serving, checkpoint, audit]
---
# DFM13 XXL-wide 859500 Shared Gemma Handoff

On 2026-10-06 the user requested a stop only after `ephemeral_step_859500`
was fully written, followed by eight shared Gemma 4 26B-A4B servers with
1,024 sequence slots each. This supersedes the uninterrupted 850K-to-900K
segment on this machine. Do not automatically resume training.

## Ownership and Safety

- Plan: `logs/scheduler/dfm10_XL_epoch9_20260831`; stop request installed.
- Training root: `checkpoints/dfm13/XXL-wide-from-dfm11-epoch2`.
- Exact torchrun PID at arming: 2838116; scheduler PID: 3992530.
- Watcher: `scripts/pause_859500_launch_shared_gemma.py`, PID3021440
  after the preflight model-path correction; consult `watcher.json` for identity.
- Receipts/logs: `logs/dfm13/pause-859500-shared-gemma-20261006/`.
- The watcher validates DCP metadata and every referenced shard extent, then
  hard-links immutable checkpoint payloads into
  `checkpoints/preserved/dfm13-xxlw-pause-859500` before signaling torchrun.
- Signals use an exact pidfd and checked process start identity. No broad kill.
- Wait for training, scheduler and GPU release; under PlanLock prepare the
  existing 900K training row to resume from the saved tag. Leave stop.request.

## Shared Serving Profile

Reuse `scripts.serve_dfm13_26b_isolated` and the existing shared lifecycle:

- Local instruction-model snapshot:
  `/work/dfm/.home/.cache/huggingface/hub/models--google--gemma-4-26B-A4B-it/snapshots/4d7ae4984b7db7de8f8457170b3f1a419ee76d52`.
  Both weight shards and its native `chat_template.jinja` are present. The
  earlier brainsurgery shorthand directory lacked the chat template and was
  rejected during preflight before any server launch.
- Environment: `/home/ucloud/miniforge3/envs/audit`.
- Eight TP1 replicas, GPUs0-7, endpoints `http://127.0.0.1:8800..8807/v1`.
- Model aliases: `dfm13-gemma4` and `google/gemma-4-26B-A4B-it`.
- GPU memory utilization0.95; max_num_seqs1024; max_model_len32768;
  max_num_batched_tokens16384; compiled execution (not enforce-eager).
- Native checkpoint chat template, gemma4 tool/reasoning parsers, text-only
  inputs, VLLM_USE_FLASHINFER_SAMPLER=0, environment-local CUDA/NVCC.
- Per-GPU/per-run compilation caches; only owned server sessions are cleaned.
- The shared launcher advertises client concurrency384; 1024 is the server
  admission ceiling, not a command to start 1024 requests from every client.
- No generation/audit clients are automatically launched by this handoff.

`training-stopped.json` proves the stop/resume preparation;
`servers/status.json` reports per-replica readiness. Arming/launch receipts are
not proof that servers are ready. A failure leaves training paused.

## Verified Outcome

The handoff completed on 2026-10-06: checkpoint `ephemeral_step_859500`
was verified and preserved before torchrun was terminated. The scheduler
exited with its stop request intact; the 900K training row is pending with
`resume_from_tag=ephemeral_step_859500` and its original remaining settings.

Supervisor PID3025064 launched all eight servers. By approximately 17:46
Europe/Berlin, all endpoints were ready. A chat-completions smoke on each
port 8800-8807 returned `OK` with `finish_reason=stop`, using the native
template and `enable_thinking=false`. No W&B logging was involved.

Cold startup took approximately 25 minutes, including a shared FlashInfer
Blackwell MoE build (267 Ninja targets), kernel autotuning and graph capture.
FA4 handles attention; the FlashInfer MoE backend is separate from attention
and the disabled FlashInfer sampler. Idle GPUs during the CPU build were not
evidence of failure. Each replica reported approximately 115.59 GiB KV cache,
550,673 cache tokens and 16.81 full-32K requests of capacity; the 1024 sequence
limit does not imply that 1024 full-context requests fit simultaneously.

Other clients began using the shared endpoints immediately after readiness.
This handoff launched no such clients and did not interrupt them. Servers
remain detached and available; training remains paused.

## Explicit Training Resume

The paused state above was superseded by the user's explicit resume request
on 2026-10-06 at approximately 21:55 Europe/Berlin. No GPU processes or shared
server supervisors remained at preflight; nothing needed termination.
Checkpoint completeness was rechecked successfully. The existing scheduler
stop request was cleared and a detached runner (PID3159943) launched from
the `hrm` environment with its bin directory prepended to PATH and
`--persistent-vllm`. The existing plan and training arguments were retained.

The training log confirmed `step=859500`, `start_epoch=3`, batch-position
restoration and W&B resume of `DFM5/dfm10-xxl-wide`. Training advanced beyond
859515 with all eight GPUs utilized; the next scheduled boundary is 900000.
Log: `logs/training/dfm13_XXL_wide/to_900000/train_until_step_900000.log`.

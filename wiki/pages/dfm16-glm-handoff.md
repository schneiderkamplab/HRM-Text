---
type: Runbook
title: DFM16 GLM 5.3 Flash GPU handoff
description: Automatic eight-GPU GLM startup and disjoint full-scale generation alongside Odin.
tags: [dfm16, simplestories, glm, gpu, handoff]
status: draft
last_updated: 2026-11-02
confidence: high
---
# GLM alongside Odin

The user requested GLM 5.3 Flash on all eight GPUs once available, in addition to
Odin. This supersedes the planned Flash/Qwen server allocation, while preserving
the full 502,000-source campaign and approximate 300K accepted aim.

The GPUs currently hold the external Mistral evaluation server. Zero GPU utilization
does not mean they are free: about 176 GB per GPU remains allocated. The handoff
never signals that server or any unrelated GPU owner.

## Prepared deployment

Model `zai-org/GLM-5.3-Flash`, pinned revision
`46a050bec13002ad29ee795c16e61cf4fa3c4a9c`, is downloaded to
`/work/dfm/models/GLM-5.3-Flash`. The existing euroeval environment has vLLM 0.31.0,
native GLM5Next support, and FlashInfer 0.7.0.post1. No existing environment was upgraded.
The [official vLLM recipe](https://recipes.vllm.ai/zai-org/GLM-5.3-Flash)
documents native FP8 weights, four-way tensor parallelism and mandatory thinking.

Two TP4 replicas use all eight GPUs, respecting the requested 4/4 split:

| Role | GPUs | Endpoint |
| --- | --- | --- |
| GLM generation | 0–3 | `http://127.0.0.1:8890/v1` |
| GLM specialist auditing | 4–7 | `http://127.0.0.1:8891/v1` |

Both use a 16,384-token context, 128 sequences, FP8 KV cache and 85% memory
utilization. These launch settings are prepared, not yet live-tested while the
GPUs are occupied. Each server must pass model discovery and a real final-content
smoke before generation ownership changes. Failed startup leaves Odin running.
Only server process groups created by this handoff can be terminated by its startup cleanup.

GLM cannot obey a non-thinking request. Its isolated adapter uses documented
`reasoning_effort: low`, retains raw reasoning in receipts, and parses only final
content. Total generation budget stays 6,144 tokens; source verdicts have a 2,048
total-token budget and QA slot preparation 1,024, allowing reasoning before their
compact final outputs. Specialist reviews allow 4,096 total tokens and retain the
existing compact findings grammar. Odin's settings and 100 actual sends/rolling
minute limit are unchanged. This model-specific amendment does not rewrite the
historical non-thinking experiments.

## Automatic handoff

[Watcher](../../scripts/dfm16_glm_gpu_handoff.py) is detached, PID **3711812** at launch.
Its status and logs live in `logs/dfm16/glm-handoff-20261030/`:
`status.json`, `handoff.log`, `download-complete.json`, `software-receipt.json`.
Check the live PID/status rather than assuming the historical PID still applies.

It requires all eight GPUs below 500 MiB and no compute processes for three
consecutive checks spaced 30 seconds apart. It also requires the completed pinned
weight download. Occupied ports cause failure, not adoption of an unknown service.
After both owned GLM replicas pass health and smoke checks, it drains the original
Odin generator through `audit_pipeline` SIGTERM handling, captures its credential
only in process memory, and prepares immutable disjoint chunk assignments.

[Dual generation worker](../../scripts/dfm16_dual_generation.py) preserves completed
receipts, keeps every started/partly dispatched chunk with Odin, and routes 31/32
of untouched chunks to GLM. The remainder stays with Odin. This is one allocation
of the existing 502K sources, not a duplicate generation campaign. Separate worker
locks and telemetry avoid conflicts; the shared runtime retains per-chunk ownership.
Odin retains the global controller lock and persistent request-rate ledger.

The original Odin process is restarted as the assigned Odin worker; the old PID
is therefore expected to exit during handoff. Inspect
`dual-generation/{odin,glm}/status.json` and corresponding telemetry afterward.
GLM-specific staged and source adapters are isolated files. Raw responses, prepared
sources and model-specific review provenance are preserved with each conversation.

## Auditing and interpretation

[Live GLM audit worker](../../scripts/dfm16_glm_live_audit.py) covers the full source
manifest through `audit_pipeline`. Each row waits asynchronously for its durable
generation result, then runs the three v13 specialist scopes. Source failures are
recorded without semantic admission. Literal quotations are checked. The journal
records generator identity, parent-result hash and whether GLM is an independent
reviewer for that particular output.

These are additional audit results, not automatic admission. GLM reviewing its
own generation is self-review. GLM outputs still need independent Odin review;
that final cross-model admission integration is not implemented by this handoff.
The prior Flash/Qwen-plus-Odin configuration's 11.8% false-acceptance observation
cannot be claimed for this new model pair. No old validation result, accepted row,
production dataset or active training input changes merely because servers start.

## Verification

87 tests passed across the handoff and production suites. New checks cover all-eight
GPU availability, preservation of started/completed chunk ownership, disjoint
assignment, mandatory reasoning/final-content parsing, truncated-response rejection,
GLM review provenance and durable specialist methods. Model weights are present;
server startup and throughput remain pending GPU availability. Existing repository
OKF errors/warnings are unchanged.

## Rearmed after workspace outage, 2026-10-30

The prior watcher exited when the workspace became inaccessible; its last status
was stale. Odin also exited with an inaccessible SQLite ledger. After access was
restored, the user requested rearming. Historical watcher logs, PID and software
receipt were archived with a `before-rearm` suffix. The new watcher is PID 576770;
Odin resumed its existing journals as PID 576769. No old output was regenerated
intentionally and ambiguous interrupted sends retain the existing unresolved rule.

The wait loop now tolerates failed workspace status writes, resetting the free-GPU
check count and retrying after 30 seconds without launching or signaling anything.
Status includes `last_checked` so a dead watcher's last state is distinguishable
from a live check. Both new processes were verified live; all GPUs remain occupied
(about 85 GB each), weights are ready, and no GPU owner was interrupted. Five
handoff tests pass. See `logs/dfm16/glm-handoff-20261030/rearm.json`.

## Rearmed watcher outcome, 2026-10-31

The rearmed watcher (PID 576770) attempted GLM startup at 01:04 and failed at
01:10 with `RuntimeError: GLM startup failed; Odin was not interrupted` in
`handoff.log`; it then exited. No GLM replica ever went live and dual-generation
was never activated; the "both processes live" claim above is superseded.

## Root cause and third rearm, 2026-11-01

The startup failure was diagnosed from the archived server logs: both replicas
loaded all 62 GLM weight shards, then died in vLLM fp8 weight post-processing
when the bundled DeepGEMM JIT called `deep_jit::CUDA::find_cuda_toolkit` — no
CUDA toolkit was visible (`CUDA_HOME`/`CUDA_PATH` unset, no `/usr/local/cuda`,
no nvcc on the server PATH). DeepGEMM requires nvcc at least 12.9.

Third rearm, 2026-11-01 14:40 (supersedes the "neither process is running"
state above):

- `scripts/dfm16_glm_gpu_handoff.py` was hardened: startup preflight fails
  closed before waiting when neither `ODIN_API_KEY` in the environment nor a
  live Odin owner exists; a dead or absent Odin owner at handoff time no
  longer aborts (drain is skipped and the odin worker receives the watcher's
  environment credential); a live owner with an unexpected cmdline still
  fails closed; owned GLM server groups are now cleaned up on any failure
  before `handoff-complete.json` exists. New helpers `odin_owner`,
  `owner_command`, `owner_environ` are unit-tested in
  `tests/test_dfm16_glm_handoff.py`; 15 handoff/fullscale tests pass.
- The watcher now launches with `CUDA_HOME=/home/ucloud/miniforge3/envs/hrm-cu132`
  (full CUDA 13.2 toolkit; nvcc sanity-compiled off-GPU before arming), which
  the script passes to both server subprocesses through `os.environ`.
- Watcher PID **961946** (historical; verify live). `software-receipt.json`
  was regenerated for the hardened script hash. Prior logs and receipts were
  archived with a `before-rearm-1793540347` suffix.

## Fourth rearm and successful handoff, 2026-11-02

The hrm-cu132 toolkit fix was insufficient: DeepGEMM JIT then passed, but
FlashInfer JIT warmup failed compiling the trtllm fused MoE kernel with
`cublasLt.h: No such file or directory` — the conda cuda-toolkit package ships
cuBLAS headers only under `targets/x86_64-linux/include`, not `$CUDA_HOME/include`.
That attempt failed closed (watcher exited, owned servers cleaned up) and was
archived with a `before-rearm-1793625655` suffix.

Successful rearm, 2026-11-02 ~14:13 (watcher PID 1713633 historical):
`CUDA_HOME=/home/ucloud/miniforge3/envs/audit` (full toolkit with
`targets/x86_64-linux/{include,lib}`) plus `CPATH` and `LIBRARY_PATH` pointing
at those `targets` directories. GLM JIT warmup (DeepGEMM, FlashInfer trtllm
MoE, allreduce) and CUDA-graph capture completed; both replicas passed health
and the exact-content smoke; `handoff-complete.json` was written with
generation_pid 1752670 (GLM), odin_pid 1752669, audit_pid 1752671.

The hardened owner-absent path was exercised in production: the Odin worker
had died at 07:53 with a transient `sqlite3.OperationalError: database is
locked` after reaching chunk 671, so the handoff skipped draining and used the
watcher environment credential for the odin worker, exactly as hardened.
Assignment preserved 669 completed chunks; odin owns 105 chunks (13,440 rows,
started chunks plus the 1/32 remainder) and glm owns 3,148 chunks (402,928
rows). The GLM live audit worker runs over the full manifest; its results
remain additional evidence, not admission.

## User-requested GLM pause, 2026-11-02 ~14:52

The user requested stopping the GLM servers until they explicitly command a
resume. The GLM worker and GLM live audit worker were SIGTERM-drained (both
exited within ~30 seconds with in-flight rows handled by the shared runtime),
then both owned vLLM replicas were stopped; all eight GPUs read 0 MiB. The
API-only odin worker (PID 1752669) was left running and continues its 105
assigned chunks. Campaign `status.json` reads `glm_paused_odin_generating`
and `glm-paused.json` records the pause marker with the stopped PIDs.

Resume procedure (no watcher relaunch, no `prepare` re-run —
`handoff-complete.json` and the immutable `dual-generation/assignment.json`
remain valid, and completed receipts are skipped by the shared runtime):

1. Start both replicas exactly as the handoff launched them (identical
   vLLM arguments; environment `CUDA_HOME=/home/ucloud/miniforge3/envs/audit`,
   `CPATH`/`LIBRARY_PATH` at that env's `targets/x86_64-linux/{include,lib}`,
   `CUDA_VISIBLE_DEVICES=0,1,2,3` for port 8890 and `4,5,6,7` for 8891).
2. Verify `/v1/models` health on both ports plus the exact final-content
   smoke with `reasoning_effort: low`.
3. Launch `python -m scripts.dfm16_dual_generation glm` and
   `python -m scripts.dfm16_glm_live_audit` with `PYTHONPATH` set; launch the
   odin worker only if PID 1752669 has since died (it needs `ODIN_API_KEY`).

A resume was started on 2026-11-02 ~23:30 and aborted by the user before
health or smoke: the warming replicas were stopped, the workers were never
launched, and no rows were affected. The odin worker had already reported
`complete` over all 105 assigned chunks, so no odin relaunch is pending.
Campaign state remains paused, awaiting an explicit user command.

## Post-completion GPU memory state, 2026-11-02 ~15:00

After `handoff-complete.json` the watcher (PID 1713633) exited and both GLM
replicas remain running at the script's `--gpu-memory-utilization 0.85`
(`scripts/dfm16_glm_gpu_handoff.py:104`), holding ~155.7-159.5 GiB per GPU
(worker steady ~159.5 GiB on nvidia-smi). This leaves only ~22.7 GiB free per
B200 for co-resident work, superseding the earlier same-day state where
replicas held ~81.5 GiB (~0.45) and left ~101.9 GiB headroom.

Measured co-residency limit on 2026-11-02: a B-size (65,536 vocab) FSDP smoke
with 4,096-token microbatches fit in ~22.6 GiB device delta, while a
16,384-token microbatch (`GAS 1`) OOMs. Co-resident training must budget
against ~22.7 GiB until the replicas are drained or relaunched with a lower
utilization.

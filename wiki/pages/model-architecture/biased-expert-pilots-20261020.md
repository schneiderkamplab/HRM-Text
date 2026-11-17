---
type: Runbook
title: Source-biased dense MoE and MoS XL pilots
description: Independent 3.80M to 3.82M continuations using source-aligned metadata without changing sampled row order.
status: draft
confidence: high
last_updated: 2026-10-22
tags: [mimir2, moe, mos, routing, experiments]
---
# Source-biased expert pilots

## October 22 recovery and downstream scheduling

Both expert pilots finished training to 3.82M. Their strict EMA Mimir2 exports
are `exports/mimir2_biased_{moe,mos}_step3820000_ema_hf`. The residual/memory
GAS4 export also succeeded: its previous failure was a relocated training
chat-template path, not failed training. Use the exporter's explicit
`--chat-template-path incoming/mimir-xl-20261015/data/sampled_dfm15/chat_template.jinja`;
it verifies exact equality with the production tokenizer reference.

After machine restart, the missing local SQLite authority was restored using
SQLite's backup API from `state.backup.sqlite` in the existing plan directory;
integrity check returned `ok`. The 64 interrupted Engram inference claims were
reconciled, retaining 137 completed inference jobs. An additional cloning bug
had separated inference log directories from export/merge paths. Recovery
links retained output files into the canonical task/shard layout and gives
inference/export pairs the same directory. Never rerun completed training to
repair this error.

`scripts/recover_pilot_evaluations_20261022.py` installed the full matched
1,047-inference-job suites in order: Engram remainder, biased dense MoE,
residual plus memory branches, biased dense MoS. Each retains merges,
publication and averages in its own DFM5 pilot run. Ordinary XL continuation
waits for inference-terminal barriers, not successful publication.

The restored runner uses SQLite, persistent vLLM, 64 clients and server
concurrency 1024; compiled Mimir2 uses `--no-async-scheduling`. The Rich monitor
is in the existing `hrm-0:4` window, refreshed every 30 seconds, not a new tmux
session. W&B publication initially failed after restart because the local
login was absent; credentials must be restored and failed publication rows
retried independently of inference.

### Explicit user pause on October 22

**Resumed later October 22 at the user's request:** verified `stopped`, zero
running claims, administrative lock released, and all eight GPUs empty.
Cleared the stop and relaunched the same SQLite plan with 64 clients and
server concurrency 1024. The existing `hrm-0:4` monitor remains active.

The user requested a graceful scheduler stop during Engram. `stop.request`
is set; dispatch stops immediately, active clients drain, then the runner
closes its own persistent servers and writes the final `state.backup.sqlite`.
An intermediate consistent snapshot is `pause-requested-20261022.sqlite`.
Do not clear the stop or launch training automatically during this pause.
The monitor remains in `hrm-0:4`.

To resume after status shows `stopped` and no running claims, clear the stop
with `python -m eval_scheduler clear-stop --plan-dir
logs/scheduler/dfm10_XL_epoch9_20260831`, then use the same detached SQLite
launch: hrm Python, hrm bin prepended to PATH, `--persistent-vllm`, all eight
GPUs, `--max-clients 64 --server-concurrency 1024`. Retain the current database,
not an older TSV import. If local disk was lost, restore the final persistent
backup through SQLite's backup API first. W&B authentication must be restored
before retrying publication failures.

User authorized both pilots after Engram on October 20. The existing SQLite
plan is `logs/scheduler/dfm10_XL_epoch9_20260831`, database
`/tmp/dfm14-xxl-wide-production/jobs.sqlite`. Install/update only under its
administrative lock; preserve runtime state and release the lock afterward.
Installation completed; both rows are pending and the administrative lock
was verified released. The active branching pilot was not modified.

## Comparison contract

### Muon-only continuation queued October 22

`scripts/schedule_muon_pilot.py --install` queues
`hrm-muon-XL-from-3800000` after the MoS inference-terminal barrier, before
ordinary XL continuation. This uses the unchanged dense v1 architecture to
isolate the optimizer change; no gates, branches, experts or Engram. It starts
independently at 3.8M and stops/checkpoints at 3.82M, with a separate same-named
DFM5 run and `checkpoints/hrm_v2/hrm-muon-XL-from-3800000` output directory.
Initially no downstream evaluation was queued. **Superseded later October 22:**
the user requested the full downstream suite. `scripts/schedule_muon_evaluations.py`
adds 1,047 inference tasks plus exports/merges/syncs/averages, 2,197 rows total,
to the same plan and the same Muon DFM5 run. The pilot wrapper first exports
strict EMA to `exports/mimir2_muon_step3820000_ema_hf`, using the relocated
template explicitly. Evaluations require successful training/export; ordinary
XL continuation waits only for the Muon inference-terminal barrier, so a
failed export or publication cannot strand it.

Base LR1e-5, auto recurrence scaling, BP8, GBS262144, GAS2 and the control's
FP32 FSDP2/BF16 compute settings are preserved. Muon momentum=.95, five
Newton-Schulz iterations, `muon_lr_scale=1`. This is a conservative untuned
optimizer pilot, not an assertion of matched update magnitudes. Auxiliary
embedding/head parameters use AdamW, whereas the original optimizer used
AdamATan2. Muon's full-matrix gather/FP32 iteration can be substantially slower.

`scripts/prepare_muon_checkpoint.py` explicitly converted the immutable source
to `checkpoints/hrm_v2/muon-initialization-step3800000`: 128 hidden matrix
tensors have zero Muon momentum/optimizer-local step; two auxiliary tensors
retain Adam moments/steps. Model weights, FP32 EMA, training step and dataset
cursor remain unchanged. Conversion publishes atomically and leaves a receipt;
normal optimizer-mismatch protections remain enabled. CPU save/load/update
regression testing passed. At dispatch, a no-W&B three-step plus two-step
save/resume qualification precedes the real pilot. The full pilot restarts
from the converted 3.8M source, not the smoke output. A qualification failure
does not block the already scheduled ordinary XL continuation.

### October 22 training-metric comparison

Local W&B histories contain 4,000 complete five-step measurements per arm
(gates: 3,999 after its five-step smoke/resume). The reusable CPU-only
`scripts/compare_pilot_training.py` reads the exact training run files named
in each training log. Results and input paths are preserved in
`logs/analysis/hrm_v2_pilot_training_comparison_20261022.json`.

Final 5K-step means, steps (3,815,000, 3,820,000]:

| Arm | Loss | Training accuracy | Exact accuracy |
| --- | ---: | ---: | ---: |
| Control | 0.725415 | 82.8315% | 48.5395% |
| Invocation gates | 0.725393 | 82.8323% | 48.5331% |
| Engram | 0.725394 | 82.8323% | 48.5436% |
| Residual + memory branches | 0.820034 | 81.4907% | 46.2860% |
| Biased dense MoE | 0.727676 | 82.7834% | 48.6097% |
| Biased dense MoS | 0.725914 | 82.8143% | 48.6052% |

No improvement is statistically robust in this final window. Circular-block
bootstrap uses 20K draws, 100/500/1,000-step sensitivity blocks, and Holm
correction across five pilots times three metrics within each window/block
analysis. Gates/Engram are paired by step; GAS4 branches/MoE/MoS versus GAS2
control use independent resampling because their observed batch fluctuations
do not align. All arms share source checkpoint, corpus, GBS262144 and base
LR1e-5, but GAS differs. This is single-run training-history evidence, not
multi-seed architectural or held-out generalization evidence. The branch
arm's degradation is large and robust; downstream evaluation remains a
separate test. Full-20K and last-10K summaries are also in the JSON.

Both independently start from the original `step_3800000` under
`incoming/mimir-xl-20261015/checkpoints/dfm15/XL-from-dfm14-epoch1`.
Neither uses Engram or the other pilot's trained weights.
Stop at 3,820,000; preserve optimizer/EMA and data cursor through dense
upcycling. Base LR 1e-5 with recurrence-aware auto scaling, BP8, GBS262144,
FP32 FSDP2 parameters, BF16 compute, block wrapping, no forward reshard,
no-sync accumulation, FA4 and compilation match the control.

| Pilot | Configuration | Total parameters |
| --- | --- | ---: |
| MoE | Two active MLP experts per layer, both H and L stacks | 2,390,851,648 |
| MoS | Two active complete L stacks, shared L recurrent state | 2,277,510,146 |

No n-grams, invocation gates, memory branches, residual branches, frozen
experts, or sparse execution. Experts are cloned with inherited optimizer/EMA
slots; routers start with zero learned logits. Function parity at initialization
is tested despite unequal metadata weights.

## Routing policy

The [source-domain sidecar](/pages/dfm15-metadata-routing-sidecar.md) is complete
for all 408,412,700 epoch-zero rows. Its SHA256 is pinned in each queued command
and verified before qualification/launch.

Category 1 (math/code/tool-agentic) adds `[ln(2), -ln(2)]` to router logits;
category 2 (language/chat/summarization/translation) reverses them.
Category 0 (mixed/uncertain) adds zero. Initially this means 80/20, 20/80,
and 50/50, respectively. Learned logits remain trainable.
Hold the full bias through 3.81M, then decay linearly to zero by 3.82M.
Evaluation never applies metadata bias.

### Preserve the control's data order

Mid-epoch switching to the existing homogeneous sampler is intentionally
rejected by resume validation. Do not bypass that protection or relabel the
source checkpoint as an epoch boundary.

The opt-in `+data.routing_categories=true` instead attaches one source category
per packed input token. All tokens in an example share its source label;
padding is neutral. `homogeneous_categories=false` keeps the normal sampler,
row cursor, packing, inputs, labels and positions unchanged. Bias is therefore
source-specific within mixed microbatches, not an average across unrelated
sources. Dense MoE and dense MoS both already accept token-aligned router bias.
This mechanism defaults off and is accepted only for v2 training.

## Qualification and scheduling

`scripts/schedule_biased_expert_pilots.py --install` adds:

1. MoE after the Engram terminal barrier.
2. MoS after the MoE terminal barrier.
3. Ordinary XL continuation to 3.90M after the MoS terminal barrier.

Each pilot has its own `checkpoints/hrm_v2/hrm-biased-{moe|mos}2of2-XL-from-3800000`
directory and a same-named new W&B run in DFM5.
No downstream evaluations are added by this script.

`scripts/run_expert_pilot.py` first runs a no-W&B five-step compiled native
upcycle/save/resume qualification. Try GAS2, then GAS4, then GAS8, advancing
only for an explicit CUDA OOM or sampled free memory below 8192 MiB on any
GPU. Other failures stop the pilot. Successful qualification starts the
20K pilot afresh from 3.8M, not from the smoke checkpoint.
The selected GAS, command and evidence are recorded under
`logs/expert-pilot-qualification/<run>/selection.json`.
One-second memory sampling and five steps cannot certify all future peaks.

Failures exhaust the pilot row with no automatic retries; terminal barriers
release the next pilot/ordinary training. Existing training/eval processes
are not interrupted. GPU qualification runs only when the scheduler grants
all eight free GPUs.

## Validation

Full-size CPU preflight checks Hydra/Pydantic settings, source checkpoint
completeness, carry-free resume, original tensor mappings/shapes and new
parameter classification. CPU tests verify identical packed data with routing
enabled, cloned-model initial parity, 80/20 routes, router gradients after
expert divergence, bias decay/removal in eval, separate outputs, and
failure-tolerant scheduling.

GPU memory, speed, large-model specialization and downstream gains remain
unmeasured until these queued jobs run.

October 20 validation: **64 tests passed** across biased-pilot batching,
schedule policy, expert mixtures and v2 extensions. Both full-size preflights
passed. OKF validation retains one unrelated oversized scheduler page and
15 existing artifact-link warnings; no new page validation errors.

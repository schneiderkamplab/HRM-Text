---
type: Technical Reference
title: Engram pilot preparation and qualification — October 20
description: Contextual multi-head n-gram export, serving inputs, state migration, bounded collision measurements and remaining GPU qualification.
status: draft
confidence: high
last_updated: 2026-10-21
tags: [engram, ngram, mimir2, transformers, vllm, qualification]
---
# Engram pilot preparation

## Completed pilot: October 21

The capacity-matched pilot completed 3.80M to 3.82M with GAS2, superseding
the pending training qualification statements below. Training took 7h10m15s
including startup/checkpoints, with recent steps around 1.27-1.29 seconds.
Reported peak allocated memory was 164,400 MiB; reserved was 170,282 MiB.
Downstream evaluation was subsequently scheduled as described below; results
are not yet available.

Local W&B histories, deduplicated by training step, contain 4,000 observations
per run. Final 10K-step means (2,000 observations each):

| Metric | Ungated control | Engram |
| --- | ---: | ---: |
| Loss | 0.72578857 | 0.72576801 |
| Token accuracy | 82.82927% | 82.83103% |
| Exact accuracy | 48.64384% | 48.64275% |

This is essentially unchanged training performance, not demonstrated benefit
from the additional 608.7M parameters. No significance test or downstream
claim follows from these means. Evidence: local run
`wandb/run-20261020_174455-hrm-engram-moe-budget-XL-from-3800000`, control
`wandb/run-20261018_212824-dfm8-xl-from-dfm6-dfm7-epoch5-clean-full`, and
`logs/training/hrm_v2/hrm-engram-moe-budget-XL-from-3800000/train_until_step_3820000.log`.

### Full downstream suite queued

`scripts/schedule_engram_3820k_evals.py --install` added 1,047 inference jobs
and their merges, publication and nine averaging jobs to the existing SQLite
production plan. Prefix: `mimir2-engram-3820000-`; results root:
`logs/scheduler/mimir2_engram_3820000`. The suite matches the full gated/control
pilot template, including standard, DFM and EuroEval. Results target the
Engram training run in DFM5, with the inherited fractional epoch/step mapping.
It follows the already queued expert pilots and precedes ordinary XL 3.90M
continuation. The continuation depends only on terminal inference, not
successful merges/syncs. Installation preserved running jobs, backed up the
database, exported the TSV and released the administrative lock; DAG validated.

EMA export: `exports/mimir2_engram_step3820000_ema_hf`. Its checkpoint buffer
`model.ngram.alpha` is 1.0 (the config initialization default of zero is not
the loaded value). The explicitly relocated chat template matches the
production control template by SHA-256. The exporter now accepts
`--chat-template-path` and rejects disagreement with the tokenizer reference.

Compiled BF16 vLLM/HF tiny-model prefill and three decode-token parity passed
with contextual four-head n-grams and two requests. Evidence:
`logs/engram-pilot-qualification/vllm-parity.log`. This is not a full-size
checkpoint logits comparison. Initial fork startup failed CUDA initialization;
`VLLM_WORKER_MULTIPROC_METHOD=spawn` passed. Evaluation server flags explicitly
include `--no-async-scheduling`, disabled prefix caching and chunked prefill;
no eager mode. The serving test used 64 MiB KV cache and exited cleanly without
interrupting ongoing MoE training.

## Capacity-matched pilot queued (October 20)

Supersedes the initial unscheduled 65,536-bucket proposal below.
`scripts/schedule_engram_pilot.py` installed
`hrm-engram-moe-budget-XL-from-3800000` in the existing SQLite production
plan, after the GAS4 branching pilot's evaluation terminal and before ordinary
XL continuation to 3.90M. Training remains 3.80M to 3.82M from the original
dense checkpoint, not from the branching pilot; separate DFM5 run/checkpoints.
Four heads, orders 2/3, 196,608 buckets/order, contextual gates, absolute 2K
warm-in, base LR 1e-5 with auto recurrence scaling, GBS 262144 and BP8.
Other v2 features are disabled.

Meta-model counts: dense XL 1,786,773,504 parameters; duplicating all MLPs adds
603,979,776; duplicating the L stack adds 490,733,568 (excluding router overhead).
The proposed tables add exactly 603,979,776 and contextual projections add
4,718,592: total added 608,698,368, total model 2,395,471,872.

Superseded GAS decision (October 20): GAS4 was initially queued conservatively,
not demonstrated necessary. User approved trying GAS2 first. The pending row
now qualifies GAS2 at full capacity/full alpha, falling back to GAS4 only for
an explicit CUDA OOM or sampled free memory below 8192 MiB on any GPU.
Both candidates must complete compiled save/resume. Other errors fail the
pilot, not silently change GAS. The selected GAS and evidence are written to
`logs/engram-pilot-qualification/selection.json`; the actual training command
is rewritten to that GAS. Scheduler graph, current pilot and ordinary XL
continuation are unchanged. Three policy/scheduling unit tests passed.
One-second GPU memory polling can miss brief peaks; headroom is a guard,
not a long-run fit guarantee.

Matched GAS2
control logs reached about 159,500 MiB peak allocated / 164,104 MiB reserved.
Engram does not duplicate recurrent activation streams; a GAS2 smoke is the
right way to establish whether GAS4 is necessary.

The queued command first runs a separate no-W&B, five-step XL compiled
save/resume smoke with full memory alpha, same capacity and queued GAS.
Only successful qualification starts the independently initialized 20K pilot.
Failure reaches a terminal dependency and does not strand ordinary training.
Seven scheduling/native preparation tests passed; full-size CPU configuration
and inherited checkpoint-shape preflight passed. GPU tests remain unrun.
No Engram downstream evaluation has been added yet; CUDA vLLM graph/logit
qualification is still required before scheduling that comparison.

This is the repository's Qwen/Engram-inspired variant, **not an exact Qwen
reproduction**. Candidate: orders 2/3, four heads, 65,536 buckets, XL width
1536, continuation 3.80M → 3.82M with absolute 2K warm-in. No pilot was
scheduled or trained. No production process, checkpoint, dataset, W&B run or
environment was changed. Existing dirty changes were preserved.

The final report and evidence are in
`logs/engram-preparation-20261020/result.md` and sibling logs/JSON files.

## Implementation

The actual native `models/ngram_memory.py` hashes newest-first with base
`65599 + 2*head`, modulo buckets at every step. Each order concatenates heads
of width `hidden_size/heads`; orders sum. Eligibility requires all adjacent
positions, so packed resets invalidate crossing n-grams. The optional gate is
`sigmoid(query(RMSNorm(x)) + key(RMSNorm(memory)))`, with epsilon 1e-6 and no
learned normalization weights. Injection is `x + alpha * gate * memory` before
recurrence. Legacy defaults remain one head, no gate.

Transformers `/work/dfm/transformers` adds both config fields, copies the native
math, and passes the fields through strict consolidated-weight conversion.
The authoritative modular file generated configuration/modeling files through
the existing converter. Table names remain `model.ngram.tables.N`, ordered by
order then head; contextual weights are `model.ngram.query.weight` and
`model.ngram.key.weight`. Alpha is a required persistent buffer. Missing keys
and wrong shapes fail loading. Native/HF request caches retain bounded token
and position tails; existing beam reorder/reset behavior remains supported.
Cache cropping/speculation remain unsupported.

vLLM `/work/dfm/vllm` implements the same retrieval/gate math using the shared
HF module's parameter layout. The synchronous worker builds newest-first
bounded token windows from scheduler-owned request token records, including
generated tokens. Each request starts afresh; chunk boundaries, interleaving,
slot reuse and preemption do not create model-global history. Padding uses
invalid -1 entries. A persistent worker tensor is filled before model execution
and passed during dummy/profile/capture and real forwards, keeping graph input
addresses stable. The model math has no request-dependent Python dispatch and
does not require eager serving. CPU window preparation is O(scheduled tokens ×
maximum order); this is not host-offloaded embedding tables.

N-grams explicitly reject async scheduling, speculative decoding, dual batch
overlap and prompt embeddings. Existing global restrictions on pipeline
parallelism and quantized loading remain. Sparse MoS still requires eager.
Multi-GPU serving, CUDA graph replay, and end-to-end vLLM n-gram logits are
**not yet qualified**. Stable buffers and CPU fullgraph math are implementation
evidence, not a CUDA execution result. No-ngram/default tests remain passing.

## State and parity evidence

- Native regression set: **55 passed**, including new FP32/BF16 dense-to-Engram
  DCP migration, unsharded save/load, exact next optimizer update and FP32 EMA
  preservation, diagnostics and compiled activation-checkpointed Engram math.
- This set includes **two-rank CPU FSDP DCP save/resume** of four-head
  contextual memory, with exact subsequent parameter, momentum, variance,
  step and EMA equality; absolute 3.8M/2K warmup boundaries also pass.
- HF suite: **15 test methods passed** (with feature subtests). Native/HF
  FP32 logits use rtol 2e-5 / atol 2e-6; BF16 uses 0.05 / 0.03. Tests include
  identical greedy IDs from native full recomputation versus HF cached
  generation, causal/PrefixLM, packed resets, independent interleaved histories,
  cache/beam behavior, strict missing-gate-weight rejection and legacy defaults.
- vLLM: **9 CPU contracts passed**, including strict contextual weight/buffer
  mappings and fullgraph `aot_eager` feature math against HF under unequal
  prefill chunks, decode, request reordering, slot replacement and padding.
  The actual worker staging hook also passes a CPU stable-buffer/reuse test.
  This does not execute vLLM CUDA attention kernels or compare engine logits.

Fresh optimizer state is eagerly initialized by AdamATan2: zero step and
moments, EMA equal to the new parameter. “Fresh” does not mean absent slots.
No optimizer loader change was necessary for this variant.

Reproduce native tests with `OMP_NUM_THREADS=2 MKL_NUM_THREADS=2` and
`/home/ucloud/miniforge3/envs/hrm/bin/python -m pytest -q
 tests/test_engram_preparation.py tests/test_ngram_contextual.py
 tests/test_v2_extensions.py tests/test_hrm_v2.py`.
HF uses `HRM_TEXT_SOURCE=/work/dfm/HRM-Text` with the isolated mimir2 Python and
`-m unittest discover -s /work/dfm/transformers/tests/models/mimir2 -v`.
vLLM contracts use its `.venv/bin/python`, with
`PYTHONPATH=/work/dfm/vllm:/work/dfm/transformers/src`, running
`tests/models/language/generation/test_mimir2_contracts.py` directly.

## Actual-token occupancy and collisions

`scripts/measure_ngram_occupancy.py` mmaps the candidate DFM15 data read-only.
This run sampled **100,000 input tokens / 345 rows**, epoch 0, starting at
row **25,161,810**, the source checkpoint's preserved 3.8M row cursor.
Inputs match the dataset convention: instruction followed by response without
its final target token. Boundaries reset per row; the final row is truncated.
It is a deterministic contiguous sample, **not a random or population estimate**.
It does not reproduce multipack bin order/padding or measure a full 20K run.

Distinct tuples are stored exactly, not as potentially colliding fingerprints.
Memory is bounded by O(max_tokens × sum(orders)) Python tuple/integer storage
plus one 65,536-element int64 bucket histogram. No full corpus scan or full
corpus set is created. There are 99,655 bigram observations (49,597 distinct,
50,058 repeats) and 99,310 trigram observations (67,002 distinct, 32,308 repeats).

“Excess collision rate” is `(distinct - occupied buckets) / distinct`.
“Participating” is the fraction of distinct n-grams in buckets containing at
least two distinct n-grams. Neither is repeated-observation frequency.

| Order | Head | Occupied / 65536 | Excess collision % | Participating % | Max distinct bucket load |
| --- | --- | --- | --- | --- | --- |
| 2 | 0 | 34454 | 30.53 | 54.01 | 7 |
| 2 | 1 | 34678 | 30.08 | 53.49 | 7 |
| 2 | 2 | 34765 | 29.91 | 53.02 | 7 |
| 2 | 3 | 34582 | 30.27 | 53.70 | 8 |
| 3 | 0 | 42035 | 37.26 | 63.76 | 8 |
| 3 | 1 | 41907 | 37.45 | 64.12 | 8 |
| 3 | 2 | 41843 | 37.55 | 64.08 | 7 |
| 3 | 3 | 42066 | 37.22 | 63.75 | 8 |

Raw `occupancy.json` also contains occupancy fractions, collision counts and
colliding unordered distinct pairs. Head-specific bases do not imply statistical
independence or any demonstrated quality improvement.

## Opt-in diagnostics

Passing `diagnostics={}` to native memory forward collects detached scalar
retrieval/input/contribution RMS, contribution/input ratio, and gate
mean/min/max/saturation fraction. Without a dictionary, there are no diagnostic
reductions, hooks, transfers, logging or persistent state changes. Tests check
unchanged outputs and parameters and detached statistics. This is a small-smoke
API, not enabled production instrumentation.

Synthetic CPU demonstration (seed 17, width 16, buckets 31, nonzero random
tables, alpha 0.7): gate mean 0.50524, range 0.03020–0.98216, saturation outside
[0.01, 0.99] zero, contribution RMS 0.04824, contribution/input ratio 0.04921.
These are **not trained/post-warm-in pilot measurements**.

## GPU blockers and runnable preparation

All eight GPUs were occupied: 100% utilization, roughly 113–116 GiB allocated.
No GPU was claimed and no GPU experiment was run. XL peak memory, step time,
CUDA FSDP/compile save-resume, engine logits/generation parity, graph replay,
and post-warm-in diagnostics remain unmeasured.

`scripts/smoke_engram_xl.py` defaults to preview. `--run` requires all eight
GPUs idle, uses separate non-existing outputs, disables W&B, and runs 3 steps
from the source checkpoint followed by 2 resumed steps. Both Hydra/Pydantic
phase configurations and native XL meta-model construction were validated on
CPU, including inherited backbone shapes against source DCP metadata. It preserves the candidate data,
absolute warmup, XL FSDP transformer-block wrapping and compiled batch recipe;
all other experimental architecture features remain off. The script verifies
complete intermediate/final checkpoint receipts, captures phase logs and wall
time. Wall time includes load/compile/save; use training logs for step timing
and memory, and do not interpret five early-warm-in steps as steady-state data.
Idle checks are conservative snapshots, not a scheduler reservation.

The vLLM GPU parity entry point now accepts `--ngram`; on an independently
verified idle GPU run `examples/offline_inference/mimir2_parity.py --ngram
--compiled --dtype bfloat16`, and repeat with `--causal`. It explicitly disables
async scheduling, uses two unequal prompts, nonzero tables, three generated
tokens, and HF ID/logprob comparisons. Run only in the isolated development
environment; no environment installation or upgrade is needed or authorized by
this preparation. Completing these GPU checks remains a prerequisite to a pilot.

## Related

- [Native v2 implementation](hrm-text-v2-implementation.md)
- [Mimir2 Transformers](mimir2-transformers.md)
- [Mimir2 vLLM](mimir2-vllm.md)

## Documentation validation

Full OKF validation found one unrelated pre-existing/concurrent issue:
`request-shared-eval-scheduler.md` is 51,441 bytes, above the 50,000-byte limit,
plus 15 unresolved local-artifact link warnings. That dirty page was not edited
as part of this work. The new concept is below the size limit and indexed.

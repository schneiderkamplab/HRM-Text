---
type: Experiment
title: Embla optimized training kernels
description: Kernel implementations, numerical comparisons and full-recipe activation evidence.
status: stable
last_updated: 2026-11-16
confidence: high
---
# Embla optimized training kernels

Follow-up to [Embla experiments](embla-experiments.md). The released upstream
model explicitly replaces private training kernels with eager reference ops.
The initial native implementation was correct and bounded in memory, but much
slower than a specialized implementation. Compilation alone was intermediate.

## Implemented replacements

- `embla_fa4_window`: FA4 sliding softmax, per packed document. Prompt queries
  use symmetric local attention within the prompt; answer queries use a
  right-aligned causal suffix against full-document KV. Noncontiguous prompt
  masks are rejected rather than silently reinterpreted.
- `embla_fused_relu`: Triton squared-ReLU forward/backward, FP32 accumulation,
  original denominator and GQA. BF16 input products use tensor cores; products
  involving FP32 intermediates use TF32x3 (not single-pass TF32). Query and KV
  gradients use owned tiles and a grouped reduction, not scatter atomics.
- `embla_fused_sparse`: indexed GQA softmax forward/backward without materialized
  gathered K/V or score matrices. FP32 KV atomics operate only on valid indices;
  final KV gradients are cast once. All-masked rows produce zero outputs/gradients.
- `embla_single_topk`: score bounded query tiles against document keys and rank
  once, avoiding repeated top-k merging. Score workspace shrinks for long docs.

Reference paths remain available. New flags default false. Kernel heads currently
support dimensions32–128 and at most16 query heads per KV head. Native evaluation
can retain reference operations; architecture, weights, masks, loss, learning
rate and batch recipe are unchanged. Floating-point operation order is changed.

## Evidence before full-recipe qualification

Shared-GPU full-dimension causal BF16 microbatch (8192 tokens, no optimizer/FSDP):
5.888s reference versus1.989s combined kernels after warmup, approximately2.96x
throughput. Loss12.752168 versus12.752190, peak allocation54.85GB. These are
microbatch observations, not optimizer-step timings or a new epoch ETA.
Receipts: `logs/diagnostics/embla/full-kernels-benchmark.json` and
`full-kernels-profile.txt`. The subsequent tensor-core input optimization is
covered by the later kernel tests and full-recipe qualification, not this timing.

Packed causal/PrefixLM kernel tests cover odd lengths, GQA, FP32/BF16, output and
Q/K/V gradients. The sparse tests additionally cover duplicate keys and entirely
masked rows. Against the unchunked reference, sparse relative L2 errors are
below0.01%; chunked BF16 reference KV gradients differ by about0.35% because the
old path rounds each chunk's contribution before accumulation.

Small complete-model tests with the actual training precision (FP32 parameters,
BF16 autocast) passed causal, PrefixLM, and four-loop PrefixLM, including future
answer isolation and document isolation. Output relative L2 errors were
0.274%/0.902%/0.774%; parameter-gradient errors0.382%/1.608%/2.082%.
These are BF16 numerical comparisons, not bitwise equivalence or quality results.

Historical rejected probes: initial ReLU tiles exceeded B200 shared/tensor
memory; smaller tiles fixed this. Serial grouped KV backward was slow; per-head
work plus FP32 grouped reduction improved parallelism. An all-BF16-parameter
small-model combined test exceeded the3% gradient threshold (18.2%); it was not
accepted as the training-precision test. Individual kernels passed in that
fixture, and the actual mixed-precision recipe passed the unchanged3% threshold.

## Eight-GPU validation and rollout

Candidate configs: `logs/diagnostics/embla/candidate-configs-v6-kernels/`.
Campaign: `logs/diagnostics/embla/kernels-v7-qualification/`.
The earlier v6 attempt was stopped when real packed batches exposed recompilation
for each document length; the trainer resumed at259000. Sequence/key lengths
are now runtime inputs with specialization disabled. Five distinct lengths
reuse exactly one compiled variant of each kernel, verified by
`logs/diagnostics/embla/kernel-shape-cache.json`. The fresh campaign suspends
at259300 and preserves the earlier failed attempt.
The existing Transformer trainer was cooperatively suspended at259000 and
CUDA-offloaded for three real-data/full-optimizer eight-rank checks and a
four-loop CUDA suspension smoke. The campaign owns a temporary hold and requests
managed in-memory restoration in its cleanup path. Do not create another recovery
supervisor. Full-recipe checks passed on all24 ranks. The Transformer resumed from memory
at259300 with its original worker identities; subsequent training progress was
observed. Queue activation is recorded in `queue-activation.json` below.

The final CPU suite passes63 tests, including exports from cores with kernel
flags enabled. Export regression tests found that HF scans imports
even in disabled branches; portable export now explicitly removes training-only
kernel imports and retains reference inference, with all export tests passing.

Reproducers: `scripts/test_embla_fused_kernels.py`,
`scripts/test_embla_sparse_kernel.py`, `scripts/test_embla_fused_model.py`, and
`scripts/qualify_embla_kernels_campaign.py`. The latter is a one-off campaign,
not a persistent scheduling service; its output directory must be fresh.

## Final qualification and activation

Short real-data, full-optimizer benchmarks (two warm updates after the first
update, eight ranks; identical global batch262144/GAS4 and model recipes):

| Recipe | Previous seconds/step | Optimized seconds/step | Throughput gain | Peak allocated/rank |
| --- | ---: | ---: | ---: | ---: |
| Causal/all-token | 11.37 | 2.99 | 3.81x | 93.83 GiB |
| PrefixLM/target-only | 12.50 | 3.20 | 3.91x | 93.83 GiB |
| Four-loop PrefixLM/target-only | 28.70 | 5.73 | 5.01x | 83.89 GiB |

Values average the warm observations across ranks; this is not a sustained epoch
throughput or model-quality result. First updates included35–44s of cold setup;
subsequent changing packed lengths did not recreate the earlier compile storm.
Full receipts and ranges are in the campaign's `throughput.json`.

The existing suspension smoke completed both CUDA cycles and continued training,
but **failed exact equality between independent trajectories**. Its step2 loss
already differed before the first suspension, so that comparison is not an exact
restore oracle with parallel floating-point reductions. The failed campaign and
traceback remain unchanged; they are not relabeled as a bitwise pass.

A new direct test snapshots the same process's model, optimizer, EMA, gradients,
inputs and CUDA RNG tensors immediately before/after offload, with no intervening
optimizer update. Two actual CUDA cycles preserved all645 tensors bit-for-bit,
and a subsequent training step succeeded. Evidence:
`same-process-restore-ema/result.json`; reproducer:
`scripts/test_embla_kernel_cuda_restore.py`. An earlier AdamW variant also passed.
This verifies restoration without weakening the original equality assertion or
claiming bitwise reproducibility across separately executed training trajectories.

`scripts/activate_embla_kernels.py` checks eight-rank receipts/configuration and
software hashes, exact live restoration, CPU tests and the restored trainer. It
backs up SQLite, updates only24 unclaimed pending Embla train rows with compare-
and-swap predicates, and verifies readback. Commands now reference immutable
`candidate-configs-v6-kernels` rather than the historical v5 configs. Evidence:
`kernels-v7-qualification/queue-dry-run.json` and `queue-activation.json`.
Other training definitions, dependencies, evaluation schedule and global defaults
are unchanged. Portable exports deliberately use reference inference kernels.

## Next performance opportunities (historical inspection)

Implementation and benchmark follow-up: [supervised-position heads](supervised-output-head.md).

- FA4 PrefixLM currently copies the prompt mask to CPU on every local-attention
  invocation. Cache validated document/prompt lengths once per model forward and
  batch windows with varlen calls to reduce synchronization and launch overhead.
- Tune ReLU² and sparse backward tiles/work distribution, including sparse KV
  atomics. They together accounted for roughly35% in the last detailed profile;
  that profile precedes final dynamic-length/input-dot tuning, so refresh it on
  current real-data recipes before treating the percentage as current.
- Fuse residual mixing, gating and normalization to reduce stacked source copies,
  tiny batched matrix operations and repeated activation recomputation.
- Test GAS2 rather than GAS4 at the same262144 global tokens. Observed allocated
  peaks were84–94GiB, but reserved memory reached about150GiB; free capacity is
  not proof that twice-sized microbatches will fit. Recheck packing/epoch counts.
- Target-only training still projects *all* hidden positions into the262144-token
  vocabulary before ignoring prompt labels. Selecting supervised positions before
  the head preserves the objective if metrics/divisor/scattering are maintained,
  and can reduce logit memory and head work. A fused head/softcap/CE could further
  reduce workspace. This changes executed FLOPs: update the compute ledger and
  comparison policy rather than claiming the previous match automatically holds.

These are follow-up candidates, not additional measured speedups or queue changes.

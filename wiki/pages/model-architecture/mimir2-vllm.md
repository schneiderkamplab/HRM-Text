---
type: Reference
title: Mimir2 vLLM integration and environment
description: Isolated source integration, supported serving semantics, qualification and development environment.
tags: [architecture, mimir2, vllm, environment, inference]
status: draft
confidence: high
last_updated: 2026-10-20
---
# Mimir2 vLLM Integration

## Environment and checkout

Fresh conda environment **`mimir2`** (not `hrm2`), not a production clone:
`/home/ucloud/miniforge3/envs/mimir2`. Activate with `conda activate mimir2`.
Python 3.13.16, Torch 2.11.0+cu130, Transformers 5.21.0.dev0, and editable
vLLM 0.23.1rc1.dev102 based on `a46abb7ae68acc13a4fc5870db98619b3f97c6e0`.

Full official repository cloned to `/work/dfm/vllm`, branch `mimir2`, based on
the revision already used by production rather than upgrading Torch/vLLM in
the production environment. The companion full Transformers checkout is
`/work/dfm/transformers`, also branch `mimir2`. Both are editable installs in
the new conda environment; production environments and running jobs are unchanged.

Python dependencies were installed through `uv pip`, with matching precompiled
vLLM artifacts (`VLLM_USE_PRECOMPILED=1`, commit above, wheel variant `cu132`).
`uv pip check` passed. The initial attempt to install Torch 2.11 from the
PyTorch cu132 index failed because that version was not present there; the
normal package index supplied 2.11.0+cu130, matching production.

CUDA toolkit 13.2 was installed with conda. Saved environment variables:

```text
CUDA_HOME=/home/ucloud/miniforge3/envs/mimir2
FLASHINFER_WORKSPACE_BASE=/work/dfm/vllm/.runtime-cache
```

The pip CUDA compiler bundle resolved inconsistent compiler/header versions
and failed FlashInfer JIT compilation. **Superseded:** do not use its
`site-packages/nvidia/cu13` directory as CUDA_HOME; use the conda toolkit.
The isolated FlashInfer cache avoids sharing development builds with production.

## Implementation

`vllm/model_executor/models/mimir2.py` uses existing HRM attention and vLLM
parallel projections plus the companion HF implementation's cache-independent
feature math. Supported: default v1 recurrence, invocation gates, top-k MLP
experts, dense L-stack mixtures with shared/separate states, residual branches,
input-dependent mixing and H/L memories. Sparse MLP configurations execute as
dense masked reference mixtures, not optimized sparse kernels.

Every physical layer, recurrence and stack expert gets a distinct cache slot.
HF split projections are packed in `[gate,q,k,v]` and `[gate,up]` order.
Duplicate/mixed/incomplete projections and missing model parameters or feature
buffers fail loading. vLLM's own internal KV quantization scale defaults are
not incorrectly required in the HF checkpoint.

PrefixLM treats the full submitted prompt as bidirectional. Compare HF with
prompt token_type_ids set to one; ordinary causal HF prefill is not equivalent.
Chunked prefill and prefix caching must remain off for PrefixLM. The
`prefix_lm=false` configuration instead uses normal causal attention.

Superseded (2026-10-19): sparse MoS was initially rejected pending request-owned
state/cache integration. It now supports cached eager serving, first-token or
PrefixLM prefix-mean routes and shared/separate states. Original scheduler prompt
records determine routes independently of request slots and preemption. Sparse
projections/MLPs skip unselected tokens; attention and KV allocation remain
full-batch. Prefix-mean routing re-embeds the prompt each decode step. Do not
claim k/n attention or memory savings. `--enforce-eager` is required.

**Superseded (2026-10-20):** n-gram decoding now has a synchronous request-window
implementation and CPU contracts; see [Engram preparation](engram-preparation-20261020.md).
N-gram CUDA engine parity and graph replay remain unmeasured. Quantized loading, pipeline parallelism and speculative
decoding are also rejected. Multi-GPU and compiled serving are not qualified.
Production exports/scheduler are not switched to this development implementation.

## Validation

### Eager and sparse execution limits (2026-10-19)

| Configuration | Eager mandatory? | Execution |
| --- | --- | --- |
| No MoS | No | Fixed stack execution; graphs require qualification |
| Dense MoS | No | All stacks execute, routed outputs combined |
| Sparse MoS | Yes | Dynamic request selection/nonzero, variable shapes and skipped stacks |
| MoE, including `moe_sparse=true` | No | All MLP experts execute, top-k weights mask outputs |

The MoE path preserves mathematical routing but is not fused sparse dispatch.
Sparse MoS requires eager because current selection/scatter control flow is
not CUDA-graph-safe; this is an implementation limitation, not a property of
mixtures. Graph-compatible sparse execution needs padded/bucketed fixed-capacity
dispatch or suitable fused kernels. `--enforce-eager` disables both compilation
and CUDA graphs. Dense/non-MoS serving is permitted without it, but the earlier
parity results below used eager and do not qualify compiled execution.

Later on 2026-10-19, the tiny combined-feature BF16 test passed with
`mimir2_parity.py --features --compiled --dtype bfloat16`: torch.compile,
piecewise prefill and full decode graphs captured successfully; two requests
and three generated tokens matched HF IDs/logprob tolerance. This qualifies
that small configuration, not full-size or multi-GPU serving. The 3.82M gated
pilot/control comparison is queued without eager; see the [pilot runbook](hrm-text-v2-gated-pilot.md).

All twelve Transformers CPU test methods passed again in the fresh conda env.
Five vLLM CPU contract tests passed: slot coverage, projection packing and
ordering, malformed/duplicate inputs, unsupported-feature guards, and strict
feature-buffer loading.

Tiny GPU FP32 smoke passed with default features and with combined nonzero
gates, MLP/stack mixtures, separate L states, residual mixing and H memory.
The combined-feature causal configuration passed too. Two unequal-length
prompts with three generated tokens each matched HF greedy IDs and logprobs
(`atol=rtol=0.002`). Tests use 64 MiB KV, short contexts, eager execution and no
W&B; they do not establish full-size performance or production readiness.
The combined-feature PrefixLM BF16 smoke also passed, with identical greedy
IDs and logprob tolerance `atol=rtol=0.03` against the CPU BF16 reference.

Commands from `/work/dfm/vllm`, after activation:

```bash
python tests/models/language/generation/test_mimir2_contracts.py
CUDA_VISIBLE_DEVICES=7 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 MAX_JOBS=8 \
VLLM_ENABLE_V1_MULTIPROCESSING=0 \
python examples/offline_inference/mimir2_parity.py --features
```

Check actual free GPU memory before a smoke; do not stop production jobs.
See `docs/models/mimir2.md` in the vLLM clone for serving limitations and commands.

## Related

- [Full XL control parity](mimir2-control-serving-parity.md): 131 identical tensors,
  corrected special tokens/effective regex pipeline, 9/9 identical generations;
  remaining compiled BF16 logprob differences are explicitly quantified.

- [Transformers implementation](mimir2-transformers.md)
- [Native v2 implementation](hrm-text-v2-implementation.md)

---
type: Reference
title: Mimir2 Transformers implementation
description: Full upstream Transformers checkout with a modular HRM-Text-v2 model, strict conversion, and CPU parity evidence.
tags: [architecture, transformers, mimir2, export, hrm-v2]
status: draft
confidence: high
last_updated: 2026-10-19
---
# Mimir2 Transformers Implementation

## Checkout and conventions

On 2026-10-19, cloned the **full** `huggingface/transformers` repository into
`/work/dfm/transformers`, based on upstream commit
`4c414256ddce7b3c896cb624d55d1299ad963d20`, and created branch `mimir2`.
This is an independent sibling repository, not a partial vendored package or
an installed replacement in the production `hrm` environment.

Authoritative implementation:
`src/transformers/models/mimir2/modular_mimir2.py`.
It inherits upstream HRM-Text components; Transformers' converter generates
`configuration_mimir2.py` and `modeling_mimir2.py`. Do not edit generated files.
Public classes are `Mimir2Config`, `Mimir2Model`, `Mimir2ForCausalLM`, and
`Mimir2PreTrainedModel`, with AutoConfig/AutoModel/AutoModelForCausalLM registration.
The user-facing documentation is `docs/source/en/model_doc/mimir2.md` in that checkout.

The isolated `.venv` uses system site packages for existing Torch, with its own
editable Transformers install and development dependencies installed through
`uv pip`. Use the repository-pinned `ruff==0.14.10`; a newer Ruff introduced
unrelated repository-wide style fixes, which were reverted before continuing.

**Environment update, 2026-10-19:** the user subsequently requested a fresh
conda environment named `mimir2`. Both editable source packages are installed
there, with an independent Torch/CUDA stack; this supersedes `.venv` as the
primary development environment. See [vLLM and environment](mimir2-vllm.md).

## Coverage and limits

Structural options default off. Loaded default weights preserve v1 forward
semantics. Implemented optional gates, dense/sparse MLP experts, L-stack experts
with shared/separate states, residual streams, input-dependent mixing,
H/L recurrent memories, and causal n-gram embeddings. Every recurrent expert
invocation has independent cache slots. Effective alpha buffers are restored
from weights rather than restarting warmups during inference.

PrefixLM still requires explicit `token_type_ids`: one for prefix and zero for
response. Applying the Gemma chat template alone does not construct this mask.
Use eager/SDPA for the qualified CPU path. Generic FlashAttention is rejected
for PrefixLM; this does not replace the native specialized FA4 implementation.

Superseded (2026-10-19): sparse MoS initially required non-cached execution.
Cached eager/SDPA now preserves prompt-owned routes in `Mimir2DynamicCache`,
including beam reorder/select/repeat and reset. Selected expert KV updates
scatter into full-batch slots; sequence length comes from the always-executed
H stack, not an optionally idle first L expert. Cache cropping is rejected.
N-gram caching supports
beam reordering but explicitly rejects cache cropping/speculative decoding.
Fullgraph compilation and distributed HF serving remain unqualified.

Native optimizer/EMA upcycling, inactive-gate donor updates, metadata routing
schedules, specialist composition, and Muon remain native training recipes.
HF fresh-weight initialization is not asserted identical to native training
initialization. The tested parity contract is identical loaded weights.

## Conversion

`src/transformers/models/mimir2/convert_mimir2_weights_to_hf.py` consumes a
**consolidated LMHead state dict** and flattened native architecture JSON.
The caller selects EMA/raw weights first; FSDP shards are not accepted as such.
It splits G/Q/K/V attention and gate/up MLP projections, preserves feature
parameters and alpha buffers, validates all names/shapes strictly, and refuses
to overwrite a nonempty export directory. Tokenizer/template copying is optional.
It rejects post-norm/asymmetric H overrides rather than dropping semantics.

This supersedes the previous blanket statement that v2 has no HF implementation,
but **does not remove** the production converter's v2 rejection.
The original lack of a vLLM architecture is superseded by the later
[local vLLM integration](mimir2-vllm.md), with explicit unsupported-feature guards.
Production training, exports and scheduler were untouched.
Older pilot configs missing `gates_enabled` must explicitly enable it to match
their saved weights.

## Validation

Twelve focused CPU test methods, including feature-combination subtests, passed:

- Native FP32 logits for default and seven optional/combined configurations,
  causal and PrefixLM, with nonzero feature parameters (`rtol=2e-5`, `atol=2e-6`).
- Native BF16 parity with relaxed numeric tolerance (`rtol=0.05`, `atol=0.03`).
- Bitwise upstream HRM-Text forward parity with default features and identical weights.
- Strict conversion and AutoModel save/load, including persistent feature strengths.
- Cached/full forwards, greedy and beam generation, n-gram cache reordering.
- Left padding, BP2/5/8 gate-gradient boundaries, and activation-checkpointed gradients.

Reproduce from the Transformers checkout:

```bash
HRM_TEXT_SOURCE=/work/dfm/HRM-Text OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 \
  .venv/bin/python -m unittest discover -s tests/models/mimir2 -v

PATH="$PWD/.venv/bin:$PATH" .venv/bin/python utils/modular_model_converter.py \
  src/transformers/models/mimir2/modular_mimir2.py --num_workers 1

PATH="$PWD/.venv/bin:$PATH" make style
```

No full-size/GPU qualification or production rollout is implied by these tests.

## Related

- [Native v2 implementation](hrm-text-v2-implementation.md)
- [Gate pilot](hrm-text-v2-gated-pilot.md)

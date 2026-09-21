# PrefixLM implementation comparison

This experiment compares the causal baseline, bolgacg's existing PrefixLM
proposal, and a phase-aware library prototype against pinned Transformers.
It does not modify the registered llama.cpp submodule checkout or publish
anything. Worktrees, environments, model weights, logits, and logs live under
the ignored `logs/prefixlm-comparison` directory.

## Variants and attribution

- Baseline: `c9a5eeeb34ab8f794ea7510ca52d25da13728a5b`.
- Existing proposal: [bolgacg's PR](https://github.com/noctrex/llama.cpp/pull/1),
  head `66c7c5ed26b8251a45534ecb9d173275d7ee65a1`, base
  `bc3455a4a9398aad58c3b730c6e061b770677917`.
- `existing-original.patch` preserves that proposal exactly. `existing.patch`
  transplants it onto the baseline, changing only the renamed C++ metadata
  enum identifiers and diff context. Its attention/cache behavior is retained.
- `proposal-original` checks out the exact historical head. Its GGUF header
  uses the old metadata key names; tensor names and tensor bytes are identical
  to the modern fixture. Do not mix its header with the newer loader.
- `replacement.patch` retains the proposal's capability getter, clarifies the
  model comment, and turns oversized noncausal/logical batches into recoverable
  errors. The harness implements the proposed explicit prefill/causal-decode
  policy using the existing attention switch and a scoped reset.

The replacement is a **library prototype**, not the complete server patch.
No server scheduling, prompt-cache, restore, speculative-decoding, or retry
integration is claimed. The runner explicitly clears state for reset tests;
those results cannot establish that a server automatically clears it.
Likewise, the scoped mode switch is in the harness, not new implicit behavior
of `llama_decode`. Existing low-level causal behavior remains available.

No new attention implementation or Metal kernel is involved. The existing
proposal is credited to bolgacg. The replacement and comparison harness were
developed with Codex assistance. Upstream submission remains a separate task.

## Reproduce

From the parent repository root, on Apple Silicon with Xcode and CMake:

```bash
uv venv logs/prefixlm-comparison/venv --python 3.12
uv pip install --python logs/prefixlm-comparison/venv/bin/python -r scripts/prefixlm_comparison/requirements.lock
logs/prefixlm-comparison/venv/bin/python scripts/prefixlm_comparison/prepare.py --build
PYTHONPATH=llama.cpp/gguf-py logs/prefixlm-comparison/venv/bin/python scripts/prefixlm_comparison/fixture.py --output logs/prefixlm-comparison/fixture
logs/prefixlm-comparison/venv/bin/python scripts/prefixlm_comparison/compare.py --workspace logs/prefixlm-comparison --variants baseline existing replacement proposal-original
logs/prefixlm-comparison/venv/bin/python scripts/prefixlm_comparison/compare.py --workspace logs/prefixlm-comparison --device metal --tolerance 0.003
logs/prefixlm-comparison/venv/bin/python scripts/prefixlm_comparison/compare.py --workspace logs/prefixlm-comparison --device metal --flash on --tolerance 0.003
```

The experiment's Python environment is independent of the parent package's
Python requirement. The lock pins the Transformers source commit
`ff2421c67f35cc83a0fbabbc2633c96734685918`. Do not fix the base Python
environment to run this experiment.

`prepare.py` refuses unexpected worktree revisions or changes. It records
patch and executable hashes in `manifest.json`. Each variant links its own
build of llama.cpp. The exact original revision uses a separate worktree and
build; the other three share a common base for controlled comparison.

## Correctness cases

The tiny fixture is FP32, seed 73, 128 vocabulary entries, width 64, one layer
per L/H stack, H=2 and L=3. All three metadata forms (true, false, absent) use
identical weights. No tokenizer or quantization is involved.

The HF oracle runs real `HrmTextForCausalLM` with explicit token types. It also
checks its cached outputs against an independent full forward containing the
prefix plus a causal suffix. A native step emits raw FP32 logits plus timing,
return status, and KV positions. The same token stream is supplied to every
engine; sampling divergence cannot change later test inputs.

The cases cover prefix future visibility, answer future leakage, chunked vs
single-token answers, explicit causal control, one-token prefixes, resetting
a conversation, foreign sequence isolation, and physical batch limits.
Rejected-input tests check that existing KV state is unchanged. The false
and absent metadata controls must retain causal behavior.

The comparison intentionally reports failures for the baseline and existing
proposal. It exits unsuccessfully when the replacement fails its reference,
admission, metadata, or relational checks. Default CPU FP32 max-absolute-error
tolerance is `1e-4`; the explicit Metal tolerance is `0.003`. Reports retain
actual max error, RMSE, relative L2, and top-1 agreement so a pass threshold
cannot hide the size of a discrepancy. The tests detect leakage even where
top-1 tokens remain unchanged.

## Real Mimir smoke comparison

Download revision `2844f0178e695d7d9ce182cb660671fd34c76ce5` of
`danish-foundation-models/DFM-Mimir` to `logs/prefixlm-comparison/mimir-hf`
using `huggingface_hub.snapshot_download`, including weights, config, tokenizer,
chat template, and license. Then run:

```bash
logs/prefixlm-comparison/venv/bin/python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(
    "danish-foundation-models/DFM-Mimir",
    revision="2844f0178e695d7d9ce182cb660671fd34c76ce5",
    allow_patterns=["*.json", "*.safetensors", "*.jinja", "LICENSE"],
    local_dir="logs/prefixlm-comparison/mimir-hf",
)
PY
PYTHONPATH=llama.cpp/gguf-py logs/prefixlm-comparison/venv/bin/python scripts/prefixlm_comparison/real_model.py --model logs/prefixlm-comparison/mimir-hf --output logs/prefixlm-comparison/real
logs/prefixlm-comparison/venv/bin/python scripts/prefixlm_comparison/compare.py --workspace logs/prefixlm-comparison --suite real --device metal --tolerance 0.03
logs/prefixlm-comparison/venv/bin/python scripts/prefixlm_comparison/compare.py --workspace logs/prefixlm-comparison --suite real --device metal --flash on --tolerance 0.03
```

The real model exporter uses the same tensor mapping as the tiny fixture.
Source BF16 values are exported as FP32 without changing their values. An
early F16 export probe was rejected because small BF16 values are not all
exactly representable as F16. The GGUF uses
`no_vocab`: tokenization and chat rendering are performed once with the
checkpoint's HF tokenizer and saved in `real/prompts.json`. This checks the
runtime's logits, **not** llama.cpp's tokenizer/chat-template integration.

Three prompts cover Danish, English, and a Danish multi-turn conversation.
Each answer uses four tokens chosen by the HF reference. Compare both
single-token decode and a four-token causal answer chunk. This is a real-model
smoke test, not DAISY/MultiWikiQA, a language-quality score, or a long-context
benchmark. Real-model error tolerances must be examined alongside measured
logit margins and agreement; do not loosen them merely to make tests pass.

Fused attention uses F16 KV in this harness; unfused tests use F32 KV. The
reports label flash mode, so differences between these paths include cache
precision. Weights are not 4-bit/8-bit quantized in either suite.

Timings are diagnostic cold-prefill/four-token samples from synchronized
calls. They include mode-switch graph preparation and omit tokenization.
They are not statistically stable throughput estimates. Peak RSS is process
memory, not a complete accounting of Metal allocations. Run engines serially
and without other model work before interpreting timings.

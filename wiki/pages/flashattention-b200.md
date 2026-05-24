# FlashAttention On B200

Last updated: 2026-05-20  
Confidence: high  
Scope: Local adaptation of HRM-Text attention code for NVIDIA B200.

## Decision

Use FlashAttention 4, not FlashAttention 3, for B200.

## Why

- FA3/Hopper source and wheels were tried and did not produce a viable B200 runtime.
- Local experiments hit kernel/runtime issues and then CUTE/WGMMA architecture macro failures when trying to force SM100 behavior through the Hopper path.
- FA4 has explicit Blackwell/SM100 code paths under `flash_attn/cute`.

## Installed Dependency

Project dependency line:

```text
flash-attn-4[cu13] @ git+https://github.com/Dao-AILab/flash-attention.git#subdirectory=flash_attn/cute
```

`pyproject.toml` also declares the git source and the PyTorch cu130 index.

## Code Changes

- `models/flash_attention_prefixlm_v2.py`
  - removed FA3 custom torch op path
  - uses `flash_attn.cute.flash_attn_varlen_func`
  - runs prefix and causal varlen passes, then combines outputs

- `models/layers.py`
  - removed `flash_attn_with_kvcache`
  - cache path updates key/value tensors and uses `torch.nn.functional.scaled_dot_product_attention`

## Verification

Earlier verified:

- `python -m py_compile models/flash_attention_prefixlm_v2.py models/layers.py`
- FA4 B200 forward smoke test
- PrefixLM forward/backward CUDA smoke test
- cache attention CUDA smoke test
- imports for `pretrain`, `simple_inference_engine`, and `evaluation.engines`

## Residual Risk

Full training-step validation remains the next meaningful test once data exists.


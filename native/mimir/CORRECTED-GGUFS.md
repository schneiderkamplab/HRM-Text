# Training-faithful Mimir GGUFs — 2026-09-21

Prepared from `danish-foundation-models/DFM-Mimir`, revision
`2844f0178e695d7d9ce182cb660671fd34c76ce5`, using converter commit
`4122b9a81` in the llama.cpp submodule. Files are in `logs/mimir-corrected/`.
These are new local artifacts, not replacements for existing release packages
or the app's bundled asset. They have not yet been uploaded to Hugging Face.

| File | Bytes | Decimal size | SHA-256 |
|---|---:|---:|---|
| `dfm-mimir-q4_k_m.gguf` | 1167417504 | 1.17 GB | `8c811ca72589112f00306e8b3a23f83944751d13d3fce6dfdb39df8b31726e49` |
| `dfm-mimir-q8_0.gguf` | 1913200800 | 1.91 GB | `b4ac0d7493ffc3e56720c380ac8ed23bf3c16c60900e2bfa7f7551c654b09fce` |
| `dfm-mimir-bf16.gguf` | 3588300960 | 3.59 GB | `f2f8940a2e7dc6d6ab53ab68cfa51a52b686d8999033c3fa5b3d7392a885fc48` |

The 16-bit artifact is BF16, matching the original checkpoint's precision.
Q4_K_M is a mixed quantization, not uniformly four bits for every tensor.
Both quantized files were generated directly from the corrected BF16; no
quantized-to-quantized conversion was used. Checksums, individual license copies
and export/quantization manifests accompany the files. `SHA256SUMS` covers all three.

## Correction

Training loads `tokenizer.json` directly. Our old conversion/reference used
`AutoTokenizer`, which applied the HF export's `fix_mistral_regex=true` flag.
The HRM converter now loads the raw tokenizer graph and recognizes its
space-to-`▁` normalization and split configuration as `gemma4`. Other model
converters retain their existing AutoTokenizer behavior. No heuristic based only
on the model name selects this pre-tokenizer.

All three corrected files have `tokenizer.ggml.pre=gemma4`, retain the checkpoint's
chat template and PrefixLM metadata, and mark all 256 byte-fallback tokens.
Unlike the public noctrex file, we retain those byte-token types; the complete
native encode/decode regression suite below passes. BF16's **259 tensor payloads
are bit-identical** to our previous BF16 export: the correction changes tokenizer
metadata, not model weights.

Native tokenizer, chat and qualification reference generators now share
`tests/tokenizer_reference.py`, which loads the raw graph without the export-time
regex rewrite. The old numerical/HF-reference qualification reports are historical;
this preparation does not silently reinterpret them as training-faithful evidence.

## Validation

[Machine-readable results](corrected-gguf-results.json) contain file hashes,
precisions and actual generation outputs. For **each** precision:

- **724/724** tokenization, decoding and chat-template comparisons against the raw
  training graph pass, including randomized Unicode and whitespace cases.
- **19/19** independent training-audit chat cases pass.
- CPU and Metal chat smoke tests pass with context/batch 1024 and a 32-token budget.
  `Hvad hedder Danmarks hovedstad?` → `Danmarks hovedstad hedder København.`
  `What is 2 + 2? Answer briefly.` → `4`.
- The native client uses Mimir's embedded chat template for every generation.

This is bounded artifact qualification, not a rerun of full quality benchmarks,
long-context/performance studies, Linux/CUDA/Vulkan checks or mobile-device tests.

## Reproduce

From the repository root, using the established converter Python environment:

```sh
python native/mimir/export.py \
  --model logs/prefixlm-comparison/mimir-hf \
  --output logs/mimir-corrected/dfm-mimir-bf16.gguf --outtype bf16

logs/mimir-engine/build/bin/llama-quantize \
  logs/mimir-corrected/dfm-mimir-bf16.gguf \
  logs/mimir-corrected/dfm-mimir-q8_0.gguf Q8_0 8
logs/mimir-engine/build/bin/llama-quantize \
  logs/mimir-corrected/dfm-mimir-bf16.gguf \
  logs/mimir-corrected/dfm-mimir-q4_k_m.gguf Q4_K_M 8

python native/mimir/tests/text_reference.py \
  --model logs/prefixlm-comparison/mimir-hf \
  --output logs/mimir-corrected/text-reference.json
# Repeat with each of the three GGUF files:
python native/mimir/tests/text_parity.py \
  --client logs/mimir-multiplatform/bin/mimir-chat \
  --model logs/mimir-corrected/dfm-mimir-bf16.gguf \
  --reference logs/mimir-corrected/text-reference.json \
  --output logs/mimir-corrected/text-parity-bf16.json

python native/mimir/tests/training_gguf.py \
  --model logs/prefixlm-comparison/mimir-hf \
  --client logs/mimir-multiplatform/bin/mimir-chat \
  --gguf logs/mimir-corrected/dfm-mimir-bf16.gguf \
  --gguf logs/mimir-corrected/dfm-mimir-q8_0.gguf \
  --gguf logs/mimir-corrected/dfm-mimir-q4_k_m.gguf \
  --output logs/mimir-corrected/qualification.json
```

The exact Python executable used here was `logs/prefixlm-comparison/venv/bin/python`.
The export tool refuses to overwrite outputs; use `--verify-existing` for an
existing BF16 export. Preparation logs and the full per-case reports are retained
alongside the artifacts. The BF16 manifest includes source/input hashes; quantized
manifests identify the source BF16 hash, quantizer binary hash and command.

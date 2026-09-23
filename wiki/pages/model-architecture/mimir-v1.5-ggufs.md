---
type: Implementation Report
title: DFM Mimir v1.5 GGUF exports
description: Source revision, conversion, validation and publication of the official v1.5 GGUFs.
tags: [mimir, gguf, quantization, tokenizer, publication]
status: draft
last_updated: 2026-09-23
confidence: high
---
# DFM Mimir v1.5 GGUFs

User-authorized destination: `danish-foundation-models/DFM-Mimir-v1.5-GGUF`,
following the original `DFM-Mimir-GGUF` naming convention. The three variants
are BF16, Q8_0 and Q4_K_M. Existing model repositories and app bundles are unchanged.

Source: `danish-foundation-models/DFM-Mimir-v1.5`, pinned revision
`cc57cebadf375947ced5ccd3317d9da6bf8f9677`. Converter: llama.cpp
`4122b9a814d5bd4f48f454367419f75c05ee5215`. The export wrapper gained optional
`--model-name` so GGUFs carry `DFM Mimir v1.5`, not the temporary source-directory
name. All 259 tensors, 4096-token context and PrefixLM metadata are retained.
Both quantizations originate directly from BF16.

## Tokenizer and template

The raw tokenizer SHA-256 is
`12bac982b793c44b03d52a250a9f0d0b666813da566b910c24a6da0695fd11e6`,
identical to original Mimir. Both models use Gemma 4 tokenization/template format.
The only semantic template change is a new `tool_body is mapping` branch that
renders object-valued tool-response content; the other difference is a final
newline. The source template is embedded byte-for-byte. The converter loads
`tokenizer.json` directly, avoiding the HF configuration's regex rewrite, uses
`tokenizer.ggml.pre=gemma4` and preserves 256 byte-fallback token types.

## Validation

Each of the three files passes 724 tokenizer/decoder/template comparisons,
19 independent training-tokenizer audit cases, and CPU plus Metal generation
checks. With the embedded chat template, 1024-token context and 32-token reply
budget, every precision/backend answered the Danish capital question with
`Danmarks hovedstad hedder København.` and the arithmetic question with `4`.
Names, template bytes, tensor counts, context metadata and hashes were checked.
This is bounded artifact validation, not full benchmarks or additional platform
qualification. The new mapping branch itself is retained; app tool transcripts
currently use string content.

[Model card](../../../native/mimir/hf-gguf-v1.5/README.md) and
[validation record](../../../native/mimir/hf-gguf-v1.5/validation.json) are tracked.
Local artifacts and full per-case logs: `logs/mimir-v1.5/`; final GGUFs:
`logs/mimir-v1.5/exports/`. The earlier files directly under `logs/mimir-v1.5/`
have the generic display name `Source` and are superseded by the final exports.

## Reproduce

Using the established `logs/prefixlm-comparison/venv/bin/python` environment:

```sh
hf download danish-foundation-models/DFM-Mimir-v1.5 \
  --revision cc57cebadf375947ced5ccd3317d9da6bf8f9677 \
  --local-dir logs/mimir-v1.5/source
python native/mimir/export.py --model logs/mimir-v1.5/source \
  --model-name 'DFM Mimir v1.5' --outtype bf16 \
  --output logs/mimir-v1.5/exports/dfm-mimir-v1.5-bf16.gguf
logs/mimir-engine/build/bin/llama-quantize \
  logs/mimir-v1.5/exports/dfm-mimir-v1.5-bf16.gguf \
  logs/mimir-v1.5/exports/dfm-mimir-v1.5-q8_0.gguf Q8_0 8
logs/mimir-engine/build/bin/llama-quantize \
  logs/mimir-v1.5/exports/dfm-mimir-v1.5-bf16.gguf \
  logs/mimir-v1.5/exports/dfm-mimir-v1.5-q4_k_m.gguf Q4_K_M 8
python native/mimir/tests/text_reference.py --model logs/mimir-v1.5/source \
  --output logs/mimir-v1.5/text-reference.json
# Run text_parity.py for each precision, then training_gguf.py for all three;
# see native/mimir/CORRECTED-GGUFS.md for the established test arguments.
```

The HF upload contains only the three final GGUFs, model card, source license,
`SHA256SUMS`, `provenance.json` and `validation.json`. The provenance records source
file hashes, converter hashes and quantizer identity. Public size/SHA verification
is required after upload, before claiming publication complete.

Upload note: the default Xet transfer was slow on this host. Restarting with
`HF_XET_HIGH_PERFORMANCE=1` increased observed outgoing traffic from roughly
0.5–1 MB/s to several MB/s. This is Hugging Face's documented high-throughput
setting; observed bytes include protocol overhead and are not a percent-complete
measure because Xet deduplicates content.

## Public upload and 0.1.5 packaging

Publication completed at revision `78f92c5f126ae7ad05e98fc210d5c9c0eec3da16`.
Anonymous size/SHA checks and HTTP 206 GGUF-header downloads passed for all three
files; official Mimir+GGUF discovery finds the repository. See the
[publication record](../../../native/mimir/hf-gguf-v1.5/publication.json).

The user requested bundling v1.5 Q4_K_M, then explicitly chose **0.1.5** rather
than replacing 0.1.4. Prepare 0.1.5 build 7, preserving every 0.1.4 release asset,
body and tag. Curated catalog includes the three new files and retains originals;
the remote curated-catalog URL follows the maintained `main` branch.

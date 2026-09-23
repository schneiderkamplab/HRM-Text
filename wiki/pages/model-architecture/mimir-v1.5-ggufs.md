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

0.1.5 upgrade regression checks retain cached downloads/discovery while adding
new shipped catalog entries, and discard stale bundled-file inventory after an
app update. The bundled file is registered only after hashing its current bytes.
All 67 Flutter tests and analysis pass after these changes.

Build-tool caution: run Flutter tests and platform builds sequentially within
the same checkout. A concurrent test run regenerated Android's plugin registrant
with `integration_test` during a release build and caused a Java compile error.
Repeating the final platform builds sequentially passed.

The final 0.1.5 macOS and Android release builds and unsigned iOS archive pass;
iOS/Android report build 7. Native Metal tests with the new Q4_K_M passed tool
continuation, cache lifecycle, streaming, compaction, cancellation and shutdown.
Mounted DMG API smoke passes. Bundled model hashes and private-key scans pass.
The 0.1.4 GitHub release body, target and asset IDs/sizes/digests were compared
against a saved snapshot and remain unchanged.

All four 0.1.5 packages are verified. [CI 35864441924](https://github.com/schneiderkamplab/HRM-Text/actions/runs/35864441924)
passed 67 tests, analysis, native policy/compaction tests and CPU backend probes
on Linux/Windows. Package source is `3e36860ef4d918591c64e0d789f104df5047eba4`.
Artifacts: `logs/packages/release-0.1.5/`; test/audit evidence:
`logs/release-0.1.5-*`. Self-contained notes and checksums are in
[0.1.5.md](../../../native/app/releases/0.1.5.md). Publication awaits uploads.

## 0.1.5 publication complete

Superseding the pending-upload status above, [DFM Mimir 0.1.5](https://github.com/schneiderkamplab/HRM-Text/releases/tag/dfm-mimir-v0.1.5)
was published as Latest/non-prerelease on 2026-09-23 at 13:23:17 UTC. Tag
`dfm-mimir-v0.1.5` resolves to `b5fbe0d13c0c6a3046702430392bb557cd357c74`.
All four packages and four checksum sidecars match GitHub's sizes/SHA-256 hashes;
the published body matches the tracked release notes. The 0.1.4 tag still points
to `f5edf5184d96731168aea31c07d42d144da85f1d`, and its body and all asset
IDs/sizes/digests/timestamps are unchanged from the pre-work snapshot.
Publication evidence: `logs/release-0.1.5-publication.json` and
`logs/release-0.1.5-remote-verified.json`. iOS remains an unsigned local archive;
no TestFlight upload was made.

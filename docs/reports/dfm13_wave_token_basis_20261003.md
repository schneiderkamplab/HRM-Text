# Wave additions token accounting correction

2026-10-03. CPU-only verification against the frozen registry in
`data/dfm13/verified-wave-additions-20261003/registry.snapshot.json`.
No publisher, registry, live worker, source export, token array, or existing
assembly was modified. The parent will run the final assembler separately.

## Finding

The six failures were an assembler accounting assumption, not observed token
corruption. `dfm12.prepare.Renderer.count` sums all assistant training examples,
including repeated conversation prefixes. `dfm12.wave_release` retains that
preflight count but sets `target_message_index` to the final assistant. The wave
tokenizer consequently stores one final-target example per conversation.

| Source suffix | Rows | Preflight: all assistant targets | Training: final target | Sampled rows |
| --- | ---: | ---: | ---: | ---: |
| EuroBlocks bg | 245 | 169750 | 169631 | 6 |
| EuroBlocks hr | 48 | 43216 | 40646 | 8 |
| EuroBlocks hu | 3984 | 4077715 | 3707736 | 8 |
| Kapibara sq | 4124 | 12624254 | 6504507 | 7 |
| Baltic lv QA | 105971 | 284404437 | 95361003 | 7 |
| Baltic EuroBlocks | 166 | 142582 | 141935 | 7 |

All six pass full source/export/publication/tokenization-receipt agreement,
array integrity, contiguous starts/bounds/counts, vocabulary and context checks.
All source-row preflight counts sum exactly to the original preflight totals.
The JSON companion pins source/receipt/tokenizer/template/array hashes.

## Independent Native Token Check

43 deterministic rows, including 21 multi-assistant rows, were rerendered using
the pinned native template and tokenizer, thinking disabled, `max_seq_len=None`.
Both prompt and response token IDs matched their stored slices exactly; lengths
and start indices matched at the actual source ordinal and corresponding shard
ordinal. Earlier turns therefore survived in these sampled prompts. Every
sampled row's declared preflight count also matched the all-assistant rerender.

Selection: first, quarter, middle, three-quarter and last source ordinals,
plus the first three multi-assistant rows, deduplicated. This is bounded token
parity evidence, not full-corpus rerendering or semantic quality certification.

## Scoped Fix And Handoff

`scripts/assemble_dfm13_additions.py` now requires actual array token counts to
equal tokenization receipt and registry `tokenized_tokens`, not the preflight
budget. It retains publication/export preflight agreement, validates source-row
preflight sums when present, and rejects a preflight budget below stored tokens.
Every ready source records `token_metrics.training`, `token_metrics.preflight`,
their explicit counting bases, and `native_token_parity`. It performs the same
bounded untruncated parity check before admitting each source; mismatches fail
closed. Existing `tokens` totals continue to mean stored final-target prompt
plus response tokens, before repeat multiplication.

Tests: 38 passed in `tests/test_assemble_dfm13_additions.py`, including separate
counting bases, prompt/response mismatch rejection, overflow without truncation,
a real toy tokenizer preserving multi-turn history, and row-preflight sum checks.

Machine evidence: `docs/reports/dfm13_wave_token_basis_20261003.json` contains
individual ordinals, token counts, starts, row hashes, file hashes and six PASS
results. Existing production assembly remains unchanged. Non-wave adapters and
other unready additions remain outside this correction; no complete DFM13 claim
or final sampling is made.

Standalone CLI follow-up: direct `python scripts/assemble_dfm13_additions.py`
now explicitly adds the repository root to its import path before loading native
render helpers. A subprocess regression runs the actual CLI from outside the
repository with `PYTHONPATH` removed and verifies a real toy-tokenizer source
through native token parity. All 39 tests pass. No production assembly was
launched for this fix; the earlier JSON implementation hash identifies the
pre-CLI-fix verification code, not the updated script.

Suggested durable wiki note for parent: wave export `rendered_tokens` is the
all-assistant preflight budget with repeated prefixes; final-target training
exposure is `tokenized_tokens`. Verified additions report both separately and
require bounded untruncated native-token parity, in addition to full structural
and hash checks. Link this report rather than relabeling old receipts.

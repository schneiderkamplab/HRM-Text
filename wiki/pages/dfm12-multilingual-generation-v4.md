---
type: Runbook
title: DFM12 Non-Tool Generation Contract V4
description: Bounded escape-aware JSON and deterministic turn-pair assembly for a new multilingual calibration only.
tags: [dfm12, multilingual, generation, grammar, calibration]
status: draft
last_updated: 2026-09-27
confidence: high
---
# Non-Tool Generation V4

## Scope

The user authorized CPU preparation of a generation-contract repair and a new
calibration, not automatic admission or a new700launch. New module
`dfm12/multilingual_generation_v4.py` handles only explicit contract_version4
multiturn, OpenHermes, grounded instruction, summary/rewrite and math/code.
Poincare owns `multilingual_tasks.py` dispatch and the native tool contract.
No old frozen roots, global rendering code or shared generation dispatcher were
edited by this implementation. No GPU calls were made.

## Integration Contract

- `request(spec)` returns a payload with explicit compact EBNF under
  `structured_outputs.grammar`, thinking disabled, model26B-A4B and4096 maximum
  completion tokens. It measures the actual cached teacher Gemma template.
- `request(spec, endpoint_models=receipts)` permits a larger context only from
  actual `/models` documents supplied by the caller for every eligible endpoint.
  The exact model ID and integer max_model_len>=8192 are checked. The smallest
  advertised context wins, capped at16384; no receipts means8192. This helper
  cannot authenticate caller-supplied receipts or fetch live endpoints itself.
- Capture full raw HTTP response, finish reason, usage and request before
  calling `decode(spec, raw_content, finish_reason)`. This must happen BEFORE
  `captured_query`'s legacy `response_json`; once a permissive parser has
  discarded duplicate keys, an already-decoded dict cannot recover that evidence.
- Pass the decoded result to `assemble(spec, result)`. It validates again and
  runs the existing full student validator with actual4096-token Gemma4 training
  rendering. It also accepts raw JSON text, but transport finish_reason must be
  checked by decode/caller. Plain dict assembly is a convenience, not proof of
  strict raw decoding.
- `GenerationFailure` is a terminal per-attempt diagnostic with `code` and
  `retryable=False`. Do not feed invalid generation to a blanket transport retry.
  No repair, clipping, synthetic closing quote, or replacement source is applied.
- Existing primary and independent semantic audits remain required. Structural
  success does not approve factual accuracy or language quality. Output remains
  pilot_only, native-speaker review pending, admission_authorized=false.

The old compact_request sees no response_format and therefore leaves the explicit
grammar unchanged. Its returned CPU schema is None: the new decode/assemble
validators are mandatory, not optional replacements for later semantic audits.

## Bounded Conversation

Multiturn and OpenHermes return an exact-length `turns` array containing objects
with only `user` and `assistant` strings. CPU assembly creates role labels in
alternating order. All source turns are preserved for translation; invalid
source roles, excessive pair counts or sources that cannot fit are diagnosed,
never silently shortened. Up to6pairs are permitted. Generated fields are bounded
at900user,2400assistant and1200explanation characters, with7000total characters.
Prompt instructions prefer substantially shorter useful content.

CPU checks reject empty/whitespace/punctuation-only output, control characters,
embedded chat delimiters and conservative repetition-loop patterns. Short numeric
answers remain structurally eligible. Repetition rejection is a diagnostic hold,
not proof that all repeated structured content is semantically invalid.

Grounding text is inserted verbatim by the existing assembler. Math answers and
fixed code/test references are delegated to existing CPU assembly; generated
results cannot replace reference fields. The delegation uses an internal v3 copy
to avoid recursion through future v4 dispatch, then restores original v4 identity
and provenance. All assistant-target prefixes are rendered and checked untrimmed.
Source preflight reserves512student tokens, and final4096 checks remain mandatory.

## Grammar Evidence

The installed xgrammar JSON-schema lowering of bounded strings produces a rule
excluding backslashes; a CPU regression reproduces rejection of an escaped
newline under that old bounded-string rule. The old compact workaround strips
minLength/maxLength, sacrificing generation bounds. V4 instead supplies explicit
bounded JSON-string rules with quote, backslash, newline and Unicode escape
support. CPU schema/content checks are retained, not relaxed.

This finding is NOT an established cause of the previous malformed-stop outputs.
The live structured-output backend and token-to-returned-text path may still
violate expectations. CPU GrammarMatcher checks with the actual cached Gemma
teacher tokenizer accept escaped quotes, newlines and literal boxed syntax,
reject turn-stop106 before the whole JSON root closes, and permit it after.
No ignore_eos or artificial min_tokens workaround is installed.

The next isolated live calibration must capture raw malformed-stop versus length
or transport failures and test valid quoted/backslash/newline completions. Passing
CPU checks alone cannot claim live serialization is fixed or authorize700slots.

## Verification

67new tests plus15adjacent regression tests passed (82total), CPU only:

```bash
CUDA_VISIBLE_DEVICES='' /home/ucloud/miniforge3/envs/hrm/bin/python -m pytest -q tests/test_dfm12_multilingual_generation_v4.py tests/test_dfm12_multilingual_second_run.py tests/test_dfm12_multilingual_quarantine_pilot.py
```

Implementation SHA256:
`e3a3d845f11c96c64091166ae78be0282894962dc9c6dab70fd000e55461c165`.
Tests SHA256:
`530053cda966496f4bbf1ea106d69e7e6acf26a4dc57719b6b880a3515ccf7d2`.
Tests include strict duplicate/NaN/type/extra-field rejection, malformed JSON,
escape grammar, EOS, exact pair counts, source/teacher budgets, all7language codes,
all10fixed code-reference types, immutable input assembly and real student
assistant-prefix boundaries. No native-language correctness is inferred from
those structural language-code tests.

Related: [contract recalibration](dfm12-multilingual-contract-calibration.md),
[tool dialogue](dfm12-multilingual-tool-dialogue.md),
[earlier diagnostic evidence](dfm12-multilingual-calibration.md).

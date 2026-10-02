---
type: TechnicalReference
title: DFM12 Indexed Multilingual Review Contract
description: Opt-in bounded assistant evidence IDs, precise structural errors and independent semantic judgments for the next calibration.
tags: [dfm12, multilingual, calibration, evidence]
status: draft
last_updated: 2026-09-27
confidence: high
---
# DFM12 Indexed Multilingual Review Contract

## Authorization and Scope

The user authorized implementing review-contract remedies after the
[179-row non-infrastructure inspection](dfm12-multilingual-infrastructure-retry.md).
`dfm12/multilingual_review_indexed.py` is a new opt-in module, version
`preindexed-assistant-evidence-v1`. It does not modify legacy reviewers, frozen
outcomes, admission gates or calibration results. Parent/Epicurus owns subsequent
GPU calibration; this implementation worker performed CPU work only.

## API and Evidence

* `request(record)` returns the existing model request shape, thinking disabled,
  compact grammar and a 4096-token completion reserve.
* `keeps(review, record, deterministic=True)` raises `ContractError` on invalid
  structure; otherwise combines independent reviewer flags with unchanged routed
  deterministic checks. `deterministic=False` is diagnostic-only, not admission.
* `assess(review, record)` reports `structural_valid`, precise `structural_error`,
  `semantic_flags`, `reviewer_keep`, deterministic checks and combined `keep`.
  Structurally invalid reviews have null semantic flags/decision; reviewer flags
  are model judgments, never semantic gold labels.
* `deterministic_checks(record)` delegates to the existing routed implementation.
* `PromptBudget(tokenizer=None, context_limit=8192, server_context=8192).measure(payload)`
  uses actual raw-template tokenization. A 16384 context requires explicit
  verified server capacity of at least 16384; it is not inferred from free memory.

CPU-generated assistant-only evidence entries contain stable candidate-bound IDs,
canonical pointers and exact text chunks no longer than 200 characters. The
review copies an ID/text pair enforced together by the grammar and CPU validator;
it cannot generate offsets or mix an ID with rewritten text. All candidate and
source context remains visible. Natural-language-looking assistant content is
preferred for the main evidence when available; this is a selection heuristic,
not a language-quality classifier. Numeric/code-only candidates remain reviewable
with meaningful English literal explanations, without adding prose requirements
to the candidate. Each false dimension has exactly one issue slot and each true
dimension has null. Back-translations remain bounded at 600 characters and issue
explanations at 24..360, with separate length/type/meaningfulness error codes.

## CPU Verification

56 tests passed, no skips, including the new module plus legacy routed/tool tests.
Receipt: `data/dfm12/multilingual-review-indexed-tests-20260927-v2.xml`.
Tests cover all 242 controls' independent flags and unchanged deterministic
checks, six native tool subtypes, exact-ID/text grammar enforcement, length
boundaries, malformed reviews, symbolic fallback, and all 179 frozen outcome
hashes. Synthetic positive/negative contract fixtures are not semantic approval
of the historical candidates. The initial fixture incorrectly assumed every
audit-invalid candidate had usable evidence; it was corrected, not the gate.
`fo-grounded-instruct-23` has only punctuation and still fails closed with
`no_meaningful_assistant_evidence`.

The installed xgrammar behavior was directly reproduced with a CPU byte-token
matcher: unbounded strings accept plain text, escaped quotes, newlines and
backslashes; strings bounded by minLength/maxLength accept plain text but reject
the three escaped examples. The dedicated regression test records that behavior.
Consequently free-text lengths remain CPU-enforced, rather than using the broken
length-bounded grammar production. Exact evidence strings use constants.

Actual cached-tokenizer budget measurements:

| Input set | Measured result |
| --- | --- |
| All 242 controls | Maximum prompt 2691 + completion 4096; all fit 8K |
| Historical 81 audit-invalid | 80 reviewable; one punctuation-only rejection |
| Reviewable historical cases | Maximum prompt 8668 + completion 4096; all fit 16K |
| Historical cases exceeding 8K | 10; no truncation or review bypass |

Maximum historical case: `pl-openhermes-3`. The 16K measurements are CPU capacity
preflight, not evidence of completed GPU calibration. Endpoint model/context must
be verified by the calibration runner before requests.

Implementation SHA-256:
`678fcb6b0dffba2ddc575d26cac57273e72c289c8b1cad7c917b3b8730cde012`.
Test file SHA-256:
`9ac7e902077e33abb1818e534b2a5f059b2bb25d16e4092e26e0b8d590df5c35`.
Test receipt SHA-256:
`c1192a7800d914ce4e3341f2352f429b9810c48018fcec937e06de5b80c9b769`.

The previous failed semantic calibration is not superseded by these structural
tests. New calibration must report structural validity and semantic discrimination
separately; no artifact from the old run is repaired or automatically admitted.

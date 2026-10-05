# Epicurus: Baltic QA Gate Handoff

Owner explicitly authorized source-wide LTQA/LVQA holds on 2026-10-03. No
agent-messaging API is exposed in this thread; this file is the durable handoff,
not a claim of an acknowledged direct conversation.

## Active Contract

- Status: `quality_hold_source_fidelity` (same status as Fars/P3).
- Components: `baltic_lt_qa`, `baltic_lv_qa`.
- Registry names: `dfm13_wave3_baltic_lt_qa`, `dfm13_wave3_baltic_lv_qa`.
- Source-wide receipt schema: `dfm13-source-quality-hold-v1`.
- Receipt: `data/dfm13/baltic/publication-holds/qa-source-fidelity-20261003-v1/reason.json`.
- SHA256: `92a1796b8e48e57c888ce018c278ed8ccfc4e6252b1885944a0df01d7ffd28cb`.
- Registry fields: `status`, `training_eligible=false`, `admission_authorized=false`,
  plus `quality_hold.scope=entire_source_component` and `quality_hold.admission_authorized=false`.
- Both pointer conventions are present with identical values:
  `quality_hold.receipt` / `receipt_sha256` (Fars) and `path` / `sha256` (P3).
- Historical status is retained as `status_before_source_fidelity_hold`.
- Original published file hash, HF data revision, counts, licenses, repeats,
  tokenizer paths/receipts and token counts are unchanged.

## Fail-Closed APIs

`dfm12.wave_publication_holds.publication_hold(component)` and
`require_publication_allowed(component)` now cover both QA components in addition
to the existing Fars components. They use a code-level deny set: deleting a receipt
cannot grant permission. `entry_quality_hold(entry)` covers registry/assembly
names and existing quality-hold fields. New and already-prepared assembly checks,
tokenizer eligibility/direct tokenization and release entry points consult it.
The Baltic instruction controller skips held sources before processing or even
accepting an old uploaded publication as ready. No GPU process was stopped.

Please consume this hold in any separate global training gate. Do not clear it
merely because all rows have old `keep=true`, because upload/tokenization exists,
because a new model returns pass, or because receipt evidence is absent.
Explicit reviewed owner clearance and corresponding gate update are required.

## 31B Preparation

Same hold directory contains all-candidate bindings for **118,866** published
rows and **20** complete source-aware diagnostic requests, not a whole-corpus
review completion. Model: `google/gemma-4-31B-it`, temperature 0, max output 4096,
thinking disabled. No request submitted. Labels are separate from blind requests.
Each request contains the complete published history, upstream QA, record/source
pins and final target index. Underlying Wikipedia article is explicitly missing;
upstream generated QA is not certified gold. Unsupported material factual claims
must remain uncertain rather than being rewritten from model memory.

HF warning commits, if completed, are separate in `hub-warnings.json`; they must
not replace historical data `hf_revision` pins. Only README changes are permitted.

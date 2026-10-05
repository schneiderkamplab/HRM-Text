---
type: Runbook
title: Baltic QA Source-Wide Quality Holds
description: Fail-closed LTQA and LVQA holds, preserved publications, and source-aware 31B diagnostic packets.
status: stable
confidence: high
last_updated: 2026-10-03
---
# Baltic QA Source-Wide Quality Holds

Owner authorized source-wide holds after the independent 20-conversation review
found material errors outside P3. This supersedes the prior read-only/no-eligibility-
changes state documented in [Baltic sources](dfm13-baltic-language-sources.md).
The sample read 44 assistant turns, five accepted originals and five repairs per
language: LT 3/10 material defects; LV 6/10 material defects plus two uncertain
cases. Repairs were deliberately oversampled, so these are not population rates.

## Applied Hold

Registry status is `quality_hold_source_fidelity`, with
`training_eligible=false`, `admission_authorized=false`, and a receipt pointer:

| Component | Registry name | Published rows |
| --- | --- | ---: |
| baltic_lt_qa | dfm13_wave3_baltic_lt_qa | 12,895 |
| baltic_lv_qa | dfm13_wave3_baltic_lv_qa | 105,971 |

All **118,866 rows** are held, not merely the sampled bad cases. Original
published data, source provenance, counts, licenses, repeat policy, historical
HF revisions and tokenization artifacts remain unchanged. Registry updates use
the existing `.lock` and preserve unrelated entries.

Receipt directory:
`data/dfm13/baltic/publication-holds/qa-source-fidelity-20261003-v1`.
`reason.json` schema is `dfm13-source-quality-hold-v1`; SHA256:
`92a1796b8e48e57c888ce018c278ed8ccfc4e6252b1885944a0df01d7ffd28cb`.
It pins the full published inputs and independent assessment. Registry
`quality_hold` includes both Fars-style `receipt`/`receipt_sha256` and P3-style
`path`/`sha256`, identically valued; scope is `entire_source_component`.

`dfm12.wave_publication_holds` extends its code-level deny set with the two QA
components. `publication_hold` and `require_publication_allowed` block release
before any output write. `entry_quality_hold` rejects named sources even from
stale accepted registry snapshots. The Baltic instruction controller skips them;
tokenizer eligibility/direct entry and both new/preexisting assembly validation
reject them. Missing or malformed evidence cannot clear a code-level hold.
Only explicit reviewed owner clearance plus a corresponding gate update can
change this state; a model keep result does not automatically admit anything.

No GPU process or unrelated pipeline was stopped/restarted. There was no live
Baltic instruction publisher at application time; the existing tokenizer watcher
was left running and sees the registry hold on its next scan.

## Warning-Only Hub Updates

Only remote README was updated. Original local exports were not rewritten.
Both commits verified unchanged identity/size/LFS metadata for all three non-card
files and byte-identical downloaded warning text. Original data revision remains
the registry's `hf_revision`; warning revisions are separate evidence:

| Source | Warning commit |
| --- | --- |
| schneiderkamplab/dfm13-wave3-baltic_lt_qa | 0667ce2dc7a705f8dbd25a572f43fa2dedeccae3 |
| schneiderkamplab/dfm13-wave3-baltic_lv_qa | 350ce4734e48d65b0a3e95bfacfa61527b7c86de |

Details: `hub-warnings.json` in the hold directory. Cards clearly warn that Hub
availability and old machine keep labels do not imply training approval.

## Unsubmitted 31B Packets

`dfm12.baltic_qa_quality_hold` prepared `all-candidate-bindings.jsonl` for every
118,866 published row, plus **20 full diagnostic requests** in
`calibration-requests.jsonl`. Expectations are separate and not included in the
blind model requests. Model: `google/gemma-4-31B-it`, temperature 0, thinking
disabled, maximum output 4,096 tokens. Requests submitted: **zero**.

Packets include full final multi-turn messages, exact source/published hashes,
upstream QA, final supervised index and an explicit missing-primary-article field.
The available LT upstream contains questions/answers and LV upstream contains
generated conversations, not the underlying Wikipedia articles. Agreement with
upstream is not proof of factual correctness. A 31B model must distinguish
introduced from inherited defects, inspect all history and native language,
and hold unsupported material claims rather than rewrite from memory. These
packets are calibration preparation, not completed whole-corpus review or
automatically admissible correction proposals.

Bounded source-recovery follow-up (2026-10-03): original HF file inventories at
the pinned/current revisions contain no auxiliary article map or primary articles.
LT has question/answer fields only and no stated source date; LV has messages only,
but its card identifies the 2024-10-20 Wikipedia dump and title-bearing first
questions. Existing local LT/LV article inventories retain text, IDs and URLs from
2023-11-01. Three initial LV topics have local title candidates, not certified
generation-source matches. Exact source recovery remains unresolved; old QA is
not gold and holds are unchanged. Evidence, bounded lookup and cost distinctions:
`docs/reports/baltic_qa_article_recovery_20261003.md`.

CPU lookup follow-up completed: `dfm12.baltic_article_lookup` indexes all 200,471
existing LT/LV articles (about 949 MB SQLite index). The diagnostic20 output under
`data/dfm13/baltic/article-lookup-diagnostic20-20261003/pilot-v2/` preserves full
article evidence and hash-bound manual assessments: 5 source-support, 6 concrete
article contradictions, 4 partial-context, 2 source/date-uncertain and 3 without
relevant retrieved evidence. These are sample evidence categories, not admission
counts or population rates. In particular, Chinvali's source assigns delayed
reinforcements to Russian forces, while QA reverses this to Georgian forces.
All exact generation-source matches remain uncertified; older article snapshots
and inherited source errors are explicit. Successor adapter proposal and commands:
`docs/reports/baltic_qa_article_lookup_pilot_20261003.md`. No sealed consumer,
source hold, GPU workload or original corpus changed.

The full-inventory CPU successor is `dfm12.baltic_article_adapter`, with separate
hash-verifying hydration in `dfm12.baltic_article_adapter_verify`. Its generic
question/title/entity matching does not use the diagnostic query bank or prior
review verdicts. The development random50 (25 per language, excluding the prior
20) found 27 relevant-topic, 1 partial-context, 2 ambiguous, 2 irrelevant-only
and 18 empty retrievals. These are topic-usefulness observations, not factual
gold or admission counts; the same50 informed matcher tightening.
Full sidecar destination: `data/dfm13/baltic/article-adapter-full-20261003-v2`.
Completed and fully verified: 118866 packets (LT12895/LV105971), 81213 with
candidates and 37653 empty; 129022 references to 71446 unique full articles.
The manifest and `verification.json` bind SQLite SHA256
`ee4059a4690f044d4e18910c06f1520ede19f19e13198861c442e7a054d453a9`.
Every stored article was compared with the index and all QA messages/source
bindings verified. Eight CPU tests pass; no model calls or admission occurred.
Packets preserve zero to three full articles with snapshot/text/corpus hashes,
all `primary_source_identity=false`; homonym/date uncertainty and source holds
remain. No context truncation is performed; successor reviewer rendering still
needs full-context preflight. API, exact sample hash, limitations and Epicurus
handoff: `docs/reports/baltic_qa_article_adapter_handoff_20261003.md`.

```bash
python -m dfm12.baltic_qa_quality_hold --prepare --apply --output data/dfm13/baltic/publication-holds/qa-source-fidelity-20261003-v1
python -m dfm12.baltic_qa_quality_hold --warn-hub --output data/dfm13/baltic/publication-holds/qa-source-fidelity-20261003-v1
```

Already executed: do not rebuild over the existing receipt or repeat the card
warning. `--apply` is idempotent; preparation requires a fresh directory.

## Coordination and Verification

Epicurus handoff:
`docs/reports/baltic-qa-independent20-20261003/epicurus-gate-handoff.md`.
This records the shared gate API and compatible receipt fields for the separate
global training gate. No agent-message API was exposed in this worker, so this
is a durable handoff, not a claimed direct acknowledgment.

Tests cover stale accepted snapshots, missing receipt fail-closed behavior,
preserved registry pins/idempotency, preexisting assembly rejection, controller
skip, unrelated summary eligibility and README-only updates. Packet verification
rechecks all prepared attachment hashes, counts and blind-label separation.
No training launch, correction admission, or GPU review was performed.
Final combined CPU regression suite: **87 passed** (QA/Fars gates, release,
tokenizer, assembler, LT summary and P3 publisher tests).

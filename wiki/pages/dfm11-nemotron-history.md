---
type: Historical Record
title: DFM11 Nemotron Assessment History
description: Superseded upstream FineInstructions Nemotron proposal retained after reconciling local and origin documentation.
status: deprecated
last_updated: 2026-09-08
confidence: high
---
### Archived upstream Nemotron assessment

The following imported assessment is superseded by the DFM-native replacement
above. It is preserved as historical evidence; its commands refer to the
removed materializer and must not be used as current instructions.

#### FineInstructions Nemotron - excluded

**Decision, 2026-09-04:** DFM11 excludes
`fineinstructions/fineinstructions_nemotron`. Its Common-Crawl-derived
provenance, copyright, PII, and deliberate source-copy risks require more
review than its expected marginal value justifies for Mimir. It has a zero
token budget, is absent from the downloader manifest, and the retained
materializer refuses to run. The discussion below is the superseded candidate
assessment.

The source was considered as a fail-closed English instruction-pretraining
candidate. It is not ordinary post-training
SFT: the release contains more than one billion synthetic instruction/answer
pairs (approximately 300B tokens), generated from Nemotron-CC source documents.
The FineInstructions experiments used this representation for pretraining from
scratch and formatted each pair as an instruction and answer.

#### Superseded cap and quality proposal

- cap the admitted source at **3.0B Gemma-rendered tokens per DFM11 epoch**;
- use `repeat: 1` and do not compensate for filtering by repetition;
- retain only upstream judge score 5, with no lower-score fallback to fill the
  cap; unused budget is preferable to weaker synthetic supervision;
- deterministically sample paired data/judge shards across the release;
- materialize approximately 3.45B upstream `synthetic_token_count` tokens, then
  enforce the exact 3.0B cap after Gemma-template tokenization;
- run exact/near deduplication, protected-eval decontamination, context-length
  validation, PII review, and source-copy review before admission.

The 3B cap is deliberately about 3% of a roughly 100B-token DFM epoch: large
enough to test the paper's instruction-pretraining effect without allowing one
English Common-Crawl-derived family to dominate Danish, math/code, native chat,
or agentic supervision. At the card's aggregate average of approximately 244
tokens per row, 3B tokens corresponds to roughly 12.3M rows before downstream
filtering. Revisit the cap only after source-stratified quality and capability
ablations; 5B tokens is the provisional hard ceiling for DFM11.

A local 12-shard sample covering 7,972,982 judge labels found 15.15% score 5,
43.09% score 4, 28.46% score 3, 10.61% score 2, and 2.46% score 1. This is why
the initial gate is score 5. The upstream score remains only a quality signal,
not a privacy, licensing, correctness, or decontamination decision.

#### Exclusion rationale: license, provenance, and PII

Admission is permanently closed for DFM11. The Hugging Face card declares no dataset license.
FineInstructions says the rows derive from Nemotron-CC, which derives from
Common Crawl. Nemotron-CC is distributed under the Common Crawl Terms of Use;
those terms warn that crawled content may remain subject to source-owner terms
and place copyright, privacy, and lawful-use assessment on the user.

This transformation does not remove the underlying concern. FineInstructions
requires generated answers to contain at least 80% excerpts from source
documents, and its paper describes query moderation and benchmark
decontamination but no PII-removal stage. Therefore:

1. do not represent this source as permissively licensed;
2. obtain an explicit project-level copyright/provenance decision;
3. reject obvious emails, phone-like identifiers, IP addresses, credentials,
   addresses, and other personal identifiers, followed by a stratified semantic
   PII audit because regexes cannot reliably identify names or contextual PII;
4. measure long verbatim source spans and domain/source concentration;
5. fail closed if the source-copy and PII audits cannot establish an acceptable
   policy for the intended academic use.

An admitted materialization requires a receipt at
`data/receipts/dfm11_fineinstructions_nemotron_admission.yaml` affirming the
license decision, PII audit, source-copy audit, benchmark decontamination, and
task-quality audit. Review-only pilots remain segregated under `data/review/`:

```bash
python scripts/prepare_dfm11_fineinstructions_nemotron.py inventory
python scripts/prepare_dfm11_fineinstructions_nemotron.py materialize \
  --review-only --max-rows 100000
```

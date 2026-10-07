---
type: Runbook
title: DFM14 BAAI Access and Preparation
description: Verified access, release selection and admission boundaries for BAAI sources.
status: draft
confidence: high
last_updated: 2026-10-07
tags: [dfm14, datasets, preparation]
---
# BAAI Source Access

Superseded on 2026-10-07: earlier access-blocked observations for
Infinity-Instruct and IndustryInstruction no longer apply. Authenticated payload
range requests also succeeded (HTTP 206, Parquet signature) for COIG-PC and
IndustryCorpus2 after the user obtained access. No credentials are recorded here.

| Repository | Verified revision | Scope |
| --- | --- | --- |
| BAAI/COIG-PC | 4ca2778d69d7a9c17a0a6c1668c6e989b102176b | Train-only instruction candidates; full/train/TopN variants overlap. |
| BAAI/IndustryCorpus2 | 249ea52f1ee412303e9741ae69fdd2109c0f8e1c | Raw domain corpus, not instruction data; provenance review required before grounding admission. |

IndustryCorpus2 contains about 1.84 TB of listed Parquet payloads, including
Chinese/English and high/middle/low partitions. The high label is not proof that
a document satisfies the project's no-broad-web grounding policy. Access does
not authorize indiscriminate download or inclusion. COIG-PC access likewise does
not remove its source-specific terms or benchmark-decontamination requirements.

User decision, 2026-10-07: only a small amount of high-quality grounding text is
needed. IndustryCorpus2 is deny-by-default: admit only documents with traceable
permissive licensing/public-domain evidence. Repository Apache metadata and a
high-quality partition do not substitute for document-level evidence. Unknown
rights and broad web material remain excluded; no volume target warrants relaxing
this rule. This is a grounding candidate, not new raw-continuation authorization.

COIG-PC has overlapping full/train/TopN exports and heterogeneous task provenance.
Prefer a bounded, task-balanced train selection rather than the whole corpus;
review original-source rights and benchmark overlap. Its core release also has
unknown license metadata and is not automatically approved by access to COIG-PC.

## Completed Initial Expansion

`python -m dfm14.baai_expansion` prepared 102 files and 998,737 Chinese
instruction candidates without processing errors in
`data/dfm14/baai-expansion-v1`. This is a bounded candidate pass (100,000 rows
per file), not an accepted training-row count. It selects Infinity 7M (75 files)
and Gen (15), excluding overlapping alternative release layouts, plus all
twelve IndustryInstruction training files. Cross-source deduplication and audit
remain required. IndustryInstruction uses `lang`; explicitly named
`*_valid_train.jsonl` files are training, not validation. Separate sector repos
must not be ingested again as additional independent sources.

See [CPU audit handoff](/pages/dfm14-curated-cpu-audit.md) for admission gates.

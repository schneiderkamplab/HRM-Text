---
type: Reference
title: Ranked Individual Decision Dataset Candidates
description: Per-dataset expansion of the top seven decision clusters with scored conversion priorities and pre-tokenization paths.
tags: [decision-datasets, ranking, provenance]
status: draft
last_updated: 2026-10-22
confidence: medium
---
# Individual Dataset Ranking

The complete ranked table and full pre-tokenization path appendix are in
[docs/decision-datasets-ranked.md](../../../docs/decision-datasets-ranked.md).
This large generated inventory stays outside the bounded OKF concept pages.

It expands the seven leading clusters of the October 21 census into 911
dataset/subdataset or storage-variant entries. Shards and shot modes are
combined; heterogeneous Natural Instructions tasks and FLAN prompt variants
remain separate. The two math-answer-conditioning entries are explicitly
storage variants, not new independent datasets. Counts reconcile exactly to
the seven parent clusters. Inherited DFM sources are counted through the
current snapshot, not summed across versions.

Relevance R averages separate 1-5 Typed Decisions and Decision Index scores.
Ease E is 0-5, with zero for held-out/HOLD identifiers and no score of five
without verified turnkey conversion. The aggregate is `20 * sqrt(R * E)`.
Equal weights prevent a large easy corpus from outranking relevant data solely
because of its size. Scores are transparent identifier/documentation-based
priors, not results from a new semantic audit or benchmark experiment.

All filesystem paths in the report refer to pre-tokenization text files or
directories. Producer-machine paths are labelled; existing upstream and
converted representations are distinguished from final native repairs.
Where repair/conditioning occurred during tokenization, the report lists
parent text and explicitly notes that no separate pre-tokenization final
representation is established. Do not mistake a path listing for proof of
exact row equality with the measured token snapshot.

Reproduce with `python scripts/rank_decision_datasets.py`. The JSON companion
retains exact source keys, range IDs, path roles, count totals and scoring
components. Test with `python -m pytest tests/test_rank_decision_datasets.py`.

See [benchmark priorities](benchmark-priorities.md) and
[volume semantics](volume-method.md) before using the ranking for selection.

## Tasksource JEV Overlap Check

The report now marks source/task-family overlap against
`tasksource/tasksource-jev-typed-decisions/sources.yaml`, pinned to revision
`8b1afcc6ad12554b347134a91b5f0dc6ae2361db`. The downloaded snapshot is
`docs/reports/tasksource-jev-sources-20261022.yaml` (480 repository IDs and
754 source/task configurations); its SHA-256 is recorded in the report.

`scripts/decision_source_overlap.py` checks recorded HF IDs against direct and
upstream repository provenance, then bounded task-name aliases including
GLUE/SuperGLUE config names and punctuation variants. It distinguishes exact
repository matches, inferred task/family matches, possible synthetic/repaired
derivatives and no identified match. The full matched manifest keys are shown
next to each dataset's pre-tokenization paths. Regeneration preserves these
annotations; ranking scores are not changed by overlap.

This is not row-level duplicate detection, split identity or evidence of test
contamination. No-match is not disjointness. The Tasksource training collection
is distinct from the LocalLLaMA Typed Decisions benchmark. Unknown lineage
inside broad mixtures may require a future payload/provenance check.

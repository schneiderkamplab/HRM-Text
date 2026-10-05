# Full-article Baltic QA consumer successors

Implementation: `dfm12.baltic_qa31_article_consumer`, isolated from frozen
production and earlier sealed consumers. Preparation uses16 CPU workers with
single-threaded native tokenizer instances; no model/server calls.

## Evidence and Coverage

Input: `data/dfm13/baltic/article-adapter-full-20261003-v2`, verified manifest
SHA256 `da911f7c53593d89adfb9fea0607da5028c24037d23e577c7ddb899308afdbc3`.
All118866 rows (12895 LT,105971 LV) are retained. The evidence inventory contains
37653 no-hit,51314 one-article,11989 two-article and17910 three-article packets.
Every selected article is fully hydrated, hash-checked and rendered. No-hit
is unresolved retrieval, not automatic rejection. Selected references remain
topic candidates, not gold or certified original generation sources.

Sealed and verified successor roots:

- `data/dfm13/baltic/qa31-article-full-consumer-v3`
- `data/dfm13/baltic/qa31-article-diagnostic20-consumer-v3`

All118866 complete messages were preflighted;118369 fit and497 remain
`needs_review_context`. Zero truncations, render errors or GPU requests.

| Selected full articles | Rows | Context fit | Unresolved overflow |
| --- | ---: | ---: | ---: |
| 0 | 37653 | 37653 | 0 |
| 1 | 51314 | 51305 | 9 |
| 2 | 11989 | 11931 | 58 |
| 3 | 17910 | 17480 | 430 |

LT:12895 retained,12862 fit,33 overflow. LV:105971 retained,105507 fit,464
overflow. Largest total65563 tokens (prompt57371+8192 reserve). No-hit largest
total15824. Diagnostic20:all20 fit,maximum19341 total;5 no-hit,7 one-article,
4 two-article,4 three-article. These are automated retrieval results, not the
earlier hand-authored pilot's19/20 hit count and not factual support counts.

Manifest SHA256, full:
`deedec35930f618a4fa3975ada5c9ddfa45c21d74a0c7bfa025c4e6e38c70a28`.
Diagnostic:
`98778858e187b8f74b81d8e364750ce3cf18e29d33ce4c54a1bfedec2cd25a18`.
Both `verify` commands passed after sealing. The old capacity-v2 and v1 roots
are preserved unchanged and superseded as QA launch entry points, not repinned.

The full catalog retains all prior candidate/binding evidence and original QA.
Reviewer inputs omit old audit votes/labels. The existing20 diagnostic identities
are exposed controls, not fresh gold; the separate retrieval50 was used to revise
retrieval and likewise must not be described as untouched validation.

## Context and Gates

Every complete native31B request is measured with the verified downloaded
tokenizer, thinking enabled and `fix_mistral_regex=False`. Context is32768,
including8192 output reserve. No truncation. `catalog.sqlite` contains both the
complete `catalog` and one `budgets` result per row, including request/token-ID
hashes, article count and exact token totals. Overflows remain explicit
`needs_review_context` jobs, never factual rejections or pending dispatch.
Repair and fresh re-audit requests are measured again at runtime.

The independent fresh-context review uses the full corrected conversation,
original QA and all selected complete articles, without earlier review reasons.
Uncertain dates, homonyms, article contradictions and unsafe source advice cannot
be treated as grounded corrections. Only the final supervised target may change.
No admission, publication or training authorization is granted.

Bulk launch requires new article-aware diagnostic approval bound to the exact
policy, evidence and code, not the earlier no-article approval. Any over-budget
diagnostic remains unresolved and prevents an all20 completed calibration claim.
Measured capacity uses the existing reservation/aggregate validator: unprofiled
ceiling8/server, diagnostics always<=8; higher bulk requires measured allocation.
No extra capacity is added atop other clients. Live exact model/snapshot/context
health gates still run before dispatch. Launch templates default false.

## Commands

```bash
PY=/home/ucloud/miniforge3/envs/hrm/bin/python
$PY -m dfm12.baltic_qa31_article_consumer prepare \
  --root data/dfm13/baltic/qa31-article-full-consumer-v3 --workers 16
$PY -m dfm12.baltic_qa31_article_consumer diagnostic \
  --root data/dfm13/baltic/qa31-article-diagnostic20-consumer-v3 \
  --full data/dfm13/baltic/qa31-article-full-consumer-v3
$PY -m dfm12.baltic_qa31_article_consumer verify --root ROOT
# Only after explicit31B handoff and semantic/capacity authorization:
$PY -m dfm12.baltic_qa31_article_consumer run --root ROOT \
  --authorization APPROVAL --concurrency N --capacity-profile MEASURED_PROFILE
```

Omit capacity-profile for an authorized unprofiled run capped at8. Use
`calibration-report --root DIAGNOSTIC_ROOT` after actual completion; technical
retries are explicit `retry-technical`, unknown completions require
`--allow-unknown`, with the inherited three-attempt budget. No automatic retry
or semantic rejection is manufactured for context overflow.

Preparation resumes only under identical pins and preserves completed catalog
and budget rows. A sealed root refuses preparation; choose another successor.
Final matrix entries were changed only after full completion and pin checks.

Focused CPU tests:46 passed (article consumer/adapter, Baltic consumer, capacity
consumer and measured-profile validator). These are contract tests, not semantic
certification. Preparation PID2488379 exited successfully. No runtime ledger or
GPU run was started. Semantic calibration, explicit31B handoff after source
audits drain, and any measured-capacity approval remain pending. The497 context
overflows require a separately authorized evidence-coverage solution; they are
not trained, admitted, relabeled false, or silently removed.

---
type: Research
title: Baltic QA31 Article Twenty Review
description: Independent source and repair review of the twenty-case article-aware Baltic QA diagnostic.
status: draft
confidence: high
last_updated: 2026-10-03
tags: [dfm13, baltic, qa, quality]
---
# Baltic QA31 Article Twenty Review

CPU review of `qa31-article-diagnostic20-consumer-v3` found6 article-supported
provisional keeps and6 challenged keeps among its9 unchanged/3 repaired keeps.
The7 rejected/needs-verification cases should stay withheld; some judge rationales
incorrectly turn missing/irrelevant evidence into proof of falsehood. One invalid
review proposed repair with uncertain support; the validator correctly failed
closed. This is not a transport/GPU failure and must not be blindly reset.

Of3 repairs, Žiemgala is article-grounded; algology and Trakai have no articles.
Algology retains problematic protected history while the repair model explicitly
acknowledges it. Jankto and Tuči unchanged keeps also lack articles. Humašaha and
CO show final-answer focus missing earlier-history issues. All3 repairs preserve
protected messages/tools structurally; structural validity is not semantic safety.

The [20-case report](../../docs/reports/baltic-qa31-article20-review-20261003/report.md)
and its read-only SQLite snapshot receipt bind evidence and provide the existing
CPU operational reporting command. Sources are retrieved candidate references,
not certified original generation articles or factual gold. No publication,
bulk approval, inference, retries or changes to original data occurred.

See [QA31 consumer](dfm13-baltic-qa31-consumer.md) for operational contracts.

## Bounded Quoted-Evidence Successor (2026-10-03)

The original diagnostic's permissive evidence policy is superseded **only for
this isolated successor**, not silently changed in historical artifacts.
`dfm12/baltic_qa31_grounded_pilot.py` and its dedicated tests implement CPU
preparation and validators. Model choice is explicit: **26B-A4B defaults for
bulk; 31B is diagnostic-only**, not a presumed quality upgrade. This particular
20-case pilot is diagnostic-only regardless of model, with no GPU runner or
admission/publication authorization.

Prepared root: `data/dfm13/baltic/qa-article-quoted-diagnostic20-26b-v1`.
All20 original packets/prior reviews retained;15 requests fit32768 tokens
including8192 output reservation;5 no-article packets are verification holds
and have no request. Original source catalog remains hash-bound and unchanged.
No article is truncated. Selected26B local tokenizer revision:
`4d7ae4984b7db7de8f8457170b3f1a419ee76d52`.

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.baltic_qa31_grounded_pilot prepare \
  --root data/dfm13/baltic/qa-article-quoted-diagnostic20-26b-v1 \
  --snapshot /home/ucloud/.cache/huggingface/hub/models--google--gemma-4-26B-A4B-it/snapshots/4d7ae4984b7db7de8f8457170b3f1a419ee76d52
/home/ucloud/miniforge3/envs/hrm/bin/python -m pytest -q \
  tests/test_baltic_qa31_grounded_pilot.py tests/test_baltic_qa31_article_consumer.py
```

Preparation refuses an existing root.35 tests passed. Explicit
`--model google/gemma-4-31B-it` selects diagnostic31B with its matching local
snapshot; no downloads or calls occur. Requests exclude upstream QA/reviews as
supporting evidence. Citation quotes must match the actual article text and
article hash, never merely question/answer text. Nonoverlapping exact claim
spans must cover every assistant turn, including protected history. Candidate
or article changes invalidate the evidence binding. A repair changes final
content only and must submit fresh evidence for the complete corrected history;
CPU computes the corrected candidate binding.

Missing evidence means verification hold, not invention or proof of falsehood.
Unsupported protected history cannot be repaired by changing only the target.
Entity/date/safety checks must pass. Quote matching and text coverage do **not**
prove semantic entailment: even structurally valid positives remain
`needs_semantic_review`, never automatically accepted. No sources were deleted,
no live consumers changed, and no GPU work launched.

### Six Existing Context-Supported Salvage Candidates

These are source-relative findings from the pinned20-case review, not six new
successful pilot generations. Full IDs resolve in the report linked above.

| Case ID prefix | Candidate | Evidence available |
| --- | --- | --- |
| `00015f48af9d` | Klaipeda climate | Municipality article states35.2C July2011 and-38.3C early February1962; unchanged answer preserves both. |
| `3fbe108b9dfd` | Vincas Sinkevicius | Matching biography states1924-09-18 and Kalvarija/Marijampole; unchanged answer. |
| `46917e3945b6` | Romuva festivals | Festival section supports equinoxes/solstices and every listed example; nonexhaustive wording is appropriate. |
| `c17a6d142324` | Auslas lake | Matching lake article supports dimensions, elevation, depth, strait, islands and watercourse facts; unchanged answer. |
| `fff21bda8014` | Ploksciai church | Matching church article identifies the1670 founder; other church hits are not substituted. |
| `f06cf547c2c9` | Ziemgala | Existing repaired answer is grounded in the matching historical-region article, unlike the original narrow geography. |

The successor starts from the original20 candidates, not silently injected
repairs. Ziemgala's already inspected repair remains in preserved prior
evidence; generating or reusing a corrected target requires the new evidence
contract. No broad source release follows from these six cases.

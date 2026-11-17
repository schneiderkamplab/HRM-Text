---
language:
- nl
license: other
license_name: source-specific-cc0-and-cc-by-4.0
license_link: LICENSE.md
pretty_name: DaLA Dutch — DynaWord
task_categories:
- text-classification
- text-generation
tags:
- grammar
- spelling
- grammatical-error-correction
- acceptability
- synthetic-errors
size_categories:
- 1M<n<10M
configs:
- config_name: acceptability
  data_files:
  - split: train
    path: data/acceptability/train-*.jsonl.gz
  - split: validation
    path: data/acceptability/validation-*.jsonl.gz
  - split: test
    path: data/acceptability/test-*.jsonl.gz
- config_name: correction
  data_files:
  - split: train
    path: data/correction/train-*.jsonl.gz
  - split: validation
    path: data/correction/validation-*.jsonl.gz
  - split: test
    path: data/correction/test-*.jsonl.gz
---
# DaLA Dutch — DynaWord

Dutch grammatical acceptability and error correction with synthetic spelling and
grammar errors. **Provisional, checker-screened training data; not a human-validated
gold benchmark.** No simplification, paraphrasing or style-transfer task.

## Configurations

**478,916 original/corrupted pairs**, **957,832 chat rows
per configuration**. Every pair contributes a clean control and a corrupted input.
The two configurations share sentences and document splits and are not independent data.

| Split | Pairs | Rows per configuration |
| --- | ---: | ---: |
| train | 383,131 | 766,262 |
| validation | 47,892 | 95,784 |
| test | 47,893 | 95,786 |

- `acceptability`: answer `yes` for original controls and `no` for corrupted inputs.
- `correction`: return the source sentence, including identity correction for clean controls.

```python
from datasets import load_dataset
acceptability = load_dataset('schneiderkamplab/dala-dutch-dynaword', 'acceptability')
correction = load_dataset('schneiderkamplab/dala-dutch-dynaword', 'correction')
```

Each row has `messages` and `metadata`. Use **only messages as model input**:
metadata contains labels, edit families and audit judgments. Metadata also identifies
the canonical pair, document, split, source and source license. Join pair IDs to
`provenance/*.pairs.jsonl.gz` for exact source/edit spans and checker diagnostics.

## Sources and construction

Selected Dutch DynaWord sources, pinned to revision
`d0158defd949699532e59dea5978c5542afb0400` of
[danish-foundation-models/dutch-dynaword](https://huggingface.co/datasets/danish-foundation-models/dutch-dynaword/tree/d0158defd949699532e59dea5978c5542afb0400).

| Source | Pairs | Source-card license |
| --- | ---: | --- |
| de_rechtspraak | 240,251 | CC0 1.0 |
| eurlex | 107,033 | CC BY 4.0 |
| officiele_bekendmakingen | 50,498 | CC0 1.0 |
| dienst_publiek_en_communicatie | 81,134 | CC0 1.0 |

The government subset uses excellent annotations and excludes conversational material.
EUR-Lex selects modern dated documents. The extension uses excellent Rechtspraak
judgments and official announcements with explicit modern publication-year headers.
Annotations are screening signals, not proof of grammatical correctness. Original
article URLs and authors are unavailable: provenance preserves dataset-file URLs,
upstream record IDs, hashes, source revisions and exact offsets; no original URL or
author is invented. Anonymization/substituted names and legal extraction artifacts
can remain. Some judgments describe crime or violence.

One injected edit per pair. Guarded morphology rules, curated spelling mappings and
character-level spelling operators generate candidates. Local LanguageTool screening
requires no relevant source diagnostics and a diagnostic at the injected edit;
spelling additionally uses the pinned OpenTaal wordlist. No family-percentage caps.
Documents receive seeded splits; global exact and heuristic near-duplicate filters
reduce overlap without proving absence of semantic leakage. Parent build manifests,
source configurations, exclusions and the active profile are included under metadata.

## Quality audit and release exclusions

Before release, a fresh uniform **200-pair sample** was drawn from 478,080 previously
unreviewed pairs in the frozen 478,930-pair parent (850 earlier-reviewed originals
excluded). Agent inspection found **187 acceptable originals, 10 erroneous and
3 uncertain**: **93.5% strict source acceptance**. All **200 injected edits** were
judged valid. A separate family-coverage supplement had **24 acceptable originals
and one uncertain**, with all 25 injected edits valid. Do not pool the purposive
supplement into the uniform estimate. These are agent judgments, not independent
native-speaker annotation, and do not establish perfect corruption precision.

The release removes **14 flagged original/corrupted pairs** (13 uniform-sample flags
and one supplementary flag), preserving all remaining records unchanged. The
pre-removal audit is retained in `metadata/quality-sample.json` and related files.
**Removal does not establish a new independently measured precision rate.** Other
source-label errors almost certainly remain: original controls and correction
targets are source excerpts, not guaranteed error-free sentences. Observed defects
include duplicated words, merged headings, broken compounds and name substitutions.

Earlier pilot audits informed source filters, exclusions and the 10:1 document
priority for Rechtspraak versus official announcements in the extension. Earlier
results must not be presented as independent precision measurements for this release.

## Coverage and limitations

| Family | Pairs |
| --- | ---: |
| spelling | 241,698 |
| article_gender | 205,228 |
| adjective_inflection | 13,565 |
| article_number | 9,300 |
| demonstrative_agreement | 5,479 |
| subject_verb_agreement | 2,420 |
| possessive_agreement | 1,137 |
| relative_pronoun_agreement | 45 |
| verb_dt | 44 |

The release realizes 64 rules and 31,616
distinct case-folded surface substitutions. This is not a count of independently
observed learner-error patterns. Article changes and spelling dominate; d/dt and
relative-pronoun examples remain sparse. Professional/legal prose dominates, and
synthetic error frequencies do not represent natural learner errors.

## Validation and recreation

All exported task rows, labels, edit reconstruction, document splits and artifact
checksums are validated. Before exclusion, all 478,930 originals were independently
recovered from pinned source offsets and all 241,701 spelling edits passed OpenTaal
checks. The release is a verified unchanged subset. Packaging checks every chat
instruction, input, answer and pair ID against the instruction exports.

```sh
python recreate_dataset.py --help
python recreate_dataset.py --root .
```

The bundled standard-library script validates or recreates task shards from bundled
canonical pairs. It does not recreate upstream source selection or certify linguistic
quality. Package checksums are in `metadata/manifest.json` and mechanical results in
`metadata/validation.json`. Preserve per-row attribution and deliberate-change notices
when reusing data; see [LICENSE.md](LICENSE.md).

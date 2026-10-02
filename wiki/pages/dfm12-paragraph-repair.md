---
type: Runbook
title: DFM12 Paragraph Candidate Repair
description: Bounded paragraph-only recovery, observed DynaWord boundary formats, and isolated CPU preparation.
tags: [dfm12, dynaword, paragraphs, cpu, provenance]
status: draft
last_updated: 2026-09-24
confidence: high
---
# DFM12 Paragraph Candidate Repair

Scope: paragraph repair only. See [component preparation](dfm12-components.md)
and the separately maintained [status snapshot](dfm12-status.md). No changes to
the other three transformations, existing candidates, audit IDs/queues,
training, evaluation, or final sampling. Replacement requires coordination
with the parent task; these outputs are **not replacements or accepted data**.

## Boundary Evidence

Inspected actual local parquet rows at the pinned revisions below, initially
100 rows per file, then a bounded probe of up to 256 rows per file spread across
up to eight evenly spaced row groups. Probe receipts live in
`data/dfm12-paragraph-probe-20260924/candidates/*/receipt.json`.
This is not proof of exhaustive corpus absence.

| Source | Pinned revision | Observed format |
| --- | --- | --- |
| Norwegian | `2bc33815865fb3d610e2a080b19156db8e98feef` | Both Wikipedia variants flattened; no recoverable paragraph separators in probe |
| Swedish | `f7cf2952b597eee76d8a3bddaa732ca6788b51c1` | Wikipedia and both reviewed Riksdagen constituents flattened in probe |
| Dutch | `d0158defd949699532e59dea5978c5542afb0400` | Constituent-specific formats, described below |

The combined 1,280 NB/NN/SV probe rows had no LF, CR, U+2028, U+2029, or
literal backslash-n. Sentence punctuation and flattened section titles cannot
justify inventing paragraphs. A source version retaining document structure
or a separately reviewed structure-preserving source is needed for recovery.

Dutch government `dienst_publiek_en_communicatie` has single-newline prose
blocks interspersed with headings. Actual rows 0, 1 and 5 were inspected:
coherent government website paragraphs, not fixed-width sentence wrapping.
Single-newline interpretation is restricted to this exact source/file pair.
Wikiwijs also has single newlines but includes short educational fragments and
link text; it does **not** receive that interpretation. Naturalis has PDF line
wrapping, and PBL has mixed wrapped lines and blank-line blocks. These retain
only explicit blank-line boundaries. European Parliament contains blank-line
blocks, but also multilingual navigation and agenda material requiring audit.

Quality caveat, 2026-09-24: the earlier source-selection description in
[component preparation](dfm12-components.md) says no bulk historical OCR was
selected. That is not a row-quality guarantee: actual Swedish parliamentary
samples include 1881/1908 texts and OCR-like artifacts. This supersedes any
inference that all selected parliamentary rows are modern clean prose.

User authorization, 2026-09-24: all DynaWord/DynaInstruct licenses are acceptable
across all languages. License-only holds in earlier planning are superseded by
that authorization; provenance, quality, format and contamination checks remain.
The paragraph repair itself has no license-only gate. It reuses explicit reviewed
file selections rather than expanding to unrelated constituents.

## Loss Mechanisms

Legacy receipts: NL has 415 paragraph candidates, NB/NN/SV zero. The inherited
accepted target is 22,516 per language (candidate allowance 33,774).

`transform.window` splits only on blank lines, randomly starts anywhere including
the last two blocks, stops at an oversized block, and falls back to sentences
when its initial block is oversized. That fallback can help other tasks but
cannot preserve paragraph structure. `prepare.prepare_transforms` shares the
same window and ranks documents before task eligibility; invalid paragraph
windows occupy its bounded heap and are not backfilled. It also assigns fixed
per-file quotas, so a productive constituent cannot cover an empty one.

Probe counts compare legacy structural validity (before rendering) with the
more conservative repaired structural validity, not final acceptance:

| Dutch constituent | Rows | Legacy valid | Repair valid | Repair valid, legacy invalid |
| --- | ---: | ---: | ---: | ---: |
| Government web | 256 | 0 | 99 | 99 |
| European Parliament | 256 | 128 | 136 | 62 |
| Naturalis | 256 | 34 | 27 | 5 |
| PBL | 256 | 176 | 176 | 18 |
| Wikiwijs | 256 | 0 | 0 | 0 |

Stricter checks intentionally lose some legacy windows; larger counts are not
the sole objective. The probe's 50 emitted NL examples preceded the final
per-file hash-ranking change; use its receipts for boundary diagnostics only.

## Conservative Implementation

New modules `dfm12/paragraph_repair.py` and `dfm12/cpu_paragraph_repair.py` leave
`transform.py`, `prepare.py`, and `cpu_transforms.py` unchanged. The opt-in path:

- Selects exactly three distinct, contiguous, complete source blocks, at most
  6,000 characters; never stitches documents, crosses a rejected heading/block,
  truncates a paragraph, or substitutes sentence rearrangement.
- Recognizes blank lines, CRLF and explicit U+2029; single-newline mode is
  restricted to the inspected Dutch government file. U+2028 is not a paragraph.
- Requires each block to have at least 80 characters, ten words and terminal
  punctuation; excludes obvious list starts. This is a conservative heuristic,
  not a quality or language certification.
- Selects a deterministic viable start, validates the real training-template
  rendering, then hash-ranks eligible candidates within each file's quota.
  Invalid windows no longer displace eligible ones in the selection heap.
- Preserves the existing transform ID algorithm and records repo/revision,
  source ID, absolute parquet ordinal, original text hash, normalized document
  hash, boundary mode, selected block index and repair version.
- Requires completed download receipts and pinned reviewed selections. Creates
  fresh component directories exclusively; never enqueues audits or overwrites
  existing component/queue outputs.

Bounded scanning reads prefixes of evenly spaced row groups, not a uniform
full-corpus sample. It may underfill limits when groups are small. Fixed per-file
quotas deliberately remain; no source-exhaustion claim or repetition is allowed.

## Validation and Launch

Verified command:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m pytest tests/test_dfm12_paragraph_repair.py tests/test_dfm12.py -q
```

61 tests passed, including real tokenizer coverage and new tests for separators,
contiguity, oversized blocks, duplicate blocks, no invented sentence boundaries,
bounded parquet ordinal preservation, immutable repair outputs and stable IDs.

Detached CPU job launched as PID **572115**, with a new session, null stdin,
`CUDA_VISIBLE_DEVICES=''`, `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, and
`TOKENIZERS_PARALLELISM=false`:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm12.cpu_paragraph_repair \
  --output data/dfm12-paragraph-repair-20260924-v1 \
  --rows-per-file 16000 --candidate-limit 2000
```

Log: `data/dfm12-paragraph-repair-20260924-v1.log`. The command refuses an existing
output root. Sources are NL, NO (NB/NN), SV only; no PL output is touched.
The existing CPU transform PID 509101 was observed alive initially and absent
after launch; no signal or output mutation was performed by the repair task.

### Completed Bounded Run

PID 572115 completed in the same turn. All three component receipts exist;
their candidate-file SHA256 checksums, unique IDs, paragraph counts and unchanged
transform ID algorithm were verified. Total rows inspected: **94,425**.

| Language | Inspected rows | Emitted unaudited candidates |
| --- | ---: | ---: |
| NL | 35,647 | 1,014 |
| NB | 16,000 | 0 |
| NN | 16,000 | 0 |
| SV | 26,778 | 0 |

NL emitted counts by constituent: government web 400, European Parliament 335,
Naturalis 32, PBL 245, Wikiwijs 2 (explicit blank-line mode only). Government web
had 6,089 eligible windows among 16,000 inspected rows, of which 6,081 failed
the legacy window path; the configured per-file cap retained only 400. Thus
1,014 is a bounded preparation result, not Dutch source exhaustion. Small files
(European Parliament, Naturalis and PBL) happened to be fully covered within
the row budget; large files were not fully scanned.

All 58,778 inspected NB/NN/SV rows lacked LF, CR, U+2028 and U+2029. One NN row
had literal backslash-n, which was intentionally not decoded or treated as a
boundary. The full-corpus absence of boundaries remains unproven.

Outstanding: independent language/quality/contamination audit; source-structure
recovery for NB/NN/SV; larger reviewed coverage to approach accepted targets;
cross-component deduplication and parent coordination before any merge or
replacement. The new and legacy NL counts must not simply be added together.

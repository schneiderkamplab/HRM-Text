---
type: Runbook
title: DFM12 Icelandic and Faroese DynaInstruct Staging
description: Owner-authorized license policy and isolated CPU preparation of pinned Icelandic and Faroese instruction sources.
tags: [dfm12, dynainstruct, icelandic, faroese, cpu, provenance]
status: draft
last_updated: 2026-09-24
confidence: high
---
# DFM12 Icelandic and Faroese DynaInstruct Staging

Parent: [DFM12 components](dfm12-components.md). Related:
[DFM12 status](dfm12-status.md), [page index](index.md).

## Explicit Owner Authorization

On 2026-09-24 the project owner explicitly authorized assuming **ALL DynaWord
and DynaInstruct licenses acceptable, for ALL languages**. This is owner
authorization, **not an independently verified legal finding**, and does not
relicense the material. Preserve upstream license text and attribution.

**Superseded, 2026-09-24:** the license-only holds for Icelandic/Faroese in
the component/status pages and pinned registry are historical. The replacement
is the owner authorization above, recorded in source-specific approval receipts
under `data/dfm12/approvals/dyna-instruct-{is,fo}.json`. The pinned registry is
not rewritten. These receipts permit unaudited CPU staging, not accepted export.
The authorization applies globally to both dataset families; this runner changes
only these two source approvals. Other agents must retain non-license gates.

No quality, provenance, language, format, contamination or deduplication gate is
waived. No GPU, Mistral fix, teacher audit, final sampling, training/evaluation
change, or modification of active jobs is part of this work.

## Pinned Sources and Inspection

| Registry key | Repository under `danish-foundation-models/` | Revision | Raw rows |
| --- | --- | --- | ---: |
| dyna-instruct-is | icelandic-dyna-instruct | a9fa6eb7d8cbed0a3b6b8112cfb4845e84090dc9 | 8,108 |
| dyna-instruct-fo | faroese-dyna-instruct | 8d56426e98fed42eec75ceba857ab0d0a74cce16 | 8,609 |

Each contains only `data/dynaword-reverse-instruct/dynaword-reverse-instruct.parquet`.
All Icelandic labels are `[isl]`; all Faroese labels `[fao]`. All actual rows
have exactly two messages, user then assistant; there are no actual multi-turn
rows to flatten. The adapter nevertheless preserves and validates all turns,
including checking earlier assistant messages, covered by regression tests.

Schema: string `id/source/added/created/task`, list-of-string `language`, int64
`token_count`, list-of-struct `messages(role, content)`. Original metadata is
retained separately from message content. Upstream token counts are Llama 3
counts and are not reused as Gemma4 counts.

Pinned README/datasheets describe synthetic Gemma 4 31B IT prompts paired with
original DynaWord passages, not model-generated assistant responses. Icelandic
includes encyclopedic, blog, legal, instructional and literary passages;
Faroese derives from Wikipedia and BLARK Small. Inspection found news/blog and
fragmentary source prose: prompt-answer suitability and fluency remain real
audit requirements, not satisfied by the language labels or upstream filtering.

Both constituent datasheets retain `license: other`, `license_name: Unknown`
for the generated instruction releases. They identify underlying BY/BY-SA
passage licenses. These historical source statements remain intact; they are
not rewritten to pretend independent legal verification occurred.

## Gates and Evidence

Implementation: `dfm12/cpu_island_instruct.py`; tests:
`tests/test_dfm12_island_instruct.py`. Shared transforms/configuration are untouched.

- Strict explicit source/language checks, alternating full conversations,
  nonempty text, no tools, embedded legacy templates or corrupt control text.
- Model/vendor checks in every assistant/system turn; ambiguous names require
  nearby identity language (English, Icelandic or Faroese). This is not a
  complete semantic identity detector. No identity text is rewritten.
- Benchmark-name quarantine and normalized exact text checks over all turns:
  MMLU, MMLU-Pro, GSM8K, HellaSwag, Winogrande, BoolQ, ARC-Challenge, PIQA,
  plus 108 checked-in Danish PIQA prompts. All eight external sources loaded;
  37,929 unique hashes. Full benchmark evidence/fingerprints and hashes retained.
- Disk-backed normalized conversation, assistant-passage and prompt deduplication
  within and across these two releases. Not a completed inherited-DFM11 or
  other-component duplicate audit.
- Every assistant target is rendered with the current raw DFM11 Gemma4 tokenizer
  and Jinja template, thinking disabled, maximum 4,096 tokens. Overlong full
  contexts are rejected before tokenization, not silently truncated to fit.

Remaining release blockers: teacher/human quality and low-resource fluency
review, translated/semantic benchmark overlap, and inherited/cross-component
deduplication. DynaWord-derived assistant passages may overlap transformation
sources. Exact-match screening is not proof of contamination absence.

## Completed Staging Counts

Final v3 completed on 2026-09-24; PID 590387 exited. These are **unaudited
candidates**, not accepted training data.

| Key | Input conversations | Staged/tokenized conversations | Gemma4 tokens | Rejected |
| --- | ---: | ---: | ---: | --- |
| dyna-instruct-is | 8,108 | 8,107 | 6,578,180 | 1 duplicate assistant passage |
| dyna-instruct-fo | 8,609 | 8,609 | 2,538,727 | 0 |
| Total | 16,717 | 16,716 | 9,116,907 | 1 |

No detected identity conflict, malformed-format, language-label, context-length,
benchmark-name or normalized exact benchmark rejection in the final run. This
does not clear semantic audit requirements. Five tokenized shards per language;
zero tokenizer-skipped rows. Verified candidate SHA256, current tokenizer/template
SHA256, tokenizer completion row counts, and actual token-array lengths against
the receipts. `git diff --check` passed. Final sampling was not performed.

## Operation

Final detached reduced-priority process launched as PID `590387`, with two tokenizer
workers, two download workers, single-thread numeric/Arrow settings and an empty
`CUDA_VISIBLE_DEVICES`. Process identity is also recorded in `process.json`.
No recursive delegation was used.

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
TOKENIZERS_PARALLELISM=false RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' \
nice -n 10 /home/ucloud/miniforge3/envs/hrm/bin/python -u \
  -m dfm12.cpu_island_instruct --workers 2
```

Run from the repository root. Default output is
`data/dfm12/island-instruct-unaudited-v3`; completed or partially converted
outputs are not overwritten: use a fresh `--output` for a deliberate new run.
The launcher uses `start_new_session=True` (setsid semantics).

Log: `data/dfm12/island-instruct-unaudited-v3.log`.
Downloads: `data/dfm12/downloads/dyna-instruct-{is,fo}`.
Per-source output: `candidates.jsonl`, `rejections.jsonl`, `receipt.json`,
`tokenizer_inputs_unaudited/`, `tokenized_unaudited/`.
Root evidence: `owner-license-authorization.json`, `benchmark-review.json`,
`benchmark-hashes.json`, `process.json`, `progress.json`, `complete.json`.
Receipts include source-file and tokenizer/template hashes and retained card paths.

Validation: pytest over
`tests/test_dfm12.py tests/test_dfm12_island_instruct.py` passed 56 tests,
including eight source-specific regression cases.
`unittest discover` does not discover the pytest-style existing DFM12 tests;
use pytest for the combined suite.

## Superseded Pilot Filters

Earlier completed staging directories `island-instruct-unaudited-v1` (PID
580763) and `island-instruct-unaudited-v2` (PID 587073) are retained as historical
evidence, **superseded by v3; do not combine or sample them**. Direct inspection
of all 15 v1 identity quarantines found historical people named Claude and a
band named Llama, not conflicting model identities. The detector now requires
identity context for ambiguous names. A mathematical `0<|x-c|` expression also
triggered the initial broad marker detector; v3 requires complete token markers.
Tests protect both cases. The historical counts are not final candidate totals.

The sole remaining duplicate is Icelandic ordinal 6739
(`dynaword-reverse-instruct_06739`), whose whitespace-normalized assistant
passage equals ordinal 6322, with a different user prompt. Keep the earlier
row; record the later row as `duplicate_response`, not an exact conversation
duplicate. No text is merged.

`python scripts/validate_okf.py wiki` reported only missing immediate-child index
links for this page and the concurrently added Norwegian and Polish source pages
at the final validation check (three errors). Index edits are reserved to the parent; no other conformance
errors were reported.

The shared status/index/log pages are intentionally not edited under the owner
concurrency constraint. Parent/index maintainer should add:
`[Icelandic and Faroese DynaInstruct staging](dfm12-island-instruct.md)`.

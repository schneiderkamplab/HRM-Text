---
type: Plan Record
title: New Source Additions (Code, Math, English Instruction)
description: 'Part of DFM9 Plan: New Source Additions (Code, Math, English Instruction).'
tags:
- dfm9
- data
- training
- factual-knowledge
- code
status: stable
last_updated: 2026-08-18
confidence: high
part_of: /pages/dfm9-plan.md
---
# New Source Additions (Code, Math, English Instruction)

Part of [DFM9 Plan](/pages/dfm9-plan.md).

Update, 2026-08-07. Confidence: high from local file inspection and conversion.

Beyond FLAN cap raising, 7 new sources were added to close additional eval gaps
(code, math, English instruction-following) identified in the FlexOlmo comparison.

## Historical source audit (copyright labels superseded 2026-08-16)
All sources audited for license, PII, and provenance before inclusion:

| Source | Repo ID | Rows (converted) | License | PII | Decision |
| --- | --- | ---: | --- | --- | --- |
| NuminaMath 1.5 | `AI-MO/NuminaMath-1.5` | 786K | MIT | No | Approved, cap 300K |
| Nemotron Terminal Corpus | `nvidia/nemotron-terminal-corpus` | 2.7M | NVIDIA | No | Approved, cap 200K |
| Code Meta Reasoning | `allenai/code_meta_reasoning` | 912K | Apache 2.0 (EU TDM) | No | Approved, cap 250K |
| Natural Instructions | `posttrain_natural_instructions` | 3.0M | OBSD (EU TDM) | Filtered | Approved, cap 500K, 96 PII tasks excluded |
| CoEdIT | `posttrain_coedit` | 70K | OBSD | No | Approved, uncapped |
| ASSET | `posttrain_asset` | 2.4K | CC-BY | No | Approved, uncapped |
| Nemotron SWE | `nvidia/nemotron-swe` | 2.03M (windowed) | NVIDIA | No | **Approved, cap 500K/file** — windowed converter drops system prompt+tools, truncates issue to 1500 tokens, sliding window of prior turns within 3584-token budget. 83.4% of rows fit 4096 after template overhead. |

Superseded, 2026-08-16: the license column above was preliminary engineering
triage and must not be used as the legal source register. Acquisition snapshots
show Apache-2.0 for NuminaMath 1.5 and CoEdIT, CC-BY-4.0 plus named code
licences for Nemotron SWE, and CC-BY-4.0 for Terminal Corpus. Code Meta
Reasoning and Natural Instructions have no adequate captured repository-level
content licence. ASSET is internally contradictory (CC-BY-SA frontmatter versus
research-only/CC-BY-NC card text). Mixture and derivative licences do not by
themselves clear every embedded work. Use the token-reconciled
[DFM9 Copyright and EU TDM Review](/pages/dfm9-copyright-tdm-review.md) and its
per-source register instead.

PII-sensitive tasks excluded from natural_instructions (96 files): SMS, tweets,
Amazon reviews, hate speech, civil comments, Yelp, IMDb, sentiment140, etc.
Filter logic in `scripts/convert_dfm9_new_sources.py` (`PII_EXCLUDE_KEYWORDS`).

## Conversion
6 unconverted sources were converted via `scripts/convert_dfm9_new_sources.py`
to condition/instruction/response parquet format. Nemotron SWE was already
converted. Output in `data/converted_sources/<source>/`.

Conversion details:
- NuminaMath: problem→instruction, solution→response, condition="cot"
- Terminal Corpus: conversations→messages expansion (multi-turn extraction)
- Code Meta Reasoning: raw text→continuation, condition="direct"
- Natural Instructions: definition+inputs→instruction, targets→response
- CoEdIT: src→instruction, tgt→response
- ASSET: original→instruction, simplification→response

**Superseded for DFM10 on 2026-08-30:** the historical Terminal Corpus
conversion flattened prior native roles into labelled text inside one user
message and collided on the repeated `data_filtered.parquet` basename. DFM10
does not inherit those four legacy tokenized tasks. It uses
`scripts/prepare_nemotron_terminal_native.py`, which preserves 366,154 original
conversations across 29 source-relative files and delegates expansion of all
3,101,906 assistant turns to `scripts/tokenize_chat_template.py`. This
supersession does not rewrite the historical DFM9 sampling record below.

## Tokenization
Tokenized via `scripts/tokenize_chat_template.py` (same pipeline as DFM8/DFM9
existing data). Tokenizer: `/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json`,
chat template: `data_io/chat_templates/gemma4_native_chat.jinja`, 8 workers.

Output: `data/tokenized_dfm9_new/` (694 directories, one per parquet file).

## Prefix config updates
5 new entries + 1 update added to `data_io/prefix_config_dfm9.yaml` (now 114
prefix entries, was 109):

```yaml
# DFM9 new sources — conservative caps (~6B new tokens).
- prefix: numinamath_1_5__
  max_per_file: 300000
- prefix: nemotron_terminal_corpus__
  max_per_file: 200000
- prefix: posttrain_natural_instructions__
  max_per_file: 500000
- prefix: posttrain_coedit__
  repeat: 1
- prefix: posttrain_asset__
  repeat: 1
```

Updated: `nemotron_swe__` replaced by `nemotron_swe_windowed__` with `max_per_file: 500000`.
The old `nemotron_swe__` entries (11 dirs) were removed from `tokenized_dfm9` and replaced
with 9 new entries (1 agentless + 8 merged SWE shards).

Windowing conversion (`scripts/convert_nemotron_swe_windowed.py`):
- **Agentless**: Flexible fit (inst+resp ≤ 4096 raw tokens). 135K rows, 265M tokens, 100% fit 4096.
- **SWE**: Sliding window — drop system prompt (~1720 tokens), drop tools (~2K template overhead),
  truncate user issue to 1500 tokens, 3584-token context budget, 512-token response limit.
  1.9M rows produced, 30B tokens. After chat template tokenization, 83.4% fit 4096
  (16.6% dropped by sampler's truncate mode — template adds ~5-7 tokens/message overhead
  not counted by converter's raw token budget).
- 64 tokenization shards merged into 8 files for effective per-file capping (8 × 500K = 4M cap).

`allenai_code_meta_reasoning__` was already in config at 250K but not previously
tokenized — now tokenized and active.

## Re-sampling Complete
Update, 2026-08-08. Confidence: high from `metadata.json` and sampler report.

DFM9 re-sampled with all new sources (including SWE windowed). 10 epochs, seed=0.

```text
metadata.json total_length: 93,718,826,298  (~93.72B tokens/epoch)
DFM8 was:                  70,479,433,697  (~70.48B tokens/epoch)
DFM9 first sampling was:   79,938,703,078  (~79.94B tokens/epoch)
Increase vs DFM8:           23,239,392,601  (~23.24B, +33.0%)
```

New source contributions per epoch (from sampler coverage report):

| Source | Rows (after cap) | Tokens/epoch | % of epoch |
| --- | ---: | ---: | ---: |
| nemotron_swe_windowed | 4,135,210 | 10,417,511,228 | 11.1% |
| allenai_code_meta_reasoning | 911,517 | 1,286,748,011 | 1.4% |
| nemotron_terminal_corpus | 312,865 | 986,121,784 | 1.1% |
| posttrain_natural_instructions | 2,729,950 | 723,722,346 | 0.8% |
| numinamath_1_5 | 786,435 | 361,647,178 | 0.4% |
| posttrain_coedit | 70,783 | 4,210,935 | <0.1% |
| posttrain_asset | 2,359 | 150,768 | <0.1% |
| **Total new** | **~8.0M** | **~13.8B** | **~14.7%** |

Factual FLAN (from first sampling, unchanged): ~10.2B tokens/epoch (repeat=2, 100K cap).

Output: `data/sampled_dfm9/` with 10 epoch dirs + `tokens.npy` (754GB).

## Training-host migration footprint (2026-08-10)
Confidence: high (verified against the local sampled tree and `dataset_new.py`).

- The complete 10-epoch sampled training tree is `data/sampled_dfm9/`: 42 regular
  files, 886,672,532,932 bytes total (826 GiB by `du`), with an
  808,954,206,220-byte `tokens.npy` and four 1,942,958,160-byte index arrays in
  each of `epoch_0` through `epoch_9`.
- Core training only reads `metadata.json`, `tokens.npy`, and the four arrays for
  the active epoch. It does not open the tokenizer path embedded in metadata.
- `data/tokenized_dfm9*` is not needed to train from the sampled tree. Transfer
  it only when the destination must reproduce or change sampling.
- Preserve the Gemma tokenizer JSON named by metadata for export/evaluation, or
  deliberately update that path on the destination. The Gemma model weights are
  not needed for HRM training.
- Superseded on 2026-08-10: `config/data/dfm9.yaml` has now been added and points
  to `data/sampled_dfm9`. No DFM9 checkpoint currently exists in this working
  tree; transfer a full checkpoint separately if continuing rather than starting
  a new run.

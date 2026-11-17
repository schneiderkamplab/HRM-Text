---
language:
- nb
- nn
license: other
task_categories:
- text-generation
task_ids:
- language-modeling
pretty_name: Dynaword Backtranslation (Norwegian)
size_categories:
- 1K<n<10K
configs:
- config_name: default
  data_files:
  - split: train
    path: data/*.parquet
---

# Dataset Card for `oliverkinch/dynaword-no-bt`

## Dataset Summary

`dynaword-no-bt` is a Norwegian instruction-tuning dataset generated with backtranslation from selected subsets of
`danish-foundation-models/norwegian-dynaword`.

Each row contains:

- `prompt`: a synthetic Norwegian user request suitable for instruction fine-tuning
- `target`: the source text passage that the prompt is intended to elicit
- `meta` and `sources`: provenance metadata (source subset, source row id, split, source type)

The dataset was built with the `backtranslation_passages_dynaword_nb` pipeline in `dfm-sdg` and includes
source-aware prompting, prompt form rotation, and passage-level filtering.

## Dataset Description

- Number of rows: **6,013** (`train`)
- Avg prompt length: **155.1 chars**
- Avg target length: **1,940.7 chars**
- Source corpus: `danish-foundation-models/norwegian-dynaword`

### Source distribution

- `government-nob`: 1,240
- `maalfrid`: 1,203
- `wikipedia-nob`: 991
- `wikipedia-nno`: 967
- `government-nno`: 876
- `public-reports`: 736

## Data Fields

- `id` (`string`): synthetic row id
- `prompt` (`string`): generated Norwegian instruction-like user prompt
- `target` (`string`): source text/passage
- `meta` (`struct`): pipeline metadata including
  - `source_name`, `source_type`, `source_id`, `source_record_index`, `passage_idx`, `target_chars`
- `sources` (`list[struct]`): provenance metadata (`dataset`, `config_name`, `split`, `row_id`)

## Creation Process

Rows were generated with source-specific prompting styles:

- `government`: `maalfrid`, `government-nob`, `government-nno`, `public-reports`
- `encyclopedic`: `wikipedia-nob`, `wikipedia-nno`

Pipeline highlights:

- hybrid/passages chunking with per-source controls
- wikitext markup stripping for Wikipedia sources
- filtering for OCR noise, repetitive segments, and sensitive content
- prompt form rotation (question, direct command, conversational, task context)
- prompt post-processing and validation (Norwegian language checks, prompt-shape checks, leakage controls, enumeration rejection)

Build verification checks passed for all uploaded rows:

- `prompt_present`
- `target_present`
- `target_min_chars`

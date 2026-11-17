---
language:
- da
license: other
task_categories:
- text-generation
task_ids:
- language-modeling
pretty_name: Dynaword Backtranslation (Danish)
size_categories:
- 10K<n<100K
configs:
- config_name: default
  data_files:
  - split: train
    path: data/*.parquet
---

# Dataset Card for `oliverkinch/dynaword-bt`

## Dataset Summary

`dynaword-bt` is a Danish instruction-tuning dataset generated with backtranslation from selected subsets of
`danish-foundation-models/danish-dynaword`.

Each row contains:

- `prompt`: a synthetic Danish user request suitable for instruction fine-tuning
- `target`: the source text passage that the prompt is intended to elicit
- `meta` and `sources`: provenance metadata (source subset, source row id, split, source type)

The dataset was built with the `backtranslation_passages_dynaword` pipeline in [dfm-sdg](https://github.com/danish-foundation-models/dfm-sdg) and includes
source-aware prompting plus passage-level filtering.

## Dataset Description

- Number of rows: **31,100** (`train`)
- Avg prompt length: **220.36 chars**
- Avg target length: **1,546.62 chars**
- Source corpus: `danish-foundation-models/danish-dynaword`

### Source distribution

- `danske-taler`: 2,805
- `ft`: 1,204
- `nordjyllandnews`: 4,661
- `tv2r`: 4,968
- `skat`: 4,408
- `miljoeportalen`: 8,303
- `ai-aktindsigt`: 4,751

## Data Fields

- `id` (`string`): synthetic row id
- `prompt` (`string`): generated Danish instruction-like user prompt
- `target` (`string`): source text/passage
- `meta` (`struct`): pipeline metadata including
  - `source_name`, `source_type`, `source_id`, `source_record_index`, `passage_idx`, `target_chars`
- `sources` (`list[struct]`): provenance metadata (`dataset`, `config_name`, `split`, `row_id`)

## Creation Process

Rows were generated with source-specific prompting styles:

- `speech`: `danske-taler`, `ft`
- `news`: `nordjyllandnews`, `tv2r`
- `tax_guidance`: `skat`
- `government`: `miljoeportalen`, `ai-aktindsigt`

Pipeline highlights:

- hybrid/full/passage chunking with per-source controls
- filtering for OCR noise and repetitive segments
- filtering for sensitive or unsuitable passages
- prompt post-processing and validation (Danish language checks, prompt-shape checks, leakage controls)

Build verification checks passed for all uploaded rows:

- `prompt_present`
- `target_present`
- `target_min_chars`


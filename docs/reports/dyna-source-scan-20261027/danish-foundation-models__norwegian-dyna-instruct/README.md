---
license: other
license_name: mixed-open-licenses
license_link: LICENSE
language:
- nob
- nno
- eng
tags:
- instruction-tuning
- post-training
- continual-development
- community-collaboration
pretty_name: Norwegian dyna-instruct
configs:
- config_name: default
  data_files:
  - split: train
    path:
    - data/nb-samtale-pairs/*.parquet
    - data/norquad-wikipedia/*.parquet
    - data/fleurs-alpaca-en-no/*.parquet
    - data/magpie-qwen3-bokmaal/*.parquet
    - data/reasoning-norwegian/*.parquet
- config_name: nb-samtale-pairs
  data_files:
  - split: train
    path: data/nb-samtale-pairs/*.parquet
- config_name: norquad-wikipedia
  data_files:
  - split: train
    path: data/norquad-wikipedia/*.parquet
- config_name: fleurs-alpaca-en-no
  data_files:
  - split: train
    path: data/fleurs-alpaca-en-no/*.parquet
- config_name: magpie-qwen3-bokmaal
  data_files:
  - split: train
    path: data/magpie-qwen3-bokmaal/*.parquet
- config_name: reasoning-norwegian
  data_files:
  - split: train
    path: data/reasoning-norwegian/*.parquet
task_categories:
- question-answering
- translation
- text-generation
---

# 🧨 Norwegian dyna-instruct

<!-- START README TABLE -->
|               |                                                                                             |
| ------------- | ------------------------------------------------------------------------------------------- |
| **Version**   | 0.1.0 ([changelog](CHANGELOG.md))                                                           |
| **Languages** | Norwegian Bokmål (`nob`), Norwegian Nynorsk (`nno`), and English (`eng`) translation input |
| **License**   | Mixed open licenses; see the table below                                                   |
| **Sources**   | Five datasets ([source cards](#source-data))                                       |
<!-- END README TABLE -->

## Dataset Description

<!-- START-DESC-STATS -->
- **Number of samples**: 14.40K
- **Number of tokens (Llama 3)**: 6.27M
- **Average conversation length in tokens (min, max)**: 435.63 (4, 8.92K)
- **Average number of turns (min, max)**: 2.13 (2, 3)
<!-- END-DESC-STATS -->

### Dataset Summary

Norwegian dyna-instruct is a collection of openly licensed Norwegian
instruction-tuning datasets. The five subsets share a common chat format and can be
loaded together or separately. Each subset has its own card describing its source,
preparation, and license.

Sources are included when their origin and creation are documented well enough to
understand the resulting training examples. The [source cards](#source-data) document
each included source, its provenance, and the checks applied during preparation.

> **Benchmark note:** `fleurs-alpaca-en-no` contains FLEURS training text drawn from
> FLORES-101 `dev` and `devtest`. Exclude this subset when evaluating on FLEURS or
> FLORES.

### Loading the dataset

Load the full collection with:

```py
from datasets import load_dataset

name = "danish-foundation-models/norwegian-dyna-instruct"
ds = load_dataset(name, split="train")
sample = ds[0]
```

Load a single subset by name:

```py
ds = load_dataset(name, "nb-samtale-pairs", split="train")
```

Pass `revision=` to `load_dataset` to pin a particular release.

### Languages

Rows use ISO 639-3 codes: `nob` for Bokmål, `nno` for Nynorsk, and `eng` for the
English side of translation examples.

### Task Types

<!-- START-TASK TABLE -->
| Task                  | Sources                                       | N. Tokens   |
|:----------------------|:----------------------------------------------|:------------|
| general               | [nb-samtale-pairs], [magpie-qwen3-bokmaal]    | 1.93M       |
| instruction_following | [magpie-qwen3-bokmaal], [reasoning-norwegian] | 1.74M       |
| qa                    | [norquad-wikipedia]                           | 1.44M       |
| reasoning             | [magpie-qwen3-bokmaal]                        | 853.65K     |
| code                  | [magpie-qwen3-bokmaal]                        | 189.17K     |
| translation           | [fleurs-alpaca-en-no]                         | 115.89K     |
| **Total**             |                                               | 6.27M       |

[nb-samtale-pairs]: data/nb-samtale-pairs/datasheet.md
[norquad-wikipedia]: data/norquad-wikipedia/datasheet.md
[fleurs-alpaca-en-no]: data/fleurs-alpaca-en-no/datasheet.md
[magpie-qwen3-bokmaal]: data/magpie-qwen3-bokmaal/datasheet.md
[reasoning-norwegian]: data/reasoning-norwegian/datasheet.md
<!-- END-TASK TABLE -->

### Licensing

<!-- START-LICENSE TABLE -->
| License      | Sources                                      | N. Tokens   |
|:-------------|:---------------------------------------------|:------------|
| Apache 2.0   | [magpie-qwen3-bokmaal]                       | 2.34M       |
| CC BY-SA 4.0 | [fleurs-alpaca-en-no], [reasoning-norwegian] | 1.74M       |
| CC BY-SA 3.0 | [norquad-wikipedia]                          | 1.44M       |
| CC0          | [nb-samtale-pairs]                           | 740.05K     |
| **Total**    |                                              | 6.27M       |

[nb-samtale-pairs]: data/nb-samtale-pairs/datasheet.md
[norquad-wikipedia]: data/norquad-wikipedia/datasheet.md
[fleurs-alpaca-en-no]: data/fleurs-alpaca-en-no/datasheet.md
[magpie-qwen3-bokmaal]: data/magpie-qwen3-bokmaal/datasheet.md
[reasoning-norwegian]: data/reasoning-norwegian/datasheet.md
<!-- END-LICENSE TABLE -->

The subsets keep their original licenses. Check the table and the linked subset card
before using or redistributing the data. Attribution files for ShareAlike subsets are
stored next to the data and are not returned by `load_dataset`.

## Dataset Structure

### Data Instances

<!-- START-SAMPLE -->
```py
{
  "id": "nb-samtale-pairs_nb-1_0000",
  "messages": [
    {
      "role": "user",
      "content": "Hallo og velkommen hit til Nasjonalbiblioteket. Det er kulturnatt, og det skjer en bråte ting over hele byen, og det gjø[...]"
    },
    {
      "role": "assistant",
      "content": "Tusen takk Lars. Vi er altså mer spennende enn kokte poteter. Det var godt å høre. Det var noen som hviska bak her, er v[...]"
    }
  ],
  "source": "nb-samtale-pairs",
  "added": "2026-09-03",
  "created": "2017-01-01, 2021-12-31",
  "language": [
    "nob"
  ],
  "task": "general",
  "token_count": 1227
}
```

### Data Fields

An entry in the dataset consists of the following fields:

- `id` (`str`): A unique identifier for each sample.
- `messages` (`list[dict]`): The conversation turns, each with a `role` and a text `content` field.
- `source` (`str`): The source dataset (see [Source Data](#source-data)).
- `added` (`str`): The date when the sample was added to this collection.
- `created` (`str`): The approximate date range when the source data was created, as `"YYYY-MM-DD, YYYY-MM-DD"` (start, end). Year-level granularity is used when the exact date is unknown.
- `language` (`list[str]`): The language(s) of the sample as ISO 639-3 codes (e.g. `["nob"]`, `["nno"]`, `["nob", "eng"]`).
- `task` (`str`): The task type of the sample.
- `token_count` (`int`): The total number of tokens across all messages, computed using the Llama 3 tokenizer.
<!-- END-SAMPLE -->

### Data Splits

The collection has one `train` split. Each subset is also available as a named
configuration.

## Dataset Creation

### Curation Rationale

The collection puts reusable Norwegian post-training data into one consistent format.
It complements [`norwegian-dynaword`](https://huggingface.co/datasets/danish-foundation-models/norwegian-dynaword)
and follows the continuously developed [Dynaword](https://arxiv.org/abs/2508.02271)
approach.

### Source Data

<details>
<summary><b>Included-source overview (click to unfold)</b></summary>

<!-- START-MAIN TABLE -->
| Source                 | Description                                                                 | Task                                            | N. Tokens   | License        |
|:-----------------------|:----------------------------------------------------------------------------|:------------------------------------------------|:------------|:---------------|
| [magpie-qwen3-bokmaal] | Synthetic Bokmål conversations generated by Qwen3-235B-A22B with Magpie     | general, reasoning, code, instruction_following | 2.34M       | [Apache 2.0]   |
| [reasoning-norwegian]  | Punctuation and capitalization corrections for Norwegian Wikipedia passages | instruction_following                           | 1.63M       | [CC BY-SA 4.0] |
| [norquad-wikipedia]    | Norwegian Wikipedia questions and answers in chat format                    | qa                                              | 1.44M       | [CC BY-SA 3.0] |
| [nb-samtale-pairs]     | Consecutive turns from the NB Samtale transcripts                           | general                                         | 740.05K     | [CC0]          |
| [fleurs-alpaca-en-no]  | English-to-Bokmål translation pairs from FLEURS                             | translation                                     | 115.89K     | [CC BY-SA 4.0] |
| **Total**              |                                                                             |                                                 | 6.27M       |                |

[nb-samtale-pairs]: data/nb-samtale-pairs/datasheet.md
[norquad-wikipedia]: data/norquad-wikipedia/datasheet.md
[fleurs-alpaca-en-no]: data/fleurs-alpaca-en-no/datasheet.md
[magpie-qwen3-bokmaal]: data/magpie-qwen3-bokmaal/datasheet.md
[reasoning-norwegian]: data/reasoning-norwegian/datasheet.md


[CC0]: https://creativecommons.org/publicdomain/zero/1.0/legalcode.en
[CC BY 2.0]: https://creativecommons.org/licenses/by/2.0/deed.en
[CC BY-SA 3.0]: https://creativecommons.org/licenses/by-sa/3.0/deed.en
[CC BY-SA 4.0]: https://creativecommons.org/licenses/by-sa/4.0/deed.en
[CC-BY 4.0]: https://creativecommons.org/licenses/by/4.0/deed.en
[Apache 2.0]: https://www.apache.org/licenses/LICENSE-2.0
<!-- END-MAIN TABLE -->

</details>

The linked source cards record upstream revisions, creation methods, licensing
evidence, attribution, and preparation steps for each included subset.

### Data Collection and Processing

Each subset is converted to the shared chat format by a `create.py` script with pinned
source revisions. Shared checks validate the schema, remove empty or duplicate
conversations, and calculate token counts. The subset cards describe their individual
processing steps.

### Dataset Statistics

The following plots are regenerated from the checked-in Parquet files:

<p align="center">
<img src="./images/creation_dates.png" width="800" />
</p>

<div style="display: flex; gap: 20px; align-items: flex-start;">
<p align="center"><img src="./images/dataset_size_plot.svg" width="400" /></p>
<p align="center"><img src="./images/dataset_turns_plot.svg" width="400" /></p>
</div>

### Contributing to the dataset

See [`CONTRIBUTING.md`](CONTRIBUTING.md) to propose a new source or improve an existing
one.

## Citation Information

Please cite the original sources listed in the subset cards. For the collection
methodology, cite Dynaword:

```bibtex
@article{enevoldsen2025dynaword,
  title = {Dynaword: From One-shot to Continuously Developed Datasets},
  author = {Enevoldsen, Kenneth and others},
  year = {2025},
  journal = {arXiv preprint arXiv:2508.02271},
  url = {https://arxiv.org/abs/2508.02271}
}
```

## License Information

There is no single content license for the collection. Each subset keeps the license
shown in the table above. Code and documentation created for this repository are
licensed under [Apache 2.0](LICENSE).

### Notice and takedown policy

Open an issue if you find a rights or privacy concern, and identify the affected source
or rows where possible.

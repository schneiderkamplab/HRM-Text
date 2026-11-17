---
license: cc-by-4.0
language:
- fao
tags:
- instruction-tuning
- post-training
- continual-development
- community-collaboration
pretty_name: Faroese dyna-instruct
configs:
- config_name: default
  data_files:
  - split: train
    path: data/*/*.parquet
- config_name: dynaword-reverse-instruct
  data_files:
  - split: train
    path: data/dynaword-reverse-instruct/*.parquet
- config_name: fo-instruct
  data_files:
  - split: train
    path: data/fo-instruct/*.parquet
- config_name: faroese-flan-fmd
  data_files:
  - split: train
    path: data/faroese-flan-fmd/*.parquet
- config_name: faroese-flan-fo-wikisource
  data_files:
  - split: train
    path: data/faroese-flan-fo-wikisource/*.parquet
- config_name: faroese-flan-fo-wiktionary
  data_files:
  - split: train
    path: data/faroese-flan-fo-wiktionary/*.parquet
- config_name: faroese-flan-fpsc
  data_files:
  - split: train
    path: data/faroese-flan-fpsc/*.parquet
- config_name: faroese-flan-gerdabokur
  data_files:
  - split: train
    path: data/faroese-flan-gerdabokur/*.parquet
- config_name: faroese-flan-islex-fo
  data_files:
  - split: train
    path: data/faroese-flan-islex-fo/*.parquet
- config_name: faroese-flan-kunngerdaportalur
  data_files:
  - split: train
    path: data/faroese-flan-kunngerdaportalur/*.parquet
- config_name: faroese-flan-logir
  data_files:
  - split: train
    path: data/faroese-flan-logir/*.parquet
- config_name: faroese-flan-logting-spurningar
  data_files:
  - split: train
    path: data/faroese-flan-logting-spurningar/*.parquet
- config_name: faroese-flan-lum
  data_files:
  - split: train
    path: data/faroese-flan-lum/*.parquet
- config_name: faroese-flan-ravnlex
  data_files:
  - split: train
    path: data/faroese-flan-ravnlex/*.parquet
- config_name: faroese-flan-sprotin
  data_files:
  - split: train
    path: data/faroese-flan-sprotin/*.parquet
task_categories:
- text-generation
---

# 🧨 Faroese dyna-instruct

<!-- START README TABLE -->
|              |                                                                                                                                                                                   |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Version** | 0.1.2 ([Changelog](/CHANGELOG.md)) |
| **Language** | Faroese (fao)                                                                                                                                                                     |
| **License**  | Openly Licensed, see individual datasets                                                                                                                                          |
| **Models**   | For models trained on this data see [danish-foundation-models](https://huggingface.co/danish-foundation-models)                                                                  |
| **Contact**  | If you have questions about this project please create an issue [here](https://huggingface.co/datasets/danish-foundation-models/faroese-dyna-instruct/discussions)              |
<!-- END README TABLE -->

## Table of Contents

- [🧨 Faroese dyna-instruct](#-faroese-dyna-instruct)
  - [Dataset Description](#dataset-description)
    - [Dataset Summary](#dataset-summary)
    - [Loading the dataset](#loading-the-dataset)
    - [Languages](#languages)
    - [Task Types](#task-types)
    - [Licensing](#licensing)
  - [Dataset Structure](#dataset-structure)
    - [Data Instances](#data-instances)
    - [Data Fields](#data-fields)
    - [Data Splits](#data-splits)
  - [Dataset Creation](#dataset-creation)
    - [Curation Rationale](#curation-rationale)
    - [Source Data](#source-data)
    - [Data Collection and Processing](#data-collection-and-processing)
    - [Dataset Statistics](#dataset-statistics)
    - [Contributing to the dataset](#contributing-to-the-dataset)
  - [Citation Information](#citation-information)
  - [License Information](#license-information)

## Dataset Description

<!-- START-DESC-STATS -->
- **Number of samples**: 1.01M
- **Number of tokens (Llama 3)**: 70.09M
- **Average conversation length in tokens (min, max)**: 69.44 (9, 46.56K)
- **Average number of turns (min, max)**: 2.0 (2, 2)
<!-- END-DESC-STATS -->

### Dataset Summary

Faroese dyna-instruct is a collection of instruction-tuning datasets from various sources. All datasets are openly licensed and deemed permissible for training large language models. The dataset is used to develop the DFM models.

Faroese dyna-instruct is continually developed using the [Dynaword](https://arxiv.org/abs/2508.02271) approach, meaning it will actively be updated as new datasets become available. If you would like to contribute a dataset see the [contribute section](#contributing-to-the-dataset).

### Loading the dataset

```py
from datasets import load_dataset

name = "danish-foundation-models/faroese-dyna-instruct"
ds = load_dataset(name, split="train")
sample = ds[0]
```

Or stream it:

```py
ds = load_dataset(name, split="train", streaming=True)
sample = next(iter(ds))
```

Load a single subset:

```py
ds = load_dataset(name, "dynaword-reverse-instruct", split="train")
```

Pin a revision for reproducibility:

```py
ds = load_dataset(name, revision="{desired revision}")
```

### Languages

This dataset includes multiple languages. The following figures give an overview of the languages in the dataset.

<img src="./images/task_distribution.png" width="800"/>

### Task Types

<!-- START-TASK TABLE -->
| Task      | Sources                                                                                                                                                                                                                                                                                                                                                            | N. Tokens   |
|:----------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------|
| general   | [dynaword-reverse-instruct], [fo-instruct], [faroese-flan-fmd], [faroese-flan-fo-wikisource], [faroese-flan-fo-wiktionary], [faroese-flan-fpsc], [faroese-flan-gerdabokur], [faroese-flan-islex-fo], [faroese-flan-kunngerdaportalur], [faroese-flan-logir], [faroese-flan-logting-spurningar], [faroese-flan-lum], [faroese-flan-ravnlex], [faroese-flan-sprotin] | 70.09M      |
| **Total** |                                                                                                                                                                                                                                                                                                                                                                    | 70.09M      |

[dynaword-reverse-instruct]: data/dynaword-reverse-instruct/datasheet.md
[fo-instruct]: data/fo-instruct/datasheet.md
[faroese-flan-fmd]: data/faroese-flan-fmd/datasheet.md
[faroese-flan-fo-wikisource]: data/faroese-flan-fo-wikisource/datasheet.md
[faroese-flan-fo-wiktionary]: data/faroese-flan-fo-wiktionary/datasheet.md
[faroese-flan-fpsc]: data/faroese-flan-fpsc/datasheet.md
[faroese-flan-gerdabokur]: data/faroese-flan-gerdabokur/datasheet.md
[faroese-flan-islex-fo]: data/faroese-flan-islex-fo/datasheet.md
[faroese-flan-kunngerdaportalur]: data/faroese-flan-kunngerdaportalur/datasheet.md
[faroese-flan-logir]: data/faroese-flan-logir/datasheet.md
[faroese-flan-logting-spurningar]: data/faroese-flan-logting-spurningar/datasheet.md
[faroese-flan-lum]: data/faroese-flan-lum/datasheet.md
[faroese-flan-ravnlex]: data/faroese-flan-ravnlex/datasheet.md
[faroese-flan-sprotin]: data/faroese-flan-sprotin/datasheet.md
<!-- END-TASK TABLE -->

The following task types are used:

- `general` — diverse SFT mixtures covering many capabilities
- `translation` — Faroese↔English translation
- `reasoning` — logical and mathematical reasoning with chain-of-thought
- `refusal` — safety refusals for harmful requests
- `code` — code generation and agentic code tasks
- `tool_use` — function calling and tool selection
- `instruction_following` — instruction-following benchmarks
- `knowledge` — knowledge-grounded generation
- `qa` — question answering

### Licensing

<!-- START-LICENSE TABLE -->
| License                            | Sources                                                                                                                                  | N. Tokens   |
|:-----------------------------------|:-----------------------------------------------------------------------------------------------------------------------------------------|:------------|
| CC-BY 4.0                          | [fo-instruct], [faroese-flan-fpsc], [faroese-flan-ravnlex]                                                                               | 27.81M      |
| Public domain (Faroe Islands, § 9) | [faroese-flan-gerdabokur], [faroese-flan-kunngerdaportalur], [faroese-flan-logir], [faroese-flan-logting-spurningar], [faroese-flan-lum] | 27.40M      |
| CC-BY-SA 4.0                       | [faroese-flan-fmd], [faroese-flan-fo-wikisource], [faroese-flan-fo-wiktionary], [faroese-flan-islex-fo]                                  | 7.20M       |
| MIT + CC BY 2.0 FR                 | [faroese-flan-sprotin]                                                                                                                   | 5.04M       |
| Unknown                            | [dynaword-reverse-instruct]                                                                                                              | 2.64M       |
| **Total**                          |                                                                                                                                          | 70.09M      |

[dynaword-reverse-instruct]: data/dynaword-reverse-instruct/datasheet.md
[fo-instruct]: data/fo-instruct/datasheet.md
[faroese-flan-fmd]: data/faroese-flan-fmd/datasheet.md
[faroese-flan-fo-wikisource]: data/faroese-flan-fo-wikisource/datasheet.md
[faroese-flan-fo-wiktionary]: data/faroese-flan-fo-wiktionary/datasheet.md
[faroese-flan-fpsc]: data/faroese-flan-fpsc/datasheet.md
[faroese-flan-gerdabokur]: data/faroese-flan-gerdabokur/datasheet.md
[faroese-flan-islex-fo]: data/faroese-flan-islex-fo/datasheet.md
[faroese-flan-kunngerdaportalur]: data/faroese-flan-kunngerdaportalur/datasheet.md
[faroese-flan-logir]: data/faroese-flan-logir/datasheet.md
[faroese-flan-logting-spurningar]: data/faroese-flan-logting-spurningar/datasheet.md
[faroese-flan-lum]: data/faroese-flan-lum/datasheet.md
[faroese-flan-ravnlex]: data/faroese-flan-ravnlex/datasheet.md
[faroese-flan-sprotin]: data/faroese-flan-sprotin/datasheet.md
<!-- END-LICENSE TABLE -->

## Dataset Structure

### Data Instances

<!-- START-SAMPLE -->
```py
{
  "id": "fo-instruct_00000",
  "messages": [
    {
      "role": "user",
      "content": "Hvat meina føroyingar við, tá teir brúka orðið 'loysing' í heila tikið?"
    },
    {
      "role": "assistant",
      "content": "Orðið 'loysing' í føroyskum sipar oftast til sambandið millum Føroyar og Danmark og hugsjónina um at Føroyar eiga at ley[...]"
    }
  ],
  "source": "fo-instruct",
  "added": "2026-10-05",
  "created": "2026-01-01, 2026-12-31",
  "language": [
    "fao"
  ],
  "task": "general",
  "token_count": 99
}
```

### Data Fields

An entry in the dataset consists of the following fields:

- `id` (`str`): A unique identifier for each sample.
- `messages` (`list[dict]`): The conversation turns — see the [message format](../../README.md#data-fields) section in the main README.
- `source` (`str`): The source dataset (see [Source Data](#source-data)).
- `added` (`str`): The date when the sample was added to this collection.
- `created` (`str`): The approximate date range when the source data was created, as `"YYYY-MM-DD, YYYY-MM-DD"` (start, end). Year-level granularity is used when the exact date is unknown.
- `language` (`list[str]`): The language(s) of the sample as ISO 639-3 codes (e.g. `["fao"]`, `["eng"]`, `["fao", "eng"]`).
- `task` (`str`): The task type of the sample.
- `token_count` (`int`): The total number of tokens across all messages, computed using the Llama 3 tokenizer.
<!-- END-SAMPLE -->

### Data Splits

The entire corpus is provided in the `train` split.

## Dataset Creation

### Curation Rationale

These datasets were collected and curated to make openly licensed instruction-tuning data available for post-training large language models. Faroese dyna-instruct forms the post-training complement to [Faroese Dynaword](https://huggingface.co/datasets/danish-foundation-models/faroese-dynaword), a continuously developed collection of Faroese pre-training text. Both are part of the [Danish Foundation Models](https://www.foundationmodels.dk) initiative. While collected with model training in mind, the data may also be useful for evaluation and research on Faroese language instruction-following.

### Source Data

Below is an overview of the sources with their individual licenses.

<details>
<summary><b>Overview Table (click to unfold)</b></summary>

<!-- START-MAIN TABLE -->
| Source                            | Description                                                                                                                       | Task    | N. Tokens   | License                              |
|:----------------------------------|:----------------------------------------------------------------------------------------------------------------------------------|:--------|:------------|:-------------------------------------|
| [faroese-flan-ravnlex]            | Instruction–response pairs from Ravnlex, via [Faroese FLAN](https://huggingface.co/datasets/Frejams/faroese-flan)                 | general | 20.78M      | [CC-BY 4.0]                          |
| [faroese-flan-logir]              | Instruction–response pairs from Legislation, via [Faroese FLAN](https://huggingface.co/datasets/Frejams/faroese-flan)             | general | 19.10M      | [Public domain (Faroe Islands, § 9)] |
| [faroese-flan-fpsc]               | Instruction–response pairs from FPSC, via [Faroese FLAN](https://huggingface.co/datasets/Frejams/faroese-flan)                    | general | 7.00M       | [CC-BY 4.0]                          |
| [faroese-flan-kunngerdaportalur]  | Instruction–response pairs from Official Gazette, via [Faroese FLAN](https://huggingface.co/datasets/Frejams/faroese-flan)        | general | 5.22M       | [Public domain (Faroe Islands, § 9)] |
| [faroese-flan-sprotin]            | Instruction–response pairs from Sprotin, via [Faroese FLAN](https://huggingface.co/datasets/Frejams/faroese-flan)                 | general | 5.04M       | [MIT + CC BY 2.0 FR]                 |
| [faroese-flan-islex-fo]           | Instruction–response pairs from ISLEX, via [Faroese FLAN](https://huggingface.co/datasets/Frejams/faroese-flan)                   | general | 3.69M       | [CC-BY-SA 4.0]                       |
| [faroese-flan-fmd]                | Instruction–response pairs from FMD, via [Faroese FLAN](https://huggingface.co/datasets/Frejams/faroese-flan)                     | general | 3.23M       | [CC-BY-SA 4.0]                       |
| [dynaword-reverse-instruct]       | Faroese instruction-following pairs derived from Faroese Dynaword                                                                 | general | 2.64M       | [Unknown]                            |
| [faroese-flan-lum]                | Instruction–response pairs from Ombudsman, via [Faroese FLAN](https://huggingface.co/datasets/Frejams/faroese-flan)               | general | 2.50M       | [Public domain (Faroe Islands, § 9)] |
| [faroese-flan-logting-spurningar] | Instruction–response pairs from Parliamentary questions, via [Faroese FLAN](https://huggingface.co/datasets/Frejams/faroese-flan) | general | 499.32K     | [Public domain (Faroe Islands, § 9)] |
| [faroese-flan-fo-wiktionary]      | Instruction–response pairs from Wiktionary, via [Faroese FLAN](https://huggingface.co/datasets/Frejams/faroese-flan)              | general | 151.75K     | [CC-BY-SA 4.0]                       |
| [faroese-flan-fo-wikisource]      | Instruction–response pairs from Wikisource, via [Faroese FLAN](https://huggingface.co/datasets/Frejams/faroese-flan)              | general | 126.13K     | [CC-BY-SA 4.0]                       |
| [faroese-flan-gerdabokur]         | Instruction–response pairs from Løgting minute books, via [Faroese FLAN](https://huggingface.co/datasets/Frejams/faroese-flan)    | general | 83.22K      | [Public domain (Faroe Islands, § 9)] |
| [fo-instruct]                     | Human-written Faroese instructions from [FO-Instruct](https://huggingface.co/datasets/Setur/fo-instruct)                          | general | 38.87K      | [CC-BY 4.0]                          |
| **Total**                         |                                                                                                                                   |         | 70.09M      |                                      |

[dynaword-reverse-instruct]: data/dynaword-reverse-instruct/datasheet.md
[fo-instruct]: data/fo-instruct/datasheet.md
[faroese-flan-fmd]: data/faroese-flan-fmd/datasheet.md
[faroese-flan-fo-wikisource]: data/faroese-flan-fo-wikisource/datasheet.md
[faroese-flan-fo-wiktionary]: data/faroese-flan-fo-wiktionary/datasheet.md
[faroese-flan-fpsc]: data/faroese-flan-fpsc/datasheet.md
[faroese-flan-gerdabokur]: data/faroese-flan-gerdabokur/datasheet.md
[faroese-flan-islex-fo]: data/faroese-flan-islex-fo/datasheet.md
[faroese-flan-kunngerdaportalur]: data/faroese-flan-kunngerdaportalur/datasheet.md
[faroese-flan-logir]: data/faroese-flan-logir/datasheet.md
[faroese-flan-logting-spurningar]: data/faroese-flan-logting-spurningar/datasheet.md
[faroese-flan-lum]: data/faroese-flan-lum/datasheet.md
[faroese-flan-ravnlex]: data/faroese-flan-ravnlex/datasheet.md
[faroese-flan-sprotin]: data/faroese-flan-sprotin/datasheet.md


[CC-0]: https://creativecommons.org/publicdomain/zero/1.0/legalcode.en
[CC-BY-SA 4.0]: https://creativecommons.org/licenses/by-sa/4.0/deed.en
[CC-BY 4.0]: https://creativecommons.org/licenses/by/4.0/deed.en
[Apache 2.0]: https://www.apache.org/licenses/LICENSE-2.0
[Unknown]: ./data/dynaword-reverse-instruct/datasheet.md#license-information
[Public domain (Faroe Islands, § 9)]: ./data/faroese-flan-gerdabokur/datasheet.md#license-information
[Public domain (Faroe Islands, § 9)]: ./data/faroese-flan-kunngerdaportalur/datasheet.md#license-information
[Public domain (Faroe Islands, § 9)]: ./data/faroese-flan-logir/datasheet.md#license-information
[Public domain (Faroe Islands, § 9)]: ./data/faroese-flan-logting-spurningar/datasheet.md#license-information
[Public domain (Faroe Islands, § 9)]: ./data/faroese-flan-lum/datasheet.md#license-information
[MIT + CC BY 2.0 FR]: ./data/faroese-flan-sprotin/datasheet.md#license-information
<!-- END-MAIN TABLE -->

</details>

### Data Collection and Processing

Faroese dyna-instruct is continually developed. Data collection and processing details are documented in the individual datasheets linked in the table above, and where possible in a reproducible `data/{dataset}/create.py` script.

In addition to dataset-specific processing, automated quality checks ensure correct column formatting, unique IDs, and no duplicate conversations.

### Dataset Statistics

The following plot shows the approximate creation date range of each source:

<p align="center">
<img src="./images/creation_dates.png" width="800" />
</p>

The following plots give an overview of conversation length and turn distributions across sources:

<div style="display: flex; gap: 20px; align-items: flex-start;">
<p align="center">
<img src="./images/dataset_size_plot.svg" width="400" />
</p>
<p align="center">
<img src="./images/dataset_turns_plot.svg" width="400" />
</p>
</div>

### Contributing to the dataset

Faroese dyna-instruct is continually developed.

We welcome contributions including new sources, improved filtering, and other enhancements. See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

## Citation Information

<!-- TODO: replace with actual release citation once published -->
If you use this work, please cite:

```bibtex
@article{enevoldsen2023danish,
  title={Danish Foundation Models},
  author={Enevoldsen, Kenneth and Hansen, Lasse and Nielsen, Dan S. and
          Egeb{\ae}k, Rasmus A. F. and Holm, S{\o}ren V. and Nielsen, Martin C. and
          Bernstorff, Martin and Larsen, Rasmus and J{\o}rgensen, Peter B. and
          H{\o}jmark-Bertelsen, Malte and Vahlstrup, Peter B. and
          M{\o}ldrup-Dalum, Per and Nielbo, Kristoffer},
  year={2023},
  journal={arXiv preprint arXiv:2311.07264},
  url={https://arxiv.org/abs/2311.07264}
}
```

## License Information

The license for each constituent dataset is listed in the [Source Data](#source-data) table. The collection itself (metadata, quality control, etc.) is licensed under [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.en).

### Notice and takedown policy

We redistribute files under licenses permitting such redistribution. If you have concerns about licensing or copyright, please [contact us](https://huggingface.co/datasets/danish-foundation-models/faroese-dyna-instruct/discussions/new).

---

<h3 style="display: flex; align-items: center;">
  <a href="https://www.foundationmodels.dk">
    <img src="./docs/icon.png" width="30" style="margin-right: 10px;" />
  </a>
  A&nbsp;<a href="https://www.foundationmodels.dk">Danish Foundation Models</a>&nbsp;dataset
</h3>

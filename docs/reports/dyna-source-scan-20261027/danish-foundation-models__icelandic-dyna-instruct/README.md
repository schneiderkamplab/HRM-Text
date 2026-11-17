---
license: cc-by-4.0
language:
- isl
tags:
- instruction-tuning
- post-training
- continual-development
- community-collaboration
pretty_name: Icelandic dyna-instruct
configs:
- config_name: default
  data_files:
  - split: train
    path: data/*/*.parquet
- config_name: dynaword-reverse-instruct
  data_files:
  - split: train
    path: data/dynaword-reverse-instruct/*.parquet
- config_name: icelandic-flan-bin-dmii
  data_files:
  - split: train
    path: data/icelandic-flan-bin-dmii/*.parquet
- config_name: icelandic-flan-enis-glossary
  data_files:
  - split: train
    path: data/icelandic-flan-enis-glossary/*.parquet
- config_name: icelandic-flan-icesquer
  data_files:
  - split: train
    path: data/icelandic-flan-icesquer/*.parquet
- config_name: icelandic-flan-icewordnet
  data_files:
  - split: train
    path: data/icelandic-flan-icewordnet/*.parquet
- config_name: icelandic-flan-dmii-abbr
  data_files:
  - split: train
    path: data/icelandic-flan-dmii-abbr/*.parquet
- config_name: icelandic-flan-dim-valency
  data_files:
  - split: train
    path: data/icelandic-flan-dim-valency/*.parquet
- config_name: icelandic-flan-ejournals-is
  data_files:
  - split: train
    path: data/icelandic-flan-ejournals-is/*.parquet
- config_name: icelandic-flan-eso
  data_files:
  - split: train
    path: data/icelandic-flan-eso/*.parquet
- config_name: icelandic-flan-hagstofa
  data_files:
  - split: train
    path: data/icelandic-flan-hagstofa/*.parquet
- config_name: icelandic-flan-igc-news
  data_files:
  - split: train
    path: data/icelandic-flan-igc-news/*.parquet
- config_name: icelandic-flan-islensk-nutimamalsordabok
  data_files:
  - split: train
    path: data/icelandic-flan-islensk-nutimamalsordabok/*.parquet
- config_name: icelandic-flan-islex
  data_files:
  - split: train
    path: data/icelandic-flan-islex/*.parquet
- config_name: icelandic-flan-ordanet
  data_files:
  - split: train
    path: data/icelandic-flan-ordanet/*.parquet
- config_name: icelandic-flan-ordskiptingar
  data_files:
  - split: train
    path: data/icelandic-flan-ordskiptingar/*.parquet
- config_name: icelandic-flan-rafbokavefur
  data_files:
  - split: train
    path: data/icelandic-flan-rafbokavefur/*.parquet
- config_name: icelandic-flan-spjallromur
  data_files:
  - split: train
    path: data/icelandic-flan-spjallromur/*.parquet
- config_name: icelandic-flan-stjornartidindi
  data_files:
  - split: train
    path: data/icelandic-flan-stjornartidindi/*.parquet
- config_name: icelandic-flan-umbodsmadur
  data_files:
  - split: train
    path: data/icelandic-flan-umbodsmadur/*.parquet
task_categories:
- text-generation
---

# 🧨 Icelandic dyna-instruct

<!-- START README TABLE -->
|              |                                                                                                                                                                                   |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Version**  | 0.1.1 ([Changelog](/CHANGELOG.md))                                                                                                                                               |
| **Language** | Icelandic (isl)                                                                                                                                                                   |
| **License**  | Openly Licensed, see individual datasets                                                                                                                                          |
| **Models**   | For models trained on this data see [danish-foundation-models](https://huggingface.co/danish-foundation-models)                                                                  |
| **Contact**  | If you have questions about this project please create an issue [here](https://huggingface.co/datasets/danish-foundation-models/icelandic-dyna-instruct/discussions)            |
<!-- END README TABLE -->

## Table of Contents

- [🧨 Icelandic dyna-instruct](#-icelandic-dyna-instruct)
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
- **Number of samples**: 610.10K
- **Number of tokens (Llama 3)**: 103.86M
- **Average conversation length in tokens (min, max)**: 170.23 (9, 60.90K)
- **Average number of turns (min, max)**: 2.0 (2, 2)
<!-- END-DESC-STATS -->

### Dataset Summary

Icelandic dyna-instruct is a collection of instruction-tuning datasets from various sources. All datasets are openly licensed and deemed permissible for training large language models. The dataset is used to develop the DFM models.

Icelandic dyna-instruct is continually developed using the [Dynaword](https://arxiv.org/abs/2508.02271) approach, meaning it will actively be updated as new datasets become available. If you would like to contribute a dataset see the [contribute section](#contributing-to-the-dataset).

### Loading the dataset

```py
from datasets import load_dataset

name = "danish-foundation-models/icelandic-dyna-instruct"
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
| Task      | Sources                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | N. Tokens   |
|:----------|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------|
| general   | [icelandic-flan-bin-dmii], [icelandic-flan-enis-glossary], [icelandic-flan-icesquer], [icelandic-flan-icewordnet], [icelandic-flan-dmii-abbr], [icelandic-flan-dim-valency], [icelandic-flan-ejournals-is], [icelandic-flan-eso], [icelandic-flan-hagstofa], [icelandic-flan-igc-news], [icelandic-flan-islensk-nutimamalsordabok], [icelandic-flan-islex], [icelandic-flan-ordanet], [icelandic-flan-ordskiptingar], [icelandic-flan-rafbokavefur], [icelandic-flan-spjallromur], [icelandic-flan-stjornartidindi], [icelandic-flan-umbodsmadur] | 96.76M      |
| knowledge | [dynaword-reverse-instruct]                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | 7.09M       |
| **Total** |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | 103.86M     |

[dynaword-reverse-instruct]: data/dynaword-reverse-instruct/datasheet.md
[icelandic-flan-bin-dmii]: data/icelandic-flan-bin-dmii/datasheet.md
[icelandic-flan-enis-glossary]: data/icelandic-flan-enis-glossary/datasheet.md
[icelandic-flan-icesquer]: data/icelandic-flan-icesquer/datasheet.md
[icelandic-flan-icewordnet]: data/icelandic-flan-icewordnet/datasheet.md
[icelandic-flan-dmii-abbr]: data/icelandic-flan-dmii-abbr/datasheet.md
[icelandic-flan-dim-valency]: data/icelandic-flan-dim-valency/datasheet.md
[icelandic-flan-ejournals-is]: data/icelandic-flan-ejournals-is/datasheet.md
[icelandic-flan-eso]: data/icelandic-flan-eso/datasheet.md
[icelandic-flan-hagstofa]: data/icelandic-flan-hagstofa/datasheet.md
[icelandic-flan-igc-news]: data/icelandic-flan-igc-news/datasheet.md
[icelandic-flan-islensk-nutimamalsordabok]: data/icelandic-flan-islensk-nutimamalsordabok/datasheet.md
[icelandic-flan-islex]: data/icelandic-flan-islex/datasheet.md
[icelandic-flan-ordanet]: data/icelandic-flan-ordanet/datasheet.md
[icelandic-flan-ordskiptingar]: data/icelandic-flan-ordskiptingar/datasheet.md
[icelandic-flan-rafbokavefur]: data/icelandic-flan-rafbokavefur/datasheet.md
[icelandic-flan-spjallromur]: data/icelandic-flan-spjallromur/datasheet.md
[icelandic-flan-stjornartidindi]: data/icelandic-flan-stjornartidindi/datasheet.md
[icelandic-flan-umbodsmadur]: data/icelandic-flan-umbodsmadur/datasheet.md
<!-- END-TASK TABLE -->

The following task types are used:

- `general` — diverse SFT mixtures covering many capabilities
- `translation` — Icelandic↔English translation
- `reasoning` — logical and mathematical reasoning with chain-of-thought
- `refusal` — safety refusals for harmful requests
- `code` — code generation and agentic code tasks
- `tool_use` — function calling and tool selection
- `instruction_following` — instruction-following benchmarks
- `knowledge` — knowledge-grounded generation
- `qa` — question answering

### Licensing

<!-- START-LICENSE TABLE -->
| License                           | Sources                                                                                                                                                                                                                                                      | N. Tokens   |
|:----------------------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------|
| CC-BY 4.0                         | [icelandic-flan-enis-glossary], [icelandic-flan-icesquer], [icelandic-flan-ejournals-is], [icelandic-flan-eso], [icelandic-flan-hagstofa], [icelandic-flan-igc-news], [icelandic-flan-ordanet], [icelandic-flan-ordskiptingar], [icelandic-flan-spjallromur] | 49.26M      |
| Public domain (Iceland, Art. 9)   | [icelandic-flan-stjornartidindi], [icelandic-flan-umbodsmadur]                                                                                                                                                                                               | 33.43M      |
| Rafbókavefurinn attribution terms | [icelandic-flan-rafbokavefur]                                                                                                                                                                                                                                | 8.53M       |
| Unknown                           | [dynaword-reverse-instruct]                                                                                                                                                                                                                                  | 7.09M       |
| CC-BY-SA 4.0                      | [icelandic-flan-bin-dmii], [icelandic-flan-dmii-abbr], [icelandic-flan-dim-valency], [icelandic-flan-islensk-nutimamalsordabok], [icelandic-flan-islex]                                                                                                      | 5.40M       |
| CC-BY 3.0                         | [icelandic-flan-icewordnet]                                                                                                                                                                                                                                  | 137.93K     |
| **Total**                         |                                                                                                                                                                                                                                                              | 103.86M     |

[dynaword-reverse-instruct]: data/dynaword-reverse-instruct/datasheet.md
[icelandic-flan-bin-dmii]: data/icelandic-flan-bin-dmii/datasheet.md
[icelandic-flan-enis-glossary]: data/icelandic-flan-enis-glossary/datasheet.md
[icelandic-flan-icesquer]: data/icelandic-flan-icesquer/datasheet.md
[icelandic-flan-icewordnet]: data/icelandic-flan-icewordnet/datasheet.md
[icelandic-flan-dmii-abbr]: data/icelandic-flan-dmii-abbr/datasheet.md
[icelandic-flan-dim-valency]: data/icelandic-flan-dim-valency/datasheet.md
[icelandic-flan-ejournals-is]: data/icelandic-flan-ejournals-is/datasheet.md
[icelandic-flan-eso]: data/icelandic-flan-eso/datasheet.md
[icelandic-flan-hagstofa]: data/icelandic-flan-hagstofa/datasheet.md
[icelandic-flan-igc-news]: data/icelandic-flan-igc-news/datasheet.md
[icelandic-flan-islensk-nutimamalsordabok]: data/icelandic-flan-islensk-nutimamalsordabok/datasheet.md
[icelandic-flan-islex]: data/icelandic-flan-islex/datasheet.md
[icelandic-flan-ordanet]: data/icelandic-flan-ordanet/datasheet.md
[icelandic-flan-ordskiptingar]: data/icelandic-flan-ordskiptingar/datasheet.md
[icelandic-flan-rafbokavefur]: data/icelandic-flan-rafbokavefur/datasheet.md
[icelandic-flan-spjallromur]: data/icelandic-flan-spjallromur/datasheet.md
[icelandic-flan-stjornartidindi]: data/icelandic-flan-stjornartidindi/datasheet.md
[icelandic-flan-umbodsmadur]: data/icelandic-flan-umbodsmadur/datasheet.md
<!-- END-LICENSE TABLE -->

## Dataset Structure

### Data Instances

<!-- START-SAMPLE -->
```py
{
  "id": "dynaword-reverse-instruct_00000",
  "messages": [
    {
      "role": "user",
      "content": "Hvað er ljós, hvernig er eðli þess lýst í eðlisfræði og hvað einkennir sýnilegt ljós?"
    },
    {
      "role": "assistant",
      "content": "Ljós Ljós er rafsegulbylgjur innan ákveðins tíðnisviðs, en oftast er átt við það tíðnisvið sem mannsaugað greinir. Við n[...]"
    }
  ],
  "source": "dynaword-reverse-instruct",
  "added": "2026-09-01",
  "created": "2026-01-01, 2026-12-31",
  "language": [
    "isl"
  ],
  "task": "knowledge",
  "token_count": 588
}
```

### Data Fields

An entry in the dataset consists of the following fields:

- `id` (`str`): A unique identifier for each sample.
- `messages` (`list[dict]`): The conversation turns — see the [message format](../../README.md#data-fields) section in the main README.
- `source` (`str`): The source dataset (see [Source Data](#source-data)).
- `added` (`str`): The date when the sample was added to this collection.
- `created` (`str`): The approximate date range when the source data was created, as `"YYYY-MM-DD, YYYY-MM-DD"` (start, end). Year-level granularity is used when the exact date is unknown.
- `language` (`list[str]`): The language(s) of the sample as ISO 639-3 codes (e.g. `["isl"]`, `["eng"]`, `["isl", "eng"]`).
- `task` (`str`): The task type of the sample.
- `token_count` (`int`): The total number of tokens across all messages, computed using the Llama 3 tokenizer.
<!-- END-SAMPLE -->

### Data Splits

The entire corpus is provided in the `train` split.

## Dataset Creation

### Curation Rationale

These datasets were collected and curated to make openly licensed instruction-tuning data available for post-training large language models. Icelandic dyna-instruct forms the post-training complement to [Icelandic Dynaword](https://huggingface.co/datasets/danish-foundation-models/icelandic-dynaword), a continuously developed collection of Icelandic pre-training text. Both are part of the [Danish Foundation Models](https://www.foundationmodels.dk) initiative. While collected with model training in mind, the data may also be useful for evaluation and research on Icelandic language instruction-following.

### Source Data

Below is an overview of the sources with their individual licenses.

<details>
<summary><b>Overview Table (click to unfold)</b></summary>

<!-- START-MAIN TABLE -->
| Source                                     | Description                                                                                                                                     | Task      | N. Tokens   | License                             |
|:-------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------|:----------|:------------|:------------------------------------|
| [icelandic-flan-umbodsmadur]               | Instruction–response pairs from Ombudsman, via [Icelandic FLAN](https://huggingface.co/datasets/Frejams/Icelandic-Flan)                         | general   | 27.75M      | [Public domain (Iceland, Art. 9)]   |
| [icelandic-flan-igc-news]                  | Instruction–response pairs from IGC news, via [Icelandic FLAN](https://huggingface.co/datasets/Frejams/Icelandic-Flan)                          | general   | 24.06M      | [CC-BY 4.0]                         |
| [icelandic-flan-rafbokavefur]              | Instruction–response pairs from Rafbókavefur, via [Icelandic FLAN](https://huggingface.co/datasets/Frejams/Icelandic-Flan)                      | general   | 8.53M       | [Rafbókavefurinn attribution terms] |
| [icelandic-flan-ordskiptingar]             | Instruction–response pairs from Orðskiptingar, via [Icelandic FLAN](https://huggingface.co/datasets/Frejams/Icelandic-Flan)                     | general   | 7.92M       | [CC-BY 4.0]                         |
| [dynaword-reverse-instruct]                | Icelandic instruction-following pairs derived from Icelandic Dynaword                                                                           | knowledge | 7.09M       | [Unknown]                           |
| [icelandic-flan-stjornartidindi]           | Instruction–response pairs from Official Gazette, via [Icelandic FLAN](https://huggingface.co/datasets/Frejams/Icelandic-Flan)                  | general   | 5.68M       | [Public domain (Iceland, Art. 9)]   |
| [icelandic-flan-ejournals-is]              | Instruction–response pairs from E-journals, via [Icelandic FLAN](https://huggingface.co/datasets/Frejams/Icelandic-Flan)                        | general   | 5.31M       | [CC-BY 4.0]                         |
| [icelandic-flan-hagstofa]                  | Instruction–response pairs from Statistics Iceland, via [Icelandic FLAN](https://huggingface.co/datasets/Frejams/Icelandic-Flan)                | general   | 4.43M       | [CC-BY 4.0]                         |
| [icelandic-flan-ordanet]                   | Instruction–response pairs from Orðanet, via [Icelandic FLAN](https://huggingface.co/datasets/Frejams/Icelandic-Flan)                           | general   | 3.68M       | [CC-BY 4.0]                         |
| [icelandic-flan-enis-glossary]             | Instruction–response pairs from English–Icelandic glossary, via [Icelandic FLAN](https://huggingface.co/datasets/Frejams/Icelandic-Flan)        | general   | 2.73M       | [CC-BY 4.0]                         |
| [icelandic-flan-islex]                     | Instruction–response pairs from ISLEX, via [Icelandic FLAN](https://huggingface.co/datasets/Frejams/Icelandic-Flan)                             | general   | 2.36M       | [CC-BY-SA 4.0]                      |
| [icelandic-flan-bin-dmii]                  | Instruction–response pairs from DMII, via [Icelandic FLAN](https://huggingface.co/datasets/Frejams/Icelandic-Flan)                              | general   | 1.74M       | [CC-BY-SA 4.0]                      |
| [icelandic-flan-eso]                       | Instruction–response pairs from ESO, via [Icelandic FLAN](https://huggingface.co/datasets/Frejams/Icelandic-Flan)                               | general   | 644.23K     | [CC-BY 4.0]                         |
| [icelandic-flan-dim-valency]               | Instruction–response pairs from DIM, via [Icelandic FLAN](https://huggingface.co/datasets/Frejams/Icelandic-Flan)                               | general   | 611.02K     | [CC-BY-SA 4.0]                      |
| [icelandic-flan-islensk-nutimamalsordabok] | Instruction–response pairs from Contemporary Icelandic Dictionary, via [Icelandic FLAN](https://huggingface.co/datasets/Frejams/Icelandic-Flan) | general   | 598.05K     | [CC-BY-SA 4.0]                      |
| [icelandic-flan-icesquer]                  | Instruction–response pairs from IceSQueR, via [Icelandic FLAN](https://huggingface.co/datasets/Frejams/Icelandic-Flan)                          | general   | 258.75K     | [CC-BY 4.0]                         |
| [icelandic-flan-spjallromur]               | Instruction–response pairs from Spjallrómur, via [Icelandic FLAN](https://huggingface.co/datasets/Frejams/Icelandic-Flan)                       | general   | 217.99K     | [CC-BY 4.0]                         |
| [icelandic-flan-icewordnet]                | Instruction–response pairs from IceWordNet, via [Icelandic FLAN](https://huggingface.co/datasets/Frejams/Icelandic-Flan)                        | general   | 137.93K     | [CC-BY 3.0]                         |
| [icelandic-flan-dmii-abbr]                 | Instruction–response pairs from DMII abbreviations, via [Icelandic FLAN](https://huggingface.co/datasets/Frejams/Icelandic-Flan)                | general   | 83.47K      | [CC-BY-SA 4.0]                      |
| **Total**                                  |                                                                                                                                                 |           | 103.86M     |                                     |

[dynaword-reverse-instruct]: data/dynaword-reverse-instruct/datasheet.md
[icelandic-flan-bin-dmii]: data/icelandic-flan-bin-dmii/datasheet.md
[icelandic-flan-enis-glossary]: data/icelandic-flan-enis-glossary/datasheet.md
[icelandic-flan-icesquer]: data/icelandic-flan-icesquer/datasheet.md
[icelandic-flan-icewordnet]: data/icelandic-flan-icewordnet/datasheet.md
[icelandic-flan-dmii-abbr]: data/icelandic-flan-dmii-abbr/datasheet.md
[icelandic-flan-dim-valency]: data/icelandic-flan-dim-valency/datasheet.md
[icelandic-flan-ejournals-is]: data/icelandic-flan-ejournals-is/datasheet.md
[icelandic-flan-eso]: data/icelandic-flan-eso/datasheet.md
[icelandic-flan-hagstofa]: data/icelandic-flan-hagstofa/datasheet.md
[icelandic-flan-igc-news]: data/icelandic-flan-igc-news/datasheet.md
[icelandic-flan-islensk-nutimamalsordabok]: data/icelandic-flan-islensk-nutimamalsordabok/datasheet.md
[icelandic-flan-islex]: data/icelandic-flan-islex/datasheet.md
[icelandic-flan-ordanet]: data/icelandic-flan-ordanet/datasheet.md
[icelandic-flan-ordskiptingar]: data/icelandic-flan-ordskiptingar/datasheet.md
[icelandic-flan-rafbokavefur]: data/icelandic-flan-rafbokavefur/datasheet.md
[icelandic-flan-spjallromur]: data/icelandic-flan-spjallromur/datasheet.md
[icelandic-flan-stjornartidindi]: data/icelandic-flan-stjornartidindi/datasheet.md
[icelandic-flan-umbodsmadur]: data/icelandic-flan-umbodsmadur/datasheet.md


[CC-0]: https://creativecommons.org/publicdomain/zero/1.0/legalcode.en
[CC-BY-SA 4.0]: https://creativecommons.org/licenses/by-sa/4.0/deed.en
[CC-BY 4.0]: https://creativecommons.org/licenses/by/4.0/deed.en
[CC-BY 3.0]: https://creativecommons.org/licenses/by/3.0/deed.en
[Apache 2.0]: https://www.apache.org/licenses/LICENSE-2.0
[Unknown]: ./data/dynaword-reverse-instruct/datasheet.md#license-information
[Rafbókavefurinn attribution terms]: ./data/icelandic-flan-rafbokavefur/datasheet.md#license-information
[Public domain (Iceland, Art. 9)]: ./data/icelandic-flan-stjornartidindi/datasheet.md#license-information
[Public domain (Iceland, Art. 9)]: ./data/icelandic-flan-umbodsmadur/datasheet.md#license-information
<!-- END-MAIN TABLE -->

</details>

### Data Collection and Processing

Icelandic dyna-instruct is continually developed. Data collection and processing details are documented in the individual datasheets linked in the table above, and where possible in a reproducible `data/{dataset}/create.py` script.

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

Icelandic dyna-instruct is continually developed.

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

We redistribute files under licenses permitting such redistribution. If you have concerns about licensing or copyright, please [contact us](https://huggingface.co/datasets/danish-foundation-models/icelandic-dyna-instruct/discussions/new).

---

<h3 style="display: flex; align-items: center;">
  <a href="https://www.foundationmodels.dk">
    <img src="./docs/icon.png" width="30" style="margin-right: 10px;" />
  </a>
  A&nbsp;<a href="https://www.foundationmodels.dk">Danish Foundation Models</a>&nbsp;dataset
</h3>

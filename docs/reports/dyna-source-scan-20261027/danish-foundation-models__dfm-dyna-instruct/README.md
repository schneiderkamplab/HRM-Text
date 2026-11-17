---
license: cc-by-4.0
language:
- dan
- eng
- fra
- deu
- ita
tags:
- instruction-tuning
- post-training
- continual-development
- community-collaboration
pretty_name: DFM dyna-instruct
configs:
- config_name: default
  data_files:
  - split: train
    path: data/*/*.parquet
- config_name: danish-verifiable-reasoning
  data_files:
  - split: train
    path: data/danish-verifiable-reasoning/*.parquet
- config_name: translation-100k
  data_files:
  - split: train
    path: data/translation-100k/*.parquet
- config_name: da-refusals
  data_files:
  - split: train
    path: data/da-refusals/*.parquet
- config_name: agentic-code-sft-mix-v1
  data_files:
  - split: train
    path: data/agentic-code-sft-mix-v1/*.parquet
- config_name: apertus-sft-mixture
  data_files:
  - split: train
    path: data/apertus-sft-mixture/*.parquet
- config_name: ifbench-train
  data_files:
  - split: train
    path: data/ifbench-train/*.parquet
- config_name: when2call
  data_files:
  - split: train
    path: data/when2call/*.parquet
- config_name: wildchat-qwen
  data_files:
  - split: train
    path: data/wildchat-qwen/*.parquet
- config_name: wiki-instruct-da
  data_files:
  - split: train
    path: data/wiki-instruct-da/*.parquet
- config_name: mt-da-deepseek
  data_files:
  - split: train
    path: data/mt-da-deepseek/*.parquet
task_categories:
- text-generation
---

# 🧨 DFM dyna-instruct

<!-- START README TABLE -->
|              |                                                                                                                                                                           |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Version** | 0.1.3 ([Changelog](/CHANGELOG.md)) |
| **Language** | Danish (dan), English (eng), French (fra), German (deu), Italian (ita)                                                                                                     |
| **License**  | Openly Licensed, see individual datasets                                                                                                                                  |
| **Models**   | For models trained on this data see [danish-foundation-models](https://huggingface.co/danish-foundation-models)                                                           |
| **Contact**  | If you have questions about this project please create an issue [here](https://huggingface.co/datasets/danish-foundation-models/dfm-dyna-instruct/discussions)         |
<!-- END README TABLE -->

## Table of Contents
- [🧨 DFM dyna-instruct](#-dfm-dyna-instruct)
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
  - [License information](#license-information)

## Dataset Description

<!-- START-DESC-STATS -->
- **Number of samples**: 4.40M
- **Number of tokens (Llama 3)**: 2.85B
- **Average conversation length in tokens (min, max)**: 648.07 (4, 119.87K)
- **Average number of turns (min, max)**: 2.61 (2, 294)
<!-- END-DESC-STATS -->

### Dataset Summary

DFM dyna-instruct is a collection of instruction-tuning datasets from various sources. All datasets are openly licensed and deemed permissible for training large language models. The datasets is used to develop the DFM models.

DFM dyna-instruct is continually developed using the [Dynaword](https://arxiv.org/abs/2508.02271) approach, meaning it will actively be updated as new datasets become available. If you would like to contribute a dataset see the [contribute section](#contributing-to-the-dataset).

### Loading the dataset

```py
from datasets import load_dataset

name = "danish-foundation-models/dfm-dyna-instruct"
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
ds = load_dataset(name, "danish-verifiable-reasoning", split="train")
```

Pin a revision for reproducibility:

```py
ds = load_dataset(name, revision="{desired revision}")
```

### Languages

This dataset includes multiple languages. The following figures gives an overview of the language in the dataset.


<img src="./images/task_distribution.png" width="800"/>



### Task Types


<!-- START-TASK TABLE -->
| Task                  | Sources                                                  | N. Tokens   |
|:----------------------|:---------------------------------------------------------|:------------|
| general               | [apertus-sft-mixture], [wildchat-qwen], [mt-da-deepseek] | 2.48B       |
| knowledge             | [wiki-instruct-da]                                       | 190.21M     |
| translation           | [translation-100k]                                       | 101.39M     |
| code                  | [agentic-code-sft-mix-v1]                                | 59.38M      |
| reasoning             | [danish-verifiable-reasoning]                            | 15.92M      |
| tool_use              | [when2call]                                              | 3.60M       |
| instruction_following | [ifbench-train]                                          | 974.40K     |
| refusal               | [da-refusals]                                            | 16.87K      |
| **Total**             |                                                          | 2.85B       |

[danish-verifiable-reasoning]: data/danish-verifiable-reasoning/datasheet.md
[translation-100k]: data/translation-100k/datasheet.md
[da-refusals]: data/da-refusals/datasheet.md
[agentic-code-sft-mix-v1]: data/agentic-code-sft-mix-v1/datasheet.md
[apertus-sft-mixture]: data/apertus-sft-mixture/datasheet.md
[ifbench-train]: data/ifbench-train/datasheet.md
[when2call]: data/when2call/datasheet.md
[wildchat-qwen]: data/wildchat-qwen/datasheet.md
[wiki-instruct-da]: data/wiki-instruct-da/datasheet.md
[mt-da-deepseek]: data/mt-da-deepseek/datasheet.md
<!-- END-TASK TABLE -->



The following task types are used:

- `general` — diverse SFT mixtures covering many capabilities
- `translation` — Danish↔English translation
- `reasoning` — logical and mathematical reasoning with chain-of-thought
- `refusal` — safety refusals for harmful requests
- `code` — code generation and agentic code tasks
- `tool_use` — function calling and tool selection
- `instruction_following` — instruction-following benchmarks
- `qa` — question answering

### Licensing

<!-- START-LICENSE TABLE -->
| License      | Sources                                                                                                  | N. Tokens   |
|:-------------|:---------------------------------------------------------------------------------------------------------|:------------|
| ODC-By       | [apertus-sft-mixture]                                                                                    | 2.30B       |
| CC-BY 4.0    | [danish-verifiable-reasoning], [agentic-code-sft-mix-v1], [when2call], [wildchat-qwen], [mt-da-deepseek], [da-refusals] | 259.73M     |
| Unknown      | [ifbench-train], [wiki-instruct-da]                                                                      | 191.18M     |
| CC-BY-SA 4.0 | [translation-100k]                                                                                       | 101.39M     |
| **Total**    |                                                                                                          | 2.85B       |

[danish-verifiable-reasoning]: data/danish-verifiable-reasoning/datasheet.md
[translation-100k]: data/translation-100k/datasheet.md
[da-refusals]: data/da-refusals/datasheet.md
[agentic-code-sft-mix-v1]: data/agentic-code-sft-mix-v1/datasheet.md
[apertus-sft-mixture]: data/apertus-sft-mixture/datasheet.md
[ifbench-train]: data/ifbench-train/datasheet.md
[when2call]: data/when2call/datasheet.md
[wildchat-qwen]: data/wildchat-qwen/datasheet.md
[wiki-instruct-da]: data/wiki-instruct-da/datasheet.md
[mt-da-deepseek]: data/mt-da-deepseek/datasheet.md
<!-- END-LICENSE TABLE -->


## Dataset Structure

### Data Instances

<!-- START-SAMPLE -->
```py
{
  "id": "translation-100k_000000",
  "messages": [
    {
      "role": "user",
      "content": "Oversæt denne tekst til engelsk.\n\nSvar kun med oversættelsen.\n\nTekst:\nKongeriget Belgien, Den Tjekkiske Republik, Konger[...]"
    },
    {
      "role": "assistant",
      "content": "the Kingdom of Belgium, the Czech Republic, the Kingdom of Denmark, the Federal Republic of Germany, the Republic of Est[...]"
    }
  ],
  "source": "translation-100k",
  "added": "2026-06-03",
  "created": "1993-01-01, 2023-12-31",
  "language": [
    "dan",
    "eng"
  ],
  "task": "translation",
  "token_count": 331
}
```

### Data Fields

An entry in the dataset consists of the following fields:

- `id` (`str`): A unique identifier for each sample.
- `messages` (`list[dict]`): The conversation turns — see the [message format](../../README.md#data-fields) section in the main README.
- `source` (`str`): The source dataset (see [Source Data](#source-data)).
- `added` (`str`): The date when the sample was added to this collection.
- `created` (`str`): The approximate date range when the source data was created, as `"YYYY-MM-DD, YYYY-MM-DD"` (start, end). Year-level granularity is used when the exact date is unknown.
- `language` (`list[str]`): The language(s) of the sample as ISO 639-3 codes (e.g. `["dan"]`, `["eng"]`, `["dan", "eng"]`).
- `task` (`str`): The task type of the sample.
- `token_count` (`int`): The total number of tokens across all messages, computed using the Llama 3 tokenizer.
<!-- END-SAMPLE -->

### Data Splits

The entire corpus is provided in the `train` split.

## Dataset Creation

### Curation Rationale

These datasets were collected and curated to make openly licensed instruction-tuning data available for post-training large language models. DFM dyna-instruct forms the post-training complement to [Danish Dynaword](https://huggingface.co/datasets/danish-foundation-models/danish-dynaword), a continuously developed collection of Danish pre-training text. Both are part of the [Danish Foundation Models](https://www.foundationmodels.dk) initiative. While collected with model training in mind, the data may also be useful for evaluation and research on Danish language instruction-following.

### Source Data

Below is an overview of the sources with their individual licenses.

<details>
<summary><b>Overview Table (click to unfold)</b></summary>

<!-- START-MAIN TABLE -->
| Source                        | Description                                                                                                                                                             | Task                  | N. Tokens   | License        |
|:------------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:----------------------|:------------|:---------------|
| [apertus-sft-mixture]         | Multilingual instruction-tuning samples from the Apertus SFT training mixture, covering general instruction following, reasoning, code, and multilingual capabilities   | general               | 2.30B       | [ODC-By]       |
| [wiki-instruct-da]            | Danish instruction-following pairs derived from Danish Wikipedia, where prompts ask for a short encyclopedic article and the target is the corresponding Wikipedia text | knowledge             | 190.21M     | [Unknown]      |
| [wildchat-qwen]               | Danish-predominant real user conversations with assistant turns re-generated using Qwen3.5-397B-A17B-NVFP4                                                              | general               | 171.51M     | [CC-BY 4.0]    |
| [translation-100k]            | Danish↔English translation pairs from EU legal and administrative corpora, with diverse instruction phrasings                                                           | translation           | 101.39M     | [CC-BY-SA 4.0] |
| [agentic-code-sft-mix-v1]     | English code instruction and agentic coding samples from three NVIDIA datasets, covering code Q&A, instruction following, and SWE-bench-style repository repair         | code                  | 59.38M      | [CC-BY 4.0]    |
| [danish-verifiable-reasoning] | Synthetic Danish logic puzzles with verified solutions and Qwen-235b chain-of-thought reasoning                                                                         | reasoning             | 15.92M      | [CC-BY 4.0]    |
| [mt-da-deepseek]              | Danish multi-turn conversations grounded in real Danish text excerpts, generated using DeepSeek via the APIGen-MT and ConsistentChat methods                            | general               | 9.30M       | [CC-BY 4.0]    |
| [when2call]                   | English tool-use samples teaching the model when to call a tool, ask for clarification, or respond directly — without making unnecessary tool calls                     | tool_use              | 3.60M       | [CC-BY 4.0]    |
| [ifbench-train]               | Danish instruction-following samples with verifiable constraints, drawn from IFBench and sourced from Danish WildChat conversations                                     | instruction_following | 974.40K     | [Unknown]      |
| [da-refusals]                 | Danish refusal responses covering harmful request categories including cybercrime, violence, hate speech, and self-harm                                                 | refusal               | 16.87K      | [CC-BY 4.0]    |
| **Total**                     |                                                                                                                                                                         |                       | 2.85B       |                |

[danish-verifiable-reasoning]: data/danish-verifiable-reasoning/datasheet.md
[translation-100k]: data/translation-100k/datasheet.md
[da-refusals]: data/da-refusals/datasheet.md
[agentic-code-sft-mix-v1]: data/agentic-code-sft-mix-v1/datasheet.md
[apertus-sft-mixture]: data/apertus-sft-mixture/datasheet.md
[ifbench-train]: data/ifbench-train/datasheet.md
[when2call]: data/when2call/datasheet.md
[wildchat-qwen]: data/wildchat-qwen/datasheet.md
[wiki-instruct-da]: data/wiki-instruct-da/datasheet.md
[mt-da-deepseek]: data/mt-da-deepseek/datasheet.md


[CC-0]: https://creativecommons.org/publicdomain/zero/1.0/legalcode.en
[CC-BY-SA 4.0]: https://creativecommons.org/licenses/by-sa/4.0/deed.en
[CC-BY 4.0]: https://creativecommons.org/licenses/by/4.0/deed.en
[Apache 2.0]: https://www.apache.org/licenses/LICENSE-2.0
[Unknown]: ./data/ifbench-train/datasheet.md#license-information
<!-- END-MAIN TABLE -->

</details>

### Data Collection and Processing

DFM dyna-instruct is continually developed. Data collection and processing details are documented in the individual datasheets linked in the table above, and where possible in a reproducible `data/{dataset}/create.py` script.

In addition to dataset-specific processing, automated quality checks ensure correct column formatting, unique IDs, and no duplicate conversations.

### Dataset Statistics

The following plot shows the approximate creation date range of each source, which can be used to filter out older data:

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

DFM dyna-instruct is continually developed. The following plot tracks how the total token count grows over time as new datasets are added:

<p align="center">
<img src="./images/tokens_over_time.svg" width="600" style="margin-right: 10px;" />
</p>

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

## License information

The license for each constituent dataset is listed in the [Source data](#source-data) table. The collection itself (metadata, quality control, etc.) is licensed under [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.en).

### Notice and takedown policy

We redistribute files under licenses permitting such redistribution. If you have concerns about licensing or copyright, please [contact us](https://huggingface.co/datasets/danish-foundation-models/dfm-dyna-instruct/discussions/new).

---

<h3 style="display: flex; align-items: center;">
  <a href="https://www.foundationmodels.dk">
    <img src="./docs/icon.png" width="30" style="margin-right: 10px;" />
  </a>
  A&nbsp;<a href=https://www.foundationmodels.dk>Danish Foundation Models</a>&nbsp;dataset
</h3>

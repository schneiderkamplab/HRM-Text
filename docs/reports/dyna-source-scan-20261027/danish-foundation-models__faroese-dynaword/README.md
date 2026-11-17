---
annotations_creators:
- machine-generated
language_creators:
- crowdsourced
language:
- fo
- fao
license: cc0-1.0
multilinguality:
- monolingual
source_datasets:
- original
task_categories:
- text-generation
task_ids:
- language-modeling
tags:
- text-corpus
- continual-development
- community-collaboration
- synthetic-annotations
pretty_name: Faroese Dynaword
configs:
- config_name: default
  data_files:
  - split: train
    path: data/*/data.parquet
- config_name: meta
  data_files:
  - split: train
    path: data/*/metadata.parquet
- config_name: sosialurin-faroese-pos
  data_files:
  - split: train
    path: data/sosialurin-faroese-pos/data.parquet
- config_name: wikipedia
  data_files:
  - split: train
    path: data/wikipedia/data.parquet
- config_name: ravnursson-asr
  data_files:
  - split: train
    path: data/ravnursson-asr/data.parquet
- config_name: fpsc
  data_files:
  - split: train
    path: data/fpsc/data.parquet
- config_name: faroese-blark-small
  data_files:
  - split: train
    path: data/faroese-blark-small/data.parquet
- config_name: logir
  data_files:
  - split: train
    path: data/logir/data.parquet
language_bcp47:
- fao-Latn
---

# 🧨 Faroese Dynaword


<!-- START README TABLE -->
|              |                                                                                                                                                                 |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Version** | 0.0.8 ([Changelog](/CHANGELOG.md)) |
| **Language** | Faroese (fo, fao) |
| **License**  | Openly Licensed, See the respective dataset |
| **Models**   | Currently there are no models trained on this dataset |
| **Contact**  | If you have question about this project please create an issue [here](https://huggingface.co/datasets/danish-foundation-models/faroese-dynaword/discussions) |
<!-- END README TABLE -->

## Table of Contents
- [🧨 Faroese Dynaword](#-faroese-dynaword)
  - [Table of Contents](#table-of-contents)
  - [Dataset Description](#dataset-description)
    - [Dataset Summary](#dataset-summary)
    - [Loading the dataset](#loading-the-dataset)
    - [Languages](#languages)
    - [Domains](#domains)
    - [Licensing](#licensing)
  - [Dataset Structure](#dataset-structure)
    - [Data Instances](#data-instances)
    - [Data Fields](#data-fields)
    - [Data Splits](#data-splits)
  - [Dataset Creation](#dataset-creation)
    - [Curation Rationale](#curation-rationale)
    - [Annotations](#annotations)
    - [Source Data](#source-data)
    - [Data Collection and Processing](#data-collection-and-processing)
    - [Dataset Statistics](#dataset-statistics)
    - [Contributing to the dataset](#contributing-to-the-dataset)
  - [Citation Information](#citation-information)
  - [License information](#license-information)
    - [Personal and Sensitive Information](#personal-and-sensitive-information)
    - [Bias, Risks, and Limitations](#bias-risks-and-limitations)
    - [Notice and takedown policy](#notice-and-takedown-policy)

## Dataset Description

<!-- START-DESC-STATS -->
- **Number of samples**: 410.89K
- **Number of tokens (Llama 3)**: 59.82M
- **Average document length in tokens (min, max)**: 145.6 (2, 208.41K)
<!-- END-DESC-STATS -->

### Dataset Summary

The Faroese dynaword is a collection of Faroese free-form text datasets from various domains. All of the datasets in the Faroese Dynaword are openly licensed 
and deemed permissible for training large language models. 

Faroese dynaword is continually developed, which means that the dataset will actively be updated as new datasets become available. If you would like to contribute a dataset see the [contribute section](#contributing-to-the-dataset).

### Loading the dataset

```py
from datasets import load_dataset

name = "danish-foundation-models/faroese-dynaword"
ds = load_dataset(name, split="train")
sample = ds[0]
```

or load it by streaming the data

```py
ds = load_dataset(name, split="train", streaming=True)
sample = next(iter(ds))
```

You can also load a single subset at a time:

```py
ds = load_dataset(name, "sosialurin-faroese-pos", split="train")
```

To allow filtering we additionally provide extensive [annotations](#annotations)
available through the `meta` config:

```py
meta = load_dataset(name, "meta", split = "train")
```

For more on how to use the annotations see [the annotations section](#annotations).

As Faroese dynaword is continually expanding and curated you can make sure that you get the same dataset every time by specifying the revision:

```py
ds = load_dataset(name, revision="{desired revision}")
```

### Languages

This dataset includes the following languages:

- Faroese (`fao-Latn`)

In addition it likely contains small amounts of English due to code-switching and other languages in quotations or embedded references.

Language is denoted using [BCP-47](https://en.wikipedia.org/wiki/IETF_language_tag), using the language code from [ISO 639-3](https://en.wikipedia.org/wiki/List_of_ISO_639_language_codes) and the script code from [ISO 15924](https://en.wikipedia.org/wiki/ISO_15924).

<!-- START-LANGUAGE TABLE -->
| Language   | Sources                                                                                | N. Tokens   |
|:-----------|:---------------------------------------------------------------------------------------|:------------|
| fo         | [sosialurin-faroese-pos], [wikipedia], [ravnursson-asr], [fpsc], [faroese-blark-small], [logir] | 59.82M      |
| **Total**  |                                                                                        | 59.82M      |

[sosialurin-faroese-pos]: data/sosialurin-faroese-pos/sosialurin-faroese-pos.md
[wikipedia]: data/wikipedia/wikipedia.md
[ravnursson-asr]: data/ravnursson-asr/ravnursson-asr.md
[fpsc]: data/fpsc/fpsc.md
[faroese-blark-small]: data/faroese-blark-small/faroese-blark-small.md
[logir]: data/logir/logir.md
<!-- END-LANGUAGE TABLE -->

### Domains

This dynaword consist of data from various domains (e.g., legal, books, social media). The following table and figure give an overview of the relative distributions of these domains. To see a full overview of the source check out the [source data section](#source-data)

<div style="display: flex; gap: 20px; align-items: flex-start;">

<div style="flex: 1;">

<!-- START-DOMAIN TABLE -->
| Domain       | Sources                  | N. Tokens   |
|:-------------|:-------------------------|:------------|
| Web          | [faroese-blark-small]    | 22.25M      |
| Spoken       | [fpsc]                   | 16.64M      |
| Legal        | [logir]                  | 14.43M      |
| Encyclopedic | [wikipedia]              | 5.45M       |
| Readaloud    | [ravnursson-asr]         | 794.44K     |
| News         | [sosialurin-faroese-pos] | 263.51K     |
| **Total**    |                          | 59.82M      |

[sosialurin-faroese-pos]: data/sosialurin-faroese-pos/sosialurin-faroese-pos.md
[wikipedia]: data/wikipedia/wikipedia.md
[ravnursson-asr]: data/ravnursson-asr/ravnursson-asr.md
[fpsc]: data/fpsc/fpsc.md
[faroese-blark-small]: data/faroese-blark-small/faroese-blark-small.md
[logir]: data/logir/logir.md
<!-- END-DOMAIN TABLE -->

</div>

<div style="flex: 1;">

<p align="center">
<img src="./images/domain_distribution.png" width="400" style="margin-right: 10px;" />
</p>

</div>

</div>



### Annotation Overview
<!-- START-ANNOTATION PLOTS -->
Each document in Faroese Dynaword comes with annotations describing its content, such as content quality, information density, and educational value.
Each bar shows the share of documents at each level of one annotation, from worst (light) to best (dark).
The same plot is available for every source in its datasheet, and the counts behind it are stored in `descriptive_stats.json` under `annotations`.
To learn more, see the [annotations section](#annotations).

<p align="center">
<img src="./images/annotation_profile.png" width="700" style="margin-right: 10px;" />
</p>
<!-- END-ANNOTATION PLOTS -->

### Licensing

The following gives an overview of the licensing in the Dynaword. To get the exact license of the individual datasets check out the [overview table](#source-data).
These license is applied to the constituent data, i.e., the text. The collection of datasets (metadata, quality control, etc.) is licensed under [CC-0](https://creativecommons.org/publicdomain/zero/1.0/legalcode.en).

<!-- START-LICENSE TABLE -->
| License      | Sources                                                                   | N. Tokens   |
|:-------------|:--------------------------------------------------------------------------|:------------|
| CC-BY 4.0    | [sosialurin-faroese-pos], [ravnursson-asr], [fpsc], [faroese-blark-small] | 39.95M      |
| CC-0 | [logir]                                                                   | 14.43M      |
| CC-BY-SA 4.0 | [wikipedia]                                                               | 5.45M       |
| **Total**    |                                                                           | 59.82M      |

[sosialurin-faroese-pos]: data/sosialurin-faroese-pos/sosialurin-faroese-pos.md
[wikipedia]: data/wikipedia/wikipedia.md
[ravnursson-asr]: data/ravnursson-asr/ravnursson-asr.md
[fpsc]: data/fpsc/fpsc.md
[faroese-blark-small]: data/faroese-blark-small/faroese-blark-small.md
[logir]: data/logir/logir.md
<!-- END-LICENSE TABLE -->

## Dataset Structure

The dataset contains text from different sources which are thoroughly defined in [Source Data](#source-data).

### Data Instances

Each entry in the dataset consists of a single text with associated metadata.

<!-- START-SAMPLE -->
```py
{
  "id": "ravnursson-asr_train_00000",
  "text": "tað hendi meir enn so at hann gloymdi at hann skuldi koma eftir henni hon bíðaði tolin hundarnir hav[...]",
  "source": "ravnursson-asr",
  "added": "2026-07-03",
  "created": "2022-11-19, 2022-11-19",
  "token_count": 53
}
```

### Data Fields

An entry in the dataset consists of the following fields:

- `id` (`str`): A unique identifier for each document.
- `text` (`str`): The content of the document.
- `source` (`str`): The source of the document (see [Source Data](#source-data)).
- `added` (`str`): The date when the document was added to this collection.
- `created` (`str`): The date range when the document was originally created.
- `token_count` (`int`): The number of tokens in the sample computed using the Llama 3 tokenizer.
<!-- END-SAMPLE -->

### Data Splits

The entire corpus is provided in the `train` split.

## Dataset Creation

### Curation Rationale

These datasets were collected and curated with the intention of making openly licensed Faroese data available. While this was collected with the intention of developing language models it is likely to have multiple other uses such as examining language development and differences across domains.

### Annotations

Synthetic metadata is stored as `data/{dataset}/metadata.parquet`. These
annotations were generated with [`ellamind/propella-1-4b`](https://huggingface.co/ellamind/propella-1-4b)
and include fields for content type, quality, safety, audience level,
educational level, PII presence, regional relevance and more.

The metadata rows include `dataset` and `id`, so a subset can be filtered and
joined with the corpus rows:

```py
from datasets import load_dataset

name = "danish-foundation-models/faroese-dynaword"
texts = load_dataset(name, "fpsc", split="train")
meta = load_dataset(name, "meta", split="train").filter(
    lambda row: row["dataset"] == "fpsc"
)

texts_df = texts.to_pandas()
meta_df = meta.to_pandas()
fpsc_with_meta = texts_df.merge(meta_df, on="id", how="left")
```


### Source Data

Below follows a brief overview of the sources in the corpus along with their individual license. To get more information about the individual dataset click the hyperlink in the table.

<details>
<summary><b>Overview Table (click to unfold)</b></summary>

<!-- START-MAIN TABLE -->
| Source                   | Description                                                                                                                | Domain       | N. Tokens   | License        |
|:-------------------------|:---------------------------------------------------------------------------------------------------------------------------|:-------------|:------------|:---------------|
| [faroese-blark-small]    | [BLARK Small](https://mtd.setur.fo/en/resource/1287/) is a filtered version of the Faroese BLARK text corpus               | Web          | 22.25M      | [CC-BY 4.0]    |
| [fpsc]                   | Faroese ASR transcripts of speeches from [Løgtingið](https://www.logting.fo/), the Parliament of the Faroe Islands         | Spoken       | 16.64M      | [CC-BY 4.0]    |
| [logir]                  | Faroese laws from [Logir](https://logir.fo/)                                                                                  | Legal        | 14.43M      | [CC-0] |
| [wikipedia]              | The Faroese subsection of [Wikipedia](https://fo.wikipedia.org/wiki/Forsíða)                                               | Encyclopedic | 5.45M       | [CC-BY-SA 4.0] |
| [ravnursson-asr]         | Normalized transcripts from the [Ravnursson ASR](https://huggingface.co/datasets/carlosdanielhernandezmena/ravnursson_asr) | Readaloud    | 794.44K     | [CC-BY 4.0]    |
| [sosialurin-faroese-pos] | Faroese newspaper text from the POS-tagged [Sosialurin](https://mtd.setur.fo/en/resource/sosialurin-faroese-pos/) corpus   | News         | 263.51K     | [CC-BY 4.0]    |
| **Total**                |                                                                                                                            |              | 59.82M      |                |

[sosialurin-faroese-pos]: data/sosialurin-faroese-pos/sosialurin-faroese-pos.md
[wikipedia]: data/wikipedia/wikipedia.md
[ravnursson-asr]: data/ravnursson-asr/ravnursson-asr.md
[fpsc]: data/fpsc/fpsc.md
[faroese-blark-small]: data/faroese-blark-small/faroese-blark-small.md
[logir]: data/logir/logir.md


[CC-0]: https://creativecommons.org/publicdomain/zero/1.0/legalcode.en
[CC-BY-SA 4.0]: https://creativecommons.org/licenses/by-sa/4.0/deed.en
[CC-BY 4.0]: https://creativecommons.org/licenses/by/4.0/deed.en
[Apache 2.0]: https://www.apache.org/licenses/LICENSE-2.0
<!-- END-MAIN TABLE -->

</details>

### Data Collection and Processing

This dynaword is continually developed, which means that the dataset will actively be updated as new datasets become available. This means that the size of Dynaword increases over time as seen in the following plot:

<p align="center">
<img src="./images/tokens_over_time.svg" width="600" style="margin-right: 10px;" />
</p>

The data collection and processing varies depending on the dataset and is documented in the individual datasheets, which are linked in the above table. If possible the collection is documented both in the datasheet and in the reproducible script (`data/{dataset}/create.py`).

In addition to data specific processing we also run a series automated quality checks to ensure formatting (e.g. ensuring correctly formatted columns and unique IDs), quality checks (e.g. duplicate and empty string detection) and datasheet documentation checks. These checks are there to ensure a high quality of documentation and a minimal level of quality. To allow for the development of novel cleaning methodologies we do not provide more extensive cleaning.

### Dataset Statistics

The following plot(s) are intended to give an overview of document length in the various sources. 

<p align="center">
<img src="./images/dataset_size_plot.svg" width="600" style="margin-right: 10px;" />
</p>

### Contributing to the dataset

We welcome contributions to the dataset, including new sources, improved data filtering, and other enhancements. To get started on contributing, please see [the contribution guidelines](CONTRIBUTING.md)

## Citation Information

If you use this work, please cite the [scientific article](https://arxiv.org/abs/2508.02271) introducing the Dynaword approach:

> Enevoldsen, K.C., Jensen, K.N., Kostkan, J., Szab'o, B.I., Kardos, M., Vad, K., Heinsen, J., N'unez, A.B., Barmina, G., Nielsen, J., Larsen, R., Vahlstrup, P.B., Dalum, P.M., Elliott, D., Galke, L., Schneider-Kamp, P., & Nielbo, K.L. (2025). Dynaword: From One-shot to Continuously Developed Datasets.

```bibtex
@article{enevoldsen2025dynaword,
  title={Dynaword: From One-shot to Continuously Developed Datasets},
  author={Enevoldsen, Kenneth and Jensen, Kristian N{\o}rgaard and Kostkan, Jan and Szab{\'o}, Bal{\'a}zs and Kardos, M{\'a}rton and Vad, Kirten and N{\'u}{\~n}ez, Andrea Blasi and Barmina, Gianluca and Nielsen, Jacob and Larsen, Rasmus and others},
  journal={arXiv preprint arXiv:2508.02271},
  year={2025}
}
```

Additionally, we recommend citing the relevant source datasets as well. See the individual datasheets for more information.

## License information

The license for each constituent dataset is supplied in the [Source data](#source-data) table. This license is applied to the constituent data, i.e., the text. The collection of datasets (metadata, quality control, etc.) is licensed under [CC-0](https://creativecommons.org/publicdomain/zero/1.0/legalcode.en).

### Personal and Sensitive Information

As far as we are aware the dataset does not contain information identifying sexual orientation, political beliefs, religion, or health connected along with a personal identifier of any non-public or non-historic figures.

### Bias, Risks, and Limitations

Certain works in this collection may be historical works and thus reflect the linguistic, cultural, and ideological norms of their time.
As such, it includes perspectives, assumptions, and biases characteristic of the period, which may be considered offensive or exclusionary by contemporary standards.

### Notice and takedown policy

We redistribute files shared with us under a license permitting such redistribution. If you have concerns about the licensing of these files, please [contact us](https://huggingface.co/datasets/danish-foundation-models/faroese-dynaword/discussions/new). If you consider that the data contains material that infringe your copyright, please:

- Clearly identify yourself with detailed contact information such as an address, a telephone number, or an email address at which you can be contacted.
- Clearly reference the original work claimed to be infringed
- Clearly identify the material claimed to be infringing and information reasonably sufficient to allow us to locate the material.

You can contact us through this channel.
We will comply with legitimate requests by removing the affected sources from the next release of the corpus

---

<h3 style="display: flex; align-items: center;">
  <a href="https://www.foundationmodels.dk">
    <img src="./docs/icon.png" width="30" style="margin-right: 10px;" />
  </a>
  A&nbsp;<a href="https://www.foundationmodels.dk">Danish Foundation Models</a>&nbsp;dataset
</h3>

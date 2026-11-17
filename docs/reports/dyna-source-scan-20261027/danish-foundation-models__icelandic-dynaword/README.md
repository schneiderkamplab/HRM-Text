---
annotations_creators:
- machine-generated
language_creators:
- crowdsourced
language:
- is
- isl
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
pretty_name: Icelandic Dynaword
configs:
- config_name: default
  data_files:
  - split: train
    path: data/*/data.parquet
- config_name: meta
  data_files:
  - split: train
    path: data/*/metadata.parquet
- config_name: igc-parla
  data_files:
  - split: train
    path: data/igc-parla/data.parquet
- config_name: igc-journals-22-10
  data_files:
  - split: train
    path: data/igc-journals-22-10/data.parquet
- config_name: igc-adjud
  data_files:
  - split: train
    path: data/igc-adjud/data.parquet
- config_name: igc-law
  data_files:
  - split: train
    path: data/igc-law/data.parquet
- config_name: saga
  data_files:
  - split: train
    path: data/saga/data.parquet
- config_name: igc-social-blogs
  data_files:
  - split: train
    path: data/igc-social-blogs/data.parquet
- config_name: igc-social-bland
  data_files:
  - split: train
    path: data/igc-social-bland/data.parquet
- config_name: igc-social-hugi
  data_files:
  - split: train
    path: data/igc-social-hugi/data.parquet
- config_name: igc-social-malefnin
  data_files:
  - split: train
    path: data/igc-social-malefnin/data.parquet
- config_name: wikipedia
  data_files:
  - split: train
    path: data/wikipedia/data.parquet
- config_name: hjh-corpus
  data_files:
  - split: train
    path: data/hjh-corpus/data.parquet
- config_name: wiki-comments
  data_files:
  - split: train
    path: data/wiki-comments/data.parquet
- config_name: wikisource
  data_files:
  - split: train
    path: data/wikisource/data.parquet
- config_name: wikibooks
  data_files:
  - split: train
    path: data/wikibooks/data.parquet
- config_name: stjornartidindi
  data_files:
  - split: train
    path: data/stjornartidindi/data.parquet
- config_name: icepahc
  data_files:
  - split: train
    path: data/icepahc/data.parquet
- config_name: gutenberg
  data_files:
  - split: train
    path: data/gutenberg/data.parquet
- config_name: rafbokavefur
  data_files:
  - split: train
    path: data/rafbokavefur/data.parquet
language_bcp47:
- isl
---

# 🧨 Icelandic Dynaword


<!-- START README TABLE -->
|              |                                                                                                                                                                   |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Version** | 0.0.15 ([Changelog](/CHANGELOG.md)) |
| **Language** | Icelandic (is, isl) |
| **License**  | Openly Licensed, See the respective dataset |
| **Models**   | Currently there is no models trained on this dataset |
| **Contact**  | If you have question about this project please create an issue [here](https://huggingface.co/datasets/danish-foundation-models/icelandic-dynaword/discussions) |
<!-- END README TABLE -->

## Table of Contents
- [🧨 Icelandic Dynaword](#-icelandic-dynaword)
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
- **Number of samples**: 39.85M
- **Number of tokens (Llama 3)**: 2.67B
- **Average document length in tokens (min, max)**: 66.98 (3, 1.03M)
<!-- END-DESC-STATS -->

### Dataset Summary

The Icelandic dynaword is a collection of Icelandic free-form text datasets from various domains. All of the datasets in the Icelandic Dynaword are openly licensed 
and deemed permissible for training large language models. 

Icelandic dynaword is continually developed, which means that the dataset will actively be updated as new datasets become available. If you would like to contribute a dataset see the [contribute section](#contributing-to-the-dataset).

### Loading the dataset

```py
from datasets import load_dataset

name = "danish-foundation-models/icelandic-dynaword"
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
ds = load_dataset(name, "igc-parla", split="train")
```

To allow filtering we additionally provide extensive [annotations](#annotations)
available through the `meta` config:

```py
meta = load_dataset(name, "meta", split="train")
```

For more on how to use the annotations see [the annotations section](#annotations).

As Icelandic dynaword is continually expanding and curated you can make sure that you get the same dataset every time by specifying the revision:

```py
ds = load_dataset(name, revision="{desired revision}")
```

### Languages

This dataset includes the following languages:

- Icelandic (`isl-Latn`)

In addition it likely contains small amounts of English due to code-switching and other languages in quotations or embedded references.

Language is denoted using [BCP-47](https://en.wikipedia.org/wiki/IETF_language_tag), using the language code from [ISO 639-3](https://en.wikipedia.org/wiki/List_of_ISO_639_language_codes) and the script code from [ISO 15924](https://en.wikipedia.org/wiki/ISO_15924).

<!-- START-LANGUAGE TABLE -->
| Language   | Sources                                                                                                                                                                                                                                                                               | N. Tokens   |
|:-----------|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------|
| is         | [igc-parla], [igc-journals-22-10], [igc-adjud], [igc-law], [saga], [igc-social-blogs], [igc-social-bland], [igc-social-hugi], [igc-social-malefnin], [wikipedia], [hjh-corpus], [wiki-comments], [wikisource], [wikibooks], [stjornartidindi], [icepahc], [gutenberg], [rafbokavefur] | 2.67B       |
| **Total**  |                                                                                                                                                                                                                                                                                       | 2.67B       |

[igc-parla]: data/igc-parla/igc-parla.md
[igc-journals-22-10]: data/igc-journals-22-10/igc-journals-22-10.md
[igc-adjud]: data/igc-adjud/igc-adjud.md
[igc-law]: data/igc-law/igc-law.md
[saga]: data/saga/saga.md
[igc-social-blogs]: data/igc-social-blogs/igc-social-blogs.md
[igc-social-bland]: data/igc-social-bland/igc-social-bland.md
[igc-social-hugi]: data/igc-social-hugi/igc-social-hugi.md
[igc-social-malefnin]: data/igc-social-malefnin/igc-social-malefnin.md
[wikipedia]: data/wikipedia/wikipedia.md
[hjh-corpus]: data/hjh-corpus/hjh-corpus.md
[wiki-comments]: data/wiki-comments/wiki-comments.md
[wikisource]: data/wikisource/wikisource.md
[wikibooks]: data/wikibooks/wikibooks.md
[stjornartidindi]: data/stjornartidindi/stjornartidindi.md
[icepahc]: data/icepahc/icepahc.md
[gutenberg]: data/gutenberg/gutenberg.md
[rafbokavefur]: data/rafbokavefur/rafbokavefur.md
<!-- END-LANGUAGE TABLE -->

### Domains

This dynaword consist of data from various domains (e.g., legal, books, social media). The following table and figure give an overview of the relative distributions of these domains. To see a full overview of the source check out the [source data section](#source-data)

<div style="display: flex; gap: 20px; align-items: flex-start;">

<div style="flex: 1;">

<!-- START-DOMAIN TABLE -->
| Domain       | Sources                                                                          | N. Tokens   |
|:-------------|:---------------------------------------------------------------------------------|:------------|
| Social Media | [igc-social-blogs], [igc-social-bland], [igc-social-hugi], [igc-social-malefnin] | 1.36B       |
| Conversation | [igc-parla], [wiki-comments]                                                     | 707.14M     |
| Legal        | [igc-adjud], [igc-law], [stjornartidindi]                                        | 480.08M     |
| Encyclopedic | [igc-journals-22-10], [wikipedia]                                                | 94.47M      |
| Books        | [saga], [wikisource], [wikibooks], [icepahc], [gutenberg], [rafbokavefur]        | 27.05M      |
| Speeches     | [hjh-corpus]                                                                     | 738.68K     |
| **Total**    |                                                                                  | 2.67B       |

[igc-parla]: data/igc-parla/igc-parla.md
[igc-journals-22-10]: data/igc-journals-22-10/igc-journals-22-10.md
[igc-adjud]: data/igc-adjud/igc-adjud.md
[igc-law]: data/igc-law/igc-law.md
[saga]: data/saga/saga.md
[igc-social-blogs]: data/igc-social-blogs/igc-social-blogs.md
[igc-social-bland]: data/igc-social-bland/igc-social-bland.md
[igc-social-hugi]: data/igc-social-hugi/igc-social-hugi.md
[igc-social-malefnin]: data/igc-social-malefnin/igc-social-malefnin.md
[wikipedia]: data/wikipedia/wikipedia.md
[hjh-corpus]: data/hjh-corpus/hjh-corpus.md
[wiki-comments]: data/wiki-comments/wiki-comments.md
[wikisource]: data/wikisource/wikisource.md
[wikibooks]: data/wikibooks/wikibooks.md
[stjornartidindi]: data/stjornartidindi/stjornartidindi.md
[icepahc]: data/icepahc/icepahc.md
[gutenberg]: data/gutenberg/gutenberg.md
[rafbokavefur]: data/rafbokavefur/rafbokavefur.md
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
Each document in Icelandic Dynaword comes with annotations describing its content, such as content quality, information density, and educational value.
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
| License                      | Sources                                                                                                                                                        | N. Tokens   |
|:-----------------------------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------|
| CC-BY 4.0                    | [igc-parla], [igc-journals-22-10], [igc-adjud], [igc-law], [saga], [igc-social-blogs], [igc-social-bland], [igc-social-hugi], [igc-social-malefnin], [icepahc] | 2.52B       |
| Icelandic Copyright Law      | [stjornartidindi], [rafbokavefur]                                                                                                                              | 102.80M     |
| CC-BY-SA 4.0                 | [wikipedia], [hjh-corpus], [wiki-comments], [wikisource], [wikibooks]                                                                                          | 47.70M      |
| Other (Attribution required) | [gutenberg]                                                                                                                                                    | 227.43K     |
| **Total**                    |                                                                                                                                                                | 2.67B       |

[igc-parla]: data/igc-parla/igc-parla.md
[igc-journals-22-10]: data/igc-journals-22-10/igc-journals-22-10.md
[igc-adjud]: data/igc-adjud/igc-adjud.md
[igc-law]: data/igc-law/igc-law.md
[saga]: data/saga/saga.md
[igc-social-blogs]: data/igc-social-blogs/igc-social-blogs.md
[igc-social-bland]: data/igc-social-bland/igc-social-bland.md
[igc-social-hugi]: data/igc-social-hugi/igc-social-hugi.md
[igc-social-malefnin]: data/igc-social-malefnin/igc-social-malefnin.md
[wikipedia]: data/wikipedia/wikipedia.md
[hjh-corpus]: data/hjh-corpus/hjh-corpus.md
[wiki-comments]: data/wiki-comments/wiki-comments.md
[wikisource]: data/wikisource/wikisource.md
[wikibooks]: data/wikibooks/wikibooks.md
[stjornartidindi]: data/stjornartidindi/stjornartidindi.md
[icepahc]: data/icepahc/icepahc.md
[gutenberg]: data/gutenberg/gutenberg.md
[rafbokavefur]: data/rafbokavefur/rafbokavefur.md
<!-- END-LICENSE TABLE -->

## Dataset Structure

The dataset contains text from different sources which are thoroughly defined in [Source Data](#source-data).

### Data Instances

Each entry in the dataset consists of a single text with associated metadata.

<!-- START-SAMPLE -->
```py
{
  "id": "igc-social-bland_2000_12.1",
  "text": "Það er það eina sem ég hafði alltaf svo miklar áhyggjur af en þurfti samt ekki.",
  "source": "igc-social-bland",
  "added": "2026-07-31",
  "created": "2000-12-01, 2000-12-31",
  "token_count": 36
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

These datasets were collected and curated with the intention of making openly licensed Icelandic data available. While this was collected with the intention of developing language models it is likely to have multiple other uses such as examining language development and differences across domains.

### Annotations

Synthetic metadata is stored as `data/{dataset}/metadata.parquet`. These
annotations were generated with [`ellamind/propella-1-4b`](https://huggingface.co/ellamind/propella-1-4b)
and include fields for content type, quality, safety, audience level,
educational level, PII presence, regional relevance and more.

The metadata rows include `dataset` and `id`, so a subset can be filtered and
joined with the corpus rows:

```py
from datasets import load_dataset

name = "danish-foundation-models/icelandic-dynaword"
texts = load_dataset(name, "igc-parla", split="train")
meta = load_dataset(name, "meta", split="train").filter(
    lambda row: row["dataset"] == "igc-parla"
)

texts_df = texts.to_pandas()
meta_df = meta.to_pandas()
igc_parla_with_meta = texts_df.merge(meta_df, on="id", how="left")
```

### Source Data

Below follows a brief overview of the sources in the corpus along with their individual license. To get more information about the individual dataset click the hyperlink in the table.

<details>
<summary><b>Overview Table (click to unfold)</b></summary>

<!-- START-MAIN TABLE -->
| Source                | Description                                                                                             | Domain       | N. Tokens   | License                   |
|:----------------------|:--------------------------------------------------------------------------------------------------------|:-------------|:------------|:--------------------------|
| [igc-social-bland]    | Sentences from [Bland.is](https://bland.is), a general-interest Icelandic online forum                  | Social Media | 898.73M     | [CC-BY 4.0]               |
| [igc-parla]           | Icelandic parliamentary speeches from Alþingi                                                           | Conversation | 706.13M     | [CC-BY 4.0]               |
| [igc-social-hugi]     | Sentences from [Hugi.is](https://hugi.is), an Icelandic online discussion forum                         | Social Media | 250.14M     | [CC-BY 4.0]               |
| [igc-adjud]           | Icelandic court adjudications                                                                           | Legal        | 225.53M     | [CC-BY 4.0]               |
| [igc-social-malefnin] | Sentences from [Málefnin.com](https://malefnin.com), an Icelandic discussion forum                      | Social Media | 185.32M     | [CC-BY 4.0]               |
| [igc-law]             | Icelandic proposals, parliamentary bills, and laws                                                      | Legal        | 163.02M     | [CC-BY 4.0]               |
| [stjornartidindi]     | Icelandic laws, regulations and international agreements as published in the official state gazette     | Legal        | 91.53M      | [Icelandic Copyright Law] |
| [igc-journals-22-10]  | Icelandic scholarly and scientific journal articles                                                     | Encyclopedic | 58.31M      | [CC-BY 4.0]               |
| [wikipedia]           | The Icelandic subsection of [wikipedia](https://wikipedia.org/)                                         | Encyclopedic | 36.16M      | [CC-BY-SA 4.0]            |
| [igc-social-blogs]    | Icelandic blog posts from three sites: Jónas.is, Silfur Egils, and Heimur.is                            | Social Media | 25.13M      | [CC-BY 4.0]               |
| [rafbokavefur]        | Out-of-copyright Icelandic books, from the medieval sagas to the early twentieth century                | Books        | 11.27M      | [Icelandic Copyright Law] |
| [wikisource]          | The Icelandic subsection of [Wikisource](https://wikisource.org), a library of transcribed source texts | Books        | 7.88M       | [CC-BY-SA 4.0]            |
| [saga]                | The Icelandic sagas                                                                                     | Books        | 3.65M       | [CC-BY 4.0]               |
| [icepahc]             | Icelandic prose spanning the 12th to the 21st century, sampled from dated editions                      | Books        | 2.11M       | [CC-BY 4.0]               |
| [wikibooks]           | The Icelandic subsection of [Wikibooks](https://www.wikibooks.org)                                      | Books        | 1.90M       | [CC-BY-SA 4.0]            |
| [wiki-comments]       | Community discussion and policy pages from the Icelandic Wikipedia                                      | Conversation | 1.02M       | [CC-BY-SA 4.0]            |
| [hjh-corpus]          | Radio broadcasts by Helgi J. Halldórsson on the Icelandic language                                      | Speeches     | 738.68K     | [CC-BY-SA 4.0]            |
| [gutenberg]           | The Icelandic subsection of [Project Gutenberg](https://www.gutenberg.org)                              | Books        | 227.43K     | [Gutenberg]               |
| **Total**             |                                                                                                         |              | 2.67B       |                           |

[igc-parla]: data/igc-parla/igc-parla.md
[igc-journals-22-10]: data/igc-journals-22-10/igc-journals-22-10.md
[igc-adjud]: data/igc-adjud/igc-adjud.md
[igc-law]: data/igc-law/igc-law.md
[saga]: data/saga/saga.md
[igc-social-blogs]: data/igc-social-blogs/igc-social-blogs.md
[igc-social-bland]: data/igc-social-bland/igc-social-bland.md
[igc-social-hugi]: data/igc-social-hugi/igc-social-hugi.md
[igc-social-malefnin]: data/igc-social-malefnin/igc-social-malefnin.md
[wikipedia]: data/wikipedia/wikipedia.md
[hjh-corpus]: data/hjh-corpus/hjh-corpus.md
[wiki-comments]: data/wiki-comments/wiki-comments.md
[wikisource]: data/wikisource/wikisource.md
[wikibooks]: data/wikibooks/wikibooks.md
[stjornartidindi]: data/stjornartidindi/stjornartidindi.md
[icepahc]: data/icepahc/icepahc.md
[gutenberg]: data/gutenberg/gutenberg.md
[rafbokavefur]: data/rafbokavefur/rafbokavefur.md


[CC-0]: https://creativecommons.org/publicdomain/zero/1.0/legalcode.en
[CC-BY-SA 4.0]: https://creativecommons.org/licenses/by-sa/4.0/deed.en
[CC-BY 4.0]: https://creativecommons.org/licenses/by/4.0/deed.en
[Apache 2.0]: https://www.apache.org/licenses/LICENSE-2.0
[Icelandic Copyright Law]: ./data/stjornartidindi/stjornartidindi.md#license-information
[Gutenberg]: ./data/gutenberg/gutenberg.md#license-information
[Icelandic Copyright Law]: ./data/rafbokavefur/rafbokavefur.md#license-information
<!-- END-MAIN TABLE -->

</details>

### Data Collection and Processing

This dynaword is continually developed, which means that the dataset will actively be updated as new datasets become available. This means that the size of Dynaword increases over time as seen in the following plot:

<p align="center">
<img src="./images/tokens_over_time.svg" width="600" style="margin-right: 10px;" />
</p>

The data collection and processing varies depending on the dataset and is documentationed the individual datasheets, which is linked in the above table. If possible the collection is documented both in the datasheet and in the reproducible script (`data/{dataset}/create.py`).

In addition to data specific processing we also run a series automated quality checks to ensure formatting (e.g. ensuring correctly formatted columns and unique IDs), quality checks (e.g. duplicate and empty string detection) and datasheet documentation checks. These checks are there to ensure a high quality of documentation and a minimal level of quality. To allow for the development of novel cleaning methodologies we do not provide more extensive cleaning.

### Dataset Statistics

The following plot(s) are intended to give an overview of docuements length in the various sources. 

<p align="center">
<img src="./images/dataset_size_plot.svg" width="600" style="margin-right: 10px;" />
</p>

### Contributing to the dataset

We welcome contributions to the dataset, including new sources, improved data filtering, and other enhancements. To get started on contributing, please see [the contribution guidelines](CONTRIBUTING.md)

## Citation Information

If you use this work, please cite the [scientific article](https://arxiv.org/abs/2508.02271) introducing the Dynaword approach and with the [Icelandic Gigaword Corpus](https://igc.arnastofnun.is) which provides large parts of the datasets:

> Enevoldsen, K.C., Jensen, K.N., Kostkan, J., Szab'o, B.I., Kardos, M., Vad, K., Heinsen, J., N'unez, A.B., Barmina, G., Nielsen, J., Larsen, R., Vahlstrup, P.B., Dalum, P.M., Elliott, D., Galke, L., Schneider-Kamp, P., & Nielbo, K.L. (2025). Dynaword: From One-shot to Continuously Developed Datasets.
>
> Barkarson, Starka{\dh}ur, Steingr{\'i}msson, Stein{\th}{\'o}r, & Hafsteinsd{\'o}ttir, Hildur (2022). Evolving Large Text Corpora: Four Versions of the Icelandic Gigaword Corpus.

```bibtex
@article{enevoldsen2025dynaword,
  title={Dynaword: From One-shot to Continuously Developed Datasets},
  author={Enevoldsen, Kenneth and Jensen, Kristian N{\o}rgaard and Kostkan, Jan and Szab{\'o}, Bal{\'a}zs and Kardos, M{\'a}rton and Vad, Kirten and N{\'u}{\~n}ez, Andrea Blasi and Barmina, Gianluca and Nielsen, Jacob and Larsen, Rasmus and others},
  journal={arXiv preprint arXiv:2508.02271},
  year={2025}
}

@inproceedings{barkarson2022igc,
  title={Evolving Large Text Corpora: Four Versions of the Icelandic Gigaword Corpus},
  author={Barkarson, Starka{\dh}ur and Steingr{\'\i}msson, Stein{\th}{\'o}r and Hafsteinsd{\'o}ttir, Hildur},
  booktitle={Proceedings of the Language Resources and Evaluation Conference},
  pages={2371--2381},
  year={2022}
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

We redistribute files shared with us under a license permitting such redistribution. If you have concerns about the licensing of these files, please [contact us](https://huggingface.co/datasets/danish-foundation-models/icelandic-dynaword/discussions/new). If you consider that the data contains material that infringe your copyright, please:

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

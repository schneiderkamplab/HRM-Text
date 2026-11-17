---
annotations_creators:
- machine-generated
language_creators:
- crowdsourced
language:
- da
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
pretty_name: Danish Dynaword
configs:
- config_name: default
  data_files:
  - split: train
    path: data/*/data.parquet
- config_name: meta
  data_files:
  - split: train
    path: data/*/metadata.parquet
language_bcp47:
- da
- da-bornholm
- da-synnejyl
---

<!-- 
readme structure is inspired by:
https://github.com/huggingface/datasets/blob/main/templates/README_guide.md 
-->


# 🧨 Dynaword Staging/Sandbox

This is a staging/sandbox repository based on the Danish Dynaword. It is used for testing purposes only.

<!-- START README TABLE -->
|              |                                                                                                                                                             |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Version** | 1.2.20 ([Changelog](/CHANGELOG.md)) |
| **Language** | dan, dansk, Danish                                                                                                                                          |
| **License**  | Openly Licensed, See the respective dataset                                                                                                                 |
| **Models**   | For model trained used this data see [danish-foundation-models](https://huggingface.co/danish-foundation-models)                                            |
| **Contact**  | If you have question about this project please create an issue [here](https://huggingface.co/datasets/danish-foundation-models/danish-dynaword/discussions) |



<!-- END README TABLE -->

## Table of Contents
- [🧨 Danish Dynaword](#-danish-dynaword)
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
- **Number of samples**: 300
- **Number of tokens (Llama 3)**: 1.03M
- **Average document length in tokens (min, max)**: 3.43K (13, 180.71K)
<!-- END-DESC-STATS -->


### Dataset Summary

The Danish dynaword is a collection of Danish free-form text datasets from various domains. All of the datasets in Danish Dynaword are openly licensed 
and deemed permissible for training large language models. 

Danish Dynaword is continually developed, which means that the dataset will actively be updated as new datasets become available. If you would like to contribute a dataset see the [contribute section](#contributing-to-the-dataset).

### Loading the dataset

```py
from datasets import load_dataset

name = "danish-foundation-models/danish-dynaword"
ds = load_dataset(name, split = "train")
sample = ds[1] # see "Data Instances" below
```

or load it by streaming the data
```py
ds = load_dataset(name, split = "train", streaming=True)
dataset_iter = iter(ds)
sample = next(iter(dataset_iter))
```

You can also load a single subset at a time:
```py
ds = load_dataset(name, "adl", split = "train")
```

To allow filtering we additionally provide extensive [annotations](#annotations)
available through the `meta` config:

```py
meta = load_dataset(name, "meta", split = "train")
```

For more on how to use the annotations see [the annotations section](#annotations).


As Danish Dynaword is continually expanding and curated you can make sure that you get the same dataset every time by specifying the revision:
You can also load a single subset at a time:
```py
ds = load_dataset(name, revision="{desired revision}")
```

### Languages
This dataset includes the following languages:

- Danish (dan-Latn) as we as the dialects Bornholmsk (dan-Latn-bornholm) and Synderjysk (dan-Latn-synnejyl)

In addition it likely contains small amounts of English due to code-switching and Norwegian due to the historical relation between the two languages and language misclassificaitons due to their similarity.

Language is denoted using [BCP-47](https://en.wikipedia.org/wiki/IETF_language_tag), using the langauge code ISO 639-3 and the script code ISO 15924. The third element denote the region variant.


### Domains

This dynaword consist of data from various domains (e.g., legal, books, social media). The following table and figure give an overview of the relative distributions of these domains. To see a full overview of the source check out the [source data section](#source-data)

<div style="display: flex; gap: 20px; align-items: flex-start;">

<div style="flex: 1;">


<!-- START-DOMAIN TABLE -->
| Domain       | Sources                   | N. Tokens   |
|:-------------|:--------------------------|:------------|
| Encyclopedic | [wikisource], [wikipedia] | 943.60K     |
| Books        | [wikibooks]               | 85.50K      |
| **Total**    |                           | 1.03M       |

[wikisource]: data/wikisource/wikisource.md
[wikibooks]: data/wikibooks/wikibooks.md
[wikipedia]: data/wikipedia/wikipedia.md
<!-- END-DOMAIN TABLE -->

</div>

<div style="flex: 1;">

<p align="center">
<img src="./images/domain_distribution.png" width="400" style="margin-right: 10px;" />
</p>

</div>

</div>


### Licensing

The following gives an overview of the licensing in the Dynaword. To get the exact license of the individual datasets check out the [overview table](#source-data).
These license is applied to the constituent data, i.e., the text. The collection of datasets (metadata, quality control, etc.) is licensed under [CC-0](https://creativecommons.org/publicdomain/zero/1.0/legalcode.en).

<!-- START-LICENSE TABLE -->
| License      | Sources                                | N. Tokens   |
|:-------------|:---------------------------------------|:------------|
| CC-BY-SA 4.0 | [wikisource], [wikibooks], [wikipedia] | 1.03M       |
| **Total**    |                                        | 1.03M       |

[wikisource]: data/wikisource/wikisource.md
[wikibooks]: data/wikibooks/wikibooks.md
[wikipedia]: data/wikipedia/wikipedia.md
<!-- END-LICENSE TABLE -->



## Dataset Structure

The dataset contains text from different sources which are thoroughly defined in [Source Data](#source-data).

### Data Instances

Each entry in the dataset consists of a single text with associated metadata

<!-- START-SAMPLE -->
```py
{
  "id": "wiki_2",
  "text": "Arkæologi\nArkæologi er studiet af tidligere tiders menneskelige aktivitet, primært gennem studiet af[...]",
  "source": "wiki",
  "added": "2025-08-18",
  "created": "2024-06-16, 2024-06-16",
  "token_count": 3380
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

These datasets were collected and curated with the intention of making openly license Danish data available. While this was collected with the intention of developing language models it is likely to have multiple other uses such as examining language development and differences across domains.



### Annotations

Synthetic metadata is stored as `data/{dataset}/metadata.parquet`. These
annotations were generated with [`ellamind/propella-1-4b`](https://huggingface.co/ellamind/propella-1-4b)
and include fields for content type, quality, safety, audience level,
educational level, PII presence, regional relevance and more.

The metadata rows include `dataset` and `id`, so a subset can be filtered and
joined with the corpus rows:

```py
from datasets import load_dataset

name = "danish-foundation-models/danish-dynaword"
texts = load_dataset(name, "adl", split="train")
meta = load_dataset(name, "meta", split="train").filter(
    lambda row: row["dataset"] == "adl"
)

texts_df = texts.to_pandas()
meta_df = meta.to_pandas()
adl_with_meta = texts_df.merge(meta_df, on="id", how="left")
```


### Source Data


Below follows a brief overview of the sources in the corpus along with their individual license. To get more information about the individual dataset click the hyperlink in the table.

<details>
<summary><b>Overview Table (click to unfold)</b></summary>

You can learn more about each dataset by pressing the link in the first column.

<!-- START-MAIN TABLE -->
| Source       | Description                                                                     | Domain       | N. Tokens   | License        |
|:-------------|:--------------------------------------------------------------------------------|:-------------|:------------|:---------------|
| [wikisource] | The Danish subsection of [Wikisource](https://en.wikisource.org/wiki/Main_Page) | Encyclopedic | 687.84K     | [CC-BY-SA 4.0] |
| [wikipedia]  | The Danish subsection of [wikipedia](https://en.wikipedia.org/wiki/Main_Page)   | Encyclopedic | 255.76K     | [CC-BY-SA 4.0] |
| [wikibooks]  | The Danish Subsection of [Wikibooks](https://www.wikibooks.org)                 | Books        | 85.50K      | [CC-BY-SA 4.0] |
| **Total**    |                                                                                 |              | 1.03M       |                |

[wikisource]: data/wikisource/wikisource.md
[wikibooks]: data/wikibooks/wikibooks.md
[wikipedia]: data/wikipedia/wikipedia.md


[CC-0]: https://creativecommons.org/publicdomain/zero/1.0/legalcode.en
[CC-BY-SA 4.0]: https://creativecommons.org/licenses/by-sa/4.0/deed.en
[CC-BY 4.0]: https://creativecommons.org/licenses/by/4.0/deed.en
[Apache 2.0]: https://www.apache.org/licenses/LICENSE-2.0
<!-- END-MAIN TABLE -->

</details>


### Data Collection and Processing

Danish Dynaword is continually developed, which means that the dataset will actively be updated as new datasets become available. This means that the size of Dynaword increases over time as seen in the following plot:

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

If you use this work, please cite the [scientific article](https://arxiv.org/abs/2508.02271), we recommend citing the following:

> Enevoldsen, K.C., Jensen, K.N., Kostkan, J., Szab'o, B.I., Kardos, M., Vad, K., Heinsen, J., N'unez, A.B., Barmina, G., Nielsen, J., Larsen, R., Vahlstrup, P.B., Dalum, P.M., Elliott, D., Galke, L., Schneider-Kamp, P., & Nielbo, K.L. (2025). Dynaword: From One-shot to Continuously Developed Datasets.


```
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

As far as we are aware the dataset does not contain information identifying sexual orientation, political beliefs, religion, or health connected with utterer ID. In case that such information is present in the data we have been removed utterer information from social media content.

### Bias, Risks, and Limitations

Certain works in this collection are historical works and thus reflect the linguistic, cultural, and ideological norms of their time.
As such, it includes perspectives, assumptions, and biases characteristic of the period. For instance, the works of N.F.S. Grundtvig (`grundtvig`) were known to nationalistic views and critical stances toward specific groups, such as Germans, which may be considered offensive or exclusionary by contemporary standards.


### Notice and takedown policy
We redistribute files shared with us under a license permitting such redistribution. If you have concerns about the licensing of these files, please [contact us](https://huggingface.co/datasets/danish-foundation-models/danish-dynaword/discussions/new). If you consider that the data contains material that infringe your copyright, please:
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
  A&nbsp;<a href=https://www.foundationmodels.dk>Danish Foundation Models</a>&nbsp;dataset
</h3>

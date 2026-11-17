---
annotations_creators:
- machine-generated
language_creators:
- crowdsourced
language:
- nl
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
pretty_name: Dutch Dynaword
configs:
- config_name: default
  data_files:
  - split: train
    path: data/*/data.parquet
- config_name: meta
  data_files:
  - split: train
    path: data/*/metadata.parquet
- config_name: auditdienstrijk
  data_files:
  - split: train
    path: data/auditdienstrijk/data.parquet
- config_name: pbl
  data_files:
  - split: train
    path: data/pbl/data.parquet
- config_name: naturalis
  data_files:
  - split: train
    path: data/naturalis/data.parquet
- config_name: european_parliament
  data_files:
  - split: train
    path: data/european_parliament/data.parquet
- config_name: zeeuws_archief
  data_files:
  - split: train
    path: data/zeeuws_archief/data.parquet
- config_name: noord_hollands_archief
  data_files:
  - split: train
    path: data/noord_hollands_archief/data.parquet
- config_name: utrechts_archief
  data_files:
  - split: train
    path: data/utrechts_archief/data.parquet
- config_name: dans_knaw
  data_files:
  - split: train
    path: data/dans_knaw/data.parquet
- config_name: wikiwijs
  data_files:
  - split: train
    path: data/wikiwijs/data.parquet
- config_name: c5_filtered
  data_files:
  - split: train
    path: data/c5_filtered/data.parquet
- config_name: eurlex
  data_files:
  - split: train
    path: data/eurlex/data.parquet
- config_name: dienst_publiek_en_communicatie
  data_files:
  - split: train
    path: data/dienst_publiek_en_communicatie/data.parquet
- config_name: belgian_journal
  data_files:
  - split: train
    path: data/belgian_journal/data.parquet
- config_name: nationaal_archief
  data_files:
  - split: train
    path: data/nationaal_archief/data.parquet
- config_name: tweede_kamer
  data_files:
  - split: train
    path: data/tweede_kamer/data.parquet
- config_name: de_rechtspraak
  data_files:
  - split: train
    path: data/de_rechtspraak/data.parquet
- config_name: koninklijke_bibliotheek
  data_files:
  - split: train
    path: data/koninklijke_bibliotheek/data.parquet
- config_name: officiele_bekendmakingen
  data_files:
  - split: train
    path: data/officiele_bekendmakingen/data.parquet
- config_name: woogle
  data_files:
  - split: train
    path: data/woogle/data.parquet
- config_name: openraadsinformatie
  data_files:
  - split: train
    path: data/openraadsinformatie/data.parquet
---

<!-- 
readme structure is inspired by:
https://github.com/huggingface/datasets/blob/main/templates/README_guide.md 
-->


# 🧨 Dutch Dynaword


<!-- START README TABLE -->
|              |                                                                                                                                                             |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Version** | 1.0.1 ([Changelog](/CHANGELOG.md)) |
| **Language** | nld, Nederlands, Dutch                                                                                                                                          |
| **License**  | Openly Licensed, See the respective dataset                                                                                                                 |
| **Models**   | For model trained used this data see [danish-foundation-models](https://huggingface.co/danish-foundation-models)                                            |
| **Contact**  | If you have question about this project please create an issue [here](https://huggingface.co/datasets/danish-foundation-models/dutch-dynaword/discussions) |



<!-- END README TABLE -->

## Table of Contents
- [🧨 Dutch Dynaword](#-dutch-dynaword)
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
- **Number of samples**: 14.45M
- **Number of tokens (Llama 3)**: 37.89B
- **Average document length in tokens (min, max)**: 2.62K (2, 5.45M)
<!-- END-DESC-STATS -->


### Dataset Summary

The Dutch dynaword is a collection of Dutch free-form text datasets from various domains. All of the datasets in Dutch Dynaword are openly licensed 
and deemed permissible for training large language models. 

Dutch Dynaword is continually developed, which means that the dataset will actively be updated as new datasets become available. If you would like to contribute a dataset see the [contribute section](#contributing-to-the-dataset).

### Loading the dataset

```py
from datasets import load_dataset

name = "danish-foundation-models/dutch-dynaword"
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
ds = load_dataset(name, "auditdienstrijk", split = "train")
```

To allow filtering we additionally provide extensive [annotations](#annotations)
available through the `meta` config:

```py
meta = load_dataset(name, "meta", split = "train")
```

For more on how to use the annotations see [the annotations section](#annotations).


As Dutch Dynaword is continually expanding and curated you can make sure that you get the same dataset every time by specifying the revision:
You can also load a single subset at a time:
```py
ds = load_dataset(name, revision="{desired revision}")
```

### Languages
This dataset includes the following languages:

- Dutch (nld-Latn)

In addition it likely contains small amounts of English due to code-switching.

Language is denoted using [BCP-47](https://en.wikipedia.org/wiki/IETF_language_tag), using the langauge code ISO 639-3 and the script code ISO 15924. The third element denote the region variant.


### Domains

This dynaword consist of data from various domains (e.g., legal, books, social media). The following table and figure give an overview of the relative distributions of these domains. To see a full overview of the source check out the [source data section](#source-data)

<div style="display: flex; gap: 20px; align-items: flex-start;">

<div style="flex: 1;">


<!-- START-DOMAIN TABLE -->
| Domain       | Sources                                                                                                                                                                                                                  | N. Tokens   |
|:-------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------|
| Legal        | [auditdienstrijk], [zeeuws_archief], [noord_hollands_archief], [utrechts_archief], [eurlex], [belgian_journal], [nationaal_archief], [tweede_kamer], [de_rechtspraak], [officiele_bekendmakingen], [openraadsinformatie] | 30.69B      |
| Other        | [pbl], [naturalis], [dans_knaw], [wikiwijs], [woogle]                                                                                                                                                                    | 3.83B       |
| News         | [koninklijke_bibliotheek]                                                                                                                                                                                                | 3.14B       |
| Web          | [c5_filtered], [dienst_publiek_en_communicatie]                                                                                                                                                                          | 155.10M     |
| Conversation | [european_parliament]                                                                                                                                                                                                    | 71.13M      |
| **Total**    |                                                                                                                                                                                                                          | 37.89B      |

[auditdienstrijk]: data/auditdienstrijk/auditdienstrijk.md
[pbl]: data/pbl/pbl.md
[naturalis]: data/naturalis/naturalis.md
[european_parliament]: data/european_parliament/european_parliament.md
[zeeuws_archief]: data/zeeuws_archief/zeeuws_archief.md
[noord_hollands_archief]: data/noord_hollands_archief/noord_hollands_archief.md
[utrechts_archief]: data/utrechts_archief/utrechts_archief.md
[dans_knaw]: data/dans_knaw/dans_knaw.md
[wikiwijs]: data/wikiwijs/wikiwijs.md
[c5_filtered]: data/c5_filtered/c5_filtered.md
[eurlex]: data/eurlex/eurlex.md
[dienst_publiek_en_communicatie]: data/dienst_publiek_en_communicatie/dienst_publiek_en_communicatie.md
[belgian_journal]: data/belgian_journal/belgian_journal.md
[nationaal_archief]: data/nationaal_archief/nationaal_archief.md
[tweede_kamer]: data/tweede_kamer/tweede_kamer.md
[de_rechtspraak]: data/de_rechtspraak/de_rechtspraak.md
[koninklijke_bibliotheek]: data/koninklijke_bibliotheek/koninklijke_bibliotheek.md
[officiele_bekendmakingen]: data/officiele_bekendmakingen/officiele_bekendmakingen.md
[woogle]: data/woogle/woogle.md
[openraadsinformatie]: data/openraadsinformatie/openraadsinformatie.md
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
Each document in Dutch Dynaword comes with annotations describing its content, such as content quality, information density, and educational value.
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
| License   | Sources                                                                                                                                                                                                                                                                                            | N. Tokens   |
|:----------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------|
| CC-0      | [auditdienstrijk], [zeeuws_archief], [noord_hollands_archief], [utrechts_archief], [dans_knaw], [dienst_publiek_en_communicatie], [belgian_journal], [nationaal_archief], [tweede_kamer], [de_rechtspraak], [koninklijke_bibliotheek], [officiele_bekendmakingen], [woogle], [openraadsinformatie] | 37.57B      |
| CC-BY 4.0 | [pbl], [naturalis], [european_parliament], [wikiwijs], [c5_filtered], [eurlex]                                                                                                                                                                                                                     | 315.87M     |
| **Total** |                                                                                                                                                                                                                                                                                                    | 37.89B      |

[auditdienstrijk]: data/auditdienstrijk/auditdienstrijk.md
[pbl]: data/pbl/pbl.md
[naturalis]: data/naturalis/naturalis.md
[european_parliament]: data/european_parliament/european_parliament.md
[zeeuws_archief]: data/zeeuws_archief/zeeuws_archief.md
[noord_hollands_archief]: data/noord_hollands_archief/noord_hollands_archief.md
[utrechts_archief]: data/utrechts_archief/utrechts_archief.md
[dans_knaw]: data/dans_knaw/dans_knaw.md
[wikiwijs]: data/wikiwijs/wikiwijs.md
[c5_filtered]: data/c5_filtered/c5_filtered.md
[eurlex]: data/eurlex/eurlex.md
[dienst_publiek_en_communicatie]: data/dienst_publiek_en_communicatie/dienst_publiek_en_communicatie.md
[belgian_journal]: data/belgian_journal/belgian_journal.md
[nationaal_archief]: data/nationaal_archief/nationaal_archief.md
[tweede_kamer]: data/tweede_kamer/tweede_kamer.md
[de_rechtspraak]: data/de_rechtspraak/de_rechtspraak.md
[koninklijke_bibliotheek]: data/koninklijke_bibliotheek/koninklijke_bibliotheek.md
[officiele_bekendmakingen]: data/officiele_bekendmakingen/officiele_bekendmakingen.md
[woogle]: data/woogle/woogle.md
[openraadsinformatie]: data/openraadsinformatie/openraadsinformatie.md
<!-- END-LICENSE TABLE -->



## Dataset Structure

The dataset contains text from different sources which are thoroughly defined in [Source Data](#source-data).

### Data Instances

Each entry in the dataset consists of a single text with associated metadata

<!-- START-SAMPLE -->
```py
{
  "id": "dienst_publiek_en_communicatie_0",
  "text": "Wet- en regelgeving\nOm te voorkomen dat vervalste medicijnen in de legale distributieketen terechtko[...]",
  "source": "dienst_publiek_en_communicatie",
  "added": "2026-09-07",
  "created": "2010-01-01, 2025-12-31",
  "token_count": 208
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

These datasets were collected and curated with the intention of making openly licensed Dutch data available. While this was collected with the intention of developing language models it is likely to have multiple other uses such as examining language development and differences across domains.



### Annotations

Synthetic metadata is stored as `data/{dataset}/metadata.parquet`. These
annotations were generated with [`ellamind/propella-1-4b`](https://huggingface.co/ellamind/propella-1-4b)
and include fields for content type, quality, safety, audience level,
educational level, PII presence, regional relevance and more.

The metadata rows include `dataset` and `id`, so a subset can be filtered and
joined with the corpus rows:

```py
from datasets import load_dataset

name = "danish-foundation-models/dutch-dynaword"
texts = load_dataset(name, "auditdienstrijk", split="train")
meta = load_dataset(name, "meta", split="train").filter(
    lambda row: row["dataset"] == "auditdienstrijk"
)

texts_df = texts.to_pandas()
meta_df = meta.to_pandas()
adr_with_meta = texts_df.merge(meta_df, on="id", how="left")
```


### Source Data


Below follows a brief overview of the sources in the corpus along with their individual license. To get more information about the individual dataset click the hyperlink in the table.

<details>
<summary><b>Overview Table (click to unfold)</b></summary>

You can learn more about each dataset by pressing the link in the first column.

<!-- START-MAIN TABLE -->
| Source                           | Description                                                                                                                                                          | Domain       | N. Tokens   | License     |
|:---------------------------------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------|:-------------|:------------|:------------|
| [openraadsinformatie]            | Municipal and provincial council documents from [Open Raadsinformatie](https://www.openraadsinformatie.nl/)                                                          | Legal        | 19.08B      | [CC-0]      |
| [officiele_bekendmakingen]       | Dutch parliamentary proceedings and government announcements from [officielebekendmakingen.nl](https://www.officielebekendmakingen.nl)                               | Legal        | 3.88B       | [CC-0]      |
| [woogle]                         | Dutch government documents disclosed under freedom-of-information law, from [Woogle](https://wooverheid.nl/)                                                         | Other        | 3.73B       | [CC-0]      |
| [de_rechtspraak]                 | Dutch court judgments published by [De Rechtspraak](https://www.rechtspraak.nl/)                                                                                     | Legal        | 3.19B       | [CC-0]      |
| [koninklijke_bibliotheek]        | Public domain newspapers and books from the [Koninklijke Bibliotheek](https://www.kb.nl/), the Dutch national library                                                | News         | 3.14B       | [CC-0]      |
| [tweede_kamer]                   | Documents of the Dutch House of Representatives from [opendata.tweedekamer.nl](https://opendata.tweedekamer.nl/)                                                     | Legal        | 1.77B       | [CC-0]      |
| [nationaal_archief]              | Digitised records from the [Nationaal Archief](https://www.nationaalarchief.nl/), the national archive of the Netherlands                                            | Legal        | 1.29B       | [CC-0]      |
| [belgian_journal]                | Company and association filings from the Dutch-language annexes of the [Belgisch Staatsblad](https://www.ejustice.just.fgov.be/)                                     | Legal        | 1.02B       | [CC-0]      |
| [utrechts_archief]               | Digitised archival records from [Het Utrechts Archief](https://hetutrechtsarchief.nl/onderzoek/collecties), the regional archive of the city and province of Utrecht | Legal        | 252.50M     | [CC-0]      |
| [eurlex]                         | Dutch versions of European Union legislation from [MultiEURLEX](https://huggingface.co/datasets/coastalcph/multi_eurlex)                                             | Legal        | 124.03M     | [CC-BY 4.0] |
| [dienst_publiek_en_communicatie] | Dutch government website content collected by the [Dienst Publiek en Communicatie](https://www.rijksoverheid.nl/)                                                    | Web          | 107.60M     | [CC-0]      |
| [european_parliament]            | Dutch verbatim reports of [European Parliament](https://www.europarl.europa.eu/plenary/nl/minutes.html) plenary sittings                                             | Conversation | 71.13M      | [CC-BY 4.0] |
| [zeeuws_archief]                 | Digitised municipal records from the [Zeeuws Archief](https://zeeuwsarchief.nl/), the regional archive of the Dutch province of Zeeland                              | Legal        | 47.85M      | [CC-0]      |
| [c5_filtered]                    | Creative Commons licensed Dutch web pages from [C5](https://huggingface.co/datasets/BramVanroy/CommonCrawl-CreativeCommons)                                          | Web          | 47.49M      | [CC-BY 4.0] |
| [wikiwijs]                       | Open educational material shared by teachers on [Wikiwijs](https://www.wikiwijs.nl/)                                                                                 | Other        | 34.38M      | [CC-BY 4.0] |
| [dans_knaw]                      | Research dataset descriptions from [DANS](https://dans.knaw.nl/), the Dutch national centre of expertise for research data                                           | Other        | 30.73M      | [CC-0]      |
| [noord_hollands_archief]         | Digitised administrative records from the [Noord-Hollands Archief](https://noord-hollandsarchief.nl/), the regional archive of the province of North Holland         | Legal        | 29.92M      | [CC-0]      |
| [naturalis]                      | Biological and taxonomic publications from the [Naturalis Biodiversity Center](https://repository.naturalis.nl) repository                                           | Other        | 20.05M      | [CC-BY 4.0] |
| [pbl]                            | Policy research reports from the [Planbureau voor de Leefomgeving](https://www.pbl.nl/publicaties/)                                                                  | Other        | 18.77M      | [CC-BY 4.0] |
| [auditdienstrijk]                | Audit reports from the [Auditdienst Rijk](https://www.auditdienstrijk.nl/)                                                                                           | Legal        | 7.16M       | [CC-0]      |
| **Total**                        |                                                                                                                                                                      |              | 37.89B      |             |

[auditdienstrijk]: data/auditdienstrijk/auditdienstrijk.md
[pbl]: data/pbl/pbl.md
[naturalis]: data/naturalis/naturalis.md
[european_parliament]: data/european_parliament/european_parliament.md
[zeeuws_archief]: data/zeeuws_archief/zeeuws_archief.md
[noord_hollands_archief]: data/noord_hollands_archief/noord_hollands_archief.md
[utrechts_archief]: data/utrechts_archief/utrechts_archief.md
[dans_knaw]: data/dans_knaw/dans_knaw.md
[wikiwijs]: data/wikiwijs/wikiwijs.md
[c5_filtered]: data/c5_filtered/c5_filtered.md
[eurlex]: data/eurlex/eurlex.md
[dienst_publiek_en_communicatie]: data/dienst_publiek_en_communicatie/dienst_publiek_en_communicatie.md
[belgian_journal]: data/belgian_journal/belgian_journal.md
[nationaal_archief]: data/nationaal_archief/nationaal_archief.md
[tweede_kamer]: data/tweede_kamer/tweede_kamer.md
[de_rechtspraak]: data/de_rechtspraak/de_rechtspraak.md
[koninklijke_bibliotheek]: data/koninklijke_bibliotheek/koninklijke_bibliotheek.md
[officiele_bekendmakingen]: data/officiele_bekendmakingen/officiele_bekendmakingen.md
[woogle]: data/woogle/woogle.md
[openraadsinformatie]: data/openraadsinformatie/openraadsinformatie.md


[CC-0]: https://creativecommons.org/publicdomain/zero/1.0/legalcode.en
[CC-BY-SA 4.0]: https://creativecommons.org/licenses/by-sa/4.0/deed.en
[CC-BY 4.0]: https://creativecommons.org/licenses/by/4.0/deed.en
[Apache 2.0]: https://www.apache.org/licenses/LICENSE-2.0
<!-- END-MAIN TABLE -->

</details>


### Data Collection and Processing

Dutch Dynaword is continually developed, which means that the dataset will actively be updated as new datasets become available. This means that the size of Dynaword increases over time as seen in the following plot:

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
As such, it includes perspectives, assumptions, and biases characteristic of the period.


### Notice and takedown policy
We redistribute files shared with us under a license permitting such redistribution. If you have concerns about the licensing of these files, please [contact us](https://huggingface.co/datasets/danish-foundation-models/dutch-dynaword/discussions/new). If you consider that the data contains material that infringe your copyright, please:
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

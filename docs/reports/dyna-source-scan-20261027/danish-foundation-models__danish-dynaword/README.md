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
- config_name: ai-aktindsigt
  data_files:
  - split: train
    path: data/ai-aktindsigt/data.parquet
- config_name: cellar
  data_files:
  - split: train
    path: data/cellar/data.parquet
- config_name: comparia
  data_files:
  - split: train
    path: data/comparia/data.parquet
- config_name: enevaeldens_nyheder
  data_files:
  - split: train
    path: data/enevaeldens_nyheder/data.parquet
- config_name: grundtvig
  data_files:
  - split: train
    path: data/grundtvig/data.parquet
- config_name: danske-taler
  data_files:
  - split: train
    path: data/danske-taler/data.parquet
- config_name: ncc_books
  data_files:
  - split: train
    path: data/ncc_books/data.parquet
- config_name: ncc_newspaper
  data_files:
  - split: train
    path: data/ncc_newspaper/data.parquet
- config_name: ncc_maalfrid
  data_files:
  - split: train
    path: data/ncc_maalfrid/data.parquet
- config_name: ncc_parliament
  data_files:
  - split: train
    path: data/ncc_parliament/data.parquet
- config_name: eur-lex-sum-da
  data_files:
  - split: train
    path: data/eur-lex-sum-da/data.parquet
- config_name: miljoeportalen
  data_files:
  - split: train
    path: data/miljoeportalen/data.parquet
- config_name: fm-udgivelser
  data_files:
  - split: train
    path: data/fm-udgivelser/data.parquet
- config_name: memo
  data_files:
  - split: train
    path: data/memo/data.parquet
- config_name: opensubtitles
  data_files:
  - split: train
    path: data/opensubtitles/data.parquet
- config_name: retsinformationdk
  data_files:
  - split: train
    path: data/retsinformationdk/data.parquet
- config_name: ep
  data_files:
  - split: train
    path: data/ep/data.parquet
- config_name: ft
  data_files:
  - split: train
    path: data/ft/data.parquet
- config_name: wikisource
  data_files:
  - split: train
    path: data/wikisource/data.parquet
- config_name: spont
  data_files:
  - split: train
    path: data/spont/data.parquet
- config_name: tv2r
  data_files:
  - split: train
    path: data/tv2r/data.parquet
- config_name: adl
  data_files:
  - split: train
    path: data/adl/data.parquet
- config_name: hest
  data_files:
  - split: train
    path: data/hest/data.parquet
- config_name: skat
  data_files:
  - split: train
    path: data/skat/data.parquet
- config_name: dannet
  data_files:
  - split: train
    path: data/dannet/data.parquet
- config_name: retspraksis
  data_files:
  - split: train
    path: data/retspraksis/data.parquet
- config_name: wikibooks
  data_files:
  - split: train
    path: data/wikibooks/data.parquet
- config_name: jvj
  data_files:
  - split: train
    path: data/jvj/data.parquet
- config_name: gutenberg
  data_files:
  - split: train
    path: data/gutenberg/data.parquet
- config_name: botxt
  data_files:
  - split: train
    path: data/botxt/data.parquet
- config_name: depbank
  data_files:
  - split: train
    path: data/depbank/data.parquet
- config_name: naat
  data_files:
  - split: train
    path: data/naat/data.parquet
- config_name: synne
  data_files:
  - split: train
    path: data/synne/data.parquet
- config_name: wikipedia
  data_files:
  - split: train
    path: data/wikipedia/data.parquet
- config_name: wiki-comments
  data_files:
  - split: train
    path: data/wiki-comments/data.parquet
- config_name: nordjyllandnews
  data_files:
  - split: train
    path: data/nordjyllandnews/data.parquet
- config_name: relig
  data_files:
  - split: train
    path: data/relig/data.parquet
- config_name: nota
  data_files:
  - split: train
    path: data/nota/data.parquet
- config_name: health_hovedstaden
  data_files:
  - split: train
    path: data/health_hovedstaden/data.parquet
- config_name: domsdatabasen
  data_files:
  - split: train
    path: data/domsdatabasen/data.parquet
- config_name: historical-danish-handwriting
  data_files:
  - split: train
    path: data/historical-danish-handwriting/data.parquet
- config_name: kb_administrative_publication
  data_files:
  - split: train
    path: data/kb_administrative_publication/data.parquet
- config_name: kb_historical_letters
  data_files:
  - split: train
    path: data/kb_historical_letters/data.parquet
- config_name: trykkefrihedens_skrifter
  data_files:
  - split: train
    path: data/trykkefrihedens_skrifter/data.parquet
- config_name: municipality_meetings
  data_files:
  - split: train
    path: data/municipality_meetings/data.parquet
- config_name: hvadvilduhelst
  data_files:
  - split: train
    path: data/hvadvilduhelst/data.parquet
- config_name: tidsskrift-dk
  data_files:
  - split: train
    path: data/tidsskrift-dk/data.parquet
- config_name: dakultur
  data_files:
  - split: train
    path: data/dakultur/data.parquet
- config_name: mosel_voxpopuli
  data_files:
  - split: train
    path: data/mosel_voxpopuli/data.parquet
- config_name: mosel_youtubecommons
  data_files:
  - split: train
    path: data/mosel_youtubecommons/data.parquet
- config_name: folketingets-dokumenter
  data_files:
  - split: train
    path: data/folketingets-dokumenter/data.parquet
- config_name: kalliope
  data_files:
  - split: train
    path: data/kalliope/data.parquet
- config_name: logir
  data_files:
  - split: train
    path: data/logir/data.parquet
language_bcp47:
- da
- da-bornholm
- da-synnejyl
---

<!-- 
readme structure is inspired by:
https://github.com/huggingface/datasets/blob/main/templates/README_guide.md 
-->


# 🧨 Danish Dynaword


<!-- START README TABLE -->
|              |                                                                                                                                                             |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Version** | 1.2.30 ([Changelog](/CHANGELOG.md)) |
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
    - [Annotation Overview](#annotation-overview)
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
- **Number of samples**: 8.02M
- **Number of tokens (Llama 3)**: 14.85B
- **Average document length in tokens (min, max)**: 1.85K (2, 19.46M)
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
| Domain       | Sources                                                                                                                                                                     | N. Tokens   |
|:-------------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------|
| Legal        | [cellar], [eur-lex-sum-da], [fm-udgivelser], [retsinformationdk], [skat], [retspraksis], [domsdatabasen], [kb_administrative_publication], [municipality_meetings], [logir] | 8.20B       |
| Other        | [ncc_parliament], [dannet], [depbank], [synne], [historical-danish-handwriting], [kb_historical_letters], [tidsskrift-dk], [folketingets-dokumenter]                        | 3.22B       |
| News         | [enevaeldens_nyheder], [ncc_newspaper], [tv2r], [nordjyllandnews]                                                                                                           | 1.11B       |
| Books        | [grundtvig], [ncc_books], [memo], [adl], [wikibooks], [jvj], [gutenberg], [relig], [trykkefrihedens_skrifter], [kalliope]                                                   | 755.24M     |
| Conversation | [comparia], [danske-taler], [opensubtitles], [ep], [ft], [spont], [naat], [dakultur], [mosel_youtubecommons]                                                                | 497.11M     |
| Social Media | [hest]                                                                                                                                                                      | 389.32M     |
| Web          | [ai-aktindsigt], [ncc_maalfrid], [miljoeportalen], [hvadvilduhelst]                                                                                                         | 295.93M     |
| Encyclopedic | [wikisource], [wikipedia], [wiki-comments]                                                                                                                                  | 185.75M     |
| Speeches     | [mosel_voxpopuli]                                                                                                                                                           | 161.33M     |
| Medical      | [health_hovedstaden]                                                                                                                                                        | 27.07M      |
| Readaloud    | [nota]                                                                                                                                                                      | 7.30M       |
| Dialect      | [botxt]                                                                                                                                                                     | 847.97K     |
| **Total**    |                                                                                                                                                                             | 14.85B      |

[ai-aktindsigt]: data/ai-aktindsigt/ai-aktindsigt.md
[cellar]: data/cellar/cellar.md
[comparia]: data/comparia/comparia.md
[enevaeldens_nyheder]: data/enevaeldens_nyheder/enevaeldens_nyheder.md
[grundtvig]: data/grundtvig/grundtvig.md
[danske-taler]: data/danske-taler/danske-taler.md
[ncc_books]: data/ncc_books/ncc_books.md
[ncc_newspaper]: data/ncc_newspaper/ncc_newspaper.md
[ncc_maalfrid]: data/ncc_maalfrid/ncc_maalfrid.md
[ncc_parliament]: data/ncc_parliament/ncc_parliament.md
[eur-lex-sum-da]: data/eur-lex-sum-da/eur-lex-sum-da.md
[miljoeportalen]: data/miljoeportalen/miljoeportalen.md
[fm-udgivelser]: data/fm-udgivelser/fm-udgivelser.md
[memo]: data/memo/memo.md
[opensubtitles]: data/opensubtitles/opensubtitles.md
[retsinformationdk]: data/retsinformationdk/retsinformationdk.md
[ep]: data/ep/ep.md
[ft]: data/ft/ft.md
[wikisource]: data/wikisource/wikisource.md
[spont]: data/spont/spont.md
[tv2r]: data/tv2r/tv2r.md
[adl]: data/adl/adl.md
[hest]: data/hest/hest.md
[skat]: data/skat/skat.md
[dannet]: data/dannet/dannet.md
[retspraksis]: data/retspraksis/retspraksis.md
[wikibooks]: data/wikibooks/wikibooks.md
[jvj]: data/jvj/jvj.md
[gutenberg]: data/gutenberg/gutenberg.md
[botxt]: data/botxt/botxt.md
[depbank]: data/depbank/depbank.md
[naat]: data/naat/naat.md
[synne]: data/synne/synne.md
[wikipedia]: data/wikipedia/wikipedia.md
[wiki-comments]: data/wiki-comments/wiki-comments.md
[nordjyllandnews]: data/nordjyllandnews/nordjyllandnews.md
[relig]: data/relig/relig.md
[nota]: data/nota/nota.md
[health_hovedstaden]: data/health_hovedstaden/health_hovedstaden.md
[domsdatabasen]: data/domsdatabasen/domsdatabasen.md
[historical-danish-handwriting]: data/historical-danish-handwriting/historical-danish-handwriting.md
[kb_administrative_publication]: data/kb_administrative_publication/kb_administrative_publication.md
[kb_historical_letters]: data/kb_historical_letters/kb_historical_letters.md
[trykkefrihedens_skrifter]: data/trykkefrihedens_skrifter/trykkefrihedens_skrifter.md
[municipality_meetings]: data/municipality_meetings/municipality_meetings.md
[hvadvilduhelst]: data/hvadvilduhelst/hvadvilduhelst.md
[tidsskrift-dk]: data/tidsskrift-dk/tidsskrift-dk.md
[dakultur]: data/dakultur/dakultur.md
[mosel_voxpopuli]: data/mosel_voxpopuli/mosel_voxpopuli.md
[mosel_youtubecommons]: data/mosel_youtubecommons/mosel_youtubecommons.md
[folketingets-dokumenter]: data/folketingets-dokumenter/folketingets-dokumenter.md
[kalliope]: data/kalliope/kalliope.md
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
Each document in Danish Dynaword comes with annotations describing its content, such as content quality, information density, and educational value.
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
| License                         | Sources                                                                                                                                                                                                                                                                                                                                 | N. Tokens   |
|:--------------------------------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------|
| CC-BY-SA 4.0                    | [cellar], [enevaeldens_nyheder], [eur-lex-sum-da], [fm-udgivelser], [memo], [wikisource], [tv2r], [wikibooks], [jvj], [depbank], [wikipedia], [wiki-comments]                                                                                                                                                                           | 7.62B       |
| CC BY 4.0                       | [folketingets-dokumenter]                                                                                                                                                                                                                                                                                                               | 2.81B       |
| CC-0                            | [grundtvig], [danske-taler], [ncc_books], [ncc_newspaper], [miljoeportalen], [opensubtitles], [ep], [ft], [spont], [adl], [hest], [skat], [retspraksis], [botxt], [naat], [synne], [nordjyllandnews], [relig], [nota], [health_hovedstaden], [kb_administrative_publication], [kb_historical_letters], [municipality_meetings], [logir] | 2.76B       |
| Other (No attribution required) | [retsinformationdk], [domsdatabasen]                                                                                                                                                                                                                                                                                                    | 904.61M     |
| Other (Attribution required)    | [ai-aktindsigt], [ncc_maalfrid], [ncc_parliament], [dannet], [gutenberg]                                                                                                                                                                                                                                                                | 515.61M     |
| CC-BY 4.0                       | [historical-danish-handwriting], [hvadvilduhelst], [tidsskrift-dk], [mosel_voxpopuli], [mosel_youtubecommons]                                                                                                                                                                                                                           | 216.60M     |
| Public domain                   | [trykkefrihedens_skrifter], [kalliope]                                                                                                                                                                                                                                                                                                  | 23.46M      |
| MIT                             | [dakultur]                                                                                                                                                                                                                                                                                                                              | 5.49K       |
| Etalab 2.0                      | [comparia]                                                                                                                                                                                                                                                                                                                              | 1.35K       |
| **Total**                       |                                                                                                                                                                                                                                                                                                                                         | 14.85B      |

[ai-aktindsigt]: data/ai-aktindsigt/ai-aktindsigt.md
[cellar]: data/cellar/cellar.md
[comparia]: data/comparia/comparia.md
[enevaeldens_nyheder]: data/enevaeldens_nyheder/enevaeldens_nyheder.md
[grundtvig]: data/grundtvig/grundtvig.md
[danske-taler]: data/danske-taler/danske-taler.md
[ncc_books]: data/ncc_books/ncc_books.md
[ncc_newspaper]: data/ncc_newspaper/ncc_newspaper.md
[ncc_maalfrid]: data/ncc_maalfrid/ncc_maalfrid.md
[ncc_parliament]: data/ncc_parliament/ncc_parliament.md
[eur-lex-sum-da]: data/eur-lex-sum-da/eur-lex-sum-da.md
[miljoeportalen]: data/miljoeportalen/miljoeportalen.md
[fm-udgivelser]: data/fm-udgivelser/fm-udgivelser.md
[memo]: data/memo/memo.md
[opensubtitles]: data/opensubtitles/opensubtitles.md
[retsinformationdk]: data/retsinformationdk/retsinformationdk.md
[ep]: data/ep/ep.md
[ft]: data/ft/ft.md
[wikisource]: data/wikisource/wikisource.md
[spont]: data/spont/spont.md
[tv2r]: data/tv2r/tv2r.md
[adl]: data/adl/adl.md
[hest]: data/hest/hest.md
[skat]: data/skat/skat.md
[dannet]: data/dannet/dannet.md
[retspraksis]: data/retspraksis/retspraksis.md
[wikibooks]: data/wikibooks/wikibooks.md
[jvj]: data/jvj/jvj.md
[gutenberg]: data/gutenberg/gutenberg.md
[botxt]: data/botxt/botxt.md
[depbank]: data/depbank/depbank.md
[naat]: data/naat/naat.md
[synne]: data/synne/synne.md
[wikipedia]: data/wikipedia/wikipedia.md
[wiki-comments]: data/wiki-comments/wiki-comments.md
[nordjyllandnews]: data/nordjyllandnews/nordjyllandnews.md
[relig]: data/relig/relig.md
[nota]: data/nota/nota.md
[health_hovedstaden]: data/health_hovedstaden/health_hovedstaden.md
[domsdatabasen]: data/domsdatabasen/domsdatabasen.md
[historical-danish-handwriting]: data/historical-danish-handwriting/historical-danish-handwriting.md
[kb_administrative_publication]: data/kb_administrative_publication/kb_administrative_publication.md
[kb_historical_letters]: data/kb_historical_letters/kb_historical_letters.md
[trykkefrihedens_skrifter]: data/trykkefrihedens_skrifter/trykkefrihedens_skrifter.md
[municipality_meetings]: data/municipality_meetings/municipality_meetings.md
[hvadvilduhelst]: data/hvadvilduhelst/hvadvilduhelst.md
[tidsskrift-dk]: data/tidsskrift-dk/tidsskrift-dk.md
[dakultur]: data/dakultur/dakultur.md
[mosel_voxpopuli]: data/mosel_voxpopuli/mosel_voxpopuli.md
[mosel_youtubecommons]: data/mosel_youtubecommons/mosel_youtubecommons.md
[folketingets-dokumenter]: data/folketingets-dokumenter/folketingets-dokumenter.md
[kalliope]: data/kalliope/kalliope.md
[logir]: data/logir/logir.md
<!-- END-LICENSE TABLE -->



## Dataset Structure

The dataset contains text from different sources which are thoroughly defined in [Source Data](#source-data).

### Data Instances

Each entry in the dataset consists of a single text with associated metadata

<!-- START-SAMPLE -->
```py
{
  "id": "mosel_youtubecommons_2Yv7Y4FIIkY-32720-800",
  "text": "Så kommer Lille Sofus. Kan du tage med?",
  "source": "mosel_youtubecommons",
  "added": "2026-08-04",
  "created": "2019-08-02, 2019-08-02",
  "token_count": 15
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
| Source                          | Description                                                                                                                                                                                              | Domain       | N. Tokens   | License                |
|:--------------------------------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:-------------|:------------|:-----------------------|
| [cellar]                        | The official digital repository for European Union legal documents and open data                                                                                                                         | Legal        | 6.15B       | [CC-BY-SA 4.0]         |
| [folketingets-dokumenter]       | [Danish parliamentary records](https://sprogteknologi.dk/dataset/folketingets-dokumenter-traeningsdata)                                                                                                  | Other        | 2.81B       | [CC BY 4.0]            |
| [enevaeldens_nyheder]           | High quality OCR'd texts from Danish and Norwegian newspapers during the period of constitutional absolutism in Denmark (1660–1849)                                                                      | News         | 1.05B       | [CC-BY-SA 4.0]         |
| [kb_administrative_publication] | Administrative publications from "Det Administrative Bibliotek"                                                                                                                                          | Legal        | 844.58M     | [CC-0]                 |
| [retsinformationdk]             | [retsinformation.dk](https://www.retsinformation.dk) (legal-information.dk) the official legal information system of Denmark                                                                             | Legal        | 818.25M     | [Danish Copyright Law] |
| [ncc_books]                     | Danish books extracted from the [Norwegian Colossal Corpus](https://huggingface.co/datasets/NbAiLab/NCC) derived from OCR                                                                                | Books        | 531.97M     | [CC-0]                 |
| [hest]                          | Samples from the Danish debate forum www.heste-nettet.dk                                                                                                                                                 | Social Media | 389.32M     | [CC-0]                 |
| [ncc_parliament]                | Collections from the Norwegian parliament in Danish. Extracted from the [Norwegian Colossal Corpus](https://huggingface.co/datasets/NbAiLab/NCC) derived from ocr                                        | Other        | 338.87M     | [NLOD 2.0]             |
| [opensubtitles]                 | Danish subsection of [OpenSubtitles](https://opus.nlpl.eu/OpenSubtitles/corpus/version/OpenSubtitles)                                                                                                    | Conversation | 271.60M     | [CC-0]                 |
| [wikipedia]                     | The Danish subsection of [wikipedia](https://en.wikipedia.org/wiki/Main_Page)                                                                                                                            | Encyclopedic | 173.33M     | [CC-BY-SA 4.0]         |
| [mosel_voxpopuli]               | Transcripts of European Parliament recordings from the [MOSEL VoxPopuli collection](https://huggingface.co/datasets/FBK-MT/mosel)                                                                        | Speeches     | 161.33M     | [CC-BY 4.0]            |
| [ai-aktindsigt]                 | Multiple web scrapes from municipality websites collected as a part of the [AI-aktindsigt](https://ai-aktindsigt.dk) project                                                                             | Web          | 139.23M     | [Apache 2.0]           |
| [miljoeportalen]                | Data from [Danmarks Miljøportalen](https://www.miljoeportal.dk/om-danmarks-miljoeportal/) (Denmark's Environment Portal)                                                                                 | Web          | 127.38M     | [CC-0]                 |
| [skat]                          | Skat is the Danish tax authority. This dataset contains content from its website skat.dk                                                                                                                 | Legal        | 122.11M     | [CC-0]                 |
| [ft]                            | Records from all meetings of The Danish parliament (Folketinget) in the parliament hall                                                                                                                  | Conversation | 114.09M     | [CC-0]                 |
| [memo]                          | The MeMo corpus comprising almost all Danish novels from the period 1870-1899, known as the Modern Breakthrough                                                                                          | Books        | 113.74M     | [CC-BY-SA 4.0]         |
| [ep]                            | The Danish subsection of [Europarl](https://aclanthology.org/2005.mtsummit-papers.11/)                                                                                                                   | Conversation | 100.84M     | [CC-0]                 |
| [domsdatabasen]                 | [Domsdatabasen.dk](https://domsdatabasen.dk/) is a public database containing selected judgments from the Danish courts                                                                                  | Legal        | 86.35M      | [Danish Copyright Law] |
| [adl]                           | Danish literature from 1700-2023 from the [Archive for Danish Literature](https://tekster.kb.dk/text?editorial=no&f%5Bsubcollection_ssi%5D%5B%5D=adl&match=one&search_field=Alt) (ADL)                   | Books        | 56.36M      | [CC-0]                 |
| [retspraksis]                   | Case law or judical practice in Denmark derived from [Retspraksis](https://da.wikipedia.org/wiki/Retspraksis)                                                                                            | Legal        | 56.26M      | [CC-0]                 |
| [fm-udgivelser]                 | The official publication series of the Danish Ministry of Finance containing economic analyses, budget proposals, and fiscal policy documents                                                            | Legal        | 50.34M      | [CC-BY-SA 4.0]         |
| [tidsskrift-dk]                 | Danish academic articles from [tidsskrift.dk](https://tidsskrift.dk), the Royal Danish Library's portal for open-access journals                                                                         | Other        | 50.01M      | [CC-BY 4.0]            |
| [nordjyllandnews]               | Articles from the Danish Newspaper [TV2 Nord](https://www.tv2nord.dk)                                                                                                                                    | News         | 37.90M      | [CC-0]                 |
| [eur-lex-sum-da]                | The Danish subsection of EUR-lex SUM consisting of EU legislation paired with professionally written summaries                                                                                           | Legal        | 31.37M      | [CC-BY-SA 4.0]         |
| [ncc_maalfrid]                  | Danish content from Norwegian institutions websites                                                                                                                                                      | Web          | 29.26M      | [NLOD 2.0]             |
| [health_hovedstaden]            | Guidelines and informational documents for healthcare professionals from the Capital Region                                                                                                              | Medical      | 27.07M      | [CC-0]                 |
| [municipality_meetings]         | Committee meeting records from 5 municipalities                                                                                                                                                          | Legal        | 22.64M      | [CC-0]                 |
| [tv2r]                          | Contemporary Danish newswire articles published between 2010 and 2019                                                                                                                                    | News         | 21.67M      | [CC-BY-SA 4.0]         |
| [logir]                         | Laws in Danish from [Logir](https://logir.fo/)                                                                                                                                                           | Legal        | 15.00M      | [CC-0]                 |
| [kb_historical_letters]         | Historical letters from the 1500s up to the 1900s                                                                                                                                                        | Other        | 14.75M      | [CC-0]                 |
| [kalliope]                      | Poetry from the [Kalliope digital library](https://kalliope.org/da/about/kalliope)                                                                                                                       | Books        | 14.01M      | [Public domain]        |
| [grundtvig]                     | The complete collection of [Grundtvig](https://en.wikipedia.org/wiki/N._F._S._Grundtvig) (1783-1872) one of Denmark’s most influential figures                                                           | Books        | 10.53M      | [CC-0]                 |
| [trykkefrihedens_skrifter]      | Pamphlets from the press freedom period 1770-1773, from the Royal Danish Library's [Trykkefrihedens Skrifter](https://tekster.kb.dk/tfs)                                                                 | Books        | 9.46M       | [Public domain]        |
| [danske-taler]                  | Danish Speeches from [dansketaler.dk](https://www.dansketaler.dk)                                                                                                                                        | Conversation | 8.72M       | [CC-0]                 |
| [wikibooks]                     | The Danish Subsection of [Wikibooks](https://www.wikibooks.org)                                                                                                                                          | Books        | 7.63M       | [CC-BY-SA 4.0]         |
| [nota]                          | The text only part of the [Nota lyd- og tekstdata](https://sprogteknologi.dk/dataset/nota-lyd-og-tekstdata) dataset                                                                                      | Readaloud    | 7.30M       | [CC-0]                 |
| [gutenberg]                     | The Danish subsection from Project [Gutenberg](https://www.gutenberg.org)                                                                                                                                | Books        | 6.76M       | [Gutenberg]            |
| [wikisource]                    | The Danish subsection of [Wikisource](https://en.wikisource.org/wiki/Main_Page)                                                                                                                          | Encyclopedic | 6.28M       | [CC-BY-SA 4.0]         |
| [wiki-comments]                 | Text from the comments sections of the Danish Wikipedia                                                                                                                                                  | Encyclopedic | 6.14M       | [CC-BY-SA 4.0]         |
| [historical-danish-handwriting] | Minutes from City and Parish Council meetings between 1841 and 1939 from [The Historical Danish handwriting dataset](https://huggingface.co/datasets/aarhus-city-archives/historical-danish-handwriting) | Other        | 5.20M       | [CC-BY 4.0]            |
| [jvj]                           | The works of the Danish author and poet, [Johannes V. Jensen](https://da.wikipedia.org/wiki/Johannes_V._Jensen)                                                                                          | Books        | 3.55M       | [CC-BY-SA 4.0]         |
| [spont]                         | Conversational samples collected as a part of research projects at Aarhus University                                                                                                                     | Conversation | 1.56M       | [CC-0]                 |
| [dannet]                        | [DanNet](https://cst.ku.dk/projekter/dannet) is a Danish WordNet                                                                                                                                         | Other        | 1.48M       | [DanNet 1.0]           |
| [relig]                         | Danish religious text from the 1700-2022                                                                                                                                                                 | Books        | 1.24M       | [CC-0]                 |
| [ncc_newspaper]                 | OCR'd Newspapers derived from [NCC](https://huggingface.co/datasets/NbAiLab/NCC)                                                                                                                         | News         | 1.05M       | [CC-0]                 |
| [botxt]                         | The Bornholmsk Ordbog Dictionary Project                                                                                                                                                                 | Dialect      | 847.97K     | [CC-0]                 |
| [naat]                          | Danish speeches from 1930-2022                                                                                                                                                                           | Conversation | 286.68K     | [CC-0]                 |
| [depbank]                       | The Danish subsection of the [Universal Dependencies Treebank](https://github.com/UniversalDependencies/UD_Danish-DDT)                                                                                   | Other        | 185.45K     | [CC-BY-SA 4.0]         |
| [hvadvilduhelst]                | Danish "would you rather" questions from [hyg.dk](https://hyg.dk)                                                                                                                                        | Web          | 57.22K      | [CC-BY 4.0]            |
| [synne]                         | Dataset collected from [synnejysk forening's website](https://www.synnejysk.dk), covering the Danish dialect sønderjysk                                                                                  | Other        | 52.02K      | [CC-0]                 |
| [mosel_youtubecommons]          | Transcripts of YouTube videos from [MOSEL](https://huggingface.co/datasets/FBK-MT/mosel)                                                                                                                 | Conversation | 7.09K       | [CC-BY 4.0]            |
| [dakultur]                      | Danish queries probing cultural knowledge, from the [DaKultur](https://huggingface.co/datasets/NLPnorth/dakultur) study                                                                                  | Conversation | 5.49K       | [MIT]                  |
| [comparia]                      | Danish user queries from [ComparIA](https://huggingface.co/datasets/ministere-culture/comparia-conversations)                                                                                            | Conversation | 1.35K       | [Etalab 2.0]           |
| **Total**                       |                                                                                                                                                                                                          |              | 14.85B      |                        |

[ai-aktindsigt]: data/ai-aktindsigt/ai-aktindsigt.md
[cellar]: data/cellar/cellar.md
[comparia]: data/comparia/comparia.md
[enevaeldens_nyheder]: data/enevaeldens_nyheder/enevaeldens_nyheder.md
[grundtvig]: data/grundtvig/grundtvig.md
[danske-taler]: data/danske-taler/danske-taler.md
[ncc_books]: data/ncc_books/ncc_books.md
[ncc_newspaper]: data/ncc_newspaper/ncc_newspaper.md
[ncc_maalfrid]: data/ncc_maalfrid/ncc_maalfrid.md
[ncc_parliament]: data/ncc_parliament/ncc_parliament.md
[eur-lex-sum-da]: data/eur-lex-sum-da/eur-lex-sum-da.md
[miljoeportalen]: data/miljoeportalen/miljoeportalen.md
[fm-udgivelser]: data/fm-udgivelser/fm-udgivelser.md
[memo]: data/memo/memo.md
[opensubtitles]: data/opensubtitles/opensubtitles.md
[retsinformationdk]: data/retsinformationdk/retsinformationdk.md
[ep]: data/ep/ep.md
[ft]: data/ft/ft.md
[wikisource]: data/wikisource/wikisource.md
[spont]: data/spont/spont.md
[tv2r]: data/tv2r/tv2r.md
[adl]: data/adl/adl.md
[hest]: data/hest/hest.md
[skat]: data/skat/skat.md
[dannet]: data/dannet/dannet.md
[retspraksis]: data/retspraksis/retspraksis.md
[wikibooks]: data/wikibooks/wikibooks.md
[jvj]: data/jvj/jvj.md
[gutenberg]: data/gutenberg/gutenberg.md
[botxt]: data/botxt/botxt.md
[depbank]: data/depbank/depbank.md
[naat]: data/naat/naat.md
[synne]: data/synne/synne.md
[wikipedia]: data/wikipedia/wikipedia.md
[wiki-comments]: data/wiki-comments/wiki-comments.md
[nordjyllandnews]: data/nordjyllandnews/nordjyllandnews.md
[relig]: data/relig/relig.md
[nota]: data/nota/nota.md
[health_hovedstaden]: data/health_hovedstaden/health_hovedstaden.md
[domsdatabasen]: data/domsdatabasen/domsdatabasen.md
[historical-danish-handwriting]: data/historical-danish-handwriting/historical-danish-handwriting.md
[kb_administrative_publication]: data/kb_administrative_publication/kb_administrative_publication.md
[kb_historical_letters]: data/kb_historical_letters/kb_historical_letters.md
[trykkefrihedens_skrifter]: data/trykkefrihedens_skrifter/trykkefrihedens_skrifter.md
[municipality_meetings]: data/municipality_meetings/municipality_meetings.md
[hvadvilduhelst]: data/hvadvilduhelst/hvadvilduhelst.md
[tidsskrift-dk]: data/tidsskrift-dk/tidsskrift-dk.md
[dakultur]: data/dakultur/dakultur.md
[mosel_voxpopuli]: data/mosel_voxpopuli/mosel_voxpopuli.md
[mosel_youtubecommons]: data/mosel_youtubecommons/mosel_youtubecommons.md
[folketingets-dokumenter]: data/folketingets-dokumenter/folketingets-dokumenter.md
[kalliope]: data/kalliope/kalliope.md
[logir]: data/logir/logir.md


[CC-0]: https://creativecommons.org/publicdomain/zero/1.0/legalcode.en
[CC-BY-SA 4.0]: https://creativecommons.org/licenses/by-sa/4.0/deed.en
[CC-BY 4.0]: https://creativecommons.org/licenses/by/4.0/deed.en
[Apache 2.0]: https://www.apache.org/licenses/LICENSE-2.0
[Etalab 2.0]: ./data/comparia/comparia.md#license-information
[NLOD 2.0]: ./data/ncc_maalfrid/ncc_maalfrid.md#license-information
[NLOD 2.0]: ./data/ncc_parliament/ncc_parliament.md#license-information
[Danish Copyright Law]: ./data/retsinformationdk/retsinformationdk.md#license-information
[DanNet 1.0]: ./data/dannet/dannet.md#license-information
[Gutenberg]: ./data/gutenberg/gutenberg.md#license-information
[Danish Copyright Law]: ./data/domsdatabasen/domsdatabasen.md#license-information
[Public domain]: ./data/trykkefrihedens_skrifter/trykkefrihedens_skrifter.md#license-information
[MIT]: ./data/dakultur/dakultur.md#license-information
[Public domain]: ./data/kalliope/kalliope.md#license-information
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

---
annotations_creators:
- machine-generated
language_creators:
- crowdsourced
language:
- 'no'
- nb
- nn
- nor
- nob
- nno
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
pretty_name: Norwegian Dynaword
configs:
- config_name: wikiquote-nno
  data_files:
  - split: train
    path: data/wikiquote-nno/data.parquet
- config_name: wikiquote-nob
  data_files:
  - split: train
    path: data/wikiquote-nob/data.parquet
- config_name: wiktionary-nno
  data_files:
  - split: train
    path: data/wiktionary-nno/data.parquet
- config_name: wiktionary-nob
  data_files:
  - split: train
    path: data/wiktionary-nob/data.parquet
- config_name: wikinews
  data_files:
  - split: train
    path: data/wikinews/data.parquet
- config_name: lagmannsrettene
  data_files:
  - split: train
    path: data/lagmannsrettene/data.parquet
- config_name: tingrettene
  data_files:
  - split: train
    path: data/tingrettene/data.parquet
- config_name: hoyesterett
  data_files:
  - split: train
    path: data/hoyesterett/data.parquet
- config_name: nva-cc-by
  data_files:
  - split: train
    path: data/nva-cc-by/data.parquet
- config_name: nva-cc-by-sa
  data_files:
  - split: train
    path: data/nva-cc-by-sa/data.parquet
- config_name: nva-cc0
  data_files:
  - split: train
    path: data/nva-cc0/data.parquet
- config_name: default
  data_files:
  - split: train
    path: data/*/data.parquet
- config_name: meta
  data_files:
  - split: train
    path: data/*/metadata.parquet
- config_name: maalfrid
  data_files:
  - split: train
    path: data/maalfrid/data.parquet
- config_name: ncc-newspapers
  data_files:
  - split: train
    path: data/ncc-newspapers/data.parquet
- config_name: wikipedia-nno
  data_files:
  - split: train
    path: data/wikipedia-nno/data.parquet
- config_name: wikipedia-nob
  data_files:
  - split: train
    path: data/wikipedia-nob/data.parquet
- config_name: stortingsforhandlingerne
  data_files:
  - split: train
    path: data/stortingsforhandlingerne/data.parquet
- config_name: ncc-books
  data_files:
  - split: train
    path: data/ncc-books/data.parquet
- config_name: government-nob
  data_files:
  - split: train
    path: data/government-nob/data.parquet
- config_name: government-nno
  data_files:
  - split: train
    path: data/government-nno/data.parquet
- config_name: public-reports
  data_files:
  - split: train
    path: data/public-reports/data.parquet
- config_name: lovdata
  data_files:
  - split: train
    path: data/lovdata/data.parquet
- config_name: gutenberg
  data_files:
  - split: train
    path: data/gutenberg/data.parquet
- config_name: wikibooks
  data_files:
  - split: train
    path: data/wikibooks/data.parquet
- config_name: wiki-comments
  data_files:
  - split: train
    path: data/wiki-comments/data.parquet
- config_name: cellar
  data_files:
  - split: train
    path: data/cellar/data.parquet
- config_name: bokselskap
  data_files:
  - split: train
    path: data/bokselskap/data.parquet
- config_name: nbdigital
  data_files:
  - split: train
    path: data/nbdigital/data.parquet
- config_name: veidemann-municipalities
  data_files:
  - split: train
    path: data/veidemann-municipalities/data.parquet
- config_name: wikisource
  data_files:
  - split: train
    path: data/wikisource/data.parquet
- config_name: lovdata-ncc-norgeslover
  data_files:
  - split: train
    path: data/lovdata-ncc-norgeslover/data.parquet
- config_name: lovdata-ncc-sentrale-forskrifter
  data_files:
  - split: train
    path: data/lovdata-ncc-sentrale-forskrifter/data.parquet
- config_name: lovdata-ncc-lokale-forskrifter
  data_files:
  - split: train
    path: data/lovdata-ncc-lokale-forskrifter/data.parquet
- config_name: lovdata-ncc-odelsting
  data_files:
  - split: train
    path: data/lovdata-ncc-odelsting/data.parquet
- config_name: lovdata-ncc-somb-rundskriv
  data_files:
  - split: train
    path: data/lovdata-ncc-somb-rundskriv/data.parquet
- config_name: lovdata-ncc-rtv-rundskriv
  data_files:
  - split: train
    path: data/lovdata-ncc-rtv-rundskriv/data.parquet
- config_name: lovdata-ncc-skatt-rundskriv
  data_files:
  - split: train
    path: data/lovdata-ncc-skatt-rundskriv/data.parquet
- config_name: lovdata-ncc-rundskriv-lovavdeling
  data_files:
  - split: train
    path: data/lovdata-ncc-rundskriv-lovavdeling/data.parquet
language_bcp47:
- nno
- nob
- nor
---

<!-- 
readme structure is inspired by:
https://github.com/huggingface/datasets/blob/main/templates/README_guide.md 
-->


# 🧨 Norwegian Dynaword


<!-- START README TABLE -->
|              |                                                                                                                                                                |
| ------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Version** | 0.0.22 ([Changelog](/CHANGELOG.md)) |
| **Language** | Norwegian (no, nor), including Bokmål (nb, nob) and Nynorsk (nn, nno)                                                                                                  |
| **License**  | Openly Licensed, See the respective dataset                                                                                                                    |
| **Models**   | Currently there is no models trained on this dataset                                                                                                           |
| **Contact**  | If you have question about this project please create an issue [here](https://huggingface.co/datasets/danish-foundation-models/norwegian-dynaword/discussions) |



<!-- END README TABLE -->

## Table of Contents
- [🧨 Norwegian Dynaword](#-norwegian-dynaword)
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
- **Number of samples**: 4.57M
- **Number of tokens (Llama 3)**: 10.73B
- **Average document length in tokens (min, max)**: 2.35K (2, 3.21M)
<!-- END-DESC-STATS -->


### Dataset Summary

The Norwegian dynaword is a collection of Norwegian free-form text datasets from various domains. All of the datasets in the Norwegian Dynaword are openly licensed 
and deemed permissible for training large language models. 

Norwegian dynaword is continually developed, which means that the dataset will actively be updated as new datasets become available. If you would like to contribute a dataset see the [contribute section](#contributing-to-the-dataset).

### Loading the dataset

```py
from datasets import load_dataset

name = "danish-foundation-models/norwegian-dynaword"
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
ds = load_dataset(name, "maalfrid", split = "train")
```

To allow filtering we additionally provide extensive [annotations](#annotations)
available through the `meta` config:

```py
meta = load_dataset(name, "meta", split="train")
```

For more on how to use the annotations see [the annotations section](#annotations).


As Norwegian dynaword is continually expanding and curated you can make sure that you get the same dataset every time by specifying the revision:
You can also load a single subset at a time:
```py
ds = load_dataset(name, revision="{desired revision}")
```

### Languages
This dataset includes the following languages:

- Norwegian (nor-Latn), including Bokmål (nob-Latn), and Nynorsk (nno-Latn) 

In addition it likely contains small amounts of English due to code-switching and Danish due to the historical relation between the two languages and language misclassificaitons due to their similarity.

Language is denoted using [BCP-47](https://en.wikipedia.org/wiki/IETF_language_tag), using the langauge code ISO [639-3](https://en.wikipedia.org/wiki/List_of_ISO_639_language_codes) and the script code [ISO 15924](https://en.wikipedia.org/wiki/ISO_15924).

### Domains

This dynaword consist of data from various domains (e.g., legal, books, social media). The following table and figure give an overview of the relative distributions of these domains. To see a full overview of the source check out the [source data section](#source-data)

<div style="display: flex; gap: 20px; align-items: flex-start;">

<div style="flex: 1;">


<!-- START-DOMAIN TABLE -->
| Domain       | Sources                                                                                                                                                                                                                                                                                                                                                   | N. Tokens   |
|:-------------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------|
| Books        | [ncc-books], [gutenberg], [wikibooks], [bokselskap], [nbdigital]                                                                                                                                                                                                                                                                                          | 3.42B       |
| Spoken       | [stortingsforhandlingerne]                                                                                                                                                                                                                                                                                                                                | 2.85B       |
| Web          | [maalfrid]                                                                                                                                                                                                                                                                                                                                                | 2.23B       |
| Report       | [nva-cc-by], [nva-cc-by-sa], [nva-cc0], [government-nob], [government-nno], [public-reports]                                                                                                                                                                                                                                                              | 1.23B       |
| Legal        | [lagmannsrettene], [tingrettene], [hoyesterett], [lovdata], [cellar], [veidemann-municipalities], [lovdata-ncc-norgeslover], [lovdata-ncc-sentrale-forskrifter], [lovdata-ncc-lokale-forskrifter], [lovdata-ncc-odelsting], [lovdata-ncc-somb-rundskriv], [lovdata-ncc-rtv-rundskriv], [lovdata-ncc-skatt-rundskriv], [lovdata-ncc-rundskriv-lovavdeling] | 514.89M     |
| Encyclopedic | [wikiquote-nno], [wikiquote-nob], [wiktionary-nno], [wiktionary-nob], [wikipedia-nno], [wikipedia-nob], [wiki-comments], [wikisource]                                                                                                                                                                                                                     | 343.74M     |
| News         | [wikinews], [ncc-newspapers]                                                                                                                                                                                                                                                                                                                              | 143.98M     |
| **Total**    |                                                                                                                                                                                                                                                                                                                                                           | 10.73B      |

[wikiquote-nno]: data/wikiquote-nno/wikiquote-nno.md
[wikiquote-nob]: data/wikiquote-nob/wikiquote-nob.md
[wiktionary-nno]: data/wiktionary-nno/wiktionary-nno.md
[wiktionary-nob]: data/wiktionary-nob/wiktionary-nob.md
[wikinews]: data/wikinews/wikinews.md
[lagmannsrettene]: data/lagmannsrettene/lagmannsrettene.md
[tingrettene]: data/tingrettene/tingrettene.md
[hoyesterett]: data/hoyesterett/hoyesterett.md
[nva-cc-by]: data/nva-cc-by/nva-cc-by.md
[nva-cc-by-sa]: data/nva-cc-by-sa/nva-cc-by-sa.md
[nva-cc0]: data/nva-cc0/nva-cc0.md
[maalfrid]: data/maalfrid/maalfrid.md
[ncc-newspapers]: data/ncc-newspapers/ncc-newspapers.md
[wikipedia-nno]: data/wikipedia-nno/wikipedia-nno.md
[wikipedia-nob]: data/wikipedia-nob/wikipedia-nob.md
[stortingsforhandlingerne]: data/stortingsforhandlingerne/stortingsforhandlingerne.md
[ncc-books]: data/ncc-books/ncc-books.md
[government-nob]: data/government-nob/government-nob.md
[government-nno]: data/government-nno/government-nno.md
[public-reports]: data/public-reports/public-reports.md
[lovdata]: data/lovdata/lovdata.md
[gutenberg]: data/gutenberg/gutenberg.md
[wikibooks]: data/wikibooks/wikibooks.md
[wiki-comments]: data/wiki-comments/wiki-comments.md
[cellar]: data/cellar/cellar.md
[bokselskap]: data/bokselskap/bokselskap.md
[nbdigital]: data/nbdigital/nbdigital.md
[veidemann-municipalities]: data/veidemann-municipalities/veidemann-municipalities.md
[wikisource]: data/wikisource/wikisource.md
[lovdata-ncc-norgeslover]: data/lovdata-ncc-norgeslover/lovdata-ncc-norgeslover.md
[lovdata-ncc-sentrale-forskrifter]: data/lovdata-ncc-sentrale-forskrifter/lovdata-ncc-sentrale-forskrifter.md
[lovdata-ncc-lokale-forskrifter]: data/lovdata-ncc-lokale-forskrifter/lovdata-ncc-lokale-forskrifter.md
[lovdata-ncc-odelsting]: data/lovdata-ncc-odelsting/lovdata-ncc-odelsting.md
[lovdata-ncc-somb-rundskriv]: data/lovdata-ncc-somb-rundskriv/lovdata-ncc-somb-rundskriv.md
[lovdata-ncc-rtv-rundskriv]: data/lovdata-ncc-rtv-rundskriv/lovdata-ncc-rtv-rundskriv.md
[lovdata-ncc-skatt-rundskriv]: data/lovdata-ncc-skatt-rundskriv/lovdata-ncc-skatt-rundskriv.md
[lovdata-ncc-rundskriv-lovavdeling]: data/lovdata-ncc-rundskriv-lovavdeling/lovdata-ncc-rundskriv-lovavdeling.md
<!-- END-DOMAIN TABLE -->

</div>

<div style="flex: 1;">

<p align="center">
<img src="./images/domain_distribution.png" width="400" style="margin-right: 10px;" />
</p>

</div>

</div>

### Language

This dynaword consist of data from various language, including Norwegian Bokmål (nob), nynorsk (nno) and Norwegian that is either mixed or where it
is unknown if it is Nynorsk or Bokmål, for these we use the macrolanguage tag for Norwegian (nor) along with the individual language ids (nob, nno). 
The following table and figure give an overview of the relative distributions of these languages. To see a full overview of the source check out the [source data section](#source-data)

<div style="display: flex; gap: 20px; align-items: flex-start;">

<div style="flex: 1;">


<!-- START-LANGUAGE TABLE -->
| Language      | Sources                                                                                                                                                                                                                                                                              | N. Tokens   |
|:--------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------|
| nob, nno, nor | [nva-cc-by], [nva-cc-by-sa], [nva-cc0], [maalfrid], [ncc-newspapers], [stortingsforhandlingerne], [wikisource]                                                                                                                                                                       | 5.94B       |
| nob           | [wikiquote-nob], [wiktionary-nob], [tingrettene], [wikipedia-nob], [ncc-books], [government-nob]                                                                                                                                                                                     | 2.34B       |
| nob, nno      | [wikinews], [lagmannsrettene], [hoyesterett], [cellar], [bokselskap], [nbdigital], [veidemann-municipalities]                                                                                                                                                                        | 1.99B       |
| nob, nor, nno | [public-reports], [lovdata], [lovdata-ncc-norgeslover], [lovdata-ncc-sentrale-forskrifter], [lovdata-ncc-lokale-forskrifter], [lovdata-ncc-odelsting], [lovdata-ncc-somb-rundskriv], [lovdata-ncc-rtv-rundskriv], [lovdata-ncc-skatt-rundskriv], [lovdata-ncc-rundskriv-lovavdeling] | 325.47M     |
| nno           | [wikiquote-nno], [wiktionary-nno], [wikipedia-nno], [government-nno]                                                                                                                                                                                                                 | 103.26M     |
| nno, nob      | [wikibooks], [wiki-comments]                                                                                                                                                                                                                                                         | 32.98M      |
| nno, nor, nob | [gutenberg]                                                                                                                                                                                                                                                                          | 1.55M       |
| **Total**     |                                                                                                                                                                                                                                                                                      | 10.73B      |

[wikiquote-nno]: data/wikiquote-nno/wikiquote-nno.md
[wikiquote-nob]: data/wikiquote-nob/wikiquote-nob.md
[wiktionary-nno]: data/wiktionary-nno/wiktionary-nno.md
[wiktionary-nob]: data/wiktionary-nob/wiktionary-nob.md
[wikinews]: data/wikinews/wikinews.md
[lagmannsrettene]: data/lagmannsrettene/lagmannsrettene.md
[tingrettene]: data/tingrettene/tingrettene.md
[hoyesterett]: data/hoyesterett/hoyesterett.md
[nva-cc-by]: data/nva-cc-by/nva-cc-by.md
[nva-cc-by-sa]: data/nva-cc-by-sa/nva-cc-by-sa.md
[nva-cc0]: data/nva-cc0/nva-cc0.md
[maalfrid]: data/maalfrid/maalfrid.md
[ncc-newspapers]: data/ncc-newspapers/ncc-newspapers.md
[wikipedia-nno]: data/wikipedia-nno/wikipedia-nno.md
[wikipedia-nob]: data/wikipedia-nob/wikipedia-nob.md
[stortingsforhandlingerne]: data/stortingsforhandlingerne/stortingsforhandlingerne.md
[ncc-books]: data/ncc-books/ncc-books.md
[government-nob]: data/government-nob/government-nob.md
[government-nno]: data/government-nno/government-nno.md
[public-reports]: data/public-reports/public-reports.md
[lovdata]: data/lovdata/lovdata.md
[gutenberg]: data/gutenberg/gutenberg.md
[wikibooks]: data/wikibooks/wikibooks.md
[wiki-comments]: data/wiki-comments/wiki-comments.md
[cellar]: data/cellar/cellar.md
[bokselskap]: data/bokselskap/bokselskap.md
[nbdigital]: data/nbdigital/nbdigital.md
[veidemann-municipalities]: data/veidemann-municipalities/veidemann-municipalities.md
[wikisource]: data/wikisource/wikisource.md
[lovdata-ncc-norgeslover]: data/lovdata-ncc-norgeslover/lovdata-ncc-norgeslover.md
[lovdata-ncc-sentrale-forskrifter]: data/lovdata-ncc-sentrale-forskrifter/lovdata-ncc-sentrale-forskrifter.md
[lovdata-ncc-lokale-forskrifter]: data/lovdata-ncc-lokale-forskrifter/lovdata-ncc-lokale-forskrifter.md
[lovdata-ncc-odelsting]: data/lovdata-ncc-odelsting/lovdata-ncc-odelsting.md
[lovdata-ncc-somb-rundskriv]: data/lovdata-ncc-somb-rundskriv/lovdata-ncc-somb-rundskriv.md
[lovdata-ncc-rtv-rundskriv]: data/lovdata-ncc-rtv-rundskriv/lovdata-ncc-rtv-rundskriv.md
[lovdata-ncc-skatt-rundskriv]: data/lovdata-ncc-skatt-rundskriv/lovdata-ncc-skatt-rundskriv.md
[lovdata-ncc-rundskriv-lovavdeling]: data/lovdata-ncc-rundskriv-lovavdeling/lovdata-ncc-rundskriv-lovavdeling.md
<!-- END-LANGUAGE TABLE -->

</div>

<div style="flex: 1;">

<p align="center">
<img src="./images/language_distribution.svg" width="600" style="margin-right: 10px;" />
</p>

</div>

</div>




### Annotation Overview
<!-- START-ANNOTATION PLOTS -->
Annotated documents in Norwegian Dynaword come with annotations describing their content, such as content quality, information density, and educational value.
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
| License                      | Sources                                                                                                                                                                                                                                                                                                                                                                       | N. Tokens   |
|:-----------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------|
| Other (Attribution required) | [maalfrid], [stortingsforhandlingerne], [government-nob], [government-nno], [public-reports], [lovdata], [gutenberg], [lovdata-ncc-norgeslover], [lovdata-ncc-sentrale-forskrifter], [lovdata-ncc-lokale-forskrifter], [lovdata-ncc-odelsting], [lovdata-ncc-somb-rundskriv], [lovdata-ncc-rtv-rundskriv], [lovdata-ncc-skatt-rundskriv], [lovdata-ncc-rundskriv-lovavdeling] | 5.75B       |
| CC-0                         | [nva-cc0], [ncc-newspapers], [wikipedia-nno], [wikipedia-nob], [ncc-books], [wikibooks], [wiki-comments], [bokselskap], [nbdigital], [veidemann-municipalities]                                                                                                                                                                                                               | 4.22B       |
| CC-BY 4.0                    | [nva-cc-by]                                                                                                                                                                                                                                                                                                                                                                   | 695.95M     |
| Norwegian Copyright Act §14  | [lagmannsrettene], [tingrettene], [hoyesterett]                                                                                                                                                                                                                                                                                                                               | 33.18M      |
| CC-BY-SA 4.0                 | [wikiquote-nno], [wikiquote-nob], [wiktionary-nno], [wiktionary-nob], [nva-cc-by-sa], [cellar], [wikisource]                                                                                                                                                                                                                                                                  | 28.23M      |
| CC BY 2.5 / CC BY 4.0        | [wikinews]                                                                                                                                                                                                                                                                                                                                                                    | 245.59K     |
| **Total**                    |                                                                                                                                                                                                                                                                                                                                                                               | 10.73B      |

[wikiquote-nno]: data/wikiquote-nno/wikiquote-nno.md
[wikiquote-nob]: data/wikiquote-nob/wikiquote-nob.md
[wiktionary-nno]: data/wiktionary-nno/wiktionary-nno.md
[wiktionary-nob]: data/wiktionary-nob/wiktionary-nob.md
[wikinews]: data/wikinews/wikinews.md
[lagmannsrettene]: data/lagmannsrettene/lagmannsrettene.md
[tingrettene]: data/tingrettene/tingrettene.md
[hoyesterett]: data/hoyesterett/hoyesterett.md
[nva-cc-by]: data/nva-cc-by/nva-cc-by.md
[nva-cc-by-sa]: data/nva-cc-by-sa/nva-cc-by-sa.md
[nva-cc0]: data/nva-cc0/nva-cc0.md
[maalfrid]: data/maalfrid/maalfrid.md
[ncc-newspapers]: data/ncc-newspapers/ncc-newspapers.md
[wikipedia-nno]: data/wikipedia-nno/wikipedia-nno.md
[wikipedia-nob]: data/wikipedia-nob/wikipedia-nob.md
[stortingsforhandlingerne]: data/stortingsforhandlingerne/stortingsforhandlingerne.md
[ncc-books]: data/ncc-books/ncc-books.md
[government-nob]: data/government-nob/government-nob.md
[government-nno]: data/government-nno/government-nno.md
[public-reports]: data/public-reports/public-reports.md
[lovdata]: data/lovdata/lovdata.md
[gutenberg]: data/gutenberg/gutenberg.md
[wikibooks]: data/wikibooks/wikibooks.md
[wiki-comments]: data/wiki-comments/wiki-comments.md
[cellar]: data/cellar/cellar.md
[bokselskap]: data/bokselskap/bokselskap.md
[nbdigital]: data/nbdigital/nbdigital.md
[veidemann-municipalities]: data/veidemann-municipalities/veidemann-municipalities.md
[wikisource]: data/wikisource/wikisource.md
[lovdata-ncc-norgeslover]: data/lovdata-ncc-norgeslover/lovdata-ncc-norgeslover.md
[lovdata-ncc-sentrale-forskrifter]: data/lovdata-ncc-sentrale-forskrifter/lovdata-ncc-sentrale-forskrifter.md
[lovdata-ncc-lokale-forskrifter]: data/lovdata-ncc-lokale-forskrifter/lovdata-ncc-lokale-forskrifter.md
[lovdata-ncc-odelsting]: data/lovdata-ncc-odelsting/lovdata-ncc-odelsting.md
[lovdata-ncc-somb-rundskriv]: data/lovdata-ncc-somb-rundskriv/lovdata-ncc-somb-rundskriv.md
[lovdata-ncc-rtv-rundskriv]: data/lovdata-ncc-rtv-rundskriv/lovdata-ncc-rtv-rundskriv.md
[lovdata-ncc-skatt-rundskriv]: data/lovdata-ncc-skatt-rundskriv/lovdata-ncc-skatt-rundskriv.md
[lovdata-ncc-rundskriv-lovavdeling]: data/lovdata-ncc-rundskriv-lovavdeling/lovdata-ncc-rundskriv-lovavdeling.md
<!-- END-LICENSE TABLE -->



## Dataset Structure

The dataset contains text from different sources which are thoroughly defined in [Source Data](#source-data).

### Data Instances

Each entry in the dataset consists of a single text with associated metadata

<!-- START-SAMPLE -->
```py
{
  "id": "wikipedia-nno-0",
  "text": "'''Fredrik Hope''' () er ein norsk målmann og felespelar frå Hyen i Gloppen. Han vart leiar for Nors[...]",
  "source": "wikipedia-nno",
  "added": "2026-01-25",
  "created": "2021-01-01, 2021-12-31",
  "token_count": 214
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

These datasets were collected and curated with the intention of making openly license Norwegian data available. While this was collected with the intention of developing language models it is likely to have multiple other uses such as examining language development and differences across domains.


### Annotations

Synthetic metadata is stored as `data/{dataset}/metadata.parquet`. These
annotations were generated with [`ellamind/propella-1-4b`](https://huggingface.co/ellamind/propella-1-4b)
and include fields for content type, quality, safety, audience level,
educational level, PII presence, regional relevance and more.

The metadata rows include `dataset` and `id`, so a subset can be filtered and
joined with the corpus rows:

```py
from datasets import load_dataset

name = "danish-foundation-models/norwegian-dynaword"
texts = load_dataset(name, "maalfrid", split="train")
meta = load_dataset(name, "meta", split="train").filter(
    lambda row: row["dataset"] == "maalfrid"
)

texts_df = texts.to_pandas()
meta_df = meta.to_pandas()
maalfrid_with_meta = texts_df.merge(meta_df, on="id", how="left")
```


### Source Data

Below follows a brief overview of the sources in the corpus along with their individual license. To get more information about the individual dataset click the hyperlink in the table.

<details>
<summary><b>Overview Table (click to unfold)</b></summary>

You can learn more about each dataset by pressing the link in the first column.

<!-- START-MAIN TABLE -->
| Source                              | Description                                                                                                                                                                                                  | Domain       | N. Tokens   | License                       |
|:------------------------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:-------------|:------------|:------------------------------|
| [stortingsforhandlingerne]          | OCR'd documents from the Norwegian parliament Stortinget                                                                                                                                                     | Spoken       | 2.85B       | [NLOD 2.0]                    |
| [maalfrid]                          | Norwegian content from Norwegian institutions websites                                                                                                                                                       | Web          | 2.23B       | [NLOD 2.0]                    |
| [ncc-books]                         | Public Domains Norwegian books from [NCC](https://huggingface.co/datasets/NbAiLab/NCC)                                                                                                                       | Books        | 1.78B       | [CC-0]                        |
| [nbdigital]                         | Documents from Norwegian public domain books/documents from NBdigital                                                                                                                                        | Books        | 1.61B       | [CC-0]                        |
| [nva-cc-by]                         | Norwegian research texts from [NVA](https://nva.sikt.no/)                                                                                                                                                    | Report       | 695.95M     | [CC-BY 4.0]                   |
| [veidemann-municipalities]          | Documents from Norwegian municipalities scraped by the Veidemann web crawler                                                                                                                                 | Legal        | 316.96M     | [CC-0]                        |
| [government-nob]                    | Govermental reports written on Norwegian Bokmål                                                                                                                                                              | Report       | 305.61M     | [NLOD 2.0]                    |
| [wikipedia-nob]                     | The Norwegian Bokmål subsection of [wikipedia](https://en.wikipedia.org/wiki/Main_Page)                                                                                                                      | Encyclopedic | 247.69M     | [CC-0]                        |
| [public-reports]                    | Public reports form the NLN portal                                                                                                                                                                           | Report       | 162.78M     | [NLOD 2.0]                    |
| [ncc-newspapers]                    | OCR'd Newspapers released by the National Library of Norway (NLN)                                                                                                                                            | News         | 143.73M     | [CC-0]                        |
| [lovdata-ncc-odelsting]             | Legislative documents from the Odelsting from Lovdata's CD/DVD collection, via the [NCC](https://huggingface.co/datasets/NbAiLab/NCC)                                                                        | Legal        | 81.71M      | [NLOD 2.0]                    |
| [wikipedia-nno]                     | The Norwegian Nynorsk subsection of [wikipedia](https://en.wikipedia.org/wiki/Main_Page)                                                                                                                     | Encyclopedic | 60.50M      | [CC-0]                        |
| [government-nno]                    | Govermental reports written on Norwegian Nynorsk                                                                                                                                                             | Report       | 42.14M      | [NLOD 2.0]                    |
| [lovdata]                           | Current Norwegian laws and central regulations from [Lovdata](https://lovdata.no)'s public-data API, via the [Lovverk](https://github.com/bartoszkobylinski/lovverk) corpus                                  | Legal        | 41.23M      | [NLOD 2.0]                    |
| [bokselskap]                        | Documents from Norwegian public domain books scraped from [bokselskap.no](https://www.bokselskap.no) project                                                                                                 | Books        | 32.79M      | [CC-0]                        |
| [wiki-comments]                     | Text from the comments sections of the Norwegian Wikipedia                                                                                                                                                   | Encyclopedic | 30.96M      | [CC-0]                        |
| [hoyesterett]                       | Court decisions from [Høyesterett](https://www.domstol.no/no/hoyesterett/avgjorelser/)                                                                                                                       | Legal        | 29.82M      | [Norwegian Copyright Act §14] |
| [nva-cc-by-sa]                      | Norwegian research texts from [NVA](https://nva.sikt.no/)                                                                                                                                                    | Report       | 21.58M      | [CC-BY-SA 4.0]                |
| [lovdata-ncc-sentrale-forskrifter]  | Norwegian central regulations (*sentrale forskrifter*) from Lovdata's CD/DVD collection, via the [NCC](https://huggingface.co/datasets/NbAiLab/NCC)                                                          | Legal        | 12.03M      | [NLOD 2.0]                    |
| [lovdata-ncc-somb-rundskriv]        | Statements from the Norwegian Parliamentary Ombudsman (*Sivilombudsmannen*) from Lovdata's CD/DVD collection, via the [NCC](https://huggingface.co/datasets/NbAiLab/NCC)                                     | Legal        | 11.56M      | [NLOD 2.0]                    |
| [lovdata-ncc-lokale-forskrifter]    | Norwegian local regulations (*lokale forskrifter*) from Lovdata's CD/DVD collection, via the [NCC](https://huggingface.co/datasets/NbAiLab/NCC)                                                              | Legal        | 5.28M       | [NLOD 2.0]                    |
| [lovdata-ncc-norgeslover]           | Norwegian acts of parliament (*Norges Lover*) from Lovdata's CD/DVD collection, via the [NCC](https://huggingface.co/datasets/NbAiLab/NCC)                                                                   | Legal        | 4.02M       | [NLOD 2.0]                    |
| [nva-cc0]                           | Norwegian research texts from [NVA](https://nva.sikt.no/)                                                                                                                                                    | Report       | 3.98M       | [CC-0]                        |
| [lovdata-ncc-rtv-rundskriv]         | Circulars from the Norwegian National Insurance Administration (*Rikstrygdeverket*) from Lovdata's CD/DVD collection, via the [NCC](https://huggingface.co/datasets/NbAiLab/NCC)                             | Legal        | 3.18M       | [NLOD 2.0]                    |
| [lovdata-ncc-skatt-rundskriv]       | Circulars from the Norwegian Tax Administration (*Skatteetaten*) from Lovdata's CD/DVD collection, via the [NCC](https://huggingface.co/datasets/NbAiLab/NCC)                                                | Legal        | 2.63M       | [NLOD 2.0]                    |
| [tingrettene]                       | Decisions from Norway’s [district courts](https://www.domstol.no/)                                                                                                                                           | Legal        | 2.44M       | [Norwegian Copyright Act §14] |
| [wiktionary-nob]                    | Dictionary entries from [Bokmål Wiktionary](https://no.wiktionary.org/)                                                                                                                                      | Encyclopedic | 2.10M       | [CC-BY-SA 4.0]                |
| [cellar]                            | The official digital repository for European Union legal documents and open data                                                                                                                             | Legal        | 2.06M       | [CC-BY-SA 4.0]                |
| [wikibooks]                         | The Danish Subsection of [Wikibooks](https://www.wikibooks.org)                                                                                                                                              | Books        | 2.01M       | [CC-0]                        |
| [gutenberg]                         | The Norwegian subsection from Project [Gutenberg](https://www.gutenberg.org)                                                                                                                                 | Books        | 1.55M       | [Gutenberg]                   |
| [wikisource]                        | The Norwegian subsection of [Wikisource (Wikikilden)](https://no.wikisource.org/)                                                                                                                            | Encyclopedic | 1.31M       | [CC-BY-SA 4.0]                |
| [lovdata-ncc-rundskriv-lovavdeling] | Circulars and statements from the Legislation Department (*Lovavdelingen*) of the Norwegian Ministry of Justice from Lovdata's CD/DVD collection, via the [NCC](https://huggingface.co/datasets/NbAiLab/NCC) | Legal        | 1.06M       | [NLOD 2.0]                    |
| [lagmannsrettene]                   | Decisions from Norway’s [courts of appeal](https://www.domstol.no/)                                                                                                                                          | Legal        | 921.55K     | [Norwegian Copyright Act §14] |
| [wikiquote-nob]                     | Quotations and proverbs from [Bokmål Wikiquote](https://no.wikiquote.org/)                                                                                                                                   | Encyclopedic | 567.21K     | [CC-BY-SA 4.0]                |
| [wikiquote-nno]                     | Quotations and proverbs from [Nynorsk Wikiquote](https://nn.wikiquote.org/)                                                                                                                                  | Encyclopedic | 399.58K     | [CC-BY-SA 4.0]                |
| [wikinews]                          | News articles from [Norwegian Wikinews](https://no.wikinews.org/)                                                                                                                                            | News         | 245.59K     | [CC BY 2.5 / CC BY 4.0]       |
| [wiktionary-nno]                    | Dictionary entries from [Nynorsk Wiktionary](https://nn.wiktionary.org/)                                                                                                                                     | Encyclopedic | 216.90K     | [CC-BY-SA 4.0]                |
| **Total**                           |                                                                                                                                                                                                              |              | 10.73B      |                               |

[wikiquote-nno]: data/wikiquote-nno/wikiquote-nno.md
[wikiquote-nob]: data/wikiquote-nob/wikiquote-nob.md
[wiktionary-nno]: data/wiktionary-nno/wiktionary-nno.md
[wiktionary-nob]: data/wiktionary-nob/wiktionary-nob.md
[wikinews]: data/wikinews/wikinews.md
[lagmannsrettene]: data/lagmannsrettene/lagmannsrettene.md
[tingrettene]: data/tingrettene/tingrettene.md
[hoyesterett]: data/hoyesterett/hoyesterett.md
[nva-cc-by]: data/nva-cc-by/nva-cc-by.md
[nva-cc-by-sa]: data/nva-cc-by-sa/nva-cc-by-sa.md
[nva-cc0]: data/nva-cc0/nva-cc0.md
[maalfrid]: data/maalfrid/maalfrid.md
[ncc-newspapers]: data/ncc-newspapers/ncc-newspapers.md
[wikipedia-nno]: data/wikipedia-nno/wikipedia-nno.md
[wikipedia-nob]: data/wikipedia-nob/wikipedia-nob.md
[stortingsforhandlingerne]: data/stortingsforhandlingerne/stortingsforhandlingerne.md
[ncc-books]: data/ncc-books/ncc-books.md
[government-nob]: data/government-nob/government-nob.md
[government-nno]: data/government-nno/government-nno.md
[public-reports]: data/public-reports/public-reports.md
[lovdata]: data/lovdata/lovdata.md
[gutenberg]: data/gutenberg/gutenberg.md
[wikibooks]: data/wikibooks/wikibooks.md
[wiki-comments]: data/wiki-comments/wiki-comments.md
[cellar]: data/cellar/cellar.md
[bokselskap]: data/bokselskap/bokselskap.md
[nbdigital]: data/nbdigital/nbdigital.md
[veidemann-municipalities]: data/veidemann-municipalities/veidemann-municipalities.md
[wikisource]: data/wikisource/wikisource.md
[lovdata-ncc-norgeslover]: data/lovdata-ncc-norgeslover/lovdata-ncc-norgeslover.md
[lovdata-ncc-sentrale-forskrifter]: data/lovdata-ncc-sentrale-forskrifter/lovdata-ncc-sentrale-forskrifter.md
[lovdata-ncc-lokale-forskrifter]: data/lovdata-ncc-lokale-forskrifter/lovdata-ncc-lokale-forskrifter.md
[lovdata-ncc-odelsting]: data/lovdata-ncc-odelsting/lovdata-ncc-odelsting.md
[lovdata-ncc-somb-rundskriv]: data/lovdata-ncc-somb-rundskriv/lovdata-ncc-somb-rundskriv.md
[lovdata-ncc-rtv-rundskriv]: data/lovdata-ncc-rtv-rundskriv/lovdata-ncc-rtv-rundskriv.md
[lovdata-ncc-skatt-rundskriv]: data/lovdata-ncc-skatt-rundskriv/lovdata-ncc-skatt-rundskriv.md
[lovdata-ncc-rundskriv-lovavdeling]: data/lovdata-ncc-rundskriv-lovavdeling/lovdata-ncc-rundskriv-lovavdeling.md


[CC-0]: https://creativecommons.org/publicdomain/zero/1.0/legalcode.en
[CC-BY-SA 4.0]: https://creativecommons.org/licenses/by-sa/4.0/deed.en
[CC-BY 4.0]: https://creativecommons.org/licenses/by/4.0/deed.en
[Apache 2.0]: https://www.apache.org/licenses/LICENSE-2.0
[CC BY 2.5 / CC BY 4.0]: ./data/wikinews/wikinews.md#license-information
[Norwegian Copyright Act §14]: ./data/lagmannsrettene/lagmannsrettene.md#license-information
[Norwegian Copyright Act §14]: ./data/tingrettene/tingrettene.md#license-information
[Norwegian Copyright Act §14]: ./data/hoyesterett/hoyesterett.md#license-information
[NLOD 2.0]: ./data/maalfrid/maalfrid.md#license-information
[NLOD 2.0]: ./data/stortingsforhandlingerne/stortingsforhandlingerne.md#license-information
[NLOD 2.0]: ./data/government-nob/government-nob.md#license-information
[NLOD 2.0]: ./data/government-nno/government-nno.md#license-information
[NLOD 2.0]: ./data/public-reports/public-reports.md#license-information
[NLOD 2.0]: ./data/lovdata/lovdata.md#license-information
[Gutenberg]: ./data/gutenberg/gutenberg.md#license-information
[NLOD 2.0]: ./data/lovdata-ncc-norgeslover/lovdata-ncc-norgeslover.md#license-information
[NLOD 2.0]: ./data/lovdata-ncc-sentrale-forskrifter/lovdata-ncc-sentrale-forskrifter.md#license-information
[NLOD 2.0]: ./data/lovdata-ncc-lokale-forskrifter/lovdata-ncc-lokale-forskrifter.md#license-information
[NLOD 2.0]: ./data/lovdata-ncc-odelsting/lovdata-ncc-odelsting.md#license-information
[NLOD 2.0]: ./data/lovdata-ncc-somb-rundskriv/lovdata-ncc-somb-rundskriv.md#license-information
[NLOD 2.0]: ./data/lovdata-ncc-rtv-rundskriv/lovdata-ncc-rtv-rundskriv.md#license-information
[NLOD 2.0]: ./data/lovdata-ncc-skatt-rundskriv/lovdata-ncc-skatt-rundskriv.md#license-information
[NLOD 2.0]: ./data/lovdata-ncc-rundskriv-lovavdeling/lovdata-ncc-rundskriv-lovavdeling.md#license-information
<!-- END-MAIN TABLE -->

</details>


### Data Collection and Processing

Norwegian dynaword is continually developed, which means that the dataset will actively be updated as new datasets become available. This means that the size of Dynaword increases over time as seen in the following plot:

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

If you use this work, please cite the [scientific article](https://arxiv.org/abs/2508.02271) introducing the Dynaword approach and with the [NCC](https://huggingface.co/datasets/NbAiLab/NCC) which provides large parts of the datasets:

> Enevoldsen, K.C., Jensen, K.N., Kostkan, J., Szab'o, B.I., Kardos, M., Vad, K., Heinsen, J., N'unez, A.B., Barmina, G., Nielsen, J., Larsen, R., Vahlstrup, P.B., Dalum, P.M., Elliott, D., Galke, L., Schneider-Kamp, P., & Nielbo, K.L. (2025). Dynaword: From One-shot to Continuously Developed Datasets.
>
> Per Kummervold, Freddy Wetjen, and Javier de la Rosa. 2022. The Norwegian Colossal Corpus: A Text Corpus for Training Large Norwegian Language Models. In Proceedings of the Thirteenth Language Resources and Evaluation Conference, pages 3852–3860, Marseille, France. European Language Resources Association.


```
@article{enevoldsen2025dynaword,
  title={Dynaword: From One-shot to Continuously Developed Datasets},
  author={Enevoldsen, Kenneth and Jensen, Kristian N{\o}rgaard and Kostkan, Jan and Szab{\'o}, Bal{\'a}zs and Kardos, M{\'a}rton and Vad, Kirten and N{\'u}{\~n}ez, Andrea Blasi and Barmina, Gianluca and Nielsen, Jacob and Larsen, Rasmus and others},
  journal={arXiv preprint arXiv:2508.02271},
  year={2025}
}
@inproceedings{kummervold-etal-2022-norwegian,
    title = "The {N}orwegian Colossal Corpus: A Text Corpus for Training Large {N}orwegian Language Models",
    author = "Kummervold, Per  and
      Wetjen, Freddy  and
      de la Rosa, Javier",
    booktitle = "Proceedings of the Thirteenth Language Resources and Evaluation Conference",
    month = jun,
    year = "2022",
    address = "Marseille, France",
    publisher = "European Language Resources Association",
    url = "https://aclanthology.org/2022.lrec-1.410/",
}
```

Additionally, we recommend citing the relevant source datasets as well. See the individual datasheets for more information.

## License information

The license for each constituent dataset is supplied in the [Source data](#source-data) table. This license is applied to the constituent data, i.e., the text. The collection of datasets (metadata, quality control, etc.) is licensed under [CC-0](https://creativecommons.org/publicdomain/zero/1.0/legalcode.en).

### Personal and Sensitive Information

As far as we are aware the dataset does not contain information identifying sexual orientation, political beliefs, religion, or health connected along with a personal identifier of any non-public or non-historic figures.


### Bias, Risks, and Limitations

Certain works in this collection are historical works and thus reflect the linguistic, cultural, and ideological norms of their time.
As such, it includes perspectives, assumptions, and biases characteristic of the period, which may be considered offensive or exclusionary by contemporary standards.


### Notice and takedown policy
We redistribute files shared with us under a license permitting such redistribution. If you have concerns about the licensing of these files, please [contact us](https://huggingface.co/datasets/danish-foundation-models/norwegian-dynaword/discussions/new). If you consider that the data contains material that infringe your copyright, please:
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

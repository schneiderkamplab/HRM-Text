---
pretty_name: 8 Sidor
language:
- sv
license: cc-by-4.0
license_name: CC-BY 4.0
size_categories:
- 100K<n<1M
task_categories:
- text-generation
- fill-mask
task_ids:
- language-modeling
source_datasets:
- original
domains:
- News
---

# Dataset Card for 8 Sidor

<!-- START-SHORT DESCRIPTION -->
Easy-to-read news from [8 Sidor](https://spraakbanken.gu.se/en/resources/attasidor).
<!-- END-SHORT DESCRIPTION -->

Swedish news written in simplified language for readers who benefit from accessible texts.

## Dataset Description

<!-- START-DESC-STATS -->
- **Number of samples**: 496.54K
- **Number of tokens (Llama 3)**: 10.50M
- **Average document length in tokens (min, max)**: 21.14 (2, 435)
<!-- END-DESC-STATS -->

## Dataset Structure

<!-- START-SAMPLE -->
```py
{
  "id": "attasidor_00000001",
  "text": "Det är omkring 500 kronor\ni månaden.",
  "source": "attasidor",
  "added": "2026-10-23",
  "created": "2016-04-01, 2016-04-01",
  "token_count": 16
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

### Dataset Statistics

<!-- START-DATASET PLOTS -->
<p align="center">
<img src="./images/dist_document_length.png" width="600" style="margin-right: 10px;" />
</p>
<!-- END-DATASET PLOTS -->

## Additional Information

### Source

Språkbanken Text’s [8 Sidor](https://spraakbanken.gu.se/en/resources/attasidor) corpus. DOI: [10.23695/f6ds-f045](https://doi.org/10.23695/f6ds-f045).

### Citation Information

Språkbanken (2025). 8 Sidor (updated: 2025-12-01). [Data set]. Enriched and distributed by Språkbanken. https://doi.org/10.23695/f6ds-f045

### Limitations

The source sentences are shuffled, so surrounding context and document order are unavailable. Spacing is approximated where the source provides only word tokens. Dates follow the source metadata.

## License Information

Språkbanken Text distributes this corpus under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

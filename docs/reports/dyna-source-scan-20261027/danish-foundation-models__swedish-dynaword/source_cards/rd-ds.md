---
pretty_name: "Riksdagens \xF6ppna data: Departementsserien"
language:
- sv
license: cc-by-4.0
license_name: CC-BY 4.0
size_categories:
- 1K<n<10K
task_categories:
- text-generation
- fill-mask
task_ids:
- language-modeling
source_datasets:
- original
domains:
- Report
---

# Dataset Card for Riksdagens öppna data: Departementsserien

<!-- START-SHORT DESCRIPTION -->
Ministry reports from [Riksdagens öppna data](https://spraakbanken.gu.se/en/resources/rd-ds).
<!-- END-SHORT DESCRIPTION -->

Reports in Departementsserien on government policy and proposed legislation.

## Dataset Description

<!-- START-DESC-STATS -->
- **Number of samples**: 1.40K
- **Number of tokens (Llama 3)**: 106.37M
- **Average document length in tokens (min, max)**: 75.87K (7, 865.06K)
<!-- END-DESC-STATS -->

## Dataset Structure

<!-- START-SAMPLE -->
```py
{
  "id": "rd-ds_00000001",
  "text": "97 9 AVSLUTANDE SYNPUNKTER Forskningenom offentlig tjänsteproduktionbefinnersig ännu i ett in- ledan[...]",
  "source": "rd-ds",
  "added": "2026-10-18",
  "created": "1992-01-01, 1992-01-01",
  "token_count": 1413
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

Språkbanken Text’s [Riksdagens öppna data: Departementsserien](https://spraakbanken.gu.se/en/resources/rd-ds) corpus. DOI: [10.23695/yc3t-mg58](https://doi.org/10.23695/yc3t-mg58).

### Citation Information

Språkbanken (2022). Riksdagens öppna data: Departementsserien (updated: 2022-09-06). [Data set]. Enriched and distributed by Språkbanken. https://doi.org/10.23695/yc3t-mg58

### Limitations

Spacing is approximated where the source provides only word tokens. Dates follow the source metadata.

## License Information

Språkbanken Text distributes this corpus under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

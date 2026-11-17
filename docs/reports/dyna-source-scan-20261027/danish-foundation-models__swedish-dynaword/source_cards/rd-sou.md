---
pretty_name: "Riksdagens \xF6ppna data: Statens offentliga utredningar"
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

# Dataset Card for Riksdagens öppna data: Statens offentliga utredningar

<!-- START-SHORT DESCRIPTION -->
Government inquiry reports from [Riksdagens öppna data](https://spraakbanken.gu.se/en/resources/rd-sou).
<!-- END-SHORT DESCRIPTION -->

Reports from government commissions on public policy and proposed reforms.

## Dataset Description

<!-- START-DESC-STATS -->
- **Number of samples**: 3.71K
- **Number of tokens (Llama 3)**: 575.76M
- **Average document length in tokens (min, max)**: 154.98K (4, 799.62K)
<!-- END-DESC-STATS -->

## Dataset Structure

<!-- START-SAMPLE -->
```py
{
  "id": "rd-sou_00000001",
  "text": "SOU 1998:44 185 10 Förvaring 10.1De allmänna förvaringsbestämmelserna 10.1.1Gällande rätt I 1973 års[...]",
  "source": "rd-sou",
  "added": "2026-10-18",
  "created": "1999-01-01, 1999-01-01",
  "token_count": 110756
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

Språkbanken Text’s [Riksdagens öppna data: Statens offentliga utredningar](https://spraakbanken.gu.se/en/resources/rd-sou) corpus. DOI: [10.23695/9tff-ay21](https://doi.org/10.23695/9tff-ay21).

### Citation Information

Språkbanken (2024). Riksdagens öppna data: Statens offentliga utredningar (updated: 2024-01-11). [Data set]. Enriched and distributed by Språkbanken. https://doi.org/10.23695/9tff-ay21

### Limitations

OCR errors may remain in digitized texts. Spacing is approximated where the source provides only word tokens. Dates follow the source metadata.

## License Information

Språkbanken Text distributes this corpus under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

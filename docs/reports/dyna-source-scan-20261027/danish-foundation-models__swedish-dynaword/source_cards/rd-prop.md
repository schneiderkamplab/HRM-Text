---
pretty_name: "Riksdagens \xF6ppna data: Proposition"
language:
- sv
license: cc-by-4.0
license_name: CC-BY 4.0
size_categories:
- 10K<n<100K
task_categories:
- text-generation
- fill-mask
task_ids:
- language-modeling
source_datasets:
- original
domains:
- Legal
---

# Dataset Card for Riksdagens öppna data: Proposition

<!-- START-SHORT DESCRIPTION -->
Government bills and letters from [Riksdagens öppna data](https://spraakbanken.gu.se/en/resources/rd-prop).
<!-- END-SHORT DESCRIPTION -->

Proposed legislation and government communications to the Swedish parliament.

## Dataset Description

<!-- START-DESC-STATS -->
- **Number of samples**: 11.01K
- **Number of tokens (Llama 3)**: 852.65M
- **Average document length in tokens (min, max)**: 77.46K (3, 4.24M)
<!-- END-DESC-STATS -->

## Dataset Structure

<!-- START-SAMPLE -->
```py
{
  "id": "rd-prop_00000001",
  "text": "Kungl. Maj:tsproposition nr 117 år 1973        Prop.1973:117 Nr 117 Kungl.Maj:ts proposition angåend[...]",
  "source": "rd-prop",
  "added": "2026-10-18",
  "created": "1973-12-31, 1973-12-31",
  "token_count": 35688
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

Språkbanken Text’s [Riksdagens öppna data: Proposition](https://spraakbanken.gu.se/en/resources/rd-prop) corpus. DOI: [10.23695/9rtb-tx57](https://doi.org/10.23695/9rtb-tx57).

### Citation Information

Språkbanken (2022). Riksdagens öppna data: Proposition (updated: 2022-10-12). [Data set]. Enriched and distributed by Språkbanken. https://doi.org/10.23695/9rtb-tx57

### Limitations

OCR errors may remain in digitized texts. Spacing is approximated where the source provides only word tokens. Dates follow the source metadata. Texts without source dates are omitted.

## License Information

Språkbanken Text distributes this corpus under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

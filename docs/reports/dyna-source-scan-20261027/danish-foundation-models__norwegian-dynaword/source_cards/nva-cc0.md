---
pretty_name: NVA CC0
language:
- nob
- nno
- nor
license: cc0-1.0
license_name: CC-0
task_categories:
- text-generation
task_ids:
- language-modeling
source_datasets:
- original
domains:
- Report
---

# Dataset Card for NVA CC0

<!-- START-SHORT DESCRIPTION -->
Norwegian research texts from [NVA](https://nva.sikt.no/).
<!-- END-SHORT DESCRIPTION -->

This dataset contains theses, research articles, reports, and other academic texts from Norwegian institutions.

## Dataset Description

<!-- START-DESC-STATS -->
- **Number of samples**: 98
- **Number of tokens (Llama 3)**: 3.98M
- **Average document length in tokens (min, max)**: 40.66K (223, 142.52K)
<!-- END-DESC-STATS -->

### Source

The texts come from Sikt's Norwegian Research Information Repository (NVA), mainly through [Danish Foundation Models' NVA text release](https://huggingface.co/datasets/danish-foundation-models/nasjonalt-vitenarkiv). NVA marks the publications as Norwegian and their files as CC0 1.0.

## Dataset Structure

<!-- START-SAMPLE -->
```py
{
  "id": "nva-cc0_010a1538-8350-4718-a89b-7e10cbb84b8d",
  "text": "Fra pilot til implementering?\n\n# **Morgendagens sykehjem**\n\n- fra pilot til implementering?\n\n# **Mor[...]",
  "source": "nva-cc0",
  "added": "2026-10-13",
  "created": "2016-01-01, 2016-12-31",
  "token_count": 24730
}
```

### Data Fields

An entry in the dataset consists of the following fields:

- `id` (`str`): A unique identifier for each document.
- `text` (`str`): The content of the document.
- `source` (`str`): The source of the document (see [Source](#source)).
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

### License Information

NVA lists the included texts under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). The original publications and author information are available through [NVA](https://nva.sikt.no/).

### Limitations

PDF reading order, tables, and OCR may be imperfect. Documents with too little extractable text are excluded. The collection reflects NVA's language and license records and may include passages in other languages.

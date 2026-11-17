---
pretty_name: NVA CC BY-SA
language:
- nob
- nno
- nor
license: cc-by-sa-4.0
license_name: CC-BY-SA 4.0
task_categories:
- text-generation
task_ids:
- language-modeling
source_datasets:
- original
domains:
- Report
---

# Dataset Card for NVA CC BY-SA

<!-- START-SHORT DESCRIPTION -->
Norwegian research texts from [NVA](https://nva.sikt.no/).
<!-- END-SHORT DESCRIPTION -->

This dataset contains theses, research articles, reports, and other academic texts from Norwegian institutions.

## Dataset Description

<!-- START-DESC-STATS -->
- **Number of samples**: 572
- **Number of tokens (Llama 3)**: 21.58M
- **Average document length in tokens (min, max)**: 37.73K (142, 585.65K)
<!-- END-DESC-STATS -->

### Source

The texts come from public PDF attachments in Sikt's Norwegian Research Information Repository (NVA). NVA marks the publications as Norwegian and their files as CC BY-SA 4.0.

## Dataset Structure

<!-- START-SAMPLE -->
```py
{
  "id": "nva-cc-by-sa_ee99cfcc-0761-4d90-b081-a16d09531d11",
  "text": "(CC BY­SA 4.0)\n\nAslaug Vaa og den moderne sonetten\n\nJan Inge Sørbø\n\nInnleiing\n\nAslaug Vaa (1889–1965[...]",
  "source": "nva-cc-by-sa",
  "added": "2026-10-13",
  "created": "2026-01-01, 2026-12-31",
  "token_count": 12666
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

NVA lists the included texts under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). The original publications and author information are available through [NVA](https://nva.sikt.no/).

### Limitations

PDF reading order, tables, and line breaks may be imperfect. Documents with too little extractable text are excluded. The collection reflects NVA's language and license records and may include passages in other languages.

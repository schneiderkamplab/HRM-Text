---
pretty_name: Swedish-PD
language:
- sv
license: other
license_name: Public domain
size_categories:
- 1K<n<10K
task_categories:
- text-generation
- fill-mask
task_ids:
- language-modeling
source_datasets:
- PleIAs/Swedish-PD
domains:
- Books
- News
---

# Dataset Card for Swedish-PD

<!-- START-SHORT DESCRIPTION -->
Public-domain books and periodicals from [PleIAs](https://huggingface.co/datasets/PleIAs/Swedish-PD).
<!-- END-SHORT DESCRIPTION -->

Swedish historical literature, scholarly works, newspapers and other periodicals digitised by libraries and cultural heritage institutions.

## Dataset Description

<!-- START-DESC-STATS -->
- **Number of samples**: 4.43K
- **Number of tokens (Llama 3)**: 1.05B
- **Average document length in tokens (min, max)**: 236.65K (2, 4.45M)
<!-- END-DESC-STATS -->

## Dataset Structure

<!-- START-SAMPLE -->
```py
{
  "id": "swedish-pd_000001",
  "text": "Biblioteket \nTO \n\n\nCKHOLM \n\n\nMA NERTD \n\n\nAF \n\n\nLorp BYRON. \n\n\n——— ——— \n\n\nÖfversättn ing \naf \n\n\nJon. [...]",
  "source": "swedish-pd",
  "added": "2026-10-25",
  "created": "1826-01-01, 1826-12-31",
  "token_count": 23769
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

All four Parquet files from [PleIAs/Swedish-PD](https://huggingface.co/datasets/PleIAs/Swedish-PD), collected from Internet Archive and European libraries.

### Limitations

OCR errors, historical spelling and scanning notices remain. Some records contain only short fragments. Dates are catalogue publication years and can refer to a series rather than an individual volume. Some works also appear in other Dynaword subsets.

## License Information

PleIAs describes the collection as public domain and permits reuse and redistribution.

---
pretty_name: 'The Swedish Literature Bank: Restricted Works'
language:
- sv
license: cc-by-4.0
license_name: CC-BY 4.0
size_categories:
- 1M<n<10M
task_categories:
- text-generation
- fill-mask
task_ids:
- language-modeling
source_datasets:
- original
domains:
- Books
---

# Dataset Card for The Swedish Literature Bank: Restricted Works

<!-- START-SHORT DESCRIPTION -->
Scrambled sentences from [Litteraturbanken’s protected works](https://sprakbanken.se/resurser/lb-restricted).
<!-- END-SHORT DESCRIPTION -->

Swedish literary works and related essays, commentary and translations from Litteraturbanken.

## Dataset Description

<!-- START-DESC-STATS -->
- **Number of samples**: 6.29M
- **Number of tokens (Llama 3)**: 299.45M
- **Average document length in tokens (min, max)**: 47.6 (2, 56.71K)
<!-- END-DESC-STATS -->

## Dataset Structure

<!-- START-SAMPLE -->
```py
{
  "id": "lb-restricted_00000001",
  "text": "Strålkastarna slocknade bort, scenen sjönk ned till\ndansgolv, mörka gossar från Trinidad spelade vil[...]",
  "source": "lb-restricted",
  "added": "2026-10-25",
  "created": "1967-01-01, 1967-12-31",
  "token_count": 50
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

Språkbanken Text’s sentence-scrambled release of *The Swedish Literature Bank: Restricted Works*. [Source page](https://sprakbanken.se/resurser/lb-restricted). DOI: [10.23695/ma34-gh02](https://doi.org/10.23695/ma34-gh02).

### Citation Information

Språkbanken (2023). The Swedish Literature Bank: Restricted Works (updated: 2023-10-28). [Data set]. Enriched and distributed by Språkbanken. https://doi.org/10.23695/ma34-gh02

### Limitations

Sentences are scrambled, so surrounding context is unavailable. OCR errors and historical spelling remain. Source dates can refer to the edition rather than the original work; missing dates use years from titles or bibliographic records.

## License Information

Språkbanken Text labels the downloadable scrambled corpus [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

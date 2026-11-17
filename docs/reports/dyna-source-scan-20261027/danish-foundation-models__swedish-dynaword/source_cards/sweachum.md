---
pretty_name: 'Academic texts: Humanities'
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
- Academic Writing
---

# Dataset Card for Academic texts: Humanities

<!-- START-SHORT DESCRIPTION -->
Academic sentences in the [humanities](https://spraakbanken.gu.se/en/resources/sweachum).
<!-- END-SHORT DESCRIPTION -->

Swedish academic writing in the humanities, collected and distributed by Språkbanken Text.

## Dataset Description

<!-- START-DESC-STATS -->
- **Number of samples**: 611.26K
- **Number of tokens (Llama 3)**: 26.83M
- **Average document length in tokens (min, max)**: 43.89 (2, 11.80K)
<!-- END-DESC-STATS -->

## Dataset Structure

<!-- START-SAMPLE -->
```py
{
  "id": "sweachum_00000001",
  "text": "I studien har frågan om protomusikalitet avgränsats till att i första hand handla om musikalisk stäm[...]",
  "source": "sweachum",
  "added": "2026-10-19",
  "created": "2012-01-01, 2012-12-31",
  "token_count": 36
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

Språkbanken Text’s [Academic texts: Humanities](https://spraakbanken.gu.se/en/resources/sweachum) corpus. DOI: [10.23695/fzgk-fj93](https://doi.org/10.23695/fzgk-fj93).

### Citation Information

Språkbanken (2017). Academic texts: Humanities (updated: 2017-05-19). [Data set]. Enriched and distributed by Språkbanken. https://doi.org/10.23695/fzgk-fj93

### Limitations

Identical sentences appear once within this subset.

The source sentences are shuffled, so surrounding context and document order are unavailable. Spacing is approximated where the source provides only word tokens. Dates follow the source metadata. English passages, references, and text extraction errors remain. Sentences without a publication date use the broad range 1996–2013 from the [published corpus description](https://gupea.ub.gu.se/server/api/core/bitstreams/4fa93988-d2e9-4228-be85-117d4003d5a7/content).

## License Information

Språkbanken Text distributes this corpus under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

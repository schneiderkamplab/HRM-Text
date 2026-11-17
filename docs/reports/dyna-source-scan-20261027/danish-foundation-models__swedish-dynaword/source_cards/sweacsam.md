---
pretty_name: 'Academic texts: Social science'
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

# Dataset Card for Academic texts: Social science

<!-- START-SHORT DESCRIPTION -->
Academic sentences in the [social sciences](https://spraakbanken.gu.se/en/resources/sweacsam).
<!-- END-SHORT DESCRIPTION -->

Swedish academic writing in the social sciences, collected and distributed by Språkbanken Text.

## Dataset Description

<!-- START-DESC-STATS -->
- **Number of samples**: 464.72K
- **Number of tokens (Llama 3)**: 20.06M
- **Average document length in tokens (min, max)**: 43.18 (2, 8.47K)
<!-- END-DESC-STATS -->

## Dataset Structure

<!-- START-SAMPLE -->
```py
{
  "id": "sweacsam_00000001",
  "text": "Man uppfattade ett hot mot både företagsidén och konstidén och musikföretagarna agerade på olika sät[...]",
  "source": "sweacsam",
  "added": "2026-10-19",
  "created": "2007-01-01, 2007-12-31",
  "token_count": 44
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

Språkbanken Text’s [Academic texts: Social science](https://spraakbanken.gu.se/en/resources/sweacsam) corpus. DOI: [10.23695/195e-ye66](https://doi.org/10.23695/195e-ye66).

### Citation Information

Språkbanken (2017). Academic texts: Social science (updated: 2017-06-07). [Data set]. Enriched and distributed by Språkbanken. https://doi.org/10.23695/195e-ye66

### Limitations

Identical sentences appear once within this subset.

The source sentences are shuffled, so surrounding context and document order are unavailable. Spacing is approximated where the source provides only word tokens. Dates follow the source metadata. English passages, references, and text extraction errors remain.

## License Information

Språkbanken Text distributes this corpus under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

---
pretty_name: Swedish Gutenberg
language:
- sv
license: other
license_name: Unrestricted under US copyright law
license_link: https://www.gutenberg.org/policy/license.html
size_categories:
- n<1K
task_categories:
- text-generation
- fill-mask
task_ids:
- language-modeling
source_datasets:
- original
domains:
- Books
- News
---

# Dataset Card for Swedish Gutenberg

<!-- START-SHORT DESCRIPTION -->
Swedish-language books from [Project Gutenberg](https://www.gutenberg.org/).
<!-- END-SHORT DESCRIPTION -->

Swedish fiction, poetry, plays, essays, reference works, and periodicals.

## Dataset Description

<!-- START-DESC-STATS -->
- **Number of samples**: 257
- **Number of tokens (Llama 3)**: 23.90M
- **Average document length in tokens (min, max)**: 93.01K (1.03K, 1.60M)
<!-- END-DESC-STATS -->

## Dataset Structure

<!-- START-SAMPLE -->
```py
{
  "id": "gutenberg_2100",
  "text": "BIBELN\n\neller\n\nDEN HELIGA SKRIFT\n\ninnehållande\n\nGAMLA OCH NYA TESTAMENTETS\n\nKANONISKA BÖCKER\n\n\n\n\nINN[...]",
  "source": "gutenberg",
  "added": "2026-10-24",
  "created": "1700-01-01, 2026-12-31",
  "token_count": 1603549
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

[Project Gutenberg](https://www.gutenberg.org/) ebooks listed as Swedish in [Gutendex](https://gutendex.com/), including multilingual books.

### Limitations

Historical spelling, transcription errors, editorial notes, and passages in other languages remain. `created` approximates the first listed author’s lifetime, from birth year to death year. When usable author dates are unavailable, it uses `1700-01-01, 2026-12-31`, following Norwegian Dynaword. These ranges are not publication dates.

## License Information

The source identifies these texts as unrestricted under US copyright law. Their copyright status in other countries may differ. See the [source terms](https://www.gutenberg.org/policy/license.html).

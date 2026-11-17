---
pretty_name: "Wiktionary (Bokm\xE5l)"
language:
- nob
license: cc-by-sa-4.0
license_name: CC-BY-SA 4.0
task_categories:
- text-generation
- fill-mask
task_ids:
- language-modeling
domains:
- Encyclopedic
---

# Dataset Card for Wiktionary (Bokmål)

<!-- START-SHORT DESCRIPTION -->
Dictionary entries from [Bokmål Wiktionary](https://no.wiktionary.org/).
<!-- END-SHORT DESCRIPTION -->

Short dictionary entries with definitions, examples, etymologies and translations. The dictionary describes words from Norwegian and other languages.

## Dataset Description

<!-- START-DESC-STATS -->
- **Number of samples**: 68.31K
- **Number of tokens (Llama 3)**: 2.10M
- **Average document length in tokens (min, max)**: 30.74 (4, 7.59K)
<!-- END-DESC-STATS -->

### Source

The [Wikimedia dump from 1 July 2026](https://dumps.wikimedia.org/nowiktionary/20260701/). Each entry contains one page. The `created` field records the page's last revision date. Original pages and their edit histories can be found at `https://no.wiktionary.org/?curid=PAGE_ID`, using the numeric part of the record ID.

## Dataset Structure

<!-- START-SAMPLE -->
```py
{
  "id": "wiktionary-nob_680",
  "text": "stol\n* 1)  et møbel som én person kan sitte på\n * Sett frem en stol til gjesten, er du snill!\n * 1) [...]",
  "source": "wiktionary-nob",
  "added": "2026-07-20",
  "created": "2024-02-13, 2024-02-13",
  "token_count": 659
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

## License Information

Text is published under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Credit the [Wiktionary (Bokmål)](https://no.wiktionary.org/) contributors and retain the license when sharing adapted text.

### Limitations

Because dictionary entries are inherently short and formulaic (headword, part of speech, short gloss, sometimes translation tables), this source contributes far less linguistic diversity per token than free-form prose sources in this collection. Some noise from residual wikicode table/translation-box formatting may remain in the text.

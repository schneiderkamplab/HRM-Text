---
pretty_name: Wikisource
language:
- sv
license: cc-by-sa-4.0
license_name: CC BY-SA 4.0
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
- Books
- Legal
---

# Dataset Card for Wikisource

<!-- START-SHORT DESCRIPTION -->
Literature and historical documents from [Swedish Wikisource](https://sv.wikisource.org/).
<!-- END-SHORT DESCRIPTION -->

Wikisource is a library of source texts maintained by volunteers. Its Swedish collection includes prose, poetry, letters, laws and other historical documents, providing material for studying Swedish language and history.

## Dataset Description

<!-- START-DESC-STATS -->
- **Number of samples**: 20.32K
- **Number of tokens (Llama 3)**: 10.74M
- **Average document length in tokens (min, max)**: 528.57 (11, 470.87K)
<!-- END-DESC-STATS -->

## Dataset Structure
An example from the dataset looks as follows.

<!-- START-SAMPLE -->
```py
{
  "id": "wikisource_2",
  "text": "Regeringsform 1634\nVi efterskrefne Sveriges rikes råd och ständer, grefver, friherrer, biskoper, rid[...]",
  "source": "wikisource",
  "added": "2026-10-25",
  "created": "2025-10-03, 2025-10-03",
  "token_count": 25097
}
```

### Data Fields

An entry in the dataset consists of the following fields:

- `id` (`str`): A unique identifier for each document.
- `text` (`str`): The content of the document.
- `source` (`str`): The source of the document (see [Source](#source)).
- `added` (`str`): The date when the document was added to this collection.
- `created` (`str`): The page revision date recorded in the dump.
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

The main-namespace pages in Wikimedia's [Swedish Wikisource dump of 1 October 2026](https://dumps.wikimedia.org/svwikisource/20261001/).

### Parser choice

The original contributor selected [wtf_wikipedia](https://github.com/spencermountain/wtf_wikipedia) after comparing several parsers. It handles links, templates and image markup to reduce leftover wiki syntax and formatting instructions in the text.

### Limitations

Historical spelling and transcription errors remain. Text included from other wiki pages is not expanded, so some entries are incomplete or absent. The `created` field records the page's last revision date in the dump, not the original work's publication date.

## License Information

Wikisource contains public-domain works and freely licensed texts. Its site terms use CC BY-SA 4.0, with additional terms where indicated; see [Swedish Wikisource's copyright policy](https://sv.wikisource.org/wiki/Wikisource:Upphovsr%C3%A4tt). The number after `wikisource_` in each sample ID is the source page ID, accessible at `https://sv.wikisource.org/?curid=PAGE_ID`.

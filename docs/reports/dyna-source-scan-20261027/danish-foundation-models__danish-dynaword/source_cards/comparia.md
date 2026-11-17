---
pretty_name: ComparIA Danish queries
language:
- da
license: other
license_name: Etalab 2.0
license_link: https://github.com/etalab/licence-ouverte/blob/master/open-licence.md
size_categories:
- n<1K
task_categories:
- text-generation
task_ids:
- language-modeling
source_datasets:
- ministere-culture/comparia-conversations
domains:
- Conversation
---

# Dataset Card for ComparIA Danish queries

<!-- START-SHORT DESCRIPTION -->
Danish user queries from [ComparIA](https://huggingface.co/datasets/ministere-culture/comparia-conversations).
<!-- END-SHORT DESCRIPTION -->

Each document is a Danish question or follow-up from the French Ministry of Culture's ComparIA platform. Model replies and user identifiers are excluded.

## Dataset Description

<!-- START-DESC-STATS -->
- **Number of samples**: 51
- **Number of tokens (Llama 3)**: 1.35K
- **Average document length in tokens (min, max)**: 26.55 (5, 182)
<!-- END-DESC-STATS -->

## Dataset Structure

<!-- START-SAMPLE -->
```py
{
  "id": "comparia_521599_a_0",
  "text": "Hvad hedder Danmarks statsminister?",
  "source": "comparia",
  "added": "2026-10-25",
  "created": "2025-05-20, 2025-05-20",
  "token_count": 12
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

## License Information

The French Ministry of Culture publishes [comparia-conversations](https://huggingface.co/datasets/ministere-culture/comparia-conversations#licenses) under [Etalab Open Licence 2.0](https://github.com/etalab/licence-ouverte/blob/master/open-licence.md). It permits copying, adaptation, redistribution, and commercial reuse with attribution to the source and its latest update date.

Attribution: Ministère de la Culture (SNUM), ComparIA conversations, source updated 19 May 2026. This subset uses [revision 675c8a6](https://huggingface.co/datasets/ministere-culture/comparia-conversations/tree/675c8a6c91f3d8bd8effede407e3366f43b9026b).

The source card reserves potential third-party rights in model outputs. This subset contains user messages only; it does not redistribute those outputs.

## Additional Information

### Source Data

- [ComparIA conversations on Hugging Face](https://huggingface.co/datasets/ministere-culture/comparia-conversations)
- [ComparIA platform](https://comparia.beta.gouv.fr/)

### Limitations

Only conversations tagged exclusively as Danish in the source are included. Language labels can be imperfect, and Danish messages in multilingual conversations are omitted. Short follow-up queries can depend on earlier questions or replies that are not part of the same document. Repeated and empty queries are removed.

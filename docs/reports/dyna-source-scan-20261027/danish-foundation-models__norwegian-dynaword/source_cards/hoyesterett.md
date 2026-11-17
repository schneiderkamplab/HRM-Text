---
pretty_name: Høyesterett
language:
- nob
- nno
license: other
license_name: Norwegian Copyright Act §14
task_categories:
- text-generation
task_ids:
- language-modeling
source_datasets:
- original
domains:
- Legal
---

# Dataset Card for Høyesterett

<!-- START-SHORT DESCRIPTION -->
Court decisions from [Høyesterett](https://www.domstol.no/no/hoyesterett/avgjorelser/).
<!-- END-SHORT DESCRIPTION -->

Judgments, orders and decisions from Norway’s Supreme Court and its appeals committee, covering civil and criminal cases.

## Dataset Description

<!-- START-DESC-STATS -->
- **Number of samples**: 5.16K
- **Number of tokens (Llama 3)**: 29.82M
- **Average document length in tokens (min, max)**: 5.78K (285, 52.92K)
<!-- END-DESC-STATS -->

### Source

The original Norwegian decisions published in [Høyesterett’s official archive](https://www.domstol.no/no/hoyesterett/avgjorelser/), collected on 15 October 2026. Each entry contains the text published for one decision.

## Dataset Structure

<!-- START-SAMPLE -->
```py
{
  "id": "hoyesterett-decision-0b36b361a1",
  "text": "NORGES HØYESTERETT\n\nDen 15. januar 2004 avsa Høyesterett dom i\n\nNH-2004-0079-A, (sak nr. 2003/782), [...]",
  "source": "hoyesterett",
  "added": "2026-10-15",
  "created": "2004-01-15, 2004-01-15",
  "token_count": 3774
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

Court decisions are not protected by copyright under [section 14 of the Norwegian Copyright Act](https://lovdata.no/lov/2018-06-15-40/§14). The texts come directly from the court. Restrictions on public disclosure and rights in separately quoted works may still apply.

### Limitations

Coverage follows the decisions available on the court’s website. Some older web entries contain only part of a decision. Text extraction from PDFs may contain errors.

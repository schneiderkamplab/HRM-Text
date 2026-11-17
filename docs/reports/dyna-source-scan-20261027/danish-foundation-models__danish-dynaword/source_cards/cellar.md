---
pretty_name: Cellar
language:
- da
license: cc-by-sa-4.0
license_name: CC-BY-SA 4.0
task_categories:
- text-generation
- fill-mask
task_ids:
- language-modeling
domains:
- Legal
---

# Dataset Card for Cellar

<!-- START-SHORT DESCRIPTION -->
The official digital repository for European Union legal documents and open data.
<!-- END-SHORT DESCRIPTION -->

The EU Dataset [Cellar](https://op.europa.eu/en/web/cellar/home) serves as the central access point for all official EU publications, legislation, and open data resources. Maintained by the Publications Office of the European Union, this comprehensive digital archive contains millions of documents in multiple languages, including regulations, directives, decisions, treaties, case law, and preparatory acts dating back decades. The repository employs standardized metadata and unique identifiers to organize its vast collection, making it an essential resource for researchers, legal professionals, policymakers, and citizens seeking authoritative information on EU law and policy. The Cellar's linked data architecture also enables sophisticated search capabilities and integration with other information systems across the European Union's digital landscape.


## Dataset Description

<!-- START-DESC-STATS -->
- **Number of samples**: 619.25K
- **Number of tokens (Llama 3)**: 6.15B
- **Average document length in tokens (min, max)**: 9.93K (2, 3.71M)
<!-- END-DESC-STATS -->


## Dataset Structure
An example from the dataset looks as follows.


<!-- START-SAMPLE -->
```py
{
  "id": "cellar_1280871",
  "text": "**Dette dokument er et dokumentationsredskab, og institutionerne påtager sig intet ansvar herfor**\n\n[...]",
  "source": "cellar",
  "added": "2026-07-12",
  "created": "2010-05-10, 2010-05-10",
  "token_count": 84334
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

### Annotation Overview
<!-- START-ANNOTATION PLOTS -->
Each document comes with annotations describing its content, such as content quality, information density, and educational value.
Each bar shows the share of documents at each level of one annotation, from worst (light) to best (dark).
To learn more about the annotations and how to use them, see the [annotations section](https://huggingface.co/datasets/danish-foundation-models/danish-dynaword#annotations) of the main readme.

<p align="center">
<img src="./images/annotation_profile.png" width="700" style="margin-right: 10px;" />
</p>
<!-- END-ANNOTATION PLOTS -->




## Additional Information

### License Information

Data is licensed under the [Attribution-ShareAlike 4.0 International license](https://creativecommons.org/licenses/by-sa/4.0/). Thus, attribution is required when using this data.

### Citation Information

No citation is applicable for this work.

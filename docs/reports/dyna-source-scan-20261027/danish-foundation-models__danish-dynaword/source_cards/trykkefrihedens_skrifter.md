---
pretty_name: Trykkefrihedens Skrifter
language:
- da
license: other
license_name: Public domain
task_categories:
- text-generation
- fill-mask
task_ids:
- language-modeling
domains:
- Books
---

# Dataset Card for Trykkefrihedens Skrifter

<!-- START-SHORT DESCRIPTION -->
Pamphlets from the press freedom period 1770-1773, from the Royal Danish Library's [Trykkefrihedens Skrifter](https://tekster.kb.dk/tfs).
<!-- END-SHORT DESCRIPTION -->

On 14 September 1770 Christian 7. and Struensee abolished censorship in Denmark-Norway. Over the following three years, people of all ranks published a flood of pamphlets on everything from grain prices, guilds and the university to the queen, Struensee's fall and his execution. They were collected as they appeared, and the collection of about 1,000 writings, bound in 46 volumes, is today known as Trykkefrihedens Skrifter.

The dataset contains one document per pamphlet. It includes *Fortegnelsen over Trykkefrihedens Skrifter*, a contemporary review journal of the pamphlets, which the library treats as part of the collection.

## Dataset Description

<!-- START-DESC-STATS -->
- **Number of samples**: 988
- **Number of tokens (Llama 3)**: 9.46M
- **Average document length in tokens (min, max)**: 9.57K (142, 173.13K)
<!-- END-DESC-STATS -->

### Dataset Sources

The texts were downloaded from the Royal Danish Library's open access repository LOAR, collection [Freedom of Press Writings (Trykkefrihedens Skrifter)](https://loar.kb.dk/collections/4002ea75-53d6-44f8-b0ee-0f1a88ac76ee), version 2.00 (2021). The library scanned the volumes, ran OCR and then manually proofread most of the result. Titles and publication years come from each pamphlet's page on the library's text portal, [tekster.kb.dk/tfs](https://tekster.kb.dk/tfs), and are listed in [registry.csv](registry.csv).


## Dataset Structure
An example from the dataset looks as follows.

<!-- START-SAMPLE -->
```py
{
  "id": "trykkefrihedens_skrifter_1_001_001",
  "text": "Philopatreias\ntrende\nAnmærkninger\nI. Om de dyre Tider og Handelens\nSvaghed.\n2. Om Rettergang.\n3. Om [...]",
  "source": "trykkefrihedens_skrifter",
  "added": "2026-10-06",
  "created": "1770-01-01, 1770-12-31",
  "token_count": 12034
}
```

### Data Fields

An entry in the dataset consists of the fields:

- `id` (`str`): A unique identifier for each document.
- `text` (`str`): The content of the document.
- `source` (`str`): The source of the document (see [Source Data](#source-data)).
- `added` (`str`): The date when the document was added to this collection.
- `created` (`str`): The date range when the document was originally created.
- `token_count` (`int`): The number of tokens in the sample computed using the Llama 3 tokenizer.
<!-- END-SAMPLE -->

The last part of the `id` gives series, volume and pamphlet number, e.g. `trykkefrihedens_skrifter_1_001_001` is the first pamphlet in volume 1 of series 1. Series 3 is the quarto volume and series 4 is *Fortegnelsen*.

### Dataset Statistics

<!-- START-DATASET PLOTS -->
<p align="center">
<img src="./images/dist_document_length.png" width="600" style="margin-right: 10px;" />
</p>
<!-- END-DATASET PLOTS -->

## License Information

The Royal Danish Library states that the entire collection is in the public domain and free of known restrictions under copyright law ([Public Domain Mark 1.0](https://creativecommons.org/publicdomain/mark/1.0/)).

## Additional Information

### Limitations

- **OCR quality varies.** Most of the text was proofread by the library, but the German pamphlets seem not to have been. The originals are printed in a mix of fraktur and antiqua.
- **Line breaks follow the printed page.** Each printed line is a line in the text, so sentences in prose are broken mid-sentence, while verse keeps line structure. Words hyphenated across lines are rejoined. Pages are separated by a blank line; paragraphs are not marked.
- **Handwritten items are left out.** Eight items are handwritten and their OCR output is unreadable; these and two items without text are not included.
- **Some dates are approximate.** `created` is the year of publication. Years the library has inferred are used as given. Pamphlets without a year are given the range of the whole collection, `1770-01-01, 1775-12-31`.
- **Texts reflect their time.** The pamphlets are polemical and include libel, obscenity, and antisemitic and misogynistic material.

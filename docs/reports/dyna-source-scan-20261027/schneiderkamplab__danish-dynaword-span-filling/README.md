---
license: apache-2.0
language:
- da
tags:
- instruction-tuning
- chat
- danish
- dynaword
pretty_name: danish-dynaword-span-filling
---

# danish-dynaword-span-filling

Chat-template-ready Danish span filling examples derived from DynaWord. This upload contains only judge-accepted rows from a larger generated DynaWord export.

## Contents

- Format: gzip-compressed JSON Lines under `data/*.jsonl.gz`
- Schema: `{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}`
- Files: `2`
- Rows: `54,968`
- Task: Danish span filling

## Sources

Accepted rows by source family:

| Source family | Accepted rows |
|---|---:|
| [`danish-foundation-models/danish-dynaword`](https://huggingface.co/datasets/danish-foundation-models/danish-dynaword) | 54,968 |

Effective source files:

| Source file | Accepted rows |
|---|---:|
| `data/adl/adl.parquet` | 29,232 |
| `data/ai-aktindsigt/ai-aktindsigt.parquet` | 25,736 |

## Example

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Gendan teksten ved at udfylde de manglende dele. Han var Far til Margrethe og skulde have Aftægt af Gaarden; skjønt han havde afstaaet Ejendommen til Mads Søndergaard, havde han stadig megen Magt og maatte omgaas som et raaddent Æg, thi tog han hele den lovformelig fastsatte Aftægt, kunde Mads komme til at sidde haardt nok i det, for han var ulykkeligvis ikke blandt de velbeslaaede i Engkjær, Det gjaldt da <mask_2> den gamle under Øjne <mask_3> havde tilranet sig Børnenes Opdragelse, og ogsaa Jens faldt ind under hans Tugts Ris. Drengen næred en uhyre Rædsel for den visne Olding, der altid <mask_1> havde aldrig kunnet glemme den fr"
    },
    {
      "role": "assistant",
      "content": "Han var Far til Margrethe og skulde have Aftægt af Gaarden; skjønt han havde afstaaet Ejendommen til Mads Søndergaard, havde han stadig megen Magt og maatte omgaas som et raaddent Æg, thi tog han hele den lovformelig fastsatte Aftægt, kunde Mads komme til at sidde haardt nok i det, for han var ulykkeligvis ikke blandt de velbeslaaede i Engkjær, Det gjaldt da om at gaa den gamle under Øjne og finde sig i hans daglige Overgreb. Han havde tilranet sig Børnenes Opdragelse, og ogsaa Jens faldt ind under hans Tugts Ris. Drengen næred en uhyre Rædsel for den visne Olding, der altid stank af Løg og Brændevin, han havde aldrig kunnet glemme den fr"
    }
  ]
}
```

## Filtering

Rows were judged with [`google/gemma-4-31B-it`](https://huggingface.co/google/gemma-4-31B-it).

| Outcome | Rows |
|---|---:|
| Audited | 56,315 |
| Accepted/uploaded | 54,968 |
| Rejected | 1,347 |

Main rejection reasons: response-mismatch, incoherent-or-ocr, wrong-language, metadata-boilerplate. Machine-readable counts are in `audit_summary.json`.

The larger generated export had `5,567,226` rows; this upload keeps only rows with an explicit accepted audit decision.

## Recreate

`recreate_dataset.py` can regenerate a similar dataset from local Parquet files:

```bash
python recreate_dataset.py \
  --input-root /path/to/source-parquet-root \
  --output-root data
```

The script also includes `audit` and `filter` subcommands for rerunning the judge/filter workflow with an OpenAI-compatible endpoint.

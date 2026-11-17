---
license: apache-2.0
language:
- da
tags:
- instruction-tuning
- chat
- danish
- dynaword
pretty_name: danish-dynaword-prefix-continuation
---

# danish-dynaword-prefix-continuation

Chat-template-ready Danish prefix continuation examples derived from DynaWord. This upload contains only judge-accepted rows from a larger generated DynaWord export.

## Contents

- Format: gzip-compressed JSON Lines under `data/*.jsonl.gz`
- Schema: `{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}`
- Files: `2`
- Rows: `105,317`
- Task: Danish prefix continuation

## Sources

Accepted rows by source family:

| Source family | Accepted rows |
|---|---:|
| [`danish-foundation-models/danish-dynaword`](https://huggingface.co/datasets/danish-foundation-models/danish-dynaword) | 105,317 |

Effective source files:

| Source file | Accepted rows |
|---|---:|
| `data/adl/adl.parquet` | 57,194 |
| `data/ai-aktindsigt/ai-aktindsigt.parquet` | 48,123 |

## Example

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Fortsæt teksten naturligt. Men i næste Nu var de gyldne Skaaler igjen forsvundne i Skatollets Mørke, og atter stod der den fattigste Stodder i de fladeste Træsko af Verden og med store Bødeklude paa Knæ og Albue, en Mand, som da ingen Retfærdighed paa Jorden kunde falde paa at paaligne større Kommuneskat. Alt i denne By bar Præg af Ælde. Stuerne var lave med svære Bjælker under Lofterne, saa en voksen Mand maatte bøje sig stærkt for at skridte"
    },
    {
      "role": "assistant",
      "content": "hen under dem. Gulvene var som oftest af Ler, der bugted sig i Bakke-Dal ligesom gamle Danmark. Bordet var i Længde med Stuen og stod langs den ene Væg, adskilt fra den ved en murfast Bænk, under hvilken der var pikket med Kampsten. Ved"
    }
  ]
}
```

## Filtering

Rows were judged with [`google/gemma-4-31B-it`](https://huggingface.co/google/gemma-4-31B-it).

| Outcome | Rows |
|---|---:|
| Audited | 110,396 |
| Accepted/uploaded | 105,317 |
| Rejected | 5,079 |

Main rejection reasons: incoherent-or-ocr, metadata-boilerplate, response-mismatch, wrong-language. Machine-readable counts are in `audit_summary.json`.

The larger generated export had `3,268,392` rows; this upload keeps only rows with an explicit accepted audit decision.

## Recreate

`recreate_dataset.py` can regenerate a similar dataset from local Parquet files:

```bash
python recreate_dataset.py \
  --input-root /path/to/source-parquet-root \
  --output-root data
```

The script also includes `audit` and `filter` subcommands for rerunning the judge/filter workflow with an OpenAI-compatible endpoint.

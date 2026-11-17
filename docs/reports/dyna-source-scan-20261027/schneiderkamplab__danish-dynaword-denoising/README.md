---
license: apache-2.0
language:
- da
tags:
- instruction-tuning
- chat
- danish
- dynaword
pretty_name: danish-dynaword-denoising
---

# danish-dynaword-denoising

Chat-template-ready Danish denoising / text restoration examples derived from DynaWord. This upload contains only judge-accepted rows from a larger generated DynaWord export.

## Contents

- Format: gzip-compressed JSON Lines under `data/*.jsonl.gz`
- Schema: `{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}`
- Files: `4`
- Rows: `65,518`
- Task: Danish denoising / text restoration

## Sources

Accepted rows by source family:

| Source family | Accepted rows |
|---|---:|
| [`danish-foundation-models/danish-dynaword`](https://huggingface.co/datasets/danish-foundation-models/danish-dynaword) | 65,518 |

Effective source files:

| Source file | Accepted rows |
|---|---:|
| `data/adl/adl.parquet` | 28,730 |
| `data/ai-aktindsigt/ai-aktindsigt.parquet` | 29,011 |
| `data/botxt/botxt.parquet` | 524 |
| `data/cellar/cellar.parquet` | 7,253 |

## Example

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Gendan den oprindelige tekst. Gaardene Selv syntes forsvinde under de favndybe Driver, der i Masser tætpakkede taarned sig op i Højde Mønningen og endte i en hvorfra Sneen taarned røg til Vejrs som Damp taarned en Gryde. Skorstenene var var eneste, hvorigjennem Husene"
    },
    {
      "role": "assistant",
      "content": "Selv Gaardene syntes at forsvinde under de favndybe Driver, der i tætpakkede Masser taarned sig op i Højde med Mønningen og endte i en Spids, hvorfra Sneen røg til Vejrs som Damp af en Gryde. Skorstenene var det eneste, hvorigjennem Husene"
    }
  ]
}
```

## Filtering

Rows were judged with [`google/gemma-4-31B-it`](https://huggingface.co/google/gemma-4-31B-it).

| Outcome | Rows |
|---|---:|
| Audited | 69,907 |
| Accepted/uploaded | 65,518 |
| Rejected | 4,389 |

Main rejection reasons: low-value-trivial, wrong-language, response-mismatch, incoherent-or-ocr. Machine-readable counts are in `audit_summary.json`.

## Recreate

`recreate_dataset.py` can regenerate a similar dataset from local Parquet files:

```bash
python recreate_dataset.py \
  --input-root /path/to/source-parquet-root \
  --output-root data
```

The script also includes `audit` and `filter` subcommands for rerunning the judge/filter workflow with an OpenAI-compatible endpoint.

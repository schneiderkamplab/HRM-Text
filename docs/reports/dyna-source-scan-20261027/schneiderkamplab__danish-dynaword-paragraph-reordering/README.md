---
license: apache-2.0
language:
- da
tags:
- instruction-tuning
- chat
- danish
- dynaword
pretty_name: danish-dynaword-paragraph-reordering
---

# danish-dynaword-paragraph-reordering

Chat-template-ready Danish paragraph reordering examples derived from DynaWord. This upload contains only judge-accepted rows from a larger generated DynaWord export.

## Contents

- Format: gzip-compressed JSON Lines under `data/*.jsonl.gz`
- Schema: `{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}`
- Files: `3`
- Rows: `55,340`
- Task: Danish paragraph reordering

## Sources

Accepted rows by source family:

| Source family | Accepted rows |
|---|---:|
| [`danish-foundation-models/danish-dynaword`](https://huggingface.co/datasets/danish-foundation-models/danish-dynaword) | 55,340 |

Effective source files:

| Source file | Accepted rows |
|---|---:|
| `data/adl/adl.parquet` | 17,904 |
| `data/botxt/botxt.parquet` | 475 |
| `data/cellar/cellar.parquet` | 36,961 |

## Example

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Gendan den oprindelige rækkefølge af afsnittene. Svar med teksten i korrekt rækkefølge. [1] \"Te1) der jo gaar møj Skidteri af bode den jen og den naaen Handtiring, tho det ved a wal. Det war aalle aant, end det Or2), a tjent i Vistorp; a war søen en Stønnis3)-Dreng, ja, a fulle da mej bode te det jett og det aant, gik mi Skor og to mi Dram med de anne4). A haar aalle gawn5) aa æ Vej for æ Arbed, og den Sæk, a lod sto, den war der sgu flir, der lod sto. Se saa haaj de en Pig - ja, hind kjend du da, Søren, det er hind An Mari, der nu æ gywt mæ Brill-Dawed6)\". [2] \"An Mari, Søren Pallisens Dætter? Jow, det ka gjan vær, - a haar kjowt7) manne hvid Stud i hinne Fødgoed\". [3] Denne Histories Sandhed vilde Kren Konradsen vel ikke ligefrem bestride, men han trøsted sig med det Ord af sin Børnelærdom:"
    },
    {
      "role": "assistant",
      "content": "Denne Histories Sandhed vilde Kren Konradsen vel ikke ligefrem bestride, men han trøsted sig med det Ord af sin Børnelærdom: \"Te1) der jo gaar møj Skidteri af bode den jen og den naaen Handtiring, tho det ved a wal. Det war aalle aant, end det Or2), a tjent i Vistorp; a war søen en Stønnis3)-Dreng, ja, a fulle da mej bode te det jett og det aant, gik mi Skor og to mi Dram med de anne4). A haar aalle gawn5) aa æ Vej for æ Arbed, og den Sæk, a lod sto, den war der sgu flir, der lod sto. Se saa haaj de en Pig - ja, hind kjend du da, Søren, det er hind An Mari, der nu æ gywt mæ Brill-Dawed6)\". \"An Mari, Søren Pallisens Dætter? Jow, det ka gjan vær, - a haar kjowt7) manne hvid Stud i hinne Fødgoed\"."
    }
  ]
}
```

## Filtering

Rows were judged with [`google/gemma-4-31B-it`](https://huggingface.co/google/gemma-4-31B-it).

| Outcome | Rows |
|---|---:|
| Audited | 211,870 |
| Accepted/uploaded | 55,340 |
| Rejected | 156,530 |

Main rejection reasons: wrong-language, arbitrary-order, response-mismatch, incoherent-or-ocr. Machine-readable counts are in `audit_summary.json`.

The larger generated export had `939,361` rows; this upload keeps only rows with an explicit accepted audit decision.

## Recreate

`recreate_dataset.py` can regenerate a similar dataset from local Parquet files:

```bash
python recreate_dataset.py \
  --input-root /path/to/source-parquet-root \
  --output-root data
```

The script also includes `audit` and `filter` subcommands for rerunning the judge/filter workflow with an OpenAI-compatible endpoint.

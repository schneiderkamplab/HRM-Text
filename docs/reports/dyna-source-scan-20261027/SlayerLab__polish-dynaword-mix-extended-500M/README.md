---
language:
- pl
license: cc-by-sa-4.0
task_categories:
- text-generation
pretty_name: BDH - Polish DynaWord Mix (Extended, ~500M tokens)
size_categories:
- 100M<n<1B
tags:
- polish
- language-modeling
- curated
- open-license
- pii-scrubbed
configs:
- config_name: default
  data_files:
  - split: train
    path: train.parquet
  - split: validation
    path: validation.parquet
---


# Polish DynaWord Mix — Extended (~500M tokens)

*Maintained by **Arkadiusz Słota** · [SlayerLab](https://huggingface.co/SlayerLab)*

A curated, openly-licensed **Polish** text corpus for language-model pretraining and
research baselines. Built on top of the open **polish-dynaword** lineage and extended to
**~500 million tokens** (32k BPE) with additional curated, license-compatible sources
and a documented cleaning + PII-scrubbing pipeline.

> **Why this exists:** most large Polish web corpora are legal/parliamentary-heavy and
> carry uncurated PII from raw crawls. This dataset trades raw scale for **traceable
> licensing, reduced stylistic bias, and verified PII removal** — a corpus you can train
> on and publish results from without a legal or privacy footgun.

## Dataset summary

| Property | Value |
|---|---|
| Language | Polish (`pl`) |
| Tokens | ~500,000,000 (32k BPE); validation ~10.2M |
| Sources | curated open-license mix (see **Composition**) |
| License | CC-BY-SA-4.0 (inherited) + attribution to parent sources |
| PII | email + phone scrubbed to `[Email]` / `[Telefon]` placeholders, independently verified |
| Format | Parquet (zstd), UTF-8 — mix section: one document per row; top-up section: one line per row (see **Data format**) |

## Data format (Parquet v2)

The corpus is published as **Parquet** (zstd-compressed), replacing the earlier plain-text
`train.txt` / `validation.txt`. Row semantics follow the original corpus structure:

- **mix section** (polish-dynaword-mix, ~58.5M tokens): documents separated by blank lines →
  **one row = one document** (48,201 train / 2,536 validation documents).
- **top-up section** (DynaWord curated, ~441.5M tokens): the source text carried no document
  separators, so **one row = one line** (14,364,083 train / 152,646 validation lines).

Total rows: **14,412,284 train / 155,182 validation** (column `text`).

**Byte-fidelity:** the parquet is a lossless repackaging of the previously published text —
`'\n\n'.join(mix_rows) + '\n'.join(topup_rows)` reproduces the original `train.txt` /
`validation.txt` byte-for-byte. Verified roundtrip SHA-256: `train.parquet`
`bdc2d3a0…401d` (== previously pinned `train.txt`), `validation.parquet`
`d87026a1…68a5` (== previously pinned `validation.txt`). PII statements and token
counts below are unchanged from the v1 card.

## Composition

Exact token counts (32k BPE):

| Source | Train tokens | Validation tokens |
|---|---|---|
| polish-dynaword-mix (source dataset), PII-scrubbed | 58,542,031 | 3,417,717 |
| DynaWord curated top-up | 441,457,969 | 6,827,009 |
| **Total** | **500,000,000** | **10,244,726** |

Curated open Polish sources: Wikipedia, Wikisource, Wolne Lektury, Wikinews/Wikibooks/Wikivoyage;
EUR-Lex/parliamentary capped for style balance.

Source proportions follow a quality-oriented sampling policy (`temperature_alpha=0.5`,
legal/parliamentary capped at ≤15%) to reduce legalese over-representation while
preserving fully traceable open licensing.

## Curation & cleaning

- **Deduplication:** exact + normalized-text; validation held out with **zero train↔val leak**.
- **Boilerplate removal:** navigation, cookie banners, repeated headers/footers, template remnants.
- **Structural hygiene:** UTF-8 validated, control characters removed, sentence/paragraph structure preserved.
- **PII scrubbing:** emails and phone numbers (Polish + international) replaced with neutral
  placeholders `[Email]` / `[Telefon]` — **not** fake values (which would poison training and
  risk collisions with real numbers) and **not** typos (which leave identifiability).
- **Scrubbing method (reproducible):** *normalize-first* over separators (space, dot, all
  Unicode dashes incl. figure-dash, slash, non-breaking/thin spaces) rather than
  format-enumeration; strong/weak label detection with digit-length gating; structural
  false-positive guards (dates, time-ranges, historical year-ranges, software versions,
  currency/units, registry IDs — NIP/REGON/KRS/PESEL/IBAN). Deterministic, versioned, and
  test-covered; every clean artifact is SHA-256-pinned and independently re-verified.

## PII statement

**PII scrubbing:** contact PII (email; phone incl. foreign +CC and space/dot/dash/en-dash/em-dash/figure-dash/slash separators, concatenated and multi-per-label formats) replaced with `[Email]`/`[Telefon]` placeholders. Independently verified by a second reviewer using a superset lens wider than the scrubber (`check ⊋ scrub`) with false-positive-guard self-audit: **email-residual = 0, real-phone-residual = 0** on corpus `train sha256 bdc2d3a012a5d37f721442519436dc5261cce6261d2e6359d8f1ea57bc8e401d` / `val sha256 d87026a1e938cec8ea0531da6ddcdd6b989384e4c28ad3f1723926e5c73a68a5`, cross-confirmed by literal-grep (two-method agreement). Regex residual-tail (institutional/registry numbers, prices, software versions, historical year-ranges) confirmed non-PII by byte-level triage.

Totals: **27,639** phone placeholders, **1,124** email placeholders. Verification method and reproducible scrubber: see _Curation & cleaning_.

## Licensing & attribution

Distributed under **CC-BY-SA-4.0**, inheriting the share-alike terms of the parent
[SlayerLab/polish-dynaword](https://huggingface.co/datasets/SlayerLab/polish-dynaword) sources.
Attribution to the original per-source providers is preserved; downstream use must retain
attribution and share-alike.

## Intended use & limitations

- **Intended:** pretraining/finetuning small–medium Polish LMs, reproducible baselines, tokenizer
  and data-mix research.
- **Limitations:** small-to-medium scale (not web-scale); placeholder tokens replace contact
  details; residual rare edge-cases may remain in the long tail (documented in the PII statement);
  not intended for tasks requiring verbatim contact data.

## Citation

```
@misc{polish_dynaword_mix_extended,
  title     = {Polish DynaWord Mix — Extended (~500M tokens)},
  author    = {Arkadiusz S{\l}ota},
  publisher = {SlayerLab},
  year      = {2026},
  note      = {CC-BY-SA-4.0; extended and PII-scrubbed from the polish-dynaword lineage}
}
```
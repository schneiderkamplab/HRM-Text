---
type: Research
title: DynaWord and DynaInstruct October 27 refresh
description: Hub-wide name discovery, pinned file deltas and candidate triage against DFM15 and earlier inventories.
status: draft
confidence: high
last_updated: 2026-10-27
tags: [datasets, dfm16, dynaword, dynainstruct, source-review]
---
# Dyna source refresh

Read-only discovery found **38 accessible repositories** across Hub searches
`dynaword`, `dyna-instruct`, `dynainstruct`, and `dyna_instruct`. This is not a
claim to discover hidden/private repositories or differently named derivatives.
No corpus, sampled index, source admission, GPU job or training setting changed.

Reproduce: `python -m scripts.scan_dyna_hub_refresh`. Evidence:
`docs/reports/dyna-source-scan-20261027/inventory.json`, pinned README/changelog
copies and 19 selected constituent cards under that directory. Compared LFS
hashes/Git IDs with the October 5 scan and later DFM15 organization inventory.
The latter is an inventory, not proof of training inclusion. Exact identical
revisions establish unchanged small files even where old inventories omitted
Git blob IDs. Metadata, samples, attribution and rights-audit files must not be
counted as new training payloads. This is card/file-level screening, not a
random quality audit or complete inherited-versus-candidate row deduplication.

## Findings

| Collection | Finding |
|---|---|
| Swedish DynaWord | 111 added Parquet payloads since the saved organization inventory; current version v0.0.26, October 25. Large parliamentary, literary, academic, news, archival and blog additions. |
| Norwegian DynaWord | Five new Wikimedia subsets since the organization inventory. Six research/court subsets added October 14-15 were already inventoried but are not thereby integrated; they were absent from the October 5 scan. |
| Danish DynaWord | New `comparia` and `trykkefrihedens_skrifter`; changed `cellar` and `enevaeldens_nyheder`, each with accompanying metadata. |
| Polish DynaWord | Extensive October rights/quality cleanup, withdrawals and replacements, not a blanket new-data increment. Current revision `316e366f802a9114ffd0ade740afc19069f2277a`. |
| Dutch, Faroese, Icelandic DynaWord | Same revisions as the saved organization inventory. Faroese Logir was already part of the DFM14 enrichment track. |
| Danish, Faroese, Icelandic, Norwegian DynaInstruct | Same revisions and payloads as the DFM15 organization inventory. FO/IS additions already admitted through DFM15 must not be added again. |
| Oliverkinch Dyna derivatives; Syvai extraction/Laya | Unchanged since October 5. Some remain useful previously unintegrated candidates, below. |
| Our schneiderkamplab exports | Existing derivatives, not novel independent data. The new `dfm2-dynaword-historical` repository is a reconstruction package, not a DFM16 addition. |
| Explorer index, annotations, staging mirror, Polish extended mixture | No novel independent training payload established. Avoid duplicate admission. |

## Prioritized Candidates

Sizes below are **upstream card figures**, generally Llama-3 tokens, not Gemma
tokens or sampled epoch contributions. Recommendations are not admissions.

| Priority | Source / subsets | Size | Proposed use and caveats |
|---|---|---|---|
| High, easy SFT | [oliverkinch/dynaword-no-bt](https://huggingface.co/datasets/oliverkinch/dynaword-no-bt) | 6,013 prompt/target rows | Norwegian backtranslated instructions. The old Danish-only exclusion rationale is obsolete for a 50-language corpus; seek admission, verify prompt/passage coherence and overlap with existing Norwegian instructions. Preserve source notices. |
| High, conversion | [syvai/danish-dynaword-laya](https://huggingface.co/datasets/syvai/danish-dynaword-laya), `ctx1024` train | 75,708 cases / 337,395 questions | Native structured decisions with evidence windows; reuse typed-decision conversion principles. Synthetic labels/confidence need checking, not treatment as calibrated truth. Keep document-held-out test out; default/ctx1024 overlap and must not both be admitted. |
| High, grounding | [Norwegian DynaWord](https://huggingface.co/datasets/danish-foundation-models/norwegian-dynaword), `nva-cc-by`, `nva-cc-by-sa`, `nva-cc0` | About 19.72K documents / 721.51M tokens | Norwegian research/theses/reports; grounded QA, summary, rewrites and transformations. Inspect PDF ordering, tables and mixed-language passages; deduplicate `nasjonalt-vitenarkiv` and other research routes. |
| High, grounding | [Swedish DynaWord](https://huggingface.co/datasets/danish-foundation-models/swedish-dynaword), `rd-sou`, `rd-ds` | About 5.11K reports / 682.13M tokens | Long coherent policy/research reports. Section-aware windows, grounded QA/summaries and transformations. Source examples show fused spaces/OCR artifacts; clean and audit. Check overlap with old `statens-offentliga-utredningar` and parliamentary variants. |
| Medium | Swedish `rd-prop`, other `rd-*` | `rd-prop` alone 852.65M tokens | More policy/legal breadth, but cap the domain and deduplicate old parliamentary corpora. |
| Medium | Swedish `swedish-pd`, `gutenberg`, `wikisource` | 1.05B / 23.90M / 10.74M tokens | Historical narrative/nonfiction diversity; substantial OCR filtering, source overlap checks and historical spelling awareness. Retain work-level attribution/terms; Wikisource site license alone does not describe every imported work. |
| Medium, sentence-only | Swedish `sweachum`, `sweacsam`, `attasidor` | 26.83M / 20.06M / 10.50M tokens | Shuffled academic/easy-news sentences. Sentence rewriting, correction, denoising or span filling only. Do not concatenate them into invented documents or paragraph-order tasks. |
| Medium | [Danish DynaWord](https://huggingface.co/datasets/danish-foundation-models/danish-dynaword), `trykkefrihedens_skrifter` | 988 texts / 9.46M tokens | Danish historical modernization, grounded QA and summaries. Most OCR proofread; German material less reliable. Printed lines are not paragraphs, and polemical content needs contextual handling. |
| Medium, replacement/delta | Danish `enevaeldens_nyheder` ENO 1.0 | Full updated source 4.66M records / 1.05B tokens | Modernization/historical grounding; use stable-ID/text deltas rather than repeat the inherited corpus. Headlines/ads, OCR, German/Latin and near duplicates require selection. |
| Medium/low | Norwegian `wiktionary-nob`, `wiktionary-nno`, `wikinews` | 2.10M / 216.90K / 245.59K tokens | Small lexical and news additions; glossary tasks and evidence-grounded questions, not generic long-document transforms. |
| Conditional | Norwegian `hoyesterett`, `tingrettene`, `lagmannsrettene` | About 33.18M tokens | Legal summarization and grounded reasoning. Separate privacy/disclosure/quoted-work checks from the source's stated official-document copyright status. |

## Defer or Avoid

- Danish `comparia`: only **51 user queries / 1.35K tokens**, no assistant
  answers. At most a tiny prompt seed set, not ready-made SFT. Some follow-ups
  depend on omitted context. Do not confuse it with the inherited French
  ComparIA preferred-response dataset.
- Danish `cellar`: refreshed **full** source is 6.15B tokens, not 6.15B new.
  Lower marginal value given substantial inherited EU/legal data; compare
  stable IDs and text hashes before deciding on a bounded delta.
- Swedish `bloggmix*`: bulk blogs conflict with the earlier preference for
  curated/non-web grounding. Do not reopen that decision from this scan.
- Swedish `lb-restricted`: 299.45M tokens of scrambled sentences, not intact
  literary works. Low priority; upstream labels the downloadable release
  CC-BY, but the format alone makes it unsuitable for long-context transforms.
- Swedish `riksarkivet-*-lines`: historical handwritten-transcription lines,
  not coherent ready-to-use documents. Consider only a specialized repair or
  modernization pipeline with authentic page/document reconstruction.
- Norwegian Wikiquote: quotations are not preferred fresh grounding; retain
  work-level attribution and assess underlying text rights before use.
- Do not add both Syvai extractions and Laya as independent content.

## Polish Replacement Warning

The [upstream changelog](https://huggingface.co/datasets/SlayerLab/polish-dynaword/blob/316e366f802a9114ffd0ade740afc19069f2277a/CHANGELOG.md)
reports v0.2.6: 27 sources, 3,394,876 documents and 7.037B cl100k-proxy tokens.
It explicitly says its planned corpus-wide NERGAL personal-data pass has not
yet run. These are upstream statements, not our independent legal findings.

Removed/held files relative to the October 5 inventory include OpenStax PL,
Kultura bez Barier, Common Voice, Fandom, Wikiquote, Wikisource, samorzad,
1000_novels, sejm_interpellations and UZP. Read per-source reasons rather than
assuming every withdrawal has the same cause. Wikipedia, Biblioteka Nauki,
parliamentary, government, literature and educational payloads were also
replaced or filtered. The new Wikipedia citations file is auxiliary, not an
extra training corpus.

This supersedes the October 5 blanket recommendation for those withdrawn
payloads. **Do not silently keep using old pins for new additions.** Review
lineage of inherited Polish exports separately before any destructive change.
DFM14's saved enrichment source lock includes `kultura_bez_barier_pl`,
`edukacja_medialna_pl`, `open_icm_pl` and other selected old payloads; the lock
alone does not establish which rows survived audit into the final mixture.
OpenStax was requested in that lock's patterns but absent from its selected
files. Prefer retained cleaned education/science content where useful, replacing
matching old passages rather than stacking both revisions.

## Next Action

For a compact increment, start with Norwegian no-bt and Danish Laya conversion,
then a capped Norwegian NVA / Swedish reports grounding campaign. Add historical
Swedish/Danish material for diversity, not as the dominant increment. All
grounding-to-instruction generation must use the established shared audit
pipeline and native Gemma template. No new non-Danish raw continuation route
is implied. Resolve proposed source selections and repeats before resampling.

Related: [previous scan](dyna-source-updates-20261005.md),
[DFM14 candidates](dfm14-potential-additions.md), [DFM16](dfm16-plan.md).

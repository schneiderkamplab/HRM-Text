---
type: Plan
title: DFM14 Potential Additions
description: Prioritized corpus additions and replacements from the Dyna source review, with Faroese completion context and admission requirements.
status: draft
confidence: medium
last_updated: 2026-10-05
tags: [data, multilingual, dfm14, dynaword, dynainstruct]
---
# DFM14 Potential Additions

## Scope

This page is part of the [DFM14 plan](dfm14-plan.md), renamed by the owner on
2026-10-05. Sources remain candidates unless individually approved.

For missing-language priorities and potential reasoning transfer, see
[DFM14 Language Priorities](dfm14-language-priorities.md).

These are **future candidates, not approved DFM13 additions**. Do not reopen
the running DFM13 verification or silently change its sample for these sources.
The separately authorized `Setur/fo-instruct` repeat-10 addition belongs to
DFM13 and is not part of this future list.

The [October 5 Dyna source scan](dyna-source-updates-20261005.md) contains
individual-source counts, exact revisions, source links, baseline limitations,
and the reproducible inventory. It inspected 37 public repositories, including
seven upstream DynaWord and four upstream DynaInstruct collections. New payloads
were concentrated in Polish DynaWord (16 subsets) and Danish/Faroese `logir`.
All four DynaInstruct collections and Dutch, Norwegian, Swedish and Icelandic
DynaWord matched our local pinned revisions. No new instruction subset was
found there. Selected upstream sample inspection is not a full quality audit.

## Recommended First Increment

### Persian Matina Access Granted

**2026-10-05 owner update:** access has been granted to
[`MatinaAI/matina_persian_text_corpus`](https://huggingface.co/datasets/MatinaAI/matina_persian_text_corpus).
This supersedes the earlier access-pending/HTTP-403 blocker recorded in the
[fourth-wave plan](fourth-language-extension-wave.md), but does not imply a
verified payload download, completed audit, or integration.

Keep this as a **post-DFM13** Persian enrichment candidate. Next steps are to
confirm authenticated payload access, inspect structure and domain diversity,
deduplicate against TLPC and inherited Persian sources, and select material
for the four transformation tasks and grounded QA/chat. Preserve source terms
and attribution. Do not reopen current DFM13 sampling for this addition.

### Dyna Source Candidates

| Repository | Subsets | Rationale and intended use |
|---|---|---|
| `danish-foundation-models/faroese-dynaword` | `logir` | Highest priority for new native Faroese source diversity and long coherent passages. Four transformations plus grounded QA and summaries. About 5,080 documents / 14.43M Llama-3 tokens. Cap legal-domain share. |
| `SlayerLab/polish-dynaword` | `openstax_pl`, `open_agh_chemistry_pl`, `edukacja_medialna_pl` | Educational/scientific explanations and media literacy. Preserve equations; exclude tasks requiring absent diagrams. |
| `SlayerLab/polish-dynaword` | `open_icm_pl`, `studia_bas`, `wiadomosci_statystyczne_pl`, `kultura_bez_barier_pl` | Academic, policy, statistics and accessibility breadth. Clean PDF extraction, bilingual duplicates, headers and non-content material. |

The seven Polish sources together provide about **2,419 documents / 12.3M
upstream proxy tokens**. This is a compact, diverse first increment rather than
hundreds of millions of repetitive legal/discussion tokens. Counts are not
Gemma 4 tokens, accepted training rows, or final epoch contributions.

## Other Candidates

| Repository | Subsets | Assessment |
|---|---|---|
| `danish-foundation-models/danish-dynaword` | `logir` | Useful lower-priority Danish legal prose: about 2,110 documents / 15M Llama-3 tokens. Ground questions in provided documents and dates; do not teach historical statutes as unqualified current advice. |
| `SlayerLab/polish-dynaword` | `sejm_api_2011_2022`, `sejm_committee_transcripts`, `sejm_interpellations` | About 329.6M proxy tokens. Source-balance and deduplicate existing parliamentary material; preserve speakers. Confirm actual linked answers before turning interpellations into QA. |
| `SlayerLab/polish-dynaword` | `fandom_pl` | About 50,653 records / 45.79M proxy tokens. Conditional games/fiction/hobby breadth. Remove markup and clearly distinguish fictional knowledge from real-world claims. |
| `SlayerLab/polish-dynaword` | `common_voice_pl` | About 45,043 sentences / 1M proxy tokens. Sentence-level denoising/span filling; not paragraph reordering or invented multi-paragraph continuity. |
| `SlayerLab/polish-dynaword` | `ted_pl` | Low priority: public-procurement notices, **not TED talks**. Structured extraction may be useful; bulk generic instruction would be repetitive. |
| `syvai/danish-dynaword-laya` | `ctx1024` or longer default, not both | Separate structured extraction/typed-decision candidate. Short config has 75,708 train cases / 337,395 questions; configs overlap. Convert to native SFT, preserve train/test separation, verify window-local evidence, and do not treat synthetic confidence values as gold. |

Danish and Faroese Logir may support a translation project, but shared hosting
does not prove parallelism. Check corresponding law/version identifiers and
paragraph alignment before generating pairs.

## Defer or Avoid

- Polish `plwiki_talk` and `plwiki_user_talk`: editor arguments, signatures,
  templated onboarding and context-dependent chatter. Defer general SFT use.
- Polish `nonsa`: satire and offensive examples were observed. Do not use as
  factual/general instruction. Any future humour task would need explicit
  framing and separate review.
- `syvai/danish-dynaword-extractions`: no README at the scanned revision;
  semantics and quality remain unestablished. Do not add both it and its Laya
  derivative without deduplication.
- Our `schneiderkamplab` Dyna-derived exports are already-derived data, not new
  independent sources. Do not double-count them.
- Oliverkinch DynaWord-derived repositories last changed in May; the Polish
  extended-500M mixture is an August derivative. Neither is a newly discovered
  independent corpus increment. Explorer indices, annotations and staging
  mirrors are not automatically training data.

## Replace, Do Not Duplicate

- **Danish ADL:** repaired extraction, removal of roughly 160 textless volumes,
  and corrected edition dates. Current source has 338 volumes / 56.36M Llama-3
  tokens. Trace and replace/deduplicate affected inherited examples; inspect
  historical spelling and non-Danish passages. Exact inherited coverage was
  not established by the scan's Danish temporal baseline.
- **Polish `samorzad_gov_pl`:** rebuilt, de-identified upstream v0.2, about
  72,472 documents / 40M proxy tokens. Replacement candidate, not an extra copy.
- `global_voices` and `rock_pollub_pl` changed sidecars but not payload parquet
  bytes. `rock_pollub_pl` and `uzp_orzeczenia_pl` were already in the local
  Polish baseline. Do not count these as new subsets.
- Polish `main` contains development additions beyond the stable tag. Pin
  reviewed payloads explicitly; its headline README totals predate Fandom and
  are not a reliable current aggregate.

## Faroese Shortfall Was Resolved

The earlier September 28 shortage is **historical, not outstanding**:

| Family | Initially accepted before reopening | Final accepted / target |
|---|---:|---:|
| Grounded instruction | 2,453 | 20,000 / 20,000 |
| Multi-turn | 601 | 15,000 / 15,000 |
| Summary/rewrite | 725 | 10,000 / 10,000 |
| Math/code | Not part of the three waived families | 6,000 / 6,000 |
| OpenHermes-style | Not part of the three waived families | 15,000 / 15,000 |
| Tool dialogue | Not part of the three waived families | 4,000 / 4,000 |

Initial preparation had only **6,793 eligible Faroese source windows** against
a requested 250,000; short documents were the main source-supply limitation.
The owner initially accepted reduced quotas, then superseded that decision by
authorizing fresh candidates from reused source rows and expanded attempt
budgets. Acceptance and duplicate checks remained in place. The final ledger
shows **70,000 accepted conversations**, all six targets reached, subsequently
published and integrated.

Evidence: `data/dfm12/joint-synthetic-source-expansion-20260929/progress.json`,
`campaigns.original.groups`, and the
[joint production completion record](dfm12-joint-synthetic-production.md).
The older [original campaign note](dfm12-multilingual-quarter-production.md)
must be read together with that superseding completion record.

Thus Logir is proposed to improve **source diversity and long grounded text**,
not to repair a missing Faroese row quota. More conversations based on the same
small source reservoir are not equivalent to more underlying source coverage.

## Preparation Requirements

1. Approve a post-DFM13 scope and pin source revisions without changing DFM13.
2. Establish actual inherited source coverage and exact/near-duplicate checks;
   apply replacements rather than duplicating repaired payloads.
3. Sample broadly by document/source and cap oversized parliamentary/legal
   shares. Keep original language, source/version, dates and attribution.
4. For non-Danish corpora use the four transformations and grounded SFT, not
   automatic raw continuation. Preserve paragraph structure where available.
5. Render with the native Gemma 4 template; independently audit generated tasks
   for grounding, language quality, answerability and format.
6. Report accepted rows and measured Gemma-token totals before choosing repeats
   and sampling. Existing owner approval covers DynaWord/DynaInstruct licensing;
   retain notices rather than imposing a new blanket license gate.

No generation targets, repeats, audit jobs or inclusion decisions for these
candidates are authorized by this note.

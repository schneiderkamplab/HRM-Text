---
type: Research
title: DynaWord and DynaInstruct Source Update Scan
description: Read-only comparison of October 5 Hub inventories with local source pins and candidate recommendations.
status: draft
confidence: high
last_updated: 2026-10-05
tags: [data, dfm13, dynaword, dynainstruct, source-review]
---
# Dyna Source Updates: 2026-10-05

Future inclusion recommendations and the resolved Faroese generation shortage
are consolidated in [Potential DFM14 Additions](dfm14-potential-additions.md).

## Scope and Method

Discovery queried the Hugging Face API for `dynaword`, `dyna-instruct`, and
`dynainstruct`: 37 repositories, including mirrors, our exports, annotations,
and exploratory derivatives. Seven upstream DynaWord language collections and
four upstream DynaInstruct collections are the primary scope. Compared file
names, sizes, Git blob IDs and LFS hashes; this is not a full corpus quality audit.
Read source cards and the first two supplied sample rows for each new Polish
subset having a sample file. These are upstream-selected examples, not random
quality estimates. Recommendations below are engineering judgments.

Reproduce: `python -m scripts.scan_dyna_source_updates`.
Evidence: `docs/reports/dyna-source-scan-20261005/inventory.json`, pinned upstream
cards and source-specific cards/samples in the same directory.

Ten upstream collections have an exact baseline in
`data/dfm12/sources.lock.json`. Danish DynaWord does not have a complete local
pin there; its temporal comparison uses September 1 commit
`c2f51be06848df26b5aad71cafeec1bc6064b1cc`, explicitly **not** proof of exact
inherited training coverage. Other derivative repositories without pins are
inventoried, not declared unchanged by comparison.

No candidate from this scan was registered, tokenized, or scheduled for audit.
The running DFM13 verification is left alone. Setur/fo-instruct is a separate,
already authorized addition, not a DynaInstruct update.

## Collection-Level Findings

| Collection | Result against baseline |
|---|---|
| Danish DynaWord | New `logir`; changed ADL payload and annotations since temporal baseline |
| Faroese DynaWord | New `logir`, September 30 |
| Polish DynaWord | 16 new payload subsets, September 29 through October 4; changed `samorzad_gov_pl` payload |
| Dutch, Norwegian, Swedish, Icelandic DynaWord | Current revisions equal local pins; no new subsets |
| Danish (`dfm-dyna-instruct`), Faroese, Icelandic, Norwegian DynaInstruct | All current revisions equal local pins; no new subsets |

Polish current pin: `a91237f297c2a69efab17f99c9f1575503f154b0`, compared with
`1564cb054434ba049cbd0d355a9bfaf044b6a852`.
Faroese current pin: `24ab901896257f4a1c6e4b0e6b0619ffc500f72d`, compared with
`41cdd41007ff3d787beb6e602bdbac131a2cd3ee`.
Danish current pin: `1ae189bf3b6765a5356450b8921a0d9ad7987a37`.

## Prioritized Candidates

Counts below are source-card figures, **not Gemma 4 tokens and not tokens added
to an epoch**. Polish figures generally use cl100k proxy tokens; Danish and
Faroese cards use Llama 3 tokens. Retained training counts need conversion and
audit. Existing owner authorization accepts DynaWord/DynaInstruct licenses;
retain attribution without inventing a new blanket license gate.

| Source/subset | Documents | Source tokens | Recommendation |
|---|---:|---:|---|
| Faroese DynaWord `logir` | ~5,080 | 14.43M | High priority: substantial native Faroese prose; four transformations and grounded QA/summaries; cap legal-domain share |
| Danish DynaWord `logir` | ~2,110 | 15.00M | Useful but lower marginal priority; same transformations, source-conditioned legal QA; historical laws must not become unqualified current advice |
| Polish `openstax_pl` | 1,422 | 4.6M | High priority: educational explanations and science; preserve equations, exclude questions needing absent diagrams |
| Polish `open_agh_chemistry_pl` | 370 | 0.6M | High priority after figure-reference filtering; chemistry explanations and grounded QA |
| Polish `edukacja_medialna_pl` | 252 | 0.7M | High priority: clean instructional prose, media literacy and source-based reasoning |
| Polish `open_icm_pl` | 85 | 2.4M | Useful academic breadth; remove headers/bibliography and separate bilingual abstracts |
| Polish `studia_bas` | 112 | 2.3M | Useful policy/economics prose; grounded summaries and QA |
| Polish `wiadomosci_statystyczne_pl` | 169 | 1.5M | Useful statistics prose; filter announcements, bilingual duplicates and PDF debris |
| Polish `kultura_bez_barier_pl` | 9 | 0.2M | Useful accessibility/procedural niche, but extraction cleanup required |
| Polish `sejm_api_2011_2022` | 118,902 | 135.1M | Include selectively; speaker-aware grounded summaries; deduplicate inherited parliamentary material |
| Polish `sejm_committee_transcripts` | 653,411 | 166.3M | Include with a cap; preserve speaker/turn structure and don't confuse parliamentary speech with assistant answers |
| Polish `sejm_interpellations` | 25,950 | 28.2M | Promising real questions/official responses; check whether records retain actual linked responses before treating as QA |
| Polish `fandom_pl` | 50,653 | 45.79M | Conditional breadth: games/fiction/hobbies, domain-labelled grounded tasks; filter residual markup and distinguish fictional facts |
| Polish `common_voice_pl` | 45,043 | 1.0M | Small sentence-level denoising/span filling only; too short for genuine paragraph reordering |
| Polish `ted_pl` | 15,544 | 42.5M | Low priority: public-procurement notices, not TED talks; possible structured extraction, too templated for bulk generic chat |
| Polish `plwiki_talk` | 43,054 | 55.6M | Defer bulk use: arguments, signatures and context-dependent editing discussion; not reliable assistant supervision |
| Polish `plwiki_user_talk` | 380,527 | 381.4M | Defer: substantial templated onboarding/editor chatter; low marginal quality despite volume |
| Polish `nonsa` | 12,304 | 16.9M | Do not add as factual/general instruction; satire and offensive material observed; only a separately labelled humour task could be justified |

The seven compact Polish educational/scientific/accessibility sources together
have approximately **2,419 documents / 12.3M source tokens**. These plus Faroese
Logir are the best first increment; they add diversity without hundreds of
millions of repetitive parliamentary/wiki-discussion tokens.

For non-Danish raw corpora, follow the existing transformation/grounded SFT
recipe, not automatic raw continuation. Render converted assistant supervision
through the same Gemma 4 template, preserve document IDs, and audit generated
tasks. Legal QA should be explicitly grounded in supplied text/date.

Faroese and Danish Logir may offer useful translation material, but common
hosting does **not** establish parallelism. Inspect corresponding law/version
identifiers and paragraph alignment before proposing translation pairs.

## Updates Rather Than Additions

- Danish ADL now has 338 volumes / 56.36M Llama-3 tokens. Source notes describe
  removal of roughly 160 textless volumes, corrected edition dates, and some
  multilingual volumes. Replace/deduplicate old ADL-derived examples when
  regenerating; do not append a second copy. The inventory confirms changed
  payload bytes, but does not quantify which inherited training rows change.
- Polish `samorzad_gov_pl` has a rebuilt, de-identified v0.2 payload (72,472
  documents / about 40M proxy tokens). Prefer this as a replacement after
  checking source-to-training lineage, not additive duplication.
- `global_voices` and `rock_pollub_pl` have changed evidence/sidecar files but
  unchanged parquet payloads. They are not additional training text.
- `uzp_orzeczenia_pl` and `rock_pollub_pl` are already present in the local
  Polish baseline revision. The upstream development-source table must not be
  mistaken for our exact new-source delta.
- Polish `main` contains development additions not yet in the tagged stable
  release; pin reviewed files explicitly. Its README totals predate the latest
  Fandom addition, so do not treat the headline total as a current inventory.

## Other Search Hits

`syvai/danish-dynaword-laya` (September 21) is a potentially useful structured
extraction/typed-decision derivative, not a new upstream DynaWord subset. Its
card reports 75,708 train cases / 337,395 questions for `ctx1024`, versus 41,300
cases / 336,662 questions for the longer configuration. They overlap: select
one representation, not both. It would require an SFT converter and checks that
every answer is supported in the supplied window. Prefer short contexts for
the current 4K training. Do not supervise model-generated confidence values as
ground truth. This is a separate candidate, not a new inclusion decision.

`syvai/danish-dynaword-extractions` has no README at the scanned revision; its
inventory is recorded, but quality/semantics are not established here.
Oliverkinch's six discovered DynaWord-derived repositories have last updates in
May; they are not recent additions. Our `schneiderkamplab` exports are derivative
outputs and must not be added again as independent sources. Explorer indices,
annotation repositories and staging mirrors are not automatically training
corpora. The Polish extended-500M mix is an August mixture, not a newly released
independent source.

## Sources

- [Polish DynaWord](https://huggingface.co/datasets/SlayerLab/polish-dynaword)
- [Faroese Logir](https://huggingface.co/datasets/danish-foundation-models/faroese-dynaword/blob/main/data/logir/logir.md)
- [Danish Logir](https://huggingface.co/datasets/danish-foundation-models/danish-dynaword/blob/main/data/logir/logir.md)
- [Danish ADL](https://huggingface.co/datasets/danish-foundation-models/danish-dynaword/blob/main/data/adl/adl.md)
- [Danish Laya derivative](https://huggingface.co/datasets/syvai/danish-dynaword-laya)
- [Language-wave recipe](language-extension-waves.md)
- [DFM13 plan](dfm13-plan.md)

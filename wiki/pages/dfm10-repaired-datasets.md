---
type: Dataset Inventory
title: DFM10 Production Replacement Inventory
description: Exact row and token counts for every disabled legacy dataset and its active DFM10 repaired replacement.
tags: [dfm10, datasets, repair, tokenization, quality]
status: stable
last_updated: 2026-08-29
confidence: high
---
# DFM10 Production Replacement Inventory

These values were measured directly from the current token arrays on
2026-08-29. “Original” means the complete tokenized legacy prefix or prefixes
that DFM10 now sets to zero; “repaired” means the complete production
replacement before sampling caps, repeats, 4,097-token packing, or epoch index
selection. Rows are tokenizer target rows, not necessarily upstream source
records.

| Replacement family | Why the legacy form is disabled | Original rows | Original tokens | Repaired rows | Repaired tokens |
| --- | --- | ---: | ---: | ---: | ---: |
| NordjyllandNews | Generic-summary prompt plus unsupported or incomplete targets | 75,219 | 37,188,521 | 47,120 | 26,590,391 |
| DynaWord Instruct (four variants) | Prompt/target mismatch, OCR damage, abrupt target extraction | 70,081 | 42,503,362 | 65,548 | 39,422,832 |
| DBC abstracts and reviews | Wrong-language prompts, opaque review IDs, boilerplate and weak rows | 11,878,022 | 1,603,117,009 | 9,517,244 | 984,542,417 |
| OPUS DA–EN | Misaligned, incomplete, wrong-language pairs and visible provenance text | 58,522,188 | 5,664,687,618 | 41,155,546 | 3,629,237,788 |
| Nemotron SWE | Duplicated cumulative targets, lost tool contract, clipped/contextless actions | 10,082,062 | 30,272,312,633 | 2,472,316 | 6,597,089,585 |
| DOLCI tool use | Dropped environment results, duplicate call IDs, malformed call/result groups | 1,141,793 | 1,113,190,635 | 996,180 | 1,530,751,609 |
| OpenMathInstruct2 | Unverified/duplicate traces and benchmark contamination | 25,023,023 | 6,602,987,880 | 7,490,945 | 2,140,161,586 |
| Code Meta-Reasoning | Empty user prompt, flattened problem/target, unsafe and recursive task families | 911,517 | 1,309,780,132 | 429,301 | 667,312,660 |
| GovReport | Character-truncated evidence paired with full unsupported summaries | 4,152 | 2,206,151 | 891 | 2,987,781 |
| WikiCatSum | Noisy web evidence, truncation, boilerplate and unsupported lead claims | 153,911 | 102,608,687 | 11,791 | 2,317,983 |
| DST table prompts | Weak table grounding and unsupported generated claims | 3,043 | 5,113,852 | 2,909 | 4,111,556 |
| Danish university portals BT | Incomplete fragments, extraction corruption and missing context | 4,505 | 2,176,575 | 3,049 | 1,607,730 |
| Danmarks Statistik BT | Topic-only persona prompts that targets did not answer | 7,154 | 1,886,248 | 5,627 | 1,282,988 |

## Counting Notes

- DOLCI trajectories can yield multiple assistant targets. The original side
  counts only `dolci_native_tool_use__`, the active DFM9 representation that
  the repair supersedes; two older non-native representations were already
  disabled and are not counted. Neither side is a count of unique upstream
  conversations.
- OPUS rows are directional translation tasks. The original 29,261,517 pairs
  produced 58,523,034 candidate directional rows; the stored legacy token tree
  contains 58,522,188 rows. The repair retains 20,577,773 accepted pairs and
  emits both directions, yielding 41,155,546 rows.
- GovReport is the only replacement with more stored tokens despite fewer
  rows. The repaired examples preserve complete reports instead of the legacy
  character-truncated prompts.
- The counts are corpus inventory totals, not per-epoch mix contributions.
  DBC, OPUS, Nemotron SWE, DOLCI, Code Meta-Reasoning, and other sources are
  subsequently affected by per-file caps, repeats, or context-window packing.
- Folketing, Andersen, Alexandra train additions, and DeepDive are omitted
  because they are new DFM10 sources rather than replacements for disabled
  inherited sources.

## Volume Assessment

Do not relax the current quality gates merely to restore legacy volume. Most
large apparent reductions are either non-binding at sampling time or remove
known inflation:

- DBC still fills exactly the same 2,250,000-row per-epoch cap as the legacy
  corpus, and repaired OPUS still fills its 30,000,000-row cap.
- Nemotron SWE removes cumulative-target multiplication and still supplies
  2.47M structurally complete targets. DOLCI retains 190,736/229,183 source
  trajectories (83.22%) and stores more tokens than the active legacy native
  conversion because tool results are no longer silently discarded.
- OpenMathInstruct2 remains very large at 7.49M traces over 581,346 selected
  problems. Code Meta-Reasoning retains 429,301 clean rows, although the
  sampling policy deliberately caps the family at approximately 250K rows.
- GovReport loses rows because complete reports must fit 4K, but repeat two
  gives 5.98M repaired pre-index tokens versus 4.41M for the truncated legacy
  corpus. Recover more only in an 8K+ stage, not by restoring unsupported 4K
  examples.

The sources most worth expanding through source-grounded recovery are:

1. **WikiCatSum:** 11,791 rows and 4.64M repeated tokens are likely too small
   to contribute much summarization breadth. Its gate should not be loosened;
   expand by constructing newly grounded summaries from cleaned evidence or
   by adding a cleaner summarization source.

The university-portals and Danmarks Statistik source-grounded recoveries were
completed on 2026-08-29 and are reflected in the table. WikiCatSum is now the
next active recovery target.

NordjyllandNews retains enough authentic breadth for the current mix. Its
25,977 rejects should only return through article-grounded target regeneration,
not a lower unsupported-claim threshold. Raising the Code Meta-Reasoning
sampling cap from 250K toward its 429K clean-row inventory is also defensible
if code capability is prioritized, but that is a mix-weight decision rather
than a repair defect.

The controlling policy is
[`data_io/prefix_config_dfm10.yaml`](/../data_io/prefix_config_dfm10.yaml), and
the active tokenized roots are recorded by
`data/tokenized_dfm10/union_manifest.json`. Individual repair methods and
quality gates are linked from the [DFM10 plan](/pages/dfm10-plan.md) and
[source-quality audit](/pages/dfm10-source-quality-audit.md).

## Remaining audited-source triage

**Correction 2026-08-29:** completing the source-grounded DST, university, and
WikiCatSum recovery queue does not close every `Filter` or `Repair` disposition
from the 178-source audit.

- `laion/Scientific-Summaries` has a completed 3,312,314-row repaired rebuild
  and a passing 40,044-row E4B audit (91.04% usable), but the repaired tree is
  not tokenized or linked into the DFM10 union. The legacy
  `dfm4_laion_scientific_summaries__` prefix remains active at 3,000 rows per
  file. This is an integration defect, not unfinished semantic repair.
- `oliverkinch/machine-translation-da-ar` and `-da-uk` scored only 7% and 23%
  usable. The documented decision is to exclude them unless those language
  pairs become explicit objectives, but `prefix_config_dfm10.yaml` still caps
  each at one million rows instead of disabling it. Resolve this policy/config
  contradiction before sampling.
- Several active inherited families remain at the source audit's `Filter` or
  `Repair` disposition, including small Sapient QReCC/SciBench/MSMARCO/AESLC
  tasks; Danish DaCoref, Tidsskrift, EUR-Lex BT, DynaWord BT, DOAB, Kænguruen,
  Multi-Zebra, and EUR-Lex summarization; and English ASSET, IF-SFT, CoEdIT,
  Tulu algebra, MegaScience TextbookReasoning, Natural Instructions, plus
  selected translation tasks. These require source-specific deterministic
  filtering, repair, or explicit exclusion; they are not implicitly cleared by
  the completed high-profile replacements.

Do not sample final DFM10 until this residual matrix is reconciled against the
active task prefixes and every unresolved source has an explicit keep, repair,
filter, or exclude decision.

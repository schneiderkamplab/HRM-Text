---
type: Research
title: Portuguese Variant Coverage Reassessment
description: Separate pt-PT and pt-BR supply evidence and remaining dual-gate admission requirements.
status: draft
confidence: medium
last_updated: 2026-09-26
tags: [multilingual, portuguese, datasets, dala]
---
# Portuguese Variant Coverage Reassessment

## Revised Finding

2026-09-26: **Superseded** is the earlier implication that pt-PT lacks substantial
instruction supply and must rely on Brazilian resources. AMALIA provides a
substantial European-Portuguese-focused ecosystem. Promote pt-PT to near-term
verification, not automatic admission under the [two-gate policy](european-language-expansion-joint-priorities.md#mandatory-eligibility-policy).
The previous Portuguese rank 7 is a historical language-level estimate, not a
validated separate variant ranking. Do not apply global reach to pt-PT alone.

## European Portuguese Supply

| HF source | Size observed | Use and caveat |
|---|---|---|
| [amalia-llm/CorEGe-PT](https://huggingface.co/datasets/amalia-llm/CorEGe-PT) | Card: 34,285 extracted documents, about 1.1B tokens; 29,766 classified pt-PT | Structured academic text. Total tokens are not the filtered pt-PT count. Filter extraction artifacts, mixed-language passages and individual document rights. |
| [amalia-llm/persona_general](https://huggingface.co/datasets/amalia-llm/persona_general) | Size API: 156,397 train rows | Synthetic general instruction candidate; audit variant and answers. |
| [amalia-llm/persona_instruction_following](https://huggingface.co/datasets/amalia-llm/persona_instruction_following) | Filtered pt: 9,084; full pt: 27,781 | Use filtered Portuguese, not English or both nested versions. Card reports Gemma 3 27B generation and quality-score selection. |
| [amalia-llm/wikipedia_conversations](https://huggingface.co/datasets/amalia-llm/wikipedia_conversations) | 97,553 train rows | Grounded conversations; check variant and overlap. |
| [amalia-llm/smol_summarize_pt](https://huggingface.co/datasets/amalia-llm/smol_summarize_pt) | 96,356 train rows | Summarization; protect constituent evaluation material. |
| [amalia-llm/AMALIA-LLM-0626-SFT-Dataset](https://huggingface.co/datasets/amalia-llm/AMALIA-LLM-0626-SFT-Dataset) | Size API: base 847,923; ramp_down 726,565 | Mixed-language mixture, not unique pt-PT totals. Do not add to component counts. |

The four component instruction sources total **359,390 rows before** variant
screening, independent audit and cross-source deduplication. The mixture card
also reports translated ramp-down components: 43,074 DOLCI, 73,645 Nemotron IF,
51,194 Hermes-system examples. These recipe counts are not additional unique
rows certified by this inspection. Published mixture sizes and recipe counts
differ; use pinned artifacts for accounting. Remove AMALIA identity content
and evaluation-derived material such as WMT benchmark examples.

CorEGe provides language/variant confidence fields and declares CC BY-NC-SA
4.0. This fits the user's non-commercial preference in principle, but some
document license URIs are missing; open access alone is not redistribution
permission. Individual rights and retained quality still need checking.

[Fine PT-PT Web](https://arxiv.org/html/2609.07699v1) reports 24.6M documents
and 41B GPT-2 tokens from Arquivo.pt. This is another supply lead, not a verified
HF-downloadable corpus here: the inspected paper links processing code, but
an exact released HF corpus was not established.

## Brazilian / Broader Portuguese

[Polygl0t/gigaverbo-v2](https://huggingface.co/datasets/Polygl0t/gigaverbo-v2)
reports 372,108,576 default rows, 317.7B tokens and education/toxicity scores.
It is Portuguese-wide, not a verified pure pt-BR subset. Select quality sources
rather than relying on raw web volume.

[Polygl0t/gigaverbo-v2-sft](https://huggingface.co/datasets/Polygl0t/gigaverbo-v2-sft)
reports 4,089,089 examples, 2.152B tokens and 12 task categories, substantially
expanding the older Tucano inventory. Variant proportions remain unmeasured.
Teacher-based quality filtering is not independent validation. Convert Qwen
reasoning/tool syntax to Gemma format and check benchmark overlap.

## DaLA Gate

### Updated DaLA Assessment (2026-09-26)

Re-read the updated local source
`/work/mimir/DaLA/wiki/pages/european-language-ranking.md`, especially
"Portuguese reassessment: separate pt-PT and pt-BR". It now explicitly ranks
**pt-PT 11/B and pt-BR 12/B**, both viable second-wave candidates. This
supersedes treating pt-BR as unassessed. Neither is yet a validated production
pack, and their relative ordering is provisional.

- **pt-PT grammar:** COPLE2 gives naturally observed learner-error evidence,
  but aligned export coverage, correction minimality and safe extraction still
  need verification. Complement learner patterns with native-writer evidence.
- **pt-BR grammar:** the benchmark's 34 sets are mainly lexical confusions,
  not 34 independent syntactic families. Excluding internet normalization leaves
  242 candidate examples, not 242 verified usable correction pairs. Inspect
  edit direction and ambiguity. Essay-BR scores essays; it is not an aligned
  minimal-correction corpus.
- **pt-BR spelling:** Gimenes et al. report 1,139 and 1,260 error operations
  from two corpora, supporting language-specific accents, cedilla, character
  edits and spacing. These counts are neither unique mappings nor training
  pairs, and the study does not establish a reusable mapping release.
- **Implementation:** CoGrOO and variant-specific LanguageTool resources
  support an actionable route. Share validated morphological primitives, but
  keep variant-specific dictionaries, prompts, source provenance, held-out
  examples and acceptance tests. Do not count shared rules twice.
- **Remaining gate:** pt-PT needs audited export/pattern extraction; pt-BR
  needs broader verified grammatical evidence beyond lexical confusions and
  a reusable spelling inventory. Both require stratified corruption validation
  and variant-competent review. These are concrete verification tasks, not
  evidence that either variant is impossible.

The supporting references and exact caveats are in the updated DaLA source;
no new corpus or rule implementation was tested during this local comparison.

- pt-PT: [COPLE2](https://aclanthology.org/L18-1649/) offers empirical grammar,
  spelling and lexical annotation. The DaLA survey already considers a route
  feasible in principle; usable annotated access and safe-rule validation
  remain unresolved. A large paired corpus is not required if sound empirical
  rules can be applied to new clean text.
- Both variants: [LanguageTool Portuguese rules](https://github.com/languagetool-org/languagetool/tree/master/languagetool-language-modules/pt/src/main/resources/org/languagetool/rules/pt)
  are a tooling lead, not certification of DaLA suitability.
- pt-BR: [Penteado and Perez](https://arxiv.org/html/2306.15788v2) describe
  102 grammar, 100 spelling, 40 fast-typing and 40 internet-language cases.
  This small constructed evaluation set is not broad natural-error training
  coverage. Reserve it for validation; register normalization is not necessarily
  grammatical correction. [CoGrOO](https://ccsl.ime.usp.br/cogroo/assets/LREC_COGROO_2006.pdf)
  supplies another grammar-checking lead requiring assessment.

## Recommendation

| Variant | Broad-data gate | DaLA gate | Action |
|---|---|---|---|
| pt-PT | Substantial text/SFT candidates verified; accepted yield and quality pending | Credible route, validation pending | Near-term verification; no longer hold for apparent lack of pt-PT instructions. |
| pt-BR | Abundant Portuguese supply; isolate and audit variant-specific subsets | Updated DaLA tier B: feasible candidate, grammar/spelling validation pending | Second-wave verification alongside pt-PT; do not borrow pt-PT's validation. |

Use explicit variant prompts and metadata; validate shared transformations for
both standards. Never mark a valid variant incorrect solely for differing from
the requested style. Keep ambiguous text Portuguese-neutral rather than forcing
an unreliable label. No bulk downloads or admissions made: cards, papers and
size metadata only were inspected on 2026-09-26.

# Data Mix Policy

Last updated: 2026-06-01
Confidence: high  
Scope: Dataset inclusion policy for academic/non-commercial HRM-Text training.

## Objective

Replace or supplement Sapient's original cleaned corpus with a cleaner, more controllable mix while preserving HRM-Text's PrefixLM training format:

```text
instruction span + response span
```

This repo does not currently train on raw documents as ordinary causal-LM pretraining. Raw text must be converted to continuation rows:

```text
condition = direct
instruction = ""
response = document chunk
```

Primary evaluation goal, clarified on 2026-06-01: data-mix changes should aim
to be strong across all currently run evaluations, not just Danish evaluations.
This includes English factual/reasoning/reading-comprehension benchmarks
(`MMLU`, `Winogrande`, `ARC-C`, `BoolQ`, `DROP`, `HellaSwag`, `MATH`,
`GSM8k`), Danish dfm-evals (`danish-citizen-tests`, `dala`, `gec_dala`,
`wmt24pp-en-da`, `multi_wiki_qa`, `piqa`, `ifeval-da`,
`generative-talemaader`, summarization tasks such as `NordjyllandNews`), and
code/human-eval style tasks. Treat drops in any of these families as a
data-balance regression unless an ablation intentionally trades one family
against another.

## Continuation Data

Only Danish continuation data is currently allowed:

- Include: `danish-foundation-models/danish-dynaword`
- Exclude: Common Pile. Common Pile was removed from the downloader manifest.

Recommended continuation share: capped auxiliary slice, roughly 5-10% of total tokens if used.

## Sapient Cleaned Policy

Sapient cleaned data is included only after source filtering.

Broad exclusions:

- ReClor
- SciBench
- ScienceQA
- most FLAN
- most Tasksource

Narrow FLAN/Tasksource allow overrides are documented in [[pages/source-filtering]].

## Include / Prefer

Academic/non-commercial use permits CC-BY-NC sources, but provenance and GDPR/PII concerns still matter.

Good instruction/reasoning sources:

- Sapient non-denied cleaned sources
- `synquid/danish-verifiable-reasoning`
- `synquid/translation-100k`
- `synquid/ifbench-train`
- Oliver Kinch Danish instruction/backtranslation, QA, summarization, and translation sources with public/OPUS provenance:
  - `oliverkinch/instruct-bt` is now approved for the DFM mix after row-level
    access and schema verification on 2026-05-27.
  - Added open sources: `multi-wiki-qa-high-quality-subset`, `eur-lex-sum-instruct`, `machine-translation-da-{en,uk,ar}`, `danmarks-statistik-bt`, `tidsskrift-dk-bt`, `doab-da-bt`, `danish-university-portals-bt`, `eur-lex-bt`, `dynaword-bt`, and `dst-table-prompts-bt`.
- AllenAI Dolci SFT variants
- AllenAI Tulu SFT/persona/reasoning variants
- Nemotron instruction/SWE/terminal/agentic/multilingual, capped by objective
- DynaWord as the only raw continuation source
- Local DBC/LexDK/OPUS instruction-style additions under `data/downloads/datasets`: DBC abstracts/reviews/Faktalink/Forfatterweb, LexDK articles, and OPUS Danish-English translation shards when both language sides are present. These are converted to supervised bibliographic/article-writing/translation tasks, not empty-instruction raw continuation.

Gated sources not downloaded in the earlier `--exclude-gated` run, but intended
for the DFM mix once explicitly downloaded with an authorized token:

- `danish-foundation-models/laerebogen`
- `synquid/wiki-instruct-da`
- `oliverkinch/instruct-bt`
- `synquid/mt-da-deepseek`
- `synquid/wildchat-100k-qwen-messages`, tightly capped because it is generated
  answers to WildChat prompts.

## Oliver Kinch Source Policy

Reviewed on 2026-05-21 from Hugging Face dataset metadata, cards, and sample schemas.

Include:

- Public Danish backtranslation/instruction datasets where targets come from CC-BY, EU legal, DST, DOAB, university portal, tidsskrift.dk, or DynaWord-style public provenance.
- Public Danish QA from Wikipedia-derived `multi-wiki-qa-high-quality-subset`.
- Danish translation pairs from `machine-translation-da-en`, `machine-translation-da-uk`, and `machine-translation-da-ar`, with sampling caps because `da-en` is much larger than the other additions.

Exclude by default:

- Raw Oliver Kinch document corpora such as `danish_wikipedia`, `eur-lex`, `tidsskrift-dk`, `tidsskrift-dk-en`, `danmarks-statistik`, `danish-university-portals`, `doab-da`, and `dst-table-prompts`; the current plan allows only Danish DynaWord as raw continuation data.
- `oliverkinch/dsk-bt`; the card says it is derived from non-public internal DSK material and is not intended for public redistribution.
- `oliverkinch/da-bird`; useful as an evaluation/text-to-SQL benchmark, but its Harbor task layout and CC-BY-SA inherited BIRD tasks make it a poor fit for the current mixed training corpus.
- `oliverkinch/dynaword-no-bt`; Norwegian rather than Danish.
- Small/no-license synthetic/demo datasets (`life-in-the-uk-multiple-choice`, `synthetic-qa`, `synthetic-qa-context-qa`, `mt_da_uk`) unless separately justified.

Confidence: medium for source-card safety; high for local manifest/converter support after `py_compile` and downloader dry-run.

## Exclude / Avoid

- AllenAI WildChat was removed from the downloader manifest by decision.
- Common Pile was removed from the downloader manifest by decision.
- Raw non-Danish continuation corpora should not be used in the current plan.
- Local DBC raw/crawl/continuation files are denied by default. Only the instruction-style DBC, LexDK, and OPUS families listed above are allowlisted.

## Sampling Shape

For a 40B-token target, a reasonable target allocation remains:

- 35-45% math/reasoning/STEM
- 25-35% Danish instruction/chat/translation
- 10-20% general instruction/chat
- 5-15% code/SWE/terminal/agentic
- 0-10% Danish raw continuation

Use token-budgeted sampling rather than row-count caps alone.

## DFM Mix

Decision on 2026-05-27. Confidence: high for local schema/access checks and
manifest/config edits; medium for the exact caps until sampled analytics are
measured.

The DFM mix is the next mixed-corpus target:

- Name: `dfm`
- Sampling config: `data_io/prefix_config_dfm.yaml`
- Intended output: `data/sampled_dfm`
- Training data config: `config/data/dfm.yaml`
- Target size: about 28B tokens per epoch
- Content: safe filtered Sapient sources plus all approved additional sources,
  including gated Danish instruction sources where access is available.

`synquid/wildchat-100k-qwen` is superseded by
`synquid/wildchat-100k-qwen-messages`. The messages variant was row-accessible
with an explicit HF token on 2026-05-27 and uses a `messages` JSONL schema that
the existing converter supports. It is included only with a tight
`50,000`-row cap per file. `oliverkinch/instruct-bt` was also row-accessible on
2026-05-27 and uses a `messages` Parquet schema supported by the existing
converter.

## DFM2 Raw-Text Task Mix

Decision recorded on 2026-05-30. Confidence: high for the target policy and
verified local DFM2 sample outputs.

Superseded clarification, 2026-05-30: `X` is not the entire current DFM
direct/instruction-style corpus. In this context, `X` is the existing
approximately `2.8B` DynaWord direct/continuation-token slice per epoch. Keep
that existing direct slice and add `5X` additional raw-text-derived task tokens.

DFM2 should keep the current DynaWord direct/continuation token budget as `X`,
then add raw-text-derived objectives with the following covered-token budgets:

- `X` existing direct/continuation tokens, preserving the current DynaWord
  plain-text signal.
- `X` continuation-task tokens where each example gives a non-trivial document
  prefix as instruction/context and trains the model to generate the suffix.
  The prefix should be randomly selected between `25%` and `75%` of the chunk.
- `X` denoising-task tokens where the instruction contains corrupted text and
  the response is the clean original text. Corruption should affect about
  `10%` of words, using a mix of word swaps, deletions, replacements, and
  random inserted words after selected words.
- `3X` autoregressive span-filling tokens. The instruction contains the full
  text with masked spans; the response rewrites the full clean text, filling in
  the masked spans.

Total DFM2 raw/plain-text-derived target size is therefore `6X` covered tokens
for the DynaWord-derived component if `X` is measured over sampled covered
tokens. With `X ~= 2.8B` per epoch, the new additions are about `14B` tokens per
epoch and the total DynaWord-derived component becomes about `16.8B` tokens per
epoch. The added `5X` part is split as `1X` prefix-continuation, `1X`
denoising, and `3X` span filling, with span filling intentionally dominating
the self-supervised additions.

Implemented and sampled locally on 2026-05-30:

- Generator: `scripts/generate_dfm2_dynaword_tasks.py`
- Sampling config: `data_io/prefix_config_dfm2.yaml`
- Training data config: `config/data/dfm2.yaml`
- Generated converted sources: `data/converted_sources_dfm2_dynaword_tasks`
- Generated tokenized sources: `data/tokenized_dfm2_dynaword_tasks`
- Tokenized union: `data/tokenized_dfm2`
- Sampled output: `data/sampled_dfm2`
- Analytics: `data/show_analytics_dfm2.md`

The final implementation avoids `repeat: 2` for generated DynaWord task
families because repeating can duplicate rows. Instead it creates two unique
prefix-continuation variants, two unique denoising variants, and six unique
span-fill variants. The generated tokenization was run with exactly one
tokenizer worker.

Verified DFM2 sampled totals:

- `metadata.total_length`: `42,317,252,803` tokens per epoch.
- Global unique tokens sampled: `71,801,166,164 / 95,130,241,400` across four
  epochs.
- Retained direct DynaWord slice: `11,255,771,693` covered tokens across four
  epochs, or `2,813,942,923` per epoch. This is `X`.
- Generated DynaWord task additions: `56,253,792,196` covered tokens across
  four epochs, or `14,063,448,049` per epoch. This is `4.998X`.

Measured generated additions by objective:

| Objective family | Covered tokens / epoch |
|---|---:|
| Prefix continuation v1 | `1,320,302,625` |
| Prefix continuation v2 | `1,320,302,124` |
| Denoising v1 | `1,456,506,751` |
| Denoising v2 | `1,456,578,755` |
| Span fill v1 | `1,418,307,269` |
| Span fill v2 | `1,418,288,911` |
| Span fill v3 | `1,418,277,059` |
| Span fill v4 | `1,418,307,269` |
| Span fill v5 | `1,418,305,179` |
| Span fill v6 | `1,418,272,107` |

## English Eval Remediation Hypothesis

Recorded on 2026-05-31. Confidence: medium for causal attribution, high for
local source-filter and analytics facts.

Problem: DFM/DFM2 improves Danish coverage but can underperform the original
Sapient run on English factual/commonsense/reading-comprehension evaluations
such as `MMLU`, `Winogrande`, `ARC-C`, `HellaSwag`, `DROP`, and `BoolQ`.

Local evidence:

- Original Sapient sampling had broad `flan` as the largest component:
  `23,896,311,328` covered tokens across four epochs, or `42.6%` of the
  original covered-token budget. It also had `tasksource` at `617,688,319`
  covered tokens.
- The source filter now denies broad `sapient_cleaned/data_clustered/flan/**`
  and `sapient_cleaned/data_clustered/tasksource/**`, with narrow allow
  overrides only for selected math/science/commonsense/reasoning tasks.
- The denied FLAN/Tasksource space included many English benchmark-adjacent
  instruction families: ARC, BoolQ, DROP, SQuAD, TriviaQA, Natural Questions,
  SuperGLUE/GLUE, ANLI/SNLI/MNLI, CoQA/QuAC, summarization/news, dialogue, and
  broad commonsense tasks.
- Three Platypus files are also denied: `reclor.jsonl`, `scibench.jsonl`, and
  `scienceqa.jsonl`; these are smaller than FLAN but align with reasoning,
  reading comprehension, and science QA.

Likely explanation:

- `MMLU` loss is probably mostly factual/world-knowledge and broad
  instruction coverage loss, not just missing exact MMLU-style rows.
- `ARC-C`, `BoolQ`, and `DROP` loss is likely direct removal of related
  QA/reading-comprehension formats from broad FLAN.
- `Winogrande` and `HellaSwag` are partially protected because narrow FLAN
  allow overrides include `winogrande` and `hellaswag`, but the current caps
  may still be much smaller than the original broad FLAN exposure.

Candidate remediation mix:

- Add a small English open-text self-supervised slice, initially `5-10B`
  covered tokens per epoch, from cleaner Common Pile components rather than
  broad web text. Prefer filtered/public-domain/open-license components such as
  Wikimedia, StackExchange, PubMed, arXiv abstracts/papers, USGPO/regulations,
  USPTO, public-domain books/reviews, and Library of Congress material. Avoid
  YouTube/IRC/social-chat components by default because of PII/GDPR and
  conversation-quality risks.
- Convert this slice with the same objective family as DFM2, but in English:
  direct continuation, prefix continuation, denoising, and span filling. This
  should help language modeling, factual recall, and reading-comprehension
  robustness without reintroducing the broad FLAN aggregate.
- Upscale existing approved English instruction sources before re-admitting
  risky Sapient aggregates: `allenai_tulu_*`, `dolci_*`,
  `nemotron_instruction_reasoning_off`, `allenai_if_sft_verified`, selected
  `nemotron_multilingual`, `no_robots`, and retained allowed FLAN/Tasksource
  science/commonsense tasks.
- For benchmark-adjacent train data, make an explicit policy distinction:
  using official train splits of ARC/BoolQ/DROP/HellaSwag/Winogrande is useful
  for capability recovery but should be marked as benchmark-adjacent and kept
  separate from “clean generalization” runs. If included, hash-dedupe against
  evaluation prompts and report it clearly.

Recommended first ablation:

- Keep DFM2 unchanged.
- Add `5B` covered tokens per epoch of English Common-Pile-derived
  self-supervised tasks from the cleaner components above.
- Add `2-4B` covered tokens per epoch by raising caps on approved English SFT
  sources.
- Optionally add a tightly capped, benchmark-adjacent train-only slice for
  ARC/BoolQ/DROP/HellaSwag/Winogrande only in a separate run label.

## DFM3 English Recovery Mix

Decision recorded on 2026-05-31. Confidence: high for local repo
implementation and Common Pile inventory dry-run; medium for final token
proportions until DFM3 is downloaded/tokenized/sampled and
`data/show_analytics_dfm3.md` is inspected.

DFM3 is the combined remediation run:

- Base: DFM2.
- Add selected Common Pile raw text with DFM2-style objectives using
  `X ~= 2.8B` covered tokens per epoch, matching the DFM2 DynaWord direct
  slice.
- Add another approximate `14B` covered tokens per epoch by raising caps for
  already approved English/multilingual instruction data most likely to help
  English factual, commonsense, and reading-comprehension evals.

Common Pile raw-objective target:

- `1X` direct continuation.
- `1X` prefix continuation, with 25-75% prefix.
- `1X` denoising, with about 10% word corruption.
- `3X` span filling, implemented as three span-fill variants.

Not included in DFM3: paragraph reordering. The DFM2 and DFM3 generators only
emit direct continuation, prefix continuation, denoising, and span-filling
families. A safe follow-up is an additive DFM4-style task source that samples
multi-paragraph documents from both DynaWord and selected Common Pile, shuffles
paragraph order while preserving paragraph contents, and asks the model to
restore the original order. Use response text as the original correctly ordered
document rather than only an index sequence, so target-only training still
teaches fluent reconstruction. Confidence: high for current absence; medium for
the proposed mix until implemented and sampled.

Summarization follow-up candidates:

- Already included/local instruction-style summarization includes DBC abstracts
  and the Oliver Kinch Danish EUR-Lex summarization manifest entry.
- Common Pile `arxiv_abstracts_filtered` contains standalone abstracts, while
  `arxiv_papers_filtered` contains full paper text with abstract-like sections.
  These can be paired by arXiv id or section-extracted to create paper-to-
  abstract summarization tasks, subject to per-record license filtering.
- Common Pile `pubmed_filtered` contains full PubMed Central article text with
  license metadata and can often support article-to-abstract or intro/body-to-
  abstract tasks if an abstract section can be extracted robustly.
- Common Pile `uspto_filtered` has patent text where early summary/object
  sections may be extractable, but this is weaker and noisier than arXiv/PubMed.
- External HF candidates that need explicit license/provenance checks before
  inclusion: `ccdv/pubmed-summarization`, `ccdv/govreport-summarization`,
  `billsum`/`FiscalNote/billsum`, `allenai/multi_lexsum`, `bigbio/multi_xscience`,
  and `laion/Scientific-Summaries`. Avoid news-web summarization corpora such as
  CNN/DailyMail, XSum, and Multi-News by default because they are more likely to
  reintroduce copyrighted-news risk. Confidence: medium.

## DFM4 Paragraph Reordering And Summarization

Decision recorded on 2026-06-01. Confidence: high for local implementation and
final sampled analytics.

DFM4 is DFM3 plus six additive task families:

- `dfm4_dynaword_paragraph_reorder__`: paragraph reordering from DynaWord,
  targeting about `2.8B` covered tokens per epoch.
- `dfm4_common_pile_paragraph_reorder__`: paragraph reordering from selected
  Common Pile, targeting about `2.8B` covered tokens per epoch.
- `dfm4_arxiv_paper_summarization__`: arXiv paper-to-abstract summarization
  extracted from locally downloaded Common Pile arXiv papers, targeting about
  `2.8B` covered tokens per epoch.
- `dfm4_govreport_summarization__`: GovReport summarization from
  `ccdv/govreport-summarization`, capped conservatively with `repeat: 2`
  because this source is small and unique coverage will be much smaller than
  exposure coverage.
- `dfm4_wiki_cat_sum_summarization__`: Wikipedia/WikiSum-derived
  summarization from `GEM/wiki_cat_sum`, capped conservatively with `repeat: 2`
  because this source is also relatively small and repeated exposure should not
  dominate.
- `dfm4_laion_scientific_summaries__`: structured scientific summarization
  from the arXiv slice of `laion/Scientific-Summaries`, enlarged to absorb the
  remaining summarization budget.

Summarization length policy adjustment, 2026-06-01. Confidence: high for local
schema/length samples; medium for final token proportions until DFM4 analytics
are inspected.

- LAION Scientific-Summaries full structured responses are usually too long
  for the current 4k-context training format. A local sample showed median
  full-response length around `14k` characters, leaving no document budget under
  the response-preserving length policy. The generator is therefore adjusted to
  use the full structured summary only when it naturally fits; otherwise it
  falls back to a compact response from `executive_summary`, `key_results`, and
  `three_takeaways`, and finally to abstract-to-`key_results` or
  abstract-to-`three_takeaways` tasks when document-to-summary does not fit.
- GovReport is not problematic because of source quality; the risk is
  conversion quality. Its summaries are often long relative to 4k context, so
  response preservation can leave too little source document. With `repeat: 2`,
  GovReport is a small auxiliary source, but DFM4 analytics should confirm that
  converted rows retain useful document context.
- WikiCatSum has short enough targets in local samples and should work with the
  current document-trimming policy.
- Common Pile arXiv paper summaries do not have the LAION full-structured-
  response problem. A local sample found `## ABSTRACT` extraction in about
  `69%` of the first `4,000` sampled records from two shards; abstracts had
  median length around `965` characters and median remaining document budget
  around `1,735` characters.

The new HF downloader entries are:

- `govreport_summarization`: `ccdv/govreport-summarization`,
  `document/train-*.parquet`.
- `wiki_cat_sum`: `GEM/wiki_cat_sum`, `main_splits/train-*.jsonl`.
- `laion_scientific_summaries`: `laion/Scientific-Summaries`,
  `data/arxiv/*.parquet` only by default. The HF card reports `cc-by-4.0` and
  LLM-generated structured summaries; use this as a synthetic-data source.

Local inventory on 2026-06-01:

```text
govreport_summarization:        435.4 MB,     3 files
wiki_cat_sum:                     5.4 GB,     4 files
laion_scientific_summaries:     142.7 GB, 4,008 files
Total selected HF bytes:        148.6 GB
```

Implemented local paths:

- Generator: `scripts/generate_dfm4_tasks.py`
- Tokenized union builder: `scripts/build_tokenized_dfm4_tree.py`
- Sampling config: `data_io/prefix_config_dfm4.yaml`
- Training data config: `config/data/dfm4.yaml`
- Stage script: `scripts/prepare_dfm4_paragraph_and_summarization.sh`

Superseded: the first DFM4 sampled analytics used four epochs and the earlier
single-window paragraph-reorder generation. The current sample below supersedes
those four-epoch numbers.

Current DFM4 sampled analytics, verified 2026-06-01:

- `data/sampled_dfm4/metadata.json` reports `total_length=72,007,089,569`
  tokens per epoch and `max_seq_len=4097`; sampling was run with `epochs=5`.
- `data/show_analytics_dfm4.md` reports `360,035,447,845` covered tokens
  across five epochs, or `72,007,089,569` covered tokens per epoch.
- DFM4 additive category exposure across five epochs:
  - `dfm4_common_pile_paragraph_reorder`: `7,919,193,665` covered tokens.
  - `dfm4_laion_scientific_summaries`: `7,320,261,295` covered tokens.
  - `dfm4_dynaword_paragraph_reorder`: `3,205,404,709` covered tokens.
  - `dfm4_wiki_cat_sum_summarization`: `1,141,780,940` covered tokens.
  - `dfm4_arxiv_paper_summarization`: `725,773,415` covered tokens.
  - `dfm4_govreport_summarization`: `25,075,850` covered tokens.
- The final GovReport contribution is intentionally tiny; the conservative
  `repeat: 2` keeps it auxiliary because long summaries make conversion quality
  less reliable at 4k context.
- The final LAION contribution is much larger than the original broken
  full-structured-summary conversion would have been, but still far below the
  requested residual summarization budget because only short-enough or compact
  summary forms are retained.

Important caveat: the user asked for `2.8GB` per epoch, interpreted here as
the standing project target of approximately `2.8B` covered/exposure tokens per
epoch. The sampler is row-capped, not byte-capped, so exact budgets require
post-sampling analytics inspection and cap tuning.

Length-policy plan retained for near-term execution:

- Keep `sample_tokenized.py` truncation as a final guard only.
- Add conversion/generation-time length policy by task type.
- Raw continuation is safe as empty-instruction response-only data.
- Prefix continuation should trim prefix if needed, but preserve a non-trivial
  suffix/response.
- Reconstruction tasks such as denoising, span fill, and paragraph reorder
  should enforce response space at least equal to instruction payload space
  plus prompt overhead; generated chunks should be about half-context by char
  proxy unless token-aware fitting is added.
- Summarization should keep the summary response intact when possible, trim the
  source document to leave room for the response, and drop rows whose summary
  alone is too long.
- Translation should preserve target parity with source; drop or split very
  long pairs instead of truncating target aggressively.
- Extractive QA should cap context or trim around answer spans when available;
  reserve a small fixed answer budget.
- Chat/tool/agent/SWE data should trim oldest history/logs first and never let
  history erase the assistant response.
- Generic instruction/output rows should be response-priority: trim instruction
  first, drop or split overlong responses.
- Add sampler analytics for dropped/truncated rows and truncated response
  tokens per task before treating sampled caps as final.

Current cap/repeat recommendations before DFM4 sampling:

- Cap `sapient_cleaned__data_clustered__flan__cot_` explicitly rather than
  leaving it uncapped through prefix overlap. The concern is not that the data
  is intrinsically low quality, but that it is benchmark-adjacent, template
  heavy, and can make English eval gains less clean/broader if it silently
  dominates retained FLAN.
- Keep DFM4 GovReport and WikiCatSum exposure conservative. The previous
  `repeat: 8` and `repeat: 6` are superseded by `repeat: 2` for both sources.
  Shift the remaining summarization budget to LAION Scientific-Summaries and
  arXiv paper summarization.
- Preserve the intended self-supervised objective ratio: direct continuation,
  prefix continuation, denoising, and paragraph reordering are each `1X`
  families, while span filling is `3X` in aggregate. For Common Pile, this means
  either leave all three span-fill variants at the same per-file cap as the
  direct/prefix/denoise families, or reduce all of those family caps together.
  Do not reduce span-fill variants below the other Common Pile raw-objective
  families.
- For DFM4, `X = 1.4B` covered/exposure tokens per epoch is the chosen
  controlled target for the additive raw-objective families. This gives roughly
  `9.8B` tokens/epoch across direct continuation, prefix continuation,
  denoising, paragraph reordering, and aggregate span filling (`3X`). Based on
  DFM3 analytics, the starting Common Pile caps are `5k` rows/file for
  direct/prefix continuation and `2.5k` rows/file for denoising and each
  span-fill variant. This preserves the `3X` aggregate span-fill budget because
  there are three span-fill variants. DFM4 paragraph-reorder starting caps are
  `30k` rows/file for DynaWord and `2.5k` rows/file for Common Pile, pending
  DFM4 analytics because paragraph reordering is also a reconstruction-style
  objective with higher tokens/row.
- `synquid_danish_verifiable_reasoning` and `oliverkinch_instruct_bt` are both
  set to `repeat: 5` for DFM4. This keeps useful Danish reasoning/instruction
  signal without the heavier duplicate exposure from the earlier
  `synquid_danish_verifiable_reasoning` `repeat: 20`.
- Consider reducing `laerebogen_with_followups` repeat from `2` to `1` if DFM4
  becomes too large or too Danish-instruction-heavy; DFM3 analytics show it is
  already a large Danish instruction component at about `5.1B` exposure tokens
  per epoch.
- Consider reducing `nemotron_multilingual` from `250k` max/source to
  `100k-150k` unless multilingual transfer is explicitly prioritized; DFM3
  analytics show it is one of the largest non-Danish instruction components at
  about `8.9B` exposure tokens per epoch.
- Post-DFM4 assessment: `nemotron_multilingual` is probably not the most
  efficient source for recovering English MMLU/ARC-C/BoolQ/DROP-style scores.
  The local README says it is translated from Nemotron Math, Competitive
  Programming, and Science into German, Spanish, French, Italian, Japanese,
  and Chinese; prompts/answers are in the target language while reasoning
  traces remain English. It is useful for multilingual STEM/code/math transfer
  and may help reasoning robustness, but it is not English factual/world
  knowledge, English commonsense, or English reading-comprehension coverage.
  In DFM4 it contributes `35,754,497,240` sampled tokens across four epochs
  (`13.4%` of category exposure, `19.3%` of response exposure), which is large
  relative to its expected direct benefit for MMLU/ARC-C. For an English eval
  recovery run, prefer lowering this cap and reallocating some budget to
  English instruction/reasoning/QA sources such as `nemotron_instruction`,
  Dolci/Tulu, selected retained FLAN/Tasksource benchmark-adjacent train
  families, and clean English raw-text objectives. Confidence: high for local
  schema/analytics; medium for transfer-effect prediction.
- DFM4 adjustment after that assessment: `nemotron_multilingual__` is reduced
  to `max_per_file: 50_000`. The reclaimed budget is reallocated to diverse
  English instruction/reasoning sources and benchmark-adjacent Sapient FLAN
  train-derived families. `allenai_big_reasoning_traces`,
  `allenai_verifiable_reasoning_*`, `natural_reasoning`,
  `principia_collection`, `textbook_reasoning`, `webinstruct_verified`,
  `nemotron_instruction_reasoning_off`, Dolci SFT/no-tools, and Tulu SFT caps
  were raised moderately rather than using large repeats. Confidence: high for
  config edits; medium for expected eval impact.
- For academic/non-commercial training, RACE and TriviaQA are now accepted as
  benchmark-adjacent sources with explicit caps. The source filter admits RACE
  reading-comprehension files and TriviaQA/Trivia question files from the
  Sapient FLAN tree, plus ARC, BoolQ, DROP, SQuAD, ANLI, MNLI,
  GLUE/SuperGLUE, HellaSwag, Winogrande, OpenBookQA, QASC, SciQ,
  StrategyQA, Quartz, COPA/XCOPA, PIQA, and StoryCloze train-derived families.
  Superseded on 2026-06-01 for harsh robots: Natural Questions Open and
  MS MARCO are excluded again.
  `stereoset_classification_race` remains excluded because "race" there is
  the protected-attribute sense, not the RACE reading-comprehension benchmark.
  Confidence: high for local file matching; medium for source-card risk.
- Relationship to the original Sapient mix, 2026-06-01. Confidence: high for
  local analytics/config inspection; medium for impact prediction. The original
  Sapient sample was dominated by broad FLAN: `23.90B` covered tokens across
  four epochs (`42.6%`), with `SYNTH` at `14.27B` (`25.4%`) and `tasksource`
  at `0.62B` (`1.1%`). DFM4 caps are deliberately not a row-for-row recreation
  of that mix. The `20k` per-file caps on selected FLAN benchmark-adjacent
  families are intended to recover ARC/BoolQ/DROP/SQuAD/TriviaQA/RACE/NLI/
  commonsense formats while keeping each source bounded. Superseded for harsh
  robots: NQ/MS MARCO/WMT/News Commentary are now excluded. The
  generic FLAN fallback is lower (`5k` per file), so newly allowed broad
  residual FLAN remains auxiliary. Tasksource remains tightly capped (`10k`,
  with `race-c` at `20k`). Repeats are used mainly for small, trusted Danish
  sources and small summarization sources; large English recovery sources use
  caps rather than repeats to increase diversity and avoid duplicate exposure.
  The existing `data/show_analytics_dfm4.md` predates the latest cap changes
  and still shows old exposure such as `nemotron_multilingual` at `35.75B`
  across four epochs; rerun sampling is required for final DFM4 exposure
  numbers after the current config changes.
- Current remaining source-filter exclusions after the Article 3/GDPR policy
  update, computed by `python scripts/build_filtered_source_tree.py --dry-run`
  on 2026-06-01. Confidence: high for local filter evaluation. Intended filter
  result after the later review/spam/ReClor tightening: `9,832` allowed data
  files and `337` denied data files. The denied data files are `312` Sapient
  FLAN files matching user/chat/social/review/opinion/spam/toxicity PII-risk
  patterns, `23` Sapient Tasksource files matching similar PII-risk or ReClor
  eval-only patterns, and two explicit Platypus eval-only exclusions:
  `reclor.jsonl` and `scibench.jsonl`. `scienceqa.jsonl` is now included.
- Legal/policy reassessment for non-commercial EU academic training with an
  intent to publish open weights, 2026-06-01. Confidence: medium; this is not
  legal advice. The working basis is Article 3 scientific-research TDM, not
  ordinary open-license reuse. Under that basis, lawful access and secure copy
  handling matter more than permissive licensing, and contractual limits that
  contradict Article 3 are not treated as blockers. ScienceQA is included under
  this rationale. ReClor and SciBench remain excluded by project decision for
  training and may be used later for evaluation. Included sources that deserve
  extra notation before open-weight publication are mainly those with possible
  personal data: chat, social-media, user reviews, toxicity/offensive speech,
  and similar non-public-person text. Sources that are acceptable under this
  policy should not be downweighted merely because Sapient downweighted them
  differently; use caps for corpus balance and duplicate-exposure control.
- Clarified policy update, 2026-06-01. Confidence: medium. The current project
  decision is that the EU DSM Directive Article 3 research TDM exception is the
  working copyright basis when a qualifying research organisation has lawful
  access to the dataset/content. Under that basis, licensing terms, ShareAlike,
  non-commercial terms, and benchmark adjacency are not blockers by themselves;
  GDPR/PII risk involving non-public persons remains the hard constraint.
  Article 3 also requires appropriate security for TDM copies retained for
  scientific research. ReClor and SciBench stay excluded from training by
  project decision and may be used later for evaluation. ScienceQA is included
  under the lawful-access/TDM rationale unless later legal review rejects that
  basis. For allowed FLAN files, the default target is to match Sapient-original
  per-file exposure: generic FLAN `max_per_file: 5_000`, FLAN CoT uncapped as
  in the original config, generic Tasksource `max_per_file: 10_000`, and
  Platypus `repeat: 10`. DFM4 is much larger than Sapient original and excludes
  the PII-risk files, so allowed FLAN should no longer dominate percentage-wise.
- Lawful-access clarification, 2026-06-01. Confidence: medium. Do not treat
  "available on Hugging Face" as sufficient proof of lawful access. The stronger
  Article 3 case is content accessible without login or technical circumvention
  from an apparently lawful source, such as the rightsholder/original publisher
  website, open-access repository, authorised institutional subscription, or
  official dataset host. If IXL/source educational content used by ScienceQA is
  visible on the IXL site without login or circumvention, that is treated as a
  strong lawful-access basis for Article 3 research TDM even if website terms
  purport to forbid training, because Article 7 makes contractual provisions
  contrary to Article 3 unenforceable. Third-party mirrors remain weaker unless
  there is evidence they are authorised or the same content is lawfully
  accessible from an original/public source.
- Robots.txt clarification, 2026-06-01. Confidence: medium. For Article 3
  scientific-research TDM, robots.txt is not an Article 4-style rights
  reservation mechanism and should not by itself defeat the exception. It is
  still operational evidence about whether the source is trying to constrain
  automated access and whether a collection method is respectful/non-abusive.
  For Article 4 general TDM, machine-readable reservations for public online
  content matter directly. IXL's robots.txt allows ordinary `User-agent: *`
  access to science skill pages but disallows `GPTBot`, `CCBot`, and
  `Applebot-Extended`; this supports public page access for ordinary browsing
  but not generic bot training under Article 4. The checked IXL science skill
  pages return HTTP 200 without login and describe "free questions"; their HTML
  includes an unauthenticated practice model and daily-practice-limit logic, but
  the question text itself is loaded dynamically rather than embedded in the
  static HTML. Treat IXL as publicly browsable with no login for at least some
  practice access, but verify exact ScienceQA-source question accessibility if
  we need source-by-source evidence.
- Bot-specific robots.txt interpretation, 2026-06-01. Confidence: medium. A
  robots.txt exclusion for named AI crawlers such as `GPTBot`, `CCBot`, or
  `Applebot-Extended` should be treated as strong evidence of a rights
  reservation/opt-out for Article 4 general TDM by those agents, and as an
  operational signal not to use those agents for collection. It is not the same
  as a login wall, paywall, anti-circumvention control, or global disallow for
  ordinary browsing. Current EU practice is unsettled, but the Article 3
  scientific-research exception does not contain Article 4's rights-reservation
  mechanism, and German LAION litigation commentary indicates that Article 3 may
  still apply to scientific-research TDM even where an Article 4 opt-out would
  matter for general/commercial TDM. For this project, bot-specific robots
  exclusions do not by themselves make no-login public human access unlawful,
  but they do argue against direct broad crawling with the excluded agents.
- Full-site/relevant-path robots.txt interpretation, 2026-06-01. Confidence:
  medium. If `User-agent: *` disallows the full site or the relevant source
  path, do not directly crawl that source for corpus construction. For Article 4
  this is a strong machine-readable rights reservation. For Article 3 it still
  is not an opt-out mechanism, but it weakens the lawful-automated-access case
  and should require another lawful access route such as an official dataset
  download, authorised institutional subscription, API/license, or manual/public
  inspection for verification rather than automated harvesting. A public page
  that can be viewed manually without login can still support source
  verification, but direct automated collection against a relevant
  `User-agent: *` disallow should be avoided.
- LAION TDM decision relevance, 2026-06-01. Confidence: medium. The Hamburg
  Regional Court's 2024 Kneschke v. LAION decision treated LAION's dataset
  creation as covered by Germany's Article 3 scientific-research TDM
  implementation, rather than needing Article 4. This supports the project
  distinction between Article 3 research TDM and Article 4 general/commercial
  TDM opt-outs. It is not a CJEU ruling and should not be read as a blanket
  clearance for commercial model training or unrestricted redistribution of
  source content, but it supports treating research dataset preparation as TDM
  where access is lawful and the actor qualifies for Article 3.
- Systematic inclusion/exclusion reconsideration, 2026-06-01. Confidence: high
  for local filename/filter audit, medium for legal classification. Current
  policy keeps ScienceQA and most FLAN/Tasksource benchmark, exam, translation,
  news-summarization, and reasoning files included under the Article 3 lawful
  access/TDM rationale, unless they raise non-public-person GDPR/PII risk. It
  excludes direct user/chat/social/review/opinion/spam/toxicity families such
  as Twitter/tweets, dialogs, PersonaChat, QReCC/wiki_dialog, SMS/spam,
  Amazon/Yelp/IMDb/app/book/product reviews, opinion spam, CivilComments,
  hate/offensive/toxicity, and similar Tasksource recasts. ReClor stays
  training-excluded in both Platypus and Tasksource forms by project decision;
  SciBench stays training-excluded. Superseded for harsh robots on 2026-06-01:
  News Commentary is excluded. Other news summarization files such as
  CNN/DailyMail, XSum, MultiNews, Newsroom, and Gigaword are included for now
  because the current hard filter is GDPR/PII plus harsh full-site/relevant-path
  robots cases rather than copyright licensing alone, but they should remain
  documented as Article 3-dependent sources rather than permissive-license
  sources.
- Web/chat/robots review, 2026-06-01. Confidence: high for local dataset-card,
  sample, regex, and robots.txt observations; medium for legal classification.
  Common Pile sources are accepted for DFM4 by project decision and no longer
  need source-by-source exclusion just because they are raw web-derived
  components. `synquid/wildchat-100k-qwen-messages` remains the riskiest
  current Danish chat source: the local card says it is generated Qwen answers
  to WildChat prompts, and a simple local scan of 99,688 user-prompt rows found
  65 email-like matches, 2,052 phone-number-like matches, 1,797 URL matches,
  and 4,619 rows matching address/name/contact words. Many matches are benign
  false positives, but examples include prompts about collecting name, address,
  and email for orders and prompts naming family members. Project decision:
  keep this source included, but capped tightly, and treat it as a priority
  candidate for later PII scrubbing.
  `TIGER-Lab/WebInstruct-verified` is Apache-2.0 and locally consists of
  228,736 web-sourced verifiable QA rows across math, physics, chemistry,
  business, finance, economics, history, biology, and related subjects. Its
  card explicitly says the authors traced WebInstruct data back to original web
  pages and re-crawled question-answer pairs; keep it as high-value reasoning
  data, but mark it Article-3/source-route dependent because per-row source
  URLs are not present in the local Parquet schema. `HuggingFaceH4/no_robots`
  is not a robots.txt issue despite its name: it is a 9,500-row human-annotated
  CC-BY-NC instruction dataset. The issue is that the card leaves source data,
  annotator identity, and personal/sensitive information as "More Information
  Needed"; a local regex scan found 9 email-like matches and 37 phone-like
  matches, including a prompt whose task is to redact PII. Keep it capped as a
  small human instruction source, but do not treat it as provenance-clean.
- Representative robots.txt review for FLAN news/web summarization and web
  QA/search, 2026-06-01. Confidence: high for fetched robots.txt files; medium
  for mapping many-source datasets to representative domains. Checked domains:
  CNN, Daily Mail, BBC, New York Times, Washington Post, The Guardian, Reuters,
  wikiHow, English Wikipedia, Google, Bing, `statmt.org`, and `data.statmt.org`.
  CNN, Daily Mail, BBC, New York Times, Washington Post, The Guardian, and
  wikiHow did not show full-site `User-agent: *` disallow in the fetched files,
  but most explicitly disallow named AI crawlers such as GPTBot, CCBot,
  Applebot-Extended, ClaudeBot/anthropic-ai, or similar. Under the current
  Article 3 research policy this is not by itself an exclusion, but it argues
  against direct fresh crawling with those agents. Reuters is harsher:
  `User-agent: *` disallows `/`, so Reuters-derived news content should rely on
  an official dataset/subscription/source route, not direct web crawling.
  Google and Bing do not globally disallow all ordinary crawling, but both
  disallow search endpoints (`/search` and many search-like paths), so Natural
  Questions/MS MARCO should be treated as official-dataset-route sources rather
  than something to recreate by crawling search result pages. English Wikipedia
  is comparatively clean for article-derived QA/summarization: no full-site
  `User-agent: *` disallow was observed, though API/special paths are
  restricted. `statmt.org` had no full-site disallow, but `data.statmt.org`
  disallowed `/`; WMT/news-commentary files should therefore be treated as
  official dataset downloads, not direct automated crawling from `data.statmt`.
- Harsh robots exclusion update, 2026-06-01. Confidence: high for local filter
  output. Project decision: keep `synquid/wildchat-100k-qwen-messages` capped,
  but exclude the harsh robots cases from Sapient FLAN. `source_filter.yaml`
  now denies `natural_questions_open`/`naturalquestion`, `msmarco`, `wmt`, and
  `newscomm` FLAN files. The corresponding allow overrides and DFM4 sampling
  cap entries for Natural Questions Open and WMT were removed. Rebuilding the
  filtered source tree produced `9,780` allowed files, `389` denied files, and
  `806,841,101,662` allowed bytes. Verification found zero
  `natural_questions_open`, `msmarco`, `wmt`, or `newscomm` Parquet files under
  `data/filtered_sources/sapient_cleaned/data_clustered/flan`.
- Sapient-original cap/repeat equivalence for DFM4, 2026-06-01. Confidence:
  high for config inspection. For Sapient-origin files that remain included,
  DFM4 generally keeps the original Sapient sampling rule rather than an exact
  token quota: `SYNTH` uses `max_per_file: 20_000`, FLAN CoT remains uncapped
  via the `cot_` prefix, ordinary FLAN uses `max_per_file: 5_000`,
  `dmmath`/`ampsmathematica`/`tasksource`/`openmathinstruct2`/`acereason`/
  `openthoughts2`/`sudoku_extreme` keep the original caps, and
  Sapient `Platypus` plus Sapient `no_robots` keep `repeat: 10`. The explicit
  benchmark-adjacent FLAN entries in `prefix_config_dfm4.yaml` mostly restate
  the same `5_000` per-file cap before the generic FLAN fallback; they are not
  higher than the original FLAN cap. This means retained files should have
  comparable exposure to the original under the same sampler, modulo stochastic
  sampling/boundary effects and token length distribution. Excluded files have
  zero exposure, and newly added non-Sapient DFM/DFM2/DFM3/DFM4 sources use
  their own caps/repeats and substantially increase the total epoch size.
- Non-Sapient DFM4 cap/repeat review, 2026-06-01. Confidence: high for local
  config and existing `data/show_analytics_dfm4.md`; medium for final numbers
  until DFM4 is resampled after the latest filter/config edits. Most added
  sources are reasonable, but several deserve attention. The existing analytics
  predate the latest `nemotron_multilingual__ max_per_file: 50_000` reduction;
  with 18 local converted files, the current cap should be far smaller than the
  old `8.9B` covered tokens/epoch shown in analytics and is probably reasonable.
  `laerebogen_with_followups repeat: 2` is still large at about `5.1B` covered
  tokens/epoch in the old analytics; reduce to `repeat: 1` if DFM4 should give
  more room to English factual/commonsense data. DFM2 DynaWord objectives are
  balanced as intended: prefix continuation and denoising are each about one
  unit, and span filling is about three units. DFM3 Common Pile objectives have
  the right 1:1:1:3 shape but at only about `1.5B` covered tokens/epoch per
  unit, not the original `2.8B`; increasing caps would make sense only if we
  deliberately want a larger English raw-objective share. DFM4 summarization
  and paragraph-reordering additions underfill several targets: arXiv
  summarization and DynaWord paragraph reordering are limited by generated row
  volume rather than sampler caps, while WikiCatSum could reach the intended
  ~`0.45B` covered tokens/epoch by increasing `repeat` from `2` to about `4`.
  GovReport remains tiny even with `repeat: 2` and should stay auxiliary rather
  than be repeated aggressively. Small Danish Oliver Kinch/Synquid sources with
  high repeats are mostly negligible in token share and can remain unless we
  want to reduce exact duplicate exposure for aesthetic/data-diversity reasons.
- OPUS and high-repeat inventory, 2026-06-01. Confidence: high for config and
  analytics inspection. OPUS Danish-English is small in DFM4 because
  `opus__` has `max_per_file: 200_000` and the local converted OPUS source is a
  single large file (`58,522,141` rows, `5.3G` converted Parquet). The sampler
  therefore draws only about `200k` rows/epoch, producing about `20.6M` covered
  tokens/epoch despite the source containing about `6.0B` converted tokens.
  Repeats greater than 2 in the Sapient-original portion of DFM4 are
  `sapient_cleaned__data__Platypus__ repeat: 10` and
  `sapient_cleaned__data__no_robots.jsonl repeat: 10`. Repeats greater than 2
  outside Sapient-original are: `dbc__dbc-faktalink repeat: 20`,
  `dbc__dbc-farfatterweb repeat: 20`, `lexdk__ repeat: 10`,
  `oliverkinch_instruct_bt__ repeat: 5`,
  `synquid_danish_verifiable_reasoning__ repeat: 5`,
  `synquid_ifbench_train__ repeat: 10`,
  `oliverkinch_multi_wiki_qa_high_quality__ repeat: 20`,
  `oliverkinch_eur_lex_sum_instruct__ repeat: 20`,
  `oliverkinch_dst_table_prompts_bt__ repeat: 10`,
  `oliverkinch_tidsskrift_dk_bt__ repeat: 10`,
  `oliverkinch_dynaword_bt__ repeat: 8`,
  `oliverkinch_danish_university_portals_bt__ repeat: 10`,
  `oliverkinch_danmarks_statistik_bt__ repeat: 10`,
  `oliverkinch_doab_da_bt__ repeat: 10`,
  `oliverkinch_eur_lex_bt__ repeat: 10`, and standalone
  `no_robots__ repeat: 10`.
- DFM4 non-Sapient cap update, 2026-06-01. Confidence: high for config edit;
  medium for token estimates until resampling. `data_io/prefix_config_dfm4.yaml`
  was adjusted so no repeat exceeds `10`. OPUS Danish-English was raised from
  `max_per_file: 200_000` to `10_000_000`; based on the old analytics, this
  should raise OPUS from about `20.6M` to roughly `1.0B` covered tokens/epoch if
  sampling remains close to linear. DFM3 Common Pile self-supervised caps were
  scaled to approximately match DFM2 DynaWord unit sizes with clean round caps:
  direct/prefix continuation `5_000 -> 10_000` rows/file and denoising/span-fill
  variants `2_500 -> 5_000` rows/file. This should move each Common Pile unit
  from about `1.5B` to about `3.0B` covered tokens/epoch, preserving the
  1:1:1:3 objective shape. Repeats clipped from above 10:
  `dbc__dbc-faktalink 20 -> 10`, `dbc__dbc-farfatterweb 20 -> 10`,
  `oliverkinch_multi_wiki_qa_high_quality 20 -> 10`, and
  `oliverkinch_eur_lex_sum_instruct 20 -> 10`. Repeats increased to 10:
  `oliverkinch_instruct_bt 5 -> 10`,
  `synquid_danish_verifiable_reasoning 5 -> 10`, and
  `oliverkinch_dynaword_bt 8 -> 10`.
- Paragraph-reorder scaling assessment, 2026-06-01. Confidence: high for local
  generator/config/analytics inspection; medium for impact prediction. The
  DFM4 paragraph-reorder generator is context-conservative: it trims source
  text to about half the context-char budget, requires at least three
  paragraphs, uses at most eight paragraphs, and rejects rows where the
  scrambled instruction would crowd the response. Therefore context length is
  not the main blocker. The current blocker is row volume and duplicate
  exposure. Existing analytics show DynaWord paragraph reorder at about
  `0.16B` covered tokens/epoch (`0.058X`) and Common Pile paragraph reorder at
  about `0.66B` covered tokens/epoch (`0.24X`). DynaWord has only `243,318`
  generated rows, so raising only the sampler cap can at most move it to around
  `0.08X`; reaching `0.25X` would require roughly four shuffled variants per
  eligible row, and reaching `1X` would require too many near-duplicate
  variants. Common Pile has `2,443,026` generated rows and is capped at
  `2,500` rows/file; raising the cap toward the generated maximum of `6,000`
  rows/file can grow it to roughly `0.55-0.60X` without new generation. Reaching
  `1X` would require regenerating more rows per Common Pile file and/or adding
  variants. Recommended conservative target: raise Common Pile paragraph
  reorder first; keep DynaWord paragraph reorder small unless we intentionally
  generate a small number of alternate shuffles and accept response
  duplication.
- Paragraph-window improvement idea, 2026-06-01. Confidence: high for current
  code behavior and local tokenization, medium for expected gain. Superseded:
  `generate_dfm4_tasks.py` previously trimmed text before paragraph splitting
  and then used the first up to eight paragraphs. It now splits the full
  cleaned document into paragraphs first, samples deterministic contiguous
  paragraph windows that fit the reconstruction budget, and shuffles each
  window. The current DFM4 sample uses regenerated DynaWord paragraph-window
  tasks plus the existing complete Common Pile paragraph tokenization. A full
  Common Pile paragraph-window regeneration was started but stopped because it
  became slow on large shards; do not treat the partially regenerated Common
  Pile converted tree as complete.

Remaining excluded Sapient original clusters after the DFM4 filter expansion,
measured by original Sapient sampled exposure across four epochs:

| Cluster | Original sampled tokens | Benchmark value | Problem level | Covered elsewhere |
|---|---:|---|---|---|
| Miscellaneous FLAN/NIV2 task soup | `13.47B` | Medium: broad instruction following and task format diversity | Medium/high: broad aggregator, mixed provenance, many tiny/generated task transforms | Partly by Tulu, Dolci, Nemotron instruction, DFM raw-objective tasks |
| Translation/multilingual | `2.15B` | Low/medium for English evals; useful for translation/multilingual | Medium: many WMT/multilingual components with varied provenance; WMT/news-commentary now excluded for harsh robots | Mostly by OPUS, Synquid/Oliver Kinch translation, Nemotron multilingual |
| Classification/sentiment/toxicity | `1.18B` | Low for MMLU/ARC/DROP; some general classification skill | Medium/high: reviews/social/toxicity datasets can have PII and web provenance | Partly by Tulu/Dolci/general instruction |
| Conversational QA/RC left out, e.g. CoQA/QuAC/MSMARCO/ROPES | `1.01B` | Medium/high for reading comprehension, lower direct eval overlap than DROP/SQuAD/NQ | Medium/high: web/dialog sources and some ambiguous provenance; MS MARCO and NQ now excluded for harsh robots | Partly by SQuAD/DROP/CoQA/QuAC/ROPES plus Common Pile objectives |
| Paraphrase/grammar/generation | `0.96B` | Low/medium; helps linguistic robustness | Low/medium to medium depending source; less core to target evals | Partly by Tulu/Dolci and direct instruction data |
| NLI/GLUE/SuperGLUE still excluded, mostly SNLI/eSNLI and residual tasks | `0.69B` | Medium for entailment/reading robustness | Medium: benchmark-adjacent and mixed upstream licenses | Partly by admitted ANLI/MNLI/RTE/SuperGLUE plus Tasksource NLI |
| News/web summarization | `0.67B` | Medium for summarization, low for MMLU/ARC | High: copyrighted news/web summarization risk | Covered by DFM4 LAION/arXiv/GovReport/WikiCatSum and DBC summaries |
| Commonsense/story residual, e.g. CREAK/ECQA/SenseMaking/Social/Cosmos | `0.56B` | Medium/high for HellaSwag/Winogrande/common sense | Medium: benchmark-adjacent, some web/social/story provenance | Partly by admitted HellaSwag/Winogrande/COPA/PIQA/StoryCloze/QASC |
| Platypus denied: ReClor, SciBench, ScienceQA, and Tasksource ReClor | `0.30B` | Medium for reasoning/science | High: textbook/web/exam/source-rights concerns and benchmark contamination | Partly by ARC/OpenBookQA/SciQ/QASC, science summaries, reasoning data |
| Dialog/chat residual | `0.29B` | Low/medium; chat robustness, not core evals | Medium/high: dialogue/web provenance and possible PII | Covered by Tulu/Dolci/Nemotron agentic and approved chat data |
| Tasksource residual eval-adjacent | `0.07B` | Low/medium | Medium: recast/mixed provenance | Partly by admitted Tasksource NLI/logic/medical/science |
- `nemotron_agentic` currently has `max_per_file: 800k`, but DFM3 analytics
  show about `1.4B` exposure tokens per epoch, much smaller than
  `nemotron_multilingual`; lower it only if truncation/long-history analytics
  show poor response retention.
- `allenai_tulu_v2_sft_long_mixture` currently has `max_per_file: 1.5M`, but
  the actual DFM3 exposure was only about `0.6B` tokens per epoch because the
  local file has about `532k` rows. It is not currently a large token-share
  problem, but it remains a long-context/truncation-risk source.
- Consider lowering `allenai_tulu_v2_sft_long_mixture`,
  `nemotron_agentic`, and `nemotron_swe` or marking them `long_context: drop`
  after adding truncation analytics, because they are prompt/history-heavy and
  are likely to suffer response truncation.
- Keep small high-value Danish tasks repeated, but avoid further increasing
  `synquid_danish_verifiable_reasoning`, `synquid_wiki_instruct_da`,
  `oliverkinch_*_bt`, and DBC repeats until DFM4 analytics show the new
  English summarization/reordering additions have not diluted Danish too much.

Selected Common Pile sources added to the downloader manifest under group
`common_pile`:

- `common-pile/wikimedia_filtered`
- `common-pile/wikiteam_filtered`
- `common-pile/stackexchange_filtered`
- `common-pile/pubmed_filtered`
- `common-pile/arxiv_abstracts_filtered`
- `common-pile/arxiv_papers_filtered`
- `common-pile/usgpo_filtered`
- `common-pile/regulations_filtered`
- `common-pile/uspto_filtered`
- `common-pile/project_gutenberg_filtered`
- `common-pile/public_domain_review_filtered`
- `common-pile/library_of_congress`

Local dry-run inventory on 2026-05-31:

```text
Selected Common Pile bytes: 275.1 GB
Selected files: 480
```

The largest selected components are `common_pile_uspto_filtered` (`137.9 GB`),
`common_pile_pubmed_filtered` (`40.6 GB`),
`common_pile_stackexchange_filtered` (`32.5 GB`),
`common_pile_wikimedia_filtered` (`20.1 GB`), and
`common_pile_library_of_congress` (`16.8 GB`).

Implemented local paths:

- Downloader manifest: `scripts/download_training_datasets.py`
- Common Pile raw-text conversion: `scripts/convert_filtered_sources.py`
- Generator: `scripts/generate_dfm3_common_pile_tasks.py`
- Tokenized union builder: `scripts/build_tokenized_dfm3_tree.py`
- Sampling config: `data_io/prefix_config_dfm3.yaml`
- Training data config: `config/data/dfm3.yaml`
- Stage script: `scripts/prepare_dfm3_english_recovery.sh`

The DFM3 sampling config raises the approved English/multilingual instruction
caps for `nemotron_*`, `dolci_*`, `allenai_tulu_*`,
`allenai_big_reasoning_traces`, `allenai_if_*`, `allenai_verifiable_*`, and
other already approved English reasoning/instruction families. Based on DFM2
analytics, fully uncapping the already present approved English-ish families
can add roughly `12.9B` covered tokens per epoch; the new config also includes
approved-but-not-yet-sampled manifest entries such as `natural_reasoning`,
`principia_collection`, `textbook_reasoning`, `webinstruct_verified`,
`allenai_code_meta_reasoning`, and `allenai_rlvr_ifeval` so the sampled
addition can approach the requested `14B` after download/conversion.

## Original Plus Mixed Danish Instruction Rich

Verified locally on 2026-05-24 from:

- `data/show_analytics_original_sapient.md`
- `data/show_analytics_original_plus_mixed_danish_instruction_rich.md`
- `data/tokenized_original_plus_mixed/union_manifest.json`

The `original_plus_mixed_danish_instruction_rich` sample preserves the original Sapient portion almost exactly, then adds mixed/Danish sources on top.

Source union facts:

- `data/tokenized_original_plus_mixed/union_manifest.json` records `original_tasks: 5212`.
- All `5212` original Sapient tokenized tasks are present in the original+mixed union.
- `mixed_tasks_added: 226`.
- `include_mixed_sapient: false`, so duplicate Sapient tasks from the mixed tree are skipped rather than added twice.

Covered-token comparison across 4 epochs:

| Sample | Original Sapient covered tokens | Global covered tokens |
|---|---:|---:|
| `sampled_original_sapient` | `56,140,714,711` | `56,140,714,711` |
| `sampled_original_plus_mixed_danish_instruction_rich` | `56,140,181,363` | `110,736,199,356` |

Difference in the original Sapient portion: `-533,348` tokens, about `0.00095%`. This is consistent with sampling/shuffling boundary effects, not intentional reweighting of the original subset.

Per-category ratios for original Sapient categories in `original_plus_mixed_danish_instruction_rich` versus `original_sapient`:

| Category | Ratio |
|---|---:|
| `Platypus` | `1.000000` |
| `SYNTH` | `1.000000` |
| `acereason` | `0.999996` |
| `ampsmathematica` | `0.999924` |
| `dmmath` | `0.999944` |
| `flan` | `0.999960` |
| `openmathinstruct2` | `1.000217` |
| `openthoughts2` | `0.999905` |
| `sudoku_extreme` | `1.000000` |
| `tasksource` | `0.999956` |
| `textbookreasoning` | `1.000000` |

Task/file-level comparison:

- Matching original tasks: `5212 / 5212`
- Missing original tasks: `0`
- Exact same covered-token count: `2645 / 5212`
- Within `10,000` tokens: `4738 / 5212`
- Within `100,000` tokens: `5193 / 5212`
- Largest observed task difference: `openmathinstruct2__cot.parquet`, about `+902,328` covered tokens, ratio `1.000279`.

Conclusion: use `original_plus_mixed_danish_instruction_rich` when the goal is to keep the original Sapient training signal essentially unchanged while adding roughly `54.6B` extra covered tokens over 4 epochs from the mixed/Danish additions.

Confidence: high.

## Mixed English/Danish Filtered 2x-Original Cap

Verified/created locally on 2026-05-24.

The first mixed-only filtered sample used `data_io/prefix_config.yaml` against `data/tokenized_mixed` and produced a very large corpus:

- Output: `data/sampled_mixed_english_danish_filtered`
- Analytics: `data/show_analytics_mixed_english_danish_filtered.md`
- Per-epoch `metadata.total_length`: `70,644,435,216` tokens
- 4-epoch covered tokens: `282,577,740,862`

Cause: `data/tokenized_mixed` task names include source prefixes such as `sapient_cleaned__data_clustered__SYNTH__...`, but the shared `data_io/prefix_config.yaml` uses unprefixed Sapient rules such as `SYNTH__`, `flan__`, and `dmmath__`. Those rules therefore did not match the filtered Sapient tasks in the mixed-only tokenized tree, causing most filtered Sapient files to be sampled uncapped.

A dedicated capped config was added:

```text
data_io/prefix_config_mixed_2x_original.yaml
```

Target ceiling:

- Original Sapient sample: `56,140,714,711` covered tokens over 4 epochs.
- Original per-epoch size: `14,035,178,677.75` tokens.
- 2x ceiling: `28,070,357,355.5` tokens per epoch.

Dry-run estimate after applying the new config with PrefixLM truncation/filtering:

- Estimated per-epoch sampled tokens: `24,630,898,966`
- Ratio to original per-epoch size: `1.755x`
- This is below the `2x` ceiling.

Final completed sample:

- Output: `data/sampled_mixed_english_danish_filtered_2x_original`
- Analytics: `data/show_analytics_mixed_english_danish_filtered_2x_original.md`
- Hydra config: `config/data/mixed_english_danish_filtered_2x_original.yaml`
- `metadata.total_length`: `24,630,436,020` tokens per epoch
- 4-epoch covered tokens: `98,521,744,082`
- Ratio to original per-epoch size: `1.755x`
- Unique sampled tokens: `55,258,504,135 / 78,082,414,846` (`70.77%`)
- Directory size: about `625G`

Note: `sample_tokenized.py` copies the full token bank into output `tokens.npy` before writing capped epoch indices, so the disk footprint remains large even though the epoch index budget is capped.

Estimated largest per-epoch category shares:

| Category | Estimated tokens/epoch | Share |
|---|---:|---:|
| `sapient_cleaned` | `8,129,060,084` | `33.0%` |
| `danish_dynaword` | `3,093,170,660` | `12.6%` |
| `nemotron_multilingual` | `3,001,252,991` | `12.2%` |
| `allenai_big_reasoning_traces` | `1,624,580,477` | `6.6%` |
| `dolci_instruct_sft` | `1,380,220,345` | `5.6%` |
| `dolci_instruct_sft_no_tools` | `962,106,919` | `3.9%` |
| `allenai_tulu_v2_sft_mixture` | `902,702,844` | `3.7%` |
| `allenai_tulu_3_sft_mixture` | `831,587,284` | `3.4%` |

Sampling was launched in tmux:

```bash
cd /work/dfm/HRM-Text/data_io
/home/ucloud/miniforge3/envs/hrm/bin/python sample_tokenized.py \
  tokenized_path=../data/tokenized_mixed \
  output_path=../data/sampled_mixed_english_danish_filtered_2x_original \
  prefix_config_path=prefix_config_mixed_2x_original.yaml \
  epochs=4 \
  concat_workers=4 \
  > ../data/show_analytics_mixed_english_danish_filtered_2x_original.md \
  2> ../logs/sample_mixed_english_danish_filtered_2x_original.err
```

Session:

```bash
tmux attach -t hrm_sample_mixed_2x_original
```

Confidence: high.

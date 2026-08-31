---
type: Decision Record
title: DFM10 Final Source Reconciliation
description: Final repair, exclusion, and sampling-weight decisions for audited Repair and Filter sources.
tags: [dfm10, data-quality, sampling, repair]
status: stable
last_updated: 2026-08-31
confidence: high
---
# DFM10 Final Source Reconciliation

## Repair dispositions

The final DFM10 build disables `oliverkinch/machine-translation-da-ar`: its
source audit found only 7% usable rows, and Arabic translation is not a current
DFM objective. The inherited DA/UK prefix is also disabled. Its raw 1,726,440
aligned pairs are instead split over eight shards and passed through explicit
Danish/Ukrainian language-direction checks and LaBSE semantic-alignment
filtering. Only accepted pairs are rebuilt as bidirectional Gemma-native tasks.

The old QReCC-II and SciBench prefixes are disabled. QReCC-II is rebuilt by
completing the deliberately open final dialogue turn with the answer supplied
by the source prompt. The converter turns valid rows into either final-answer
prediction or next-question prediction, depending on whether the open source
dialogue ends in a question or an answer. It retains 2,675 of 3,133 zero-shot
rows and 4,259 of 6,231 few-shot rows; missing, template-leaked, and structurally
contradictory turns fail closed. The replacement has 6,934 rows and 1,329,371
exact Gemma-rendered tokens. SciBench retains all 867 rows, but derives the response
contract from the target: 758 concise-answer rows use `direct`, while 109
substantive derivations use `cot`. The replacement has 144,919 tokens.

The completed Scientific Summaries repair was not too strict. It retained
3,312,314 of 3,324,592 source rows (99.631%), never character-truncated a target
or support field, and passed its 40,044-row E4B audit at 91.04% usable. DFM10
therefore disables the legacy character-truncated conversion and integrates the
repaired source at one pass. Tokenization retained all 3,312,314 rows with zero
skips and produced 6,319,894,802 unique tokens. Because this is about five times
the old conversion's 1.27B-token weight, DFM10 caps each of the 4,006 repaired
files at 167 rows. That selects 636,100 rows and an estimated 1.198B tokens per
epoch, sampling broadly across the complete repair while staying near the legacy
budget; final sampled analytics are authoritative.

## Filter dispositions and actual weights

Every one of the 32 `Filter` dispositions in the 2026-08-26 source audit has an
explicit decision in
[`config/dfm10_filter_source_decisions.yaml`](/../config/dfm10_filter_source_decisions.yaml).
The reproducible reconciliation command is:

```bash
PYTHONPATH=. python scripts/reconcile_dfm10_filter_sources.py
```

It writes machine-readable details to
`data/dfm10_filter_reconciliation.json` and the review table to
[`docs/dfm10-filter-reconciliation.md`](/../docs/dfm10-filter-reconciliation.md).
The calculation applies first-match prefix semantics, the 4,097-token sampler
contract, per-file caps, and repeats. Final sampled analytics supersede its
mean-length token estimates.

The final policy uses repaired replacements for WikiCatSum, Danmarks Statistik,
QReCC-II, Code Meta-Reasoning, the DynaWord instruction family,
OpenMathInstruct-2, OPUS DA/EN, NordjyllandNews, and DOLCI tool use. It excludes
DaCoref, the two tiny low-quality MSMARCO question-generation variants, and the
unfiltered Oliver Kinch DA/EN corpus. The remaining borderline sources are kept
at one natural pass. In particular, Multi-Zebra is reduced from 8x to 1x,
Kænguruen from 20x to 1x, Tidsskrift and DynaWord BT from 2x to 1x, and EUR-Lex
BT, EUR-Lex summarization, and DOAB from 10x to 1x. Broad Natural Instructions,
TextbookReasoning, CoEdIT, IF-SFT, ASSET, Tulu algebra, regular QReCC, AESLC,
paper-review, and NewsComm supervision remain at one pass because their breadth
or utility justifies retaining the audited borderline rows without amplification.

## Production gate

Do not construct final epoch indices until all of the following hold:

1. WikiCat recovery generation, independent audit, merge, and tokenization are complete.
2. DA/UK language/alignment filtering, rebuild, and tokenization are complete.
3. Scientific Summaries tokenization is complete.
4. The DFM10 union is rebuilt with all replacement roots.
5. The Filter reconciliation is rerun against that final union and reports no unresolved source.
6. Ten final epoch index sets are sampled and their exact analytics are archived.

## Post-reconciliation quality backlog, 2026-08-30

The statement that the Filter reconciliation has no unresolved source means
that every audited source has an explicit keep, replace, cap, or exclude
decision. It does not mean that the current, substantially revised union has
received a fresh source-stratified quality audit. The original audit covered
17,555 examples from 178 logical sources before several repaired, native-chat,
and newly generated packages reached their final representation.

Before final DFM10 sampling, run a delta audit over the exact tokenized
prompt/target examples in the rebuilt union. Use at least 100 examples per
logical source and stratify large or heterogeneous families more deeply. The
highest-priority strata are:

1. The 17 policy-filtered or repaired Sapient packages (318,751,245 source
   rows in the export inventory). Audit each package and major task family
   independently; a single pooled 100-row Sapient sample is not representative.
2. Final native/4K renderings of Nemotron Terminal, repaired DOLCI tool use,
   Glaive, ToolACE, xLAM, and DeepDive. Combine structural validators with a
   semantic audit, and sample each Terminal adapter/config independently.
3. Folketing error correction. Its accepted-row source audit marked only
   18/25 rows usable, versus 22/25 denoising, 23/25 continuation, and 24/25
   span filling. Audit a larger accepted-row sample and tighten deterministic
   OCR/no-op/corruption gates if the deficit persists; do not regenerate the
   other three families merely because they share the same source corpus.
4. Active one-pass borderline Danish sources: legacy Tidsskrift BT, EUR-Lex
   BT and summarization, DynaWord BT, DOAB, Kænguruen, and Multi-Zebra.
   Prefer exact-answer or grounding checks where possible. Replace legacy
   Tidsskrift BT with the strict-open grounded SFT/chat packages once those
   packages finish rather than amplifying or broadly repairing the BT source.
5. Active one-pass borderline English sources: ASSET, CoEdIT, IF-SFT, Tulu
   algebra, TextbookReasoning, regular QReCC, AESLC, paper-review, NewsComm,
   and the final PII-filtered Natural Instructions representation. These are
   lower priority than the high-volume and tool-use strata; start with
   deterministic contract/answer checks and repair only defects that survive
   a task-aware re-audit.
6. Every package currently marked `work_in_progress` in
   `exports_dfm10/manifest.json`. Generation completion is not an admission
   gate: independent audit, final validation, Gemma-native tokenization, and a
   final-union delta sample are required before sampling weight is assigned.

Do not repeat a full-row LLM audit of every inherited source by default. The
earlier estimate was thousands of B200 GPU-hours and most retained borderline
sources contribute only one natural pass. Use the delta audit to escalate only
high-volume sources, systematic defects, or task families where deterministic
validation identifies a measurable failure mode.

The WikiCat recovery launcher supports `START_PHASE=audit` so a completed 31B
generation/candidate build can resume directly at the independent E4B audit.
An idle-GPU stability barrier is required between the 31B generation and E4B
audit server phases: without it, servers that are still releasing model memory
can leave no KV-cache headroom for the next phase. The finalizer gates on
every fully-written required artifact rather than producer PIDs or one legacy
marker, so a replaced producer or stale tokenization marker cannot incorrectly
release the production gate.

Judge-format failures are retried over four complete audit passes. Any sample
still failing after those retries is recorded as an explicit terminal rejected
judgment, never admitted without a valid audit. A recovery-specific completion
sentinel is written only after the final filtered source has been tokenized.
The WikiCat tokenized root is built from scratch under a temporary path and
then swapped into place; `--force` alone does not prune obsolete task names and
must not be used to refresh this replacement root in place.

## Final production outcome

Production completed on 2026-08-29. The final WikiCat source contains 47,115
rows: 11,791 rows from the earlier grounded repair plus 35,324 of 58,925
generated recovery candidates accepted by the independent E4B audit. The audit
covered every candidate and fail-closed 81 terminal judge-format failures. Its
strict acceptance rate was 59.95% (35,324/58,925). The fresh tokenized root has
one task, zero skipped rows, and 72,179,055 tokens.

The DA/UK repair accepted 446,988 of 1,726,440 aligned source pairs and emitted
893,976 bidirectional rows. Tokenization retained every emitted row across
eight tasks and produced 79,496,908 tokens. A source-weighted 100-row E4B
validation of the repaired output marked 95 rows usable; mean language quality,
instruction/answer coherence, and training value were respectively 4.91, 4.68,
and 4.10 out of 5. The five rejected rows were genuine residual semantic
mismatches, supporting one-pass use without amplification. Audit artifacts are
under `logs/data_audits/machine_translation_da_uk_repaired_e4b_20260829`.
The final Scientific Summaries,
QReCC-II, and SciBench replacement roots contain respectively 6,319,894,802,
1,329,371, and 144,919 unique tokens before sampling.

**Superseded on 2026-08-30:** the earlier final union contained 15,689 task
directories. After integrating the expanded Mimir grounded SFT and other
completed additions, `data/tokenized_dfm10` contains 15,711 task directories.
The Mimir addition contributes three tasks, 732,763 rows, and 138,161,296
Gemma-native tokens at repeat one.

The existing sampling produced `data/sampled_dfm10/epoch_0` through `epoch_9`;
every epoch
has all four index arrays and 229,097,054 rows. `metadata.json` reports
101,731,426,509 tokens per epoch, the rounded mean across the ten independently
sampled epochs. All instruction and response spans were checked to remain
within the 241,976,982,257-token backing array. Exact sampling analytics are in
`data/show_analytics_dfm10.md`. Those sampled indices predate the expanded
Mimir integration and are now a historical snapshot; regenerate them before
claiming that a sampled DFM10 epoch contains the new source.

## Published-package integration audit

The 2026-08-30 reconciliation of `exports_dfm10/manifest.json`,
`data/tokenized_dfm10/union_manifest.json`,
`data_io/prefix_config_dfm10.yaml`, and the sampled analytics found that all 26
uploaded packages and the one `ready_for_upload` package are wired into the
DFM10 build and present in the tokenized union. The already materialized
`data/sampled_dfm10` indices contain 25 of those 27 packages. They predate both
`dfm10-openstax-mimir-sft` and
`dfm10-mimir-grounded-expanded-sft`, whose tokenized roots contain 50,000 rows
in 16 tasks and 732,763 rows in three tasks respectively. Resample DFM10 before
claiming either Mimir package is part of a training epoch.

The intentional non-unit package repeats are Andersen modernization at 20x;
Alexandra ScandiQA and DaNE at 4x; repaired DynaWord instruction at 4x;
repaired DOLCI tool use at 2x; repaired GovReport and WikiCatSum at 2x; and the
repaired DST table prompts, Danish university portals, and Danmarks Statistik
BT sets at 10x. Keep the other uploaded/ready packages at one pass. In
particular, Multi-Zebra's borderline audit, SciBench/QReCC-II's narrow
benchmark-like supervision, and DeepDive's multiple supervised assistant turns
argue against amplifying their small source-row counts. OpenStax and expanded
Mimir are complementary grounded corpora and should also remain at one pass.
Across these ten amplified packages, repetition adds 1,158,846,120 tokens per
epoch beyond their 996,393,628 unique tokens, for a final repeated contribution
of 2,155,239,748 tokens per epoch.

## Tokenizer lineage audit, 2026-08-30

The active DFM10 union does not inherit the legacy 65,536-token arrays from
DFM2--DFM5. Those four historical unions correctly declare the old HRM
tokenizer, but DFM6 retokenized its selected raw/converted sources with the
262,144-entry Gemma tokenizer and `gemma4_native_chat.jinja`. DFM7, DFM8,
DFM9, and DFM10 inherit that Gemma-native lineage. DFM10's union builder also
byte-compares every DFM10 addition's tokenizer/template metadata against the
DFM9 base before linking it.

## Current production sample, 2026-08-30

The superseded sampled snapshot was rebuilt from the current
`data/tokenized_dfm10` union with ten independently permuted epoch index sets.
The sampler consumed 15,737 tokenized task directories and produced
232,138,339 rows in each epoch. `metadata.json` reports 103,143,215,009 tokens
per epoch and a 4,097-token maximum sequence length; `tokens.npy` contains
212,996,621,848 backing tokens. Exact analytics are archived at
`data/show_analytics_dfm10.md`.

Use the recovery-safe wrapper rather than invoking the sampler directly:

```bash
bash scripts/resample_dfm10_current.sh
```

The wrapper sampled into `data/sampled_dfm10_rebuild_20260830`, validated every
instruction and response span against the backing token array in bounded
chunks, and only then atomically promoted the staged directory. The prior
snapshot is preserved as `data/sampled_dfm10_pre_20260830`; a failed sampler or
validator therefore leaves `data/sampled_dfm10` unchanged.

The final Filter preflight command remains
`PYTHONPATH=. python scripts/reconcile_dfm10_filter_sources.py`. Its report
writer must tolerate audit-only unmatched-source records, which intentionally
lack sampled row/token estimates; those fields render as zero instead of
aborting the reconciliation with `KeyError`.

Compared with the canonical seven-epoch DFM8 sample, DFM10 grows from
70,479,433,697 to 103,143,215,009 tokens per epoch (+46.35%), while rows grow
from 218,313,891 to 232,138,339 (+6.33%). Mean sampled tokens per row therefore
rise from 322.8 to 444.3. Eligible source tokens grow from 127.382B to 188.767B,
and backing tokens from 139.427B to 212.997B. The largest positive per-epoch
category deltas are factual FLAN (+10.199B), repaired Nemotron SWE (+6.597B),
the four Folketing transformations (+17.497B combined), native Nemotron
Terminal (+2.889B), repaired OPUS DA/EN (+2.645B), repaired OpenMathInstruct2
(+2.140B), repaired DOLCI tool use (+1.744B), repaired Scientific Summaries
(+1.198B), and OpenStax grounded chats (+1.157B). Several are replacements,
not additive duplicates: raw OpenMathInstruct2 (-6.603B), raw OPUS (-2.904B),
legacy DOLCI tool use (-1.621B), and legacy Scientific Summaries (-1.271B) are
removed.

This snapshot includes the finalized Mimir answer-contract and expanded
grounded SFT packages present in the union at sampling time. The still-running
Mimir IFEval verifier, BoolQ entailment, DROP reasoning, and event/coreference
campaigns are not part of these epochs. The queued English/Danish MedQuAD
adaptation is also absent. Admit these five additions together in the next
union rebuild and resample.

### Folketing value and weight assessment

The four Folketing transformations contribute 17.497B sampled tokens per
epoch, or 16.96% of DFM10: 5.391B denoising, 4.866B error correction, 2.852B
prefix continuation, and 4.388B span filling. This is valuable formal and
historical Danish coverage from 123,018 documents, but it is not 13.2M
independent semantic examples. The four families derive from 3,655,419 source
windows; denoising, error correction, and span filling normally expose closely
related inputs with the same complete clean-window target.

The independent 100-row post-acceptance audit rated 87 rows usable, with mean
language, coherence, and training-value scores of 4.38, 4.59, and 4.48. Results
were 22/25 for denoising, 18/25 for error correction, 23/25 for continuation,
and 24/25 for span filling. Residual historical OCR in the nominal clean target
is the principal risk: synthetic corruption can teach reconstruction back to
an already damaged source. The corpus is therefore high-value auxiliary Danish
midtraining data, but its current 17% share is an aggressive concentration for
a general instruction model.

**Superseded on 2026-08-30:** the initial assessment said that no weight change
had been applied and described equal caps as a proposal. The production
sampling specification now sets `max_per_file: 1000000` for each of the four
Folketing families. At current mean lengths, the cap alone contributes about
5.36B tokens per epoch (5.2% of the current DFM10 epoch) instead of 17.50B.
Because capped sampling carries each task's permutation across epochs, this
still rotates through the larger accepted pool rather than fixing one static
million-row subset.

The independent audit's exact no-reported-issue criterion retained 59/100
rows; 41/100 had an issue in at least one language, coherence, or training-value
dimension. Those labels exist only for the independent 100-row sample and
cannot be projected as row IDs onto the full accepted corpus. A production
strict filter should therefore judge each of the 3,655,419 underlying clean
source windows once and propagate the result to its correlated task variants,
rather than rejudging all 13.2M task rows. Reject unresolved OCR/extraction
damage but do not equate legitimate historical spelling with corruption. Audit
a larger stratified sample of the resulting keep/drop boundary before
retokenizing, rebuilding the union, and resampling. Compare Danish language,
GEC, summarization, instruction, and general English/math evaluations before
treating the cap as final policy.

For scale comparison, canonical DFM9 has 93,929,976,190 tokens and 242,869,754
rows per epoch. Current DFM10 is larger at 103,143,215,009 tokens (+9.81%) but
has fewer rows at 232,138,339 (-4.42%), reflecting its longer repaired,
grounded, tool, and reconstruction examples. Applying the configured four
1M-row Folketing caps in the next resample should reduce DFM10 to approximately
91.00B tokens and
222.91M rows per epoch before stricter-filter length effects, about 3.12%
smaller than DFM9 by tokens. That projected reduction is caused by removing
about 12.14B Folketing tokens from the current mix, not because DFM10's other
additions are smaller than DFM9.

The existing `data/sampled_dfm10` remains the uncapped 103.143B-token snapshot.
Regeneration is deliberately deferred until the four active Mimir campaigns
and queued MedQuAD adaptation finish, avoiding two large rebuilds in immediate
succession.

### Expected quality relative to DFM9

DFM10 is better engineered than DFM9: it replaces known malformed or inflated
representations of Nemotron SWE, DOLCI tool use, OpenMathInstruct2, OPUS,
Scientific Summaries, DBC, Code Meta-Reasoning, GovReport, WikiCatSum,
DynaWord instruction, and several smaller grounded sources. It also adds
factual FLAN, native Terminal supervision, grounded chats, Danish knowledge,
and formal/historical Danish breadth. These changes should improve factual
English, translation, grounded summarization, code/tool behavior, and Danish
coverage per useful token. “Less math” should not be inferred from the total
mix without a complete category accounting. The known reduction is
specifically OpenMathInstruct2: DFM9's 25.02M CoT/direct rows and 6.603B tokens
become 7.49M rows over 581,346 problems and 2.140B tokens after answer
verification, PRM filtering, conflict removal, global deduplication, exact
GSM8K/MATH-test decontamination, and an eight-trace-per-problem cap. Other math
families remain active. This is less duplicated math exposure but substantially
better verified math supervision; net math capability remains an evaluation
question.

Dataset engineering alone does not prove downstream superiority. The current
uncapped sample gives correlated Folketing reconstruction 16.96% of an epoch,
which can dilute conversational, English, math, and agentic supervision and
overweight parliamentary/historical register. The expected ordering is
therefore: strictly filtered and capped DFM10 should outperform DFM9 broadly;
current uncapped DFM10 is likely stronger in several targeted capabilities but
has uncertain aggregate quality. Confirm with a controlled equal-token A/B
continuation from the same checkpoint and optimizer state, evaluating Danish,
English, math/code, tool calling, and summarization suites separately.

### Recommended DFM10 continuation checkpoint

Use the DFM8 XL EMA checkpoint at step 1,650,000 rather than the completed
DFM9 endpoint at step 2,127,489 as the default DFM10 starting point. The later
checkpoint is operationally valid and retains newer optimizer/EMA state, but
its finalized metrics are broadly weaker. From 1.65M to the DFM9 endpoint,
`suite_avg_v3/standard` is effectively flat (`0.72806` to `0.72830`), while
DFM-eval falls from `0.66103` to `0.62751` and EuroEval from `0.56997` to
`0.54702`. Danish, English, Math/Code, and overall headline averages all fall:
`0.62025` to `0.60863`, `0.68637` to `0.67014`, `0.47382` to `0.46289`, and
`0.59348` to `0.57994` respectively. DFM10 was explicitly repaired and expanded
against capability gaps measured at 1.65M, so the known stronger checkpoint is
the cleaner controlled baseline. Preserve the DFM9 endpoint for a short
continuation A/B if compute permits; do not assume its extra training is an
advantage.

A read-only audit resolved all 15,712 active DFM10 task links to 32 physical
token roots. Every root declares the 262,144-entry Gemma tokenizer, the native
Jinja chat-template mode, and thinking disabled. One DFM9 root serving 682
Natural Instructions tasks spells the same chat-template path absolutely
rather than relatively; normalized paths and file contents agree. Sampling
6,028,032 tokens across the beginning, middle, and end of every task found
Gemma vocabulary IDs above 65,535 in every physical root. All instruction and
response index arrays had equal example counts and valid token-array bounds.

Multi-turn source/target checks also match the intended semantics:

- Danish Wikipedia: 261,588 assistant targets and tokenized examples;
- DeepDive: 9,070 assistant targets and tokenized examples;
- repaired DOLCI tool use: 996,180 assistant targets and tokenized examples;
- repaired Nemotron SWE: 2,472,316 explicitly selected targets and tokenized
  examples;
- inherited AI Arena: 4,569 assistant targets and tokenized examples;
- inherited flattened WildChat: 129,688 rows and tokenized examples.

The English and Danish repaired OpenHermes packages contain 1,895,454
assistant targets and 1,895,405 tokenized examples. The 49 fail-closed targets
are 0.0026% of the total; 44 are malformed assistant-first targets with no
prompt and five hit other tokenizer rendering guards. This is a narrow source
cleanup issue, not a tokenizer-lineage mismatch.

Two limitations remain. Historical `tokenizer_info.json` files record paths but
not content hashes, so this audit combines metadata with token-array evidence
rather than proving the exact historical template bytes cryptographically.
The `data/tokenized_dfm9/union_manifest.json` file is also a stale byte-for-byte
copy of the DFM8 manifest even though the DFM9 tree has 694 additional task
links; use the resolved physical-link audit and DFM10 union manifest rather
than that stale DFM9 manifest for current provenance.
Also, `mimir_grounded_500k_model.py` currently defaults its generation/build
length check to the legacy tokenizer. The final Mimir integration explicitly
used Gemma for tokenization, and all 732,763 resulting examples are below 4,096
Gemma tokens (maximum 1,931), so the current corpus is unaffected; future
rebuilds should pass or default to the canonical Gemma tokenizer.

## Hugging Face reconstruction boundary

The Common Pile dependency has three distinct cases. The six Common Pile
corpora used as evidence for expanded Mimir are grounding inputs only; rebuild
DFM10 from the published accepted package
`schneiderkamplab/dfm10-mimir-grounded-expanded-sft` rather than regenerating
it from those corpora. The four audited transformation datasets are likewise
published directly as `schneiderkamplab/common-pile-{denoising,paragraph-reordering,prefix-continuation,span-filling}`.
Their raw Common Pile inputs are not reconstruction dependencies.

**Superseded locally on 2026-08-30:** one inherited exception remained:
`dfm4_arxiv_paper_summarization` directly
uses `common-pile/arxiv_papers_filtered` and contributes 213,354 rows and
129,586,132 unique tokens before DFM10 sampling. Until that converted task is
published as a standalone accepted package and the source mapping is changed,
a faithful from-scratch DFM10 reconstruction still needs this one Common Pile
repository. The other Common Pile repositories are not required.

`common-pile/arxiv_papers_filtered` starts from arXiv's bulk LaTeX source and
metadata carrying per-paper licence declarations. Common Pile admits only
CC BY 3.0/4.0, CC BY-SA 4.0, public-domain, and CC0 records. Its published
dataset card describes conversion from LaTeX to HTML with LaTeXML and then to
plain text with Trafilatura. The subsequent Dolma filtering tags quality,
language, PII, safety, perplexity, and duplicates; its arXiv mixer excludes
documents with English probability at most 0.5 and documents tagged as at
least 90% duplicate, and replaces detected email-address spans. The published
filtered dataset reports 304,048 documents and 19 UTF-8 GB.

The local DFM conversion in `scripts/generate_dfm4_tasks.py` is a further
derived task, not raw-paper continuation. It locates a Markdown-style Abstract
section, requires at least 120 abstract characters, removes that section from
the source text, requires at least 500 body characters, and trims the remaining
paper text so instruction plus target fit a roughly 3,000-character budget. It
then emits a `direct` example with the prompt `Write a concise abstract-style
summary of the scientific paper.`, the arXiv row ID, and the trimmed excerpt;
the removed abstract is the target. Consequently this is excerpt-to-abstract
supervision rather than full-paper summarization. Eight converted shards yield
213,354 rows; DFM10's 100,000-row per-file cap does not reduce any of them.

The 2026-08-26 DFM10 source-quality audit sampled 100 converted examples from
this task and judged them with Gemma 4 26B A4B. All 100 were marked usable.
Mean language quality was 4.95/5, instruction/answer coherence 4.97/5, and
training value 4.96/5; seven rows had at least one issue and the source received
the low-severity score 0.5, role `SFT`, and quality disposition `Use`. Recurring
findings were minor repetition or verbosity and grammar/fluency defects, each
in 2% of the sample. No sampled row was rejected.

That audit supports retaining the source as a small, one-pass scientific-style
SFT component, but it does not eliminate a construction-level grounding risk:
an original abstract can report methods and results not present in the short
paper prefix supplied to the model. Treat the source as useful scientific
abstract-style supervision, not as a gold-standard benchmark for faithful
document summarization. A future standalone package should either provide a
larger evidence-bearing paper selection or filter targets for support by the
retained excerpt.

The exact derivative is now materialized locally as
`exports_dfm10/dfm10-arxiv-paper-summarization-sft`. Its complete scan validates 213,354 rows, and a canonical
content hash over condition, instruction, and response is identical to the
training source. Every row has an arXiv ID, URL, authors, licence, Common Pile
source shard and row, and pinned Hub revision. **Superseded 2026-08-30:** the
package was uploaded publicly as
`schneiderkamplab/dfm10-arxiv-paper-summarization-sft` at commit
`f8b5b81d54e2ace242916b8f1dbd7dcc5248cb09`. This closes the public
from-scratch build dependency on the raw Common Pile repository once the
download/source mapping selects the materialized package.

The exact Hugging Face namespaces represented by repositories used directly
as inherited DFM8/DFM9 training sources or as published DFM10 training packages
are: `AI-MO`, `allenai`, `ccdv`, `common-pile`,
`danish-foundation-models`, `facebook`, `GEM`, `giannor`, `glaiveai`,
`grammarly`, `HuggingFaceH4`, `kobprof`, `laion`, `MegaScience`,
`Muennighoff`, `nvidia`, `oliverkinch`, `open-thoughts`, `Salesforce`,
`sapientinc`, `schneiderkamplab`, `synquid`, and `Team-ACE`. This is a
materialized-training namespace list, not an attribution list: newer DFM10
packages under `schneiderkamplab` also preserve upstream provenance from
organizations such as `alexandrainst` and `zai-org` in their package metadata.

This boundary was verified on 2026-08-30 against the 159-source DFM8 inventory,
the nine DFM9 additions, and 29 published exact DFM10 artifacts. The audit is
stored at `logs/data_audits/dfm10_hf_remote_availability_20260830/report.json`.

## Composite-source duplicate exposure

The active DFM10 union contains four Synquid datasets both as direct tokenized
sources and as constituent files of `danish-foundation-models/dfm-dyna-instruct`.
The composite has repeat one. Per epoch, Danish Wiki Instruct contributes
988,119,510 tokens through its direct repeat-six route plus 164,686,585 through
the composite; Danish verifiable reasoning contributes 18,131,360 through its
direct repeat-two route plus 9,064,406 through the composite; IFBench train
contributes 12,689,130 through its direct repeat-ten route plus 1,262,590
through the composite; and Translation 100k contributes 98,234,612 directly
plus 98,008,752 through the composite. Minor conversion differences mean the
paired token streams are not assumed byte-identical.

Together, the configured direct routes contribute 1,117,174,612 tokens per
epoch, while the composite adds 273,022,333, yielding 1,390,196,945 effective
tokens. A future rebuild should select one lineage per source and then assign
the intended total repeat explicitly, rather than retaining accidental
composite duplication.

## Danish-researcher Hub gap scan

An authenticated/current Hub catalog scan on 2026-08-30 covered
`danish-foundation-models`, `synquid`, `oliverkinch`, `schneiderkamplab`,
`alexandrainst`, `giannor`, `kobprof`, `saattrupdan`, and
`KennethEnevoldsen`.

**Superseded (2026-08-30):** the initial scan recommended reserving the nominal
test splits and made the second Croco repository conditional on a future audit.
The executed decision below admits all charter rows and excludes Croco.

`danish-foundation-models/synthetic-values-model-charter`: use all 1,360 SFT
rows for a small alignment/post-training slice and all 1,360 DPO pairs for
preference training; by the 2026-08-30 project decision, the nominal test files
are not held out. The audited
`danish-foundation-models/croco-munin-apertus-8b-da-50k` candidate is excluded:
49,825 of 49,832 prompts overlap the active `*-simpo-full-50k`, leaving only
seven candidate-only prompts and no material task-coverage gain.
`oliverkinch/danish-personas` is useful as a synthetic
generation seed, not as direct assistant supervision. `alexandrainst/domsdatabasen`
could support grounded Danish legal tasks, but remains deferred because its Hub
card has no explicit license and pseudonymized judgments still carry privacy
and redistribution risk.

Do not add benchmark families (`ifeval-da`, PIQA/GSM8K/WMT, Daisy, Edda,
Da-BIRD, MultiWikiQA derivatives, multilingual ARC/MMLU/HellaSwag/TruthfulQA)
to training. Raw Gigaword/Wikipedia/Reddit corpora conflict with the current
continuation policy. Danish WildChat 4.8M contains translated user prompts but
no assistant targets. The GLM agentic trace snapshot is small, contains failed
and truncated traces, and overlaps existing agentic/SWE supervision. RAGTruth
translations have usage restrictions and unsafe rejected responses as direct
targets. Agentic Code SFT and DA-Refusals are not missing: both are already
present inside `dfm-dyna-instruct`.

---
type: Evaluation Analysis
title: Mimir v1 Evaluation Gap Analysis
description: Detailed capability-gap review of the DFM8 XL 1,650,000-step EMA checkpoint and implications for targeted data generation.
tags: [mimir-v1, dfm8, evaluation, mmlu, synthetic-data, data-planning]
status: stable
last_updated: 2026-08-30
confidence: high
---
# Mimir v1 Evaluation Gap Analysis

## Scope

This review covers the DFM8 XL EMA checkpoint at step 1,650,000, exported as
`exports/dfm8_XL_step1650000_ema_hf` and evaluated at epoch
`6.564012269760203`. The headline result table is
`docs/dfm8-xl-step1650000-eval-metrics.md`; detailed MMLU shard artifacts are
under
`logs/eval/dfm8_XL_steps1250k_1450k_vllm_hrmenv/step_1650000/standard_shards/MMLU/`.

The merged MMLU subject values are unweighted means of four nearly balanced
shards. Per-subject shard sizes differ by at most one in most cases, so this is
negligibly different from a sample-weighted merge, but the merged `n` fields
must not be interpreted as total sample counts.

## Evaluation-contract artifacts

The MMLU run was five-shot, `condition=direct`, `max_tokens=1`, with strict
one-letter scoring. Invalid outputs received chance credit of `0.25`, so a
subject at approximately `0.25` can mean that the model produced almost no
valid option letters. The production run did use the matching Gemma chat
template and stopped on the correct `<turn|>` token; it did not use legacy HRM
prompt markers.

| Subject | Reported accuracy | Invalid rate | Interpretation |
| --- | ---: | ---: | --- |
| High-school mathematics | 0.251 | 0.989 | Not a capability measurement; almost every output violated the one-letter contract. |
| College mathematics | 0.405 | 0.260 | Partly format-affected. Accuracy among valid outputs is approximately 0.46. |
| College chemistry | 0.383 | 0.090 | Mostly a real weakness, with a smaller format component. |
| Abstract algebra | 0.428 | 0.030 | Credible capability gap. |

Prompt length is not the cause. Rendered five-shot prompt lengths are only
534--704 tokens for high-school mathematics and 613--772 for college
mathematics, far below the 4,096-token limit.

The repository's earlier DFM6 investigation already reproduced the production
behavior with the Gemma template: abstract algebra, college mathematics, and
high-school mathematics commonly begin with a `<think>` reasoning trace rather
than an option letter. The one-token cap truncates that trace and strict scoring
marks it invalid. Prompt length is not responsible, and simply asking for a
letter reduced but did not eliminate this behavior on the reasoning-prone
subjects.

A separate deterministic 16-row probe on 2026-08-29 deliberately used the
legacy `hrm_tokens` path and observed immediate `<turn|>` termination. This
confirmed that legacy pseudo-markers are unsafe with a Gemma-tokenizer export,
but it was not a reproduction of the production prompt contract and must not be
cited as the cause of the historical score. The DFM8 tokenizer splits the old
HRM marker strings into ordinary pieces, whereas the original Sapient tokenizer
represents them atomically.

Before using high-school or college mathematics to allocate new training data,
rerun MMLU with the Gemma template, an explicit direct-answer instruction,
enough output room to normalize simple wrappers, retained generations, and zero
credit for invalid output. If reasoning traces remain common, compare a
constrained-choice or choice-log-probability evaluation with a separate
reasoning-then-final-letter evaluation. The near-zero-invalid subjects remain
useful as capability diagnostics; the high-invalid subjects are provisional.

### General evaluator fix, 2026-08-29

The evaluator now fails closed instead of silently combining incompatible
checkpoint and prompt formats:

- `VLLMEngine` validates that every legacy HRM marker is an atomic tokenizer
  token before accepting `prompt_mode=hrm` or `hrm_tokens`.
- The legacy EOA ID is derived from the checkpoint's atomic `<|box_end|>` token
  rather than hard-coded as 11.
- `prompt_mode=auto` selects atomic HRM tokens for the original Sapient
  tokenizer and Gemma chat for exports whose EOS token is `<turn|>`; unknown
  tokenizer contracts fail with an actionable error.
- The evaluation copy of the Gemma 4 template is synchronized byte-for-byte
  with the data-tokenization template.
- Invalid standard MCQ and MMLU outputs now score as wrong. They remain exposed
  through the invalid-rate metric but no longer receive 25% chance credit.
- Gemma standard MCQ configurations now state the one-letter contract
  explicitly, allow up to eight output tokens, and normalize only unambiguous
  forms such as `C`, `(C)`, or `Answer: C`; empty or multi-option responses
  remain invalid.
- `evaluation/config/gemma4_vllm_mmlu_fa4.yaml` is the explicit in-process
  Gemma/FA4 MMLU configuration. Legacy `hrm_vllm_tokens_*` configurations are
  reserved for exports with the original atomic HRM tokenizer.

Regression tests verify prompt-contract rejection, automatic Gemma selection,
tokenizer-derived EOA IDs, and zero credit for invalid MCQ output. A real
tokenizer check confirms that the original Sapient export resolves HRM marker
IDs `6, 7, 8, 9, 11, 12, 13`, while the DFM8 export does not resolve those
markers and has `<turn|>` as EOS.

The corrected four-shard MMLU rerun is queued in
`logs/scheduler/mimir_v1_mmlu_corrected_20260829`. It waits for at least
175,000 MiB free on a GPU, uses the 1,650,000-step EMA HF export, retains
generations, retries three times with batch halving, and merges locally without
overwriting W&B until the result is reviewed.

## Other confirmed evaluation defects

| Result | Defect | Required remedy |
| --- | --- | --- |
| Expanded PIQA EN = 0 | The model often emitted the correct bare `A` or `B`, but the stock Inspect scorer required the exact `ANSWER:\n$LETTER` wrapper and recorded an empty parsed answer. | Rerun with the repository's tolerant, unambiguous PIQA choice scorer or make generation and scorer contracts identical. |
| Generative Talemaader = 0 | The Gemma E4B judge was capped at 64 output tokens. Stored judge responses are truncated before the required final `GRADE:` line, so all 808 samples become grade-not-found failures. | Raise the judge cap to at least 256, preferably emit the grade before a short rationale, and report judge-format failures separately from model failures. |
| Historical sharded MMLU `n` fields | Each shard reports 57 subjects as aggregate `n`; the old generic merger summed that to 228 and averaged per-subject sample counts instead of reconstructing totals. Accuracy was close because shards were balanced, but counts were not meaningful. | Resolved 2026-08-29: the merger now sums each `n_<subject>`, weights each subject metric by that count, and recomputes the macro headline from merged subjects. A local remerge gives 57 subjects and 14,042 total examples across their subject counts. |
| Standard MCQ generation | The historical MMLU/ARC/HellaSwag/WinoGrande/BoolQ path used one generated token. The latter four had zero invalids at this checkpoint, but the contract is fragile for reasoning-prone models. | Keep invalids at zero credit and retained generations; add a canonical constrained-choice or token-log-probability path for direct MCQ capability. |

The expanded `PIQA EN=0` and `Generative Talemaader=0` values must not drive
data allocation. ARC, HellaSwag, WinoGrande, and BoolQ remain usable for this
checkpoint because their historical invalid rates were zero, despite the
fragile one-token contract.

## Credible MMLU gaps

The weakest credible subject groups are:

| Priority | Subjects and scores | Evidence | Data implication |
| --- | --- | --- | --- |
| 1 | College physics 0.244; college chemistry 0.383; abstract algebra 0.428; econometrics 0.431; high-school physics 0.444; formal logic 0.460 | Invalid rates are zero or low, except 9% for chemistry. | Add source-grounded technical problem solving, misconceptions, derivations, units, and conceptual contrasts. |
| 2 | Professional medicine 0.423; professional law 0.439; professional accounting 0.464; anatomy 0.445; virology 0.428 | Large professional-law sample and near-zero invalid rates make this a robust gap. | Add authoritative case vignettes with rationale, distractor analysis, and calibrated uncertainty. |
| 3 | Global facts 0.360; world religions 0.509 | Consistent with NQ Open 0.125 and TriviaQA 0.212. | Add source-grounded factual QA with aliases, temporal metadata, answerability, and diverse domains. |
| 4 | Moral scenarios 0.448; machine learning 0.500; college computer science 0.513; computer security 0.520 | Near-zero invalid rates. | Add compositional scenarios and technical concept/application contrasts rather than isolated trivia. |

Subjects already strong enough not to warrant targeted generation include
marketing 0.825, high-school computer science 0.813, high-school world history
0.802, high-school psychology 0.776, US foreign policy 0.770,
jurisprudence 0.759, and European history 0.757.

## Cross-suite evidence

The MMLU pattern is reinforced by broader results:

| Capability | Relevant results | Assessment |
| --- | --- | --- |
| Compositional reasoning | BBH 0.289, AGIEval 0.376, MMLU-Pro 0.248 | High-priority general gap; likely more valuable than optimizing isolated MMLU subjects. |
| Open-domain factual QA | NQ Open 0.125, TriviaQA 0.212, MultiWikiQA exact match 0.649 | Retrieval-free factual breadth and answer normalization remain weak. |
| Mathematical reasoning | MATH 0.453, GSM8K 0.870 | Arithmetic is strong; advanced symbolic/technical reasoning and answer contracts are weaker. |
| Code | HumanEval 0.567, HumanEval+ 0.494, MBPP 0.533, corrected MBPP+ 0.612 | Useful secondary target, but not the most severe gap. DFM10 already repairs substantial code/SWE data. |
| Tool use and instruction following | BFCL 0.560, IFEval-DA 0.667, IFEval EN 74.35% | Worth rechecking after DFM10's tool-call repairs before generating another large tool corpus. |
| Danish language | DaLA 0.961, GEC-DaLA 0.859, Danish citizen 0.747 | Broad Danish language quality is comparatively strong; targeted Danish gaps should come from specific diagnostics rather than blanket scaling. |

## Recommended generation program

A first targeted program should aim for approximately 1.0--1.5 million accepted
examples, not millions per individual MMLU subject:

| Slice | Accepted rows | Preferred construction |
| --- | ---: | --- |
| Physics, chemistry, algebra, statistics/econometrics, and formal logic | 300k--450k | Ground questions and solutions in open textbooks/problem banks. Include conceptual, quantitative, misconception-correction, and transfer variants. |
| Medicine, anatomy, virology, law, and accounting | 250k--350k | Generate from authoritative source passages as applied cases. Require independent factual audit and retain source identifiers. |
| Compositional and constraint reasoning | 200k--300k | Verifiable symbolic, counterfactual, ordering, classification, and multi-constraint tasks with difficulty balancing. |
| Grounded factual QA | 200k--300k | Generate from diverse high-quality passages; include aliases, no-answer cases, temporal scope, and short-answer normalization. |
| MCQ answer-contract calibration | 50k--100k | Use novel questions only. Mix subject domains and explicitly require one option letter; store free-form rationales separately from direct targets. |

Do not synthesize benchmark paraphrases. Deduplicate prompts, answers, source
passages, and semantic near-neighbors against MMLU, MMLU-Pro, BBH, AGIEval,
GSM8K, MATH, and the other held-out evaluations. For knowledge-heavy domains,
source-grounded mid-training data is preferable to unsupported teacher-only QA.
Keep a broad anchor slice during targeted continuation so the intervention does
not narrow general instruction behavior.

## Grounding-source map

Use authoritative passages as the source of truth and retain source ID, URL,
license, extraction date, and passage hash on every generated row. Existing
instruction/reasoning collections may seed task shapes, but must not silently
become the factual authority.

| Generation slice | Primary grounding sources | Secondary/style sources | Important exclusions and controls |
| --- | --- | --- | --- |
| Physics, chemistry, algebra, statistics, economics, and accounting | OpenStax books for the corresponding subjects; use direct OpenStax exports where possible, with `izumi-lab/open-text-books` only after validating its per-book provenance | `common-pile/arxiv_papers_filtered`, `allenai/peS2o`, and `common-pile/stackexchange_filtered` for advanced transfer and misconception examples | Textbooks should dominate canonical questions. Preserve document licenses; do not treat arbitrary papers or forum answers as unquestioned truth. |
| Formal logic | `OpenLogicProject/OpenLogic`, including its open textbook builds; optionally other explicitly open `forall x` derivatives | Programmatically generated truth-table, proof-step, equivalence, and countermodel tasks with deterministic checking | Do not use benchmark questions as seeds. Compile/parse formulas and verify every target mechanically. |
| Medicine, anatomy, and virology | `common-pile/pubmed_filtered`/PMC Open Access, restricted to acceptable per-document licenses; public-domain US-government health material where provenance is explicit | Review articles and guidelines for case construction and calibrated uncertainty | Prefer reviews/guidelines over isolated findings. Attach dates, distinguish evidence from advice, and independently audit clinical claims. |
| US law and regulation | `common-pile/usgpo_filtered` and `common-pile/regulations_filtered` | Generated issue-spotting, rule-application, and exception cases grounded in quoted provisions | Scope every answer by jurisdiction and date. Exclude proprietary legal summaries and bar-exam/test-bank questions. |
| EU law | EUR-Lex source documents, including the existing Danish/English EUR-Lex material | Bilingual rule-application and document-navigation tasks | Retain CELEX ID, language, document date, and consolidation status; do not present a consolidated text as authoritative beyond its stated date. |
| Grounded factual QA | `common-pile/wikimedia_filtered` plus a versioned Wikidata dump | `common-pile/wikiteam_filtered` only after site-quality filtering; bilingual Danish questions from LexDK, DynaWord, and official Danish sources | Require passage support, aliases, temporal scope, answerability/no-answer cases, and entity-level train/eval deduplication. Wikidata is best used for structure, not fluent evidence passages. |
| Compositional and constraint reasoning | Wikidata subgraphs, OpenStax tables/worked examples, and official statistical tables such as DST or US-government data | `allenai/verifiable-reasoning-filtered-*`, `facebook/principia-collection`, and `MegaScience/TextbookReasoning` as task-pattern seeds | Generate from a latent program/graph and compute the answer independently. Reject any row the solver cannot reproduce. |
| MCQ answer-contract calibration | Novel questions derived from the grounded sources above | Existing direct/instruction templates for phrasing variation | Randomize option order and final letter, generate type-matched distractors, retain a separate rationale, and semantically deduplicate against all held-out benchmarks. This slice teaches the contract, not domain knowledge. |

The repository downloader already knows the principal Common Pile, SciRIFF,
verifiable-reasoning, Principia, and TextbookReasoning sources. OpenStax and the
Open Logic Project should be ingested as first-class, provenance-preserving
sources rather than relying solely on repackaged copies. `SciRIFF`, Principia,
TextbookReasoning, and the AllenAI reasoning sets are useful training/task
sources, but they do not replace the primary grounding layer.

### OpenStax licensing supersession, 2026-08-29

The unconditional OpenStax recommendation above is superseded. Current
OpenStax help and individual book pages describe much of the library as
`CC BY-NC-SA 4.0` and explicitly state that books may not be used to train or
otherwise be ingested into LLMs without OpenStax permission. Do not use current
OpenStax content for Mimir training without written permission.

Some fixed older OpenStax PDFs contain `CC BY 4.0` notices. Whether those exact
historical editions can be used depends on authentic version-level provenance,
their original license and attribution terms, and legal review; current site
content must not be substituted for such a fixed artifact. The provisional
local download `data/downloads/datasets/open_text_books` is quarantined from
generation because `izumi-lab/open-text-books` contains only a `text` field,
does not identify the source book/version per row, declares `CC BY-SA 4.0` at
repository level, and contains rows with embedded `CC BY 4.0` notices. This is
insufficient attribution and license lineage for production SFT.

If permission or a defensible fixed-edition set is obtained, OpenStax remains a
strong technical source for physics, chemistry, algebra, statistics,
economics, accounting, anatomy, and related Mimir gaps. Preserve book, edition,
section, source URL, license, attribution text, and passage hash on every
derived row, and publish derivatives under the required terms. Until then,
substitute sources with unambiguous training-compatible provenance, including
Open Logic for formal logic and appropriately licensed Common Pile scholarly,
government, and Wikimedia sources.

#### Article 3 / Danish section 11c qualification, 2026-08-29

The preceding operational prohibition is qualified for tightly controlled
scientific research by a Danish research organisation. DSM Directive Article 3,
implemented as Danish Copyright Act section 11c, permits research organisations
with lawful access to reproduce and extract works for scientific text and data
mining. Unlike the general Article 4/section 11b exception, a rights-holder TDM
reservation does not disapply Article 3, and the Danish provision cannot be
overridden by contract. Copies must be secured and retained for scientific
research purposes.

This is not yet a sufficient basis for putting OpenStax into the production
Mimir corpus without institutional legal approval. As of this date, whether
generative-model training is within the TDM exceptions remains unsettled in
Danish/EU law (including pending CJEU case C-250/25). Article 3 expressly covers
reproduction and extraction, but does not itself grant a general right to
publish adapted OpenStax-derived SFT, redistribute source copies, or communicate
protected expression in outputs. The strongest defensible scope would therefore
be an SDU-controlled, non-commercial scientific experiment using lawfully
accessed, securely stored material, with no public release of the derived SFT
and separate review before model-weight or output release. Obtain written
OpenStax permission or an SDU legal determination before activation; keep the
local source quarantined meanwhile.

#### Verified historical CC BY inventory, 2026-08-29

An edition-level audit of OpenStax's official Git repositories, rendered book
state, and fixed PDF artifacts found **107 distinct editions or volumes that
are presently recoverable with CC BY 4.0 evidence**. The machine-readable
inventory is `docs/openstax_cc_by_inventory.csv` and contains one row per
edition with title, slug, language, artifact type, retrieval URL, evidence URL,
and immutable Git or content-version identifier where available.

The 107 rows comprise 91 English, 8 Spanish, and 8 Polish books: 75 are pinned
official Git source snapshots whose collection metadata says CC BY; 23 are
retained, version-identified OpenStax web editions; 7 are fixed official PDFs;
and 2 are additional OpenStax Poland web books. For repositories later changed
to CC BY-NC-SA, the inventory points to the parent commit immediately before
the licence-change commit, not to current `main`. Collection-level metadata is
authoritative over a repository-level licence: this excludes Business Law I
Essentials and Introduction to Business 2e snapshots whose collection files
already said CC BY-NC-SA despite an older root `LICENSE` file saying CC BY.

Five additional 2024 nursing titles have strong evidence of an original CC BY
release but are not in the ready inventory because their stable OpenStax PDF
URLs now return replacement CC BY-NC-SA files: Clinical Nursing Skills,
Fundamentals of Nursing, Maternal-Newborn Nursing, Medical-Surgical Nursing,
and Psychiatric-Mental Health Nursing. Recover an independently archived copy,
verify its embedded licence and edition identifiers, and hash it before moving
any of these into the ready inventory.

The 2019 Business Law I Essentials PDF is similarly excluded: stale OpenStax
search metadata describes a CC BY PDF, but its historical URL no longer returns
that artifact and the official source collection declares CC BY-NC-SA throughout
its available history. Do not infer a usable licence from the repository's old,
conflicting root `LICENSE` file.

The inventory establishes retrievability and licence lineage, not permission to
activate the books in Mimir. Preserve per-section attribution, exclude
separately credited or restricted media, and obtain the institutional legal
determination described above before generation or training.

#### English OpenStax relevance allowlist, 2026-08-29

Of the 91 recoverable English editions, **51 are primary Mimir grounding
sources** and **10 are useful supplemental sources that should be capped for
overlap**. This is a content-relevance decision, not an activation decision:
every title remains subject to the pinned-artifact, attribution, media
filtering, and institutional-review requirements above. Use the exact slug in
`docs/openstax_cc_by_inventory.csv`; do not substitute a current OpenStax
edition with the same or a similar title.

The primary set is:

| Category | Selected English titles and exact inventory slugs |
| --- | --- |
| Mathematics and statistics | *Algebra 1* (`algebra-1`); *Algebra and Trigonometry 2e* (`algebra-and-trigonometry-2e`); *College Algebra 2e* (`college-algebra-2e`); *Contemporary Mathematics* (`contemporary-mathematics`); *Elementary Algebra 2e* (`elementary-algebra-2e`); *Intermediate Algebra 2e* (`intermediate-algebra-2e`); *Introductory Business Statistics 2e* (`introductory-business-statistics-2e`); *Introductory Statistics 2e* (`introductory-statistics-2e`); *Prealgebra 2e* (`prealgebra-2e`); *Precalculus 2e* (`precalculus-2e`) |
| Natural and health sciences | *Anatomy and Physiology 2e* (`anatomy-and-physiology-2e`); *Astronomy 2e* (`astronomy-2e`); *Biology 2e* (`biology-2e`); *Chemistry 2e* (`chemistry-2e`); *College Physics 2e* (`college-physics-2e`); *Microbiology* (`microbiology`); *Nutrition for Nurses* (`nutrition`); *Pharmacology for Nurses* (`pharmacology`); *Physics* (`physics`); *Population Health for Nurses* (`population-health`); *University Physics*, volumes 1--3 (`university-physics-volume-{1,2,3}`) |
| Business, economics, and professional domains | *Business Ethics* (`business-ethics`); *Entrepreneurship* (`entrepreneurship`); *Introduction to Business* (`introduction-business`); *Introduction to Intellectual Property* (`introduction-intellectual-property`); *Organizational Behavior* (`organizational-behavior`); *Principles of Economics 3e* (`principles-economics-3e`); *Principles of Finance* (`principles-finance`); *Principles of Macroeconomics 3e* (`principles-macroeconomics-3e`); *Principles of Management* (`principles-management`); *Principles of Marketing* (`principles-marketing`); *Principles of Microeconomics 3e* (`principles-microeconomics-3e`) |
| Social sciences and humanities | *American Government 4e* (`american-government-4e`); *Introduction to Anthropology* (`introduction-anthropology`); *Introduction to Philosophy* (`introduction-philosophy`); *Introduction to Political Science* (`introduction-political-science`); *Introduction to Sociology 3e* (`introduction-sociology-3e`); *Life, Liberty, and the Pursuit of Happiness* (`life-liberty-and-pursuit-happiness`); *Lifespan Development* (`lifespan-development`); *Psychology 2e* (`psychology-2e`); *U.S. History* (`us-history`); *World History*, volumes 1--2 (`world-history-volume-{1,2}`); *Writing Guide with Handbook* (`writing-guide`) |
| Computing and technical practice | *Additive Manufacturing Essentials* (`additive-manufacturing-essentials`); *Foundations of Information Systems* (`foundations-information-systems`); *Introduction to Python Programming* (`introduction-python-programming`); *Principles of Data Science* (`principles-data-science`); *Workplace Software and Skills* (`workplace-software-skills`) |

The supplemental set is useful but substantially overlaps a primary title or
serves a narrower AP, corequisite, or study-skills audience. Admit it only with
book-aware deduplication and a lower sampling cap: *Biology for AP Courses*
(`biology-ap-courses`); *Chemistry: Atoms First 2e*
(`chemistry-atoms-first-2e`); *College Algebra with Corequisite Support 2e*
(`college-algebra-corequisite-support-2e`); *College Physics for AP Courses 2e*
(`college-physics-ap-courses-2e`); *College Success Concise*
(`college-success-concise`); *Concepts of Biology* (`concepts-biology`);
*Preparing for College Success* (`preparing-for-college-success`); *Principles
of Macroeconomics for AP Courses 2e*
(`principles-macroeconomics-ap-courses-2e`); *Principles of Microeconomics for
AP Courses 2e* (`principles-microeconomics-ap-courses-2e`); and *Statistics*
(`statistics`).

The remaining 30 English inventory rows are not selected: they are older
editions superseded by a selected pinned CC BY edition, or the overlapping full
*College Success* edition. The five overwritten nursing releases and Business
Law I Essentials remain outside the 91-row ready inventory and quarantined.
Do not add current NC-SA-only books such as Calculus, Organic Chemistry,
Accounting, Behavioral Neuroscience, or Introduction to Computer Science under
this allowlist.

#### Current corpus status and downloaded title inventory

**Superseded on 2026-08-29 for the Mimir augmentation corpus:** no OpenStax book
was active in DFM8, DFM9, DFM10, or the Mimir grounding corpus when the local
repack was first inspected. The local `izumi-lab/open-text-books` repack remains
quarantined and contributes zero sampled or generated rows. The replacement
Mimir source pool uses only the allowlisted immutable official artifacts from
`docs/openstax_cc_by_inventory.csv`; this does not retroactively add OpenStax
to DFM8--DFM10.

Inspection identified a contiguous historical-looking block containing 44
OpenStax titles: *Chemistry 2e*; *Biology 2e*; *Anatomy and Physiology 2e*;
*College Success Concise*; *Intermediate Algebra 2e*; *Biology for AP
Courses*; *Elementary Algebra 2e*; *Entrepreneurship*; *Concepts of Biology*;
*College Success*; *Business Ethics*; *Introduction to Anthropology*;
*Microbiology*; *Chemistry: Atoms First 2e*; *College Physics 2e*;
*Introduction to Philosophy*; *Astronomy 2e*; *American Government 3e*;
*College Physics for AP Courses 2e*; *Introduction to Political Science*;
*Introductory Business Statistics*; *Contemporary Mathematics*; *Principles
of Economics 3e*; *Introduction to Business*; *Introduction to Sociology 3e*;
*Introductory Statistics*; *Principles of Macroeconomics 3e*; *Principles of
Microeconomics 3e*; *Organizational Behavior*; *Prealgebra 2e*; *Precalculus
2e*; *Preparing for College Success*; *Principles of Marketing*; *Principles
of Finance*; *Principles of Management*; *University Physics*, volumes 1--3;
*U.S. History*; *World History*, volumes 1--2; *Writing Guide with Handbook*;
*Algebra and Trigonometry 2e*; and *College Algebra 2e*. These are inventory
findings, not an allowlist.

The license lineage is conflicting and therefore unusable without
reconciliation: the Hugging Face wrapper declares `CC BY-SA 4.0`, embedded
historical OpenStax notices commonly declare `CC BY 4.0`, while current
OpenStax licensing guidance uses `CC BY-NC-SA 4.0` and current book pages may
also prohibit LLM ingestion without permission. Exact book, edition, source
artifact, and attribution metadata are absent from the row schema. Treat all
44 titles as quarantined regardless of the permissive notice embedded in some
rows.

#### Immutable-source activation for Mimir augmentation, 2026-08-29

The English relevance allowlist is now materialized independently of the
Hugging Face repack. `scripts/prepare_openstax_cc_by_sources.py` verifies 60
books from pinned official Git snapshots and one versioned official OpenStax web archive,
checks each book-level licence assertion, removes figures and media, retains
module/page provenance and attribution, and exact-deduplicates bundled titles
with primary editions taking precedence. Its verified output is:

```text
data/mimir_grounded_500k/openstax_cc_by/passages.jsonl
data/mimir_grounded_500k/openstax_cc_by/summary.json
```

The pool contains 61 books, 20,047 unique passages, and 95,979,948 passage
characters. Every row records the exact book slug, immutable commit
or content version, module/page, source and evidence URLs, artifact and passage
hashes, `CC-BY-4.0`, and the required OpenStax attribution. This pool is active
only for the Mimir augmentation preparation.

**Superseded for the exact allowlisted derivatives on 2026-08-29:** the project
decision now permits independently audited SFT derived exclusively from these
61 immutable historical CC BY artifacts to enter DFM10 after the production
gate completes. Current OpenStax editions, the quarantined Hugging Face repack,
unverified artifacts, and separately restricted content remain excluded.

The initial *Additive Manufacturing Essentials* pin at
`24bbb8006f63f7f24a5b8f1dc9119ef13b2594b4` is superseded: its collection and
root metadata said CC BY, but its newly added book preface said CC BY-NC-SA.
The verified pool instead uses the earlier commit
`26653ddb1048708bd974e8c11471e426b1ff5520`, where collection metadata, root
licence, and all 41 content modules consistently support CC BY. The extractor
also rejects textual modules containing third-party permission or
all-rights-reserved markers; separately credited figures and media are removed
unconditionally. These second-stage checks account for the corrected totals
above and supersede the earlier 20,074-passage build.

The initial 13,000-request run completed as a pipeline pilot with 10,000
accepted rows. Exact post-build measurement with the DFM8 tokenizer and Gemma
4 template found a median of 158 tokens, a 95th percentile of 290, a maximum
of 782, and zero rows above 4,096 tokens. That completed artifact is preserved
as `data/mimir_openstax_sft/accepted/openstax_mimir_sft_pilot10k.jsonl`.

Because 10,000 rows are too small for 61 books, an expanded run now has 65,000
unique passage/task-family requests across all titles and five task families,
targeting 50,000 accepted English SFT rows after strict generation checks and
an independent full audit. A larger 100,000 accepted target was not used for
this run because 1.3x rejection headroom would exceed the roughly 100,000
unique passage/task-family combinations in the current source pool and force
repeated grounding combinations.

The source passage is present only in the teacher and auditor prompts. Final
learner-facing rows contain a user instruction and assistant response rendered
with the DFM8 Gemma 4 tokenizer and native chat template. Generation is capped
at 2,048 output tokens, and both generation acceptance and final building
reject any rendered training row above 4,096 tokens. The teacher-side vLLM
context remains 8,192 tokens; an exact check of the 2,000 candidates with the
largest source passages found a maximum 3,543-token teacher prompt, or 5,591
tokens including the full output allowance.

Requests are under
`data/mimir_openstax_sft/requests`; the queued launcher is
`scripts/run_openstax_mimir_sft_after_current_work.sh`. It waits for the active
WikiCat recovery workload instead of competing for GPUs. GPU work is ordered as
WikiCat recovery, OpenStax pilot, then the corrected MMLU ontology retry; the
ontology launcher explicitly waits for the OpenStax pilot so the two queued
launchers cannot deadlock or compete for the same eight GPUs.

### Cost envelope

For the proposed 1.0--1.5 million accepted rows, budget approximately
`600--1,100` B200 GPU-hours end to end when using Gemma 4 31B for both
generation and judgment. This assumes explanatory or worked targets averaging
roughly 300--500 generated tokens, eight independent vLLM servers, source
passages prepared offline, one full audit, and selective repair/re-audit rather
than regenerating every row. On eight dedicated B200s this is roughly 3--6
days wall time after startup and tail effects. A useful planning split is:

| Phase | B200 GPU-hours | Notes |
| --- | ---: | --- |
| Grounded generation | 450--800 | Dominated by target length; quantitative derivations and case rationales are slower than direct QA. |
| Full quality/factual audit | 40--150 | Consistent with the locally measured 10k--40k A4B audit decisions per GPU-hour, with longer passages near the slow end. |
| Selective repair and re-audit | 80--150 | Assumes approximately 10--20% of rows need model-based repair; deterministic rejects should not consume generation. |
| Total | 600--1,100 | Excludes engineering time, downloads, CPU extraction, deduplication, and tokenization. |

Before committing the full budget, run a 50k--100k accepted-row pilot spanning
all slices. Expect approximately 25--70 B200 GPU-hours for generation, audit,
and one repair pass. Measure accepted tokens and throughput by slice, because
row counts hide large differences between direct QA and worked solutions.

## Evaluation-informed generation firewall

Reviewing individual failures is useful for diagnosis, but generating a lesson
for the exact topic of every held-out test question is test-set-informed
training. Removing the original wording or grounding the lesson in an
independent textbook does not remove that adaptive signal. Such training would
probably improve answer rates, but the resulting MMLU score could no longer be
presented as a clean held-out measurement.

Use the following separation:

1. Retain question-level generations from the corrected evaluation and classify
   failures as invalid-format, knowledge, reasoning, calculation, ambiguity, or
   likely label/problem defect.
2. Aggregate knowledge/reasoning failures into a fixed coarse ontology such as
   mechanics, electromagnetism, stoichiometry, probability, regression,
   propositional logic, anatomy, and contract law. Do not pass question text,
   choices, gold labels, named entities, distinctive numbers, or a one-to-one
   topic list into generation.
3. Sample source passages independently within those broad ontology cells and
   generate varied explanations, applications, counterexamples, and problems.
   A source passage should yield multiple task families, while no generated row
   should be traceable to one held-out item.
4. Deduplicate source passages and generated rows lexically and semantically
   against all evaluation questions and choices. Quarantine close matches.
5. Freeze a new shadow evaluation before generation. Continue reporting the old
   MMLU result with an explicit `evaluation-informed curriculum` qualification,
   and use the untouched shadow set to measure generalization.

The strictest alternative is to use only MMLU development examples for
curriculum design and inspect test failures only after the data recipe is
frozen. If exact failed-test-item targeting is intentionally used, designate
MMLU as a development benchmark from that point onward.

Concept-focused explanatory data can help future Mimir checkpoints: it provides
more transferable supervision than memorizing an option letter, especially
when each concept is taught through definitions, derivations, misconceptions,
worked applications, and novel transfer problems. Its value should be measured
on untouched questions from the same capability family rather than only on the
items that motivated generation.

### Detailed Inspect artifact and 500k pilot decision

The sibling checkout `../HRM-test-additional` contains a complete Inspect log
for `HRM-Mimir-v1`:

```text
logs_original/HRM-Mimir-v1/
2026-08-22T08-39-08-00-00_mmlu-5shot_Wxtt3J8acBC4wX4GU2Dxg9.eval
```

It contains all 14,042 sample records: five-shot prompt, terminal question and
options, gold label, generated completion, subject, token usage, and score. The
run produced only one output token, so it supports fine-grained question-topic,
knowledge-form, and cognitive-operation labeling but does not reveal the
model's reasoning process. Extraction on 2026-08-29 found 8,124 correct,
5,630 valid-letter wrong, and 288 invalid samples. Of the invalids, 266 are in
high-school mathematics; those rows inform format calibration and are excluded
from the knowledge ontology by default.

Question-level diagnostics are quarantined under
`logs/analysis/mimir_v1_mmlu_failure_ontology/`. The generation pipeline may
consume only `ontology_aggregate_k10.json`, which removes questions, choices,
answers, sample IDs, and cells supported by fewer than ten failures. Extraction
and classification are implemented by:

```text
scripts/extract_mimir_mmlu_failure_inventory.py
scripts/classify_mimir_mmlu_failure_ontology.py
scripts/run_mimir_mmlu_ontology_when_free.sh
```

**Invalidated on 2026-08-29:** the first classifier run produced only 734
valid labels and 4,896 malformed constrained-JSON responses. Its biased
aggregate was moved to
`ontology_aggregate_k10.invalid_20260829.json` and must not be consumed. The
classifier now preserves malformed responses, recovers complete schema fields
from constrained-JSON stalls, maps unrecoverable rows to the shared retry key,
and migrates the first run's errors so `--resume` retries rather than silently
skips them. A new `ontology_aggregate_k10.json` is valid only after all 5,630
requests classify successfully and aggregation is rerun.

The accepted-row pilot target is now 500,000 rows: exactly 100,000 each for
technical STEM, professional domains, compositional/constraint reasoning,
grounded factual QA, and MCQ answer-contract calibration. Initial generation
should overproduce approximately 20--30% per slice, audit strictly, and top up
short slices rather than weakening acceptance. The source-passage preparation
script is `scripts/prepare_mimir_grounding_passages.py`; its outputs live under
`data/mimir_grounded_500k/source_passages`. **Superseded on 2026-08-29:** the
provisional OpenStax repack was not admitted; the replacement official,
immutable, provenance-preserving pool described above is now used instead. The
official Open Logic checkout is pinned locally at commit
`1e960beff9ed7835bf3e3f1335e21af3439cd107`.

### Five-by-100k production campaign, 2026-08-29

The full campaign is implemented separately from the 50k OpenStax expansion
under `data/mimir_grounded_500k_sft`. Its fixed policy is
`config/mimir_grounded_500k_sft.json`: 130,000 generated candidates for each
of the five categories, 650,000 candidates total, and exactly 100,000 accepted
rows per category after deterministic checks and independent judgment. The
640-shard layout keeps work restartable and lets each of eight GPU workers
claim new shards atomically as it becomes free.

```text
scripts/prepare_mimir_grounded_500k_requests.py
scripts/mimir_grounded_500k_model.py
scripts/run_mimir_grounded_500k_8gpu.sh
scripts/queue_mimir_grounded_500k.sh
```

Request preparation runs independently on CPU. The detached GPU runner holds
`data/mimir_grounded_500k_sft/campaign.lock`, waits for a complete 650,000-row
manifest and for all eight GPUs to fall below the configured memory threshold,
and does not terminate or reuse servers from the separate OpenStax workload.
Generation and audit outputs are category-labelled, provenance-preserving, and
resume-safe. MCQ candidates require four unique options, a requested balanced
answer position, a separately retained rationale, and a direct one-letter
assistant target.

The production request manifest completed on 2026-08-29: 650,000 rows in 640
shards (approximately 3.5 GB), with exactly 130,000 candidates in each category.
The MCQ requested positions contain exactly 32,500 examples for each of A, B,
C, and D. Grounding passages have median 5,135 characters, p95/p99 6,000, and
maximum 6,040, leaving generation headroom within the 8,192-token serving
limit. The detached runner is queued and waiting for the active 50k OpenStax
workload to release all GPUs naturally.

An initial 40-shard production sample exposed a deterministic-contract defect:
Gemma returned substantive verification strings for technical, professional,
factual, and MCQ rows, while the checker admitted only object/list
verifications. This incorrectly reduced pre-audit acceptance to 15.5% even
though the independent audit accepted 99.4% of structurally admitted rows. The
checker now accepts dictionaries, lists, or substantive strings of at least 20
characters. All 40 affected shards were atomically requeued, their old done
markers were retained under
`state/superseded_20260829_verification_contract`, and active workers were not
interrupted. Boolean or empty verification remains rejected.

Finalization is fail-closed: all 640 request, generation, and audit shards must
exist; every accepted row must fit the 4,096-token Gemma template; each category
must have at least 100,000 accepted unique prompts; and a separate held-out
benchmark decontamination report must have status `passed`. Short categories
must be topped up with additional candidates rather than lowering the audit
threshold. The queued runner log is selected through
`data/mimir_grounded_500k_sft/current_run_log_root.txt`.

**Campaign-specific decision, 2026-08-29:** decontamination for this 500k build
is normalized exact matching only. `scripts/decontaminate_mimir_grounded_500k_exact.py`
uses NFKC normalization, case folding, punctuation/symbol/separator replacement,
and whitespace collapse on generated instructions/MCQ stems and canonical
held-out question stems. Exact matches enter `denied_request_ids`; n-gram,
MinHash, embedding, semantic, and judge-based similarity checks are explicitly
not performed. The builder verifies both `status: passed` and
`mode: normalized_exact_only`; this narrower decision supersedes semantic
near-duplicate filtering for this campaign, but not the broader evaluation
firewall guidance for future data programs.

`scripts/finalize_mimir_grounded_500k_when_ready.sh` is queued as a detached,
CPU-only finalizer. It waits for all 640 durable done markers, runs the
normalized-exact checker, then invokes the mode-locked builder. It never starts
or stops GPU servers.

**Expanded on 2026-08-29:** the exact 100,000-per-category output cap is
superseded. All independently audited, length-valid, normalized-exact-clean,
globally prompt-unique rows are retained. A separate Technical/STEM top-up under
`data/mimir_grounded_500k_sft/technical_topup_100k` contains 130,000 candidates
in 128 shards and must contribute at least 100,000 additional accepted unique
rows. Its campaign version and request IDs are distinct from the base campaign.
The top-up uses the same source proportions, generation checks, independent
audit, Gemma template, and exact-only decontamination policy. The finalizer now
waits for both 640 base and 128 top-up done markers, checks both roots in one
decontamination report, and writes
`accepted/mimir_grounded_expanded_sft.jsonl`. It fails rather than capping rows
or accepting fewer than 100,000 incremental Technical/STEM examples.

**Completed on 2026-08-30:** all 640 base shards and all 128 Technical/STEM
top-up shards finished generation and independent audit with no failed shards.
The final globally prompt-deduplicated build contains 732,763 rows and an
estimated 164,687,503 Gemma-template training tokens:

| Category | Rows | Training tokens |
|---|---:|---:|
| Technical/STEM | 223,728 | 76,589,776 |
| Professional domains | 127,944 | 30,519,994 |
| Compositional reasoning | 125,036 | 28,399,865 |
| Grounded factual QA | 128,687 | 11,587,862 |
| MCQ answer contract | 127,368 | 17,590,006 |

The Technical/STEM top-up contributed 110,978 accepted unique rows. Exact
decontamination checked 736,127 independently accepted candidates against
44,982 normalized units from the benchmark manifest and found zero exact
matches. Because current `datasets` releases reject PIQA's legacy loading
script, PIQA validation questions are read directly from the canonical AI2
`physicaliqa-train-dev.zip` static artifact; the report records its member path
and SHA-256 (`54d32a04f59a7e354396f321723c8d7ec35cc6b08506563d8d1ffcc15ce98ddd`).
The final JSONL is
`data/mimir_grounded_500k_sft/accepted/mimir_grounded_expanded_sft.jsonl` and
its machine-readable counts are in the adjacent `summary.json`.

The same rows are packaged for local Hugging Face export as
`exports_dfm10/dfm10-mimir-grounded-expanded-sft`. The upload-ready package has
three deterministic gzip JSONL shards, a dataset card, mixed-source license
notice, checksummed manifest, standalone validator, and a successful complete
validation receipt. No upload was performed as part of staging.

**DFM10 integration, 2026-08-30:** the package is exposed through uniquely
named source-shard links under `data/dfm10_mimir_grounded_expanded_sources` and
tokenized with the Gemma 4 native chat template under
`data/tokenized_dfm10_mimir_grounded_expanded_sft`. All 732,763 rows tokenized
with zero skips into three tasks and 138,161,296 exact training tokens
(47,640,298 prompt and 90,520,998 assistant-target tokens). The rendered
maximum is 1,931 tokens and no row exceeds the 4,097-token training limit. The
canonical
`data/tokenized_dfm10` union contains all three tasks, and
`data_io/prefix_config_dfm10.yaml` selects them at repeat one. The integration
is reproducible through `scripts/integrate_mimir_grounded_expanded_sft.sh` and
the normal `scripts/prepare_dfm10_data.sh` path. Existing
`data/sampled_dfm10` epochs predate this addition and must be rebuilt during
the next final DFM10 sampling pass; export staging and tokenized-union
integration do not retroactively modify old epoch indices.

The Common Pile repositories are grounding inputs, not directly tokenized
training sources. Deterministically sampled passage windows are shown to the
31B teacher during generation and to the independent judge during audit. The
accepted training row contains only the resulting standalone user/assistant
messages; the evidence hash and provenance stay in metadata, which the
tokenizer does not train on. Deterministic checks reject long source copying,
passage-dependent wording, missing verification, and rows beyond the context
contract. Of the 732,763 accepted rows, 613,001 (83.66%) are grounded in Common
Pile: Wikimedia 193,008; arXiv 161,683; PubMed 82,866; StackExchange 61,619;
USGPO 60,202; and Regulations 53,623. OpenStax and OpenLogic ground the
remaining 119,762 rows. One passage may support multiple independently
generated task forms, but exact prompt duplication is forbidden.

## Relationship to DFM10

The post-integration marginal program for MMLU, ARC-C, WinoGrande, HellaSwag,
IFEval, BoolQ, and DROP is maintained separately in
[Mimir Benchmark Data Priorities](/pages/mimir-benchmark-data-priorities.md).

DFM10 already adds or repairs substantial generic math, code, reasoning, and
tool-use material, especially repaired OpenMathInstruct-2, NuminaMath,
verifiable reasoning, code-meta reasoning, Nemotron SWE, and DOLCI tool use.
Therefore:

1. Do not respond to Mimir v1 by merely adding more generic math or code rows.
2. Prioritize the underrepresented technical-science and professional-domain
   slices above.
3. Re-evaluate an early DFM10 checkpoint before committing to another large
   reasoning/tool corpus.
4. Add stored-generation diagnostics for MCQ math so capability and answer
   formatting cannot be conflated again.

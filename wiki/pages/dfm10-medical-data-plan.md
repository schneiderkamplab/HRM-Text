---
type: Plan
title: DFM10 Medical Data Plan
description: License-gated Danish and English medical data candidates for improving Mimir without admitting protected clinical or handbook content.
tags: [dfm10, medical, danish, english, hugging-face, licensing, privacy]
status: draft
last_updated: 2026-08-30
confidence: medium
sources:
  - id: patienthaandbogen-terms
    resource: https://www.sundhed.dk/borger/patienthaandbogen/om-patienthaandbogen/brugervilkaar-og-jura/
    title: Brugervilkaar og jura - Patienthaandbogen
    author: org:sundhed.dk
  - id: dynaword-health-hovedstaden
    resource: https://huggingface.co/datasets/danish-foundation-models/danish-dynaword/tree/main/data/health_hovedstaden
    title: Health Hovedstaden dataset card
    author: org:danish-foundation-models
  - id: elrc-medical-v2
    resource: https://huggingface.co/datasets/qanastek/ELRC-Medical-V2
    title: ELRC-Medical-V2
    author: org:ELRC
  - id: ema-legal-notice
    resource: https://www.ema.europa.eu/en/about-us/about-website/legal-notice
    title: European Medicines Agency legal notice
    author: org:EMA
  - id: pmc-open-access
    resource: https://pmc.ncbi.nlm.nih.gov/tools/openftlist/
    title: PMC Open Access Subset
    author: org:NLM
  - id: openmedtext
    resource: https://huggingface.co/datasets/ywchoi/OpenMedText
    title: OpenMedText
    author: person:Younwoo-Choi
  - id: medquad
    resource: https://huggingface.co/datasets/bowang0911/MedQuAD
    title: MedQuAD
    author: org:NIH
  - id: nhs-synthetic-notes
    resource: https://huggingface.co/datasets/NHSEDataScience/synthetic_clinical_notes
    title: Synthetic Clinical Notes
    author: org:NHSEDataScience
  - id: mimic-guidance
    resource: https://www.physionet.org/content/mimiciv/2.0/
    title: MIMIC-IV access and derived-resource guidance
    author: org:PhysioNet
---
# DFM10 Medical Data Plan

## Objective

Improve Danish and English medical terminology, grounded explanation,
translation, summarization, and cautious clinical reasoning without treating
free web access as permission, laundering source rights through a Hugging Face
repack, or admitting identifiable patient data.

This remains a candidate plan for the larger medical corpus. The first narrow
tranche described below was staged for the next DFM10 union rebuild on
2026-08-30 after revision pinning, deterministic conversion, real-row
inspection, and local tokenization. Every
other source still requires row inspection, exact revision pinning, benchmark
decontamination, and source-level license/provenance review before activation.

## Staged First Tranche

| Source | Revision | Conversion | Accepted rows | Gemma-native tokens | Per-epoch weight |
| --- | --- | --- | ---: | ---: | ---: |
| `qanastek/ELRC-Medical-V2`, `csv/en-da.csv` | `7f5633e7f9903947a9e51ab0e12ff483574aeebf` | Both translation directions; duplicate, short, TOC, and formatting-artifact filtering | 13,203 pairs / 26,406 rows | 2,714,245 | repeat 2 |
| `NHSEDataScience/synthetic_clinical_notes` | `368a5bd2a55090a0bae3436f2823d606c5077158` | Grounded note-type, note-title, and exact span restoration; synthetic identifiers redacted and mojibake repaired | 4,756 rows from 1,602 notes | 1,252,716 | repeat 1 |

The tranche will contribute approximately 6,681,206 sampled tokens per DFM10
epoch after the next union rebuild and resampling. It is implemented by
`scripts/prepare_dfm10_medical.py`, tokenized under
`data/tokenized_dfm10_medical`, registered in
`scripts/build_tokenized_dfm10_tree.py`, and weighted in
`data_io/prefix_config_dfm10.yaml`.

Real-row inspection found that ELRC's medical-domain label is broader than its
contents: many rows are generic EU policy or public-sector prose. The converter
therefore uses honest generic translation prompts rather than claiming each
row is medical, and the source remains conservatively weighted. This tranche
adds useful bilingual terminology but is not a substitute for a genuinely
clinical Danish corpus.

## Hard Exclusions

### Laegehaandbogen and Patienthaandbogen

Do not scrape, train on, summarize into a derivative training corpus, or use as
synthetic-generation grounding without written permission. The official terms
state that reproduction is generally prohibited and explicitly reserve text
and data-mining rights for both works under Danish Copyright Act section 11b
and DSM Directive Article 4.[^patienthaandbogen-terms]

### MIMIC and other credentialed clinical records

Do not place MIMIC or MIMIC-derived records in an openly redistributable Mimir
training pipeline. PhysioNet requires credentialing and a data-use agreement,
and says derived datasets or models must be treated as sensitive and shared
under the same agreement.[^mimic-guidance] Prefer genuinely synthetic clinical
records that did not use real patient records as generation seeds.

### Unfiltered medical web and guideline collections

Do not admit a corpus merely because its Hub card assigns one repository-wide
license. In particular, web-scraped guideline aggregates can contain documents
that expressly prohibit reproduction. `epfl-llm/guidelines` visibly contains
such documents and is excluded unless rebuilt from a positive allowlist of
individually reusable sources.

## Danish Candidates

| Priority | Dataset | Scale | Rights/provenance | Proposed use |
| --- | --- | ---: | --- | --- |
| A | `danish-foundation-models/danish-dynaword`, config `health_hovedstaden` | 23,996 documents; 27.07M Llama-3 tokens; 79.88M characters | Source card says CC0 and prepared for language-technology development | Keep the already downloaded/tokenized corpus; measure its current DFM10 exposure, then derive audited professional-guideline QA, summarization, terminology, and audience-rewriting tasks instead of duplicating raw text. |
| A, staged | `qanastek/ELRC-Medical-V2`, config `en-da` | 13,242 aligned pairs; 13,203 retained | CC BY 4.0; EU Publications Office medical-domain parallel corpus, with substantial generic policy content | Bidirectional English-Danish translation is staged at repeat 2 with provenance retained and generic prompts that do not overstate the medical domain. |
| B | `qanastek/EMEA-V3`, pair `da-en` | approximately 360,186 aligned segments | EMA/OPUS-derived; Hub card lacks a license. EMA allows reuse of EMA-owned public material with attribution but excludes third-party content.[^ema-legal-notice] | Admit only after provenance reconstruction, third-party filtering, deduplication against ELRC, and alignment audit. This may be the largest useful Danish medical terminology source. |
| C | `birgermoell/icd10-clinical-notes` | 1,802 rows total; only 53 Danish rows | CC BY 4.0; synthetic notes, but Danish rows have Danish diagnosis names and mostly English notes | Optional terminology/coding micro-slice or held-out diagnostic-format test. It is too small and not Danish enough to be a primary training source. |
| Eval | `FreedomIntelligence/ApolloMoEBench`, Danish clinical-knowledge subset | 264 Danish multiple-choice rows | MIT wrapper; translated MMLU clinical-knowledge provenance | Consider as evaluation-only after exact overlap checks against existing MMLU/EuroEval assets. Do not train on it. |

The `health_hovedstaden` files already exist locally under
`data/downloads/datasets/danish_dynaword/data/health_hovedstaden` and have
multiple DynaWord-derived tokenized task variants. Integration work should
therefore begin with exposure accounting and task quality, not another
download.

## English Candidates

| Priority | Dataset | Scale | Rights/provenance | Proposed use |
| --- | --- | ---: | --- | --- |
| A, local and verified | OpenStax CC BY health books in `data/mimir_grounded_500k/openstax_cc_by/passages.jsonl` | 3,168 passages / 16.01M source characters across anatomy and physiology, lifespan development, microbiology, nutrition, pharmacology, and population health | Locally verified immutable OpenStax artifacts with per-row CC BY attribution and provenance | Immediate English grounding supplement for EMEA-derived chats. Use explanatory, patient-friendly rewriting, terminology, summarization, and evidence-bounded QA tasks; retain book and passage attribution. |
| A/B | `ywchoi/OpenMedText` | 121,489 MDPI biomedical articles plus 29 open medical textbooks | Dataset card says MDPI articles are CC BY 4.0; textbooks are separated into CC BY, CC BY-SA, CC BY-NC, and CC BY-NC-SA components | Best larger near-term supplement. Build a manifest-pinned subset that retains component-level license and attribution; start with CC BY/CC BY-SA and admit NC components only under the project's non-commercial policy. Audit extraction quality and deduplicate against local OpenStax and PMC. |
| A | PMC Open Access Subset, retrieved through official NLM bulk services | Millions of articles; select by explicit article license | NLM warns that not all PMC content is reusable and that licenses vary by article.[^pmc-open-access] | Build a manifest-pinned CC0/CC BY/CC BY-SA, text-only medical subset. Preserve article IDs, license, attribution, and retraction/removal status. Prefer this over generic PubMed or PMC repacks. |
| A, staged | `NHSEDataScience/synthetic_clinical_notes` | 1,602 notes for 69 synthetic patients | MIT; card states no real data was used and describes clinician involvement | Staged at repeat 1 as grounded classification and span restoration. Synthetic identifiers are redacted and common encoding defects repaired; no ungrounded summaries or clinical advice are generated. |
| A/B | `starmpcc/Asclepius-Synthetic-Clinical-Notes` | 158,114 instruction rows | CC BY-NC-SA 4.0; synthetic notes generated from PMC-Patients case reports | Suitable for academic non-commercial use only after checking PMC-Patients lineage, deduplicating source cases, and auditing medical correctness and GPT-3.5 style. |
| B | `FreedomIntelligence/medical-o1-reasoning-SFT`, English config | 19,700 rows | Apache 2.0 wrapper; GPT-4o reasoning over 40,644 exam-derived verifiable problems | Potential reasoning SFT, but the underlying problems derive from medical exams. Admit only train splits after provenance, answer-quality, and benchmark contamination review; keep all matching eval material out. |
| B | `meditron-fo-anon/fully-open-meditron`, synthetic configs only | 214,654 synthetic QA; 145,681 guideline QA; 24,465 open-ended vignettes | Synthetic components marked CC BY-NC 4.0; current card is an anonymous 2026 submission | Promising but provisional. Review source prompts/guidelines and use only source components that pass rights, correctness, and decontamination gates. Do not ingest the aggregated `curated_qa` component wholesale. |
| B | `R2MED/PMC-Clinical` | 60,406 corpus passages plus 114 retrieval queries | Card says CC BY 4.0; synthetic retrieval benchmark built around PMC clinical material | Prefer evaluation/retrieval experiments. For training, verify every PMCID against the current PMC OA license list rather than trusting the aggregate card alone. |
| B | `findzebra/case-reports` | 3,344 rare-disease case reports | Card says CC BY 4.0; fetched through PubMed API | Useful rare-disease extraction/grounded QA seed if PMCID-level source licenses confirm reuse. Do not infer article rights from the repository label alone. |
| B, audited English and Danish adaptation | Original `abachaa/MedQuAD`, with `bowang0911/MedQuAD` used only as a convenient MTEB cross-check | 47,441 nominal QA entries; 16,407 have both question and answer in the original XML; the MTEB derivative has 14,977 linked QA rows | Original dataset is CC BY 4.0 and retains source site, URL, question type, focus, and UMLS metadata. Answers in three MedlinePlus subsets were deliberately removed for copyright compliance and must remain excluded. | Audit the non-empty original rows, retain accepted English QA, and produce an attributed Danish translation/adaptation. Use modestly for consumer-health question/style diversity; do not use it as the principal factual grounding corpus. |

### English grounding supplement decision (2026-08-30)

For the planned EMEA-grounded medical-chat campaign, supplement rather than
replace EMEA English with the six locally verified OpenStax health books. A
reasonable first English allocation is 50% EMEA evidence, 25% OpenStax health
evidence, and 25% a manifest-pinned OpenMedText pilot. Until the OpenMedText
pilot passes attribution, extraction, quality, and deduplication checks, assign
that final quarter back to EMEA and OpenStax rather than using unverified web
medical text. PMC OA is the later scale-up path, not the fastest first build.

### Danish MedQuAD adaptation decision (2026-08-30)

Create a Danish MedQuAD adaptation from the original XML rather than translating
the metadata-poor MTEB derivative. Preserve the English question and answer,
source site, source URL, question type, focus, UMLS identifiers, original IDs,
upstream revision, CC BY attribution, and an explicit indication that the
Danish fields are machine-translated adaptations. Never crawl or reconstruct
the deliberately removed A.D.A.M., MedlinePlus Drugs, or MedlinePlus Herbs and
Supplements answers.

Use Gemma 4 31B for faithful translation, not medical rewriting or content
expansion. Normalize mechanical question defects such as duplicated terminal
question marks before translation. Audit every Danish pair independently for:

1. preservation of diagnoses, symptoms, negation, uncertainty, numerical
   values, doses, units, and named treatments;
2. natural Danish medical terminology and question formulation;
3. question-answer coherence and completeness relative to the English source;
4. absence of newly introduced diagnosis, advice, dosage, or prognosis claims;
5. source and benchmark duplication, obsolete time-sensitive advice, and
   malformed boilerplate.

Keep only accepted rows and package English and Danish as separately selectable
subsets with stable cross-language pair IDs. Use repeat 1 for each initially;
the two language versions encode the same facts and should not be multiplied
aggressively. A reasonable expectation is approximately 12,000--15,000 accepted
pairs after quality and freshness filtering, but the actual count must be
reported from the complete audit.

#### Implementation state

Implemented and queued on 2026-08-30:

- `scripts/prepare_dfm10_medquad_da.py` pins the official repository at commit
  `577bd37b96c02d1833b2c9eed2de9f96964e96cb`, extracts source metadata,
  deterministically shards translation requests, resumes generation/audit by
  stable ID, and atomically builds separate English and Danish datasets.
- The prepared campaign contains 16,296 candidate pairs. It excluded 31,029
  deliberately withheld answers, 64 answers above the safe 8K translation
  round-trip budget, 47 exact duplicate pairs, and five other empty rows.
- Deterministic translation checks preserve numeric values; a separate Gemma 4
  31B audit gates source quality, medical coherence, translation fidelity,
  natural Danish, training value, and major freshness risk.
- `scripts/run_dfm10_medquad_da_8gpu.sh` waits without disturbing active GPU
  work, starts one 31B vLLM server per free GPU, translates and audits at
  concurrency 64, tears down only its own server process groups, tokenizes with
  16 workers, and rebuilds the DFM10 union under its union lock.
- The queued detached runner is recorded in
  `data/dfm10_medquad_da_work/queued_runner.pid`; operational output is in
  `logs/dfm10_medquad_da_runner.log`.
- Both accepted subsets use repeat 1 via `medquad_english__` and
  `medquad_danish__`.

**Superseded, 2026-08-31:** the first production builder required successful
translation and audit coverage for every candidate, causing 16,027 fully
validated pairs to be rejected as a corpus when 269 of 16,296 candidates
remained incomplete after four recovery passes. Candidate coverage is now an
informational quota: only the intersection with structurally successful
translation and audit records is eligible, while every row-level validation
and audit acceptance gate remains fail-closed. The manifest records complete,
missing-translation, and missing-audit counts explicitly.

**Production result, 2026-08-31:** 12,472 accepted bilingual pairs were
materialized as separate English and Danish sources (24,944 training rows in
total), tokenized with the Gemma 4 native template without skipped rows, and
linked into `data/tokenized_dfm10` at repeat 1 under `medquad_english__` and
`medquad_danish__`. The current `data/sampled_dfm10` was built on 2026-08-30
and therefore does not yet contain these additions; the next DFM10 resampling
must consume the updated tokenized union. The final sources were packaged and
published separately as `schneiderkamplab/dfm10-medquad-english-sft` (revision
`96a12f8cebeb954abcadfe0c6c574aba1e029309`) and
`schneiderkamplab/dfm10-medquad-danish-sft` (revision
`8f044a6d7c7f05ed26f2cafc115d9ad37d1a75d8`). Both remote repositories passed
complete expected-file verification and contain 12,472 rows with zero package
conversion skips.

## Evaluation-Only or Seed-Only Sources

- Keep MedQA, MedMCQA, PubMedQA, medical MMLU, and their translations out of
  training when they are used for evaluation. A repository license does not
  automatically settle the copyright of underlying exam questions or article
  abstracts.
- `ApolloMoEDataset` is not ready for admission: it is a 13.5 GB aggregate
  covering many languages, while the card does not enumerate the training
  components or their retained licenses sufficiently for source-level policy.
- Medical Meadows, ChatDoctor/HealthCareMagic, and similar scraped patient-QA
  repacks remain excluded pending source-by-source rights and privacy review.
- `WMT-16-PubMed` is not a Danish candidate in practice: its current Hub files
  expose only three language-pair configurations despite broader language tags,
  and its card does not provide a usable license.

## Recommended Build Order

1. Measure the current DFM10 token and per-epoch exposure of
   `health_hovedstaden`, including all DynaWord-derived task variants.
2. **Completed 2026-08-30:** downloaded the pinned
   `ELRC-Medical-V2/en-da` snapshot, filtered obvious artefacts and duplicates,
   and produced bidirectional Gemma-4-native translation rows.
3. Build a held-out Danish medical evaluation suite before generating training
   data. Start with the 264-row Apollo Danish clinical subset only if overlap
   checks permit it, and add newly authored/translated tests under compatible
   licenses.
4. Pilot 10,000-50,000 grounded Danish instruction rows from
   `health_hovedstaden`, covering professional explanation, patient-friendly
   rewriting, terminology, summarization, information extraction, and
   uncertainty/safety behavior. Audit with a strong medical-capable judge and
   manually review a stratified sample.
5. Add a modest English synthetic-medical slice from the A-tier candidates;
   preserve source and synthetic provenance per row.
6. Only then consider a larger article-level PMC OA corpus or EMEA-V3. Both
   require explicit manifests and deduplication, not broad Hub ingestion.

## Safety and Quality Gates

- Separate factual medical knowledge from clinical advice behavior. Training
  answers must state uncertainty, seek missing context, and direct emergencies
  or patient-specific treatment decisions to qualified care.
- Do not fabricate citations, drug doses, contraindications, or evidence
  grades during synthetic generation. Ground outputs in an admitted source and
  retain source identifiers.
- Reject direct identifiers and plausible real-patient narratives unless the
  source is demonstrably synthetic or properly de-identified and legally
  admissible.
- Pin revisions and retain licenses at row/document level. Recheck living
  sources and removal/retraction lists before each rebuild.
- Deduplicate against existing OpenStax nursing material, DynaWord, medical
  benchmark test sets, and all synthetic seeds.

[^patienthaandbogen-terms]: The terms were updated 2024-12-12 and apply the TDM reservation to both Laegehaandbogen and Patienthaandbogen.
[^mimic-guidance]: PhysioNet's MIMIC-IV page includes explicit guidance for derived datasets and models.
[^ema-legal-notice]: EMA-owned public material may be reproduced with source acknowledgement; third-party material is excluded from that permission.
[^pmc-open-access]: NLM requires use of its official bulk services and compliance with each article's license.

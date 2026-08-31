---
type: Plan
title: DFM10 Danish Hub Gap Integration
description: Concrete admission, conversion, audit, sampling, and preference-data plan for newly identified Danish-researcher datasets.
tags: [dfm10, data, danish, preference, alignment, huggingface]
status: draft
last_updated: 2026-08-30
confidence: high
---
# DFM10 Danish Hub Gap Integration

## Objectives

1. Remove accidental duplicate exposure inherited through
   `dfm-dyna-instruct`.
2. Add all model-charter alignment data without mixing rejected responses into
   ordinary SFT. The nominal test splits are training data by project decision,
   not held out.
3. Determine whether the second Croco-Munin 50K preference repository contains
   genuinely new supervision.
4. Use Danish personas only as generation seeds.
5. Keep Danish legal text behind explicit privacy, provenance, and grounding
   gates.

## Admission table

| Priority | Source | Ordinary DFM10 SFT | Preference data | Gate |
| ---: | --- | --- | --- | --- |
| 0 | Four duplicated Synquid constituents | Keep direct routes only | No | Disable matching `dfm-dyna-instruct` constituent paths. |
| 1 | `danish-foundation-models/synthetic-values-model-charter` | Add all 1,360 SFT rows at repeat 10 | Add all 1,360 DPO pairs once | Pin Hub revision and charter commit; keep rejected responses out of SFT. |
| 2 | `danish-foundation-models/croco-munin-apertus-8b-da-50k` | Do not add | Do not add | Audit found only 7 candidate-only prompts and no meaningful task-coverage delta. |
| 3 | `oliverkinch/danish-personas` | Add only generated and audited chats, initially repeat 2 | No | Generate 20,000 diverse multi-turn chats from 5,000 personas. |
| 4 | `alexandrainst/domsdatabasen` | Add generated grounded chats at repeat 1 | No | Nonempty pseudonymized text only; generation plus privacy and grounding audits. |

## Phase 1: normalize inherited duplication

Add source-specific `max_per_file: 0` rules for these four composite paths,
while retaining their direct prefixes and current direct repeats:

| Composite constituent disabled | Direct prefix retained | Repeat retained | Tokens removed per epoch |
| --- | --- | ---: | ---: |
| `dfm_dyna_instruct__data__wiki-instruct-da__` | `synquid_wiki_instruct_da__` | 6 | 164,686,585 |
| `dfm_dyna_instruct__data__danish-verifiable-reasoning__` | `synquid_danish_verifiable_reasoning__` | 2 | 9,064,406 |
| `dfm_dyna_instruct__data__ifbench-train__` | `synquid_ifbench_train__` | 10 | 1,262,590 |
| `dfm_dyna_instruct__data__translation-100k__` | `synquid_translation_100k__` | 1 | 98,008,752 |

Expected reduction: 273,022,333 tokens per epoch. Verify each task's sampled
count becomes zero through the composite prefix and remains nonzero through the
direct prefix.

## Phase 2: model-charter alignment data

**Superseded (2026-08-30):** the initial plan reserved the nominal 272-row SFT
and DPO test files. The project decision is to admit them because this corpus is
training/alignment data and no internal holdout is required.

Pin dataset revision `5c14264c4bd5901fe93c0c8bbf9d296cde658fcc` and
model-charter source commit `e60e41aad338c6261cc21f926847b3ab77ff4226`.
Convert all 1,360 rows from `sft_train.jsonl` and `sft_test.jsonl` into
Gemma-native user/assistant messages. Preserve
`id`, `scenario_id`, and `value_unit_id` as metadata. Reject empty turns,
duplicate IDs, scenario inconsistencies, template leakage, and rows exceeding
the active context limit. Tokenize and add one explicit prefix at repeat 10.

Convert all 1,360 DPO rows from both nominal splits separately into
prompt/chosen/rejected pairs. Never place rejected responses in the ordinary
tokenized union. No split is reserved as a held-out test set.

The completed conversion produced 1,360 SFT rows and 1,360 preference rows.
Tokenization produced 432,223 tokens (56,407 prompt and 375,816 response), or
4,322,230 effective tokens per epoch at repeat 10. Acceptance requires complete
schema validation, exact SFT/chosen agreement by scenario, Gemma-template
rendering, and balanced coverage of value units and scenario types.

## Phase 3: Croco-Munin delta audit

**Superseded (2026-08-30):** the initial plan conditionally admitted unique
candidate pairs after audit. The measured prompt overlap below triggered the
drop decision instead.

The deterministic audit compared `croco-munin-apertus-8b-da-50k` with the active
`croco-munin-apertus-8b-da-simpo-full-50k` using normalized hashes of prompt,
chosen response, and rejected response. Of 49,832 candidate prompts, 49,825 are
shared and only 7 are candidate-only. Although 49,798 full pairs and 38,077
chosen responses differ, they are alternative responses to essentially the
same tasks. The mean chosen-score delta on shared prompts is only +0.00647
(median zero), with 19,588 candidate wins and 19,322 losses. This is not useful
new task coverage, so the candidate is dropped from both SFT and preference
training. The reproducible report is at
`logs/data_audits/dfm10_croco_munin_overlap_20260830/report.json`.

## Phase 4: persona-seeded Danish chat

Do not tokenize persona profiles directly. Generate four chats per profile:
ordinary assistance, constrained instruction following, knowledge-seeking
dialogue, and multi-turn clarification/revision. Target exactly five assistant
turns on average with a 3--7-turn distribution: 10%/20%/40%/20%/10% for
3/4/5/6/7 assistant turns. This yields about 100,000 supervised assistant turns
across 20,000 accepted chats. Require natural Danish, no claim that the model
is the persona, and no
invented sensitive personal data. Generate with the established Gemma 4 31B
pipeline and independently audit every row. Target 20,000 accepted chats;
package and upload the accepted artifact before linking it into DFM10 at repeat
two.

## Phase 5: Domsdatabasen decision gate

**Superseded (2026-08-30):** the source was initially deferred pending a
project-level privacy and redistribution decision. The project subsequently
approved inclusion through the constrained grounded-chat path below; raw legal
continuation remains excluded.

This source does not block DFM10 and is not currently admitted. It has 3,917
long Danish judgments (about 91.2M characters in `text`; 96.5M in
`text_anonymized`) and could have moderate-to-high niche value for formal legal
Danish, grounded summarization/QA, and long-context training. Its general
capability impact would likely be modest.

The exact pseudonymized-text length profile under the active Gemma tokenizer is
33,365,727 tokens across 3,656 nonempty documents; 261 documents have an empty
`text_anonymized` field. Among nonempty documents, median length is 2,780
tokens, p75 7,516, p90 18,698, p95 33,098, p99 97,923, and maximum 709,815.
The median is 2,458 if empty rows are retained in the denominator. Of the
nonempty documents, 2,240
(61.3%) fit 4K, 2,804 (76.7%) fit 8K, 3,237 (88.5%) fit 16K, and 3,470 (94.9%)
fit 32K; 186 exceed 32K. This supports chunked grounded conversion rather than
whole-document examples under the current context limits.

Risk is material. The Hub card declares no explicit license; official public
download and the status of judgments reduce ordinary copyright concern but do
not establish ML-training or derivative-redistribution permission. Official
API access requires an application and an acknowledged purpose. The source is
pseudonymized, not anonymous: 3,620 rows contain anonymization tags, 261 rows
have empty `text_anonymized`, and some professional/corporate identities remain
by design. The publishing authority's GDPR basis does not automatically become
the project's training basis.

Recommendation: defer until written authorization or a legal review covers ML
training and redistribution. If admitted, use only nonempty official
pseudonymized text while retaining anonymization tags; fail closed on missing
anonymized versions; run PII/OCR checks; create grounded chunked tasks with
source IDs and evidence; and exclude unrestricted continuation and legal-advice
targets.

A natural initial production target, after those gates pass, is 3,000--4,500
accepted grounded conversations at repeat one, averaging four to five
supervised assistant turns (roughly 15,000--20,000 targets). Use one
conversation per usable judgment where possible. Feed the 2,240 documents that
fit 4K as whole-document evidence; use section/evidence chunks for longer
judgments, normally capped at one or two conversations per judgment. Mix
neutral case summarization, fact-versus-claim separation, procedural posture,
holding/outcome extraction, evidence-citing QA, and timeline reconstruction.
This is large enough to add legal-register and grounded-reading value without
amplifying a small corpus as if it were broad Danish supervision.

Use a natural grounded conversation rather than independent questions that
repeat the judgment. The first user message supplies the pseudonymized judgment
or selected evidence sections and requires answers based only on that material.
A representative five-assistant-turn sequence is:

1. neutral short summary of the case;
2. separation of parties' claims from facts established or accepted by the
   court;
3. procedural posture and the question the court had to decide;
4. holding/outcome with concise evidence references to the supplied text; and
5. a constrained follow-up such as a timeline, shorter rewrite, uncertainty
   check, or correction of a deliberately unsupported user inference.

Vary order and task selection; not every conversation needs all five forms.
Follow-ups must be answerable from the supplied evidence and should rely on the
existing conversation rather than restating the whole document. Assistant
answers must distinguish allegations, evidence, reasoning, and outcome; state
when the text is insufficient; preserve anonymization markers; and never offer
personalized legal advice or predict another case.

### Privacy and redistribution gates

Public access does not make the judgments anonymous or transfer the publishing
authority's processing basis to this project. Before admission, resolve all of
the following in writing:

1. **Controller and legal basis:** identify the project data controller and a
   GDPR Article 6 basis; obtain specific Danish-law review for Article 9 data
   and Article 10 criminal-conviction/offence data. Document why research use
   is necessary and proportionate and which Article 89 safeguards apply.
2. **DPIA:** complete a data-protection impact assessment covering model
   memorization, extraction attacks, stigmatization, false attribution,
   vulnerable parties, and downstream publication of data or weights.
3. **Residual identification:** treat pseudonymized judgments as personal data.
   Exclude the 261 empty anonymized texts; retain `<anonym>` markers; strip or
   separately justify case numbers, police journal numbers, exact dates,
   locations, participant metadata, and rare fact combinations; run automated
   and sampled human PII checks after OCR and after generation.
4. **Corrections and withdrawal:** source from the official update-capable API
   if authorized, record immutable source/version IDs, and propagate corrected,
   republished, or withdrawn judgments into training derivatives. A static Hub
   scrape is insufficient for this obligation.
5. **Security and minimization:** restrict raw access, log processing, define
   retention/deletion periods, keep generation and audit infrastructure under
   approved jurisdiction/vendor terms, and release only the minimum evidence
   needed for the training objective.
6. **Source and database permission:** court decisions are generally outside
   Danish copyright under Ophavsretsloven section 9, but independently authored
   contributions can remain protected, and the compiled database may have a
   section 71 database right. Obtain permission covering bulk extraction and
   reuse rather than inferring it from free web access.
7. **API and product terms:** obtain Domsdatabasen API authorization for the
   research purpose and written confirmation that permission covers model
   training, generated SFT derivatives, publication of those derivatives, and
   release of trained weights. Record any attribution, access, update, and
   public-product conditions.
8. **Alexandra dataset rights:** the Hub card declares no license. Obtain an
   explicit license or bypass the scrape by rebuilding from an authorized
   official source. Clarify rights in OCR text, metadata selection, and the
   dataset/database compilation.
9. **Derivative release review:** audit generated summaries and QA for copied
   passages, leaked identifiers, unsupported allegations, and sensitive facts.
   Do not assume a generated paraphrase is anonymous or unrestricted.

The admitted artifact is registered as
`dfm10-domsdatabasen-grounded-chats`, targeting 3,000--4,500 accepted chats and
15,000--20,000 assistant turns at repeat one. It contributes zero DFM10 tokens
until generation, privacy/grounding audit, tokenization, and packaging are
complete.

## Rebuild and validation

1. Add pinned download entries and converters; never overwrite inherited raw
   downloads.
2. Write converted outputs atomically with source manifests and row counts.
3. Tokenize accepted SFT sources with the Gemma tokenizer/template and verify
   prompt/response spans and context fit.
4. Do not rebuild `data/tokenized_dfm10` or resample yet. More DFM10 sources are
   still expected. The future union builder is wired to the charter token tree;
   rebuild once source admission is closed, then regenerate all sampled epochs
   with seed 0.
5. Regenerate analytics and reconcile expected token deltas. The mandatory
   baseline delta is minus 273,022,333 tokens per epoch before additions.
6. Validate that rejected preference responses have zero direct presence in
   the SFT union using normalized hashes.
7. Keep preference pairs in a dedicated export and training configuration;
   ordinary `pretrain.py data=dfm10` must not consume them.
8. Materialize/upload any generated derivative before declaring DFM10
   reconstructible from public Hub sources.

## Export-inventory state

As of 2026-08-30, none of the four newly reviewed repositories appears in
`exports_dfm10/manifest.json` or `exports_dfm10/inherited_hf_audit.json`.
This was expected for the excluded Croco candidate, persona generation seed,
and then-deferred Domsdatabasen source. The admitted Synthetic Values Model Charter is
already public upstream and therefore does not require a derivative export
package, but it should be added to the inherited-HF audit during the next export
inventory refresh. Any future accepted persona-generated artifact should be
materialized and registered as its own derivative package.

**Superseded (2026-08-30):** the persona artifact was subsequently registered
as the unmaterialized work-in-progress package `dfm10-danish-persona-chats`,
targeting 20,000 accepted chats, about 100,000 assistant turns, and repeat two.
The approved legal derivative is likewise registered as the unmaterialized
work-in-progress package `dfm10-domsdatabasen-grounded-chats` at repeat one.

## Deferred and excluded findings

Keep benchmark datasets evaluation-only. Do not add prompt-only Danish
WildChat as SFT, raw Gigaword/Wikipedia/Reddit under the current continuation
policy, failed/truncated GLM agent traces, or hallucination corpora with usage
restrictions and benchmark overlap. Agentic Code SFT and DA-Refusals require no
new download because their rows are already constituents of
`dfm-dyna-instruct`.

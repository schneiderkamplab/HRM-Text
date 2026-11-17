---
type: Review
title: Mimir-Decide sources for DFM16
description: Candidate message and MCQ additions distinguished from inherited DFM data and evaluation material.
status: draft
confidence: medium
last_updated: 2026-10-26
tags: [dfm16, datasets, decisions, instruction]
---
# Decision sources for DFM16

Inspection only; no source newly admitted, converted, tokenized or sampled.
Reviewed `/work/dfm/mimir-decide/configs/{data_v1.yaml,data_slot_restart.yaml,
decision_expansion_sources.json}`, the expansion inventory/receipts and
candidate manifests, expansion converters, D60/O63 documentation, and one
example from each of eight synthetic and three public candidate families.
This is source triage, not a representative row-quality audit.

## Inventory boundaries

Existing inputs: tasksource typed decisions, verified Bekko subsets,
LocalLLaMA/typed-decisions, MASSIVE, HelpSteer2 and DFM-derived decisions.
The historical full DFM conversion yielded 72,692,316 DFM-derived decisions:
do not feed that corpus back as supposedly new training content.

Expansion reports list 94 HF repositories, 91 collected (534 files), plus
four GitHub repositories and FlakeFlagger metadata. Downloaded is not approved.
Final review pool: 233,187 rows, 208,757 train and 24,430 development, comprising
100K executable synthetic, 50K UltraFeedback, 50K complaint classification,
and 33,187 WebJev rows. These counts include development unless stated.
Earlier unguarded full-scale DFM conversion and later guarded expansion are
different artifacts; never infer common decontamination from their location.

## Priorities

| Priority | Source | Proposed use / caveat |
|---|---|---|
| High | Local `decision-curriculum-v1` | 90,120 train rows; eight equally sized families before splitting: policy exceptions, deadlines, constrained tool selection, state tracking, expected value, versioned record lookup, ordinal rubrics, evidence checking. Deterministic answers and decisive/irrelevant/missing-evidence variants are valuable. Modest exposure: templates are repetitive. |
| High | nvidia/Nemotron-RL-knowledge-mcqa | Broad knowledge MCQ, approximately 617K upstream train rows. Preserve correct option mapping; no invented rationale. Card says CC-BY-4.0 despite local registry marking license unknown. |
| High | nvidia/OpenScienceReasoning-2 | Science and wider-domain QA with existing reasoning. Native Gemma reasoning/final separation, complete length-fitting examples and deduplication against Nemotron MCQA, which partly derives from this source. |
| High/conditional | Lexmount/WebJev; osunlp/Mind2Web | Grounded next-action decisions from page state. MCQ easiest; native tool messages only with complete schema, arguments and observations. WebJev retained 33,187 candidates across splits after filtering, not all training. |
| High/conditional | AgentGym/AgentTraj-L | Actual action/observation trajectories, especially SQL/science/tools. Preserve observations and successful trajectories; check component provenance and action schemas. Local license unresolved. |
| Medium | tasksource/nli4ct; copenlu/fever_gold_evidence | Evidence-grounded entailment/support with explicit insufficient evidence where labels permit. Keep evidence in prompt; do not fabricate rationales. Check inherited row overlap and source terms. |
| Medium | LocalLLaMA/typed-decisions; ZefanCai/Open-Jev{,-v1.1} | Operational choice/rubric examples. Select novel families rather than duplicate aggregated NLP tasks; retain soft-target semantics. v1.1 terms unresolved locally. |
| Medium | bigcode/commitpackft | Code-edit requests and before/after code, not artificial MCQ. Validate edit boundaries, project licensing and inherited code-source overlap. |
| Medium | emozilla/quality; qiaojin/PubMedQA | Reading comprehension/grounded scientific QA. Useful only with complete evidence fitting context and valid source split; inspect terms and lineage. |
| Low/incremental | UltraFeedback; HelpSteer2/3; Arena preferences | Evaluation/comparison instructions or high-quality chosen responses. Many already inherited; do not re-add all, do not present rejected responses as desirable completions. |
| Low | Complaint narratives, sentiment/topic/intent collections | Some document classification benefit, but likely low novelty; complaint privacy and redaction need checking. Synthetic customer-support sources preferable as a small first addition. |

Inherited matches confirmed: WANLI explicitly allowed in source filter;
ToolACE has repaired DFM11 native release; HelpSteer3 has audited DFM13
edit/preference releases. This is lineage evidence, not exhaustive row hashes.
Tasksource/FLAN/MASSIVE and common benchmark collections require source-level
and then row-level novelty checks; no claim that every such row is inherited.

## Conversion contract

- Render `state + question + options` as a user message; hard-label answer
  as requested option ID plus text, or an explicit free-response label/value.
  Randomize unordered options with aligned answers; preserve ordinal scales.
- Never put verification answers, provenance labels or targets in the prompt.
  The inspected UltraFeedback adapter always puts chosen first: shuffle before
  converting to MCQ. A soft preference distribution is not a certain argmax.
- Preserve native language and full relevant context. All use Gemma 4 native
  messages/template. Direct labels need no thinking; supplied valid reasoning
  can use native reasoning fields. Do not invent explanations from labels.
- Keep synthetic sibling groups together and separate train/development.
  Missing-evidence answers should refer to supplied evidence, not universal
  absence of knowledge. Tool selection MCQs are not substitutes for tool-call
  trajectory training. Native tools need schemas, valid calls and responses.
- Recompute lengths with the actual DFM tokenizer/template. Slot-v2 token
  totals are not DFM token totals. Do not truncate away decisive evidence.

## Not blanket imports

Do not import active benchmark held-out data: MMLU, ARC, BoolQ, HellaSwag,
PIQA, WinoGrande, RewardBench and related wrappers require split and alias
checks. Train splits are not automatically forbidden, but their marginal
novelty is usually lower. Finance test-only, TruthfulQA validation-only,
CodeReviewer valid/test, unresolved POP909 partitions, VAST/ACOS and raw
unknown-license sources stay out of this recommendation. Bias-in-Bios
sensitive-attribute inference is not a default general-assistant target.

Recommended first tranche: executable curriculum + Nemotron knowledge MCQ +
deduplicated OpenScience reasoning + a small grounded agent/evidence tranche.
Expected benefits are hypotheses; no downstream gain has been measured.

## External checks

- [Nemotron MCQA card](https://huggingface.co/datasets/nvidia/Nemotron-RL-knowledge-mcqa): train count, CC-BY-4.0, partial OpenScience lineage.
- [OpenScienceReasoning-2 card](https://huggingface.co/datasets/nvidia/OpenScienceReasoning-2): detailed reasoning and scientific/multidomain scope. Card/viewer counts differ; derive exact usable count from pinned local files.
- [AgentTraj-L files](https://huggingface.co/datasets/AgentGym/AgentTraj-L/tree/main): separate explicit environment training files.

---
type: Reference
title: DFM15 Organization Scan Dispositions
description: Complete 42-repository inventory with separate admission and decision-suitability assessments.
tags: [data, dfm15, decision, inventory]
status: draft
last_updated: 2026-10-21
confidence: medium
---
# DFM15 Organization Scan Dispositions

[Latest overview](latest-datasets.md). [DFM15 analysis](latest-dfm15.md).

Exact IDs and recorded dispositions from `data/dfm15/organization-inventory.json`
(42 entries). Scan decisions are historical evidence, not current remote-access
claims. Proposed suitability is separate from admission. The October 17
completion record supersedes the four additions' prepared-only status; its cited
full-mixture receipt is absent on this checkout. No new content audit was run.

For all `preserve_train_eval_boundary` entries, retain the original train/eval
split policy: this does not declare entire DaLA repositories eval-only. Existing
training partitions can supply A acceptability decisions, while heldout and
benchmark copies cannot be repurposed. Instruction-following checks may be B
where mechanically specified, but still evaluation-only on heldout splits.

| Exact HF ID | Recorded scan decision | Admission / proposed suitability |
|---|---|---|
| `danish-foundation-models/danish-gigaword` | `grounding_not_direct_sft` | D direct; B/C only after a separately scoped derivation |
| `danish-foundation-models/danish-dynaword` | `grounding_not_direct_sft` | D direct; B/C only after a separately scoped derivation |
| `danish-foundation-models/dala` | `preserve_train_eval_boundary` | Eval-only splits protected; A/B structure does not permit train admission |
| `danish-foundation-models/dala_large` | `preserve_train_eval_boundary` | Eval-only splits protected; A/B structure does not permit train admission |
| `danish-foundation-models/dala_medium` | `preserve_train_eval_boundary` | Eval-only splits protected; A/B structure does not permit train admission |
| `danish-foundation-models/dialog-k2-da` | `blocked_private_storage` | Pending/blocked; D now |
| `danish-foundation-models/instruction-dataset-v1` | `blocked_private_storage` | Pending/blocked; D now |
| `danish-foundation-models/norwegian-dynaword` | `grounding_not_direct_sft` | D direct; B/C only after a separately scoped derivation |
| `danish-foundation-models/ai_arena_udtraek` | `retain_inherited_routes` | Inherited audited routes; C generally, A only for recovered original decisions |
| `danish-foundation-models/ifeval-da` | `preserve_train_eval_boundary` | Eval-only splits protected; A/B structure does not permit train admission |
| `danish-foundation-models/swedish-dynaword` | `grounding_not_direct_sft` | D direct; B/C only after a separately scoped derivation |
| `danish-foundation-models/multi-ifeval` | `preserve_train_eval_boundary` | Eval-only splits protected; A/B structure does not permit train admission |
| `danish-foundation-models/global-piqa-da` | `preserve_train_eval_boundary` | Eval-only splits protected; A/B structure does not permit train admission |
| `danish-foundation-models/laerebogen` | `retain_inherited_routes` | Inherited audited routes; C generally, A only for recovered original decisions |
| `danish-foundation-models/cellar-metadata` | `grounding_not_direct_sft` | D direct; B/C only after a separately scoped derivation |
| `danish-foundation-models/kaenguruen` | `retain_inherited_routes` | Inherited audited routes; C generally, A only for recovered original decisions |
| `danish-foundation-models/dala_gen_v3` | `preserve_train_eval_boundary` | Eval-only splits protected; A/B structure does not permit train admission |
| `danish-foundation-models/linguistic-quality` | `prepared_addition` | Active per October 17 completion record; see source-specific grade |
| `danish-foundation-models/multilingual-gsm-symbolic` | `train_synthetic_only` | Active English synthetic train only; B/C |
| `danish-foundation-models/icelandic-dynaword` | `grounding_not_direct_sft` | D direct; B/C only after a separately scoped derivation |
| `danish-foundation-models/danish-wildchat4.8M` | `retain_exclusion` | Excluded; D |
| `danish-foundation-models/dynaword-annotations` | `grounding_not_direct_sft` | D direct; B/C only after a separately scoped derivation |
| `danish-foundation-models/dfm-dyna-instruct` | `unchanged_composite` | Inherited subset policy; not a new addition; mixed A/B/C only by task |
| `danish-foundation-models/ai-arenaen` | `retain_inherited_routes` | Inherited audited routes; C generally, A only for recovered original decisions |
| `danish-foundation-models/ai-arenaen-raw` | `retain_inherited_routes` | Inherited audited routes; C generally, A only for recovered original decisions |
| `danish-foundation-models/croco-munin-apertus-8b-da` | `retain_existing_selection` | Existing selected route only; C; no automatic preference label |
| `danish-foundation-models/croco-munin-apertus-8b-da-gold` | `retain_existing_selection` | Existing selected route only; C; no automatic preference label |
| `danish-foundation-models/croco-munin-apertus-8b-da-generated` | `retain_existing_selection` | Existing selected route only; C; no automatic preference label |
| `danish-foundation-models/croco-munin-apertus-8b-da-ls` | `retain_existing_selection` | Existing selected route only; C; no automatic preference label |
| `danish-foundation-models/faroese-dynaword` | `grounding_not_direct_sft` | D direct; B/C only after a separately scoped derivation |
| `danish-foundation-models/croco-munin-apertus-8b-da-simpo` | `retain_existing_selection` | Existing selected route only; C; no automatic preference label |
| `danish-foundation-models/croco-munin-apertus-8b-da-simpo-tuned` | `retain_existing_selection` | Existing selected route only; C; no automatic preference label |
| `danish-foundation-models/croco-munin-apertus-8b-da-simpo-full` | `retain_existing_selection` | Existing selected route only; C; no automatic preference label |
| `danish-foundation-models/croco-munin-apertus-8b-da-simpo-full-50k` | `retain_existing_selection` | Existing selected route only; C; no automatic preference label |
| `danish-foundation-models/nasjonalt-vitenarkiv` | `grounding_not_direct_sft` | D direct; B/C only after a separately scoped derivation |
| `danish-foundation-models/croco-munin-apertus-8b-da-50k` | `retain_existing_selection` | Existing selected route only; C; no automatic preference label |
| `danish-foundation-models/synthetic-values-model-charter` | `retain_inherited_routes` | Inherited audited routes; C generally, A only for recovered original decisions |
| `danish-foundation-models/Icelandic-flan` | `no_data_files` | Unavailable standalone payload; D |
| `danish-foundation-models/faroese-dyna-instruct` | `prepared_addition` | Active per October 17 completion record; see source-specific grade |
| `danish-foundation-models/icelandic-dyna-instruct` | `prepared_addition` | Active per October 17 completion record; see source-specific grade |
| `danish-foundation-models/dutch-dynaword` | `grounding_not_direct_sft` | D direct; B/C only after a separately scoped derivation |
| `danish-foundation-models/norwegian-dyna-instruct` | `unchanged_composite` | Inherited subset policy; not a new addition; mixed A/B/C only by task |

## Interpretation

Arena exports retain audited SFT routes, not necessarily original pairwise
votes; recovering intact preferences may yield A, whereas repaired-response
preferences require re-adjudication (C). Model-charter responses are not
universal truth labels. Croco generated/gold/SimPO names do not establish a
scored or pairwise decision target; retain the selected simpo-full-50k route
and shared-prompt overlap constraints.

Raw DynaWord/Gigaword, Nasjonalt vitenarkiv and metadata are D for direct
bounded-decision supervision. Source-exact extraction with known offsets can
be B under an explicit evidence/identity task; semantic relevance or quality
choices require C. Do not treat absence in a metadata catalogue as a negative
world fact. Earlier Danish-only raw-continuation policy is not changed here.

Private collections need content access, schema inspection and duplicate
resolution before any proposed task. Never combine filtered and unfiltered
Dialog copies, or both constituent and all-shuffled instruction copies.
`danish-wildchat4.8M` remains explicitly excluded, not a fresh pending candidate.

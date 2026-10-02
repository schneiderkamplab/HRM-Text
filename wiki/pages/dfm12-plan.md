---
type: Plan
title: DFM12 Dataset Plan
description: Approved additions and implementation requirements for DFM12.
tags: [dfm12, datasets, acceptability, correction]
status: draft
last_updated: 2026-09-25
confidence: high
---
# DFM12 Dataset Plan

Dataset-by-dataset progress is maintained in [DFM12 addition status](dfm12-status.md).

## Identity Sampling Weight

Owner decision, 2026-09-25: include audited Mimir identity at **repeat 10**.
`dfm12/config.yaml` records `identity_repeat: 10`; accepted identity component
manifests carry that weight. Keep source rows unique and apply repetition only
at final sampling, which remains explicitly deferred. The current automated-pass
inventory is 8,715 conversations / 4,109,461 tokens, implying **41,094,610 tokens
per epoch** at repeat 10 if all these rows pass final admission. Other source
weights are unchanged. This is not approval to include rejected, duplicate or
failed-generation rows, nor a claim that identity has already been exported.

## English and Dutch DaLA

Decision (2026-09-22): include both linguistic acceptability and grammatical
error correction from the following repositories, analogous to the inherited
Giannor TV2R instruction tasks. Training split only; include clean controls
as well as corrupted examples.

| HF repository | Configuration | Language | Training rows |
|---|---|---|---:|
| schneiderkamplab/dala-english-common-pile | acceptability | English | 766,288 |
| schneiderkamplab/dala-english-common-pile | correction | English | 766,288 |
| schneiderkamplab/dala-dutch-dynaword | acceptability | Dutch | 766,262 |
| schneiderkamplab/dala-dutch-dynaword | correction | Dutch | 766,262 |

Total: 3,065,100 training rows before conversion validation. Configurations
share original/corrupted pairs, so this is not a count of independent examples.
Counts are from the source cards, not local tokenization. Repeat and token
allocation remain to be determined.

Source cards inspected:
- [English](https://huggingface.co/datasets/schneiderkamplab/dala-english-common-pile), revision `243eaa2b50d740611db42b6b17e67c6e2fd2cfbf`.
- [Dutch](https://huggingface.co/datasets/schneiderkamplab/dala-dutch-dynaword), revision `a09dffe55c9db956f3ae39ed1916cb2d5dfaff73`.

## Implementation Contract

- Registered under downloader group `dfm12`, with both configurations' training
  JSONL.GZ shards. Validation/test are not included in the download patterns.
- Use the existing structured `messages`, not the TV2R field parser: these
  datasets already provide user instructions and assistant responses.
- Render with the training Gemma4 tokenizer/template once. Preserve the source
  instructions and exact yes/no acceptability labels, including for Dutch.
- Correction targets contain only the corrected sentence; clean controls retain
  their identity-correction target. Do not introduce explanations or reasoning.
- Metadata contains labels and audit judgments: never expose it in prompts.
  Retain pair/document IDs, source attribution, split and revision separately.
- Keep configurations separately identifiable through conversion/tokenization
  and sampling. Preserve document-level split boundaries across both tasks.
- Validate roles, nonempty messages and task targets before tokenization;
  report rejected rows and rendered token counts per language and task.
- These are provisional synthetic training sources, not new gold evaluations.
  English's source-card sample reports 11 clearly erroneous and 9 uncertain
  originals in 100 pairs; Dutch also reports residual source-label noise.
  Inclusion is approved, but these caveats must accompany quality assessments.

Historical state (2026-09-22, superseded by the update below): downloader
registration and inclusion plan only; no preparation had been launched.

Related: [TV2R integration](dfm8-plan/danish-linguistic-acceptability-and-gec-data.md).

## Multilingual Expansion, 2026-09-24

Approved additions: multilingual profile-aware Mimir identity, new-language
DynaWord transformations, direct permissively licensed OPUS translation pairs,
and reviewed multilingual post-training sources. Implementation, fixed policy
choices, commands and current blockers are in
[DFM12 component preparation](/pages/dfm12-components.md).

User refinement: **no final sampling yet**. Other threads are adding further
DaLA-like correction/acceptability sources and other datasets. Prepare and
audit independent components without freezing DFM12 or rebuilding inherited
DFM11. Current generation/audit choice is Gemma 4 26B-A4B, not the older 31B
teacher used for DFM8 transformations.

Owner update, 2026-09-25: include `V4ldeLund/scandi-translated-instruct` and
the Norwegian DynaInstruct NorQuAD-Wikipedia/FLEURS-Alpaca subsets. Supersede
the earlier source omissions/holds; retain benchmark contamination annotations,
provenance, deduplication and automated quality review. Queue these audits in
isolated roots without rewriting active main/DaLA audit manifests. See
[current status](dfm12-status.md#source-inclusion-supersession-2026-09-25).

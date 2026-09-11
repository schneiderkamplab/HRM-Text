---
type: Training Data Plan
title: DFM11 Post-Training Subset
description: Built quality-weighted successor to DFM8-post using corrected DFM11 sources.
tags: [dfm11, post-training, sampling]
status: stable
last_updated: 2026-09-08
confidence: medium
---
# DFM11 Post-Training Subset

Original proposal (superseded by the implementation below). Based on the corrected
103.215B DFM11 sample and its report at `logs/dfm11/sample_corrected.log`.
Predecessor: [DFM8-post](dfm8-plan/dfm8-post-training-rl-subset.md).

## Target

### Approved implementation, 2026-09-08

User approved reducing repeats to 1 or 2, excluding pretraining-like and
peripheral families entirely, measuring behavior volume, then drawing 33% of
FINAL tokens broadly from the OTHER non-excluded sources. This supersedes both
the earlier 20% anchor target and discretionary 24B/34B total-size proposals.
No fixed total is enforced.

Implemented by `scripts/prepare_dfm11_post.py` using the corrected completed
DFM11 task report (post-filter lengths) and the current DFM11 policy. The
baseline and inventory hashes are saved in `logs/dfm11_post/manifest.json`.
The repeat-2 families are explicit in `TWICE`; other included families have
repeat 1 and all inherited exclusions/caps remain upper bounds. Repaired
Folketing error correction has an additional source-wide 100K-example cap.
Unclassified inputs fail closed (excluded with a reason in the manifest).

The broad pool is disjoint from behavior sources. Allocate token budgets
proportional to square root of source-level eligible token capacity, saturating
at one capped pass; spread each source budget proportionally across its files.
Round down row caps. This retains small-source diversity, bounds large-source
dominance, and never repeats anchors to meet the target. Extra anchors needed
are behavior_tokens * 0.33 / 0.67, not behavior_tokens * 0.33.

Initial measured-inventory projection:

| Portion | Expected tokens/epoch |
| --- | ---: |
| Behavior | 23,924,762,092 |
| Broad anchors | 11,782,937,526 |
| Total | 35,707,699,618 |
| Anchor share | 32.9983% |

These are expectations from exact eligible length sums and row caps, not
claims about the sampled rows' realized lengths. Ten epochs are being sampled,
matching full DFM11's index availability; this does not prescribe ten epochs
of post-training. After completion, `logs/dfm11_post/measured.json` records
actual average tokens and checks the anchor share within 0.5 percentage points.

Paths: `data/tokenized_dfm11_post`, `data/sampled_dfm11_post`,
`data_io/prefix_config_dfm11_post.yaml`, `config/data/dfm11_post.yaml`.
Logs: `logs/dfm11_post/prepare.log` and `logs/dfm11_post/sample.log`.
The generated exact-task allowlist and filtered symlink tree prevent unmatched
sources from leaking into sampling. No DFM11 source or sampled artifact is
modified; no retokenization is needed. The builder refuses existing outputs.

Run: `python scripts/prepare_dfm11_post.py --epochs 10 --anchor-fraction 0.33 --sample`.

Completion receipt, 2026-09-08: all ten epochs finished and the sampler exited.
Actual mean per epoch is 35,707,711,739 tokens: 23,924,758,414 behavior and
11,782,953,325 anchors (32.99834%). The anchor-share check passed. Each epoch
has four readable, matching-length index arrays with 54,054,093 entries.
Metadata and `logs/dfm11_post/measured.json` are written. This supersedes the
sampling-in-progress status above.

### Quality review revision, 2026-09-08

User approved reviewing other large contributors and undersampling where
warranted. This supersedes the repeat/exposure decisions above for the
specific sources below, not the 33% final-anchor rule. Ten tokenized targets
were sampled from each of sixteen other families initially contributing >=2%,
alongside the earlier twenty complete Koolbardi conversations. Evidence and
per-source decisions: `logs/dfm11_post/large_source_review_20260908/assessment.md`.
These are qualitative spot-checks, not measured corpus-wide defect rates.

- Koolbardi DA/EN: approximately half of whole conversations, stratified
  across topic, interaction mode, complexity and length within each language.
  A fixed selected pool preserves all assistant targets; this supersedes the
  proposed rotating conversation pools for this build.
- Nemotron Agentic: half the fitting targets; drop, never truncate, overlength
  answers. Narrow authentication-heavy dialogues previously consumed 11.6%.
- Nemotron Instruction and FineInstructions EN controlled: half target caps.
  FineInstructions contains incomplete responses even before sampler truncation.
- Repaired synthetic native tools and DFM8 synthetic multi-turn chat: repeat
  2 -> 1. Weather-heavy tool scenarios and mixed-quality/persona-heavy chat do
  not justify double exposure in this post subset.
- Anchor allocation weights: x0.5 for FLAN, FLAN factual, SYNTH, DFM Dyna
  Instruct and repaired Nemotron SWE; x0.25 for Nemotron Terminal, whose actual
  targets still contain legacy think/JSON command formats. Re-normalize other
  anchors to 33% of the reduced final total, without exceeding one pass.
- Retain OpenStax chats, scientific summaries, DOLCI repaired tools, summary
  controls and Natural Instructions at their previous repeat settings.

Policy code lives in `scripts/dfm11_post_quality.py`. Whole-conversation
selections are explicit sorted original-row ordinals supplied through the
sampler's optional `selection_indices_path`, applied AFTER computing backing
token offsets and BEFORE eligibility filtering. Unspecified selections leave
the existing sampler path unchanged. No raw/tokenized source rewrites.

Rebuild command: `python scripts/prepare_dfm11_post.py --epochs 10 --anchor-fraction 0.33 --rebuild --sample`.
Build in `data/sampled_dfm11_post.rebuilding`, hardlink the unchanged token
backing store after verifying task layout, validate ten index sets and the
anchor share, then publish to the existing path. Retain the old directory as
`data/sampled_dfm11_post.pre_quality_review` for rollback. Never run a rebuild
while that post corpus is in use. Existing DFM10 training is unaffected.

Completed revision: ten epochs, 42,877,601 targets each. Measured mean per
epoch: **25,511,448,228 tokens**, consisting of 17,093,442,624 behavior and
8,418,005,604 broad-anchor tokens (32.99697%). This is 28.55% below the earlier
35.708B version. Final metadata and `logs/dfm11_post/measured.json` agree.
Koolbardi retained 278,918 DA and 275,106 EN conversations (approximately 52%,
with small strata rounded up), preserving every target of each selected
conversation. Physical `tokens.npy` remains the old backing store, hardlinked
to avoid copying it; exposure/epoch counts come from indices, not its size.

| Changed source | Previous B/epoch | Revised B/epoch (rounded projection) |
| --- | ---: | ---: |
| Nemotron Agentic | 4.138 | 1.888 |
| Koolbardi DA | 2.704 | 1.416 |
| Koolbardi EN | 2.611 | 1.368 |
| Nemotron Instruction | 1.603 | 0.802 |
| Synthetic native tools | 1.026 | 0.513 |
| Nemotron SWE | 1.021 | 0.471 |
| FLAN factual | 0.898 | 0.414 |
| FLAN | 0.826 | 0.381 |
| Nemotron Terminal | 0.807 | 0.186 |
| SYNTH | 0.739 | 0.341 |
| FineInstructions EN controlled | 0.738 | 0.369 |
| Synthetic multi-turn chat | 0.733 | 0.366 |
| DFM Dyna Instruct | 0.719 | 0.332 |

Full DFM11 policy and corpus remain unchanged. Undersampling limits exposure;
it does not repair the remaining factual or formatting defects.

### Earlier size proposal (superseded)

Start with approximately 24B tokens per epoch: 80% behavior-focused SFT and
20% broadly sampled capability anchors. This is not preference/RL training.
Suggested disjoint token budgets (not measured outputs):

| Bucket | Share | B tokens |
| --- | ---: | ---: |
| Multi-turn and grounded conversation | 30% | 7.2 |
| Native tools and agentic trajectories | 25% | 6.0 |
| Instruction, format, answer contracts | 15% | 3.6 |
| Summarization, editing, Danish language control | 10% | 2.4 |
| Diverse math/code/general anchors | 20% | 4.8 |

## Source decisions proposed

- DFM8 retained core: audited English/Danish OpenHermes, six behavior-focused
  synthetic families, SkoleGPT, verified instruction data and no_robots.
  Strict math/code synthetics can belong to anchors; assign each row once.
- DFM9: include CoEdIT, ASSET and selected Natural Instructions as behavior
  supervision; factual FLAN, NuminaMath and general reasoning only as diverse
  capped anchors. Native Terminal trajectories are eligible for the tool
  budget, not an automatic inclusion of all 4.12B current tokens.
- DFM10: emphasize persona chats, grounded Domsdatabasen, Wikipedia/OpenStax/
  Tidsskrift chats, Mimir grounded/answer-contract/IFEval/entailment/DROP/event
  tasks. Use instruction tasks directly, but distinguish verifier judgments
  from examples teaching the model itself to comply with instructions.
- Include repaired Nordjylland/GovReport/WikiCat/scientific summarization,
  TV2R language/editing, Andersen/DiEm and small Danish lexical/NER supervision.
  Keep Bornholmsk, medical, book-ad and literary sources as small diversity
  slices rather than large repeats. ScandiQA is a small QA component; do not
  amplify borderline MultiZebra. DaCoref stays excluded.
- DFM11: Koolbardi DA/EN (5.3155B at one pass) and FineInstructions chats
  (1.6978B at one pass) become conversation core. Retain the existing balanced
  100K English legacy selection, not the entire legacy reservoir. These two
  families nearly fill 7.2B themselves, so cap them to leave room for genuine
  and other grounded chat sources; do not mechanically double repeats.
- Use ONLY repaired DOLCI, Glaive, ToolACE, Nemotron tool calling, and DFM11
  synthetic native tools; retain xLAM and fitting DeepDive/search trajectories.
  Cap repaired SWE and terminal data so long code traces cannot crowd out
  ordinary calls, clarification, tool-result use and final responses.
- Mathagentic: retain approved TinyGSM cap and verified Prolog; use as small
  math/tool bridges, not a reason to scale Python-only answer styles broadly.
- Folketing repaired error correction: small instruction-editing slice only.
  Bulk Folketing/DynaWord/Common Pile reconstruction and prefix continuation,
  bulk OPUS translation, large Laerebogen repeats and bulk FLAN are not the
  behavioral core. Most are omitted; suitable diverse rows can enter anchors.
- Model-charter supervision: retain a small bounded slice after resolving
  physical source aliases. Current report shows `data__model_charter_values_da.jsonl`,
  while policy names use `dfm10_synthetic_values_model_charter_da__`; do not
  assume a named prefix or its repeat actually matched. Verify EN availability.

## Implementation gates

1. Enumerate actual DFM11 tasks and resolve each to a source identity, audit
   status, replacement lineage and exactly one budget bucket. Never copy the
   stale DFM8-post prefixes. Preserve all current DFM10/11 exclusion decisions.
2. Construct an explicit allowlisted tree or enforce unmatched-task failure;
   default repeat=1 must not leak the rest of DFM11 into the post corpus.
3. Preserve Gemma 4 native messages, tool schemas/results, assistant turn
   boundaries and reasoning/final contracts. Check actual rows, not names.
4. Broad anchors must be stratified over sources and task types, not only the
   largest math files. Balance Danish/English within applicable behavior
   buckets; start with 40-50% Danish in language-bearing behavior supervision,
   accounting for language-neutral code/tools separately.
5. Budget by effective sampled tokens after caps/repeats. Preserve source
   conversations and lineage to avoid redundant pair-plus-chat supervision.
   Cap total per-source exposure; do not let extra file sharding alter caps.
6. Generate a source-level projected report before sampling. Tune repeats only
   after accounting for real available token mass. 24B is a proposal, not a
   requirement to inflate tiny gold datasets. Sample pilot and verify totals,
   source exclusion, bounds and the 20% anchor share before full build.
7. Start with a short continuation and compare chat/tool/format behavior plus
   math/code/general regression metrics. Epoch count and LR require a separate
   training decision; having many index sets does not imply training all of them.

Related: [DFM11 policy and build corrections](dfm11-portability.md).

---
type: Runbook
title: Reviewed EMA Stochastic Preferences and Corrective SFT Handoff
description: Partial semantic review, immutable reviewed exports, exposure-aware recipe and unresolved EMA decisions.
tags: [dfm12, identity, ema, preferences, review]
status: stable
last_updated: 2026-09-27
confidence: high
---
# EMA Stochastic Review Handoff

## Authorized 10K Corrective Continuation, 2026-09-27

The user explicitly chose **5% identity and 95% DFM11 replay throughout all
10,000 optimizer updates**. This supersedes the parent's proposed 0.5% identity
mixture and the earlier short-course exposure ceilings below. At global batch
262144, nominal rendered-token budgets are 131,072,000 identity and
2,490,368,000 replay. Report actual packing, repetition and supervised-token
counts separately; do not silently reduce the requested identity share.

Keep the existing EMA decay **0.9999 and accumulated EMA state unchanged**:
no reset or replacement with current parameter weights. Resume checkpoint
step_2887261 with its model and optimizer state. Keep constant base LR 1e-5,
lr_auto, no warmup and no decay. Evaluation and export remain EMA-only.

The user's memory ceiling applies to **combined work in this thread: at most
50% of each GPU**. The infrastructure-retry servers and corrective training must
not overlap if their combined allocation exceeds this ceiling. Verify a capped,
non-W&B training smoke before starting the 10K continuation; adjust accumulation
and/or activation checkpointing while preserving global batch and training
semantics. These are authorized settings, not a claim that training has started.

## Full Review and Sealed Holdout Preparation, 2026-09-27

All four sampling-index ledgers have now been reviewed: 560 stochastic turns
in total. Sample-index verdicts (correct/partial/wrong) are 18/38/84,
27/42/71, 20/37/83 and 22/35/83. These are assistant semantic judgments,
not independent human labels; partial/wrong counts are not hallucination counts.
The full merged export is now
`data/dfm12/identity-ema-preferences-20260927-v6-full-reviewed` with all 560
stochastic turns reviewed and zero pending. Including the 140 earlier reviewed
greedy turns, it contains 700 chosen answers and 587 same-history preference
pairs. Deduplicated targeted SFT has 249 training examples (43,604 rendered /
13,010 target tokens) and 82 validation examples (14,134 / 4,784 tokens).
The full export supersedes V5 as the corrective training source; actual training
still requires the independently checked packed data and capped memory smoke.

Parent accepted the packed handoff after all 331 train/validation rows passed
actual `V1Dataset._load_batch` input, shifted-label, position and padding checks.
All 10 ambiguous first-turn rows remain excluded from targeted SFT. The 65-test
corpus/packer suite passed. `final-data-ready.json` records the accepted hashes
under `logs/training/dfm12_XL_identity_corrective10000steps`.
The detached supervisor was re-armed after independent safety review and is
building the 95/5 mixture. It requires a complete smoke checkpoint at 2887264
before starting production from the original 2887261 state, never smoke weights.
Infrastructure errors fail closed; only verified memory failures trigger the
full-checkpointing fallback. The pilot's infrastructure retry is complete;
its release receipt leaves all borrowed foreign audit servers untouched.

The capped smoke subsequently completed updates 2887262-2887264 and wrote a
complete checkpoint; peak owned GPU memory was 58.5-60.7 GiB. Production then
resumed separately from the original step2887261, not smoke weights. At the
2026-09-27 launch check it had completed step2887264 and was entering 2887265,
logging to DFM5/run `dfm12-xl-identity-da-en-1000`. The production log is
`logs/training/dfm12_XL_identity_corrective10000steps/configs/train.log`.
GAS8, no activation checkpointing, constant base LR1e-5/lr_auto and unchanged
EMA0.9999 are active. Target stop is2897261. The observed training allocation
remains below the user's half-GPU ceiling; unrelated audit servers coexist.

The new composition holdout is sealed at
`data/dfm12/identity-composition-holdout-20260927-v1`: 20 Danish and 20 English
two-turn conversations, 80 turns total. Manifest SHA:
`bd1181b9d37b4da3afc8dfbc7ee20599a1010dd85b60c867d712b712a369787c`.
Independent CPU checks verified 97 pins and no exact normalized prompt overlap
against the recorded exclusion pools, including a supplemental read-only scan
of the original identity SQLite database. This checks exact strings, not semantic
novelty; these are new compositions of established facts, not new knowledge.
The prompts must never enter corrective training. Independent semantic rubric
review passed without blockers; the final packed-corpus handoff and memory smoke
remain explicit gates. Receipt and review are under
`data/dfm12/identity-holdout-independent-review-20260927`.

## Historical V5 Handoff

2026-09-27: Tesla independently reviewed the140sampled-answer subset and reported
no blockers after one classification correction: case62/sample0/turn1 says
`XL has16layers` in response to an each-module question. This may implicitly mean
16each; it is **partial/completeness**, not a clear factual contradiction. The
corrected row remains in all-admitted SFT/preferences but is excluded from the
targeted factual/positive subset. No published v4 artifacts were overwritten.

**Use `data/dfm12/identity-ema-preferences-20260927-v5-stochastic-reviewed/targeted-sft`
for repacking.** Root manifest SHA:
`e4720b1a60caa74dbac4ece4e5b1b79d27602ef81738ebaeefbe7ea41a9bb2ae`.
Targeted child manifest SHA:
`3c6df48af23080aa67bc3fe7ecb101ce6be8cf7a17d2c4284f430c564465a9ee`.

| V5 targeted split | Rows | Rendered tokens | Supervised target tokens |
| --- | ---: | ---: | ---: |
| Train | 131 | 19776 | 6441 |
| Validation | 34 | 6308 | 1793 |

Coverage remains **140reviewed/420pending**; revised subset verdicts are
18verified-correct,38partial,84wrong. Its122pairs are93factual corrections,
20completeness, seven precision, two style. Combined exports remain280chosen
rows and236pairs. Factual-EOS DPO is now114train/32validation. Every pending raw
answer remains excluded. Independent review does not imply all560were reviewed.

V5 embeds the corrected recipe at `corrective-sft-recipe.json`, SHA
`76ae175bd7d9dd821d8621b72f5bd5f8389384423899741c04682098c1a3f2db`:
**zero warmup, constant1e-5 LR, no LR decay**; proposed ceiling one train pass,
6441supervised tokens and at most20optimizer updates, first limit wins. These
remain proposals, not authorization. EMA horizon, effective batch and optimizer
handling require explicit decisions. No user approval of EMA0.99 is claimed.
The sealed composition holdout remains uncreated; all old100prompts remain dev.

99CPU tests passed, including the ambiguous-depth exclusion regression; v5 file
pins and unchanged v4 manifest were verified. The parent's166-row loader check
below applies to v4; v5 has165targeted rows and must be repacked/revalidated by
the parent. No training, GPU actions, packer edits or pilot changes occurred.
The following v4 counts and separate recipe revision are historical context,
superseded for the next candidate by this v5 handoff.

## Coverage

2026-09-27: **140/560 stochastic answers reviewed;420excluded pending review**.
The selection was sampling index0 for all100original conversations, chosen without
lexical scores: all25families,70DA/70EN answers. Pending coverage is210per language.
Whole-response assistant judgments are18verified-correct,37partial,85wrong;
these are NOT overall560-answer accuracy or independent human signoff.
Tesla/parent independent review of chosen answers remains a separate gate.

The122new pairs comprise94factual corrections,19completeness, seven precision,
two style preferences. Factual correction includes unsupported additions, not
only proven false statements. Initial correct phrases did not exempt the rest
of an answer from review. Failures include Gemma/LLaMA weight ancestry, wrong
training-team roles, invented rosters, and layer/pass confusion. No anchor-recall
score was used as semantic approval.

Source: `data/dfm12/identity-ema-stochastic-20260927-manual-v2/samples/responses.json`,
SHA `a9f16885642ef9946f43137846688803716c2e77d0a52668082bb9be175a4982`.
All400conversations/560turns have complete operational coverage and all-eight-worker
EMA verification. Length stops are completed operational outputs, not correct
answers. No raw auto-admission occurred.

## Export and Review

Artifact: `data/dfm12/identity-ema-preferences-20260927-v4-stochastic-reviewed`.
Manifest SHA: `7c80d7a915b8acc0bafa1d28838b23863b1a238558916e8a5c84dfcf21eea3dc`.
`review.md` includes every newly reviewed exact history, response, correction
and rationale; `review-ledger.json` records case/turn/seed, prompt/response hashes,
language, family, factual authority and preference kind. `pending-review.json`
names all420excluded turns. Existing reviewed140greedy rows are retained, giving
280chosen SFT rows and236DPO pairs in the combined export.

Builder: `scripts/prepare_dfm12_identity_stochastic_preferences.py`.
Review source: `configs/dfm12/identity-ema-stochastic-20260927-reviewed.yaml`.
An explicitly reviewed first turn can reuse an already verified chosen answer
only for an identical full prompt, with its source row ID retained. Such reuse
was approved individually after reading each answer, not automatically applied
to unreviewed samples. Followup reuse across generated histories is rejected;
followups receive individually authored corrections for their actual history.
Every DPO pair shares exact input/history. All prior assistant tokens are masked.

| Export | Train rows | Rendered / target tokens | Validation rows | Rendered / target tokens |
| --- | ---: | ---: | ---: | ---: |
| All admitted SFT | 216 | 28544 /10339 | 64 | 9367 /3051 |
| Targeted SFT | 132 | 19864 /6494 | 34 | 6308 /1793 |

Targeted SFT keeps factual corrections and verified positives, excludes ambiguous
initial weight-training prompts, and deduplicates exact supervised tokens/labels
while retaining all source row IDs. Train languages:67DA/65EN; validation18DA/16EN.
All family splits are inherited before sampling:20train/five validation families,
with language siblings and all variants together. These are DEVELOPMENT splits.

### Ambiguity

The Danish `allerførste vægttræning` wording can mean bodybuilding; English weight
training is also potentially ambiguous. Original cases0and1 turn1 are flagged
`prompt_ambiguity`, excluded from targeted SFT and factual-EOS DPO, and not treated
as blanket identity-deficit evidence. Physique values remain unverified, but an
alternative reading alone is not an identity failure. The new Danish correction
starts `Hvis du mener sprogmodellen`. Explicit Gemma followup claims are separately
assessed against the model facts. No system-message interventions were added.

## Parent Packer Handoff

Use `<artifact>/targeted-sft` with the parent-owned existing packer; its manifest
SHA is `25404eb8a7a9b7750bb74042cb6e42d41952d83c06198094d0d2b6256d62db94`.
`admitted-sft` is the all-reviewed alternative. Each child exposes
`chosen-sft-tokenized/{train,validation}.jsonl` and the original packer manifest
contract. `review_complete:true` means every EXPORTED row reviewed, while
`excluded_unreviewed_source_turns:420` stays explicit. The root source-review
manifest remains partial. Published corpus files and manifests were not mutated.

Parent has packed the targeted subset to
`data/dfm12/identity-ema-preferences-20260927-v4-targeted-v1-packed` and reports
actual `V1Dataset._load_batch` input/shifted-label/padding equality for all166rows.
Parent's combined stochastic/base/packer suite passed59tests. The earlier
`identity-ema-preferences-20260927-v3-v1-packed` receipt has108train rows,
14686rendered/5066target tokens;32validation rows,4439rendered/1515target tokens.
Its independent140-row loader verification and nine packer tests are recorded in
the [preference runbook](/pages/dfm12-identity-ema-preferences.md).
Consumers require `target_only=True`; repeat=1 and only epoch_0 are provided.
No packer, pretrain, dataset loader, scheduler or multilingual-pilot edits were
made by this review task. No training or GPU actions were launched.

## Provisional Recipe

**Superseded by explicit user authorization on 2026-09-27:** retain existing
EMA decay/state0.9999 and optimizer/active weights without reset or EMA-weight
initialization replacement; train10,000updates with **5% final targeted SFT /
95% DFM11** throughout, not0.5%. Identity rendered budget is131,072,000tokens
at GBS262144. No warmup/decay; constant1e-5 with lr_auto and BP8. The parent's
final reviewed560-sample data, owned retry release and capped no-W&B memory
smokes gate the isolated supervisor described in
[identity continuation](dfm12-identity-continuation.md#corrective-10000-step-supervisor-2026-09-27).
The earlier short-course recipe and answer-pending language below are historical,
not the currently authorized recipe. Only EMA evaluation/export is allowed.

**Supersedes the frozen corpus's warmup2 recipe, without overwriting it:**
`data/dfm12/identity-corrective-sft-proposal-20260927-v2/recipe.json`, SHA
`f17b5c97e7e1151d4eddf513c6f032281aa19acb0f7983746edc27e5e5716696`.
No warmup, no LR decay;1e-5 is a provisional constant LR consistent with latest
identity settings. Require verified EMA step2887261 initialization, not silent
substitution of non-EMA active weights. Optimizer-state handling and batch choice
remain explicit approval decisions, not assumed resume behavior.

Initial proposed ceiling: **one pass over132targeted train rows,6494supervised
tokens, at most20optimizer updates, stopping at the first limit**. Batch sizing
must follow the measured packed row/token counts and prevent corpus wrapping.
Do not inherit the broad1000step loop:262144tokens x1000updates x5percent gives
13,107,200identity rendered tokens, about892passes over the old14686token corpus.
This is an exposure illustration, not a measured new run; row-based mixture
percentages must not silently be equated with target-token percentages.

The inspected config has LR1e-5, GBS262144, GAS2, BP8 and EMA0.9999. AdamATan2
updates EMA once per optimizer update via `lerp_(...,1-ema)`. Old weight coefficient
0.9999^N is99.8002percent after20updates,99.0049percent after100,90.4833percent
after1000. A short course barely moves this EMA. Parent has asked the user about
an isolated shorter-horizon EMA0.99 branch versus retaining0.9999 with a longer
LOW-EXPOSURE course, or remaining data-only. **Answer pending; none is approved.**
Do not reset EMA, change decay, evaluate non-EMA, or replay the tiny identity set
to defeat this lag without explicit authorization.

## Readiness Gates

Create a separately authored and sealed prompt-COMPOSITION holdout using the
same approved facts, not claimed unseen knowledge: proposed20conversations per
language, at least10multi-turn per language. Include disambiguated model-weight
context, role corrections, tokenizer/weight distinctions and cycle arithmetic
compositions. Check full user turns against all previous training/development
pools, independently review targets and pin/hash before optimization. This new
sealed set is **not created**; old100prompts and all derivatives remain development.

`dpo-factual-eos` has115train/32validation pairs, omitting ambiguity, other
preference kinds and length-stopped rejections for an initial candidate. This is
data preparation, NOT a verified DPO training pipeline. Still require independent
chosen review, a pinned EMA reference, actual trainer completion-only logprob/EOS
tests, bounded exposure and approval after corrective-SFT semantic review.
No automatic SFT-to-DPO or full-evaluation chaining.

98CPU tests passed across new stochastic admission, prior preference and evaluator
tests; after the separate recipe correction,15focused tests passed. All140new
rows passed exact raw-template/prompt-token binding and final-only label checks.
Remaining:420semantic reviews, independent chosen review, sealed compositions,
EMA/batch/optimizer decisions and explicit training authorization.

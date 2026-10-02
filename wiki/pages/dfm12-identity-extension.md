---
type: Runbook
title: DFM12 Curated DA/EN Identity Extension
description: Isolated materialized originals-plus-curated identity conversations, held-out paraphrases, and sealed source provenance.
tags: [dfm12, identity, provenance, dataset]
status: stable
last_updated: 2026-09-28
confidence: high
---
# DFM12 Curated DA/EN Identity Extension

## 21-Language Extension Queue, 2026-09-28

The user requested approximately 2,000 accepted conversations per language
across 21 languages. A separate [CPU-prepared identity extension queue](dfm12-identity-multilingual-extension.md)
retains corrected v4 DA/EN and accepted originals for the other seven existing
languages, with 31,286 new candidate requests toward the cumulative target.
Generation is blocked pending coordination; no GPU, training or active joint
production change is authorized by preparation. Curated DA/EN retention is not
retroactive teacher-audit certification. Existing artifacts and heldouts remain unchanged.

## Multilingual Accepted Target, 2026-09-28

User clarified the end goal: approximately **2000 accepted conversations per
language across all 21 languages**, not 2000 attempts or additional rows atop
each existing corpus. Preserve existing accepted material and top up against
verified per-language counts. DA/EN provide the extended recipe; the original
seven languages are nl, nb, nn, sv, is, fo, pl, and the new twelve are de, fr,
es, it, cs, pt_pt, fi, el, ro, uk, et, ca. Preparation and queue construction
are in progress; this target is not a claim that generation has started.

## Future Comparison GPU Utilization, 2026-09-26

User directive: when all eight GPUs are available, identity checkpoint
comparisons must use all eight, not a single GPU while the others idle.
Distribute independent checkpoint/conversation shards across workers and allow
free workers to take remaining shards. Keep each multi-turn conversation intact
with that checkpoint's generated history. Write separate worker outputs, then
merge by checkpoint/conversation/turn IDs and validate complete, duplicate-free
coverage before semantic review. Preserve prompts, decoding settings and holdout
boundaries. This applies to future comparisons; leave the current comparison
undisturbed. The single-GPU allocation used previously is superseded policy,
not a template for subsequent comparisons.

## Additional 6000-Step CPU Mixture

2026-09-26: user authorized another **6,000 updates**, after the current EMA
full suite, using the same corrected v4 identity data without additions.
CPU preparation is complete at
`data/sampled_dfm11_identity_da_en_next6000steps`. No weights, existing data,
GPU processes or scheduler state were changed. Parent/Harvey owns launch timing.

The unchanged adaptation builder sampled seed **20260930**, 95% DFM11 / 5%
identity by rendered tokens, GBS **262144**, GAS **2**, world **8**. Resume
contract is **step_2881261 to 2887261**, trainer epoch **15**, data alias
`epoch_14 -> epoch_0`, zero batch and row cursors. The launcher must provide an
isolated zero-cursor resume view; checkpoint metadata overrides CLI arguments.

Prepared totals are **1,572,864,583 rendered tokens**, **3,836,966 rows**, and
**1,495,647,234 physically stored tokens**. DFM11 contributes 3,409,714 distinct
rows; DA contributes 213,299 sampled targets from 3,868 unique targets, and EN
213,953 from 3,880. Each identity target appears 55 or 56 times in this mixture,
reusing stored token spans rather than duplicating conversation/source records.
There is no extra repeat-10 multiplier, and target-only supervision is retained.

Packing was independently reconstructed: **6,019 optimizer steps available**,
with row boundary **3,824,362** at the requested 6,000. Prepared identity share
is **5.000012%** of rendered tokens. At the stop boundary there are
**1,563,845,355 nonpadding tokens**, including **77,966,649 identity tokens**
(**4.985573%**). Response tokens at that boundary are **517,372,314 DFM11**,
**17,313,473 DA**, and **12,710,858 EN**, giving **5.484931% identity response
supervision**. Full-prepared response share is 5.484307%.

Build receipt SHA256:
`a7ca26d092333b56d259a00abaff2fde598a637bc02a6ba315e749bc8262b346`.
Metadata SHA256:
`c0371050cfe11ab5f95ede40f23740b6422a040dd09d9ad5e4991e7d60692444`.
The mixture's `identity-lineage.json` records source/output verification,
reconstructed packing, response fractions and repetition counts. Its source
manifest remains the unchanged v4 hash `b750f605...`; heldout and development
data remain excluded. New helper `dfm12/identity_mixture_receipt.py` verifies
the prepared output without editing the pinned corpus/builder, refusing to
overwrite an existing lineage receipt. **31 focused tests passed**, including
the six new receipt/continuation tests and the adaptation/v4 suites.

Reproduction, with fresh output paths and the CPU-only environment prefix:

```bash
python -m dfm12.build_identity_adaptation --base data/sampled_dfm11 --tokenized data/tokenized_identity_corrected_da_en_20260926_v4 --output <fresh-output> --steps 6000 --global-batch 262144 --seed 20260930 --start-step 2881261 --start-checkpoint step_2881261 --data-epoch 14 --gas 2 --world-size 8 --identity-manifest data/dfm12/identity-corrected-da-en-20260926-v4/manifest.json
python -m dfm12.identity_mixture_receipt --output <fresh-output>
```

## Current V4 Correction and CPU Preparation

**2026-09-26: v4 supersedes v3 for the fourth continuation's CPU inputs.**
It is correction-led, not another volume expansion: no new training
conversations were added. All prior artifacts, registry files, and v1-v3
builders/specs remain intact. This is an agent-authored, CPU-validated local
artifact, not human-reviewed, GPU-audited, or evidence of model improvement.

`dfm12/identity_correction.py` and `dfm12/identity_correction.yaml` consume the
sealed v3 corpus, the third semantic assessment, and Tesla's read-only review
at `data/dfm12/identity-v4-readonly-review-20260926-v1/`. That review screened
all 3,951 conversations / 7,749 assistant targets, but is not exhaustive
semantic certification of every original sentence. Its 241 candidates receive
explicit dispositions: 179 broad matches retained, 62 assistant turns corrected.
These include all nine confirmed contradictions, the unsupported roster
addition, 21 unsupported historical comparisons, 21 current-tokenizer scope
issues, seven role ambiguities, and three other history/quantity/sharing issues.
Unsupported claims are distinguished from proven falsehoods.

The runtime binding says **Gemma-4-derived tokenizer and adapted training
template**: vocabulary and merges match the pinned official tokenizer, but
postprocessing and template differ. It does not silently revise the historical
registry or claim byte identity. Corrections retain the distinction between
DFM leadership and training-team leadership, without claiming Kristoffer was
uninvolved, or inventing historical v1 layer dimensions.

734 existing v2/v3 quantitative openers that omitted Mimir now explicitly name
Mimir XL and historical Mimir v1 as their context. No numerical answer is added
to those prompts. Unchanged records retain their IDs; changed records receive
new IDs with exact original/updated record and turn hashes. Corrected assistant
history propagates naturally into every later target when the complete native
messages are retokenized. One full-conversation duplicate created by correction
is removed with its own ledger. The correction ledger records 787 changed
conversations / 796 changed messages before this deduplication.

Artifact: `data/dfm12/identity-corrected-da-en-20260926-v4/`.
Manifest SHA256:
`b750f605d951fc22740d483fe4e913265427b3b711af44fbfc35490c2d3d476b`.

| Language | Training conversations | Assistant targets | Rendered tokens | Response tokens | Unique user questions |
| --- | ---: | ---: | ---: | ---: | ---: |
| DA | 1,969 | 3,868 | 800,964 | 314,959 | 2,225 |
| EN | 1,981 | 3,880 | 625,099 | 231,225 | 2,392 |

Total training render size is **1,426,063 tokens**, with **546,184 response
tokens**. Actual Gemma-template maximum lengths are 790 DA / 525 EN, below
4096. Training turn histograms (1/2/3/4 turns) are DA 969/367/367/266 and
EN 981/367/367/266. The 62 assistant corrections shorten affected inherited
prose without replacing unrelated valid original conversations. Prompt-context
clarifications increase rendered prompt tokens but not response supervision.

Each language has **50 fresh heldout conversations / 70 targets**: 30
single-turn and 20 two-turn. The independent wording shares known facts and
answer banks; it is a diagnostic test, not native-language gold. Both earlier
heldout sets are now development: **100 conversations / 190 targets per
language**, preserved unchanged in
`development/{da,en}/previous-heldout.jsonl.gz`. Evaluation should include these
development regressions alongside fresh `heldout/{da,en}/test.jsonl.gz`, report
them separately, and never treat the failure-informed older set as fresh gold.
No development or heldout records enter tokenization inputs. Exact normalized
cross-split prompt overlap is checked; this is not semantic-leakage detection.

Inspect `metadata/correction-ledger.jsonl.gz`,
`metadata/deduplication-ledger.jsonl.gz`,
`metadata/candidate-dispositions.jsonl.gz`,
`metadata/response-measurements.jsonl.gz`, and `review/corrections.md` for
before/after evidence, dispositions and per-target response lengths. Readable
whole-corpus source views are `review/{da,en}-train.md` and heldout counterparts.

CPU preparation is complete, without a GPU/scheduler/training action:

- Tokenized root: `data/tokenized_identity_corrected_da_en_20260926_v4`;
  exactly two input files, 7,748 targets, zero skips.
- Mixture: `data/sampled_dfm11_identity_da_en_fourth1000steps`;
  seed **20260929**, target-only retained, 95/5 rendered-token allocation.
- Contract: `step_2880261` to **2881261**, trainer epoch **14**, data index
  **13**, fresh batch/row cursors zero, GBS **262144**, GAS **2**, world **8**.
  Parent must use an isolated zero-cursor resume view; checkpoint metadata
  overrides CLI settings. Preparation itself does not change any checkpoint.
- Prepared mixture: **262,144,160 rendered tokens**, 5.0000408% identity,
  **250,462,908 physically stored tokens**, 1,003 packed steps available.
- At the requested 1,000-step boundary: row end **638,617**,
  **260,661,030 nonpadding tokens**, **12,996,007 identity nonpadding tokens**
  (4.985788%). Response supervision is **86,263,965 DFM11**, **2,886,050 DA**,
  **2,119,534 EN**, or **5.484397% identity response tokens**. Rendered-token
  allocation and supervised-response allocation are distinct measures.

Build receipt SHA256:
`71a7b63b3ca02ff1fdee03f830cc6dbc328e47078f560ccc8f04281d4900b6d8`.
Mixture metadata SHA256:
`4565ac978e8ffea88117a8424ec18d54f89bacf29d19c012b9bce44b3f9d1e50`.
`identity-lineage.json` pins these receipts and records response fractions at
the full prepared extent and requested stop. The adaptation builder explicitly
dispatches the v4 manifest verifier; unknown schemas still fail closed.

Commands, using the repository's CPU-only environment prefix:

```bash
python -m dfm12.identity_correction verify --root data/dfm12/identity-corrected-da-en-20260926-v4
# Reproduction only: every output path must be fresh.
python -m dfm12.identity_correction build --output <fresh-v4-root>
python scripts/tokenize_chat_template.py <fresh-v4-root>/inputs --output-dir <fresh-tokenized-root> --tokenizer-path data/dfm11_tokenizer/tokenizer.json --chat-template data/dfm11_tokenizer/chat_template.jinja --max-seq-len 4096 --workers 2
python -m dfm12.identity_correction mixture --root <fresh-v4-root> --tokenized <fresh-tokenized-root> --output <fresh-mixture-root>
```

Final combined validation passed **89 tests** across v4, adaptation and the
unchanged v1/v2/v3 suites. The focused subset passed **25 tests** (11 v4 plus
14 adaptation), covering
all ledger dispositions, original preservation, fail-closed source drift,
deduplication, heldout isolation, multi-turn rendering, response accounting,
runtime wording and epoch-14 continuation. No tokenizer/training/pilot code or
global quality gate was weakened. All mixture output hashes and both languages'
tokenized response totals were independently rechecked; OKF validation returned
zero errors and warnings. Lineage receipt SHA256:
`f240ea1cb486c4f895ca01c4fcc3b425390e2259ba737a3c1d1637af2c44d200`.

## Current V3 Repair and CPU Preparation

**2026-09-26 follow-up: v3 is not cleared for another unchanged continuation.**
Read-only review after the third identity comparison found retained original
targets contradicting the fact registry: EN row 329 names Kristoffer alongside
Peter as training-team lead; EN rows 131 and 435 assign the custom 65,536-token
HRM-Text BPE tokenizer to Mimir v1; DA row 47 adds Kristoffer to the stated
training roster. Row numbers here are zero-based in the sealed v3 input shards.
Inspected token arrays retain these answers, and the sampled mixture repeats
the identified lead/tokenizer targets 9-10 times. No obvious response-mask
failure was found. These findings supersede any inference that retaining all
previously accepted originals guarantees factual consistency.

The user authorized corrected identity supervision and a fourth 1,000-step
continuation. Correct inherited contradictions with a per-row provenance ledger
before tokenization; additions alone are insufficient. In the full third-run
prepared mixture, originals account for 64.94% of identity response tokens,
versus 16.07% for v3 additions (not exact consumed-step fractions). Verify the
next mixture's supervised-response coverage as well as total token share.

**2026-09-26: v3 supersedes v2-r2 as the latest prepared identity corpus.**
V2-r2, v1, their original source files and earlier tokenized/sampled outputs
are preserved. V3 adds **another 500 new training conversations per language**,
retaining both the accepted originals and all earlier 500 v2 additions.
It also creates 50 fresh held-out conversations per language.

Source and builder: `dfm12/identity_repair_expansion.yaml` and
`dfm12/identity_repair_expansion.py`. The failure-informed design reads
`data/dfm12/identity-evaluation-second1000-20260926/reviewer-assessment.md`;
that report is copied and hash-pinned in the new artifact. The facts registry
is unchanged. The user clarification about random initial pretraining versus
checkpoint continuation is separately recorded as authorized context in the
new spec, not silently added to the existing registry.

Dataset: `data/dfm12/identity-repair-da-en-20260926-v3`.
Manifest SHA-256:
`af0b82b1dfa43012893cd54255923cf15fc5fca67627f16efacfcd0fc6f8bbf1`.

| Language | Accepted | Prior additions | New additions | Merged train | Fresh held-out | Old held-out now development |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| DA | 969 | 500 | 500 | 1969 | 50 | 50 |
| EN | 982 | 500 | 500 | 1982 | 50 | 50 |

| Language | New train tokens | Merged train tokens | Fresh held-out tokens | New train max context |
| --- | ---: | ---: | ---: | ---: |
| DA | 155017 | 790938 | 16040 | 407 |
| EN | 123287 | 615737 | 11987 | 312 |

Merged training totals: **3,951 conversations, 7,749 assistant targets,
1,406,675 rendered tokens**. New additions contribute 950 assistant targets
per language; fresh held-out sets contain 95 targets each. All full causal
assistant-target renders pass the raw non-thinking Gemma template check at
4096 without truncation. Fresh held-out context maxima are 389 DA / 279 EN;
merged maxima remain 790 DA / 525 EN.

### Targeted Content and Split Status

The new targets bind concepts explicitly: original from-scratch training is not
Gemma-weight initialization/fine-tuning; Gemma 4 supplies v1's tokenizer/template;
DFM organization leaders are not both training-team leads; 161 counts historical
datasets, not models/people; 16 plus 16 gives 32 layers across two modules, not
32 passes; 2 times 3 plus 2 gives 8 module passes; and historical 4096 denotes
context tokens, not hidden dimensions or batch/epoch size. Roster answers keep
the exact six stated names and distinguish Peter's leadership from membership.
No unsupported CEO/consultant roles or hardware/secrecy explanations are added.

From-scratch targets explicitly concern **original lineage pretraining**.
Checkpoint continuation retains learned weights; it does not randomly reset
them. A conditional synthetic-text QA distinguishes learning from generated
examples from copying the generating model's weights. It does not claim there
was no model-generated data, no Gemma influence, or no distillation.

There are 28 fact-specific request bindings, 50 new training families and 10
fresh held-out families. Per-language new training turn histogram is
**250 / 100 / 100 / 50** for 1/2/3/4-turn conversations; fresh held-out is
**25 / 10 / 10 / 5**. Single-turn variants 0 and 1 preserve direct opening-only
requests; remaining variants change the substantive branch question. Each
target part is one or two sentences. Brief and contrast modes each cover 475
training assistant turns per language. Repetition of natural follow-up wording
within a split is allowed, but full conversations are unique.

Each language has **356 unique normalized new-training user turns**, 78 atomic
questions and 256 assistant texts; fresh held-out has **66 / 38 / 54**.
Maximum repeated-user-turn frequency is 14 in training and 3 in fresh held-out.
Opening-topic counts: from-scratch 100; tokenizer 50; identity 20; organization
40; training team 60; layers/passes 110; historical backpropagation 30;
context 50; dataset quantities 30; scoped uncertainty 10. Full request counts
and repetition histograms are in `manifest.json`.

**The old v2 held-out set is now development data**, because its errors informed
this tuning design. Its rows remain unchanged but are copied separately to
`development/{da,en}/previous-heldout.jsonl.gz` with development provenance;
they are never included in training or tokenization. Fresh held-out user turns
and atomic questions are checked against prior training/development and new
training. New training cannot copy prior held-out/development questions.
These are exact normalized checks, not a claim of semantic independence.
Facts/answer banks are shared; all new rows remain **agent-authored, not
human-reviewed, GPU-audited or native-language gold**.

Native merged rows are under `inputs/`, new additions alone under `curated/`,
fresh held-out under `heldout/`, and readable new conversations under
`review/{da,en}-{train,heldout}.md`. Provenance retains earlier rows and their
IDs, plus new family/variant/fact/derivation references. Verification reconstructs
the merged rows from unchanged v2 training plus the new compiled additions.

### Third Mixture and Resume Contract

Only final v3 `inputs/` was tokenized into
`data/tokenized_identity_repair_da_en_20260926_v3`: **two files, 7,749 targets,
zero skipped targets**. No development, held-out or additions-only file was scanned.

Fresh mixture: `data/sampled_dfm11_identity_da_en_third1000steps`.
Seed **20260928**, 1,000 updates, global batch 262144, GAS 2, world size 8.

| Component | Selected rows | Unique rows | Rendered tokens |
| --- | ---: | ---: | ---: |
| DFM11 replay | 567824 | 567824 | 249037167 |
| DA identity | 36057 | 3868 | 7369895 |
| EN identity | 36169 | 3881 | 5737394 |

Total **262,144,456 rendered tokens**, identity **5.000025%**; compact storage
250,443,842 tokens. Every unique identity target is selected 9 or 10 times;
export repeat-10 metadata is not multiplied in. CPU packing supplies 1,003
optimizer steps; the intended first 1,000 consume 637,912 rows, 260,637,960
nonpadding tokens and 12,995,852 identity nonpadding tokens (**4.986170%**).

Final agreed contract: **resume tag `step_2879261`**, start step **2879261**,
stop **2880261**, trainer **epoch 13**, data index **12**. The fresh corpus has
`epoch_12 -> epoch_0`. Parent must provide an **isolated zero-cursor checkpoint
view** whose metadata retains step 2879261, sets epoch 13 and zeroes batch/row
cursors. Do not use the canonical step sidecar unchanged or rely on CLI cursor
overrides; checkpoint metadata takes precedence. Earlier discussion of an
`epoch_12` checkpoint alias for this run is superseded by this step-tag contract.
This worker created no checkpoint view and changed no scheduler/GPU process.

Data config is `path: data/sampled_dfm11_identity_da_en_third1000steps` with
`target_only: true`; required launch values are `epochs=13`,
`training_total_steps=2880261`, `stop_after_step=2880261` and
`resume_checkpoint_tag=step_2879261`. Parent owns checkpoint view, model/LR
settings, training and evaluation.

The adaptation builder now explicitly dispatches by v2/v3 manifest schema to
the corresponding full verifier; unknown schemas fail closed. Historical
receipts retain their original builder hashes, while new receipts pin the
updated dispatcher. Existing sampled arrays/receipts were not rewritten.

Build receipt SHA-256:
`8e879679483411c7892860f959e8be3cb6651c6dbe1e66651fffb6bd180db09a`.
Mixture metadata SHA-256:
`e041dcc3ae6f3e874dffd952ddae8637399c144323c2f0f7330813f499652e85`.
Both files and all recorded source/output array hashes were rechecked.
`identity-lineage.json` separately links the source manifest, build receipt,
metadata and tokenizer completion; held-out/development exclusion is explicit.

**78 combined tests passed** across repair expansion, adaptation, v2 expansion
and v1 extension. Coverage includes schema dispatch/rejection, exact counts,
polarity, roster/numeric bindings, direct questions, source preservation,
development retirement/leak checks, deterministic rebuild, source/file integrity
and actual full Gemma renders. The v1/v2 artifacts still verify. CPU preparation
is complete; no training, evaluation, upload or W&B was launched here.

```bash
# Already-built final artifact verification:
CUDA_VISIBLE_DEVICES='' /home/ucloud/miniforge3/envs/hrm/bin/python \
  -m dfm12.identity_repair_expansion verify \
  --root data/dfm12/identity-repair-da-en-20260926-v3

# Reproduction only; use fresh output names rather than existing roots:
CUDA_VISIBLE_DEVICES='' /home/ucloud/miniforge3/envs/hrm/bin/python \
  -m dfm12.identity_repair_expansion build --output <fresh-dataset-root>

CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
  /home/ucloud/miniforge3/envs/hrm/bin/python scripts/tokenize_chat_template.py \
  <fresh-dataset-root>/inputs --output-dir <fresh-tokenized-root> \
  --tokenizer-path data/dfm11_tokenizer/tokenizer.json \
  --chat-template data/dfm11_tokenizer/chat_template.jinja --max-seq-len 4096 --workers 2

CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
  /home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.identity_repair_expansion mixture \
  --root <fresh-dataset-root> --tokenized <fresh-tokenized-root> --output <fresh-mixture-root>
```

## Preserved V2 and Continuation Context

### Third Identity Interlude Authorized, 2026-09-26

The user requested another **500 new DA and 500 new EN conversations**,
explicitly including training-from-scratch provenance, followed by another
1,000 XL updates. Preparation retains the earlier accepted originals and v2-r2
additions, uses a fresh 95/5 DFM11/identity mixture, and continues non-reset
weights, optimizer and EMA from `step_2879261` to `step_2880261`. Base LR remains
`1e-5` with `lr_auto=true`, no warmup and no decay; GBS 262144 and GAS 2.
This does not mean reinitializing or training the XL model from scratch.

The earlier heldout answers now inform targeted dataset design and must be
described as development/regression evidence, not fresh heldout generalization.
Prepare 50 new heldout conversations per language, excluded from tokenization.
Focus targets on scratch-trained weights versus Gemma tokenizer/template,
organization versus training-team roles, and layers/passes/context units;
avoid unsupported numerical/history additions and unnecessary fact dumps.

`scripts/schedule_identity_continuation.py` now accepts an optional `campaign`
object with explicit checkpoint roots, job ID, log root and trainer epoch.
The original defaults remain the second interlude. The third interlude uses
trainer epoch 13 / index epoch_12 solely to begin its new sample at row zero;
global optimizer steps remain continuous. Canonical checkpoint metadata is not
edited. Completed identity evaluations with length stops enter manual review
as such, not automatic success; incomplete evaluations still fail closed.
Full evaluation remains conditional on an explicit assessment, and the terminal
barrier releases XXL even if training/evaluation fails or review times out.

**Operational handoff armed:** detached supervisor PID `2773516` is waiting for
fully written XXL `ephemeral_step_663000`; the scheduler stop request is present
while XXL continues to that checkpoint. Specification and launch log are under
`logs/training/dfm12_XL_identity_expanded_3000steps/`. The next identity checkpoint
root is `checkpoints/dfm12/XL-identity-expanded-from-step2879261`. Training has not
started at this handoff snapshot. The supervisor revalidates pins before stopping
XXL, preserves its checkpoint, and uses the existing scheduler rather than a
separate training launcher. Same W&B run: `DFM5/dfm12-xl-identity-da-en-1000`.

The final prepared artifact is `data/dfm12/identity-repair-da-en-20260926-v3`
(manifest `af0b82b1dfa43012893cd54255923cf15fc5fca67627f16efacfcd0fc6f8bbf1`).
It retains earlier rows and adds exactly 500 conversations per language, yielding
1,969 DA and 1,982 EN training conversations, with 50 fresh heldout per language.
Tokenization has 7,749 assistant targets and zero skipped rows. The fresh mixture
`data/sampled_dfm11_identity_da_en_third1000steps` contains 262,144,456 nominal
sampled tokens; its first 1,000 packed updates contain 260,637,960 nonpadding
tokens, including 12,995,852 identity tokens (4.98617%).

The versioned evaluator `scripts/evaluate_dfm12_identity_continuation_v3.py`
passed CPU preflight against the frozen manifest: 16 development regression
questions plus 100 fresh conversations, 206 turns per checkpoint. Previous
heldout is explicitly development-only. It compares non-EMA 2879261 and 2880261
without fact priming, using generated prior assistant turns. The target review
found no blocking issue; it is an agent review, not independent human/native
gold. Future outputs still require semantic assessment. Handoff tests passed
13 cases; corpus preparation reported 78 tests and evaluator review 38 tests.

### Second Identity Continuation Outcome, 2026-09-26

The additional 1,000 updates completed at `step_2879261` in
`checkpoints/dfm12/XL-identity-expanded-from-step2878261`, using the fresh
95/5 mixture and constant base LR `1e-5`. The scheduler resumed XXL from its
preserved `ephemeral_step_661500` after evaluation. The conditional full suite
was not launched.

Comparison artifacts are under
`data/dfm12/identity-evaluation-second1000-20260926/`: `responses.md` contains
all prompts and answers; `reviewer-assessment.md` records the qualitative review.
Both non-EMA checkpoints completed all 16 regression questions and 100 heldout
conversations (206 answer turns each). Length-limited answers fell from 30 to 2.
Direct regression questions improved or retained their core answers, but heldout
conversations introduced material errors about Gemma weight provenance, training
leadership, tokenizer source and architectural/history facts. The assessment is
therefore mixed, not approval of the conditional full evaluation. Lexical anchor
scores are not semantic accuracy. Exit code 4 denotes completed coverage with
length stops, not a model-loading failure; the scheduler recorded it as an
evaluation error and safely released the XXL continuation.

**Superseded by v3 on 2026-09-26: v2-r2 was the latest prepared version.** V1 below remains a
preserved, verifiable historical artifact. The new implementation and source
bank are `dfm12/identity_expansion.py` and `dfm12/identity_expansion.yaml`;
neither v1's builder nor its YAML was changed. V2 adds **500 new training
conversations and 50 held-out conversations per language relative to accepted
originals**, not 500 on top of the earlier 24 additions.

Final root: `data/dfm12/identity-expansion-da-en-20260926-v2-r2`.
Manifest SHA-256:
`28cb1b97c542a25af19128c7b91bc37b24d87a6144dd62e220d10af3705125a4`.

| Language | Accepted originals | New train | Merged train | Held-out | New train tokens | Merged train tokens | Held-out tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DA | 969 | 500 | 1469 | 50 | 175752 | 635921 | 17179 |
| EN | 982 | 500 | 1482 | 50 | 131041 | 492450 | 13067 |

The merged training total is **2,951 conversations, 5,849 assistant targets,
and 1,128,371 rendered tokens**. Each language adds 950 assistant targets;
each held-out split has 95. Maximum new training contexts are 464 DA / 343 EN;
held-out maxima are 435 DA / 328 EN. Merged maxima remain 790 DA / 525 EN.
Every assistant-target context was rendered using the actual raw Gemma template
with thinking disabled, checked against prompt-plus-response tokenization, and
kept below 4096 without truncation. These are render-validation counts, not a
new tokenized training corpus.

### Composition and Diversity

The source bank has 29 fact-specific request/answer bindings, concise/detailed
targets, 50 training prompt families and 10 separately worded held-out families.
Each training family expands into 10 scenarios; each held-out family into 5.
Variants change factual branches and dialogue progression rather than adding
arbitrary numbered prefixes. For single-turn families, variants 0 and 1 ask
only the opening question: variant 0 preserves the exact natural question,
and variant 1 requests explanation. Remaining variants ask an additional
fact-specific question. Multiturn families change requested facts over 2-4 turns.
This is explicitly questionnaire-like compositional coverage, not 500 independently
authored question families or newly established native-language gold.

Per-language training turn histogram: **250 single-turn, 100 two-turn,
100 three-turn, 50 four-turn**. Held-out histogram: **25 / 10 / 10 / 5**.
Training contains **356 unique normalized user turns**, **78 unique atomic
questions**, and 259 unique assistant texts; held-out contains **60 / 32 / 49**.
Repeated natural follow-ups within a split are intentional: maximum user-turn
frequency is 21 in training and 5 in held-out. Full conversations are unique.
The manifest records the complete repetition histogram and per-request counts.
Training answer modes are balanced at 475 concise / 475 detailed assistant turns
per language. No exact normalized held-out turn or atomic-question overlap with
training/originals is permitted. Facts and target answers are deliberately shared;
this is a prompt-family wording holdout, not a held-out-knowledge evaluation.

Opening-topic counts per language: identity 10; namesake 50; creator 30;
leadership 70; full team membership 20; architecture depth 40; cycles 50;
complete architecture 20; current/historical distinction 70; tokenizer 60;
scoped uncertainty 50; limitations 30. Follow-up requests cross these topics.
Targets distinguish organizational leadership from training-team leadership,
tokenizers/templates from Gemma weights, module passes from layer counts,
and unspecified deployment properties from known XL facts.

### Review Correction and Preservation

**Superseded draft:** `data/dfm12/identity-expansion-da-en-20260926-v2`, hash
`860bd455fda9aa40fd806e805ebd910310e29d28f62f7973612211e4424a0af2`,
was retained, not overwritten. Its open-ended tokenizer/context questions
incorrectly received concise answers beginning `No,` / `Nej,`. V2-r2 uses
explicit neutral answer bindings for those questions: five training and three
held-out uses per language. Polar false-premise corrections still begin with
`No,` / `Nej,`. Regression tests check the exact affected counts and polarity.
The draft's source pins now differ from the corrected builder/spec; it is not
the final verified artifact and must not be used for integration.

Final v2-r2 and historical v1 verify successfully. The corrected expansion and
v1 extension suites pass **45 tests**, including malformed/extra YAML field
rejection, exact DA/EN language maps, direct-question exposure, substantive
branch diversity, split separation, natural in-training repetition, actual
rendering of all 1,100 new conversations, deterministic rebuild, source drift,
unsafe paths, unchanged originals, and original-plus-train reconstruction.

### V2 Handoff

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
  /home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.identity_expansion verify \
  --root data/dfm12/identity-expansion-da-en-20260926-v2-r2

# Reproduce only into a fresh root; the final artifact is already materialized.
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
  /home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.identity_expansion build \
  --output data/dfm12/identity-expansion-da-en-20260926-v2-reproduction
```

API: `compile_spec`, `build`, `verify`, and `diversity` in the new module.
Readable full source views are `review/{da,en}-{train,heldout}.md` under the
artifact root. Native merged rows are under `inputs/`; additions alone under
`curated/`; held-out rows under `heldout/`; provenance and frozen YAML/facts
under `metadata/`. The seal pins the builder/helper, sources, original packages,
tokenizer/template, generated files and source metadata; individual provenance
rows include record hashes and selected family, branch, answer-form and fact IDs.

**Isolated integration only:** no active build is changed. The subsequently
authorized CPU continuation preparation below tokenizes only this final root's
`inputs/` subdirectory, never the whole artifact or its `curated/`/`heldout/`
directories. No training,
upload, W&B, GPU process, accepted original, other-language package or published
receipt was changed. New targets are **agent-authored, not human-reviewed or
GPU-audited**. Parent owns any later training policy and central index/log updates.

## Second 1000-Step CPU Preparation

2026-09-26 user authorization: prepare another 1,000 XL updates using a fresh
95% DFM11 / 5% merged DA/EN identity mixture, followed by parent-owned evaluation.
This section records **CPU preparation only**, not a training/eval launch.

Tokenized root: `data/tokenized_identity_expansion_da_en_20260926_v2_r2`.
The existing raw Gemma tokenizer processed exactly the final v2-r2 `inputs/`
directory: **2 files, 5,849 assistant targets, zero skipped targets**, maximum
length 4096, thinking disabled. Counts and token totals match the sealed source:
DA 2,918 targets / 635,921 tokens; EN 2,931 targets / 492,450 tokens.
No held-out/additions-only files were scanned. Tokenization completion and
tokenizer metadata are retained in this new root.

Fresh mixture: `data/sampled_dfm11_identity_da_en_second1000steps`.
The previous 1,000-step corpus and its receipt remain unchanged.

| Component | Selected rows | Unique rows | Rendered tokens |
| --- | ---: | ---: | ---: |
| DFM11 replay | 567295 | 567295 | 249037170 |
| DA identity | 33912 | 2918 | 7386981 |
| EN identity | 34073 | 2931 | 5720360 |

Seed **20260927**, distinct from the first build's 20260926. Total rendered
tokens **262,144,511**; identity fraction **5.000044%**. Compact storage contains
250,165,541 tokens, with repeated rows sharing source spans. All 5,849 unique
identity targets appear 11 or 12 times; the old export's repeat-10 metadata is
not multiplied in. Replay sampling is without replacement within this build;
1,383 replay rows overlap the previous run's independent draw. A different seed
does not imply strict disjointness between runs.

CPU multipack simulation at global batch 262144, GAS 2 and world size 8 provides
**1,003 optimizer steps**. The intended first **1,000** consume 633,110 rows,
260,601,527 nonpadding tokens, and 12,999,205 identity nonpadding tokens:
**4.988154% identity**. Stop at the explicit optimizer-step endpoint rather than
exhausting the extra packing headroom.

### Continuation Contract

`dfm12/build_identity_adaptation.py` now accepts explicit `start_step`,
`start_checkpoint`, `data_epoch`, `seed`, `global_batch`, `gas`, `world_size` and
optional `identity_manifest`, while preserving the first-build defaults.
It validates tag/step/epoch agreement and the final identity manifest, checks
tokenized target counts/tokens and tokenizer/template bytes, and records source
and output file hashes. No scheduler or trainer code changed.

The source `step_2878261` checkpoint metadata records trainer epoch 11,
batch 2000 and row cursor 629152 from the **old** data. `pretrain.py` prefers
checkpoint metadata over CLI resume cursor values. Do not resume that sidecar
unchanged against the fresh corpus.

Agreed parent/Harvey handoff: an **isolated `epoch_11` resume alias** references
the original step-2878261 checkpoint with its optimizer state preserved and
metadata retaining step 2878261. An epoch tag makes the trainer start epoch 12
at row/batch zero. This builder created `epoch_11 -> epoch_0` under the fresh
data root. The source checkpoint/sidecar was not modified, and creating the
isolated resume alias remains the parent's responsibility.

Required data configuration:

```yaml
path: data/sampled_dfm11_identity_da_en_second1000steps
target_only: true
```

Required continuation values: `resume_checkpoint_tag=epoch_11`, an isolated
parent-prepared `resume_checkpoint_path`, `epochs=12`,
`training_total_steps=2879261`, and `stop_after_step=2879261`.
Start optimizer step is **2878261**, exactly **1000 updates** to **2879261**.
The receipt's `requires_isolated_zero_cursor_resume_metadata=false` means an
epoch tag intrinsically resets the cursor; it does **not** mean that the new
alias already exists or that the old step-tag metadata may be reused unchanged.
Parent retains responsibility for model/LR/optimizer settings, launch and eval.

### Receipts and Tests

`data/sampled_dfm11_identity_da_en_second1000steps/build-receipt.json` SHA-256:
`50503524eb84d61a4b7a32b488400b4b86264d84f94ebf0ae296a8e7edd94f1e`.
Final mixture metadata SHA-256:
`a24ef0411a5e9332f07512ffbbc627a4e838f12ee0a246239c7aee79420a615f`.
Receipt pins the final v2-r2 manifest `28cb1b97...`, tokenizer metadata, tokenized
source arrays, selected source-row indices, mixture arrays, labels and builder.
All recorded tokenized-source and mixture-output hashes were independently
rechecked after the build; epoch alias resolution was also checked.

Adaptation tests: **11 passed**, including explicit second-continuation contract,
bad tag/step/epoch rejection, fresh epoch index, independent seed, source
preservation, overwrite refusal, output hashes and actual CPU packing.

Reproduction commands (use fresh output roots; these builds already exist):

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
  /home/ucloud/miniforge3/envs/hrm/bin/python scripts/tokenize_chat_template.py \
  data/dfm12/identity-expansion-da-en-20260926-v2-r2/inputs \
  --output-dir data/tokenized_identity_expansion_da_en_20260926_v2_r2 \
  --tokenizer-path data/dfm11_tokenizer/tokenizer.json \
  --chat-template data/dfm11_tokenizer/chat_template.jinja --max-seq-len 4096 --workers 2

CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
  /home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.build_identity_adaptation \
  --base data/sampled_dfm11 --tokenized data/tokenized_identity_expansion_da_en_20260926_v2_r2 \
  --output data/sampled_dfm11_identity_da_en_second1000steps \
  --steps 1000 --global-batch 262144 --seed 20260927 \
  --start-step 2878261 --start-checkpoint epoch_11 --data-epoch 11 --gas 2 --world-size 8 \
  --identity-manifest data/dfm12/identity-expansion-da-en-20260926-v2-r2/manifest.json
```

## Preserved V1 Record

The sections below describe the original 24-per-language extension, not the
latest 500-per-language expansion above.

## Purpose and Scope

User-authorized follow-up to the four flawed answers in the
[identity smoke and source review](/pages/dfm12-identity-export.md).
This is a new **local** DA/EN dataset version, not a replacement public export.
Accepted originals, other languages, published receipts, active sampled corpus,
training configuration and checkpoints remain unchanged. No GPU, tokenization,
training, upload or W&B operations were performed.

The agent-authored targets use the existing owner-provided facts registry and
the `xl-full-bp` profile: 16 layers in each L/H module, 2 H cycles with 3 L
cycles each, 6 L plus 2 H passes, and current full backpropagation.
They distinguish current settings from historical v1 truncated backpropagation.
Provenance explicitly says `human_reviewed: false`, `gpu_audited: false` and
`native_gold: false`. CPU checks do not establish semantic or native-language gold.
No accepted-audit decisions or published-package receipts are fabricated.

## Curated Content

`dfm12/identity_extension.yaml` contains 24 bilingual training scenarios and
8 bilingual held-out scenarios. Single-turn and two/three-turn conversations
cover uncued namesake questions, creator/name intent switches, complete XL
architecture, known architecture versus unspecified hardware, and leadership.
Brief namesake prompts receive a one-sentence target; other answers can explain
the metaphor without uniformly attaching a consciousness disclaimer.

Explicit English questions include `Who leads DFM?`, `Who leads your training
team?`, and `Is Kristoffer Nielbo training lead?`, with Danish counterparts.
The false premise receives `No,` / `Nej,`: Peter Schneider-Kamp leads the
training team; he and Kristoffer Nielbo lead the organization. This does not
assert that Kristoffer is uninvolved. Team-member answers preserve Jacob Nielsen,
Lukas Galke Poech, Gianluca Barmina, Annemette Brok Pirchert and Kenneth Enevoldsen.
There is no identity-facts system prompt; all training content uses native roles.

## Materialized Artifact

Root: `data/dfm12/identity-extension-da-en-20260926-v1`.

| Language | Original conversations | Added train | Merged train | Held-out |
| --- | ---: | ---: | ---: | ---: |
| DA | 969 | 24 | 993 | 8 |
| EN | 982 | 24 | 1006 | 8 |

| Language | Original tokens | Added tokens | Merged tokens | Held-out tokens | Merged assistant targets | Maximum context |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| DA | 460169 | 4516 | 464685 | 1252 | 2005 | 790 |
| EN | 361409 | 3407 | 364816 | 940 | 2018 | 525 |

Each language adds 37 training assistant targets and 11 held-out targets.
Totals: 1,999 merged conversations, 4,023 assistant targets, 829,501 rendered
training tokens; 16 separate held-out conversations and 2,192 held-out tokens.
Tokens count the full causal context for **each** assistant target, not merely
the final conversation. The current raw Gemma training template is rendered
with thinking disabled; full token length must equal prompt plus response token
length and remain at most 4096. No truncation is allowed. New training maximum
lengths are 287 DA / 199 EN; held-out maxima are 202 DA / 139 EN.

Manifest SHA-256:
`908e1c13fb7e69230f6fafddc30ef3500c3ba1332e7fc333dd6239899db1d3fc`.
Facts SHA-256:
`d81c94652a494d84e9937299964baad5519f150e96bea056ce197d5c95488a71`.
The manifest pins the builder, YAML specification, facts, tokenizer, template,
original manifests, original data and metadata files, plus every owned artifact.
`seal.json` is a reproducibility/integrity checksum, not a signature or review.

Layout:

- `inputs/dfm12-identity-xl-full-bp-{da,en}/train-00000.jsonl.gz`: original native rows, unchanged as records, followed by new training rows.
- `curated/{da,en}/train.jsonl.gz`: additions alone for inspection; do not tokenize these alongside merged inputs.
- `heldout/{da,en}/test.jsonl.gz`: separated evaluation paraphrases, never included under `inputs/`.
- `metadata/provenance.jsonl.gz`: original source-manifest and ordinal mapping, or curated scenario/answer/fact references, split, language, profile and render counters.
- `metadata/identity_extension.yaml`, `metadata/identity_facts.yaml`: frozen source copies.
- `manifest.json`, `seal.json`: own local artifact contract; not the strict accepted public-export schema.

## Validation and Reproduction

The thin builder validates original packages through the existing read-only
export validator before combining them. It rejects duplicate curated groups,
normalized questions, conversations, IDs, invalid fact references and profile
drift. Exact new/original conversation duplicates fail closed; normalized
training-question overlaps are reported, while held-out/original question
overlaps fail closed. Actual build found **zero** such overlaps in either
language. These checks are not a semantic paraphrase-leakage detector.

Held-out groups retain both languages and all turns together. They hold out
question wording/scenarios, **not facts or target answers**: the answer bank is
shared deliberately. They are not prompt examples or training inputs. Do not
claim independent broad-language evaluation or unseen-knowledge generalization.

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
  /home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.identity_extension verify \
  --root data/dfm12/identity-extension-da-en-20260926-v1

# Reproduction only: output must not already exist.
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
  /home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.identity_extension build \
  --output data/dfm12/identity-extension-da-en-20260926-reproduction
```

API: `build(output, exports=..., spec=..., facts=..., metadata=...) -> receipt`,
`verify(root) -> integrity receipt`, and `compile_spec() -> (row, provenance)`
pairs. Existing paths are never overwritten. Identical inputs produce identical
compressed artifacts and manifest hashes. Verification also detects source-pin
drift and unlisted files. Keep this receipt's manifest hash as the external pin.

`tests/test_dfm12_identity_extension.py`: **18 passed**, including actual local
Gemma rendering of all 64 curated conversations and rejection of oversized
input, deterministic rebuild, original preservation, held-out exclusion,
source/artifact drift and direct leadership/verbosity regressions.

## Remaining Integration

Dataset materialization is complete; no additional build run is needed.
Parent reviews the local artifact and chooses any later tokenization/training.
Only pass this artifact's **`inputs/` subdirectory** to
`scripts/tokenize_chat_template.py`, with a fresh tokenized output directory;
never pass the whole artifact root. Package basenames match the existing DA/EN
adaptation builder's input convention. Rows have one physical copy; no new
repeat factor or training weighting is selected here.

The main public training builder requires published export receipts, which this
local artifact intentionally does not invent or bypass. The current
`dfm12/build_identity_adaptation.py` also hardcodes the original epoch-10 start
checkpoint/step; a future continuation from the identity-adapted checkpoint
must set an explicit continuation policy rather than blindly reuse that default.
This extension is not evidence that the smoke failures have been fixed in model
weights. Central wiki index/log registration is handed to the parent coordinator.

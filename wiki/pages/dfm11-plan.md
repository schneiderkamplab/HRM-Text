---
type: Training Data Plan
title: DFM11 Plan
description: Deferred quality repair and task-aware admission plan derived from the completed DFM10 residual audit.
tags: [dfm11, data-quality, filtering, repair, audit, training-data]
status: draft
last_updated: 2026-09-01
confidence: medium
sources:
  - id: magpie-paper
    resource: https://arxiv.org/abs/2406.08464
    title: "Magpie: Alignment Data Synthesis from Scratch by Prompting Aligned LLMs with Nothing"
    author: org:Magpie-Align
  - id: magpie-code
    resource: https://github.com/magpie-align/magpie
    title: Magpie generation and filtering implementation
    author: org:Magpie-Align
  - id: magpie-gemma2-format-reference
    resource: https://huggingface.co/datasets/Magpie-Align/Magpie-Gemma2-Pro-200K-Filtered
    title: Magpie Gemma 2 filtered dataset card and schema reference only
    author: org:Magpie-Align
  - id: fineinstructions-nemotron-card
    resource: https://huggingface.co/datasets/fineinstructions/fineinstructions_nemotron
    title: FineInstructions Nemotron dataset card
    author: org:fineinstructions
  - id: fineinstructions-paper
    resource: https://arxiv.org/abs/2601.22146
    title: "FineInstructions: Scaling Synthetic Instructions to Pre-Training Scale"
    author: org:FineInstructions
  - id: nemotron-cc-paper
    resource: https://arxiv.org/abs/2412.02595
    title: "Nemotron-CC: Transforming Common Crawl into a Refined Long-Horizon Pretraining Dataset"
    author: org:NVIDIA
  - id: common-crawl-terms
    resource: https://commoncrawl.org/terms-of-use
    title: Common Crawl Terms of Use
    author: org:Common-Crawl
---
# DFM11 Plan

## Decision and boundary

DFM10's residual-quality scope is frozen for near-term training, but the final
DFM10 data snapshot is not yet frozen. The outstanding, already-approved
boundary operation is integration of the audited Danish Model Charter package
`dfm10-synthetic-values-model-charter-da`, followed by the authoritative DFM10
union rebuild and resampling. A separate workstream owns that operation. DFM11
work must not duplicate, modify, or race it.

The DFM10 freeze becomes effective only after that integration and resampling
complete and their metadata are validated. The residual-quality findings
completed on 2026-08-31 will not delay this finalization or the ensuing DFM10
training. After the boundary is reached, only a train-blocking integrity defect
such as a missing artifact, corrupt file, or invalid manifest may change the
DFM10 snapshot, and such a correction must be recorded explicitly rather than
presented as quality curation.

DFM11 starts from the exact finalized DFM10 source and sampling manifest, then
applies isolated replacements and exclusions. It must not overwrite DFM10
converted, tokenized, or sampled artifacts. The intended paths are:

- source policy: `config/data/dfm11.yaml` and DFM11-specific filter decisions;
- tokenized union: `data/tokenized_dfm11`;
- sampled corpus: `data/sampled_dfm11`;
- repaired sources: distinct DFM11 names until their admission gates pass.

Before DFM11 work starts, verify the Danish Model Charter receipt and record
hashes and row/token inventories for the resulting final DFM10 config, union
metadata, source inventory, and sampled metadata. This post-resampling snapshot
is the sole DFM11 baseline. It makes the DFM10-to-DFM11 delta reproducible and
prevents repairs from leaking into an already running DFM10 experiment.

## Evidence from DFM10

The completed [DFM10 residual quality audit](dfm10-residual-quality-audit-queue.md)
examined 46,872 exact training representations and found 39,605 usable (84.5%)
with no unresolved judge errors.

| Stratum | Audited | Usable | Main DFM11 concern |
|---|---:|---:|---|
| Sapient packages | 8,500 | 7,059 (83.0%) | Contract-sensitive math judging, QReCC-II corruption, and noisy large families |
| Native tool and agent | 5,900 | 5,589 (94.7%) | Generic judges misclassify valid intermediate tool calls; some real schema/coherence defects remain |
| Folketing error correction | 5,000 | 3,127 (62.5%) | No-op or negligible corrections, residual OCR damage, and truncated targets |
| Borderline Danish | 2,359 | 1,690 (71.6%) | Legacy back-translation grounding, truncation, and instruction/target mismatch |
| Borderline English | 19,113 | 16,287 (85.2%) | Concentrated bad Natural Instructions tasks and contract failures in one-pass SFT sources |
| Completed Mimir/persona packages | 6,000 | 5,853 (97.6%) | Small known-answer or schema-verification tail; no case for regeneration |

The audit is a triage signal, not a universal row-level admission oracle.
OpenMath direct answers failed the generic judge at 42.6%, versus 22.6% for CoT,
partly because the judge expected derivations from a direct-answer contract.
DeepDive intermediate assistant tool calls were similarly judged as incomplete
final responses. DFM11 must use task-aware verification before excluding either
family.

## FineInstructions Nemotron admission

DFM11 adds `fineinstructions/fineinstructions_nemotron` as a fail-closed
English instruction-pretraining candidate. It is not ordinary post-training
SFT: the release contains more than one billion synthetic instruction/answer
pairs (approximately 300B tokens), generated from Nemotron-CC source documents.
The FineInstructions experiments used this representation for pretraining from
scratch and formatted each pair as an instruction and answer.

The pinned revision is
`b1f556ec27529d09602e4dbe49de4263f5ebd068`. The generic downloader retrieves
only its card and snapshot metadata. The full corpus is roughly 1.7TB of
Parquet plus 6.1GB of row-aligned judge scores, so selective materialization is
owned by `scripts/prepare_dfm11_fineinstructions_nemotron.py` and policy is
pinned in `config/data/dfm11_fineinstructions_nemotron.yaml`.

### Initial cap and quality policy

- cap the admitted source at **3.0B Gemma-rendered tokens per DFM11 epoch**;
- use `repeat: 1` and do not compensate for filtering by repetition;
- retain only upstream judge score 5, not the paper's broader score >=4 gate;
- deterministically sample paired data/judge shards across the release;
- materialize approximately 3.45B upstream `synthetic_token_count` tokens, then
  enforce the exact 3.0B cap after Gemma-template tokenization;
- run exact/near deduplication, protected-eval decontamination, context-length
  validation, PII review, and source-copy review before admission.

The 3B cap is deliberately about 3% of a roughly 100B-token DFM epoch: large
enough to test the paper's instruction-pretraining effect without allowing one
English Common-Crawl-derived family to dominate Danish, math/code, native chat,
or agentic supervision. At the card's aggregate average of approximately 244
tokens per row, 3B tokens corresponds to roughly 12.3M rows before downstream
filtering. Revisit the cap only after source-stratified quality and capability
ablations; 5B tokens is the provisional hard ceiling for DFM11.

A local 12-shard sample covering 7,972,982 judge labels found 15.15% score 5,
43.09% score 4, 28.46% score 3, 10.61% score 2, and 2.46% score 1. This is why
the initial gate is score 5. The upstream score remains only a quality signal,
not a privacy, licensing, correctness, or decontamination decision.

### License, provenance, and PII status

Admission remains blocked. The Hugging Face card declares no dataset license.
FineInstructions says the rows derive from Nemotron-CC, which derives from
Common Crawl. Nemotron-CC is distributed under the Common Crawl Terms of Use;
those terms warn that crawled content may remain subject to source-owner terms
and place copyright, privacy, and lawful-use assessment on the user.

This transformation does not remove the underlying concern. FineInstructions
requires generated answers to contain at least 80% excerpts from source
documents, and its paper describes query moderation and benchmark
decontamination but no PII-removal stage. Therefore:

1. do not represent this source as permissively licensed;
2. obtain an explicit project-level copyright/provenance decision;
3. reject obvious emails, phone-like identifiers, IP addresses, credentials,
   addresses, and other personal identifiers, followed by a stratified semantic
   PII audit because regexes cannot reliably identify names or contextual PII;
4. measure long verbatim source spans and domain/source concentration;
5. fail closed if the source-copy and PII audits cannot establish an acceptable
   policy for the intended academic use.

An admitted materialization requires a receipt at
`data/receipts/dfm11_fineinstructions_nemotron_admission.yaml` affirming the
license decision, PII audit, source-copy audit, benchmark decontamination, and
task-quality audit. Review-only pilots remain segregated under `data/review/`:

```bash
python scripts/prepare_dfm11_fineinstructions_nemotron.py inventory
python scripts/prepare_dfm11_fineinstructions_nemotron.py materialize \
  --review-only --max-rows 100000
```

### FineInstructions-seeded multi-turn chats

FineInstructions can seed useful multi-turn generation, but semantic clustering
should control **coverage and sampling**, not mechanically concatenate or order
independent question/answer rows. Similar standalone questions rarely form a
conversation with genuine turn dependencies, and concatenation can combine
incompatible source contexts or repeat copied passages.

Use a hybrid method:

1. embed and cluster accepted score-5 instructions by domain, task, difficulty,
   and intent; cap large clusters and sample a broad seed distribution;
2. use one seed, or at most a few source-compatible seeds sharing provenance,
   to construct a latent conversation plan;
3. ask the pinned Gemma 4 31B teacher to generate a fresh 2-6-turn native chat
   with clarification, follow-up, correction, or elaboration dependencies;
4. do not copy the seed answer into the conversation and do not expose source
   text unless the task explicitly requires grounded context;
5. independently audit every assistant turn for coherence, factual support,
   PII, source reproduction, language, and native Gemma formatting;
6. deduplicate against both FineInstructions and the separate DFM11 Magpie
   corpus, and retain seed IDs and cluster IDs as provenance metadata.

Start with a 20,000-chat pilot and admit at most **100,000-200,000 accepted
English chats** after an ablation. Free, unseeded Gemma generation already
belongs to the bilingual Magpie workstream; the value of FineInstructions here
is coverage guidance, not another route to unconstrained free generation. Do
not translate these chats to manufacture Danish balance. Use native Danish
seeds or the independent Danish Magpie lane for matched Danish coverage.

## Gemma 4 31B Magpie-style chat generation

DFM11 will use the Magpie self-synthesis method, not historical Magpie data.
No rows from `Magpie-Gemma2-Pro-200K-Filtered` or any other released Magpie
corpus are training inputs: those datasets were generated by older teacher
models and are consulted only for method, metadata, and filtering design.

The core Magpie observation is that an aligned model can generate a plausible
user query when decoding starts immediately after its native pre-user template.
The original work generated four million instructions and selected 300,000
high-quality instances; its public pipeline separately generates instructions
and responses, tags quality/difficulty/category/safety/language, and removes
near-duplicates. DFM11 adapts that process to the pinned fresh Gemma 4 31B IT
checkpoint at
`data/models/google/gemma-4-31B-it-fresh-20260604`.

### Language-balanced generation

Do not generate an uncontrolled pool and hope that half is Danish. Use two
independent, symmetric queues with separate seeds, counters, and receipts:

| Lane | Instruction-generation condition | Accepted quota |
|---|---|---:|
| Danish | A minimal native system condition requiring natural Danish, followed by the open native user-turn prefix | 50% |
| English | The equivalent minimal condition requiring natural English, followed by the open native user-turn prefix | 50% |

The condition controls only instruction synthesis. After extracting and
validating the generated user request, generate its assistant response from a
fresh native Gemma 4 conversation containing that user request but no repetitive
language-control system message. The final row therefore remains an ordinary,
self-contained Gemma-native `messages` conversation. Retain the exact
instruction-generation system condition in a separate top-level row field for
provenance and later stratified analysis; do not insert it into `messages`.

Enforce balance after filtering, not before it:

1. over-generate each lane independently and refill only the deficient lane;
2. require both the user request and assistant response to match the lane;
3. use Lingua as a high-confidence deterministic rejection gate, with a
   task-aware exception path for code, formulas, and very short outputs;
4. run an independent semantic language/coherence audit on uncertain rows;
5. stop only when both accepted-row quotas are met;
6. deterministically downsample the larger lane if necessary;
7. report both row balance and rendered-token balance, then adjust DFM11
   sampling weights so this Magpie slice is approximately 50% Danish and 50%
   English by tokens as well as exactly balanced by accepted rows.

Never fill a Danish shortfall by translating accepted English Magpie rows.
Translation would collapse the independently sampled intent distribution and
make the two halves paraphrastic rather than genuinely bilingual.

### Complexity-conditioned lanes

The same instruction-generation system condition may control linguistic
complexity, but keep four dimensions separate in metadata and sampling:

1. linguistic complexity of the user's wording;
2. cognitive difficulty of the requested task;
3. domain-expertise level;
4. requested response length and detail.

For example, a Danish instruction-generation prefix may say:

```text
<bos><|turn>system
Samtalen skal foregå på naturligt dansk. Den næste brugerbesked skal være
formuleret i enkelt, hverdagsnært sprog, men den må gerne stille et fagligt
krævende spørgsmål. Nævn ikke disse instruktioner.<turn|>
<|turn>user
```

Use symmetric English conditions and stable labels such as `accessible`,
`general`, `advanced`, and `specialist`. A provisional within-language mix is
20%, 50%, 20%, and 10%; freeze it only after the bilingual pilot measures
quality, diversity, and response-length effects.

The generation-only condition is removed before response generation. If the
generated user request happens to ask for a particular audience or response
style, Gemma 4 may follow it naturally, but the pipeline must not force response
complexity through a hidden system condition. The response teacher otherwise
chooses its own appropriate style, length, and complexity. Audit each
language-by-user-complexity cell independently and balance accepted rows, not
raw attempts.

### Native generation contract

- Verified locally on 2026-08-31: the pinned fresh Gemma 4 31B IT
  `chat_template.jinja` accepts an initial `system` or `developer` message and
  renders it as `<|turn>system`. Use exactly one initial system message for
  Magpie conditioning; do not inject system messages later in a conversation.
- Derive the pre-user prefix and stop-token IDs from the pinned Gemma 4
  tokenizer/template; do not hard-code a Gemma 2 or stale local template.
- Use raw token/completions generation for the unfinished user turn, stopping
  exactly at the native turn boundary. Reject leaked role/control tokens,
  missing boundaries, empty requests, and malformed Unicode.
- Render response generation through the pinned Gemma 4 native chat template.
- Preserve final data as native `messages`, not ShareGPT `from`/`value` rows.
- Store the exact generation-only condition separately, for example as
  `magpie_system_prompt`, alongside `language_lane` and
  `user_complexity_level`. This field is metadata and is not rendered as a
  training turn.
- Keep each complete rendered conversation within the active DFM11 context
  contract. Do not truncate either side to make a row fit.
- Record model revision, tokenizer hash, template hash, random seed, sampling
  parameters, lane, generation server version, and parent IDs in every row.

### Diversity and quality pipeline

Generate with a calibrated mixture of instruction temperatures rather than one
fixed decoding configuration. Select the final mixture only after a 10,000-row
pilot per language. Response temperature may be lower than instruction
temperature because intent diversity comes primarily from the generated user
turn.

Apply, in order:

1. structural, boundary, length, language, and special-token validation;
2. exact and normalized deduplication within and across languages;
3. embedding-neighbor deduplication against Magpie candidates, final DFM10
   instructions, and protected evaluation prompts;
4. intent, task-category, difficulty, safety, and required-knowledge tagging;
5. category-aware caps so generic advice and simple information questions do
   not dominate math, code, reasoning, writing, editing, planning, and Danish
   knowledge requests;
6. independent instruction-quality and response-coherence auditing;
7. stricter task-aware verification for math, code, exact-format, and factual
   claims;
8. a final stratified human-readable sample report before admission.

The initial production target is one million accepted conversations, 500,000
per language, subject to the pilot demonstrating sufficient diversity and
quality. Extend a calibrated subset into native multi-turn conversations of
2-6 user/assistant exchanges while preserving the same language and context
limit. Audit every supervised assistant turn and retain the complete native
history; do not flatten prior assistant turns into user text.

Based on observed local Gemma 4 31B throughput, a 20,000-row bilingual pilot is
roughly 4-12 B200 GPU-hours. One million accepted rows will likely require
1.5-3 million raw candidates after filtering and approximately 300-700 B200
GPU-hours for instruction generation, response generation, audit, retries, and
tail handling, or about two to five days wall time on eight B200s. Re-estimate
after the pilot rather than treating this range as a quota commitment.

### Implementation ownership

Implemented on 2026-08-31 as the reusable, self-contained Git submodule
`koolbardi`, with its own intended remote at
`https://github.com/schneiderkamplab/koolbardi.git`. It is not named after a
specific DFM version: DFM11 is its first consumer, but bilingual
self-synthesis, auditing, and dataset publication remain usable by later data
versions.

The upstream MIT-licensed code is checked out at commit `b734a368` under the
parent repository's ignored `external/magpie` path as a behavioral reference.
That checkout is deliberately not a submodule, dependency, import, vendored
component, or part of Koolbardi's history. The production implementation does
not use upstream's model-specific shell scripts, older serving assumptions,
notebook filters, or ShareGPT conversion path.

The intended repository structure is:

```text
koolbardi/
  README.md
  pyproject.toml
  src/koolbardi/
  configs/
  scripts/
  tests/
```

Runtime artifacts remain outside the source package under `data/koolbardi/`
and `logs/koolbardi/`. The initial implementation provides typed Pydantic/YAML
configuration, SQLite WAL `BEGIN IMMEDIATE` shard claims, full-shard retries,
atomic JSONL replacement, separate instruction/response/audit phases, native
template derivation, per-language post-audit quotas, deterministic language and
structure gates, semantic auditing, exact deduplication, native `messages`
output, token-limit rejection, and machine-readable receipts. Pilot and
provisional production configs target 10,000 and 500,000 accepted rows per
language respectively. Embedding-neighbor deduplication, protected-eval
matching, category-aware caps, richer task verifiers, and publication upload
remain admission work after the pilot; the current finalizer must not be
represented as completing those later gates.

## Workstreams

### 1. Folketing error correction

Keep DFM10's denoising, span-filling, and prefix-continuation families
unchanged. Rebuild only error correction with deterministic gates that reject:

- normalized source/target identity and negligible edits;
- targets retaining a high density of obvious OCR corruption;
- truncated or structurally incomplete targets;
- transformations that introduce corruption or lose substantive source text.

Re-audit 5,000 stratified final examples. Admit the DFM11 replacement only if
at least 90% are usable, normalized no-ops are below 1%, truncation is below
0.5%, and no source stratum has a hidden systematic failure. Do not regenerate
all 3.1M rows. Estimated cost: 4-12 engineering/CPU hours and 0.2-0.8 B200
GPU-hours. Full regeneration would cost roughly 780-1,550 B200 GPU-hours and is
out of scope unless a later experiment demonstrates exceptional marginal value.

### 2. Natural Instructions task selection

Convert the residual audit into a task-level policy rather than a global row
filter:

- exclude the 48 tasks with at least 50% sampled failures;
- re-audit the 74 tasks in the 25-49% band at 100 rows per task;
- retain cleaner tasks unless task-aware validation contradicts the generic
  judgment;
- preserve task definitions and expected output contracts in every audit.

Admission requires at least 85% usable examples per retained task, no systemic
prompt/target inversion, and exact validators for tasks with computable labels.
Estimated cost: 2-4 engineering hours and 0.2-0.8 B200 GPU-hours.

### 3. Legacy Danish back-translation cleanup

Retire legacy Tidsskrift BT, EUR-Lex BT/summary, and DOAB BT where grounded
replacements already provide the intended capability. Apply deterministic
completion and contract filters to DynaWord BT. Verify Kænguruen and Multi-Zebra
against their known answers rather than relying on free-form judging.

Each retained family must reach at least 90% usable under a task-aware delta
audit. Small sources that cannot meet the gate should be omitted rather than
regenerated. Estimated cost: 2-4 engineering hours and 0.2-1.0 B200 GPU-hours.

### 4. Native tool and agent trajectories

Re-audit DeepDive and repaired DOLCI with a trajectory-aware representation
that identifies whether the supervised assistant turn is an intermediate tool
call or a final natural-language response. The audit should see enough suffix
metadata to establish that an intermediate call receives a matching tool result
and eventually reaches a valid terminal answer, without training on future
turns in the prompt.

Native schema, call/result pairing, tool-name resolution, and JSON validity are
deterministic gates. Generic semantic judgment is secondary. Admission requires
100% structural validity and at least 90% usable sampled trajectories. Estimated
cost: 3-6 engineering hours and 0.4-1.6 B200 GPU-hours.

### 5. Sapient math and dialogue families

Audit math under separate `direct` and `cot` contracts:

- direct targets may be concise but must match the verified expected answer;
- CoT targets require coherent reasoning and exactly one canonical final answer;
- symbolic/final-answer verification remains authoritative where available;
- PRM or LLM judgments assess reasoning quality, not direct-answer verbosity.

Run a full task-aware audit of the small repaired QReCC-II family and drop it if
its observed 47% defect rate persists. For AMPS Mathematica, DMMath, FLAN
dialogue, and other very large families, identify defective task strata and
reduce caps or exclude strata rather than attempting wholesale regeneration.
Estimated cost: 4-8 engineering hours and 2-8 B200 GPU-hours for stratified
audits. Any proposal for full-family LLM auditing requires a separate compute
budget and expected-value argument.

### 6. Remaining one-pass English sources

Add task-specific deterministic checks for ASSET, IF-SFT, AESLC, CoEdIT, Tulu
algebra, TextbookReasoning, regular QReCC, and related retained sources. Re-audit
only rejected or borderline strata. Prefer dropping malformed rows to rewriting
authentic targets. Estimated cost: 4-8 engineering hours and 1-4 B200 GPU-hours.

### 7. Mimir and persona verification tail

Use known answers and structural validators for answer-contract calibration,
DROP, event/coreference, and IFEval. Preserve Danish persona chats unless a
deterministic structural issue is found. Their 97.6% aggregate usability does
not justify broad regeneration. Estimated cost: 2-4 engineering hours and
0.2-1.0 B200 GPU-hours.

## Execution sequence

1. Wait for the owning workstream to integrate
   `dfm10-synthetic-values-model-charter-da`, rebuild the union as needed, and
   finish authoritative DFM10 resampling.
2. Validate and fingerprint that post-Model-Charter DFM10 snapshot.
3. Run the 20,000-row bilingual Gemma 4 31B Magpie pilot and freeze its
   generation, language-control, metadata, and filtering contracts.
4. Implement CPU-only source/task filters and produce a proposed DFM11 delta.
5. Run task-aware audits only for strata that cannot be decided
   deterministically.
6. Run Magpie production and materialize repairs under separate names;
   validate schema, provenance,
   deduplication, context length, and Gemma-native formatting.
7. Build `data/tokenized_dfm11` without modifying the DFM10 union.
8. Produce row/token deltas by source and category before assigning repeats or
   caps.
9. Sample a DFM11 pilot and compare source balance against DFM10.
10. Run format, tool-use, math-contract, Danish-language, and memorization smoke
   checks before full sampling.
11. Sample the intended epochs only after all admission receipts and the final
   DFM10-to-DFM11 delta report pass.

## Budget and stop conditions

The minimum practical DFM11 cleanup is workstreams 1-4 and 7: approximately
one to two engineering days and 1-5 B200 GPU-hours, excluding filesystem-heavy
token-tree rebuilding and sampling. The complete plan is approximately three
to five engineering days and 4-15 B200 GPU-hours if the targeted audits confirm
that deterministic filtering is sufficient. Magpie generation is a separate
major production budget: initially 4-12 B200 GPU-hours for the pilot and an
estimated 300-700 B200 GPU-hours for the proposed one-million-row corpus.

Stop and reconsider a workstream when:

- repair requires broad synthetic rewriting without retained provenance;
- projected generation exceeds 100 B200 GPU-hours without a measured capability
  benefit;
- a task-aware audit shows that the generic residual judge produced most of
  the apparent failures;
- the source contributes too few unique tokens to justify repair;
- the replacement worsens source diversity or creates benchmark contamination.

## DFM10 non-regression rule

Before the boundary, DFM11 work waits and does not inspect transient resampling
outputs as its baseline. After the Danish Model Charter integration and
resampling receipts are complete, DFM11 may read and fingerprint DFM10
artifacts but must not mutate them. DFM10 training proceeds from that finalized
snapshot while DFM11 curation is a separate successor effort. Any later
comparison must report both the exact data delta and whether observed changes
come from filtering, replacement, resampling, or additional training tokens.

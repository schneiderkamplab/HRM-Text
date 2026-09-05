---
type: Training Data Plan
title: DFM11 FineInstructions Grounded Chats
description: Balanced bilingual grounded-chat generation, salvage, finalization, and extension policy for DFM11.
tags: [dfm11, fineinstructions, grounded-chat, synthetic-data, bilingual]
status: stable
last_updated: 2026-09-04
confidence: high
---
# DFM11 FineInstructions Grounded Chats

## Controlled interaction modes

The English FineInstructions campaign retains its first 183,978 accepted chats
unchanged. For the remaining accepted pairs, the generator applies a seeded,
restart-stable, balanced cycle over 20 interaction modes adapted from
Koolbardi's documented ontology. The implementation is owned by the
FineInstructions submodule and has no Koolbardi runtime dependency. Newly
accepted rows retain mode metadata and must pass an explicit mode-adherence
score in addition to the existing grounding and quality gates. Modes that act
on supplied material may use the preceding answer or text actually embedded in
the follow-up, never the hidden grounding document.

Schema-constrained output that reaches its token cap is salvaged only at safe
boundaries: retain fully decoded message objects, discard a dangling user or
partial message, and remove complete trailing exchanges until the rendered
conversation fits 3,900 tokens. Never synthesize missing closing text.

The shared command supports explicit Danish generation with localized mode
labels and the identical salvage/audit contract. The current automatic Danish
handoff ends after helper-model distillation; a later Danish production
pair/chat launcher must select
`--language da --controlled-interaction-modes --balance-interaction-modes`.

## Balanced releases and extension

The release target is 500,000 rows per language. English preserves its 183,978
legacy chats and balances the remaining 316,022 selected rows over all 20
modes. Generation uses per-mode accepted quotas, while deterministic
finalization writes a named immutable release and retains all accepted surplus.

Later extensions raise the quotas under the same seed and pair ordering and
write a new release, without mutating the 500K snapshot. Danish helper-model
distillation remains unchanged; its later production stage should use the same
500K per-mode quota contract over source-balanced grounding candidates.

Deficit-filling passes skip unresolved pairs assigned to already-complete modes
before making model requests. Assignment remains deterministic, and accepted
surplus from bounded in-flight work stays in the append-only ledger.

The English launcher parameterizes both the target and release name, and uses
target-specific generation/finalization markers. This makes later balanced
extensions resumable without deleting the immutable 500K release or replaying
already accepted pair IDs. The initial release uses:

```bash
bash fineinstructions/scripts/run_dfm11_english_1m.sh
```

A later extension can use, for example:

```bash
CHAT_TARGET=650000 \
RELEASE_NAME=english-650k-balanced-v1 \
bash fineinstructions/scripts/run_dfm11_english_1m.sh
```

Generate additional grounded pairs before permitting multiple chat variants
from one pair. Keep every release immutable and retain the append-only accepted
ledger so larger balanced releases remain reproducible.

## English 500K release state

Verified on 2026-09-04: the immutable English release is complete at
`data/fineinstructions/dfm11-english-1m/releases/english-500k-balanced-v1`.
It contains five 100,000-row pair shards and five corresponding 100,000-row
chat shards. The receipt records exactly 183,978 preserved uncontrolled chats
plus 316,022 controlled chats at exact 15,801/15,802 mode quotas. Pair IDs and
chat `pair_id` values match in every corresponding row.

Superseded on 2026-09-04: the integration and upload prerequisites described
above are complete. The immutable campaign release remains unchanged. A
portable package was generated at
`exports_dfm11/dfm11-fineinstructions-en` and uploaded as
`schneiderkamplab/dfm11-fineinstructions-en` at revision
`80f44dfc3cbc0ac8d6e219cc65bee4275db27414`. Its `pairs` and `chats`
configurations each contain exactly 500,000 rows in five deterministic gzip
JSONL shards. Absolute provenance paths were replaced by stable
`source_id/basename` references; stable source revisions and row/window
coordinates remain. An aligned selection map identifies legacy versus
controlled rows and controlled interaction modes without requiring the private
campaign ledger. The package manifest records SHA-256 and byte size for every
shard. The credential-pattern review found no HF, W&B, AWS, or
private-key strings; apparent `sk-...` matches were ordinary hyphenated prose
and URL slugs.

## Legacy versus controlled-chat quality

A complete release scan on 2026-09-04 compared the 183,978 preserved legacy
chats with the 316,022 controlled-mode chats:

| Measure | Legacy | Controlled |
|---|---:|---:|
| Mean rendered tokens | 1,087.6 | 1,133.3 |
| Exact repeated turn text | 1.62% | 0.55% |
| Any assistant turn under five words | 0.31% | 0.52% |
| Four-message conversations | 0.42% | 45.99% |
| Six-message conversations | 52.37% | 47.79% |
| Eight-or-more-message conversations | 47.21% | 6.22% |

The controlled slice is better for task diversity and exact-turn repetition:
all 20 modes have exact quotas, sampled follow-ups are more purposeful, and
verbatim repeated turns are about one third as frequent. It is not established
as uniformly better semantic data. It inherits the original pair exchange,
including awkward prompts and source artifacts, and is materially shallower as
multi-turn supervision because almost half of its rows contain only one new
user/assistant exchange.

Accepted audit fields cannot resolve this comparison: all shared quality means
round to 5.0 in both slices, and the controlled mode-adherence mean is 4.9987.
Generation and audit are separate requests to the same Gemma 4 checkpoint, so
their errors may be correlated. Most non-empty complaint fields are the literal
string `none`; excluding those leaves real criticism in roughly 0.1% of the
controlled rows. Before upload or DFM11 admission, run a model-independent,
stratified audit by source, mode, and conversation depth, with special checks
for malformed initial exchanges, truncated final prose, source leakage, and
whether the follow-up genuinely depends on prior turns.

## Proposed DFM11 admission mix

Pending project approval and the independent audit, use the conversations as
the primary training artifact rather than training on every pair and its chat:

| Slice | Proposed per-epoch admission | Reason |
|---|---:|---|
| Controlled chats | All 316,022, repeat 1 | Exact 20-mode breadth and the strongest marginal instruction-following value |
| Legacy chats | 100,000 source-balanced rows, repeat 1 | Retain deeper multi-turn and reading-comprehension behavior without allowing the legacy concentration to dominate |
| Pairs represented by admitted chats | Exclude | Their complete user/assistant exchange already begins the chat, so inclusion would duplicate supervision |
| Other accepted pairs | Initially exclude; optional 50,000-100,000 source/task-balanced ablation, repeat 1 | They can add single-turn coverage but are not the distinctive value of this artifact and inherit the same source/prompt defects |

The approved chat-only selection contributes 465,175,486 release-rendered
tokens: 358,143,555 controlled and 107,031,931 legacy. Preserve all 500,000
release rows on the Hub even though the initial DFM11 training selection uses a
deterministic 100,000-row legacy subset. Do not repeat any slice. Admit optional
pair-only rows only from pair IDs absent from the admitted chat set, and compare
their marginal validation effect before expanding them.

## DFM11 integration state

The approved selection is materialized under
`data/converted_dfm11/fineinstructions_english` as two independently named
prefixes. Controlled uses all 316,022 chats. Legacy uses a deterministic
source-balanced 100,000-row sample: all 7,276 available Project Gutenberg
legacy chats and 10,302-10,303 rows from each of the other nine families. The
selection seed is 11031. No represented pair rows are staged.

The final Gemma 4 native-template tokenization completed in 279.8 seconds with eight CPU
workers and a 4,096-token limit. It produced nine tasks, 1,184,450 supervised
assistant targets, zero overlength skips, and 1,033,994,750 stored tokens:

| Prefix | Chats | Assistant targets | Stored tokens | Repeat |
|---|---:|---:|---:|---:|
| `dfm11-fineinstructions-en-controlled__` | 316,022 | 835,770 | 737,680,897 | 1 |
| `dfm11-fineinstructions-en-legacy-balanced__` | 100,000 | 348,680 | 296,313,853 | 1 |

The task arrays are present in `data/tokenized_dfm11_additions`, and both
repeat-one rules are at the top of `data_io/prefix_config_dfm11.yaml`. The
source-specific policy and pinned Hub revision live in
`config/data/dfm11_fineinstructions_english.yaml`.

The aggregate `data/tokenized_dfm11` union could not be rebuilt on the current
host because its inherited `data/tokenized_dfm10/tokenizer_info.json` base is
not present. `scripts/build_tokenized_dfm11_tree.py --force` failed immediately
on that missing prerequisite without modifying the completed addition. Rebuild
the union after transferring or recreating the DFM10 tokenized base; sampling
must wait for that complete union rather than silently sampling additions only.

The preparation command is restart-safe with `--force` and leaves the immutable
release untouched:

```bash
python scripts/prepare_dfm11_fineinstructions_english.py --force
python scripts/tokenize_chat_template.py \
  data/converted_dfm11/fineinstructions_english \
  -o data/tokenized_dfm11_additions \
  --tokenizer-path ../brainsurgery/models/gemma4_31b/tokenizer.json \
  --chat-template data_io/chat_templates/gemma4_native_chat.jinja \
  --max-seq-len 4096 --workers 8 --force
```

## Danish distillation recovery

On 2026-09-04, four-way Danish retrieval completed with 499,797 unique
candidates, 203 below the original hard minimum of 500,000. This caused the
automatic handoff to exit and retry while GPUs 4-7 were idle; the subsequent
`no managed state` messages were harmless server-cleanup output rather than the
failure itself. The retrieval gate is now 499,000. The downstream requirement
of 100,000 accepted instantiator examples is unchanged.

Superseded later on 2026-09-04: passing the retrieval-count gate did not make
the silver set viable. Gemma labeled 129,612 of 130,000 generated
template/document rows incompatible. The subsequent independent audit accepted
only 14 of its first 8,192 decisions, so it could not possibly reach the
100,000-row target. The automatic handoff was stopped with `HANDOFF_STOP`, and
only its exact managed audit and vLLM processes were terminated. Preserve the
generated ledgers for diagnosis, but do not resume the audit or train the
instantiator from this set.

The observed failure is consistent with the implementation having skipped the
planned Danish retrieval qualification: document-description silver labels,
hard-positive/negative calibration, and a controlled comparison before deciding
whether BGE-M3 needs Danish fine-tuning. Resolve and smoke-test that stage before
regenerating instantiator silver labels. An all-stage ETA is undefined until a
qualification demonstrates a compatibility yield sufficient for 100,000
positives plus at most 5% genuine incompatible examples.

Two source-balanced 2,000-document qualifications then isolated the bottleneck.
Selecting the six highest-scoring templates from the 50,000-row silver bank
produced 27 positives among 6,004 valid teacher labels (0.45%) and covered only
1.50% of documents. Retrieving from teacher-written document capability
descriptions produced 46 positives among 5,969 labels (0.77%) and covered 2.23%
of documents. Both failed closed and their managed servers exited.

The decisive omission was the production templating pass: the published method
trains on roughly 50,000 silver templates and then templatizes a much larger
query corpus, whereas the first Danish launcher indexed the 50,000 training
labels directly. The corrected resumable path prepares 533,900 source-balanced
production queries, including 500,000 from the modernized Danish OpenHermes
corpus; retrains the 2B templatizer with best-checkpoint selection and early
stopping; materializes a 500,000-template production bank; and qualifies that
bank before full retrieval. A first recovery attempt using eight examples per
device OOMed after 12 optimizer steps when Transformers upcast the
full-vocabulary logits to FP32, peaking near 168 GiB on a B200. Superseded on
2026-09-04: the stable setting is four examples per device with two-step
accumulation on four GPUs. It preserves the original effective global batch of
32 and retained at least 47 GiB of headroom through the initial variable-length
training batches.

Generation and audit now count compatible positives and genuine incompatible
negatives independently. Production silver targets are 130,000 positive plus
6,500 negative generated labels and 100,000 positive plus 5,000 negative
audited labels. Audit scores classification correctness rather than literal
pair compatibility for negative labels, and terminal decisions are not retried.

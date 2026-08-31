---
type: Dataset Integration Record
title: DFM10 Open Grounded Chats
description: Production design and execution state for Danish Wikipedia and OpenStax multi-turn grounded chat data.
tags: [dfm10, danish, english, wikipedia, openstax, multi-turn, grounded-sft]
status: stable
last_updated: 2026-08-30
confidence: high
---
# DFM10 Open Grounded Chats

## Targets And Training Semantics

DFM10 adds two independently generated and audited multi-turn corpora:

| Corpus | Grounding | Candidate chats | Hard minimum accepted chats | Hard minimum supervised assistant turns |
| --- | --- | ---: | ---: | ---: |
| `dfm10-danish-wikipedia-open-chats` | 50,000 deterministically sampled Danish Wikipedia articles | 50,000 | 25,000 | 150,000 |
| `dfm10-openstax-open-chats` | 20,047 verified passages from 61 immutable OpenStax CC BY 4.0 artifacts, each viewed through eight substantive pedagogical lenses | 160,376 | 80,000 | 500,000 |

Each accepted chat has 2--10 student/assistant exchanges and must fit the
4,096-token Gemma 4 chat contract. `scripts/tokenize_chat_template.py` emits
one supervised training example per assistant reply, retaining every preceding
turn as context. The hard gates therefore count assistant turns, not JSONL rows
or conversations. Generation targets 5--7 exchanges per chat to retain enough
margin for audit rejection, while 2--10 remains the validity boundary. Both
sources have sampling repeat one.

The eight OpenStax lenses cover conceptual orientation, mechanisms,
misconceptions, application/transfer, comparison and limits, worked problem
solving where supported, evidence and assumptions, and student teach-back.
They are distinct learning objectives rather than superficial prompt
paraphrases.

## Provenance And Rights

The Danish source is
`danish-foundation-models/danish-dynaword/wikipedia`. The request builder keeps
the DynaWord row identity and dates but conservatively records Wikimedia
CC BY-SA 4.0 and an article URL/title attribution instead of relying on the
collection-wide CC0 label. List, category, template, portal, and discussion
pages are excluded; reference tails are removed before chunking.

The English source is the verified local inventory at
`data/mimir_grounded_500k/openstax_cc_by/passages.jsonl`. Every request retains
the book identity, passage and artifact hashes, immutable reference, evidence
URL, source URL, attribution, and CC BY 4.0 declaration. A missing immutable
reference or different licence fails preparation.

## Production Pipeline

The prepared manifest has exactly 50,000 Wikipedia requests in 128 atomic
shards and 160,376 OpenStax requests in 256 atomic shards. Preparation is:

```bash
python scripts/prepare_dfm10_open_grounded_chats.py
```

The resumable production runner is
`scripts/run_dfm10_open_grounded_chats_8gpu.sh`. It waits for the active
Tidsskrift campaign lock and for all eight GPUs to be free, then starts one
Gemma 4 31B server per GPU. Generation and independent audit use different
prompts, concurrency 64, and up to four row attempts. A shard may close after
98% of its requests have both generated and audited successfully; terminal
transport or malformed-output failures are excluded rather than admitted.
The global accepted-chat and assistant-turn gates remain mandatory. Atomic
done markers prevent duplicate completed work. The runner builds the final JSONL packages,
stages their Hugging Face exports, tokenizes with 16 CPU workers, and rebuilds
the DFM10 tokenized union only after all shards and hard size gates pass.

The final source and tokenized paths are:

- `data/dfm10_danish_wikipedia_open_chats_source` and
  `data/tokenized_dfm10_danish_wikipedia_open_chats`;
- `data/dfm10_openstax_open_chats_source` and
  `data/tokenized_dfm10_openstax_open_chats`.

## Production Status, 2026-08-30

Danish Wikipedia generation and audit are complete across all 128 request
shards. The accepted set currently contains 49,787 chats and 261,588 supervised
assistant turns, comfortably above both hard gates. Final JSONL materialization,
Hugging Face package staging, Gemma 4 tokenization, tokenized-union activation,
and DFM10 epoch resampling remain pending. The shared runner performs its
postprocessing only after OpenStax generation/audit finishes; therefore the
completed Wikipedia shards are stable but not yet represented in
`data/tokenized_dfm10` or existing `data/sampled_dfm10` epochs.

The queued campaign must not disturb an active generation/audit workload. Its
detached bootstrap log is `logs/dfm10_open_grounded_chats_bootstrap.log`; the
timestamped operational log path is written to
`data/dfm10_open_grounded_chats/current_run_log_root.txt` after startup.

**Superseded later on 2026-08-30:** Danish Wikipedia finalization produced a
49,787-row package with 261,588 supervised assistant turns. Its full-row
validator passes, and the package was uploaded as
`schneiderkamplab/dfm10-danish-wikipedia-open-chats`. Remote revision
`5cf6607200e6add40f01844037aeb6b2082cc7b2` contains all six expected files;
the 66,227,864-byte data shard matches the local SHA-256 manifest. Tokenization
is active with 16 workers. Tokenized-union activation and DFM10 epoch
resampling remain pending, and the OpenStax generation/audit campaign continues
independently.

**Current state later on 2026-08-30:** The first tokenization attempt used the
legacy 65,536-entry HRM tokenizer and was rejected before union construction
because DFM10 uses the 262,144-entry Gemma tokenizer. The source was rebuilt
and retokenized with
`/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json`. The corrected output
contains 261,588 examples, exactly one for every accepted assistant turn,
with 213,380,681 tokens: 195,660,928 prompt tokens and 17,719,753 supervised
response tokens. No examples were skipped. The canonical output is active in
`data/tokenized_dfm10` through the
`danish_wikipedia_open_chats.jsonl` symlink, at sampling repeat one. Existing
sampled DFM10 epochs still predate this activation and must be regenerated to
include it.

**Campaign completion later on 2026-08-30:** All 384 generation/audit shards
completed with zero failed shards. OpenStax retained 158,605 chats, 847,838
supervised assistant turns, and 245,295,063 rendered full-chat tokens. Canonical
per-assistant-turn tokenization produced 847,838 examples and 1,157,232,804
tokens with zero skips. Both upload packages pass complete row recreation and
both sources are active in the 15,721-task tokenized DFM10 union. The Danish
Wikipedia package is uploaded; OpenStax is staged as `ready_for_upload`.

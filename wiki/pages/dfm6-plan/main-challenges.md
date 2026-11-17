---
type: Plan Record
title: Main Challenges
description: 'Part of DFM6 Plan: Main Challenges.'
tags:
- dfm6
- data
- training
- evaluation
status: stable
last_updated: 2026-10-22
confidence: high
part_of: /pages/dfm6-plan.md
---
# Main Challenges

Part of [DFM6 Plan](/pages/dfm6-plan.md).

## Tokenizer Migration
Changing the tokenizer is not a cosmetic swap. Existing DFM5 tokenized data and checkpoints are not directly compatible with a new vocabulary and special-token layout.

Plan:

- Verify the exact Gemma 4 tokenizer artifact, license, vocabulary size, special tokens, and chat-template behavior before conversion.
- Update model config and embedding/output-head dimensions to the new vocabulary size.
- Rebuild tokenized and sampled DFM6 artifacts from source.
- Do not mix old tokenizer outputs with Gemma-tokenized outputs.
- Treat DFM6 as a fresh-tokenizer training run unless a deliberate upcycling/retokenization experiment is designed separately.

Local inspection on 2026-06-18:

- `/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json` and
  `/work/dfm/brainsurgery/models/gemma4_26b_a4b/tokenizer.json` both expose
  `262144` tokenizer entries.
- Important special tokens are present: `<bos>`, `<eos>`, `<pad>`, `<|turn>`,
  `<turn|>`, `<|tool>`, `<tool|>`, `<|tool_call>`, `<tool_call|>`,
  `<|tool_response>`, `<tool_response|>`, `<|think|>`, `<|channel>`, and
  `<channel|>`.
- The local `tokenizer_config.json` files have `chat_template: null`, so DFM6
  must explicitly provide the template instead of relying on the tokenizer
  snapshot to carry it.

Confidence: high from direct local JSON inspection.

## Chat Template Consistency
The tokenizer/template change affects data conversion, inference, eval serving, and export.

Plan:

- Add one canonical renderer for Gemma-template instruction rows.
- Apply it uniformly to original Sapient-style rows, DFM rows, post-training rows, synthetic rows, and tool-calling rows.
- Audit hard-coded tokenizer paths, BOS/EOS handling, stop tokens, and chat delimiters in conversion, sampling metadata, serving, export, and eval scripts.
- Run a small conversion/tokenization smoke test and inspect decoded samples before large sampling.

PrefixLM readiness verdict on 2026-06-18:

- The training dataset core in `dataset_new.py` is ready for PrefixLM rows
  shaped as one rendered prompt plus one supervised assistant response. With
  `target_only: true`, the prompt segment is masked and only the response is
  trained.
- The current Rust tokenizer in `data_io/tokenizer/src/main.rs` is not yet
  ready for native DFM6 chat/tool/reasoning rows. It injects HRM/Sapient
  BOQ/EOQ/EOA and condition marker tokens around `instruction`/`response`
  fields rather than rendering a chat template.
- DFM6 needs a new canonical rendering/tokenization path that can normalize
  messages, tools, tool calls, tool responses, and optional reasoning channels
  into the Gemma-native template before tokenization.
- The current sampled-data schema stores one `inst_*` span and one `resp_*`
  span per row. This is sufficient if each example is rendered so the final
  assistant answer is the only supervised span. It is not sufficient for
  arbitrary multi-turn supervision of several assistant spans unless those rows
  are split or the schema is extended with per-token loss masks.

Confidence: high from inspecting `dataset_new.py`,
`data_io/tokenizer/src/main.rs`, and
`evaluation/chat_templates/gemma4_native_chat.jinja`.

Update later on 2026-06-18:

- A first Rust `--template-mode gemma4-chat` renderer was compiled and
  smoke-tested, but it was superseded before use for DFM6 production
  tokenization. The reason is that an approximate renderer duplicates the
  template contract and can drift from the actual Gemma chat template.
- The interim Rust-renderer tokenization tmux session was stopped, and the
  tiny partial `data/tokenized_dfm6_raw` tree was removed.
- `scripts/tokenize_chat_template.py` is now the preferred DFM6 preparation
  path. It renders examples through `data_io/chat_templates/gemma4_native_chat.jinja`
  with Jinja2, tokenizes both the rendered prompt and full rendered
  conversation with the Gemma tokenizer, and uses the full-minus-prompt token
  suffix as the supervised response span.
- HRM-style `condition`/`instruction`/`response` rows are normalized to chat
  messages before rendering: non-`direct` conditions become a `system` message,
  the instruction becomes a `user` message, and the response becomes the
  supervised `assistant` message.
- Existing `messages` JSONL rows are kept as role/content histories; every
  assistant turn with content can become one PrefixLM example with the prior
  history as the prompt.
- The legacy Rust HRM marker path remains available and is not required for
  DFM6 Jinja tokenization.

Smoke command:

```bash
cd /work/dfm/HRM-Text
rm -rf data/tokenized_dfm6_jinja_smoke
/home/ucloud/miniforge3/envs/hrm/bin/python scripts/tokenize_chat_template.py \
  export-upload/danish-dynaword-prefix-continuation \
  --tokenizer-path /work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json \
  --chat-template data_io/chat_templates/gemma4_native_chat.jinja \
  -o data/tokenized_dfm6_jinja_smoke
```

Result: `105317` rows, `0` skipped rows. Inspected token IDs showed Gemma BOS
`2`, turn start `105`, and turn end `106`. Confidence: high.

Production tokenization started in tmux session `dfm6_jinja_tokenize`:

```bash
cd /work/dfm/HRM-Text
nice -n 10 ionice -c2 -n7 \
  /home/ucloud/miniforge3/envs/hrm/bin/python scripts/tokenize_chat_template.py \
  data/converted_sources data/converted_sources_dfm4_summarization export-upload \
  --tokenizer-path /work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json \
  --chat-template data_io/chat_templates/gemma4_native_chat.jinja \
  -o data/tokenized_dfm6_jinja
```

This uses one process and is much slower than the Rust tokenizer, but it keeps
the Jinja template as the single source of truth. Confidence: high for the
command and observed start; medium for runtime.

Superseded 2026-06-18: the DFM6 tokenization run from
`data/converted_sources` was stopped. Although the direct-Jinja renderer itself
is correct, using the old HRM `condition`/`instruction`/`response` intermediate
as the universal DFM6 input is not sufficient. It preserves already-flat
prompt/answer sources, but it can lose structure from original message, tool
call, tool response, and reasoning datasets before the Gemma chat template ever
sees them.

Replacement decision:

- DFM6 should render directly from original downloaded/filtered source schemas
  when those schemas contain `messages`, tools, tool calls, tool responses,
  reasoning fields, or other structured chat fields.
- The HRM `condition`/`instruction`/`response` intermediate is acceptable only
  for sources that are already intrinsically flat prompt/answer rows, or for
  compatibility sources such as Sapient-cleaned files that already arrive in
  that schema.
- For Sapient-cleaned FLAN example
  `data_clustered/flan/niv2_zsopt_data__task1564_triviaqa_answer_generation.parquet`,
  the string `Input: Question:What ...` is already present in the downloaded
  Sapient-cleaned parquet, the filtered symlink, and the converted parquet. Our
  converter did not introduce the missing space. The corresponding Natural
  Instructions source row also has `inputs: "Question:What ..."`.

Confidence: high from local parquet/jsonl inspection.

Implementation update later on 2026-06-18:

- Added `scripts/build_dfm6_chat_source_tree.py` to build
  `data/dfm6_chat_sources`.
- Added `scripts/audit_dfm6_chat_sources.py` to audit every source file before
  tokenization.
- `scripts/tokenize_chat_template.py` now follows symlinked source
  directories, skips export `seeds/` folders, passes top-level `tools` to the
  Gemma Jinja template, normalizes JSON-string tool-call arguments to mappings,
  maps DOLCI `environment` messages to `tool`, and handles DOLCI
  `functions`/`function_calls` fields.
- `allenai_code_meta_reasoning` was excluded from the DFM6 chat source tree for
  now because the filtered source is `id/text/token_count` raw problem text,
  not chat/instruction data, and no converted flat source exists locally.

Audit command:

```bash
cd /work/dfm/HRM-Text
python scripts/build_dfm6_chat_source_tree.py --force --output data/dfm6_chat_sources
/home/ucloud/miniforge3/envs/hrm/bin/python scripts/audit_dfm6_chat_sources.py \
  data/dfm6_chat_sources \
  --json-out logs/dfm6_chat_source_audit_20260618.json
```

Audit result: `10475` files, `8963` flat `condition`/`instruction`/`response`
files, `1512` message files, `0` unsupported files, `0` errors. Of the message
files, `4` have top-level tools. Confidence: high from local audit output.

Format smokes:

- Sapient FLAN flat source:
  `data/converted_sources/sapient_cleaned/data_clustered/flan/niv2_zsopt_data__task1564_triviaqa_answer_generation.parquet`
  decoded as one `user` turn plus supervised `model` response under Gemma
  turn tokens. The missing `Question:What` space is inherited from upstream,
  not introduced locally.
- Nemotron Agentic one-row tool-calling smoke produced Gemma `<|tool>` tool
  definitions in the prompt and `<|tool_call>` plus thought channel tokens in
  the supervised response. JSON-string arguments are now normalized to single
  Gemma argument blocks such as
  `call:get_artwork_details{artwork_id:<|"|>ART-9955<|"|>}`.
- DOLCI tool-use one-row smoke produced tool definitions, tool calls, and tool
  responses without skipped rows after normalizing DOLCI-specific fields.

Operational update 2026-06-19:

- The long DFM6 direct-Jinja tokenization tail left
  `nemotron_swe/data/swe.jsonl` and
  `nemotron_agentic/data/tool_calling.jsonl` without completed metadata.
- A dedicated one-file source tree was created at
  `data/dfm6_chat_sources_tool_calling` so `tool_calling.jsonl` can be
  tokenized into the same `data/tokenized_dfm6_direct_jinja` output without
  starting a duplicate `swe.jsonl` worker.
- The first one-file `tool_calling` run failed on a JSONL row with an invalid
  raw control character; the second showed that some physical lines are split
  inside literal string newlines. `scripts/tokenize_chat_template.py` now uses
  `json.JSONDecoder(strict=False)` and accumulates physical lines until a full
  JSON object parses.
- Restart command:

```bash
cd /work/dfm/HRM-Text
nice -n 10 ionice -c2 -n7 \
  /home/ucloud/miniforge3/envs/hrm/bin/python scripts/tokenize_chat_template.py \
  data/dfm6_chat_sources_tool_calling \
  --tokenizer-path /work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json \
  --chat-template data_io/chat_templates/gemma4_native_chat.jinja \
  --workers 1 \
  -o data/tokenized_dfm6_direct_jinja
```

Confidence: high from local failure log and restarted worker process.

SWE sharding update later on 2026-06-19:

**Reconstruction update (2026-10-21):** reuse this split/join design for the
HF-only DFM6 rebuild, too. The monolithic reconstruction was stopped after
10,522 other tasks completed; SWE was only about 12% through its source.
`scripts/rebuild_dfm6.py tokenize` now reuses completed non-SWE receipts,
splits the pinned HF SWE input into 32 complete-conversation shards using
`scripts/split_jsonl_objects.py`, and runs 32 bounded-memory HF tokenizer
workers. It uses the frozen historical adapter/template, not current chat
conversion semantics. The split must contain exactly 46,278 objects; source
and shard SHA-256 hashes are checked. `scripts/join_tokenized_shards.py`
restores source order and adjusts token offsets. All five joined arrays must
match historical SWE before linking into the reconstructed union. Sampling
still waits for verification of every source task.

Working directories under `data/rebuild_hf_dfm/serial-queue/dfm6`:
`swe_split`, `swe_sources`, and `swe_tokenized`. The existing filesystem
watchdog still guards the entire process group. Do not reuse the interrupted
monolithic `.chat-*` partial output. The streaming tokenizer itself was not
edited during this transition, preserving the 10,522 completed cache receipts.
A multi-turn, multi-line JSON split/tokenize/join test confirms equality with
monolithic tokenization, including all four index arrays; 11 focused tests pass.

**October 22 recovery:** all SWE shards and their merge completed; all five
merged arrays matched historical SWE. The later full-source comparison
stopped with its last progress line at 5,150/10,523, while `plan.json` still
said `running`. No reconstruction process or lock holder remained. The logs
do not establish why the processes disappeared; there was no recorded slow-FS
watchdog stop. Restarted the existing guarded runner from `verify` at 06:19
CEST, without resetting completed tokenization. Verification restarts its scan
because it has no per-task durable comparison receipts. Always corroborate
queue status with live PIDs and fresh log activity before reporting it running.

- `nemotron_swe/data/swe.jsonl` was split into 32 complete-JSON-object shards
  under `data/dfm6_swe_jsonl_shards` with `scripts/split_jsonl_objects.py`.
  The split produced `46278` objects across 32 shards.
- A separate tokenization run was started in tmux session
  `dfm6_swe_shard_tokenize`, writing to `data/tokenized_dfm6_swe_shards`.
  This keeps the shard outputs separate from the production
  `data/tokenized_dfm6_direct_jinja` tree until validation and joining.
- The original monolithic full-tree tokenizer session
  `dfm6_direct_jinja_tokenize` was killed after it reached very high RSS. The
  separate shard tokenizer was left running.
- To avoid a memory cliff, 24 of 32 SWE shard workers were paused with
  `SIGSTOP`, leaving the 8 most advanced shards running. The pause state was
  recorded in `logs/dfm6_swe_shard_pause_state_20260619.json`.
- Current plan: let the 8 running shards finish and flush, then resume further
  paused shards in batches before joining with `scripts/join_tokenized_shards.py`.
- Update 2026-06-20: the first 8 SWE shards finished and flushed metadata
  after about 1h36m. The remaining 24 paused shard workers were resumed with
  `SIGCONT`; at resume they were around `43.6%` to `45.1%` through their source
  bytes.
- Later on 2026-06-20, memory pressure rose again while the 24 resumed shards
  were around `80%` to `86%`. The 12 slowest active shards were paused with
  `SIGSTOP`, leaving the 12 fastest active shards running. The second pause
  state is recorded in
  `logs/dfm6_swe_shard_pause_state_20260620_second_batch.json`.
- The 12 paused workers were later resumed with `SIGCONT` after the first
  shards in the active batch began finishing. At resume, `10/32` SWE shard
  outputs had completed and `22` shard workers were open/running.
- All 32 SWE shards later finished. The shard merge was started in tmux session
  `dfm6_swe_join` with log `logs/dfm6_swe_join_20260620_094544.log`, writing
  the joined task `nemotron_swe__data__swe.jsonl` under
  `data/tokenized_dfm6_swe_shards` before validation/copy into the direct DFM6
  tokenized tree.
- `nemotron_agentic/data/tool_calling.jsonl` was force-redownloaded from
  `nvidia/Nemotron-SFT-Agentic-v2`; the fresh file matched the local file
  exactly by size and SHA-256. The huge NUL-padded corrupt physical line 1095
  is therefore upstream, not local filesystem/download corruption.
- A cleaned copy of `tool_calling.jsonl` was created at
  `data/cleaned_sources/nemotron_agentic/data/tool_calling.jsonl`, dropping
  exactly the one upstream-corrupt NUL-padded physical row. The cleaning summary
  is `data/cleaned_sources/nemotron_agentic/data/tool_calling.cleaning_summary.json`:
  `8443` rows kept, `1` row dropped. Tokenization was restarted from
  `data/dfm6_chat_sources_tool_calling_clean` into
  `data/tokenized_dfm6_direct_jinja`.

Confidence: high from local process state, tmux state, and split manifest.

Active corrected tokenization command:

```bash
cd /work/dfm/HRM-Text
nice -n 10 ionice -c2 -n7 \
  /home/ucloud/miniforge3/envs/hrm/bin/python scripts/tokenize_chat_template.py \
  data/dfm6_chat_sources \
  --tokenizer-path /work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json \
  --chat-template data_io/chat_templates/gemma4_native_chat.jinja \
  --workers 32 \
  -o data/tokenized_dfm6_direct_jinja
```

It is running in tmux session `dfm6_direct_jinja_tokenize`, with log
`logs/dfm6_direct_jinja_tokenize_workers32_20260618_160811.log`. Confidence:
high for local process/log observation.

`scripts/build_tokenized_dfm6_tree.py` prepares the selected tokenized union
after raw tokenization. It links only intended DFM6 task prefixes and maps
`sapient_cleaned__data__...` / `sapient_cleaned__data_clustered__...` raw names
back to the original Sapient task names for the allowed filtered subset. This
prevents `sample_tokenized.py` from sampling unmatched raw tokenized
directories by fallback. Confidence: high from local script inspection.

Parallelization update on 2026-06-18: `scripts/tokenize_chat_template.py` now
supports `--workers N`. It uses process-level file parallelism; each worker
loads the Gemma tokenizer and Jinja template once and writes independent output
directories. Resume remains metadata-based, so restarting with a larger worker
count skips already completed files unless `--force` is passed. A two-worker
smoke on `export-upload/danish-dynaword-prefix-continuation` completed
`105317` rows with `0` skipped rows in `49.2s`, versus `74.3s` for the earlier
single-worker smoke. Confidence: high.

## Tool Calling
DFM5 has no meaningful tool-calling ability. Adding tool data requires a schema, not just more chat rows.

Plan:

- Define canonical Danish and English schemas for function definitions, tool calls, tool results, tool errors, malformed calls, multi-turn tool traces, and final natural-language answers.
- Preserve machine-readable tool-call structure where possible rather than flattening everything into plain text.
- Include negative/error-recovery cases so the model learns when not to call a tool and how to handle tool failures.
- Add dedicated Danish and English tool-calling evals. BFCL-v2 English is necessary but not sufficient.

## Math And Code Scaling
DFM5 shows that broad instruction and language data can improve many metrics while GSM8K, HumanEval, and tool calling remain bottlenecks.

Plan:

- Set explicit token targets for Danish math, English math, Danish code, English code, and tool-calling data.
- Separate elementary arithmetic/GSM8K-style reasoning from advanced MATH-style reasoning; DFM5 is much closer on MATH than on GSM8K.
- Include code execution style data and natural-language programming assistance data.
- Track source families and caps so later ablations can distinguish math, code, tool, and post-training effects.

## Post-Training Balance
Post-training data is useful, but too much assistant-style short-response data can distort the base distribution.

Plan:

- Keep post-training as an explicitly capped component unless DFM6 is deliberately a post-trained/final-stage model.
- Maintain enough longer-form instruction, reasoning, summarization, translation, QA, and Danish content to avoid overfitting to narrow assistant turns.
- Use audited synthetic data only after judge/format checks pass.

## Contamination And Deduplication
Expanded math/code/tool data increases benchmark leakage risk.

Plan:

- Deduplicate against held-out eval prompts where practical.
- Check known train/test split boundaries for benchmark-derived sources.
- Keep explicit source manifests, sampling metadata, and cap records.
- Mark benchmark-adjacent sources as such in data-mix documentation.

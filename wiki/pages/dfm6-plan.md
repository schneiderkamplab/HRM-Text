# DFM6 Plan

Last updated: 2026-06-20
Confidence: medium
Scope: Forward-looking DFM6 training/data plan based on DFM5-L eval behavior, local scheduler/eval experience, and current repo constraints.

## Goal

DFM6 should keep the language and Danish gains seen in DFM5 while directly addressing the weak areas that remain visible in DFM5-L:

- GSM8K and elementary arithmetic reasoning lag behind the original Sapient L and external Qwen baselines.
- HumanEval/code improves but remains behind stronger external baselines.
- BFCL/tool-calling is effectively absent.
- General language gains do not automatically close math/code/tool gaps.

## Core Direction

Include:

- DFM6 is intended to be a strict superset of DFM5 at the source/data-policy
  level: every source family accepted into DFM5 should remain present unless a
  later explicit safety, quality, contamination, or licensing decision removes
  it.
- all new DFM post-training datasets that pass quality/audit checks;
- scaled-up Danish math and code data;
- scaled-up English math and code data;
- Danish tool-calling data;
- English tool-calling data.

Migration:

- Replace the current HRM/Sapient tokenizer with the intended Gemma 4 tokenizer.
- Render instruction-format data with the Gemma 4 chat template rather than the original Sapient/DFM5 instruction format.
- Because DFM6 changes tokenizer and chat-template rendering, “strict
  superset” means source coverage and sampling intent, not byte-identical
  tokenized artifacts or exactly identical rendered prompts.

Confidence: high for the user decision on 2026-06-20; medium for final caps
until the sampled DFM6 manifest is built and audited.

Clarification, 2026-06-20: no new DFM6 policy decision has been made to drop
any source family accepted into DFM5. Older DFM5 safety exclusions from the
original Sapient corpus still apply, but DFM6 should include the DFM5 accepted
set plus DFM6 additions. Any missing DFM5-accepted source in the DFM6 tokenized
union should therefore be treated as an implementation/audit issue unless it is
explicitly superseded. One current temporary omission is
`allenai_code_meta_reasoning`: it was left out of the direct chat source tree
because the local file is raw `id`/`text`/`token_count`, not a chat or
instruction row. Confidence: high from local notes and user clarification.

Update 2026-06-18: DFM6 preparation files were added without touching the
current training run:

- `config/data/dfm6.yaml` points to the future `data/sampled_dfm6` output.
- `data_io/prefix_config_dfm6.yaml` records the selected source families and
  draft caps for a future token-analytics pass.
- `data_io/chat_templates/gemma4_native_chat.jinja` is a data-prep copy of the
  repo's Gemma-native evaluation chat template.

Confidence: high for local file paths; medium for draft sampling caps.

Accepted DFM6 source decision from 2026-06-18:

- Upscale/add `nemotron_agentic`, `nemotron_swe`, and
  `nemotron_instruction_reasoning_off`.
- Include AllenAI RLVR/OpenMath sources: `allenai_rlvr_gsm`,
  `allenai_rlvr_math`, and `allenai_open_math_2_50k_r1`.
- Include Tulu persona sources for code, math, and instruction following:
  `allenai_tulu_3_personas_code`, `allenai_tulu_3_personas_math`, and
  `allenai_tulu_3_personas_if`.
- Include DOLCI no-tools and tool-use sources:
  `dolci_instruct_sft_no_tools`, `dolci_instruct_sft_tool_use`, and
  `dolci_instruct_sft_tool_use_sa`.
- Include the expanded Common Pile and Danish DynaWord export datasets when
  available, replacing the earlier smaller versions in-place rather than under
  new dataset names.

Confidence: high for the user decision; medium for final token proportions.

## Main Challenges

### Tokenizer Migration

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

### Chat Template Consistency

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

### Tool Calling

DFM5 has no meaningful tool-calling ability. Adding tool data requires a schema, not just more chat rows.

Plan:

- Define canonical Danish and English schemas for function definitions, tool calls, tool results, tool errors, malformed calls, multi-turn tool traces, and final natural-language answers.
- Preserve machine-readable tool-call structure where possible rather than flattening everything into plain text.
- Include negative/error-recovery cases so the model learns when not to call a tool and how to handle tool failures.
- Add dedicated Danish and English tool-calling evals. BFCL-v2 English is necessary but not sufficient.

### Math And Code Scaling

DFM5 shows that broad instruction and language data can improve many metrics while GSM8K, HumanEval, and tool calling remain bottlenecks.

Plan:

- Set explicit token targets for Danish math, English math, Danish code, English code, and tool-calling data.
- Separate elementary arithmetic/GSM8K-style reasoning from advanced MATH-style reasoning; DFM5 is much closer on MATH than on GSM8K.
- Include code execution style data and natural-language programming assistance data.
- Track source families and caps so later ablations can distinguish math, code, tool, and post-training effects.

### Post-Training Balance

Post-training data is useful, but too much assistant-style short-response data can distort the base distribution.

Plan:

- Keep post-training as an explicitly capped component unless DFM6 is deliberately a post-trained/final-stage model.
- Maintain enough longer-form instruction, reasoning, summarization, translation, QA, and Danish content to avoid overfitting to narrow assistant turns.
- Use audited synthetic data only after judge/format checks pass.

### Contamination And Deduplication

Expanded math/code/tool data increases benchmark leakage risk.

Plan:

- Deduplicate against held-out eval prompts where practical.
- Check known train/test split boundaries for benchmark-derived sources.
- Keep explicit source manifests, sampling metadata, and cap records.
- Mark benchmark-adjacent sources as such in data-mix documentation.

## Rehearsal Before Large Training

Before committing a full DFM6 run:

1. Convert a tiny representative sample with the Gemma tokenizer/template.
2. Tokenize and sample it.
3. Decode samples and inspect formatting.
4. Train a short smoke model.
5. Export/serve the checkpoint.
6. Run a small standard, DFM, EuroEval, and tool-calling smoke eval.

This catches tokenizer/template/export/eval failures before spending a large training budget.

## Evaluation Gates

Use the existing DFM5-style sections, but add explicit tool-calling gates:

- Danish: DaLA, GEC-DaLA, Danish Citizen Tests, MultiWikiQA, NordjyllandNews, WMT24++ en-da, IFEval-DA, EuroEval Danish tasks, Danish tool-calling.
- English: ARC-C, BoolQ, DROP, HellaSwag, MMLU, Winogrande, GovReport, English EuroEval tasks.
- Math and code: GSM8K, MATH, HumanEval, BFCL-v2, Danish/English tool-calling.

Decision rule:

- Do not judge DFM6 only by the overall average.
- Track section averages plus individual bottleneck metrics.
- Treat GSM8K, HumanEval, and tool-calling as explicit go/no-go diagnostics because they are known DFM5 weak points.

## Suggested Work Order

1. Lock tokenizer/template choice and validate local loading.
2. Implement canonical Gemma-template conversion and decoding checks.
3. Define DFM6 source manifest and token targets.
4. Add math/code/tool source families with caps and provenance notes.
5. Run contamination/dedup checks.
6. Build tokenized/sampled DFM6 artifacts from source.
7. Run the tiny end-to-end rehearsal.
8. Train a small DFM6 smoke model.
9. If smoke evals are healthy, start the main DFM6 run.

## Sampling Status

Update 2026-06-20. Confidence: high from local command output.

The DFM6 tokenized union was rebuilt from
`data/tokenized_dfm6_direct_jinja` into `data/tokenized_dfm6` after fixing
`scripts/build_tokenized_dfm6_tree.py` to strip the raw
`export-upload__` prefix for selected uploaded datasets. The rebuilt union
contains:

- `6,456` selected task directories;
- `4,891` allowed Sapient task directories, with no missing allowed Sapient
  tasks;
- all `70` `sapient-synth-*` synthetic replacement datasets;
- all `12` Common Pile, Danish DynaWord, and `transformations-*` derived
  upload dataset families;
- `1,427` selected upload-derived task directories.

The prefix audit was written to `logs/dfm6_prefix_audit_latest.json`. The only
zero configured prefixes were stale `synth_high40__`/`synth_repeat30__` names
and `allenai_code_meta_reasoning__`, which remains a known raw-text converter
gap rather than an intentional DFM6 exclusion.

Five-epoch sampling was launched in tmux session `dfm6_sample_5epochs`:

```bash
cd /work/dfm/HRM-Text/data_io
/home/ucloud/miniforge3/envs/hrm/bin/python sample_tokenized.py \
  tokenized_path=/work/dfm/HRM-Text/data/tokenized_dfm6 \
  output_path=/work/dfm/HRM-Text/data/sampled_dfm6 \
  prefix_config_path=/work/dfm/HRM-Text/data_io/prefix_config_dfm6.yaml \
  epochs=5 \
  concat_workers=1
```

Log: `logs/dfm6_sample_5epochs_20260620_100332.log`.

At launch-time monitoring, token concatenation completed and wrote
`data/sampled_dfm6/tokens.npy` at about `756G`. The process then entered
`Generating epoch indices: 0/5`; no epoch directories had been written yet.

Completion and validation update, 2026-06-20. Confidence: high from local
validation, decoding, and FSDP smoke output.

Superseded by the corrected-cap update below: the first DFM6 sample completed
successfully but accidentally used uncapped default exposure for shared
Sapient-style prefixes such as broad `flan__` and `SYNTH__`. It reported
`98,533,525,792` tokens per epoch and was used to validate the Gemma template
and sampler path, but should not be used for DFM6 training.

Corrected-cap sampling completed successfully into `data/sampled_dfm6` after
the DFM6 policy was clarified:

- DFM6 inherits DFM5 caps/repeats for every shared prefix unless
  `data_io/prefix_config_dfm6.yaml` explicitly overrides that prefix for a
  deliberate DFM6 upscale.
- Broad Sapient `flan__`, `SYNTH__`, `tasksource__`, and related original
  prefixes now use inherited DFM5 caps/repeats.
- `nemotron_swe__` is explicitly excluded with `max_per_file: 0` for the
  current sample. The huge `nemotron_swe__data__swe.jsonl` artifact has no
  usable rows at 4k context under the current PrefixLM truncation rule because
  its prompts are too long; it should only be revisited through a dedicated
  conversion/windowing path.
- The 756G `tokens.npy` backing store was reused with
  `sample_tokenized.py reuse_tokens=true`; only epoch indices and metadata were
  regenerated.

Corrected sample:

- `metadata.json` reports `max_seq_len: 4097`,
  `tokenizer_info.vocab_size: 262144`, and
  `total_length: 56,257,414,878` tokens per epoch.
- Total 5-epoch sampled exposure is about `281.29B` tokens.
- The backing `tokens.npy` has shape `(202,740,907,136,)`, dtype `int32`,
  about `756G` on disk.
- Each of `epoch_0` through `epoch_4` has
  `190,531,808` rows and the four expected index arrays.
- A 5,000-row-per-epoch bounds sample verified positive prompt lengths,
  response lengths at least 2, and in-bounds prompt/response spans.

Decoded task-level examples from `data/tokenized_dfm6` confirmed Gemma chat
template rendering:

- flat Sapient rows decode as `<bos><|turn>user ... <|turn>model` plus a
  supervised response ending in `<turn|>`;
- Common Pile and Danish DynaWord derived rows decode as normal user/model
  chat turns;
- Nemotron Agentic/SWE rows include Gemma tool/thought/tool-call tokens such as
  `<|channel>thought`, `<|tool_call>`, and `<|tool_response>`.

Smoke datasets were built from real sampled DFM6 rows:

- `data/sampled_dfm6_smoke`: `2,048` rows and `566,220` tokens for dataloader
  validation.
- `data/sampled_dfm6_train_smoke`: `49` rows and `14,375` tokens for a tiny
  training smoke.

The dataloader smoke passed with `target_only: true`, vocab size `262144`,
shifted max sequence length `4096`, packed 4096-token batches, and masked
prompt labels with supervised assistant-response labels.

A direct non-distributed `distributed_strategy=none` train smoke failed because
that path leaves FA4 inputs in FP32, while FA4 requires FP16/BF16/FP8. This is
not the intended training path for DFM6. The intended FSDP path was then tested
successfully:

```bash
cd /work/dfm/HRM-Text
CUDA_VISIBLE_DEVICES=0 WANDB_MODE=offline \
WANDB_DIR=/work/dfm/HRM-Text/logs/wandb_smoke_dfm6_xxs_fsdp \
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
/home/ucloud/miniforge3/envs/hrm/bin/torchrun --nproc_per_node=1 pretrain.py \
  data=dfm6 \
  data.path=data/sampled_dfm6_train_smoke \
  arch/size@arch=XXS \
  epochs=1 \
  global_batch_size=4096 \
  gradient_accumulation_steps=1 \
  accelerator_type=sm100 \
  distributed_strategy=fsdp \
  fsdp_params_precision=fp32 \
  compile_train_batch=false \
  log_interval=1 \
  checkpoint_path=checkpoints/smoke/dfm6_xxs_fsdp_train_smoke \
  project_name='DFM6 Smoke' \
  run_name='dfm6-xxs-fsdp-train-smoke' \
  hydra.run.dir=.
```

Result: `3/3` optimizer steps completed, W&B offline run wrote finite training
losses, and the run checkpointed to
`checkpoints/smoke/dfm6_xxs_fsdp_train_smoke`.

Corrected approximate mutually exclusive token allocation per epoch, computed
from the actual tokenized tree and `prefix_config_dfm6.yaml` after
sampler-style truncation/cap/repeat logic:

| Bucket | Tokens / epoch | Share | Rows / epoch | Notes |
|---|---:|---:|---:|---|
| English/general/other | `16.08B` | `28.6%` | not recomputed in final audit | capped Sapient FLAN/SYNTH plus DOLCI no-tools, Common Pile, Tulu SFT, transformations |
| Code/math/tool/reasoning | `24.07B` | `42.8%` | not recomputed in final audit | Nemotron Agentic/reasoning-off, OpenMath/ACE/OpenThoughts, DOLCI tool-use, AllenAI, Sapient math/reasoning |
| Danish-language sources | `16.11B` | `28.6%` | not recomputed in final audit | Laerebogen, OPUS, Danish DynaWord, transformations, Wiki Instruct DA, DBC/LexDK/Oliver Kinch/Synquid |

The allocation sum differs from `metadata.total_length` by only about
`184K` tokens due to expected-row averaging for capped random subsets. Danish
math/reasoning/tool rows are counted in the code/math/tool/reasoning bucket
when they match that bucket first.

DFM5 comparison, computed on 2026-06-20 with the same mutually exclusive bucket
rules from `data/tokenized_dfm5`, `data_io/prefix_config_dfm5.yaml`, and
`data/sampled_dfm5/metadata.json`. Confidence: high for the local computation;
medium for semantic bucket labels because they are filename/prefix heuristics.

DFM5 metadata reports `35,605,979,095` tokens per epoch. The bucket estimate
sums to `35,606,064,216`, within about `85K` tokens of metadata:

| Bucket | DFM5 tokens / epoch | DFM5 share | DFM6 tokens / epoch | DFM6 share |
|---|---:|---:|---:|---:|
| English/general/other | `16.85B` | `47.3%` | `64.78B` | `65.7%` |
| Code/math/tool/reasoning | `12.36B` | `34.7%` | `25.87B` | `26.3%` |
| Danish-language sources | `6.40B` | `18.0%` | `7.88B` | `8.0%` |

Interpretation: DFM6 is much larger per epoch than DFM5, so English/general
and code/math/tool/reasoning both increase substantially in absolute tokens.
Danish also increases in absolute tokens, but its share drops because DFM6 adds
and upscales much more English/general and tool/code/math data. Token counts
are not perfectly tokenizer-comparable because DFM5 uses the HRM 65k tokenizer
and DFM6 uses the Gemma 262k tokenizer.

DFM5-superset audit update, 2026-06-20:

The current `data/tokenized_dfm6` / `data/sampled_dfm6` artifact is not yet a
strict source-level superset of DFM5. The issue is implementation coverage, not
a new data-policy exclusion, except for the separate deliberate
`nemotron_swe__` cap of zero.

Verified local findings:

- `dolci_instruct_sft`, `nemotron_multilingual`,
  `allenai_tulu_v2_sft_mixture`, `allenai_tulu_v2_sft_long_mixture`,
  `allenai_verifiable_reasoning_gpt41`,
  `allenai_verifiable_reasoning_o4mini`, `allenai_sciriff_train_mix`,
  `allenai_if_sft_verified`, and `allenai_tulu_3_personas_algebra` are present
  under `data/downloads/datasets`, `data/filtered_sources`, and
  `data/converted_sources`, but have zero corresponding task dirs in
  `data/tokenized_dfm6_direct_jinja`. They were omitted from
  `scripts/build_dfm6_chat_source_tree.py`.
- DFM4 summarization sources are present in the raw DFM6 Jinja-tokenized tree
  as `converted_sources_dfm4_summarization__dfm4_*`, but
  `scripts/build_tokenized_dfm6_tree.py` does not select or strip that wrapper
  prefix, so the sampled DFM6 union sees zero `dfm4_*_summarization__` rows.
- Row comparison after sampler-style filtering/caps/repeats:
  DFM5 has `92,418,825` rows per epoch; current DFM6 has `190,531,808` rows
  per epoch. Missing DFM5 categories in current DFM6 include
  `dolci_instruct_sft` (`2,453,517` DFM5 rows/epoch),
  `dfm4_laion_scientific_summaries` (`2,288,807`),
  `allenai_tulu_v2_sft_mixture` (`748,824`),
  `allenai_tulu_v2_sft_long_mixture` (`532,023`),
  `nemotron_multilingual` (`396,000`),
  `dfm4_wiki_cat_sum_summarization` (`307,822`),
  `allenai_verifiable_reasoning_gpt41` (`284,811`),
  `dfm4_arxiv_paper_summarization` (`213,354`),
  `allenai_verifiable_reasoning_o4mini` (`172,000`),
  `allenai_sciriff_train_mix` (`117,983`),
  `allenai_if_sft_verified` (`31,733`),
  `allenai_tulu_3_personas_algebra` (`20,000`), and
  `dfm4_govreport_summarization` (`8,304`).
- Old DFM5 synthetic placeholder categories `synth_high40` and
  `synth_repeat30` are absent by those exact names, but DFM6 contains the
  renamed `sapient-synth-*` export datasets. That is a naming migration, not
  necessarily content loss.

Confidence: high for the local counts and path checks; medium for treating the
omissions as accidental until the source-builder intent is patched and audited.

DFM6 superset-fix token estimate update, 2026-06-20:

Supersedes the earlier pre-fix DFM6 distribution estimate above for planning
purposes. After adding the missing DFM5 source families to
`scripts/build_dfm6_chat_source_tree.py` and `scripts/build_tokenized_dfm6_tree.py`,
the in-progress raw Gemma/Jinja tokenized tree had `10,521` completed metadata
files. Applying `data_io/prefix_config_dfm6.yaml` with sampler-style filtering,
4097-token context truncation, caps, and repeats estimated `61.58B` tokens per
epoch before the two remaining tail files finish.

Provisional high-level distribution from completed files:

| Bucket | Tokens / epoch | Share |
|---|---:|---:|
| Code/math/tool/reasoning | `23.54B` | `38.2%` |
| English/general/other | `21.81B` | `35.4%` |
| Danish-language sources | `16.23B` | `26.4%` |

This is above the intended 2026-06-20 rebalance target of roughly `56B` tokens
per epoch (`16B` English/general/other, `24B` code/math/tool/reasoning, `16B`
Danish-language). Danish and code/math/tool/reasoning are close to target, but
English/general/other is roughly `5.8B` over target before the final tail files.
The final sampled artifact should therefore be audited after resampling, and a
follow-up cap pass is likely needed if the 56B target should be held tightly.

Confidence: high for the local tokenized metadata computation; medium for the
semantic bucket labels because they are prefix-based.

## Open Questions

- Exact Gemma 4 tokenizer artifact and license status.
- Whether DFM6 should be purely fresh training or include a separate upcycling experiment.
- Final token budget per epoch and number of epochs.
- Exact Danish/English tool-calling datasets and whether synthetic tool traces are needed.
- How much post-training data belongs in the base run versus a separate final refinement stage.

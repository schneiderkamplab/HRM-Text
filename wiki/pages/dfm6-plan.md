# DFM6 Plan

Last updated: 2026-06-25
Confidence: high
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

Sampled training size, 2026-06-25. Confidence: high from local metadata and
checkpoint configs. Current post-superset-fix `data/sampled_dfm6/metadata.json`
reports `total_length=62,819,933,768` tokens per epoch. Both
`checkpoints/dfm6/XL/all_config.yaml` and `checkpoints/dfm6/XL-gas2/all_config.yaml`
set `epochs=5`, so the nominal five-epoch DFM6 training exposure is
`314,099,668,840` tokens, or about `314.10B` tokens.

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

## DFM6 MultiWikiQA Early-Checkpoint Behavior

Last updated: 2026-06-22
Confidence: high
Scope: Local diagnosis of DFM6 XL-GAS2 `step_50k`, `step_100k`, and
`step_150k` MultiWikiQA eval outputs.

The poor-looking MultiWikiQA exact-match scores at `step_150000` are not best
explained by missing training data. The DFM6 tokenized union contains
`oliverkinch_multi_wiki_qa_high_quality__da__train-00000-of-00001.parquet`, and
`data_io/prefix_config_dfm6.yaml` repeats the
`oliverkinch_multi_wiki_qa_high_quality__` prefix `10` times.

Observed local metrics:

| Checkpoint | DFM F1 | DFM EM | EuroEval F1 | EuroEval EM |
|---|---:|---:|---:|---:|
| `step_50000` | `0.2964` | `0.0005` | `28.62` | `0.00` |
| `step_100000` | `0.3453` | `0.0029` | `33.14` | `0.21` |
| `step_150000` | `0.3823` | `0.0049` | `35.45` | `0.00` |

The F1 trend is improving, while exact match remains near zero. An
instance-level scan of the DFM eval outputs found that at `step_150000` about
`65%` of outputs contain a reference answer somewhere and about `62%` contain a
reference answer on the first output line, but `100%` of outputs stop by hitting
`max_tokens=32`. Typical bad outputs start with the right answer and then emit
bullets, alternatives, or repetition, so the exact-match scorer evaluates the
whole over-generated string rather than the first answer span.

Current interpretation: early DFM6 checkpoints often know how to extract the
answer span but have not yet learned the strict "answer with max 3 words and
stop" behavior. For future diagnosis, compare F1 and first-line/reference
containment alongside exact match, and consider a controlled rerun with tighter
stop/max-token settings or first-line answer extraction before treating this as
a data-coverage failure.

## DFM6 BFCL Tool-Calling Eval Smoke

Last updated: 2026-06-23
Confidence: high
Scope: Local single-request BFCL smoke tests against DFM6 XL-GAS2
`step_200000` HF export while the main training run was active.

Problem found at `step_200000`: EuroEval `bfcl-v2` failed, blocking
`average-00210` and therefore preventing W&B headline averages. The failure was
not a model score of zero; vLLM rejected every proxied request with:

```text
"auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set
```

Reason: `scripts/native_compatible_openai_proxy.py --gemma-native-bfcl-tools`
converted the EuroEval BFCL plain-text function list into OpenAI `tools`, but
the DFM6 vLLM server was launched without vLLM tool parsing enabled.

Live smoke setup:

- GPU: `7`
- vLLM memory cap: `0.30` because `0.35` requested `62.42 GiB` and the GPU had
  about `59 GiB` free under training.
- Model: `/work/dfm/HRM-Text/exports/dfm6_XL_gas2_step200000_ema_hf`
- Test prompt: one BFCL-style request with `walmart.purchase` and
  `musical_scale`, question "What is the musical scale associated with C sharp
  major?"

Variant A, OpenAI tools plus vLLM parser:

```bash
VLLM_EXTRA_ARGS='--enforce-eager --attention-backend FLASH_ATTN \
  --chat-template /work/dfm/HRM-Text/evaluation/chat_templates/gemma4_native_chat.jinja \
  --enable-auto-tool-choice --tool-call-parser gemma4'
```

Proxy mode: `--gemma-native-bfcl-tools`.

Result: request succeeded with `finish_reason=tool_calls`. The proxy converted
vLLM `message.tool_calls` to EuroEval-style text JSON:

```json
{"tool_calls":[{"function":"musical_scale","arguments":{}}]}
```

The function choice was correct; arguments were empty for this early checkpoint
and prompt.

Variant B, Gemma tool declarations as text without vLLM parser:

Proxy mode: `--gemma-native-bfcl-tools-as-text`. This injects a system message
containing Gemma-native `<|tool>declaration:...<tool|>` blocks and does not send
OpenAI `tools` to vLLM. The proxy postprocessor was widened to accept bare
Gemma-like `call:name{args}` outputs as well as wrapped
`<|tool_call>call:name{args}<tool_call|>` outputs.

Result: request succeeded and the proxy converted the bare tool-call text into
EuroEval-style JSON:

```json
{"tool_calls":[{"function":"musical_scale","arguments":{"key":"C sharp major","scale_type":"major"}}]}
```

Interpretation:

- vLLM's `gemma4` tool parser is the realistic OpenAI-compatible serving path
  and is now the default main DFM6 BFCL eval path. The scheduler appends
  `--enable-auto-tool-choice --tool-call-parser gemma4` at runtime when Gemma
  BFCL tools are enabled.
- The text-injection path is a useful diagnostic fallback. On this one smoke it
  produced better arguments, but it is less representative of real serving
  because vLLM does not see structured OpenAI `tools`.
- After changing BFCL eval settings, rerun the failed `step_200000` BFCL job and
  then allow/backfill `average-00210`.

Update 2026-06-23:

- Added scheduler metadata `hrm_vllm_gemma_bfcl_tool_mode`, defaulting to
  `parser`. Existing old plans that only have the Gemma chat template or
  `hrm_vllm_gemma_bfcl_tools=true` still resolve to parser mode.
- `scripts/run_euroeval_on_checkpoint.sh` now maps parser mode to
  `scripts/native_compatible_openai_proxy.py --gemma-native-bfcl-tools` and
  diagnostic text mode to `--gemma-native-bfcl-tools-as-text`.
- Superseded for later DFM6 checkpoints: co-running DFM6 vLLM evals initially
  used `vllm_gpu_memory_utilization=0.33`. This worked for `step_200000`, but
  at later training memory pressure around `bp_steps == 5`, `step_250000`
  failed at `0.33` with vLLM startup checks such as free memory
  `58.28 GiB < 58.85 GiB requested` and sampler warmup OOM.
- Replacement setting on 2026-06-23: use `vllm_gpu_memory_utilization=0.28`
  for regular co-running DFM6 vLLM eval jobs. This was later refined for
  judged `generative_talemaader`: keep `judged_batch=16` and
  `judged_max_connections=16`, but lower only
  `judged_vllm_gpu_memory_utilization` from `0.25` to `0.18`. The root cause
  was not batch pressure; the local `unsloth/gemma-4-E4B-it` judge OOMed
  during startup because the colocated HRM vLLM server had reserved too much KV
  cache. With `0.18`, the reset `step_250000` talemaader shards reached
  `completion 17/101 failed 0` at batch `16`.
- The active `step_250000` eval and upcoming `step_300000`, `step_350000`,
  `step_400000`, and `step_450000` plans were updated to `0.28` for regular
  vLLM rows and then to `0.18` for the judged talemaader rows only. Their GPU
  jobs also set `fixed_retry_batch=true` so retries do not silently halve batch
  size.
- The `step_250000` scheduler was stopped, its running rows were reset to
  pending attempt `0`, and it was relaunched. The restarted EuroEval rows
  launched with batch `32` and vLLM logs showed
  `gpu_memory_utilization: 0.28`; requests returned HTTP 200, and
  `danish-citizen-tests` completed successfully after the relaunch.
- The `step_200000` repair rerun completed successfully:
  `eval-00021` BFCL-v2 ended with status `0`, W&B synced
  `euroeval/en/tool-calling/bfcl-v2/tool_calling_accuracy=21.32`, and
  `average-00210` logged `467` W&B keys including `avg/overall=0.40875`.

Confidence: high from local scheduler code inspection, `py_compile`, `bash -n`,
plan metadata updates, and the live `step_200000` BFCL rerun startup logs.

## DFM6 XL-GAS2 50K Eval Scheduling

Last updated: 2026-06-20
Confidence: high
Scope: Local scheduler plan for the ongoing `dfm6-XL-gas2` training run.

The ongoing DFM6 XL gradient-accumulation run is:

```text
checkpoint_path: checkpoints/dfm6/XL-gas2
run_name:        dfm6-XL-gas2
wandb_project:   DFM5
wandb_run_id:    39ht9plp
```

The local W&B run id was verified from
`wandb/run-20260620_140018-39ht9plp/logs/debug.log`, whose config has
`run_name='dfm6-XL-gas2'`, `gradient_accumulation_steps=2`,
`checkpoint_path='checkpoints/dfm6/XL-gas2'`, and
`data.path='data/sampled_dfm6'`.

The 50K eval epoch is:

```text
50000 * 262144 / 62819933768 = 0.208647147709613
```

The eval plan was created at:

```text
logs/scheduler/dfm6_XL_gas2_step50000_vllm_main_20260620
```

with logs under:

```text
logs/eval/dfm6_XL_gas2_step50000_vllm_main_20260620
logs/dfm_evals/dfm6_XL_gas2_step50000_vllm_main_20260620
logs/euroeval/dfm6_XL_gas2_step50000_vllm_main_20260620
```

Important DFM6-specific differences from the DFM5-L wrapper:

- `--ckpt-path checkpoints/dfm6/XL-gas2`
- `--wandb-run-id 39ht9plp`
- `--wandb-run-name dfm6-XL-gas2`
- `--vllm-extra-args` uses
  `evaluation/chat_templates/gemma4_native_chat.jinja`, not
  `hrm_direct_chat.jinja`, because DFM6 was tokenized with Gemma-native chat
  rendering.
- `--no-include-report` is used because the scheduler report row currently
  regenerates the DFM5-L markdown report.
- `valeu-da` was marked `skipped`, matching the current failure-avoidance
  policy.

The launched tmux windows are:

```text
hrm-0:evaldfm6xl50
hrm-0:mondfm6xl50
```

Initial monitor state after launch:

```text
jobs done=0 running=1 ready=0 blocked_pending=208 failed=0 skipped=1 total=210
```

This means the scheduler is waiting for `step_50000` and has not started eval
work yet.

Update, 2026-06-20. Confidence: high for local plan inspection, code
inspection, and syntax checks. The first DFM6 50K plan initially had
`vllm_extra_args` set to the Gemma native chat template for DFM and EuroEval,
but standard eval used `evaluation/config/hrm_vllm_benchmarking.yaml`, whose
`prompt_mode=hrm` formats prompts with HRM direct tokens instead of Gemma
native chat turns. Because the plan was still blocked on `step_50000`, it was
patched before any eval rows could start:

```text
standard_config: evaluation/config/dfm6_vllm_benchmarking.yaml
```

`evaluation/config/dfm6_vllm_benchmarking.yaml` uses:

```text
prompt_mode: gemma_chat
chat_template_path: evaluation/chat_templates/gemma4_native_chat.jinja
```

`evaluation/engines.py` now supports `VLLMEngine(prompt_mode="gemma_chat")`,
which renders standard-eval prompts as one user message plus an assistant
generation prompt via the Gemma native Jinja template. A lightweight render
smoke produced:

```text
<bos><|turn>user\nWhat is 2+2?<turn|>\n<|turn>model\n
```

The DFM6 comparison report script is:

```bash
cd /work/dfm/HRM-Text
python scripts/generate_dfm6_eval_comparison_report.py
```

It writes `docs/dfm6.md`, with columns ordered as DFM6 checkpoints first,
then `DFM5-L 900K`, then the four Original Sapient L EMA epoch columns, then
the model-card and Qwen comparison columns reused from the DFM5 report.

Update, 2026-06-21. Confidence: high for local plan creation, plan metadata
inspection, and live scheduler monitor snapshots. The 50K eval completed with
`209` done jobs, `1` skipped job (`valeu-da`), and no failures. Four additional
DFM6 XL-GAS2 checkpoint eval plans were created and launched with indefinite
checkpoint waits:

| Checkpoint | Eval epoch | Plan dir | Port base | tmux runner | tmux monitor |
|---|---:|---|---:|---|---|
| `step_100000` | `0.41729429541922597` | `logs/scheduler/dfm6_XL_gas2_step100000_vllm_main_20260621` | `30000` | `hrm-0:evald6x100` | `hrm-0:mond6x100` |
| `step_150000` | `0.6259414431288389` | `logs/scheduler/dfm6_XL_gas2_step150000_vllm_main_20260621` | `31000` | `hrm-0:evald6x150` | `hrm-0:mond6x150` |
| `step_200000` | `0.8345885908384519` | `logs/scheduler/dfm6_XL_gas2_step200000_vllm_main_20260621` | `32000` | `hrm-0:evald6x200` | `hrm-0:mond6x200` |
| `step_250000` | `1.0432357385480648` | `logs/scheduler/dfm6_XL_gas2_step250000_vllm_main_20260621` | `33000` | `hrm-0:evald6x250` | `hrm-0:mond6x250` |

Each plan was created with:

```text
checkpoint_wait_seconds: 60
checkpoint_wait_max_seconds: 0
standard_config: evaluation/config/dfm6_vllm_benchmarking.yaml
standard_engine_backend: vllm
hrm_server_backend: vllm
hrm_vllm_native_proxy: true
vllm_extra_args: --enforce-eager --attention-backend FLASH_ATTN --chat-template /work/dfm/HRM-Text/evaluation/chat_templates/gemma4_native_chat.jinja
wandb_project: DFM5
wandb_run_id: 39ht9plp
wandb_run_name: dfm6-XL-gas2
```

Each plan has `210` jobs total: `208` blocked/pending eval-or-merge jobs,
`1` running checkpoint wait job, and `1` skipped `valeu-da` job. Distinct
`port_base` values were used to reduce collision risk if two checkpoint evals
briefly overlap.

`scripts/generate_dfm6_eval_comparison_report.py` was updated so
`docs/dfm6.md` now includes columns for `50K`, `100K`, `150K`, `200K`, and
`250K`, followed by `DFM5-L 900K`, Original Sapient L EMA epochs 1-4, and the
model-card/Qwen comparison columns.

Update, 2026-06-21. Confidence: high from local logs, W&B API inspection, and
live scheduler process checks. The completed 50K DFM6 eval initially had a W&B
visibility issue: the post-run average job logged `avg/*` metrics, while the
current DFM5/DFM6 workspace convention expects `headline_avg/*`, and the first
manual repair attempt used explicit W&B `_step=50000`, which W&B rejected
because the active training run had already advanced beyond that step.

The accepted repair command was:

```bash
cd /work/dfm/HRM-Text
python scripts/backfill_external_eval_to_wandb.py \
  --entity peter-sk-sdu \
  --project DFM5 \
  --run-id 39ht9plp \
  --run-name dfm6-XL-gas2 \
  --standard-root logs/eval/dfm6_XL_gas2_step50000_vllm_main_20260620 \
  --dfm-root logs/dfm_evals/dfm6_XL_gas2_step50000_vllm_main_20260620 \
  --euroeval-root logs/euroeval/dfm6_XL_gas2_step50000_vllm_main_20260620/step_50000 \
  --epoch 0.208647147709613 \
  --step 50000 \
  --average-prefix headline_avg \
  --log-averages
```

This logs without an explicit W&B `_step` but includes
`eval/train_step=50000`, `dfm_eval/train_step=50000`,
`euroeval/train_step=50000`, and `headline_avg/train_step=50000`.

Superseding correction later on 2026-06-21: the W&B headline panels still did
not show the 50K averages reliably after this first repair. A second explicit
average-only W&B row was logged with both historical average namespaces,
`headline_avg/*` and `avg/*`, and both epoch keys. W&B accepted the row and
showed both namespaces in run history. The 50K average values are:

```text
headline_avg/danish: 0.2906948598718148
headline_avg/english: 0.33738026773051194
headline_avg/math_code: 0.15954299972604893
headline_avg/overall: 0.26253937577612524
```

To prevent recurrence for 100K and later, `eval_scheduler/eval_scheduler/runtime.py`
now implements the scheduler `average` action by calling
`scripts/backfill_external_eval_to_wandb.py` with `--average-prefix
headline_avg --extra-average-prefix avg --log-averages`, so the final post job
logs a consolidated row containing standard, DFM, EuroEval, and headline
average metrics from the local merged artifacts under both `headline_avg/*`
and `avg/*`. `scripts/backfill_external_eval_to_wandb.py` now defines
`*/train_step` as the W&B step metric, can log additional average namespaces,
and only uses an explicit W&B history step if `--wandb-step` is provided.

Superseded/updated on 2026-06-23. Confidence: high from local plan inspection,
syntax checks, dry-run average logging, and live W&B workspace update. The
single final average job and the first suite-only split were too coarse: a
Danish headline average should not wait for unrelated English/math/standard
work, and math/code should not wait for all standard tasks after GSM8K, MATH,
HumanEval, and BFCL are complete.

The scheduler now emits independent average jobs:

- `standard-average`, `dfm-average`, and `euroeval-average` log suite-level
  metrics under `suite_avg/{standard,dfm,euroeval}` only.
- `danish-average`, `english-average`, and `math-code-average` log
  `headline_avg/{danish,english,math_code}` plus compatibility `avg/*` as soon
  as their exact producer tasks are done.
- `headline-averages` logs only `headline_avg/overall` plus `avg/overall` and
  depends on all six preceding suite and section average jobs.

The Danish average still waits for both Danish DFM metrics and Danish
EuroEval metrics, because `headline_avg/danish` is intentionally a combined
headline metric. It no longer waits for English standard tasks, English
EuroEval tasks, or math/code tasks. The W&B workspace view was refreshed as
`https://wandb.ai/peter-sk-sdu/DFM5?nw=ccnaz38y6ro` and now has a separate
`Suite Averages` section backed by `suite_avg/*`. Active/future DFM6 XL-GAS2
plans for `250K`, `300K`, `350K`, `400K`, and `450K` were migrated to this
post-eval graph. The already-completed `50K`, `100K`, `150K`, and `200K`
plans were not rewritten in place.

Superseding correction later on 2026-06-23. Confidence: high from local W&B
logging output, plan inspection, and workspace manifest. The first 250K
average recovery was unsafe because the already-running scheduler process kept
the old `run_average` implementation in memory. When the migrated
`euroeval-average` job became ready, that stale runtime ignored the new
`average_scope`/`average_prefix` metadata and logged a partial full-average
row under both old namespaces, `avg/*` and `headline_avg/*`, at W&B history
step `50148`. Those prefixes are therefore contaminated for DFM6 after 200K
and should not be used for DFM6 reporting.

Clean replacement namespaces:

- `headline_avg_v2/*`: section headline averages and overall.
- `suite_avg_v2/*`: standard/DFM/EuroEval suite averages.

Implemented code changes:

- `eval_scheduler/eval_scheduler/plan.py` now writes average metadata with
  `average_prefix=headline_avg_v2` for section/overall jobs and
  `average_prefix=suite_avg_v2` for suite jobs.
- `eval_scheduler/eval_scheduler/runtime.py` defaults to `headline_avg_v2`
  and no longer writes compatibility `avg/*` rows unless explicitly requested
  in job metadata.
- `scripts/log_dfm5_headline_averages.py` and
  `scripts/backfill_external_eval_to_wandb.py` support `--average-scope
  suites`.
- `scripts/create_dfm5_headline_workspace.py` now defaults headline panels to
  `headline_avg_v2/*` and suite panels to `suite_avg_v2/*`.

The active/future 250K, 300K, 350K, 400K, and 450K plans were patched in place
so pending average jobs use the v2 prefixes. The prematurely completed 250K
`euroeval-average` was reset to `pending`; completed eval shards were not
changed. All 250K+ scheduler/monitor processes were stopped before this
patch, so future restarts will load the patched runtime.

The correct completed 50K, 100K, 150K, and 200K averages were relogged to W&B
under the v2 prefixes with:

```bash
cd /work/dfm/HRM-Text
python scripts/log_dfm5_headline_averages.py \
  --project DFM5 --run-id 39ht9plp --run-name dfm6-XL-gas2 \
  --metric-prefix headline_avg_v2 --average-scope sections \
  --item '50000:0.208647147709613:logs/eval/dfm6_XL_gas2_step50000_vllm_main_20260620:logs/dfm_evals/dfm6_XL_gas2_step50000_vllm_main_20260620:logs/euroeval/dfm6_XL_gas2_step50000_vllm_main_20260620/step_50000' \
  --item '100000:0.41729429541922597:logs/eval/dfm6_XL_gas2_step100000_vllm_main_20260621:logs/dfm_evals/dfm6_XL_gas2_step100000_vllm_main_20260621:logs/euroeval/dfm6_XL_gas2_step100000_vllm_main_20260621/step_100000' \
  --item '150000:0.6259414431288389:logs/eval/dfm6_XL_gas2_step150000_vllm_main_20260621:logs/dfm_evals/dfm6_XL_gas2_step150000_vllm_main_20260621:logs/euroeval/dfm6_XL_gas2_step150000_vllm_main_20260621/step_150000' \
  --item '200000:0.8345885908384519:logs/eval/dfm6_XL_gas2_step200000_vllm_main_20260621:logs/dfm_evals/dfm6_XL_gas2_step200000_vllm_main_20260621:logs/euroeval/dfm6_XL_gas2_step200000_vllm_main_20260621/step_200000'

python scripts/log_dfm5_headline_averages.py \
  --project DFM5 --run-id 39ht9plp --run-name dfm6-XL-gas2 \
  --metric-prefix suite_avg_v2 --average-scope suites \
  --item '50000:0.208647147709613:logs/eval/dfm6_XL_gas2_step50000_vllm_main_20260620:logs/dfm_evals/dfm6_XL_gas2_step50000_vllm_main_20260620:logs/euroeval/dfm6_XL_gas2_step50000_vllm_main_20260620/step_50000' \
  --item '100000:0.41729429541922597:logs/eval/dfm6_XL_gas2_step100000_vllm_main_20260621:logs/dfm_evals/dfm6_XL_gas2_step100000_vllm_main_20260621:logs/euroeval/dfm6_XL_gas2_step100000_vllm_main_20260621/step_100000' \
  --item '150000:0.6259414431288389:logs/eval/dfm6_XL_gas2_step150000_vllm_main_20260621:logs/dfm_evals/dfm6_XL_gas2_step150000_vllm_main_20260621:logs/euroeval/dfm6_XL_gas2_step150000_vllm_main_20260621/step_150000' \
  --item '200000:0.8345885908384519:logs/eval/dfm6_XL_gas2_step200000_vllm_main_20260621:logs/dfm_evals/dfm6_XL_gas2_step200000_vllm_main_20260621:logs/euroeval/dfm6_XL_gas2_step200000_vllm_main_20260621/step_200000'
```

Dry-run counts before logging were complete: `18` Danish metrics, `15`
English metrics, `4` math/code metrics, `8` standard suite metrics, `11` DFM
suite metrics, and `18` EuroEval suite metrics for every checkpoint from 50K
through 200K. The refreshed clean W&B workspace is:
`https://wandb.ai/peter-sk-sdu/DFM5?nw=d4558ye9fcw`.

Follow-up on 2026-06-23. Confidence: high from local dry-runs and W&B logging
output. The same v2-prefix policy was applied to the two older comparison
runs that appear in the DFM5/DFM6 workspace:

- `original-sapient-L-dfm5-backfill-20260615`
- `dfm5-l-clean-20260619-v3`

Script changes:

- `scripts/backfill_original_sapient_l_to_dfm5.py` now rebuilds original
  Sapient L headline averages as `headline_avg_v2/*`, filters old average
  prefixes out of replayed source rows, and defines `headline_avg_v2` metrics.
- `scripts/backfill_dfm5_l_clean_wandb.py`,
  `scripts/relog_dfm5_l_clean_eval_rows.py`, and
  `scripts/append_dfm5_l_clean_from_source_wandb.py` now treat old
  `avg/*`, `headline_avg/*`, and `suite_avg/*` keys as source-only keys and
  remap them to `headline_avg_v2/*` or `suite_avg_v2/*` before logging. Their
  W&B metric definitions include only `eval`, `dfm_eval`, `euroeval`,
  `headline_avg_v2`, and `suite_avg_v2` for eval-like prefixes.

The first attempt to relog original Sapient L v2 averages used explicit W&B
history steps `81478`, `162961`, `244443`, and `325928`; W&B rejected those
rows because the resumed run's current `_step` was already `325933`. The
accepted relog omitted explicit W&B `_step` and relied on
`headline_avg_v2/epoch` plus `headline_avg_v2/train_step`, matching the DFM6
repair pattern. Four original Sapient L rows were accepted for epochs `1..4`.

For `dfm5-l-clean-20260619-v3`, average-only rows were relogged without
explicit W&B `_step` for train steps:

```text
50000, 100000, 150000, 200000, 250000, 300000, 350000, 400000, 450000,
500000, 550000, 600000, 700000, 750000, 800000, 850000, 900000
```

The local dry-run for `scripts/relog_dfm5_l_clean_eval_rows.py` on
`logs/relog_dfm5_l_clean_850k_900k_explicit_train_step_20260620.jsonl`
produced `73` rows with `0` old average keys and `18`
`headline_avg_v2/*` keys. A full audit remap check on
`logs/backfill_dfm5_l_clean_rows_v3_history650_20260619.jsonl` produced
`0` old average keys and `171` v2 average keys.

The W&B average sections were refreshed again so the panel metrics are:

- `Headline Averages`: `headline_avg_v2/{overall,danish,english,math_code}`
  over `headline_avg_v2/epoch`.
- `Suite Averages`: `suite_avg_v2/{standard,dfm,euroeval}` over
  `suite_avg_v2/epoch`.

The refreshed workspace URL is:
`https://wandb.ai/peter-sk-sdu/DFM5?nw=760qd0evtsa`.

The already-launched 100K, 150K, 200K, and 250K scheduler processes were
stopped while still in checkpoint-wait state, then relaunched with
`/home/ucloud/miniforge3/envs/hrm/bin/python` so they load the patched
scheduler runtime. This restart was repeated after adding the `avg/*`
compatibility namespace. As of the final relaunch check, each plan had
`pending=208`, `running=1`, `skipped=1`, no failures, and an active
checkpoint-wait job.

Update, 2026-06-22. Confidence: high from local plan creation, scheduler
status checks, tmux process inspection, and wait-log inspection. Four
additional DFM6 XL-GAS2 checkpoint eval plans were created and launched with
indefinite checkpoint waits:

| Checkpoint | Eval epoch | Plan dir | Port base | tmux runner | tmux monitor |
|---|---:|---|---:|---|---|
| `step_300000` | `1.2518828862576779` | `logs/scheduler/dfm6_XL_gas2_step300000_vllm_main_20260622` | `34000` | `hrm-0:evald6x300` | `hrm-0:mond6x300` |
| `step_350000` | `1.4605300339672909` | `logs/scheduler/dfm6_XL_gas2_step350000_vllm_main_20260622` | `35000` | `hrm-0:evald6x350` | `hrm-0:mond6x350` |
| `step_400000` | `1.6691771816769039` | `logs/scheduler/dfm6_XL_gas2_step400000_vllm_main_20260622` | `36000` | `hrm-0:evald6x400` | `hrm-0:mond6x400` |
| `step_450000` | `1.8778243293865167` | `logs/scheduler/dfm6_XL_gas2_step450000_vllm_main_20260622` | `37000` | `hrm-0:evald6x450` | `hrm-0:mond6x450` |

The plans match the working DFM6 vLLM settings:

```text
checkpoint_wait_seconds: 60
checkpoint_wait_max_seconds: 0
standard_config: evaluation/config/dfm6_vllm_benchmarking.yaml
standard_engine_backend: vllm
hrm_server_backend: vllm
hrm_vllm_native_proxy: true
vllm_extra_args: --enforce-eager --attention-backend FLASH_ATTN --chat-template /work/dfm/HRM-Text/evaluation/chat_templates/gemma4_native_chat.jinja
vllm_gpu_memory_utilization: 0.28
hrm_vllm_gemma_bfcl_tools: true
hrm_vllm_gemma_bfcl_tool_mode: parser
standard_batch: 64
dfm_batch: 32
ifeval_batch: 32
euroeval_batch: 32
euroeval_max_concurrent_calls: 32
judged_batch: 16
judged_max_connections: 16
judge_model: openai/gemma-4-e4b-judge
judge_server_model: unsloth/gemma-4-E4B-it
judged_vllm_gpu_memory_utilization: 0.18
govreport_max_report_chars: 9000
wandb_project: DFM5
wandb_run_id: 39ht9plp
wandb_run_name: dfm6-XL-gas2
```

Each plan has `210` jobs total: `208` pending eval-or-merge jobs, `1`
running checkpoint-wait job, and `1` skipped `valeu-da` job. The wait logs
show the expected missing-checkpoint messages for all four checkpoints, so no
eval work has started yet.

`scripts/generate_dfm6_eval_comparison_report.py` and `docs/dfm6.md` now
include future columns for `300K`, `350K`, `400K`, and `450K`.

Update, 2026-06-23. Confidence: high from local command output and W&B sync
logs. The clean v2 suite-average namespace is now backfilled for the older
comparison runs and uses epoch-level W&B x-axis labels:

- `suite_avg_v2/*` is defined against `suite_avg_v2/epoch`.
- `headline_avg_v2/*` remains defined against `headline_avg_v2/epoch`.
- Raw `eval/*`, `dfm_eval/*`, and `euroeval/*` metrics can still use their
  own eval-family x-axis fields.

Commands run from `/work/dfm/HRM-Text`:

```bash
python scripts/relog_suite_averages_v2.py original-sapient-l \
  --run-id original-sapient-L-dfm5-backfill-20260615 \
  --run-name 'original Sapient L backfilled'

python scripts/relog_suite_averages_v2.py dfm5-l-clean \
  --run-id dfm5-l-clean-20260619-v3 \
  --run-name dfm5-l-clean-20260619-v3
```

Observed sync results:

- `original-sapient-L-dfm5-backfill-20260615`: 4 suite-average rows, epochs
  `1.0` through `4.0`, with counts `standard=8`, `dfm=11`, `euroeval=18`.
- `dfm5-l-clean-20260619-v3`: 17 suite-average rows for train steps `50K`
  through `900K`, excluding `650K` because the clean average series does not
  have a complete 650K row in the local audit inputs; each logged row has
  counts `standard=8`, `dfm=11`, `euroeval=18`.

The relog helper is `scripts/relog_suite_averages_v2.py`. The DFM5 clean
backfill/relog helper scripts now define v2 average namespaces against the
epoch metric so future average rows line up with the workspace's epoch x-axis.

The eval scheduler monitor now shows a `blocked pending` section. A verified
snapshot for `logs/scheduler/dfm6_XL_gas2_step250000_vllm_main_20260621`
reported `blocked_pending=4` and correctly explained that the DFM average,
Danish average, and headline average were blocked behind the failed
`generative_talemaader` merge. This is implemented in
`eval_scheduler/eval_scheduler/monitor.py` and documented in
`eval_scheduler/README.md`.

## Current DFM6 Evaluation Contract

Last updated: 2026-06-24
Confidence: high
Scope: The current scheduler/evaluation convention for DFM6 checkpoint sweeps.

DFM6 checkpoint evaluations are scheduled through `eval_scheduler` as a DAG per
checkpoint. The intended checkpoint order is independent: a single scheduler
plan may contain multiple checkpoint subgraphs, each guarded by its own
`wait_checkpoint` row and using distinct export/log roots and port bases.

Per checkpoint, the sequence is:

1. `wait_checkpoint`: wait until `model_<tag>.safetensors` and all expected
   `carry_<tag>.<rank>.pt` files exist.
2. `export_hf`: export the EMA checkpoint to an HF/vLLM directory.
3. Run standard eval shards, DFM eval shards, DFM IFEval-DA shards, and
   EuroEval tasks. These can run as soon as the export is ready.
4. Merge rows run per task as soon as that task's shards are done.
5. Suite averages run as soon as their suite is complete:
   `standard-average`, `dfm-average`, and `euroeval-average` log to
   `suite_avg_v2/*`.
6. Section averages run as soon as their section producers are complete:
   `danish-average`, `english-average`, and `math-code-average` log to
   `headline_avg_v2/*`.
7. `headline-averages` logs `headline_avg_v2/overall` only after the three
   section averages and three suite averages are done.
8. The report job waits for `headline-averages`.

W&B x-axis policy:

- Raw standard metrics use the raw eval namespace, with `eval/epoch` and
  `eval/train_step` present.
- Raw DFM metrics use `dfm_eval/epoch` and `dfm_eval/train_step`.
- Raw EuroEval metrics use `euroeval/epoch` and `euroeval/train_step`.
- Clean section/headline averages use `headline_avg_v2/epoch` as the W&B step
  metric.
- Clean suite averages use `suite_avg_v2/epoch` as the W&B step metric.
- The old `avg/*`, `headline_avg/*`, and `suite_avg/*` namespaces are stale for
  DFM6 reporting and should not be used in panels.

Current vLLM/GPU settings while co-running with DFM6 XL-GAS2 training:

```text
standard_engine_backend: vllm
hrm_server_backend: vllm
hrm_vllm_native_proxy: true
hrm_vllm_gemma_bfcl_tools: true
hrm_vllm_gemma_bfcl_tool_mode: parser
vllm_extra_args: --enforce-eager --attention-backend FLASH_ATTN --chat-template /work/dfm/HRM-Text/evaluation/chat_templates/gemma4_native_chat.jinja
vllm_gpu_memory_utilization: 0.28
standard_batch: 64
dfm_batch: 32
ifeval_batch: 32
euroeval_batch: 32
euroeval_max_concurrent_calls: 32
judged_batch: 16
judged_max_connections: 16
judge_model: openai/gemma-4-e4b-judge
judge_server_model: unsloth/gemma-4-E4B-it
judged_vllm_gpu_memory_utilization: 0.18
govreport_max_report_chars: 9000
max_retries: 5
fixed_retry_batch: true
```

`generative_talemaader` is the only current task that starts a colocated local
judge server. Its batch and max-connections remain `16`; the working fix for
judge startup OOM is lowering only the judged-task HRM vLLM memory utilization
to `0.18`.

Known skip:

- `valeu-da` is marked `skipped` in DFM6 sweeps because the current EuroEval
  task can abort the whole run on invalid labels. It is excluded from
  `suite_avg_v2/euroeval` and `headline_avg_v2/danish`.

Update, 2026-06-23. Confidence: high from local plan inspection. A single
multi-checkpoint campaign plan was created for the next five 50K-spaced
checkpoints:

```text
plan_dir: logs/scheduler/dfm6_XL_gas2_steps300k_500k_vllm_main_20260623
checkpoints: step_300000, step_350000, step_400000, step_450000, step_500000
eval_epochs: 1.2518828862576779, 1.4605300339672909, 1.6691771816769039,
             1.8778243293865167, 2.0864714770961296
status after creation: pending=1080, skipped=5, total=1085
skipped rows: one valeu-da row per checkpoint
```

The plan validation showed `generative_talemaader` rows with
`initial_batch=16`, `max_connections=16`,
`vllm_gpu_memory_utilization=0.18`, and `fixed_retry_batch=true`. The average
rows use `suite_avg_v2` for suite averages and `headline_avg_v2` for section
and overall averages, with `headline-averages` depending on the six prior
average rows.

The campaign scheduler was launched in tmux:

```text
runner:  hrm-0:8  evald6x300500
monitor: hrm-0:9  mond6x300500
```

Initial live monitor state after launch: `done=0`, `running=4`, `ready=1`,
`blocked_pending=1075`, `failed=0`, `skipped=5`, `total=1085`. The running
jobs are checkpoint waits, not GPU eval jobs; at launch the local checkpoint
directories for `step_300000` through `step_500000` were not yet present.

Update, 2026-06-24. Confidence: high from local scheduler logs, plan state,
and code inspection. The 300K eval itself did not fail: `step_300000` exported
successfully at `2026-06-24T02:25:47+02:00`, all eval shards completed, and
the plan had no failed jobs. Progress stopped after the last 300K DFM eval
ended at `2026-06-24T04:05:27+02:00` because the scheduler's four generic
non-GPU slots were occupied by long-running future `wait_checkpoint` jobs for
350K, 400K, 450K, and 500K. Ready 300K merge/average rows also require
non-GPU slots, so they were starved behind sleeping checkpoint waits.

The runner process also left no normal `RUN_END`, `BLOCKED`, `STOPPED`, or
traceback entry at that time, so an exact process-exit reason was not recorded.
To prevent both problems going forward:

- `eval_scheduler/eval_scheduler/runtime.py` now gives `WAIT_CHECKPOINT` jobs
  their own checkpoint-wait slot pool
  (`EVAL_SCHEDULER_CHECKPOINT_WAIT_SLOTS`, default `8`) instead of consuming
  the generic merge/average/report non-GPU slots.
- Unexpected worker exceptions are now logged as `RUN_EXCEPTION <job_id> ...`
  in `status.tsv` and mark the affected job failed instead of taking down the
  whole runner and leaving stale `running` rows.

Operational repair performed on 2026-06-24:

```bash
cd /work/dfm/HRM-Text
/home/ucloud/miniforge3/envs/hrm/bin/python -m eval_scheduler plan reset-running \
  --plan-dir logs/scheduler/dfm6_XL_gas2_steps300k_500k_vllm_main_20260623

/home/ucloud/miniforge3/envs/hrm/bin/python -m eval_scheduler stop \
  --plan-dir logs/scheduler/dfm6_XL_gas2_steps300k_500k_vllm_main_20260623
```

The runner was then relaunched in `hrm-0:8` with the patched runtime. Verified
live state after relaunch: `done=216`, `running=4`, `ready=0`,
`blocked_pending=860`, `failed=0`, `skipped=5`, where the four running jobs
are checkpoint waits for 350K through 500K. 300K is complete through its report
row.

Update, 2026-06-24. Confidence: high from local config, export, and eval-log
inspection. DFM6 standard, DFM, and EuroEval vLLM evaluations are intended to
use the Gemma-native chat template consistently:

- Standard vLLM evals use `evaluation/config/dfm6_vllm_benchmarking.yaml`,
  `prompt_mode: gemma_chat`, and
  `evaluation/chat_templates/gemma4_native_chat.jinja`.
- DFM/EuroEval vLLM server jobs launch vLLM with
  `--chat-template /work/dfm/HRM-Text/evaluation/chat_templates/gemma4_native_chat.jinja`.
- `evaluation/chat_templates/gemma4_native_chat.jinja` and
  `data_io/chat_templates/gemma4_native_chat.jinja` are byte-identical
  (`sha256=33204f1acb5bd0002713e16a593847f24ceeafe711ed88bda2a352dc996a3373`).

However, the DFM6 HF export currently lacks usable EOS metadata for the Gemma
turn-end token. For `exports/dfm6_XL_gas2_step_300000_ema_hf`, Transformers
reports `eos_token=None`, while the Gemma tokenizer maps `<turn|>` to token id
`106`. The DFM6 training tokenizer path renders full assistant targets with
the assistant content followed by `<turn|>`, but vLLM is not automatically
stopping at token `106` unless the request/export supplies it as a stop token.

Observed symptom at 300K:

- DROP is a real low score, not a missing metric: `eval/DROP/f1=0.086625`
  versus DFM5-L 300K `eval/DROP/f1=0.74645`.
- DFM MultiWikiQA 300K has `f1/mean=0.354059...` but
  `exact_match/mean=0.000488...`.
- Raw MultiWikiQA predictions often start with the right short answer but then
  continue with newline-separated junk or alternative answers until
  `max_gen_toks=32`; nearly every sampled 300K MultiWikiQA output contained a
  newline. DFM5-L on the same samples usually stopped after the short answer.

Interpretation: the bad short-answer/extractive scores are not strong evidence
that the model cannot read the prompt or that the Gemma template is missing.
They are at least partly a serving/export stopping issue. Multiple-choice tasks
are less sensitive to this because their scoring usually extracts a choice,
whereas DROP and MultiWikiQA exact/F1 are punished heavily by trailing text.

Next fix to test: make the DFM6 HF export and/or eval server requests treat
`<turn|>` token id `106` as the generation stop token, and rerun a small
DROP/MultiWikiQA smoke with saved generations before relogging full metrics.

Fix applied later on 2026-06-24. Confidence: high from local file edits and
export verification.

- `conversion/convert_to_hf.py` now recognizes DFM6/Gemma
  `template_mode: jinja_chat_template` metadata and writes
  `bos_token_id=2`, `eos_token_id=106`, and `pad_token_id=0` into
  `config.json`.
- The same converter now sets tokenizer special tokens to `<bos>`, `<turn|>`,
  and `<pad>`, and carries the configured Jinja chat template into the exported
  tokenizer when the template path is available.
- `evaluation/config/dfm6_vllm_benchmarking.yaml` now also passes
  `generation_config.stop_token_ids: [106]` so standard offline vLLM evals stop
  at Gemma `<turn|>` even if an old export is accidentally used.
- Existing local DFM6 exports for `step_50000`, `step_100000`, `step_150000`,
  `step_200000`, `step_250000`, and `step_300000` were refreshed with
  `conversion/convert_to_hf.py --config-only`; model weights were not rewritten.

Verification:

```text
AutoTokenizer.from_pretrained("exports/dfm6_XL_gas2_step_300000_ema_hf"):
  bos <bos> 2
  eos <turn|> 106
  pad <pad> 0
  chat_template True
config.json:
  bos_token_id 2
  eos_token_id 106
  pad_token_id 0
```

Affected-eval assessment:

- Highest-risk already-logged DFM6 metrics: tasks whose scorer consumes the
  full generated string or exact short answer, especially DROP, DFM
  MultiWikiQA, EuroEval `multi-wiki-qa-da`, EuroEval SQuAD-like reading
  comprehension, DFM/standard GovReport, DFM/standard NordjyllandNews, WMT24++
  en-da, GEC DALA, HumanEval/code generation, and other generative EuroEval
  summarization/QA tasks.
- Lower-risk but still exposed: single-label/classification/MCQ tasks such as
  MMLU, ARC, HellaSwag, Winogrande, BoolQ, PIQA, Danish citizen tests, DALA,
  and sentiment/NER-style EuroEval tasks. These usually use one-token outputs
  or label extraction, so missing EOS is less likely to dominate the score.

Additional export/eval fix on 2026-06-24. Confidence: high from local command
output and smoke tests. Transformers warned that the exported Gemma tokenizer
needed `fix_mistral_regex=True`; loading with and without the flag produced
different token IDs for a punctuation/spacing smoke string. `conversion/convert_to_hf.py`
now persists `fix_mistral_regex: true` into DFM6
`tokenizer_config.json` for `template_mode: jinja_chat_template` exports. The
existing 300K HF export was refreshed with:

```bash
cd /work/dfm/HRM-Text
/home/ucloud/miniforge3/envs/hrm/bin/python conversion/convert_to_hf.py \
  --ckpt_path checkpoints/dfm6/XL-gas2 \
  --ckpt_tag step_300000 \
  --ckpt_use_ema true \
  --out_dir exports/dfm6_XL_gas2_step_300000_ema_hf \
  --config-only
```

Verification after refresh:

```text
AutoTokenizer.from_pretrained("exports/dfm6_XL_gas2_step_300000_ema_hf"):
  bos_token_id=2 eos_token_id=106 pad_token_id=0 fix_mistral_regex=True
```

DFM6 eval contract smoke, 2026-06-24. Confidence: high from local smoke output.
Added `scripts/smoke_dfm6_eval_contracts.py`. It checks, before a full eval:

- exported tokenizer/config metadata: BOS `2`, EOS `<turn|>` id `106`, PAD
  `0`, `fix_mistral_regex=True`, and a present chat template;
- byte-identical eval/data Gemma templates and a rendered prompt ending at the
  `<|turn>model` generation marker;
- standard task set and task-specific generation limits in
  `evaluation/config/dfm6_vllm_benchmarking.yaml`;
- DFM task configs, DFM IFEval 32-shard config, GovReport truncation, and
  judged Talemaader settings;
- full scheduler plan contract for standard, DFM, and EuroEval jobs using vLLM,
  native proxy, Gemma BFCL parser mode, FlashAttention, EuroEval concurrency
  `32`, and the new `suite_avg_v2`/`headline_avg_v2` dependency ordering.

Smoke command:

```bash
cd /work/dfm/HRM-Text
/home/ucloud/miniforge3/envs/hrm/bin/python scripts/smoke_dfm6_eval_contracts.py
```

Latest passing output:

```text
DFM6 eval smoke passed. Wrote /work/dfm/HRM-Text/logs/smoke/dfm6_eval_contracts_20260624_080712.json
Standard tasks: 10
DFM tasks: 10 + 32 IFEval shards
EuroEval groups: 20 (valeu-da skipped by plan)
```

Clean 300K stop-fix evaluation launch, 2026-06-24. Confidence: high from
created plan, spot-checked metadata, and live scheduler status. A separate
300K eval was launched into its own W&B run in project `DFM5`, leaving prior
possibly affected 300K metrics untouched:

```text
plan_dir:  logs/scheduler/dfm6_XL_gas2_step300000_stopfix_clean_20260624
standard:  logs/eval/dfm6_XL_gas2_step300000_stopfix_clean_20260624
dfm:       logs/dfm_evals/dfm6_XL_gas2_step300000_stopfix_clean_20260624
euroeval:  logs/euroeval/dfm6_XL_gas2_step300000_stopfix_clean_20260624
wandb:     project=DFM5 run_id=dfm6-xl-gas2-300k-stopfix-clean-20260624
tmux:      hrm-0:10 eval300stopfix, hrm-0:11 mon300stopfix
```

The plan has `216` pending rows plus one skipped `valeu-da` row at creation:
`85` standard shards, `51` DFM shards, `32` DFM IFEval shards, `20` EuroEval
rows including two batched IFEval rows, merges, suite averages, section
averages, overall headline average, and report generation. At startup,
checkpoint wait and HF export completed immediately, then the first eight
EuroEval jobs started with batch `32` and no failures.

Clean 300K stop-fix W&B repair, 2026-06-24. Confidence: high from local
scheduler status, merged metric files, and W&B API history queries. Supersedes
the earlier same-day diagnosis that focused on train-step axes. The DFM5
workspace eval and average panels use epoch axes, so `*/epoch` must remain the
canonical W&B step metric. `*/train_step` is useful metadata, but must not
replace `*/epoch` as the default metric axis. The
`dfm6-XL-gas2 300K stopfix clean eval` scheduler finished cleanly:
`done=216`, `failed=0`, `skipped=1`. Missing W&B chart points for Danish
headline average, GEC DaLA exact match, EuroEval ScaLA-da macro F1, and BoolQ
accuracy were not missing local eval results. They were W&B history-row issues:
some repair attempts updated summary values or axis-only rows without creating
plottable rows containing both the metric value and the relevant `*/epoch`.

Local verified values:

```text
headline_avg_v2/danish = 0.5102304507375527
dfm_eval/gec_dala/exact_match/mean = 0.4345703125
euroeval/da/linguistic-acceptability/scala-da/macro_f1 = 51.702315412643784
eval/BoolQ/acc = 0.8495
```

The 300K clean run was repaired with:

```bash
cd /work/dfm/HRM-Text
/home/ucloud/miniforge3/envs/hrm/bin/python scripts/backfill_external_eval_to_wandb.py \
  --project DFM5 \
  --run-id dfm6-xl-gas2-300k-stopfix-clean-20260624 \
  --run-name 'dfm6-XL-gas2 300K stopfix clean eval' \
  --standard-root logs/eval/dfm6_XL_gas2_step300000_stopfix_clean_20260624 \
  --dfm-root logs/dfm_evals/dfm6_XL_gas2_step300000_stopfix_clean_20260624 \
  --euroeval-root logs/euroeval/dfm6_XL_gas2_step300000_stopfix_clean_20260624/step_300000 \
  --epoch 1.2518828862576779 \
  --step 300000

/home/ucloud/miniforge3/envs/hrm/bin/python scripts/backfill_external_eval_to_wandb.py \
  --project DFM5 \
  --run-id dfm6-xl-gas2-300k-stopfix-clean-20260624 \
  --run-name 'dfm6-XL-gas2 300K stopfix clean eval' \
  --standard-root logs/eval/dfm6_XL_gas2_step300000_stopfix_clean_20260624 \
  --dfm-root logs/dfm_evals/dfm6_XL_gas2_step300000_stopfix_clean_20260624 \
  --euroeval-root logs/euroeval/dfm6_XL_gas2_step300000_stopfix_clean_20260624/step_300000 \
  --epoch 1.2518828862576779 \
  --step 300000 \
  --log-averages \
  --averages-only \
  --average-prefix headline_avg_v2 \
  --average-scope sections

/home/ucloud/miniforge3/envs/hrm/bin/python scripts/backfill_external_eval_to_wandb.py \
  --project DFM5 \
  --run-id dfm6-xl-gas2-300k-stopfix-clean-20260624 \
  --run-name 'dfm6-XL-gas2 300K stopfix clean eval' \
  --standard-root logs/eval/dfm6_XL_gas2_step300000_stopfix_clean_20260624 \
  --dfm-root logs/dfm_evals/dfm6_XL_gas2_step300000_stopfix_clean_20260624 \
  --euroeval-root logs/euroeval/dfm6_XL_gas2_step300000_stopfix_clean_20260624/step_300000 \
  --epoch 1.2518828862576779 \
  --step 300000 \
  --log-averages \
  --averages-only \
  --average-prefix suite_avg_v2 \
  --average-scope suites
```

Future-proofing patch, 2026-06-24. Confidence: high from local `py_compile`
and `bash -n` validation. The merge/log path now carries explicit train-step
metadata while keeping epoch as the canonical W&B plotting axis:

- `scripts/merge_standard_eval_shards.py` accepts `--step`, logs
  `eval/train_step`, and still defines raw `eval/*` metrics against
  `eval/epoch`.
- `scripts/merge_dfm_eval_shards.py` accepts `--step`, logs
  `dfm_eval/train_step`, and still defines raw `dfm_eval/*` metrics against
  `dfm_eval/epoch`.
- `scripts/merge_ifeval_da_shards.py` accepts `--step`, logs
  `dfm_eval/train_step`, and still defines raw DFM IFEval metrics against
  `dfm_eval/epoch`.
- `scripts/log_euroeval_to_wandb.py` accepts `--step`, logs
  `euroeval/train_step`, and still defines EuroEval metrics against
  `euroeval/epoch`.
- `eval_scheduler/eval_scheduler/runtime.py` infers the eval step from
  `metadata.eval_step` or `ckpt_tag=step_N` and passes it to all merge/log
  jobs, including shell-run EuroEval jobs through `EVAL_STEP`.
- `scripts/run_euroeval_on_checkpoint.sh` and
  `scripts/run_batched_ifeval_on_checkpoint.sh` pass `EVAL_STEP` through to
  `log_euroeval_to_wandb.py`.

Manual 300K stop-fix repair rows, 2026-06-24. Confidence: high from W&B API
`scan_history`. The four missing panels were repaired by appending small,
explicit epoch-based rows to run
`dfm6-xl-gas2-300k-stopfix-clean-20260624`. W&B history now contains rows with
the metric and its epoch:

```text
eval/BoolQ/acc + eval/epoch
dfm_eval/gec_dala/exact_match/mean + dfm_eval/epoch
euroeval/da/linguistic-acceptability/scala-da/macro_f1 + euroeval/epoch
headline_avg_v2/danish + headline_avg_v2/epoch
```

Clean 300K BFCL and Talemaader diagnosis, 2026-06-24. Confidence: high for
local metric values and logs; medium for capability interpretation. The low
BFCL-v2 score is not currently an obvious scheduler/proxy failure. The
EuroEval BFCL job used the vLLM native proxy with Gemma-native BFCL tools
enabled. `proxy_payloads.jsonl` showed 257 requests, 242 adapted responses,
and many requests with OpenAI tool schemas. The merged metric was:

```text
euroeval/en/tool-calling/bfcl-v2/tool_calling_accuracy = 0.92
```

EuroEval reports this on its usual 0-100 scale, so this is about `0.92%`.
There were no failed instances in `raw_results`. The likely cause is model
capability at 300K: BFCL requires exact function choice, JSON argument
extraction, and sometimes multi-call planning. Earlier smoke tests showed the
parser route can choose a function but may produce empty or incomplete args.

Talemaader was also locally complete but scored:

```text
dfm_eval/generative-talemaader/model_graded_fact/accuracy = 0.0
```

The 808 outputs were fluent Danish but often literal, generic, or only
partially correct idiom explanations. Example failure modes included treating
`være høj i hatten` as literally high/proud, explaining
`danse efter nogens pibe` as merely following an example, and giving vague
paraphrases. Some near-correct answers, such as `der er ugler i mosen`, may be
judge false negatives because the model judge is strict, but the sample review
does not support a pure judging/plumbing explanation for `0/808`.

DFM6 XL-GAS2 clean stop-fix backfill scheduler, 2026-06-24. Confidence: high
from local scheduler status and inspected `plan.tsv` metadata. The active
main-run 300K-500K scheduler was stopped so earlier DFM6 checkpoints could be
evaluated into the clean stop-fix W&B run
`dfm6-xl-gas2-300k-stopfix-clean-20260624`. A first combined 50K-500K plan was
discarded because 300K had an existing HF export and began running immediately,
which did not match the intended prepend semantics. The corrected plan excludes
300K, since the clean 300K eval already exists, and schedules:

```text
50K, 100K, 150K, 200K, 250K, then 350K, 400K, 450K, 500K
```

Plan directory:

```text
logs/scheduler/dfm6_XL_gas2_steps50k_250k_then350k_500k_stopfix_clean_20260624
```

The later checkpoint waits for 350K-500K are explicitly gated on
`report-01085`, the 250K report job, so the prepended 50K-250K evals finish
before the remaining later checkpoints start. The plan logs to the clean run
and uses the established DFM6 vLLM settings: `vllm_gpu_memory_utilization=0.28`,
EuroEval batch/concurrency `32`, Gemma-native BFCL tool parser mode enabled,
ValEU-da skipped, `govreport_max_report_chars=9000`, and epoch-based W&B axes
with `train_step` as auxiliary metadata.

Launch commands:

```bash
cd /work/dfm/HRM-Text
/home/ucloud/miniforge3/envs/hrm/bin/python -m eval_scheduler run \
  --plan-dir logs/scheduler/dfm6_XL_gas2_steps50k_250k_then350k_500k_stopfix_clean_20260624 \
  --gpus 0,1,2,3,4,5,6,7

/home/ucloud/miniforge3/envs/hrm/bin/python -m eval_scheduler monitor \
  --plan-dir logs/scheduler/dfm6_XL_gas2_steps50k_250k_then350k_500k_stopfix_clean_20260624 \
  --gpus 0,1,2,3,4,5,6,7 \
  --interval 30
```

As launched, the scheduler is in tmux pane `hrm-0:8` and the monitor in
`hrm-0:9`. Initial status after launch was `pending=1926`, `running=8`,
`done=10`, `failed=0`, `skipped=9`, with the first 50K EuroEval wave active.

DFM6 judged-task scheduler trap, 2026-06-24. Confidence: high from
`dfm-evals.log` tracebacks and inspected plan metadata. The 50K-250K then
350K-500K clean backfill scheduler exited with `RUN_END` because it reached a
blocked state, not because the scheduler process crashed. All `40` failures
were `generative_talemaader` shards for 50K, 100K, 150K, 200K, and 250K after
retries. The common traceback was:

```text
ValueError: Placeholder `{{judge_model}}` in `tasks[0].args[1]` for suite
`hrm_danish_generative_talemaader` requires `--judge-model`.
```

Root cause: the replacement plan was created without the known-good judged
task settings. For DFM6 plans that include `generative_talemaader`, always pass
the judge settings at plan creation time:

```bash
--judge-model openai/gemma-4-e4b-judge \
--judge-server-model unsloth/gemma-4-E4B-it \
--judge-server-dtype bfloat16 \
--judge-server-attn-implementation sdpa \
--judge-server-max-new-tokens 64 \
--judged-batch 16 \
--judged-vllm-gpu-memory-utilization 0.18
```

These match the working 300K stop-fix plan. Do not rely on scheduler defaults
for this: `runtime.py` has a fallback judge model for some code paths, but
`dfm-evals` suite placeholder resolution requires an explicit `judge_model` in
the job metadata before the eval command starts.

Superseded 2026-06-27: older notes said to use `--judged-batch none` and
`--judged-vllm-gpu-memory-utilization none`. The current CLI rejects
`--judged-batch none`; local inspection of the successful `step_500000`
Talemaader rows showed the actual working values were batch `16` and
per-judged-task vLLM utilization `0.18`. Use those explicit values for future
DFM6 plans. Confidence: high from the successful 500K plan metadata and the
failed local CLI invocation.

The live plan was repaired in place by patching every
`family=dfm`, `name=generative_talemaader`, `action=eval_dfm` row to include:

```json
{
  "judge_model": "openai/gemma-4-e4b-judge",
  "judge_server_model": "unsloth/gemma-4-E4B-it",
  "judge_server_dtype": "bfloat16",
  "judge_server_attn_implementation": "sdpa",
  "judge_server_max_new_tokens": 64
}
```

Then only the failed Talemaader rows were reset to `pending` with `attempt=0`.
The repair backup is:

```text
logs/scheduler/dfm6_XL_gas2_steps50k_250k_then350k_500k_stopfix_clean_20260624/plan.tsv.bak_judge_fix_20260624
```

After the repair, status was `done=1015`, `pending=929`, `failed=0`,
`skipped=9`, and all Talemaader eval rows had explicit judge metadata.

Evaluation startup-overhead analysis, 2026-06-26. Confidence: high from local
`plan.tsv`, `status.tsv`, and per-job eval logs for the clean stopfix scheduler.
The last three completed full evaluations in
`logs/scheduler/dfm6_XL_gas2_steps50k_250k_then350k_500k_stopfix_clean_20260624`
were `step_350000`, `step_400000`, and `step_450000`. A common-denominator
per-job aggregation across `standard`, `dfm`, and `euroeval` jobs was written to:

```text
logs/analysis/eval_startup_common_last3_dfm6_stopfix.csv
logs/analysis/eval_startup_common_last3_dfm6_stopfix_summary.tsv
```

The aggregation uses scheduler START/END as the common duration source and a
best-effort startup proxy from scheduler START to first observable vLLM
generation/API work. DFM and EuroEval server jobs have explicit lifecycle
markers; standard eval jobs use in-process vLLM markers, so this is suitable
for comparative bottleneck analysis but should not be treated as a perfect
server-ready metric.

Observed post-export full-eval wall time was stable: `step_350000` took about
`76.3` minutes, `step_400000` about `75.3` minutes, and `step_450000` about
`75.5` minutes. Per checkpoint, standard evals span about `46` minutes, DFM
evals about `70` minutes, and EuroEval about `11` minutes, with suites
overlapping under the scheduler. Startup/load overhead is a large fraction of
many short DFM and EuroEval jobs, but MATH dominates total standard GPU time
despite lower per-job startup fraction.

DFM6 XL-GAS2 550K/600K eval scheduler, 2026-06-27. Confidence: high from local
plan creation and scheduler status. Server reuse was considered but not pursued
because the expected wall-clock saving was only about `8-12` minutes per
checkpoint. A separate scheduler plan was created for `step_550000` and
`step_600000` using the same clean DFM6 vLLM settings as the completed 500K
run.

Plan directory:

```text
logs/scheduler/dfm6_XL_gas2_steps550k_600k_stopfix_clean_20260627
```

The plan logs to the existing clean W&B run
`dfm6-xl-gas2-300k-stopfix-clean-20260624` / `dfm6-XL-gas2 300K stopfix clean
eval`, includes checkpoint waits and HF export rows, uses vLLM + FA4 with the
Gemma-native chat template, logs epoch x-axis values, and keeps the known-good
judged Talemaader settings: batch `16`, judge `openai/gemma-4-e4b-judge`,
local judge server `unsloth/gemma-4-E4B-it`, and judged-task vLLM utilization
`0.18`.

Checkpoint epoch values:

```text
step_550000 -> eval_epoch 2.2951186248057427
step_600000 -> eval_epoch 2.5037657725153557
```

Plan creation summary:

```text
average                      14
eval_dfm                    102
eval_dfm_ifeval              64
eval_euroeval                36
eval_euroeval_batched_ifeval  4
eval_standard               170
export_hf                     2
merge_dfm                    20
merge_ifeval                  2
merge_standard               16
report                        2
wait_checkpoint               2
status:pending              432
status:skipped                2
```

Launch commands:

```bash
cd /work/dfm/HRM-Text
/home/ucloud/miniforge3/envs/hrm/bin/python -m eval_scheduler run \
  --plan-dir logs/scheduler/dfm6_XL_gas2_steps550k_600k_stopfix_clean_20260627 \
  --gpus 0,1,2,3,4,5,6,7

/home/ucloud/miniforge3/envs/hrm/bin/python -m eval_scheduler monitor \
  --plan-dir logs/scheduler/dfm6_XL_gas2_steps550k_600k_stopfix_clean_20260627 \
  --gpus 0,1,2,3,4,5,6,7 \
  --interval 30
```

DFM6 XL-GAS2 650K/700K/750K eval scheduler extension, 2026-06-28. Confidence:
high from local `plan.tsv` inspection and `eval_scheduler status`. The existing
live scheduler plan
`logs/scheduler/dfm6_XL_gas2_steps550k_600k_stopfix_clean_20260627` was
extended in place with full checkpoint subgraphs for `step_650000`,
`step_700000`, and `step_750000`. The extension duplicated the tuned
`step_600000` subgraph instead of using `plan create --append`, because the
existing plan has per-task batch settings that are more specific than the
uniform CLI defaults. Statuses and attempts were reset for the copied jobs;
the known skipped `valeu-da` rows remain skipped.

Added epoch x-axis values:

```text
step_650000 -> eval_epoch 2.7124129202249687
step_700000 -> eval_epoch 2.9210600679345817
step_750000 -> eval_epoch 3.1297072156441947
```

Post-extension scheduler status showed `1085` total jobs:

```text
pending=860 running=4 done=216 failed=0 skipped=5
active waits:
  step_600000
  step_650000
  step_700000
  step_750000
```

The appended jobs preserve the same W&B target
`DFM5/dfm6-xl-gas2-300k-stopfix-clean-20260624`, vLLM + FA4 settings, Gemma
native chat template, local judge settings, and tuned batches as `step_600000`.
The plan directory name still says `steps550k_600k`; it is now logically the
550K-750K scheduler.

DFM6 XL-GAS2 math invalid investigation, 2026-06-27. Confidence: high from
local tokenizer inspection, saved-generation probes, and merged metrics. The
DFM6 Gemma export has `eos_token='<turn|>'` and `eos_token_id=106`, so the
standard eval setting `stop_token_ids: [106]` matches the exported tokenizer.
The Gemma-native eval template renders ordinary non-thinking prompts as:

```text
<bos><|turn>user
...prompt...<turn|>
<|turn>model
```

It does not inject a prompt-side thinking marker when `enable_thinking=False`.
The explicit Gemma thinking token `<|think|>` is token id `98`, while the model
often emits plain XML-like `<think>` as three normal tokens (`<`, `think`, `>`).

The completed `step_500000` standard eval reported:

```text
eval/MATH/acc     = 0.32640034
eval/MATH/invalid = 0.21579308
eval/GSM8k/acc    = 0.83775504
eval/GSM8k/invalid= 0.05761782
eval/MMLU/acc     = 0.5423
eval/MMLU/invalid = 0.046975
```

MATH invalids mean `evaluation/benchmarks.py::MATH.compute_metrics` did not
find `\boxed{...}` in the scored generation. The scorer still tries
`math_verify` on the whole text, so `invalid` is primarily a formatting/completion
flag, not necessarily mathematical wrongness.

A saved-generation MATH probe at `step_500000` with the production Gemma chat
template and stop id but a shorter cap (`max_tokens=512`, 8 samples) produced
`acc=0.25`, `invalid=0.50`. The invalid examples were mostly cut off
mid-reasoning before a boxed final answer. The generations did not contain
`<turn|>` leakage, and the prompt did not include thinking markers. Some valid
generations nevertheless emitted learned `</think><answer>...` sections before
the final boxed answer. Probe artifacts:

```text
logs/analysis/dfm6_step500000_math_invalid_probe/math_probe_512.yaml
logs/analysis/dfm6_step500000_math_invalid_probe/generations_512/MATH.generations.jsonl
```

For MMLU, invalids are a different issue. `MMLU` inherits the standard MCQ
generation override `max_tokens=1`, and `MMLU.compute_metrics` accepts only an
exact stripped `A/B/C/D`. The high-invalid math/logical subjects are caused by
the model beginning a reasoning trace instead of the letter. In a probe of 12
examples per subject using the same Gemma chat template:

```text
abstract_algebra          inv1=12/12, 4-token prefix always "<think>\n"
college_mathematics       inv1=12/12, 4-token prefix always "<think>\n"
high_school_mathematics   inv1=11/12, 4-token prefix usually "<think>\n"
formal_logic              inv1= 6/12, mixed "<think>\n" and "Let's ..."
elementary_mathematics    inv1= 0/12
college_physics           inv1= 1/12
```

Adding a strict user-prefix instruction (`Answer with exactly one letter...
Do not write reasoning. Do not write <think>.`) helped formal logic but did not
solve the harder math subjects:

```text
abstract_algebra          inv1=8/8
college_mathematics       inv1=6/8
high_school_mathematics   inv1=5/8
formal_logic              inv1=1/8
```

Probe artifacts:

```text
logs/analysis/dfm6_step500000_math_invalid_probe/run_mmlu_probe.py
logs/analysis/dfm6_step500000_math_invalid_probe/mmlu_probe/mmlu_math_probe.jsonl
logs/analysis/dfm6_step500000_math_invalid_probe/run_mmlu_prompt_variant_probe.py
logs/analysis/dfm6_step500000_math_invalid_probe/mmlu_probe/mmlu_prompt_variant_probe.jsonl
```

Working interpretation: the MATH freeform invalids are mostly long reasoning
that fails to terminate with a boxed answer before the token cap. The MMLU
math-subset invalids are caused by a learned `<think>`/reasoning-output habit
under Gemma chat prompting, which conflicts with the one-token MCQ evaluator.
This is related to the Gemma-template migration in the sense that DFM6 uses the
Gemma chat prompt path, but the immediate issue is not a wrong EOS token or
template-injected thinking token. Future fixes to test separately from official
score reporting: add a task-specific answer-format instruction for MATH, allow
MCQ math subsets enough tokens to finish a short reasoning trace and extract the
final letter, or add a logits/grammar constraint for MCQ tasks if we want a pure
direct-answer evaluation. Confidence: high for the local observations; medium
for the proposed fixes until full-checkpoint reruns compare scores.

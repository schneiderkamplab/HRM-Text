# DFM6 Plan

Last updated: 2026-06-18
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

- all new DFM post-training datasets that pass quality/audit checks;
- scaled-up Danish math and code data;
- scaled-up English math and code data;
- Danish tool-calling data;
- English tool-calling data.

Migration:

- Replace the current HRM/Sapient tokenizer with the intended Gemma 4 tokenizer.
- Render instruction-format data with the Gemma 4 chat template rather than the original Sapient/DFM5 instruction format.

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

## Open Questions

- Exact Gemma 4 tokenizer artifact and license status.
- Whether DFM6 should be purely fresh training or include a separate upcycling experiment.
- Final token budget per epoch and number of epochs.
- Exact Danish/English tool-calling datasets and whether synthetic tool traces are needed.
- How much post-training data belongs in the base run versus a separate final refinement stage.

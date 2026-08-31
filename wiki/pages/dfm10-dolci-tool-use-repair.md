---
type: Runbook
title: DFM10 DOLCI Tool Use Repair
description: Rebuild, validate, tokenize, and audit DOLCI tool-use trajectories with native Gemma 4 call and response structure.
tags: [dfm10, dolci, tool-use, gemma4, data-quality]
status: stable
last_updated: 2026-08-30
confidence: high
---
# DFM10 DOLCI Tool Use Repair

## Failure and policy

DFM10 inherited `allenai/Dolci-Instruct-SFT-Tool-Use` and its SA subset through
the `dolci_native_tool_use__` conversion. The source-level audit found 75/100
and 86/100 usable targets respectively. The raw records contain `environment`
messages with actual tool results, but the old converter accepted only a
literal `tool` role and silently dropped every environment result. It also
restarted call IDs at `call_0` for each assistant turn. Rendered multi-step
records therefore contained empty tool-response boundaries, unsupported final
answers, and duplicate call IDs.

The repaired path is isolated under the `dolci_tool_use_repaired__` prefix. Do
not alter historical DFM7--DFM9 tokenized data. DFM10 switches away from the old
native prefix only after a deterministic judge audit reaches at least 90%
usable for both Tool Use and Tool Use-SA.

DFM10 retokenization uses `--max-seq-len 4096`. Multi-turn targets retain
native roles and the largest fitting complete-turn suffix. Single-request
agent traces retain the request plus the newest complete call/result groups;
targets and tool declarations are not clipped. Longer complete trajectories
remain in the converted source for dedicated long-context epochs.

## Repaired contract

[`scripts/repair_dolci_tool_use.py`](/../scripts/repair_dolci_tool_use.py)
streams the seven raw Parquet files and:

1. normalizes native tool declarations and names;
2. parses Python-style source calls into structured arguments;
3. assigns monotonically increasing call IDs across each trajectory;
4. converts every `environment` message into one or more `tool` messages bound
   to the preceding calls;
5. splits concatenated parallel-call results in call order;
6. validates declared names, required arguments, basic JSON types, enums, role
   ordering, and complete call-response groups; and
7. atomically drops rather than salvages malformed or incomplete trajectories.

The Gemma 4 template previously treated mapping-valued tool results as generic
sequences and attempted to call `.get()` on dictionary keys. The mapping check
now precedes the content-parts sequence check. Existing string-valued tool
responses render unchanged; mapping results render as native structured tool
responses.

The deterministic conversion retained 190,736/229,183 source trajectories
(83.22%), containing 996,180 assistant targets and 528,176 tool-call targets.
The largest rejection groups are 12,502 missing tool responses, 8,602 invalid
function-call strings, 6,625 call/response-count mismatches, 5,644 argument-type
mismatches, and 2,640 mixed call-and-content assistant messages. The complete
counts are in
`data/converted_sources/dolci_tool_use_repaired/repair_summary.json`.

## Commands and paths

```bash
python scripts/repair_dolci_tool_use.py --workers 7 --force

python scripts/build_dolci_tool_use_tokenizer_staging.py

python scripts/tokenize_chat_template.py \
  data/dfm10_dolci_tool_use_repaired_sources \
  --tokenizer-path /work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json \
  --chat-template data_io/chat_templates/gemma4_native_chat.jinja \
  --output-dir data/tokenized_dfm10_dolci_tool_use_repaired \
  --workers 16 --force
```

The staging builder symlinks ordinary converted files but splits any JSONL over
512 MiB into line-aligned shards targeting 256 MiB. This avoids a single long
CPU tail without changing, duplicating, or resampling source trajectories. The
largest 1.68 GiB source became seven balanced tokenizer inputs and the resumed
16-worker run finished in 4m09s. The completed corpus has 996,180 assistant
targets and 1,530,751,609 stored prompt-plus-target tokens; its tokenizer and
template metadata exactly match DFM9.

Under DFM10's 4,097-token sampler window, 939,086 targets remain eligible and
the long-context truncation policy yields 870,646,320 effective tokens before
repetition. The configured repeat 2 therefore contributes approximately
1,741,292,640 effective tokens per DFM10 epoch. This effective figure, rather
than twice the raw stored-token count, should be used in mix accounting.

After tokenization, prepare 100 deterministic eligible targets from each output
file and launch a single first-free-GPU E4B audit:

```bash
python scripts/audit_repaired_dolci_tool_use.py prepare
setsid scripts/run_repaired_dolci_tool_use_audit_when_free.sh \
  > logs/data_audits/dolci_tool_use_repaired_20260828/runner.log 2>&1 &
```

The launcher takes the cooperative per-GPU lock, starts only on a compute-idle
GPU, owns and tears down only its E4B server, retries transient judge failures,
and atomically merges the exact prepared sample set. The 2026-08-28 audit had
zero judge errors and accepted 674/700 targets (96.29%): 579/600 (96.5%) for
Tool Use and 95/100 (95.0%) for Tool Use-SA. Every original file exceeded the
90% gate. Of the 26 rejected audit samples, 22 were incomplete/incoherent
source answers to multi-part requests and four were semantically incorrect;
none exposed a remaining structural conversion failure. DFM10 therefore
retains the validated corpus without generative rewriting, disables the
superseded `dolci_instruct_sft_tool_use__`,
`dolci_instruct_sft_tool_use_sa__`, and `dolci_native_tool_use__` task
families, and samples
`dolci_tool_use_repaired__` with the existing one-million-target per-file cap
and repeat 2. Results are under
`logs/data_audits/dolci_tool_use_repaired_20260828/`.

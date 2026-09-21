---
type: Implementation Report
title: Native Mimir Text Chat
description: Verified GGUF tokenizer/template export, streaming native chat, and CPU/Metal parity against Hugging Face.
tags: [mimir, prefixlm, llama-cpp, tokenizer, chat, metal, testing]
status: draft
last_updated: 2026-09-17
confidence: high
---
# Native Mimir Text Chat

**Engine follow-up, 2026-09-17:** [first-class PrefixLM integration](llama-cpp-prefixlm-engine.md) now owns the generic phase, admission, cache and failure rules in llama.cpp. Earlier wrapper-owned descriptions below are historical.

## Required chat experiment protocol

User requirement, 2026-09-17: Mimir was pretrained with its chat template,
never without it. Every Mimir chat experiment must render the checkpoint's
own chat template, including its special tokens and generation header, using
the matching tokenizer. Raw-text prompts and substitute templates are not
valid Mimir chat experiments. If a client cannot render the template, fix or
replace the client before conducting a chat experiment.

## Scope and source state

The [native session](mimir-native-session.md) now has a C++ text layer and
terminal client under `native/mimir/`. `CHAT.md` contains reproducible export,
build, run, and testing commands; `text-results.json` retains hashes and suite
summaries. No commits, pushes, or upstream submissions were made.

The pinned engine remains `c9a5eeeb34ab8f794ea7510ca52d25da13728a5b`. Apply the
existing PrefixLM replacement patch and graph-size fix, then
`native/mimir/patches/text-codec.patch`. All are already applied locally.
The [historical comparison](llama-cpp-prefixlm-comparison.md), including the
original proposal, is retained unchanged in its separate worktrees.

## Export and tokenizer discoveries

The source is `danish-foundation-models/DFM-Mimir` revision
`2844f0178e695d7d9ce182cb660671fd34c76ce5`, with pinned Python dependencies from
`scripts/prefixlm_comparison/requirements.lock`. The source tokenizer explicitly
requests `fix_mistral_regex=true`. Correct parity requires SPM-style whitespace
normalization with Mistral regex splitting, not the existing Gemma4 splitter
nor the approximate TEKKEN splitter. A distinct `spm-bpe-mistral` mode avoids
changing those existing modes. A generated 191-range letter-category exception
table supplements llama.cpp's simple upper/lower maps, including titlecase and
mathematical letters. Its generator is retained under `native/mimir/tests`.

The converter also needed to mark all 256 `<0xXX>` fallback tokens as BYTE,
using the tokenizer model's actual byte-fallback setting. Otherwise decoding
returns literal byte-token spellings. Native Jinja trimming needed Python's
Unicode whitespace semantics and codepoint-aware explicit character sets.
The text patch contains all three changes.

**Superseded, 2026-09-17:** the initial local
`logs/mimir-chat/mimir-f32.gguf` had incorrect tokenizer metadata. Use
`logs/mimir-chat/mimir-text-f32.gguf`. The final 259 FP32 tensors, including
`hrm.z_l_init`, are bit-identical to the independently validated earlier
`logs/prefixlm-comparison/real/mimir-f32.gguf`. The new export adds the complete
correct tokenizer and template. Export validation produces a source/input hash
manifest and copies the model license beside the GGUF. The FP32 artifact is
about 7.15 GB; it is not the intended phone deployment format.

## Chat behavior

The embedded template is rendered directly using llama.cpp's Jinja runtime;
no heuristic template substitution is used. Template output already includes
BOS, so native tokenization does not insert it again. Thinking is disabled.
Supported messages are an optional initial system message, users, and
assistants; tools and multimodal input are outside this milestone.

Generation is deterministic greedy sampling and stops at configured EOS 106,
matching HF, rather than every token llama.cpp labels as end-of-generation.
UTF-8 streaming retains partial codepoints across tokens. Every new turn fully
re-prefills the retained conversation through the existing PrefixLM session.
Only completed turns enter history. Failed/cancelled turns, including those
whose partial output was displayed, are rolled back. Exceptions in consumer
callbacks clear the session and preserve completed history.

Methods must be serialized except cancellation. Cancellation producers must
stop before recovery/reset/destruction. The terminal signal handler stores a
lock-free flag; a joined worker requests cancellation. Metal cancellation may
wait for the active decode. Explicit capacity errors preserve history; there
is no automatic history truncation. `/reset` retains the system message.
The client also exposes a JSON-lines testing protocol and vocabulary-only
inspection mode. It is not a network server.

## Verified results and limits

Local macOS 26.4.1 / Apple M2 Max testing on 2026-09-17 passed:

- 724/724 HF tokenizer/template cases, both full and vocabulary-only exports;
  exact rendered prompts, token IDs, and decoded text where applicable.
- The same 724 cases under UBSan with `halt_on_error=1`.
- Five CTest suites in release and UBSan builds, including existing upstream
  Jinja string/filter regressions and PrefixLM true/false/absent session tests.
- Eight real-model end-to-end scenarios each on CPU, Metal, and fused Metal
  attention with FP16 KV. Includes independent HF free-running two-turn
  generation (answers `4` then `6`, both EOS 106), Danish/English greedy
  references, SIGINT during prefill/answer, capacity preservation, and recovery.
- 68 C++ text/lifecycle checks with the real model on Metal, including callback
  cancellation and exceptions, sticky cancellation, and retained system text.

The CI workflow now generates a small vocabulary-only GGUF and runs text parity
without downloading model weights. Remote CI has not been executed here.
Local ASan remains blocked before main even for an empty executable, as recorded
in the native-session page; only UBSan is claimed as passed locally.
These are correctness checks, not comprehensive Unicode or performance proofs.

Remaining release gates are validated weight quantization, Apple platform
packaging, iPhone/iPad memory and thermal measurements, app integration, and
release engineering. FP32 host correctness does not establish phone viability.

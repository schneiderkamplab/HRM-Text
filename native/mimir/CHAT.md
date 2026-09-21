# Native Mimir text chat

The terminal client runs the checkpoint's embedded chat template and tokenizer,
then sends each complete conversation through the PrefixLM session. Replies use
deterministic greedy sampling, stream valid UTF-8, and stop at the checkpoint's
configured EOS (106). Every new turn recomputes the full bidirectional prefix;
answers are causal. Completed turns enter history atomically. Cancelled or
failed turns are discarded, including partial answers already displayed.

## Required chat experiment protocol

User requirement, 2026-09-17: Mimir was pretrained with its chat template,
never without it. Every Mimir chat experiment must render the checkpoint's
own chat template, including its special tokens and generation header, using
the matching tokenizer. Raw-text prompts and substitute templates are not
valid Mimir chat experiments. If a client cannot render the template, fix or
replace the client before conducting a chat experiment.

## Run the existing local build

From the repository root:

```sh
logs/mimir-runtime/build/bin/mimir-chat \
  --model logs/mimir-chat/mimir-text-f32.gguf --device metal
```

Use `/reset` for a new conversation, `/quit` to exit, and Ctrl-C during generation
to cancel. `--system 'Svar på dansk.'` sets a retained system message.
`--device cpu` explicitly selects CPU; unavailable Metal is an error.
`--flash` enables fused attention. Default limits are 2048 context tokens,
1024 prompt/batch tokens, and 256 answer tokens. Increase `--ctx`, `--batch`,
and `--max-tokens` within the trained 4096-token limit as needed. Oversized
conversations fail explicitly; the client never silently truncates history.

This is a text-only host client with FP32 weights, not an iOS package. The
validated artifact is about 7.15 GB before runtime memory. Quantized weights,
phone memory/thermal qualification, Swift packaging, and UI remain later work.

## Reproduce the export

Follow the [runtime build instructions](README.md) and the pinned Python/model
setup in [the comparison guide](../../scripts/prefixlm_comparison/README.md).
Use DFM-Mimir revision `2844f0178e695d7d9ce182cb660671fd34c76ce5` and the exact
Python dependency lock. Then run:

```sh
logs/prefixlm-comparison/venv/bin/python native/mimir/export.py \
  --model logs/prefixlm-comparison/mimir-hf \
  --output logs/mimir-chat/mimir-text-f32.gguf \
  --reference-gguf logs/prefixlm-comparison/real/mimir-f32.gguf
```

Omit `--reference-gguf` if the independently validated earlier weight export is
not available. An existing output requires `--verify-existing`. The exporter
checks PrefixLM, tokenizer/template/BOS/EOS metadata, all 256 byte tokens, and
FP32 tensors including the recurrent state vector. It writes a hash manifest
and copies the checkpoint license beside the GGUF. Optional reference
verification compares every tensor bit for bit. The corrected text artifact
is `mimir-text-f32.gguf`; the initial local `mimir-f32.gguf` in `logs/mimir-chat`
is superseded because its tokenizer metadata was incorrect.

**Superseded tokenizer interpretation (2026-09-21):** the paragraph below describes
our original exported-HF reference, not training. Training reads the tokenizer JSON
directly; corrected GGUFs use `gemma4`. See [corrected GGUF preparation](CORRECTED-GGUFS.md)
for the converter fix, BF16/Q8_0/Q4_K_M artifacts and direct-training parity results.
The separate regex mode remains available but is not the correct Mimir training default.

The separate text patch, `patches/text-codec.patch`, adds the explicit
`spm-bpe-mistral` tokenizer mode required by this checkpoint's
`fix_mistral_regex=true`, correct byte-fallback token types, and Unicode Jinja
trimming. It includes a generated letter-category exception table; regenerate
it with `tests/generate_letter_cases.py` in the pinned Python environment.
It does not replace ordinary Gemma4 or TEKKEN tokenization. Historical PrefixLM
comparison worktrees and the original patch proposal remain available unchanged.

PrefixLM correctness now lives in [llama.cpp itself](ENGINE.md). This client
uses its explicit complete-prefix API and ordinary causal continuation. The
stock llama-server and llama-cli also support the bounded PrefixLM mode.

## Embed or automate

Link `mimir-chat-lib` and include `mimir/chat.h`. `TextCodec` exposes prompt
rendering and tokenization; `Chat` owns the session and completed message history.
Serialize all methods except `request_cancel()`. Stop/join cancellation
producers before `recover()`, `reset()`, or destruction. `recover()` keeps
completed history; `reset()` keeps only the system message. A throwing stream
callback rolls the turn back. A callback may request cancellation, but must not
reenter other chat methods. Metal cancellation can wait for the active decode.

The executable supports `--json` for one JSON request per line. It first emits
`ready`; a reply emits `start`, zero or more `delta` events, then `done` with
finish reason, status, text, token IDs, EOS token, and history size. Invalid
requests emit `error`. Example requests:

```json
{"text":"Hvad er 2 + 2?", "max_tokens":32}
{"op":"reset"}
{"op":"tokenize","text":"æøå 🧑🏽‍💻","add_special":false}
{"op":"prepare","messages":[{"role":"user","content":"Hej"}],"add_generation_prompt":true}
```

`--inspect --json --device cpu` loads vocabulary only and supports text
inspection without allocating inference weights or context. It rejects reply
requests. The JSON client is a local testing interface, not a network service.

## Validation

```sh
logs/prefixlm-comparison/venv/bin/python native/mimir/tests/prepare_text_ci.py \
  --source logs/prefixlm-comparison/mimir-hf
logs/prefixlm-comparison/venv/bin/python native/mimir/tests/text_parity.py \
  --client logs/mimir-runtime/build/bin/mimir-chat \
  --model logs/mimir-text-ci/vocab.gguf \
  --reference logs/mimir-text-ci/reference.json \
  --output logs/mimir-chat/text-ci-parity.json
ctest --test-dir logs/mimir-runtime/build --output-on-failure
logs/prefixlm-comparison/venv/bin/python native/mimir/tests/chat_reference.py \
  --model logs/prefixlm-comparison/mimir-hf --output logs/mimir-chat/chat-reference.json
logs/prefixlm-comparison/venv/bin/python native/mimir/tests/chat_e2e.py \
  --client logs/mimir-runtime/build/bin/mimir-chat \
  --model logs/mimir-chat/mimir-text-f32.gguf \
  --reference logs/mimir-chat/chat-reference.json \
  --short-reference logs/prefixlm-comparison/real/prompts.json \
  --output logs/mimir-chat/e2e-metal.json
logs/mimir-runtime/build/bin/mimir-text-tests logs/mimir-chat/mimir-text-f32.gguf metal
```

Repeat end-to-end testing with `--flash` or `--device cpu` and separate output
paths. The 724 text cases compare rendered prompts, token IDs, and decoding
against HF, including seeded Unicode cases, combining marks, byte fallback,
special tokens, and Python whitespace. The eight end-to-end scenarios cover
two-turn HF free-running parity, Danish/English greedy parity, actual SIGINT
during prefill and decoding, capacity preservation, and invalid-input/reset
recovery. The C++ lifecycle checks additionally exercise callback exceptions,
callback cancellation, sticky cancellation, and system-message retention.

Results and provenance are in `text-results.json`; raw logs are under
`logs/mimir-chat`. CPU CI also runs vocabulary-only parity against pinned
public tokenizer files without downloading model weights. Local release and
UBSan runs are verified; remote CI and local ASan are not claimed as passed.
The host ASan startup blocker is described in [README.md](README.md).

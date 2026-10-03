---
language:
- da
- en
license: apache-2.0
base_model: danish-foundation-models/DFM-Mimir-v1.5
base_model_relation: quantized
pipeline_tag: text-generation
tags:
- gguf
- llama-cpp
- hrm_text
- prefix-lm
- danish
---

# DFM Mimir v1.5 — GGUF

Official GGUF conversions of [DFM Mimir v1.5](https://huggingface.co/danish-foundation-models/DFM-Mimir-v1.5)
from Danish Foundation Models. See the source model card for training,
evaluation, intended uses and limitations. These files preserve the source
checkpoint's weights, tokenizer and Gemma 4 chat template; quantization reduces
weight precision for the Q8_0 and Q4_K_M variants.

## Choose a file

| File | Precision | Approximate download size |
|---|---|---:|
| [dfm-mimir-v1.5-q4_k_m.gguf](./dfm-mimir-v1.5-q4_k_m.gguf) | Mixed 4-bit Q4_K_M | 1.17 GB |
| [dfm-mimir-v1.5-q8_0.gguf](./dfm-mimir-v1.5-q8_0.gguf) | 8-bit Q8_0 | 1.91 GB |
| [dfm-mimir-v1.5-bf16.gguf](./dfm-mimir-v1.5-bf16.gguf) | Original 16-bit BF16 | 3.59 GB |

Download **one** file. Each includes its tokenizer and chat template. Download
size is not RAM use: inference needs additional memory, especially at longer
contexts. Both quantized variants were produced directly from BF16, without
requantizing an already quantized model.

```sh
hf download danish-foundation-models/DFM-Mimir-v1.5-GGUF dfm-mimir-v1.5-q4_k_m.gguf --local-dir ./mimir-v1.5
```

## Runtime and chat template

Use the [DFM Mimir app](https://github.com/schneiderkamplab/HRM-Text/releases)
or [patched llama.cpp with HRM-Text/PrefixLM support](https://github.com/schneiderkamplab/llama.cpp/tree/4122b9a814d5bd4f48f454367419f75c05ee5215).
Compatibility with arbitrary stock llama.cpp, Ollama and other GGUF runtimes is
not implied. Always use the **embedded Mimir chat template**; the model was
trained with that format, not raw untemplated prompts.

Context length is **4096 tokens**. Longer contexts are experimental and need
additional memory and validation. In the app, enable model discovery and select
**Check for newer models**, or import a downloaded GGUF. Discovery lists official
repositories containing both `mimir` and `gguf` in their names. Existing bundled
models are not automatically replaced.

The tokenizer is loaded directly from `tokenizer.json`, as during training,
without the export-time `fix_mistral_regex` rewrite. GGUF metadata uses
`tokenizer.ggml.pre=gemma4` and marks all 256 byte-fallback tokens. v1.5's tokenizer
is byte-identical to the original Mimir tokenizer. Its Gemma 4 template adds
support for mapping/object tool-response content; the supplied v1.5 template is
preserved exactly.

## Provenance and validation

- Source revision: `cc57cebadf375947ced5ccd3317d9da6bf8f9677` of
  `danish-foundation-models/DFM-Mimir-v1.5`.
- Converter revision: `4122b9a814d5bd4f48f454367419f75c05ee5215` of
  `schneiderkamplab/llama.cpp`.
- Each precision passes **724/724** tokenizer/decoder/chat-template comparisons
  and **19/19** independent training-tokenizer audit cases.
- Each precision passes short Danish and English chats on **CPU and Metal**,
  using the embedded template, 1024-token context and a 32-token reply budget.
- Validation results are recorded in [validation.json](./validation.json).
- Exact checksums: [SHA256SUMS](./SHA256SUMS).
- Source/config/tokenizer hashes and conversion provenance:
  [provenance.json](./provenance.json).

These checks are bounded artifact qualification, not full quality benchmarks,
long-context qualification, or new Linux/CUDA/Vulkan/mobile hardware testing.
License: [Apache 2.0](./LICENSE), inherited from the source model.

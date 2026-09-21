---
language:
- da
- en
license: apache-2.0
base_model: danish-foundation-models/DFM-Mimir
base_model_relation: quantized
pipeline_tag: text-generation
tags:
- gguf
- llama-cpp
- hrm_text
- prefix-lm
- danish
---

# DFM Mimir — GGUF

Official GGUF conversions of [DFM Mimir](https://huggingface.co/danish-foundation-models/DFM-Mimir)
from Danish Foundation Models, prepared for local inference using the
[DFM Mimir app and patched llama.cpp](https://github.com/schneiderkamplab/HRM-Text).
See the original model card for training, evaluation, intended uses and limitations.

## Choose a file

| File | Precision | Download size |
|---|---|---:|
| [dfm-mimir-q4_k_m.gguf](./dfm-mimir-q4_k_m.gguf) | Q4_K_M, mixed 4-bit quantization | 1.17 GB |
| [dfm-mimir-q8_0.gguf](./dfm-mimir-q8_0.gguf) | Q8_0, 8-bit quantization | 1.91 GB |
| [dfm-mimir-bf16.gguf](./dfm-mimir-bf16.gguf) | BF16, original 16-bit precision | 3.59 GB |

Download **one** GGUF; each is self-contained with its tokenizer and chat template.
Q4_K_M is the smallest option. Q8_0 and BF16 require more memory. Download sizes
are decimal GB and do not include the additional RAM required for inference.
BF16 is an unquantized conversion; both quantized variants were made directly
from this BF16 export, not from another quantized file.

For example:

```sh
hf download danish-foundation-models/DFM-Mimir-GGUF dfm-mimir-q4_k_m.gguf --local-dir ./mimir
```

## Runtime and chat template

This architecture uses PrefixLM. Use the DFM Mimir app or the
[schneiderkamplab llama.cpp fork](https://github.com/schneiderkamplab/llama.cpp/tree/4122b9a81)
with HRM-Text/PrefixLM support; these files are not a claim of compatibility with
arbitrary stock llama.cpp, Ollama or other GGUF applications.
Always use the **embedded Mimir chat template**. Raw prompts or a substitute
chat template do not reproduce the model's training input format.

The model was trained with a context length of **4096 tokens**. Larger contexts
are experimental and require additional memory and validation.

## Training-faithful tokenizer correction

These exports load the original `tokenizer.json` directly, matching the training
pipeline. They use `tokenizer.ggml.pre=gemma4` and preserve all 256 byte-fallback
token types. An earlier conversion path applied the exported HF configuration's
`fix_mistral_regex=true` flag and selected a different pre-tokenizer; that behavior
did not match training. These files correct that conversion without changing the
BF16 model tensors.

## Provenance and validation

- Source: `danish-foundation-models/DFM-Mimir`, revision
  `2844f0178e695d7d9ce182cb660671fd34c76ce5`.
- Converter: `schneiderkamplab/llama.cpp`, revision `4122b9a81`.
- Each precision passes **724/724** tokenizer, decoder and chat-template checks,
  and **19/19** independent training-tokenizer audit cases.
- Each precision passes short Danish and English generation checks on both
  macOS CPU and Metal, using Mimir's chat template.
- All 259 BF16 tensor payloads are bit-identical to the previous BF16 conversion;
  the correction affects tokenizer metadata.

These checks are bounded artifact validation, not new full benchmark scores or
qualification of every accelerator, mobile device or extended context length.

[SHA256SUMS](./SHA256SUMS) records exact file checksums.
[provenance.json](./provenance.json) records source and conversion metadata.
[validation.json](./validation.json) records the actual local validation results.
See the [reproduction report](https://github.com/schneiderkamplab/HRM-Text/blob/codex/mimir-apple-mvp/native/mimir/CORRECTED-GGUFS.md)
for commands and scope. License: [Apache 2.0](./LICENSE), inherited from the source model.

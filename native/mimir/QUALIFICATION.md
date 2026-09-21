# PrefixLM bounded qualification — 2026-09-17

Status: Apple qualification evidence collected; Linux release/ASan/UBSan remains a prerequisite to packaging and review. Remind the user at that hold point. No patch packaging or PR review was performed in this round.

## Method and scope

Apple M2 Max, 96 GB unified memory, macOS 26.4.1. Pinned llama.cpp base: `c9a5eeeb34ab8f794ea7510ca52d25da13728a5b`; local PrefixLM implementation is the rollback snapshot described in `followup-results.json`. Core code was unchanged for this experiment.

Reference: `danish-foundation-models/DFM-Mimir` revision `2844f0178e695d7d9ce182cb660671fd34c76ce5`, loaded as F32 with eager attention. Transformers revision `ff2421c67f35cc83a0fbabbc2633c96734685918`. Every chat prefix uses that checkpoint’s tokenizer and chat template with `enable_thinking=False` and the generation header. Server-rendered tokens are checked against HF before timing.

Four cases only. Answers are fixed teacher-forced targets, including EOS, not a quality benchmark or a claim that the model freely generates those answers. Independent HF full-forward mixed-prefix/answer attention supplies the reference. llama.cpp runs the answer both one token at a time and in a chunk. The extra final logit row after EOS checks execution consistency; answer-only NLL excludes that unused row.

| Case | Prefix tokens | Target tokens including EOS | Coverage |
|---|---:|---:|---|
| danish-unicode | 35 | 12 | Danish, capitalization, æ/ø/å |
| english-instruction | 26 | 9 | English, two-part instruction |
| multiturn | 160 | 11 | Retained assistant turn and user facts |
| near-limit | 480 | 8 | Retrieval across a full physical prefix batch |

Context: 512, prefix physical batch: 480. The long case fills that batch exactly, but this is a boundary test of the configured capacity—not a test of the model’s maximum trained context. Evaluation uses F32 KV, four CPU threads, all layers on Metal, flash attention on/off. BF16/Q8_0/Q4_K_M are fresh conversions of the same original checkpoint; F32 is the exact-weight control.

## Numerical and conditional-likelihood results

All vocabulary logits are compared. The old absolute threshold 0.03 is retained as a diagnostic, including failures; it is not a justified quantized-model quality gate. NLL is in nats per target token, weighted across the 40 target tokens. Top-1 agreement covers 44 positions per configuration, separately for single/chunk execution.

| Weights / attention | HF max abs, single / chunk | Chunk–single max abs | HF top-1 matches, single / chunk | Answer NLL / HF | Strict steps passing |
|---|---:|---:|---:|---:|---:|
| f32-unfused | 0.016405 / 0.016405 | 0.005407 | 44/44 / 44/44 | 1.241887 / 1.242059 | 52/52 |
| f32-flash | 0.014807 / 0.014807 | 0.004368 | 44/44 / 44/44 | 1.241940 / 1.242059 | 52/52 |
| bf16-unfused | 0.042489 / 0.052350 | 0.047675 | 44/44 / 44/44 | 1.242099 / 1.242059 | 41/52 |
| bf16-flash | 0.045022 / 0.048280 | 0.040186 | 44/44 / 44/44 | 1.242588 / 1.242059 | 45/52 |
| q8_0-unfused | 0.145638 / 0.150215 | 0.007053 | 44/44 / 44/44 | 1.238789 / 1.242059 | 0/52 |
| q8_0-flash | 0.143317 / 0.143868 | 0.007930 | 44/44 / 44/44 | 1.238722 / 1.242059 | 0/52 |
| q4_k_m-unfused | 1.593767 / 1.580689 | 0.027444 | 43/44 / 43/44 | 1.228339 / 1.242059 | 0/52 |
| q4_k_m-flash | 1.595940 / 1.581738 | 0.024548 | 43/44 / 43/44 | 1.228361 / 1.242059 | 0/52 |

Interpretation: F32 passes all 104 strict steps across both attention modes. BF16 and Q8 preserve all tested top choices; Q4 changes one of 44 in both modes. BF16/Q8/Q4 exceed the old absolute-logit threshold, and those failures remain visible. Q4’s lower average target NLL on this tiny chosen set is not evidence of better general quality. Chunk/single differences also occur in exact-weight F32, so the data are consistent with numerical execution differences; they do not isolate a particular kernel as the cause.

## Templated request performance and memory

Stock llama-server, one active slot, full Metal offload, flash attention, default F16 KV, four CPU threads, context 512, batch/ubatch 480. One warmup per length is excluded, then three measured rounds; the middle round reverses length order. Formats run serially. Every request recomputes its entire prefix (`cache_n=0`). Fixed 16-token greedy continuations ignore EOS solely to measure throughput; these continuations are not quality scores. Decode rate is the server’s reported `predicted_per_second` (its timing excludes the first sampled token).

Median [minimum–maximum] across three runs. End-to-end includes HTTP and sampling; prefill/decode are engine timings. This is a workstation measurement, not an isolated laboratory performance guarantee.

| Weights | Prefix tokens | Prefill ms | Decode tokens/s | End-to-end s |
|---|---:|---:|---:|---:|
| bf16 | 35 | 885.87 [831.19–908.44] | 4.86 [3.87–4.88] | 3.98 [3.92–4.76] |
| bf16 | 160 | 954.73 [472.19–1136.19] | 5.26 [4.13–5.89] | 3.99 [3.02–4.59] |
| bf16 | 480 | 1269.88 [1103.75–2046.17] | 15.00 [3.97–17.25] | 2.14 [2.11–5.83] |
| q8_0 | 35 | 453.52 [388.09–474.89] | 5.20 [4.45–24.55] | 3.34 [1.09–3.76] |
| q8_0 | 160 | 373.84 [340.91–841.11] | 19.77 [4.49–20.33] | 1.11 [1.10–4.18] |
| q8_0 | 480 | 931.57 [888.26–1545.82] | 17.85 [3.66–20.24] | 1.73 [1.67–5.65] |
| q4_k_m | 35 | 528.92 [260.65–696.06] | 5.94 [5.68–17.63] | 3.17 [1.11–3.22] |
| q4_k_m | 160 | 894.37 [449.22–1114.08] | 5.85 [5.44–20.30] | 3.65 [1.19–3.68] |
| q4_k_m | 480 | 1328.33 [813.28–1846.94] | 6.19 [5.10–21.37] | 3.75 [1.52–4.79] |

All four repeated continuations (warmup included) were identical within each weight/length group. Latency still varies by several-fold in some groups; do not rank formats by these medians or claim stable production throughput. Controlled performance validation remains open.

| Weights | Peak process RSS, GiB |
|---|---:|
| bf16 | 3.987 |
| q8_0 | 2.451 |
| q4_k_m | 1.767 |

RSS is the macOS `/usr/bin/time -l` high-water mark over model loading, warmup and all request lengths. It is not a measurement of total GPU allocation or total system unified-memory pressure. Other user applications were left running; no unrelated processes were stopped.

## Unchanged-mode performance controls

A tiny deterministic HRM fixture (not Mimir chat) is copied with causal/bidirectional metadata. CPU-only prompt processing uses 256 tokens; causal decoding also measures 16 tokens. Baseline/patched/patched/baseline order, 25 samples per invocation, with the first five discarded consistently. Synthetic random tokens are appropriate here only because this is an engine control, not a chat experiment.

| Mode / work | Baseline median ns | Patched median ns | Patched / baseline |
|---|---:|---:|---:|
| causal / prefill | 13966812 | 13680688 | 0.980 |
| causal / decode | 6960916 | 7771646 | 1.116 |
| bidirectional / prefill | 17530104 | 17969125 | 1.025 |

The aggregate causal decode time changes by +11.6%. Baseline round medians are 5.80 and 7.85 ms; patched rounds are 6.91 and 8.02 ms. This run does not distinguish a patch regression from time-dependent workstation effects. Repeat this bounded control on the Linux test machine before claiming no regression. These small CPU controls do not establish absence of performance regressions at production model sizes or on other backends. Raw samples and command lines remain in `controls.json`.

## Prior regression evidence and remaining gates

- Existing core tests: 724 CPU/Metal checks and 362 CPU UBSan checks; seven release and seven UBSan CTests passed. Existing causal and bidirectional functional controls remain covered. See `followup-results.json`.
- Previous independent tiny reference: 18/18 CPU, CPU UBSan and unfused Metal; 17/18 fused Metal, retaining the unchanged causal-control difference 0.00010559 against 0.0001. No tolerance was changed here.
- Previous templated chat lifecycle tests: 72 checks across BF16/Q8/Q4 and flash on/off; 23 stock-server checks, including isolation, cancellation, rejection and recovery. This round adds four varied teacher-forced cases instead of multiplying lifecycle tests.
- Linux CPU release plus ASan/UBSan must run before packaging/review. Apple ASan has not supplied usable execution evidence. CUDA, other GPUs, multi-sequence scheduling and persistence are not qualified.

## Reproduction and raw evidence

Run from the repository root with the existing pinned Python environment and built binaries. Required local model paths and overrides are documented by `--help`. The controls phase requires the existing deterministic fixture and pristine baseline build.

```sh
PY=logs/prefixlm-comparison/venv/bin/python
$PY native/mimir/tests/qualification.py prepare
$PY native/mimir/tests/qualification.py evaluate
$PY native/mimir/tests/qualification.py evaluate --weights f32
$PY native/mimir/tests/qualification.py benchmark
PYTHONPATH=llama.cpp/gguf-py $PY native/mimir/tests/qualification.py controls
$PY native/mimir/tests/qualification_report.py
```

Raw evidence: `logs/mimir-qualification/` contains template-rendered cases, HF logits, each engine specification/report, dumped logits, likelihoods, server timings/logs, controls, and provenance. Strict failures are retained. This harness still belongs to the consuming project; moving the essential evidence into the upstream submission is part of later packaging, after Linux tests.

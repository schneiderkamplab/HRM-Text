# Native Mimir generation speed — 2026-09-19

This measures the app's native `mimir::Chat` path without SwiftUI, Objective-C
callbacks, IPC or per-token output. It does not yet measure app overhead.

## Method

Apple M2 Max, 96 GiB unified memory, macOS 26.4.1; Xcode 16.3 Release build.
Bundled Q4_K_M model; full Metal offload, flash attention, F16 KV, four threads,
8,192 context/batch, greedy sampling. System instruction comes from the checked-in
DFM-Mimir-v1 profile. Both prompts use the model's actual GGUF chat template.
The longer prompt contains repeated Danish travel notes, followed by the same
request for a long story. This controls workload size, not answer quality.

One warmup for each prompt, then three measured runs each with alternating order.
History resets before each request: every run recomputes its complete prefix.
Generation stops at EOS or a 64-token budget. No compaction is performed.
Other desktop applications remain open; this is a workstation measurement,
not a thermally isolated or exclusive-GPU benchmark. Model loading is separate.

- **Time to first text:** `Chat::reply` entry through its first visible UTF-8
  callback. Includes template/tokenization, prefix processing, sampling and the
  first token's decode. It is not a pure prefill measurement.
- **Streaming rate:** tokens after the first visible chunk divided by time from
  first to last callback. Counts account for UTF-8 chunks containing several
  tokens. This includes the native greedy sampler and UTF-8 handling.
- **Total:** complete `Chat::reply` call; excludes model load and history reset.

## Reproduction

After configuring the Mac app build:

```bash
cmake --build logs/mimir-apple/macos --config Release --target mimir-native-bench
/usr/bin/time -l logs/mimir-apple/macos/Release/mimir-native-bench \
  "$PWD/logs/mimir-review/mimir-q4_k_m.gguf" \
  "$PWD/native/apple/Resources/DFM-Mimir-v1.profile.json" \
  > logs/mimir-apple/native-speed.jsonl \
  2> logs/mimir-apple/native-speed-stderr.log
```

The checked-in results JSON includes all samples, output hashes, source/model
hashes and medians/ranges. Raw generated text remains in the local JSONL log.

## Results

Median [minimum–maximum] over three measured runs per prompt.

| Prompt tokens | First text, seconds | Streaming, tokens/s | Total for 64 tokens, seconds |
|---:|---:|---:|---:|
| 102 | 0.44 [0.27–0.59] | 15.16 [5.46–41.97] | 4.59 [1.77–12.13] |
| 1617 | 7.47 [7.32–7.55] | 6.24 [4.47–6.79] | 17.64 [16.60–21.57] |

Model/context setup took 2.81 seconds. All eight runs generated 64 tokens.
Repeated outputs were identical within each prompt case: True.

The longer prompt consistently needed about 7.3–7.6 seconds before first text,
versus 0.27–0.59 seconds for the short prompt. Native streaming itself varies
substantially, especially for the short prompt. These results demonstrate that
slow generation can occur without the UI; they do not establish the hardware’s
optimal throughput or quantify app overhead. Background desktop work was active
(including a Git process consuming roughly one CPU core in a spot check).
No conclusion about the cause of variability is justified without profiling.

Next comparison should use identical native/app workloads and phase timings;
a controlled repeat and CPU/GPU profiling are needed before choosing an optimization.

## Rerun after competing Metal process stopped (2026-09-19)

The user stopped another Metal process, then the identical binary, model, prompts,
settings and warmup/repetition protocol were rerun. This supersedes treating the
earlier run as representative of performance without that competing workload.
It is still a live desktop measurement, not proof of exclusive GPU access.

| Prompt tokens | First text, seconds | Streaming, tokens/s | Total for 64 tokens, seconds | Streaming speedup |
|---:|---:|---:|---:|---:|
| 102 | 0.26 [0.24–0.26] | 43.75 [41.82–46.38] | 1.70 [1.60–1.77] | 2.89× |
| 1617 | 3.85 [3.14–7.97] | 36.63 [35.02–37.72] | 5.52 [4.86–9.77] | 5.87× |

Values are medians [minimum–maximum] of three measured runs. Every output still
contains 64 tokens and is byte-identical to its corresponding earlier output.
Model/context setup took 1.08 seconds.

Streaming is now substantially faster and more consistent. This strongly supports
the competing workload as a major contributor to the previous slowdown. Longer
prompt first-text latency remains variable (3.14–7.97 seconds); GPU contention,
scheduling or other causes cannot be distinguished from these timings alone.
A reasonable measured streaming baseline for these two workloads is now roughly
35–46 tokens/s. It is not a guarantee at all context lengths or during compaction.

Per-run metrics and hashes: [rerun results](native-speed-rerun-results.json).
Original results are preserved for comparison.

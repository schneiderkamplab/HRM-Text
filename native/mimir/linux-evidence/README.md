# Linux qualification evidence

These compact artifacts support [the Linux report](../LINUX-TESTING-REPORT.md).
Large model files, raw server logs, build trees, and Nsight trace databases remain
in `logs/linux-prefixlm/` on the qualification host; they are not committed.

- `performance.json`: original and post-fix ABBA command lines, all raw timing
  samples, per-round summaries, and baseline drift. Each invocation has 25
  samples; statistics discard the first five.
- `mask-profile.json`: before/after direct host-mask timings. The 26 calls are
  one warmup plus 25 benchmark repetitions; summaries discard the first six.
- `causal-baseline.json`: identical causal controls on the pristine base and fixed
  candidate, including CPU and CUDA flash off/on. This comparison establishes
  the pre-existing numerical failure only for the tested causal control rows.
- `pre-fix-oracles.json`: original strict tiny and real-model errors, shared-owner
  rows, top-token agreement, and NLL differences. Current reruns are recorded in
  `../linux-results.json`.
- `ownership.json`: physical occupancy, allocated KV bytes, process high-water
  RSS, and copy/flush latency for the ownership microbenchmark.
- `request-performance.json`: real templated BF16/Q8/Q4 requests, layouts,
  near-limit/mixed workloads, resource data, and save/restore timings. These
  capability measurements precede the mask specialization; they are not claims
  of final-revision absolute throughput.
- `input-sha256.json`, `environment.json`: pinned inputs and installed environment.
- `causal_oracle.cpp`, `profile_mask.cpp`: diagnostic sources. The first uses the
  common public decoder API and the generated reference specification; compile
  separately against baseline/candidate headers and libraries. The second is an
  LD_PRELOAD timer for `llama_kv_cache::set_input_kq_mask`; set `MASK_PROFILE` to
  an output CSV path. Diagnostic timings do not replace uninstrumented ABBA runs.

Commands contain the original absolute workspace paths. Adapt paths when
replaying on another host; preserve compiler, model bytes, affinity, backend,
flash mode, batch/context sizes, and repetitions. See the repository
[Linux testing guide](../../../linux-testing.md) for fixture/build commands.

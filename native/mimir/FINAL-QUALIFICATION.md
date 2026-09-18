# Final qualification and packaging preparation

2026-09-18. The user accepted the existing numerical findings as nonblocking for
this PR scope and asked to finish qualification policy and prepare packaging.
Runtime source remains exactly the Linux-tested commit
`8f4f4ef8f3139d7d262763936f1f34e48ad46d9c`. No CUDA kernel, attention semantics or
runtime serialization changes accompany this preparation.

## Acceptance decisions

| Finding | Disposition and limit |
| --- | --- |
| Tiny CUDA oracle exceeds 1e-4 | Accepted documented numerical limitation for review. Maximum error ~0.0023, 130/130 top choices match; tested causal baseline/candidate errors are identical. This does not attribute every PrefixLM discrepancy to the backend. |
| Real BF16/Q8/Q4 exceed the shared FP32-reference 0.03 limit | Accepted precision/quantization evidence for this scope, not a PrefixLM release blocker. Preserve maxima, RMS/NLL and top-token differences. No universal precision tolerance or broad language-quality claim is introduced. |
| Graph-enabled memcheck reports error 910 | Accept only the existing handled graph-update fallback under the policy below. Memory findings and unexpected API errors remain fatal. |

`linux-results.json`, its strict pass/fail fields, raw evidence and original
thresholds remain unchanged. Acceptance is a separate decision, not a rewritten
measurement. CPU oracle, semantic ownership/masking tests, persistence parity,
application completion and regression tests remain hard gates. New numerical
behavior outside the recorded revision's evidence requires investigation rather
than inheriting this acceptance automatically.

## CUDA sanitizer policy

The unmodified upstream function `ggml_cuda_graph_update_executable` calls
`cudaGraphExecUpdate`, handles `cudaErrorGraphExecUpdateFailure` by clearing the
last error, and destroys/recreates the executable graph. NVIDIA documents that
an update may fail when its constraints cannot be satisfied. Compute Sanitizer
reports API return errors even when the application handles them.

The new `tests/cuda_memcheck.py` runner:

- Keeps API reporting enabled (`--report-api-errors all`) and leak checks enabled.
- Uses `--error-exitcode 0` to preserve the application's own failure status;
  the Python wrapper supplies the final CI failure status after examining the log.
  Never use the raw sanitizer exit code with this option as a standalone gate.
- Requires a complete sanitizer banner/summary, a zero application exit status,
  a successful-test marker and agreement between reported and parsed error counts.
- With explicit `--allow-graph-fallback`, accepts only ordered pairs of error 910
  (`cudaErrorGraphExecUpdateFailure`) from `cudaGraphExecUpdate` then `cudaGetLastError`.
  Without this option, all reported errors fail (including the sampler lane).
- Rejects memory/leak errors, other API errors, unknown output formats, incomplete
  logs, mismatched counts and missing test completion. It preserves raw tool/application
  logs, their hashes, command, policy and result JSON.
- Uses a fresh isolated working directory per invocation, avoiding the engine tests'
  shared temporary state-file collision. Pass absolute model and binary paths.

The classification exception addresses one known control-flow outcome; it is not a
blanket CUDA error suppression. If a different toolkit prints an unrecognized
format, preserve the raw log and review it before changing the classifier.
Graph-disabled diagnostics remain useful but do not replace graph-enabled checks.

References: [CUDA graph update API](https://docs.nvidia.com/cuda/cuda-runtime-api/cuda_runtime_api/group__CUDART__GRAPH.html)
and [Compute Sanitizer API reporting/exit status](https://docs.nvidia.com/compute-sanitizer/ComputeSanitizer/index.html).

## Prepared package

[release-candidate/](patches/release-candidate/README.md) contains four numbered
patches: ggml UB fix, text codec, main PrefixLM, and generic generation persistence.
The Linux include/performance fix is folded into the main patch. Standalone
persistence remains an alternative application, not a fifth dependency.

`tools/package_patches.py` verifies application using a temporary Git index and
compares the final Git tree byte for byte (including file modes) with the qualified
commit. It also verifies the main-only and standalone public API boundaries.
Existing commits and historical draft files are not rewritten. The package is a
candidate pending the final checks below, not an upstream submission.

## Final bounded checks

1. Fetch the parent testing branch and initialize the pinned llama.cpp submodule.
   Verify `release-source-manifest.json` and run `tools/package_patches.py` and
   `tests/test_cuda_memcheck.py`. The workflow runs the same preflight.
2. On Linux, rerun the existing CPU ASan/UBSan CTests plus explicit host/backend
   sampler and parser tests using the pinned source. The prior Linux sanitizer
   runs passed; this is the final candidate check, not new feature coverage.
3. On one allocated CUDA device, run the graph-enabled HRM and Llama suites and
   backend sampler through the new runner, using the commands in `linux-testing.md`.
   Verify actual CUDA offload in saved output. Preserve raw logs and classification
   JSON. Do not assert this new runner has passed real CUDA until those results exist.
4. Review the four-patch scope and public API/state contracts. No broad BF16/Q8/Q4
   rerun or tolerance adjustment is required for byte-identical runtime sources.
   If code changes, refresh package/manifest and rerun the affected qualification.

Already checked locally during preparation: candidate tree reconstruction;
five sanitizer policy/runner tests including negative cases and simulated process
failures; current runtime macOS release and CPU UBSan regression each pass 8/8 CTests.
[preparation-results.json](preparation-results.json) retains the bounded local outputs. Unit fixtures are
synthetic and are not CUDA execution evidence. Final Linux runner validation and
GitHub workflow execution remain pending; no green run is fabricated.

The current release source manifest includes the updated harness/CI. The earlier
Linux and Mac manifests continue identifying their historical executions.

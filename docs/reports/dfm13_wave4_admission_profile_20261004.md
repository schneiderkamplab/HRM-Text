# W4 Admission Parser Profile and Successor

Nonblocking py-spy against PID3179944 was denied by process-inspection
permissions, including sudo-n; no signals/stops or live-pin edits. Readable
20.043s /proc thread deltas found24.85CPU seconds total,9.2s on the main thread
(45.9% of one core),625 threads. This does not establish Python stack attribution
or a continuously CPU-saturated event loop. Evidence:
`data/dfm13/wave4/batch16-thread-profile-20261004-v1.json`.

Concrete offline hot path: existing admission_metrics parses every family/label
in the57.9KB Prometheus document synchronously for each admission. cProfile200
replays took2.84s, dominated by prometheus_client label parsing; profiler overhead
included. Unprofiled500 replays: original4.894ms versus filtered0.259ms,18.90x,
identical gate signals. Evidence:
`data/dfm13/wave4/admission-filter-benchmark-20261004-v1.json` and
`data/dfm13/wave4/batch16-admission-parser-profile-20261004-v1.json`.
This is parser speed, not measured campaign-throughput improvement.

Isolated `dfm12.wave4_admission_fast` retains the proven Prometheus parser on only
the three exact KV/waiting sample names and their HELP/TYPE lines; malformed,
missing, nonfinite, negative or out-of-range relevant signals remain rejected.
Quoted-name extension falls back to the full parser. Private gate globals only;
base signal bounds, queue/KV thresholds, cooldown/health probes unchanged.

Harvey deployment: retain all inherited pins/independent authorization; add
`admission_parser_runtime_module=dfm12.wave4_admission_fast` and module SHA256
`73f9f08ffdbfa8570e13ee6297b0e8f711c6b2e42dc2de6f141fb6322047069b`.
Command: `python -u -m dfm12.wave4_admission_fast --root <W4_ROOT> --launch-mode independent`.
Existing batch launch verification is privately rebound, not bypassed. No
competing launch.11 parser-specific tests pass; warm production effect pending.

# Exact streaming loop-guard prototype

New isolated module: `dfm12/calibration_loop_guard_fast.py`.
The live pinned `dfm12/calibration_streaming.py` was NOT edited or patched.
No clients, servers, manifests or seals were changed. No GPU calls were made.

## Measured Evidence

Selected the60 newest terminal accepted/valid/review-invalid/generation-invalid
jobs from Baltic synthetic-compact-26b-20261004-v1 using SQLite mode=ro.
Read their saved generation/review stage references and raw response JSON;
104 usable SSE captures comprised60 generation and44 review streams,
19724 content-delta calls (including empty deltas),55284 content characters.
Parsed actual saved SSE events, not retokenized text or fabricated token chunks.
All104 raw file hashes and timing samples are in
`dfm13_loop_guard_benchmark_20261004.json` next to this report.

Five alternating old/new replay runs, after warmup, measured process CPU time:

| Replay | Original median | Prototype median | Speedup |
| --- | ---: | ---: | ---: |
| Guard calls alone | 138.30 ms | 7.89 ms | 17.53x |
| Existing strict_json decode plus guard | 194.68 ms | 63.49 ms | 3.07x |

Original cProfile replay:724ms total instrumented time,604ms cumulative feed,
including3,826,560 len calls. Instrumentation overhead means these profile times
must not be mixed with unprofiled medians. It identifies the guard as a major
cost in this replay; it does NOT prove that it consumes83% of the live event loop.
Measured savings are approximately6.6 microseconds per delta in this sample.
These relatively short real streams may benefit especially from skipping the
original193 size checks when the tail has fewer than512 characters. No whole-run
throughput multiplier or attribution of all observed119% CPU is claimed.

## Exact Semantics

Whitespace, quoting, escape tracking, early whitespace return,2048-character
tail retention and reason strings are copied unchanged. For repeated text,
maximum viable size is min(256,len(tail)//8). Eight equal blocks require the
character one block before the tail end to equal the last character. rfind scans
only positions corresponding to sizes64..maximum, right-to-left, so candidates
are checked in the original ascending order. Every candidate still undergoes
the identical `tail[-size:] * 8 == tail[-size*8:]` comparison. This necessary
condition cannot exclude a true repeated suffix. No fuzzy matching, sampling,
reduced repeat threshold, reason change or guard disabling is introduced.

Real replay compared return values and complete instance state after every feed.
Tests additionally cover1000 seeded randomized chunked streams,3000 randomized
tail comparisons, Unicode, empty deltas, escaping, whitespace early returns,
7/8/9 repeats around block-size boundaries63/64/65/127/128/193/255/256/257, and
explicit ascending candidate-check order. These are deterministic equivalence
tests, not formal exhaustive proof over every Unicode stream.

## Boole Integration Handoff

Recommend a controlled private successor only if main chooses to deploy.
After offload installation creates the private stream_query namespace, replace
ONLY its `LoopGuard` binding with this module's LoopGuard. For the current
private offload implementation the binding is
`controller.stream_query.__globals__['LoopGuard']`; verify namespace ownership
before assignment and include the new module in the successor's implementation
pins. Do not mutate the imported original streaming globals or a live pinned
module. Drain/migrate/restart remains Boole/main ownership; no such action was
performed here. After deployment compare live accepted/request rates and CPU
under similar workload; other serialization, provider and storage costs remain.

CPU check:
`python -m pytest -q tests/test_calibration_loop_guard_fast.py`.

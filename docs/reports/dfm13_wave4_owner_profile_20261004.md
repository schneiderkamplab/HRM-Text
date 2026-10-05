# W4 feeding: read-only profile

PID3120078, current single-owner offload runtime. No signals, code changes or
server requests were used for profiling. Baltic proof3120820 remains running.

`dfm13_wave4_owner_profile_20261004.json` captures100 wait-channel samples over
5.012s. Owner TID3120089:45 commit_blocking_request,5 folio_wait_bit_common,
28running,22futex. Main thread:49ep_poll,35running,14futex,2commit waits.
Process write_bytes increased39,710,720 and wchar34,495,641 in this interval.
This bounded snapshot implicates storage/commit serialization, not a measured
per-function CPU breakdown. Kernel stacks were permission-denied; py-spy is not
installed. No profiler installation or intrusive attachment was attempted.

Code path:
- The same one-thread Owner executes ledger/provider calls, tokenization,
  schema validation, assembly, stage files and raw writer begin/finish.
- RawResponseWriter writes request and response JSON through atomic(), which
  flushes and fsyncs each file before rename. Stage/outcome/spec files also use it.
- SourceProvider.next_spec holds a selections transaction, opens a read-only seed
  connection per seed, advances persistent cursor/used_sources and commits.
- Ledger and selection databases use WAL + synchronous=FULL. Reservation,
  terminal commit and fingerprint claim must retain single-owner serialization.
- EXPLAIN QUERY PLAN for the actual available_seeds query uses indexed pool/seq
  lookup and indexed exclusions, not an observed giant prefix/full-table scan.

The earlier async fix freed the event loop but put unrelated I/O/CPU behind one
queue. Increasing HTTP workers cannot remove this serial dependency. Boole's
proposed split should keep SQLite/provider/fingerprint operations on their owner
while distributing independent raw files and CPU validation/tokenization across
bounded workers. Preserve per-stage ordering (request durable before send, raw
response durable before validation, accepted artifact before credited ledger),
unique writer IDs, cancellation joins and exact rendered/decoded results.
Do not weaken fsync, quality checks or replay unknown requests to improve rates.

Source-provider optimization beyond this split should be separately measured;
read connection reuse may help, but query-plan evidence does not justify changing
selection semantics or concurrent cursor mutation. Hundreds of sleeping native
threads are not hundreds of Python CPU workers.

Operational ownership: Boole owns replacement files/tests; this worker owns
the coordinated W4-only drain/reseal/restart after readiness. Do not stop the
current client or Baltic background proof before that coordination.

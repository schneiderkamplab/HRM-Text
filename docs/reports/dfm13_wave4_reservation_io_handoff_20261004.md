# W4 Reservation I/O Successor

Final module `dfm12.wave4_reservation_io`, SHA256
`e0c276d45caf9b4c701c8ea304661008717e2e1601b1ba8d8fbc40d0cc668c0c`.
Supersedes the pre-fast-guard hash recorded in the earlier handoff.
No changes to pinned parallel I/O/base dependencies. Harvey owns controlled
drain, seal migration and restart. Keep prior parallel16 and launch-contract
fields; add `reservation_io_runtime_module=dfm12.wave4_reservation_io` and
absolute implementation pin. Command:

```bash
python -u -m dfm12.wave4_reservation_io --root <W4_ROOT> --launch-mode independent
```

The original atomic SQL reservation stores complete spec_json before a parallel
durable specification-file write. The caller awaits that write before constructing
stages or issuing HTTP. Failure/cancellation leaves a durable running allocation
that original recovery marks unknown, consuming the slot without replay; no
relaxed FULL commit, removed fsync, or rollback of source cursors.

Gate remaining checks read an owner-published boolean rather than performing two
SQL queries/candidate. Owner maintains cached accepted/attempt counts after reserve
and finish, respecting restricted groups; SQL reserve remains authoritative for
active quota, attempt cap, cursor and source availability. Recovery refreshes
counts from SQL for pre-existing jobs. A hint never grants an allocation itself.

Tests cover commit-before-file visibility, durable completion before returning
the job, write failure/cancellation without request artifacts, original unknown
recovery, duplicate finish/recover, active quota/attempt exhaustion and gate
callbacks without SQL. Existing full mocked W4/parallel tests remain in suite.
Production throughput improvement remains unmeasured until Harvey deploys.
Persistent readonly seed connections are explicitly not part of this patch.

Before deployment, user approved Epicurus's exact-parity fast guard in this same
successor. Only the private `c.stream_query.__globals__['LoopGuard']` is replaced;
shared streaming globals stay unchanged. Launcher requires the additional pin
`dfm12/calibration_loop_guard_fast.py` SHA256
`48843de0e8b81e4cb8d148b87d5cb5566784c4f7ecf4b3720c688ee97bb96300`.
54 combined tests passed including fast guard parity and private-binding isolation.

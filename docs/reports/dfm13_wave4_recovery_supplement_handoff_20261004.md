# W4 isolated CPU recovery handoff, 2026-10-04

## Final all-LB release policy

Latest user authorization supersedes LB35000: retain ALL original LB accepted
rows plus ALL valid unique technical recoveries, with no old LB family ceilings.
Exact verified LB eligibility is70471; original LB accepted20372; combined90843.
Other ten languages retain70000 each, for expected combined790843.

Current campaign is terminal with646551 original accepted, active0, all eight
clients exit0. CPU release supervisor PID3427653 is actively packaging at
`data/dfm13/wave4/empty-rationale-all-lb-release-20261004-v3` using
`dfm12.wave4_recovery_release`. It requires terminal/zero-active owners, NOT
completion of the obsolete770000 target. It uses64 bounded I/O workers to recheck
every selected proof hash and write new candidate/receipt files; a single SQLite
writer commits the supplement. Resumption retains identical existing files and
rejects drift. Source ledgers, raw evidence, source selections and accepted files
remain unchanged. Completion is `manifest.json`, not merely `progress.json`.

## Clean-keep integration API

`dfm12.wave4_clean_keep_review.install(private_controller)` returns the same
controller. Install LAST, after compact/group adapters, and pin this new module
in any successor manifest. It changes BOTH the review-request CPU schema and
the final validator adapter; saved proof verification selects the exact stored
old/new contract. Shared/frozen modules are not edited. Nonkeep empty reasons,
keep-with-issues, incomplete length stops, missing fields and deterministic
failures remain rejected. No rationale is fabricated.

Eight focused adapter tests pass, including the exact saved empty-rationale JSON
through real `Stages.call` and final `review_result`, nonkeep/structural failures,
length finish rejection, deterministic veto and original-schema immutability.
Recovery release tests cover uncapped LB, unchanged other quotas, proof tampering
and resumable unchanged package copies. No new GPU calls are needed.

## Authorized256-worker successor

**Completed eligibility / drain handoff:** all256 partitions completed and merged.
The prepared report contains1142896 verified eligible rows. Old770K projection
shortfall15902 is entirely LB grounded/summary; non-LB shortfall is zero.
`735k-projection.json` records a later rolling read:645853 original accepted,
89147 recoveries needed, zero projected residual shortage. LB has20372 original
accepted and needs14628, with33726 verified eligible rows even after capping at
old family gaps. These are not final admission counts while active jobs remain.
Harvey: drain the current pass; do NOT launch additional GPU top-up on this
evidence. Terminal735K allocation and package export should follow that drain.
The old finalizer was intentionally stopped for quota safety, not a crash.

**Quota supersession:** subsequent authorization changes the nominal campaign
goal to735000 (LB35000, others70000), retaining all accepted rows. The waiting
legacy-quota finalizer3418760 was stopped before any release, with receipt
`empty-rationale-recovery-256-20261004-v2.finalizer-held-735k.json`. CPU verification
continues unchanged. Finalization must use the explicit successor allocation in
`data/dfm13/wave4/topup-preparation-20261004-v1/coordination.json`, not silently
credit against the original770000 group quotas. Existing accepted surplus must
not be deleted to force nominal targets. This supersedes automatic finalizer
readiness described below.

Supersedes the running two-worker preparation below, not its saved evidence.
User explicitly authorized256 CPU workers. Coordinator PID3417763 runs
`dfm12.wave4_recovery_parallel` at
`data/dfm13/wave4/empty-rationale-recovery-256-20261004-v2`.
Original scanner3412251, worker3412270/3412271 and finalizer3413155 stopped;
the old scanner had no cooperative queue-cancel hook, so SIGINT was followed by
SIGTERM for remaining verified owned processes. Committed WAL data is preserved,
and the stop receipt records no remaining owned processes. Incomplete transactions
are not counted as completed; their rows remain eligible for rechecking.

The successor copies every committed proof/exclusion via SQLite backup, snapshots
candidate IDs once per source DB, excludes all already-checked IDs, and partitions
remaining IDs deterministically into32 subparts per each of eight source shards.
256 separate result databases each have exactly one process writer. Existing
rows are not retokenized. Student tokenizer pages load before fork for COW sharing;
all native thread pools are capped1. Individual workers support cooperative
stop-after-current-row with committed checkpoints and same-root resumption.
After workers exit, one coordinator merges results into the eight compatibility
databases; duplicate IDs/fingerprints fail closed.20 focused tests pass.

Launch verification: all256 child processes were present and all256 partitions
reported progress. Plan retained65500 committed prior checks, excluded those IDs
from revalidation, and assigned1087323 new checks from1152823 observed failures.
The first observed new progress was62700 checked/62141 eligible/559 excluded.
These are technical eligibility counts, not admitted recovery packages. Summed
worker RSS was96.72GB (including shared pages counted repeatedly).

New finalizer PID3418760 has its command receipt at the successor basename plus
`.finalizer-launch.json`. It waits on this new root and exports only after terminal
quota checks to `data/dfm13/wave4/empty-rationale-recovered-supplement-20261004-v2`.
Do not consume or restart the superseded v1 finalizer. GPU clients and all live
campaign/source/registry ledgers remain untouched.

Owner coordination: Harvey retains all generation/runtime ownership. Tesla's
finalization should consume this supplement only after its release manifest
exists, never the eligibility databases alone. No active group ledger, raw stage,
outcome, source selection, accepted directory, or global registry is modified.

## Running preparation

PID3412251, two CPU worker processes, detached; no GPU/model requests.
Terminal-only finalizer is also detached, PID3413155. Its command/pin receipt is
the preparation basename plus `.finalizer-launch.json`; wait status is
`.finalizer-progress.json`. It cannot promote while any owner holds its lock.
Module `dfm12/wave4_recovery_supplement.py` SHA256:
`e203837982b4a6498f8d69ddc95cc8815b2ff4be08fe705bf20e702f5d4fd709`.

```bash
python -m dfm12.wave4_recovery_supplement prepare \
  --bundle data/dfm13/wave4/synthetic-group-shards-20261004-v2 \
  --output data/dfm13/wave4/empty-rationale-recovery-20261004-v1 --workers 2
```

Launch receipt/log use the same output basename plus `.launch.json`/`.log`.
Do not launch a duplicate. Per-shard progress and SQLite results commit every100
checks. `report.json` will cover all66 groups with exact inspected eligibility,
current accepted totals, quota-capped projections and projected shortfalls.
Because owners remain live, those projections explicitly are NOT final quotas.
The first committed2200 checks yielded2182 eligible/18 excluded; that is not a
whole-corpus estimate. Initial two shard inventories alone total261149 failures,
so full verification is a substantial CPU/I/O pass, not a minutes-only promise.

An interim rolling read of all66 groups is saved as `interim-66-groups.json`:
621181 original accepted,148819 remaining,1119531 review-invalid candidates.
These source totals were read while owners continued, not one global atomic
snapshot. At the subsequent163-second progress check,22100 rows had completed
CPU checks (21888 eligible,212 excluded), about135 checks/second. At that rate,
full eligibility inspection is roughly2-3 hours, subject to source-family and
shared-filesystem costs; final packaging is additional. Zero recoveries admitted
at this point. Later `report.json`/release manifest supersede these observations.

## Proof contract

Reuse original `compact_keep_recovery.inspect_job`, then additionally verify
durable source-selection spec, original eligible seed payload/hash, both local
and global fingerprint ownership, full raw HTTP/SSE reconstruction and request
bindings for generation and review. Original assembly revalidates all candidate
constraints and every untrimmed assistant target at4096 student tokens or less.
Every saved file used is hash-bound in the row receipt. Source rows/raw decisions
remain unchanged; no rationale is fabricated and no human review is claimed.

Only existing production `review_invalid_output` rows with the nonempty-schema
failure and exact complete `stop` + `{verdict:keep,issues:[],reason:""}` qualify.
Actual nonkeeps, interrupted/unknown calls, length stops, holds, ownership loss,
changed sources, invalid candidates and changed raw evidence cannot qualify.
18 focused tests pass, including raw/request tampering, transport failures,
readonly DB protection, no promotion before terminal, existing narrow rationale
and deterministic gates. One real FA row passed the complete proof and rendered
to101 student tokens with10 pinned evidence files before bulk launch.

## Terminal-only supplement

`scripts/finalize_wave4_recovery.py` waits for both preparation and campaign
terminal receipt; it also acquires supervisor plus all eight controller locks.
It then computes actual remaining group quotas and selects eligible IDs in sorted
order, rechecks saved hashes and live terminal ownership/outcomes, and exports to
`data/dfm13/wave4/empty-rationale-recovered-supplement-20261004-v1`.

Release contains `supplement.sqlite`, copied unchanged candidates under
`accepted/`, separate proof `receipts/`, and `manifest.json` with66 group totals,
recovered counts and exact residual shortfalls. The original campaign's accepted
counts are NOT rewritten; report combined original+supplement counts explicitly.
The supplement must not be admitted twice. Its finalization is independent of
GPU generation and does not restart or signal any process.

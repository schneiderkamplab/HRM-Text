# W4 shard runtime handoff, 2026-10-04

## Group successor compatibility check

The subsequently prepared `dfm12.wave4_group_runtime` was independently inspected
without editing its code. Group runtime, rebalance, and shard tests pass12,
including full mock HTTP with real ledger/global claims and blocked-group
exclusion. Its `--root` CLI matches `scripts/supervise_wave4_groups.py`; inherited
run uses768/server and the assigned endpoint. Explicit language/family pairs
replace whole-language ownership, without quota or candidate-budget changes.
Inspected SHA256: `25295f2b94b5a9289accfff840418391aade9084093c48922da4785fdc2768c9`.
This check does not assert deployment or measured throughput; Harvey owns launch.

Implementation: `dfm12/wave4_shard_runtime.py` (CPU-tested, ready for deployment sealing).
Frozen runtime SHA256: `66fbde2c2b0dfb0cc7ad66c52065a66d37a1f5f2d5b9c99caa883646481bd4e1`.
Harvey owns partition migration, launch supervision, and the actual drain.
No servers or live campaign files were changed by this implementation.

CLI: `python -m dfm12.wave4_shard_runtime --root <partition>/shard-0`
Each process uses exactly its ownership endpoint with concurrency768 and zero
spacing; existing private generation/review/repair/durability policies remain.

Required immutable inputs in each shard: byte-identical original `manifest.json`,
`seal.json`, and every original manifest `input_pins` file (including config).
The partitioned ledger retains the original manifest metadata hash. Do NOT edit
its target manifest to pretend the shard has the original full770K quota.

Partition root `shard-runtime.json` contract:

```json
{
  "runtime_module": "dfm12.wave4_shard_runtime",
  "launch_authorized": true,
  "prepared_sha256": "SHA256 of prepared.json",
  "implementation_pins": {"absolute module path": "sha256"}
}
```

Pins must include all original implementation pins plus shard_prepare,
shard_runtime, admission_fast, batched_runtime, disk_pipeline. Prepared ownership
files remain unchanged, including historical launch_authorized=false; the separate
runtime seal authorizes execution. `prepared.json` remains the immutable migration
receipt. Its mutable DB hashes are migration evidence, not resume-time pins.

Verification checks eight disjoint whole-language assignments, exact coverage of
original group quotas, selected shard quota slice, original source manifest/input
and implementation hashes, accepted global fingerprint ownership, and a drained
original campaign. Generic full-campaign verification is not weakened.

Global fingerprint claims run on the shard owner thread but OUTSIDE the local
batch transaction. Global commit precedes local fingerprint insertion. If the
local operation fails, the global claim remains reserved for that candidate;
another candidate cannot reuse it. Unknown jobs retain existing no-replay rules.

Offline profile evidence: `data/dfm13/wave4/ledger-clone-profile-20261004-v2/report.json`.
Sixteen unprofiled batch16 reservations mostly took3-13ms, with one109ms outlier;
eight profiled batches took234ms total. This does not prove a particular GIL
stack, but does not support another batch-size-only fix for live76-150ms timings.

Combined runtime/partition/batch/I/O/admission tests pass55, including actual private execute with mock HTTP, real local
ledger and global registry, one-endpoint validation, both raw responses saved,
cross-shard concurrent duplicate claims, committed global claim/local failure,
no global claim under a local transaction, owner-thread SQLite creation/use/close,
and exact private `_claim`/`verify` namespace bindings. No live deployment or
throughput improvement is claimed by these CPU results.

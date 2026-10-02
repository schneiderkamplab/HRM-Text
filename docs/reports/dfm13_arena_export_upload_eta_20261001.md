# Eight Arena datasets: export/upload handoff and ETA

Read-only CPU inspection, 2026-10-01. RepoChat/Search excluded. No export,
admission, upload or GPU work started. Estimates are planning ranges, not timed
benchmarks or unconditional deadlines. Cached HF authentication passed `whoami`;
token reports write role and schneiderkamplab membership. No token was printed.
Actual repository-specific write permission is not proven until publication.

## Current counts and marginal timings

Accepted counts are before independent holds, final dedup and mask validation.
Payload estimates scale measured input bytes by accepted fraction; repaired
lengths and provenance sidecars can change these estimates. Sizes exclude private
raw audit data, which must not be uploaded.

| Dataset | Accepted snapshot | Approx data MiB | CPU package/validate | Upload/verify |
| --- | ---: | ---: | --- | --- |
| AI Arenaen | 2,341 | 9 | 1-3 min | 1-3 min |
| Arena 100K | 52,668 | 222 | 5-15 min | 2-8 min |
| Arena 140K | 88,775 | 650 | 10-25 min | 3-15 min |
| Arena 55K | 30,441 | 73 | 3-10 min | 1-5 min |
| ComparIA | 401 | 2 | 1-2 min | 1-3 min |
| HelpSteer3 edit | 6,321 | 45 | 2-5 min | 1-4 min |
| HelpSteer3 preference | 16,877 | 146 | 3-10 min | 2-6 min |
| Expert5K | 1,883 | 28 | 1-4 min | 1-4 min |

Upload assumes effective 5-25 MiB/s plus HF commit/validation latency. No upload
benchmark was run. CPU ranges assume <=16 workers with current-load allowance,
target-only render/token checks and streaming hashes. They exclude retries or
fixing newly discovered data defects. Estimated public train payload total is
about 1.15 GiB before sidecars; provision roughly 1.2-1.6 GiB public payload, not
the potentially much larger private ledger/raw snapshots.

Next-four root `logs/arena_audit/20261001-pending-next-repairs-v1` has
`complete.json`; accepted total 25,482. Main root
`logs/arena_audit/20261001-repairs-followup-v1` lacks completion. Snapshot:
AI/100K/140K fully classified; 55K has 49 outstanding/inflight rows. Main global
terminal gate blocks all four until completion/unlock. With 600-second attempt
timeouts and bounded retries, budget 5-30 additional minutes for the tail, but
this is not a guarantee and failures may remain excluded rather than retried.

## Shared prerequisites and end-to-end estimate

Current old exporters `scripts/export_dfm13_arena.py` and
`scripts/export_dfm13_ai_arenaen.py` copy pre-audit converted rows. They are NOT
safe commands for accepted-ledger publication. `dfm12.upload_exports` offers a
useful explicit-inventory/commit/receipt pattern but enforces `dfm12-` names and
DFM12 manifests. Do not relabel DFM13 data or invoke it unchanged.

A small DFM13 accepted-ledger exporter/validator/uploader adapter and focused
tests are still needed. Allow approximately 30-60 minutes engineering/CPU
preflight, conditional on approved sample receipts and owner coordination.
Then next-four package/upload work is roughly 15-40 minutes as a batch; main
four roughly 30-75 minutes after terminal readiness. Thus provisional delivery
windows from work starting are **45-100 minutes next-four**, **60-135 minutes
main-four**, plus any unbounded approval/hold resolution or network delay.
These are not promises that work is already running. All eight can pipeline;
do not sum overlapping per-dataset timing columns as a strict wall-clock ETA.

## Concrete execution sequence

1. Reuse Epicurus's **current** `scripts/dfm13_arena_export_readiness.py` v2
   `prepare`/`enforce`; no duplicate guard. Supersedes the earlier handoff's
   missing recovered-keep support: it now validates completed retry attempts,
   corrected target-only content, terminal/unlocked ledgers, evidence digests and
   sample-scoped manual receipts. No guard code changed in this inspection.
2. For finished next-four, freeze new read-only snapshots/selections now when
   execution is assigned. Main waits for matching completion counts, no inflight
   attempts and released controller lock. Preserve original lineage identity.
3. Select exactly once per source ID: original completed keeps via original
   jobs ledger; recovered unchanged keeps via repair accepted+retry proof;
   repaired keeps via candidate+correction+fresh keep proof. Subtract existing
   hash/source/ledger holds through the guard; exclude rejected, needs_review,
   technical unresolved and conflicting rows. Do not turn source-level holds
   into exact-hash-only bypasses. No old-original plus corrected duplicate.
4. Bind a truthful terminal manual receipt to each exact selection, current
   holds and assessment. Use `review_scope=sample` with reviewed/population
   counts, method and limitations when sample-based. `whole_target_reviewed`
   means complete reviewed targets, not every population row manually reviewed.
   Keep `quality_certified=false`; do not claim manual verification of all rows.
5. Materialize eight isolated packages in a NEW audited snapshot root. Preserve
   full messages, native tools, target_message_index and original source metadata;
   write audit provenance separately with original/candidate/output hashes.
   Pin raw current Gemma tokenizer/template, no Mistral fix. Validate assistant
   target-only masks, preserved preceding context and no silent truncation.
6. Final exact dedup includes messages, target index, tools and template kwargs;
   retain duplicate attribution and report inherited/held-out coverage. Preserve
   next-four screening receipt and post-repair overlap checks. License cards
   distinguish prompt/provider/teacher terms; PRISM remains excluded.
7. Enforce readiness again, validate row/hash/count conservation and package
   paths, then publish only explicit package file inventories using cached HF
   auth. Record repo/commit SHA and verify remote bytes/inventory. Never upload
   root/private metadata. Use eight unique audited package names, and separately
   propose replacing the four old config additions instead of appending both.

Example existing guard invocation (only after real selection/manual receipt):

```bash
python scripts/dfm13_arena_export_readiness.py prepare --ledger <ledger.sqlite> --selection <selection.json> --manual-review <sample-review.json> --receipt <new-readiness.json>
python scripts/dfm13_arena_export_readiness.py verify --receipt <new-readiness.json>
```

No audited export CLI exists yet in the inspected utility set. Naming an
unimplemented export command as runnable would conceal the remaining work.
Blockers: adapter/tests, exact post-filter selections/receipts, mask/dedup/license
validation, main terminal gate, explicit publication execution coordination.

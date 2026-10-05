# Wave-4 failed audit disposition, 2026-10-03

## Scope and conclusion

Read-only rolling snapshot at 18:39:36-18:39:44 UTC: **14,625 primary audit jobs marked failed**, all with four attempts. This is not a count of unrecoverable or unreviewed release candidates. Primary failures remain recorded after successful recovery. No explicit infrastructure-error signature or orphaned infrastructure retry was found; no reset or code fix is justified by this snapshot.

The initial count was 14,593; live processing advanced during the short reads. Indexed keyset batches and scalar JSON extraction avoided whole payload loads and long transactions. A fixed rowid ceiling bounded the scan. Counts below belong to this frozen rolling snapshot, not the continuously changing queue. `receipt.json` hashes `jobs.jsonl`, `report.json`, and `inspect.py`.

## Failure signatures

| Signature | Jobs |
|---|---:|
| Incomplete output: length | 9,040 |
| JSONDecodeError | 5,584 |
| Invalid audit scores | 1 |
| Explicit transport/HTTP infrastructure errors | 0 |

JSON parse errors alone do not prove their origin was generated text rather than an HTTP response. Treat them as parse failures, not independently proven hallucinations or infrastructure outages. Length/schema signatures concern output validation, not semantic quality of the underlying candidates.

Largest components: direct-hr-sq 3,385 (2,304 length, 1,081 JSON); direct-bs-sq 2,663 (1,783/880); direct-sq-sr 1,115 (859/256); direct-ro-sr 679 (464/215); direct-ro-sq 589 (224/365). Full source/error cross-tabulation is in `report.json`.

## Release dispositions

| Release state | Jobs |
|---|---:|
| No release ledger yet | 13,344 |
| Ledger busy; deliberately not blocked | 251 |
| audit_retry_pending | 369 |
| accepted | 325 |
| accepted_repair | 14 |
| rejected | 265 |
| repair_rejected | 25 |
| excluded_unreviewed | 30 |
| repair_pending | 2 |
| **Total** | **14,625** |

All 13,344 without ledgers belong to **68 direct-translation components**. Follow-up checked every one against `audit/translation-manifest.json` and `translations/config.json`: zero components absent from the manifest, zero pairs absent from requested_pairs. The sequential selection finalizer PID 2143812 was running; its loop calls the normal release processor for matching components and revisits unready pairs. This supports finalizer backlog, not an uncovered-source retry gap. The 251 busy rows all belong to direct-bg-hr and remain explicitly unknown in this snapshot.

The 369 pending ledger entries point to 269 already-done and 100 already-failed recovery audits. Their ledger states need ordinary finalizer reconciliation, not another blind GPU retry. Including the 30 excluded rows, the 130 linked failed recovery jobs consist of 129 length stops and one JSON extra-data error. The repair-audit client was live at follow-up as PID 2560055; primary audit clients 2032197 and 2111441 also remained running. These are observations, not process ownership or guarantees of future liveness.

## Stratified exact examples

All original jobs below exhausted four attempts. Exact job IDs, recovery pointers and states are preserved in `jobs.jsonl`; candidate IDs are listed here for traceability.

| Component / candidate ID | Original error | Release interpretation |
|---|---|---|
| direct-be-it / `dcd31d29d4b0e3b135fb4e4f6e878b830f911f890eef244978b3608adddd29d9` | JSON extra data, line 8 | retry pending in ledger; recovery already done at attempt 1 |
| direct-be-uk / `db516424acd3e9787768796352788c77fd886b25f2158645b258c43bb9cf80c7` | length | retry pending in ledger; recovery failed at attempt 4, also length |
| jvalline--LuxIT_wiki_subset-lb / `d0af840d47307c45aac97a5b6da33e6849ac1a64f1479163c8606ff1e2da6287` | JSON expecting value | accepted following done recovery audit |
| jvalline--LuxIT_wiki_subset-lb / `440afb48be240af08c28101e0000ecc9398fed9910290a02358440bbeb05ac04` | JSON extra data | accepted_repair; generation and recovery audit both done |
| alban-labs--Kapibara-sq / `eb29029e557b630d6819909deee5391c4e48e8a5ee137c591dad32984dbf45d8` | length | accepted following done recovery audit |
| utter-project--EuroBlocks-SFT-2512-hu / `27c42522b54276ac3faa5e49cfe72ca70e749a3337105c3dfb612a54dbe17ada` | JSON extra data | excluded_unreviewed after recovery exhausted length stops |
| ParsiAI--FarsInstruct-fa-farstail / `a66fba15e976daaacc420fa7f1518622ee9b09c97119c49ebfaa7a52659bf950` | Invalid audit scores | repair_rejected, not admitted raw |
| direct-bg-it / `8e38b54ba74d06c940229f6fc7c6e631afbf7265520bd23f4d74674590e1370e` | JSON extra data | no release ledger yet; covered by configured selection loop |

## Existing retry and quarantine contract

- `dfm12/jobs.py`: ordinary failed validations retry up to four queue attempts; expired leases are reclaimed subject to the attempt limit.
- `dfm12/european_stage.py`: current transport handling retries TransportError and HTTP 408/429/500/502/503/504, then releases owned work through cleanup rather than silently accepting output. This describes current code, not proof of the runtime version responsible for every historical failure.
- `dfm12/wave_repair.py`: primary `audit_failed` creates a separate deterministic `recovery_audit` with concise schema-constrained instructions. Original failed jobs are preserved. Successful audited outcomes become accepted/rejected; eligible instruction repairs receive their own audit.
- `quarantine_invalid_outputs` excludes only exhausted, recognized format/length failures, records evidence, and distinguishes unreviewed from invalid repair. Unrecognized infrastructure failures remain blocking rather than being converted to accepted or silently quarantined.
- `scripts/advance_wave4_selections.py` and `scripts/select_baltic_translations.py` drive component processing and accepted-only selection. They enqueue/reconcile retries; execution additionally depends on the repair client remaining available.

**Recommendation:** leave current queues and GPU audits untouched. Monitor selection progress and repair-client liveness, and allow normal reconciliation/quarantine. Investigate a specific component only if progress stalls or an explicit transport failure remains stranded. No accepted-raw fallback, model-output reset, or additional retry launch was performed. Snapshot uncertainty: 251 temporarily busy ledger rows and JSON error-origin ambiguity; no population semantic-quality claims.

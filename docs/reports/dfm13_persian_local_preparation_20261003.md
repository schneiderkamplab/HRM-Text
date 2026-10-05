# Bounded Matina/TLPC local preparation

CPU implementation ready for payload validation, access still blocked. No network
requests, source downloads, fabricated documents, GPU calls or server changes.
The full sources are NOT complete; no candidates are currently prepared/queued.

## Frozen staging plan

Module `dfm12.wave4_persian_local`; plan/seal and source-specific blocked receipts
under `data/dfm13/wave4/persian-local-v1`. Original approved source IDs, revisions,
licenses and per-file LFS hashes come from the authenticated recheck inventories.

| Source | Selected shards | Compressed bytes | Coverage |
| --- | ---: | ---: | --- |
| Matina | 11 | 1,015,840,100 | 11 source-file strata; six larger files excluded by the2GiB/shard cap |
| TLPC | 64 | 135,813,056 | 64 distinct site strata out of784 eligible sites; not all60,993 content shards |

This is an explicit bounded implementation choice consistent with the wave plan's
domain-balanced subset policy, not a previously promised full-source allocation.
Stable seed20261003; hash-order sites/categories and shards, round-robin across
strata before selecting another shard from the same site. Caps:64shards/source,
8GiB compressed/source,2GiB compressed/shard. Larger/unselected sources are
reported, not silently considered consumed. Both plans currently fail closed
because every selected payload is absent. No403 retry was performed.

Candidate caps per source derive from the existing1.5x preparation multiplier,
divided among three Persian seed-source families (Wikipedia, Matina, TLPC):
denoising25,379; prefix38,071; span22,398; paragraph11,258. These are supplementary
staging caps, NOT new accepted quotas or a rewrite of existing Wikipedia outputs.
Existing combined accepted/token selection limits remain authoritative. No repeat
inflation to hide shortfalls. Earlier Wikipedia candidate oversupply is untouched.

## Streaming and safety

* Local selected files must match exact upstream size and LFS SHA256 before any
  content ingestion. Plan and implementation/dependency hashes are checked.
* ZIP files are streamed with `zipfile`, never extracted to disk. Reject absolute,
  parent traversal, backslash/drive paths, duplicate members, symlinks, encryption,
  excessive expansion ratios, oversized members/archives and corrupt containers.
* Caps:10,000ZIP members,256MiB/member,1GiB total advertised expansion/archive,
  2MiB/JSON line,100,000rows/member or direct shard. Direct streams also have a
  256MiB expanded-byte limit. Bounded prefix scans are explicitly counted; this
  is not a uniform sample over all rows of a large shard. Whole rows/targets are
  never silently truncated. Unsupported archive formats are counted, not executed.
* Only JSON objects are considered. Matina requires a literal string `text`;
  unknown archive/member/document schemas are rejected, not guessed. Actual
  schema validation awaits granted access, so operational yield is unknown.
* TLPC requires Formal main-content arrays. Original ordered content elements
  are retained as paragraph units; type/category/date/title/URL metadata remain
  in provenance. Comments and QA are not silently merged into article text.
* Stable hash-bounded document reservoir; exact selected-window deduplication
  within each source. Original-document and selected-window hashes remain in
  provenance. This is not a claim of corpus-wide/cross-source fuzzy deduplication.
* Existing paragraph-aware `transform.window`, Persian prompts, four transforms
  and actual student renderer are reused unchanged. Only natural source windows
  are selected; no synthetic missing paragraphs/targets. Insufficient paragraphs
  fail the existing reordering validator and produce honest shortfalls.

Each candidate retains repository/revision/file hash/member/row/window/source
metadata and unchanged CC-BY-NC-ND-4.0 or CC-BY-NC-SA-4.0 license. A separate
license-notice receipt accompanies successful preparation. Candidates remain
`admission_authorized=false`, `audit_status=pending`. No accepted export is made.

## Pathway and commands

The generic downloader now includes ZIP in allow patterns, but explicitly skips
whole-repository Matina/TLPC retries and points to the bounded plan. This prevents
an accidental62k-file download. No source-specific network downloader was armed;
after a genuine access change, download only exact `plan.sources.*.files` at the
pinned revisions into the existing local roots, then use:

```bash
PY=/home/ucloud/miniforge3/envs/hrm/bin/python
$PY -m dfm12.wave4_persian_local prepare --source matina --enqueue
$PY -m dfm12.wave4_persian_local prepare --source tlpc --enqueue
```

`--enqueue` runs existing `wave4_cpu.enqueue`, including native template preflight
and the existing transactional audit queue. It neither launches GPU clients nor
changes servers. Coordinate with the31B drain owner before adding any actual
future audit jobs. Without `--enqueue`, staging remains offline. Current calls
without that flag wrote only blocked receipts, no queue mutations.

If bounds or code change, create a new plan root; never silently repin a prior
plan. Eleven focused tests passed, covering traversal, symlinks, ZIP streaming,
oversize/corrupt input, schemas/paragraph preservation, broad deterministic shard
selection and missing-file failure before renderer/network/candidate output.

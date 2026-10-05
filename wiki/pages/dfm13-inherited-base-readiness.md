---
type: Reference
title: DFM13 Inherited DFM12 Base Readiness
description: Read-only base integrity evidence and later DFM12 inventory gaps requiring explicit reconciliation.
tags: [dfm13, dfm12, data, provenance]
status: stable
last_updated: 2026-10-05
confidence: high
---
# DFM13 Inherited DFM12 Base Readiness

## Final Scope Reconciliation, 2026-10-05

The user's final sampling choice is **one epoch**. The sampler's default ten
epochs is an implementation default, not the requested policy. Tesla owns the
single existing `scripts.sample_dfm13_final` process and final assembly; this
review launches neither a second sampler nor an assembly.

Scoped implementation `scripts/dfm13_specification_reconciliation.py` enumerates
registered components, explicit source specifications, holds, deferrals and user
exclusions, and binds grouped DaLA publications to integration pins and verified
publication file hashes. It does not treat a bare completion boolean as evidence.
The initial snapshot has482integrated dispositions,187pending integration,
7held,16deferred,5excluded (these are specification/component references, NOT
unique dataset counts). Every currently integrated package is publication-ready.
The authoritative DaLA9 predecessor must not be mistaken for the final scope.

Detached reconciler PID482672, recorded in
`data/dfm13/specification-reconciliation-20261005-v1/launch.json`, waits for
`verified-all-finished-additions-20261005-v1` and its matching composition. After
actual membership, publication and inherited coverage checks pass, it atomically
writes each of `reconciliation.json` and `sampling-reconciliation.json` under
`data/dfm13/all-source-finalization-20261004-v1/`. The latter binds the final
assembly SHA and explicit user sampling authorization for Tesla's waiting sampler.
No manual future release flag is required. Operational status is in the scoped
root's `progress.json`, failures in `watcher.log`, completion in `completion.json`.

A full scan of the inherited length/start indices, without scanning the massive
token backing, verified381sources,1325parts and48949524rows: maximum combined
length4096, zero rows above4097, zero responses shorter than2, zero negative or
out-of-bounds indices. Recorded in `inherited-length-validation.json` in that root.
Earlier64-row-per-part checks alone were not a proof of zero sampler drops; this
full index scan supersedes that limitation for the381inherited components.

DaLA v2 is an incremental addition, not a blanket replacement of inherited DaLA.
Its finalizer excludes exact prior clean controls and original/corrupted pairs;
each new noisy pair produces one task row, not an additional clean twin. Prior
indices pin the modern inherited releases. Danish v2 also pins the recovered
historical `giannor_gec_dala_tv2r_it` train/val/test files, with492063clean originals
and438502distinct pairs. These are **Danish instruction-formatted** variants:
`_it` does not mean Italian. Historical DFM11 contains six DaLA/GEC-DaLA TV2R
arrays,1914691targets, explicitly included across all splits by the earlier
[TV2R policy](dfm8-plan/danish-linguistic-acceptability-and-gec-data.md).
Retain that policy and its train-contaminated-evaluation caveat; do not silently
drop these arrays or claim semantic/global message deduplication. The report
enumerates all prior-index source files/revisions and historical task arrays.

Replacement/repeat policy remains DFM11 + latest381 once + approved new additions
once, never old sampledDFM12 + latest381. Nine obsolete XL identity components are
replaced by construction; approved XL identity21 repeat10, MATH repeat5, other
sources repeat1. Separate XXL-wide identity21 remain excluded at repeat0.
Raw OpenHermes, RepoChat, both search datasets and excluded Fars summaries are
not reintroduced. Four source-fidelity holds remain held, not omitted silently.

Six focused reconciliation tests pass, covering missing membership, explicit
holds, empty/false evidence gates, drift, automatic two-receipt release and invalid
inherited lengths. Live runtime pins were not changed after launch.

The 2026-10-04 independent CPU check of the latest completed assembly
`data/dfm13/verified-finished-additions-dala9-20261004-v1/assembly.json`
confirmed its explicit base is `data/sampled_dfm12`. This is NOT an implicit
reference to the currently trained `sampled_dfm12_xl_epoch11_noidentity` corpus.
Related: [verified additions assembly](dfm13-verified-additions-assembly.md).

All ten epoch index references and the backing-token stat signature match the
assembly;1024rows per epoch pass sampled bounds/length checks, and build/merge
receipts agree at252179463rows per epoch. Stored backing has227144019403int32
tokens. Tokenizer and native Jinja template hashes match; vocabulary262144,
thinking disabled,4096student positions (`max_seq_len=4097`).89source manifests
match their recorded hashes;387staged paths resolve. No referenced dependency
was missing. Massive token/index arrays were not rehashed or fully scanned.

Pinned recovered DFM11 provenance covers16023tasks and223595843215tokens.
There are20repaired EN/DA OpenHermes shards and no raw `openhermes_2_5`/`teknium`
task entries;60recorded repaired-OpenHermes token probes match the inherited
array. Raw OpenHermes exclusion is intact; repaired OpenHermes is intentional.
The original `data/tokenized_dfm11` tree is absent locally, but is not a runtime
dependency of the self-contained sampled base. A source-level rebuild would
require restoring it; its pinned recovered inventory is present.

Coverage caveat: this base's89-source build predates the later381-source DFM12
inventory.292names are additional, and nine same-name identity packages have
replacement manifest hashes. The checked assembly contains no `dfm12-*`-named
ready additions. These require explicit parent reconciliation before claiming
all later DFM12 data or21-language identity replacements are inherited. Do not
silently switch the base, append duplicate replacements, or modify live training.

Exact evidence and name lists:
`docs/reports/dfm13_inherited_dfm12_base_check_20261004.json` and companion`.md`.
This check did not run sampling, tokenization, full-payload hashing or GPU work.

## Resolved Snapshot Delta

User authorized CPU preparation of the292new and nine replacement components.
The completed handoff is `data/dfm13/dfm12-full-inheritance-20261004-v2/`, with
`inheritance.json`, `delta.json`, `complete.json` and `handoff.json`. It references
the unchanged DFM11 base plus ALL381latest DFM12 packages, not the old sampled
DFM12 base plus duplicates. Thus the old nine XL identities are replaced by
construction, without rewriting shuffled epochs or live training inputs.

Verified1325tokenized parts,48949524rows,13806417986stored tokens;357published
packages and24explicitly authorized audited local DaLA components. Native
tokenizer/template contract matches. Exact component repo/export-path/export-hash
comparison against the pinned DFM13 registry snapshot found no overlap. This is
not whole-corpus semantic or row deduplication. Snapshot weights are recorded
(identity10, others1), not sampled; live identity_repeat0 is untouched.

The newer live catalog additionally lists21XXL-wide model-specific identity
packages (41751rows), configured repeat0, outside the approved381-source snapshot.
`additional-catalog-disposition.json` accounts for all21with verified publication
hashes and explicit exclusion rationale. They must not be silently substituted
for XL identity or enabled through an inheritance fallback. Tesla owns assembly
consumption; no running dataset or scheduler was changed.

Implementation `dfm12/inheritance_delta.py`; three focused tests passed.
Full interface and caveats:
`docs/reports/dfm13_latest_dfm12_inheritance_handoff_20261004.md`.

Upload accounting clarification: the24local inherited DaLA components map to
12dataset repositories, each with `acceptability` and `correction` configs.
Destinations are `schneiderkamplab/dala-{language}-audited` for ca,cs,de,el,es,et,
fi,fr,it,pt-pt,ro,uk. Source package manifests and README config frontmatter
confirm this grouping. Do not add24component entries to a repository-count
backlog; union these12repo IDs with the parent DaLA target list first. The earlier
282-284combined estimate mixed counting units and is invalid. Exact mapping:
`docs/reports/dfm12_inherited_dala_upload_targets_20261004.json`.

## Existing DaLA Publication Resolved

The apparent12repository collisions were investigated against pinned HF revisions
on2026-10-04. For ALL12languages, the remote producer `metadata/manifest.json`
is byte-identical to the locally pinned producer manifest; audited
`provenance/train.pairs.jsonl.gz` hashes also match. Integration receipts retain
every producer training pair, with equal per-task training row counts. These are
not a different audit generation or a reduced pair subset.

The downstream local training projection differs in packaging:50000rows/shard
versus100000upstream, different ordering, and `id/messages/language/task` fields
instead of upstream `messages/metadata`. Thus gzip hash equality and ordinal
row comparison are invalid equivalence tests. For German,24sampled native-message
records (12per config, clean and corrupted variants) matched exactly by pair ID
and variant; zero differences or missing samples. Local scans covered691942rows
per config to locate them. This is bounded message sampling, NOT exhaustive
message equivalence across all12languages. German upstream revision:
`450562298520f06d4a09c54124362553346c9f32`.

Recommendation/handoff to Tesla: reuse the12existing producer repos at the
verified pinned revisions; do not overwrite or create new audited releases.
Keep local projection hashes and tokenization receipts unchanged and record
`derived-from` provenance separately, rather than falsely claiming local gzip
files were uploaded byte-identically. The earlier local `upload_performed=false`
does not mean these upstream datasets are unpublished. No12new-repository
obligation should be added to the upload backlog for this inherited release.

Evidence: `docs/reports/dfm13_inherited_dala_collision_20261004.json`.
Exact12repo/revision/hash mappings and scoped recommendation for Tesla:
`docs/reports/dfm13_inherited_dala_reuse_handoff_20261004.json`.
No upload, overwrite, source-data mutation, tokenization or GPU work occurred.

User selected OPTION1 on2026-10-05: reuse the12existing HF repositories at the
handoff's pinned revisions, retaining local projection provenance and performing
no duplicate uploads. Final evidence/hash consistency was rechecked:12complete
repo mappings, identical producer/train-pair evidence,24/24German message samples
matched, none missing or different. This approves the reuse disposition; it does
not expand the bounded message check into an exhaustive all-language comparison.

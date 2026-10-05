# Filtered FA Assembly Contract: Read-Only Review

Initial inspection preceded the replacement module. Follow-up read-only review
of `dfm12/fa_transform_subset.py` confirms the contract below. No assembler or
publisher edits made; ownership remains with Jason/main.

## Confirmed Adapter Gap

Superseded during the same turn: Jason added the exact-policy dispatch and
`verify_assembly_publication`, which invokes package replay and pins every
attachment. He also changed final registry promotion to require exact equality
with the saved parent or completed child, preserving concurrent holds/policies.
Those two immediate findings are addressed; no competing edits were made.
Remaining completeness suggestions: explicitly expose subset lineage in the
returned assembly source record and pin external census flags/parent payload
used by replay, not only copied receipt metadata. The current adapter already
validates those external bytes during admission. Initial FA subset/structure
tests passed19; they are not a claim of completed publication or current arrays.

The actual fields are `subset_policy=fa_minimal_structural_v2`, `subset_receipt`,
`subset_receipt_sha256`, `parent_hf_revision`, and `export_manifest_sha256`.
Generic `verify_entry` currently ignores the first four. Its ordinary payload,
publication and array checks can pass without verifying the subset derivation.

Minimal scoped fix: for exactly the four FA transform names require the known
policy, call `dfm12.fa_transform_subset.verify_package(source.parent.parent)`,
compare registry/publication/export receipt pins and parent revision, pin all
`export['files']` plus the preserved parent payload and census flags/code, and
retain subset policy/receipt/parent revision in the returned source manifest.
Keep every existing generic source/array/native-parity check. Reject unknown
subset policies rather than silently treating them as ordinary wave outputs.
The package verifier already replays exact retained bytes and ordered exclusions;
no new parallel implementation of that logic is needed.

## Concurrent Hold Risk

`publish()` currently rereads the registry under lock but accepts replacement
based only on current output hash. A quality hold added during tokenization or
upload would be overwritten by the previously constructed accepted entry. Add
a final `entry_quality_hold(current)` refusal before replacement (and check
existing holds before upload). This is a concurrency hazard, not evidence that
a hold currently exists on the four FA transforms.

The actual new token-root design resolves the old-root mismatch described below:
`tokenized_fa_minimal_subsets/<name>/<digest(pins)>` with a separately pinned
receipt and all array hashes. Old payloads and token arrays remain preserved.

The current assembler verifies source/publication/export agreement, native
template pins, tokenization receipts, every array, and sampled native token
parity. It does not inspect an arbitrary derived-subset/filter receipt or retain
that lineage in its returned assembly source record.

If the replacement uses that receipt, a narrow adapter/check is needed before
admission: bind its hash identically in registry/publication/export; pin the
preserved parent payload and publication revision, census/flags and filter
implementation; verify exact child hash/counts and parent-minus-excluded row
identity (no edited targets or newly introduced rows); retain the filter receipt
and parent lineage in assembly output. The exact field mapping must await the
publisher's actual schema, not a competing invented contract.

The existing tokenizer uses a name-based output directory and correctly refuses
a changed source hash when its old receipt exists. Thus replacement publication
alone must not reuse the old tokenization flags/path. Jason's new token roots
must have new verified receipts bound to the filtered source, with stale registry
tokenization fields cleared until completion. Do not delete or retokenize old
artifacts in place. Do not verify old FA pins as current admission.

Minimal filter scope remains 7,086 exclusions from 242,042 rows; 234,956 remain.
This is a structural subset, not new semantic certification. Shared source
quality holds and all existing template/array gates must remain effective.

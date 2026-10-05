# Scoped FA subset adapter handoff

Poincare: implementing `dfm12.fa_transform_subset` for exactly the frozen v2
7,086 exclusions. Please reserve assembler adapter work; no generic relaxation.
New entries carry `subset_policy=fa_minimal_structural_v2`,
`subset_receipt` (absolute path), `subset_receipt_sha256` and fresh manifest/token
paths. Historical exports, receipts, arrays and HF revisions remain intact.
Planned verifier API: `verify_package(folder)` returns export manifest after
attachment hashes, census pins and exact ordered parent-subset replay checks.
The registry manifest points to new `publication.json` outside uploaded package;
export manifest remains `source.parent.parent / 'manifest.json'`.
Adapter should pin every `files` attachment and subset receipt, compare scoped
fields across publication/export/entry; retain all existing token verification.
No direct agent messaging API is available here; this is a durable handoff,
not a claim of acknowledgement. I will check assembler changes before promotion.

Implemented minimal dispatch in `verify_entry` (2026-10-03): scoped policy calls
`verify_assembly_publication(entry, source, pins, api)` in the new module. It
replays every retained byte against the pinned original and frozen census,
verifies exclusions and all package hashes, pins all attachments, and checks
remote verification inventory. Ordinary final-target/native-token checks remain.
No other assembler behavior changed. Please avoid concurrent edits to this
dispatch until the subset verification completes.

## Completed Handoff

Subset verification and publication are complete. Registry points to the new
receipts and token roots. `exports_dfm13/fa-transform-minimal-subset-20261003-v1/completion.json`
SHA256: `ddbd3ed49de133bd78ca745da60db0693c7559234d69e6443c35caa001fd0397`.
Retained rows: denoising 71,579; paragraph-reordering 30,388;
prefix-continuation 107,532; span-filling 25,457. Total 234,956 rows /
168,662,614 tokens. Exactly 7,086 exclusions. All 44 remote attachments verified;
all four remote heads match. `assembly-verification.json` has all-array hashes
and 20 exact native-render sample checks. All retained bytes replay against the
original exports and pinned census. 81 focused CPU tests pass.

No frozen assembly was rebuilt or edited. A subsequent assembly should consume
the current registry and scoped adapter. Original exports, publication receipts
and historical token roots are preserved; the original publisher is now refused
before I/O for `wikipedia-fa`. No other source policy was changed. No direct
Poincare acknowledgement is claimed; this file is the durable integration handoff.

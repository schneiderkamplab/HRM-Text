# Croatian manual44 subset / assembly-v4 handoff

Poincare integration note: the just-completed
`data/dfm13/verified-wave-additions-20261003-v4` is an immutable historical
snapshot of HR reordering before the authorized 44-ID change. Do not rewrite its
snapshot, hashes or array links. Current-state evidence must reverify the changed
registry entry or build a separate subsequent assembly.

New package: `exports_dfm13/hr-reordering-manual44-subset-20261003-v1`.
Only `dfm13_wave4_wikipedia_hr_paragraph_reordering` changes. Retained count
30,942; other three Croatian tasks untouched. No broad classifier is run.
New tokens live under `data/dfm13/tokenized_hr_manual44_subsets`, keyed by
source/tokenizer/template pins. Old arrays and old publication remain in place.

Minimal assembler dispatch now recognizes `hr_reordering_manual44_v1` through
`dfm12.hr_transform_subset.verify_assembly_publication`; ordinary row/array/native
checks remain. FA tokenization/publication functions accept a scoped backend
while preserving their defaults; HR verification independently enforces exact
review pins, 44 IDs and byte-identical ordered retention. No generic relaxation.

`completion.json` and `assembly-verification.json` under the new package root
are the authoritative current-entry handoff once publication completes.
No direct agent messaging API is available; this durable note is not a claim of
Poincare acknowledgement. The historical v4 snapshot itself is not modified.

## Completed

Current registry integration and entry verification succeeded. Retained 30,942
rows / 39,505,426 tokens, zero skipped rows. New HF revision:
`116c771f15f417d3ac0e06ac8d8867bb7fbc04b1`; all 13 attachments verified.
Completion SHA256:
`1e69fc3bfd7873d9e4b14ce06a10b7a1eb9f7cac7b27286e6a0235a34f6cb871`.
95 focused tests pass. No whole-assembly rebuild or GPU action was performed.

Assembly-v4 historical identity:
- `assembly.json`: `5c6a4744b8856c79fb427fd661c4342b662c01b8cecfc549f41d8ae0d1067a02`
- `registry.snapshot.json`: `7e8d0b573d9f97a6deec8a26ca2b7ad5de7c5ba31c677be80dc08160d5ff5367`

Machine-readable historical/current transition evidence:
`docs/reports/hr-manual44-transition-20261003/receipt.json`, SHA256
`22e7c28e3e57182c35537c7bcbf02e525cdfe185c4626955af1fc80c10adca5f`.
All 215 old Croatian arrays match frozen v4 hashes, not just path inequality;
the other three live HR entries/data remain unchanged. Keep v4 immutable and
use this current-entry verification or a fresh subsequent assembly.

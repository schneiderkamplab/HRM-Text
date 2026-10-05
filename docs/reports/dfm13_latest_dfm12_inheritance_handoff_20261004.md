# Latest DFM12 Inheritance Handoff

Owner boundary: CPU preparation only. Tesla owns DFM13 assembly. No live DFM12
training paths, scheduler, sampled indices, or backing arrays are changed.

## Interface

Output: `data/dfm13/dfm12-full-inheritance-20261004-v2/`.
Consume only after `complete.json` exists and its `inheritance_sha256` matches
`inheritance.json`. The latter uses schema
`dfm12-full-inheritance-reference-v1` and contains:

- `base`: explicit `data/sampled_dfm11` reference, ten existing epoch index sets.
- `sources`: all381latest DFM12 components, each with `delta` (`new`,
  `replacement`, `unchanged`), publication provenance, token parts, rows/tokens.
- `delta_counts`:292new,9replacements,80unchanged.
- `tokenized_tree`: isolated symlink tree referencing all1325existing token parts.
- `exact_component_overlaps`: same published repo, export path or export bytes
  found in the pinned DFM13 registry; include those components only once.
- `input_pins`, `base_pins`, `tokenizer_contract`, and stat/header/source binding
  evidence. Massive token arrays are not rehashed.

**Composition is DFM11 base + latest381DFM12 packages**, NOT old sampled DFM12
+381packages and NOT old sampled DFM12 +292new +9identities. The latter would
retain nine obsolete identities and duplicate their replacements. This explicit
reference reconstructs the intended full DFM12 composition without altering or
resampling the currently trained corpus. It is an assembly input, not a newly
sampled training dataset.

`repeat_mapping.json` preserves the approved completed-campaign snapshot weights
(identity10, others1) as provenance only. Current live configuration's
`identity_repeat=0` is untouched. Tesla/parent must apply the chosen DFM13 repeat
policy explicitly rather than infer it from the running DFM12 schedule.

Dedup here is exact component-identity/export equality, not whole-corpus semantic
or row-level deduplication. Raw OpenHermes remains excluded from the inherited
DFM11 provenance; repaired OpenHermes and independently audited synthetic
OpenHermes tasks are intentional distinct sources.

Implementation: `python -m dfm12.inheritance_delta --output <fresh-root>`.
Focused tests: `tests/test_dfm12_inheritance_delta.py` (three tests).

## Completed Handoff

V2 completed:381sources,1325parts,48949524rows,13806417986stored tokens.
357packages have verified publication receipts;24DaLA components have explicit
audited local-integration authority (upload not required). No missing token
parts or staged source paths; exact component overlap with the final pinned
DFM13registry snapshot is empty. No whole-corpus row deduplication is claimed.

`inheritance.json` SHA256:
`e2e8edcea32ee1344e50bc2a4f8ae463766d809e8643cdda6f74357172ab2815`.
`delta.json` gives the full292new/nine-replacement records, and `handoff.json`
pins both artifacts. All source and token links were checked after completion.
V1 is explicitly not ready: its registry changed during checking. V2 takes one
final immutable registry snapshot for overlap reconciliation, accommodating
concurrent publishers without mixed-version evidence.

Additional catalog accounting: live `training_sources.json` also lists21newer
XXL-wide identity packages (41751rows), beyond the approved381-source snapshot.
Their export/publication receipts verify, but live identity repeat is0; these
are distinct model-specific identities, not the nine XL replacements. They are
enumerated, with manifest/revision hashes and exclusion reasons, in
`additional-catalog-disposition.json`. Do not silently enable repeat0, substitute
XXL-wide persona for XL, or claim they were included in this381-source reference.

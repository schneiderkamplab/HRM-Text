---
configs:
- config_name: default
  data_files:
  - split: train
    path: data/train-*.jsonl.gz
task_categories:
- text-generation
---

# dfm12-dynaword-pl

Published accepted-only DFM12 subset. Local audit-snapshot fields describe the pre-publication build, not Hub publication status.
Only completed kept decisions with all three scores at least 4 are included, after deterministic gates.
Automated review is not native-speaker certification. Exclusion metadata contains only IDs/status/errors/scores/reasons, never excluded conversations.
Full native messages and explicit assistant target indices are preserved. OPUS pairs produce both directions,
linked by parent_pair_id; both directions share the same pair audit.
Training input must use only messages and optional target_message_index. Accepted references, stored audit decisions,
original provenance and portable attribution are under metadata, never concatenated into training messages.
Full excluded records remain only in the separate, local non-upload snapshot, not this package.

## Licensing and Attribution

No blanket license is asserted. Preserve the exact per-record source license, URL, title, history
and attribution in metadata/audits.jsonl.gz (export_provenance). Local attribution files are bundled in
metadata/evidence and referenced by relative paths. Original raw records remain unchanged for traceability.
License labels among accepted records:

- CC-BY-SA-3.0: 50142
- CC-BY-SA-4.0: 47293
- public-domain (official documents): 101155

## Validation

Run `python validate_dataset.py` using Python 3.9+; only the standard library is required.

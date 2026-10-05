# MATH Publication and TLPC Assembly Handoff

Prepared and verified on2026-10-04. Registry ownership stays with Tesla; no
registry, GPU, sampling or training changes were made. No direct agent-message
tool is available, so parent should relay this handoff to Tesla.

## MATH Ready

- Package: `exports_dfm13/dfm13-hendrycks-math-worked/`.
- External verification receipt:
  `exports_dfm13/dfm13-hendrycks-math-worked.ready.json`.
- Proposed canonical HF destination:
  `schneiderkamplab/dfm13-hendrycks-math-worked`.
- Manifest SHA256:
  `405ff14ad708e50b95ddf430e0796eabd69f413e96da013a82b68747ef0139cc`.
- Train bytes unchanged, SHA256:
  `06d35dcb70367fe4608994bbe861e3afff9e4714cc0198e1cc9cca62e2f37076`.
- 7,496 physical rows, repeat5 metadata only. No duplicated physical rows.
- Full existing MATH adapter verification passed, including source train/test
  hashes, exclusions, license evidence, native arrays and target parity.
- Native tokens remain2,431,145. No retokenization or new mixture sampling.

Package contains native messages/target indices/row provenance, a loadable HF
card, pinned source card with MIT declaration and citation, license attribution,
source inventory, original conversion manifest and screening exclusions.
Historical repeat1 in the original manifest is explicitly superseded by the
October2 repeat5 decision, without rewriting original evidence. Test data is
not uploaded as training data. Existing inherited direct-answer overlap is
documented honestly; no exhaustive global dedup claim.

Commands used:
```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m scripts.package_dfm13_math prepare
/home/ucloud/miniforge3/envs/hrm/bin/python -m scripts.package_dfm13_math validate
```

Publication is NOT claimed: `uploaded=false`. The owner can upload the package
folder only (external ready receipt is private), verify its file hashes at the
returned commit, then add HF publication metadata under the existing registry
lock. Preserve existing MATH output/token paths, repeat5, source revision and
all preparation hashes. Avoid modifying frozen assembly registry snapshots.

## TLPC Intake Reminder

Both `dfm13_tlpc_grounded_qa_fa` and `dfm13_tlpc_grounded_chat_fa` are already
uploaded and in `config/dfm13_sources.json`. Their actual assembler verification
receipt is `data/dfm13/tlpc/release-100k-v1/integration-verification.json`.
Tesla's queued all-finished successor must include both:100,000 conversations,
180,000 targets,170,673,889 tokens. No repeat publication/tokenization needed.
The old authoritative DaLA-nine root predates these additions; do not claim
they are already in that immutable snapshot.

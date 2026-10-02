---
type: Runbook
title: Audited European DaLA integration
description: Passed-only producer packages integrated as local train-only DFM12 additions.
status: draft
last_updated: 2026-09-28
confidence: high
---
# User-authorized local integration

The user requested preparation of all audited DaLA datasets for HF upload and
integration into DFM12. Twelve new producer packages contain 4,738,657 pairs
across ca, cs, de, el, es, et, fi, fr, it, pt-PT, ro and uk. Existing EN/NL and
six northern-language exports remain unchanged; no duplicate ingestion occurs.
This task prepares uploads but does not publish datasets or restart training.

Producer root: `/work/mimir/DaLA/export-upload/european-audited-20260928/`.
Upload inventory: `/work/mimir/DaLA/export-upload/audited-dala-upload-plan.json`.
All new pairs have a completed automated canonical-pair audit with four `yes`
criteria and decision `pass`; flagged, uncertain, failed and explicit exclusions
are omitted. These are automated judgments, not native-speaker validation.
HF packages preserve all splits. Only train pairs enter DFM12 additions.

# Reused pipeline

`python -m dfm12.dala_audited_release --workers 12` writes
`data/dfm12/dala-audited-european-20260928/`. It reuses the producer's standalone
chat adapter, existing message validation and fingerprint/screening preparation,
and `scripts/tokenize_chat_template.py` with the current raw Gemma tokenizer,
non-thinking template and 4,096-token context. It protects all twelve raw
producer heldout pools by exact normalized sentences and document hashes, plus
the existing European reference inventory's exact inherited/heldout chat and
heldout-text matches. Reference index coverage is partial, not full benchmark
or fuzzy/semantic decontamination. A checksummed SQLite reference snapshot on
local storage replaces repeated shared-filesystem random reads.

The final integration manifest and
`data/dfm12/local-audited-dala-additions.json` registry appear only after successful
screening, tokenization and row-count checks. The 24 components use the existing
`dfm12-dala-{code}-{task}` naming with repeat 1. Provenance links to the validated
producer package manifests. Existing raw unaudited FI/CA/CS/ES preparation is
not consumed by this route or silently relabelled as approved.

# Subsequent isolated sampled build

The normal `dfm12.build_training` now accepts an explicit local additions manifest:

```bash
python -m dfm12.build_training \
  --local-dala-additions data/dfm12/dala-audited-european-20260928/integration.json \
  --suffix european-dala-20260928 --workers 16
```

This is a subsequent build command, not launched by upload preparation. The
suffix is mandatory with local additions, so existing sampled corpus and build
receipts cannot be overwritten. Previously exported sources still require their
verified HF publication receipts; explicitly authorized local additions instead
require a complete audited train-only manifest and pinned artifacts. Duplicate
component names, heldout input files and changed files fail closed.

Five tests passed for heldout rejection, clean/corrupt controls, incomplete
admission rejection and existing sampling/merge invariants. Producer packaging
also passed independent full mechanical validation for every package.


# Completion evidence

The integration completed successfully: 24 train-only components, 3,798,535
pairs, 15,194,140 chat rows, 316 tokenized shards and 1,265,448,830 tokens.
No overlap exclusions or tokenization drops occurred in this run. The complete
`integration.json` is registered in `data/dfm12/local-audited-dala-additions.json`;
all data-file hashes, producer manifest pins, tokenizer/template hashes and
component row counts were rechecked after completion. See the run root's
`completion-summary.json`, `README.md` and `execution.json`. No current sampled
DFM12 corpus was overwritten, and no upload was performed.


# HF publication — 2026-09-28

After explicit user instruction to upload, all twelve new packages were
published publicly under `schneiderkamplab`. All 4,738,657 retained pairs have
the four-yes automated pair-audit decision; both task configurations and all
three splits are published. Verified the exact remote file inventory, sizes,
Git/LFS content hashes and downloaded manifest SHA256 at the recorded commit
for every repository. Publication receipts: `/work/mimir/DaLA/export-upload/european-audited-20260928/
upload-receipts.json`; clickable inventory: the same directory's README.md.
The local upload plan now records all twenty non-Danish language variants as
published (twelve new plus eight earlier). Earlier eight use their established
per-task-row acceptance contracts; they were not reclassified as pair audits.

HF rejected `language: pt-PT` in the Portuguese card. Corrected the card to
`language: pt` with `language_bcp47: pt-PT`; language identity, prompts, pairs and
training tokens remain European Portuguese and unchanged. Revalidated the
complete Portuguese package and updated its DFM12 manifest pins. Old/new
metadata and migration evidence are retained in the local
`portuguese-card-migration/` directory. Prepared-package `upload_performed: false`
fields describe the immutable pre-publication build; upload receipts are the
authoritative publication state. No local-only parent selection files or audit
database were uploaded.

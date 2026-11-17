---
type: Runbook
title: DFM11 HF-only rebuild recipe
description: Guarded serial-queue recipe that rebuilds the DFM11 pretrain corpus from pinned public packages and the verified DFM10 union.
tags:
- dfm11
- rebuild
- data
- huggingface
status: stable
confidence: high
last_updated: 2026-11-10
---
# DFM11 HF-only rebuild recipe


## Scheduled behind corrected DFM10 (2026-11-07)

User authorized preparation and automatic execution after exact DFM10
verification. The predecessor is now exclusively
`data/rebuild_hf_dfm/serial-queue/dfm10-hf-v2/union`. The old `dfm10` local
reconstruction cannot release this run. This supersedes the earlier
predecessor path and local-package digest preparation described below.

`scripts/dfm_hf_gate.py` requires the corrected DFM10 receipt to report
`matched`, 41 verified final arrays, HF-only plus lexdk/DBC policy, a recipe
hash matching both its frozen configuration and input receipt, and the
4,351-task token comparison. The verified union must also exist. The gate
is checked at launch and between stages, and the predecessor receipt/hash
is recorded for restart integrity. Missing verification leaves DFM11 waiting;
an invalid receipt blocks execution. Every reconstruction CLI stage also
checks the gate; `plan-lock` is metadata-only preparation.

Prepared `config/data/dfm11_hf_rebuild.json` pins 11 repositories and 360
files using remote metadata at the configured immutable revisions. LFS
SHA-256 values come from HF; regular small files are downloaded to isolated
lock-metadata storage for hashing. Public local export payloads are not
rebuild inputs. The plan covers 290 additions, 15,733 inherited tasks, and
10 sampled epochs. Preflight checked pinned code/config objects, Python
imports, remote revision access and stage-command paths. Full payload
verification occurs after acquisition, not during this preflight.

The detached CPU-only runner `scripts/schedule_dfm11_hf.py` is armed:

- Schedule: `data/rebuild_hf_dfm/serial-queue/dfm11/schedule.json`.
- Status: `data/rebuild_hf_dfm/serial-queue/dfm11/scheduled-progress.json`.
- Preflight: `data/rebuild_hf_dfm/serial-queue/dfm11/preflight.json`.
- Log: `logs/analysis/dfm-hf-provenance-20261107/dfm11-scheduled.log`.

Stages are acquire, prepare, convert/tokenize, verify-rows, assemble,
verify-addition-arrays, sample, and compare all final arrays/metadata.
The serial plan's DFM11 row points to this schedule and stays held against
legacy dispatch. No DFM12+ work or production changes are scheduled.

Preparation fixes: first-time prepare no longer requires its own nonexistent
input receipt; partial acquisitions resume; read-only historical comparisons
are not subjected to rebuild-input containment; HF cache files are excluded
from converted payload inventories. Real generated inputs remain contained.

## Shape

`data/tokenized_dfm11/union_manifest.json` records the union: base
`data/tokenized_dfm10` contributes 15,733 kept tasks (13 tasks replaced under
the eight `replaced_prefixes`: four native-tool-use families in raw and
`dfm10-` spellings, `nemotron_agentic__data__tool_calling`, the two
`dfm8-synthetic-native-tool-calling` spellings, and
`folketingets-dokumenter-error-correction__`), plus 290 additions from
`data/tokenized_dfm11_additions`, plus `tokenizer_info.json` and
`union_manifest.json` — 16,025 entries. `data/sampled_dfm11` holds ten epochs
(103,214,604,702 tokens, max_seq_len 4097); `sampled_dfm11_post` is a separate
post-training corpus outside the queue recipe.

## Additions pipeline (committed)

`scripts/tokenize_dfm11_from_hub.py` @ `4022697` (2026-09-08, byte-identical to
the working tree) is the whole additions pipeline:

1. `snapshot_download` eleven pinned packages named in
   `config/data/dfm11_{tool_replacements,mathagentic,koolbardi,
   fineinstructions_english,fineinstructions_danish}.yaml` into
   `exports_dfm11/` (7.7 GB locally; tool-calling repairs, mathagentic,
   Koolbardi DA/EN, and the two FineInstructions source packages).
2. Symlink the nine non-FineInstructions packages into the staging tree
   `data/converted_dfm11_hub`.
3. Re-derive the three FineInstructions families from the pinned
   `dfm11-fineinstructions-en` package with the deterministic
   legacy-balanced selection (seed 11031, `rank_value` + `balanced_quotas`
   from `prepare_dfm11_fineinstructions_english.py` @ `bc1e181`): exactly
   100,000 legacy pairs, 416,022 English and 503,740 Danish chats, written as
   50,000-chat gz shards.
4. Tokenize the staging tree with `--max-seq-len 4096` and the tokenizer plus
   template recorded in `data/tokenized_dfm10/tokenizer_info.json` into
   `data/tokenized_dfm11_additions` (290 tasks, 11,195,770 rows).

The union is assembled by `scripts/build_tokenized_dfm11_tree.py` @ `bc1e181`
(base DFM10, additions tree, prefix replacement, tokenizer_info
normalization). The sampling policy is `prefix_config_dfm11.yaml` @ data_io
commit `cfe0d19` (working tree byte-identical).

## Pins

- Adapter `f9b588f` (2026-09-05 "Integrate controlled Koolbardi datasets into
  DFM11") — the last adapter state before the additions tokenization.
- Template `e9584e0` (2026-09-03 "Render mapping-valued Gemma tool responses")
  — after the DFM10-era `0483afe` template; both spellings agree at
  `cfe0d19`.
- Builder + FineInstructions helpers `bc1e181` (2026-09-05).
- Driver `4022697`; data_io `cfe0d19`; tokenizer inherited from the DFM9 lock
  (semantic digest check).

## Recipe

`scripts/rebuild_dfm11.py` stages `recover-lock, acquire, prepare, convert,
verify-rows, assemble, verify`. `recover-lock` gates on verified DFM9 and
DFM10 receipts, digests the eleven packages into the lock's `acquisitions`
and writes `config/data/dfm11_hf_rebuild.json`. `acquire` re-downloads the
pinned revisions and digest-verifies them. `prepare` stages the driver,
adapter, helpers, builder, configs, prefix config, template and tokenizer,
hardlinks the acquisitions into `work/exports_dfm11`, and writes a staging
pointer `work/data/tokenized_dfm10/tokenizer_info.json` (the committed driver
reads its tokenizer/template locations from that path; the canonical
tokenizer_info is written into the additions tree after tokenization so the
builder's normalization matches the base union). `convert` runs the committed
driver with `cwd=work`, so its `ROOT`-relative paths land inside the work
tree. `verify-rows` byte-compares the nine snapshot families and compares
decompressed content for the three derived families (gz headers carry the
write time, so byte equality is impossible and unnecessary — the arrays gate
is the `verify` stage). `assemble` runs the staged builder over the rebuilt
DFM10 union and asserts the 16,023-task inventory and manifest counts.
`verify` compares all 290 additions' five arrays against
`data/tokenized_dfm11_additions`.

Queue wiring: `SAMPLE_EPOCHS[11] = 10`, `enable-dfm11` (gates DFM9+DFM10
matched receipts), `dfm11_command` (sample gated on `all-token-comparison.json`
plus the frozen prefix digest), dispatch and CLI extended. The inline
`compare` dispatch was fixed to pass the row version for versions ≥ 10
(previously the generic branch would have compared DFM1).

## Status

Recipe, wiring and five tests implemented 2026-11-02 (24 rebuild tests green
across DFM8–DFM11). `recover-lock` and `enable-dfm11` run after the DFM10
receipt is `matched`.

## Automatic start after DFM10 success (2026-11-10)

DFM10 exact verification passed all 41 sampled arrays plus metadata. The waiting
scheduler validated the corrected HF-only receipt and automatically completed
DFM11 acquire, prepare, convert, verify-rows and assemble. Token-array
verification is running, last logged 100/290 additions; sampling and final
comparison remain pending. Predecessor receipt digest is recorded in
`data/rebuild_hf_dfm/serial-queue/dfm11/scheduled-progress.json`.

## DFM12 successor requested (2026-11-10)

User requested DFM12 after DFM11 success, superseding the earlier statement
that no DFM12 work is scheduled. Recorded DFM12 as the next requested successor
in the serial plan and `dfm12/schedule.json`, requiring DFM11 matched HF-only
verification of all 41 arrays. This is a **queued recipe hold**, not an armed
executable runner: no DFM12 HF input lock or serial adapter currently exists;
`dfm12/build_training.py` depends on local export manifests/upload receipts.
These must be recovered into pinned HF acquisition and isolated reconstruction
before automatic launch can be enabled. Public local reservoirs remain
forbidden as rebuild inputs. DFM11's running comparison is unaffected; no
DFM13+ work or uploads authorized by this queue change.

DFM12 successor correction (2026-11-10): the held queue entry above is now
superseded. Its HF-only recipe, immutable input lock and preflight are complete;
the detached successor is armed and confirmed waiting for DFM11 exact success.
See the [DFM12 rebuild runbook](dfm12-hf-rebuild-recipe.md).

Completion update (2026-11-10): DFM11 final comparison passed all 41 arrays
and metadata; `verified.json` and the scheduled progress receipt are matched.
DFM12 automatically passed its predecessor gate and started HF acquisition.

---
type: Runbook
title: DFM12 Danish DynaInstruct Increment Comparison
description: Pinned composite lineage, disk-backed fingerprints, and a conservative zero-increment decision against inherited DFM11.
tags: [dfm12, dynainstruct, danish, provenance, deduplication]
status: draft
last_updated: 2026-09-24
confidence: high
---
# DFM12 Danish DynaInstruct Increment Comparison

## Decision

Registry entry `dyna-instruct-da-increments` pins
`danish-foundation-models/dfm-dyna-instruct` to
`bf1024f4f5b5c42586961a53946fbc5f2cc1eb80`. **No new constituents or source
reservoir revisions exist at this pin relative to inherited DFM11.** Exclude
all ten unchanged reservoirs from additions; do not re-tokenize them merely
because their original text was absent from the local machine.

This resolves the pending comparison described in the
[DFM12 status](dfm12-status.md) for this pin only. The shared status, index,
configuration, preparation and transformation files were deliberately left
untouched because other agents own concurrent work.

All DynaInstruct licenses are owner-authorized (2026-09-24). There is no
license-only blocker. Upstream notices, source revisions, cards and conversion
scripts are preserved; authorization is not independent legal verification.

## Actual Inheritance Evidence

The read-only SSH inspection used the original `/work/dfm/HRM-Text` host,
not merely local `data/converted_dfm11` additions. Its union manifest has
15,733 retained DFM10 tasks, 13 replacements, and 290 DFM11 addition tasks.
Its sampled metadata matches the local transferred corpus's
103,214,604,702 tokens per epoch. The complete inherited policy and union task
names were captured in `data/dfm12/danish-increments/inherited-evidence.json`.
See also [DFM11 portability](dfm11-portability.md).

Every original constituent's HF download receipt names the same registry pin.
The original Parquet files were downloaded via resumable, bandwidth-limited
rsync. All ten files passed SHA256 comparison against the inherited HF LFS
receipts, recorded in `file-verification.json`; `lineage.json` records enabled
tokenized routes.
For unsharded composite routes, source sizes and mtimes in tokenized metadata
also match the original files. Apertus uses the established 98 row-group
shards, of which 97 contain tokenized examples and part-0080 is empty.

Four composite paths are disabled by the inherited policy because the direct
Synquid routes already supply them: wiki-instruct-da, Danish verifiable
reasoning, ifbench-train and translation-100k. The comparison respects these
routes instead of incorrectly calling the disabled composite copies new.

Measured Parquet row counts (not rounded card counts):

| Constituent | Source conversations | Language scope |
| --- | ---: | --- |
| agentic-code-sft-mix-v1 | 24,192 | English |
| apertus-sft-mixture | 3,942,208 | Multilingual, principally EN/FR/DE/IT; not Danish |
| da-refusals | 404 | Danish |
| danish-verifiable-reasoning | 2,800 | Danish |
| ifbench-train | 2,000 | Danish |
| mt-da-deepseek | 1,251 | Danish |
| translation-100k | 99,914 | Danish-English |
| when2call | 3,648 | English |
| wiki-instruct-da | 226,213 | Danish |
| wildchat-qwen | 99,688 | Danish-predominant; row labels retained |
| **Total** | **4,402,318** | **Not an all-Danish corpus** |

Evidence: `parquet-inventory.json`. Source conversations, normalized unique
conversations, tokenized assistant-turn examples and sampled examples are
different counts. In particular, raw reservoir membership does not prove that
each row survived tokenization or was selected in a particular epoch.

## Fingerprints And Limits

`python -m dfm12.danish_increments` builds `fingerprints.sqlite` using NFC
Unicode normalization plus whitespace normalization on ordered role/content
pairs, followed by SHA256. It preserves case and turn order. SQLite stores
the first constituent/ordinal for each normalized fingerprint; duplicate
counts include within-source and previously visited constituent matches.
Transactions commit per completed file; interrupted files roll back and can
be rerun. The reader uses 256-row batches and one Arrow CPU/I/O thread.

At the documentation check, download and the 24,192-row agentic-code index
were complete; the Apertus scan had processed 1,245,184 of 3,942,208 rows,
including 6,503 normalized duplicates encountered so far. Final normalized
counts must be read from the completed `receipt.json`, not inferred from the
Parquet total. `complete_no_increments` is the terminal receipt state.

**This is not a complete inherited DFM11 conversation index.** The local
training transfer contains sampled token arrays, not the complete historical
source-text tree. This task recovered the ten relevant composite reservoirs
and inspected the actual inherited union remotely; it did not reconstruct
all 15,733 retained base tasks, agreement-backed sources, exact epoch row
membership, or all repaired/direct source texts. The conservative unchanged
reservoir exclusion is sufficient for zero additions at this pin. Future
changed revisions must remain staged until a broader inherited-text comparison
is available. The runner fails closed on changed/missing revisions or missing
enabled inherited routes.

Fingerprints omit auxiliary/tool metadata and are not semantic or prompt-only
decontamination. Malformed/nontext message rows are counted separately and
excluded by unchanged file identity, not flattened or accepted as chats.
Language counts preserve the upstream per-row labels, including multilingual
labels and unknowns; they are not a fluency/language audit. Apertus's card
explicitly warns about CLD2 misclassification of short or mixed-language rows.

## Held-Out Review

`python -m dfm12.danish_review` captures the pinned README and all ten
datasheets/conversion scripts, with HTTP status and SHA256 receipts in
`review-evidence.json`. All 21 documents were retrieved successfully.

- `when2call` is independently excluded as benchmark-derived material. Its
  conversion uses NVIDIA's `llm_judge` and `mcq` splits at
  `0582f7749df63a96fdc3070932e83e72396ace53`; its card identifies BFCL-derived
  tool schemas. Actual post-conversion Parquet rows are 3,648, not the card's
  pre-deduplication 3,952. Existing inherited training policy is not modified.
- `ifbench-train` is an explicitly generated training source, not automatically
  an eval split because of its name. Its WildChat origin and IFBench constraint
  methodology still require prompt-level overlap checks for future increments.
  Local eval code uses `danish-foundation-models/ifeval-da` and `multi-ifeval`.
- The English agentic-code mixture includes NVIDIA OpenCode, OpenCodeInstruct
  and SWE-v2. Future additions require repository/issue-level SWE overlap checks
  and native tool-format review; a source's SFT label is not clearance.
- Apertus is a multilingual mixture, not a blanket held-out-clean source.

No full held-out prompt/semantic scan was performed, and no absence of overlap
is claimed. **Zero new rows are admitted**, so no benchmark-derived source or
duplicate is added through this task. Inherited contamination concerns are
recorded here without changing training or evaluation configuration.

## Operation And Verification

Dedicated files: `dfm12/danish_increments.py`, `dfm12/danish_review.py`, and
`tests/test_dfm12_danish_increments.py`. No recursive delegation or GPU work.

Detached job: tmux session `dfm12-danish-increments`, observed PID `588155`.
Log: `data/dfm12/danish-increments.log`.
Workspace: `data/dfm12/danish-increments/`.
Launch interpreter: `/home/ucloud/miniforge3/envs/hrm/bin/python`.
The base interpreter lacks PyArrow; use the hrm environment for the real job.
CPU thread limits are one, well below the requested maximum of 16; transfers
are capped at 100 MiB/s. No tokenizer workers are needed for a zero increment.

The receipt records the current raw inherited Gemma4 tokenizer/template paths
and SHA256 values. No Mistral fix, tokenizer/template edit, final sampling,
training change or eval change was made. Candidate output is explicitly
`candidates_unaudited.jsonl` (empty on successful completion); pre-tokenized
additions are zero, not a claimed successful tokenization of inherited rows.

Verification command:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m unittest discover \
  -s tests -p test_dfm12_danish_increments.py -v
```

Six tests passed, covering normalization, nontext rejection, multilingual
labels, direct-route inheritance, first-match exclusion policy, and a real
temporary Parquet/SQLite run with idempotent resume and zero candidate output.
`compileall` and `git diff --check` passed. OKF validation reports four missing
immediate-child index links (this page plus the concurrent Icelandic/Faroese,
Norwegian and Polish pages), with no other errors or warnings. Indexing is
deferred to the coordinating agent to respect the shared-index edit boundary.

Related: [DFM12 component preparation](dfm12-components.md),
[DFM7 preprocessing](dfm7-plan/prep-and-tokenization-notes.md).

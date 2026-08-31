---
type: Runbook
title: DFM10 Danish University Portals Repair
description: Full-corpus filtering and replacement procedure for oliverkinch/danish-university-portals-bt.
tags: [dfm10, dataset, danish, quality, audit]
status: stable
last_updated: 2026-08-29
confidence: high
---
# DFM10 Danish University Portals Repair

## Decision

The original `oliverkinch/danish-university-portals-bt` conversion is not
sampled directly in DFM10. Its 4,505 rows contain useful Danish university
material, but a 100-row E4B source audit retained only 47% as broadly usable
and 42% under the strict all-dimensions-at-least-4 gate. Because the original
source contributes 2,176,575 unique rendered tokens and is repeated ten times,
unfiltered defects would be amplified to about 21.8M tokens per epoch.

The replacement preserves only complete, standalone instruction responses. It
does not regenerate targets or rewrite prompts.

## Filtering Procedure

[`scripts/repair_danish_university_portals_bt.py`](/../scripts/repair_danish_university_portals_bt.py)
first rejects deterministic structural defects:

- missing or very short targets;
- tab/control-character corruption;
- responses without a complete terminal punctuation marker;
- responses containing at least two PDF-style broken-hyphen artifacts.

This leaves 2,786 candidates and rejects 1,719 of 4,505 source rows. Every
candidate is then judged by Gemma 4 E4B for language quality,
instruction/answer coherence, and training value. A row is accepted only when
`usable_for_training` is true and all three scores are at least 4/5. The judge
is explicitly instructed to reject incomplete report fragments, absent
figures/tables or other external context, extraction corruption, and
scope/format mismatches.

Run the complete resumable workflow with:

```bash
cd /work/dfm/HRM-Text
setsid bash scripts/finish_danish_university_portals_bt_repair.sh \
  > logs/data_audits/danish_university_portals_bt_repair_20260829/finisher.log \
  2>&1 &
```

The GPU launcher waits until all eight GPUs have at least 180,000 MiB free for
300 seconds, then runs one E4B vLLM judge per GPU. Partition output is
resumable and the merge requires exact sample coverage with no judge errors.

## Artifacts And Integration

- Audit: `logs/data_audits/danish_university_portals_bt_repair_20260829/`
- Converted replacement: `data/converted_sources/danish_university_portals_bt_repaired/`
- Tokenized replacement: `data/tokenized_dfm10_university_portals_repaired/`
- DFM10 task prefix: `danish_university_portals_bt_repaired__`

`scripts/prepare_dfm10_data.sh` fails closed unless the completed replacement
manifest exists, retokenizes it using the Gemma 4 native chat template, and
reconciles converted and tokenized row counts before building the union tree.
The sampling config disables the legacy prefix and retains the replacement at
repeat 10.

## Final Result

The full audit completed on 2026-08-29 with exact coverage of all 2,786
candidates and zero judge errors. The strict gate retained 2,147 rows: 77.06%
of structurally valid candidates and 47.66% of the original source. The judge
rejected another 639 candidates, primarily for incoherence, incorrectness,
format defects, or low training value.

The Gemma-native tokenized replacement reconciles exactly at 2,147 rows and
contains 315,870 instruction tokens plus 718,261 response tokens, or 1,034,131
unique rendered tokens. At repeat 10 it contributes 10,341,310 tokens per
epoch, down 52.49% from the legacy source's 21,765,750-token contribution.
The current DFM10 union contains the replacement task, and a clean rebuild is
reproducible through `scripts/prepare_dfm10_data.sh`.

## Incomplete-Target Recovery

The 1,128 `incomplete_ending` rejects are recoverable from the authoritative
CC-BY source corpus rather than by unconstrained generation. The local source
snapshot is `data/downloads/datasets/oliverkinch_danish_university_portals/`
and contains the 94 full Markdown documents referenced by the BT rows.

An alignment check on 2026-08-29 found that 1,026 rejected targets are exact
substrings of their cited full document. Each of the remaining 102 has a unique
50--200 character prefix or suffix anchor in that document; none is unaligned.
For the exact matches, 1,017 reach sentence punctuation within the following
2,000 source characters. The median required continuation is 103 characters
and the 90th percentile is 248 characters.

Recovery appends only source text through a safe sentence or paragraph
boundary, normalize PDF whitespace and split-word artifacts, and remove
intervening page-footnote blocks. A strict full-row grounding/coherence audit
is required because naive first-punctuation extraction can stop inside a
footnote or citation. Ambiguous alignments and candidates that do not pass that
audit remain excluded.

The repair has ample room under the 4,096-token training context. Using the
actual Gemma tokenizer, the 1,128 incomplete rows currently have a median of
444 rendered tokens, a 99th percentile of 1,153, and a maximum of 1,357. For
the 1,017 exact alignments with a punctuation boundary within 2,000 source
characters, the reconstructed totals have a median of 471, a 99th percentile
of 1,181, and a maximum of 1,374 tokens. The finalizer must nevertheless retain
an explicit 4,096-token rendered-length gate for the anchored and exceptional
cases.

**Completed 2026-08-29:** deterministic source alignment produced 1,116
candidates from the 1,128 incomplete rows: 1,019 exact alignments and 97 unique
suffix alignments. Twelve rows remained fail-closed because alignment was
ambiguous or no safe boundary existed. The exhaustive E4B audit had zero judge
errors and accepted 902/1,116 recoveries (80.82%). The canonical replacement
now contains the prior 2,147 strict rows plus 902 disjoint source-grounded
recoveries, or 3,049 rows and 1,607,730 unique rendered tokens. At repeat ten,
it contributes 16,077,300 tokens per DFM10 epoch.

The completed recovery is under
`logs/data_audits/danish_university_portals_incomplete_recovery_20260829/` and
is reproducible with
`scripts/finish_danish_university_portals_incomplete_recovery.sh`. The launcher
must be executable or invoked explicitly with `bash`; an initial queue attempt
failed before doing work because that newly created file lacked its executable
bit.

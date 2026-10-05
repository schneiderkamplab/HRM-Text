---
type: Report
title: Persian Wikipedia Transform Sample Review
description: Independent source/window/target and semantic inspection of sixteen published Persian transformations.
status: stable
confidence: high
last_updated: 2026-10-03
---
# Persian Wikipedia Transform Sample Review

## Authorized Minimal Subset (2026-10-03)

The diagnostic-only policy below is **superseded for the exact minimal selector**
by explicit user authorization to remove its 7,086 rows. No uncertain, broad
no-prose, empty-field or fewer-than-three-paragraph filter is authorized.
New immutable package root:
`exports_dfm13/fa-transform-minimal-subset-20261003-v1`.

| Task | Excluded | Retained | Actual final-target rendered tokens |
| --- | ---: | ---: | ---: |
| Denoising | 2,223 | 71,579 | 69,317,705 |
| Paragraph reordering | 1,102 | 30,388 | 32,359,625 |
| Prefix continuation | 3,281 | 107,532 | 53,614,683 |
| Span filling | 480 | 25,457 | 13,370,601 |
| Total | 7,086 | 234,956 | 168,662,614 |

Implementation: `dfm12/fa_transform_subset.py`. Build and verification replay
every census row against its canonical record hash and copy retained byte lines
unchanged, in original order. `subset-receipt.json` and `exclusions.jsonl` bind
the exact exclusion set to parent data/revisions and census report/flags hashes.
Original accepted quality judgments are inherited, not rerun or upgraded into
semantic certification. Original messages, per-row provenance, licenses and
source card are preserved. The old four exports and publication receipts remain
immutable; new publication receipts live in the new root, with registry pointers
updated only after remote attachments and token arrays verify.

All four were retokenized with 16 workers, no skipped rows, at
`data/dfm13/tokenized_fa_minimal_subsets/<name>/<digest-of-source-tokenizer-template-pins>/tokens`.
No historical arrays or frozen assemblies are overwritten. Registry promotion
sets tokenization complete before exposing changed sources to the ordinary
watcher. Existing frozen assemblies remain historical and must not be mistaken
for a rebuilt filtered assembly. No sampling or training was performed.

Commands (build requires a fresh root):

```bash
python -m dfm12.fa_transform_subset build --root exports_dfm13/fa-transform-minimal-subset-20261003-v1
python -m dfm12.fa_transform_subset tokenize --root exports_dfm13/fa-transform-minimal-subset-20261003-v1
python -m dfm12.fa_transform_subset publish --root exports_dfm13/fa-transform-minimal-subset-20261003-v1
```

The same four HF repositories receive a new commit conditional on the old
revision still being current; every uploaded attachment is downloaded at the new
commit and hash-verified. `wave_release.release` now refuses `wikipedia-fa`
before any I/O, preventing a future old finalizer from restoring unfiltered data.
The existing controller skips the still-uploaded historical receipts, so no
unrelated workers were stopped. A scoped assembler adapter verifies the entire
ordered subset and attachment inventory, retaining all ordinary row, array and
sampled native-token checks. Coordination contract:
`docs/reports/fa-minimal-subset-assembler-handoff-20261003.md`.

Upload/promotion outcome is recorded in the new root's `completion.json`; an
absent completion file means publication/integration is not yet complete.

**Completed:** all four are `accepted_uploaded`, registry entries exactly match
the completion receipt, and all 44 uploaded attachments were downloaded and
hash-verified. Subsequent read-only Hub checks confirmed all four heads match:

| Task | New revision |
| --- | --- |
| Denoising | `1c72962862c7496e3cfdc41d0d20eee2bf597ac3` |
| Paragraph reordering | `65c77c036338c5f941a0c66718377b5d0acf2ca3` |
| Prefix continuation | `dcc7f3d1a351f27a37589183a4b897850338d81c` |
| Span filling | `fac978d13cf9e4696957c5e4457377a48cd0282d` |

Completion SHA256:
`ddbd3ed49de133bd78ca745da60db0693c7559234d69e6443c35caa001fd0397`.
`assembly-verification.json` binds every array and checks five native-template
rows per task (20 total); exact byte-subset replay covers every retained row,
not merely that token-parity sample. Old four data hashes and old publication
receipt hashes were checked unchanged after publication. All 81 focused tests
pass (subset, census, publisher, assembler, watcher); OKF validation passes.
The final registry guard also rejects concurrent policy/hold changes rather than
overwriting them. Remaining uncertain/empty-field concerns are intentionally
retained, not silently certified or filtered.

CPU-only independent review of four accepted examples per task in the current
four Persian Wikipedia publications. Deterministic preselected ordinals:
`floor((N-1)*i/3)`, i=0..3 within each published file. No population quality-rate
claim, GPU/model call, production data/code modification or eligibility change.

All 16 source identities, pinned parquet hashes, seeded windows, candidate IDs
and transform messages replay exactly. Separate checks confirm real denoising
deletions, complete nonidentity block permutations and exact trimmed suffix/span
targets. No target drift, wrong-source joins or generative-repair hallucinations
were found. All sampled rows were accepted originals.

Semantic findings distinguish structural problems from language uncertainty:

- All four reordering samples include standalone headings/category lists as
  paragraph units. Two largely test arbitrary page layout; two still have real
  ordering cues between two prose blocks. Source boundaries are genuine, but
  blank-line blocks are not necessarily meaningful prose paragraphs.
- Two prefix samples are category-only windows without the subject's name;
  another primarily predicts a category tail. One has coherent prose/list
  continuation. Nonunique continuation alone is normal language modeling, not
  a bug; metadata-only window selection is a separate usefulness issue.
- Denoising correctly restores 2, 6, 7 and 12 deleted letters in the four cases.
  One target retains an empty birth-date template and repeated club from source.
  A reordering target retains another empty birth-date field.
- Span targets are exact. Solar Impulse context contains a source chronology
  contradiction (July 2015 damage, months of repairs, then April 2015 resumption).
  Rita Marley has suspect literal Persian wording marked as native-review
  uncertainty, not independently proven biographical falsehood.

The Persian instruction templates are comprehensible. Exact source fidelity is
not factual certification, and judges seeing `audit_context.original` can check
answers without proving learner-facing recoverability: that audit metadata is
not rendered as the student's prompt. No blanket source hold or clearance was
applied based on this small sample.

Evidence and complete per-case report:
`docs/reports/persian-wiki-transforms-independent16-20261003/report.md`.
The same directory contains `evidence.json` (full source articles and records),
`mechanical-checks.json`, manual `findings.json`, hash-bound `review.json` and
`receipt.json`. All input/source publication hashes were checked again unchanged.
Report SHA256:
`f76b317439c5980deb6668826ae9d622edd4a052bb7439f8ff5c6fd4c6cb5047`.

## Full Structural Census

Follow-up CPU diagnostic scanned all 242,042 accepted examples without changing
publication or eligibility. Reusable command:
`python -m scripts.diagnose_fa_transform_structure --output <fresh-directory>`.
Seven classifier tests pass. Final diagnostic directory:
`docs/reports/fa-transform-structural-census-20261003-v2`.

| Task | Category-only | Heading-only | Empty-field-heavy | Proposed minimal exclusions |
| --- | ---: | ---: | ---: | ---: |
| Denoising | 2,223 | 0 | 2,074 | 2,223 |
| Paragraph reordering | 111 | 0 | 1,115 | 1,102 |
| Prefix continuation | 3,281 | 0 | 3,328 | 3,281 |
| Span filling | 480 | 0 | 663 | 480 |
| Total | 6,095 | 0 | 7,180 | 7,086 |

These are exact rule counts, not semantic error rates or unique article counts.
The minimal proposal combines strict metadata-only windows with reorder windows
having fewer than two detected prose blocks AND no uncertain blocks; 234,956
examples would remain untouched, not certified good. No filtering was applied.
Category-only denoising can still teach spelling; retaining that utility instead
would reduce the proposed exclusion set to 4,863 examples.

Reordering's effective prose-count histogram is 2,578 zero, 8,026 one, 7,583 two,
and 13,303 three-or-more. Do not automatically discard every low count: unknown
structures and meaningful two-prose ordering remain outside the minimal proposal.
172,522 examples across tasks have detected prose with no empty-field markers;
that is a structural distinction, not whole-corpus semantic approval.

v1 was superseded after manual inspection found ordinary function calls such as
`Eject()` falsely counted as empty fields. v2 excludes identifier-adjacent calls
and avoids calling a long prose block heavy merely for one empty parenthesis.
An empty-field-heavy flag now means at least two malformed markers, or a marker
in short detected prose (at most 300 characters) with no clean prose block.
143 of the 7,180 warnings overlap the minimal proposal; 7,037 are additional
review/cleanup candidates, not an automatic exclusion tranche.

`report.md` has exact IDs, examples, rules, counts, caveats and minimal-filter
proposal. `flags.jsonl` binds every candidate to its record/window hashes;
`report.json` pins code and all publication files/revisions. `receipt.json`
records successful input-hash rechecks. Originals and publication pins preserved.

Related: [Fourth language wave](fourth-language-extension-wave.md),
[Baltic QA source holds](dfm13-baltic-qa-quality-holds.md). QA hallucination
findings must not be automatically generalized to mechanically faithful transforms.

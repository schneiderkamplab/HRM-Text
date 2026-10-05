# Luxembourgish additive source reserve, 2026-10-03

CPU preparation completed, not production admission. Frozen roots, approvals,
targets, source files and cursors remain unchanged. No GPU/API calls.

## Artifact and reproduction

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.lb_seed_reserve \
  --root data/dfm13/wave4/lb-seed-reserve-20261003-v1
```

The command refuses an existing output root. Outputs: `seeds.sqlite`,
`reserve.jsonl`, per-window `validation-ledger.jsonl`, `manifest.json` with
input/output hashes, and `receipt.json`. `ready=true` means prepared reserve;
`admission_authorized=false` and `reserve_only=true` remain explicit.

- Existing LB pool: 34,013 document windows.
- Study candidates and verified reserve: **5,538**, no duplicate/context holds.
- Existing parent documents represented: **4,258**; new unique documents: **0**.
- 2,978 parents supply one additional view; 1,280 supply two.
- Each additional view is disjoint from the original and the other reserve view.
- All source slices, URLs, source-record identities and deterministic extractor
  outputs were checked against pinned Parquet. Unicode character offsets retained.
- Exact and whitespace-normalized duplicate exclusion covers existing LB seeds
  plus reserve, not every language or semantic near-duplicates.
- Full student-template echo probes: 5,538 passed, maximum **2,761/4,096** tokens.
  These are diagnostic user=source/assistant=source probes, not training targets
  or a guarantee that future generated conversations fit. Nothing was truncated.
- Eleven focused tests passed; output hashes and a temporary-root wave-four
  `SourceProvider.next_spec('lb','grounded-instruct',0)` selection passed.

## Pins and rights

Wikipedia revision `b04c8d1ceb2f5cd4588862100d08de323dccfbaa`, config
`20231101.lb`; source Parquet SHA256
`d88fc77344535871bc5f2db666bc44d2e44428a8f439d444a79c403d6863335d`.
Existing source-card evidence lists CC-BY-SA-3.0/GFDL. Reserve selects
CC-BY-SA-3.0 with URL/title attribution and share-alike flags; this is not a new
rights grant. Each row retains original document ID, original seed ID/window,
source revision/file/record hashes, exact text hash, and a separate stable view ID.

Manifest SHA256:
`d2e1fc098d4d5df86f0ecef79f06d337bd45fdeb8b78dc23e5cc1ad1fd5af9e8`.
SQLite SHA256:
`6cd961a5fee591332552d236b960416d115f68ef0cb486ec33e9446cd40b33f8`.
The manifest also pins the original seed database/receipt, study, download
receipt, student tokenizer/template/metadata and builder dependencies.

## Conditional admission

Keep this reserve unused unless observed accepted yield threatens the existing
20,000 grounded target. The maximum source-view inventory becomes 39,551,
requiring approximately 50.57% yield instead of 58.80%; this is capacity arithmetic,
not a measured acceptance estimate or promise to meet the target.

At that point, explicitly review and authorize a separate successor inventory
or reserve-only successor campaign. Verify manifest pins first; preserve existing
selections/cursors, original document IDs and distinct view IDs. Do not replace
the frozen SQLite, reset cursors, repin production or implicitly enable reuse.
The reserve is LB-native only, not a full-wave replacement database.

Enforce at most three total views per parent per family, including the original;
this finite reserve respects that cap but the generic provider does not enforce
parent-level reuse independently. Require distinct task coverage, normal native
generation/review, semantic/near-duplicate checks and actual full-conversation
student rendering before admission. Retain attribution/share-alike provenance.
No short-document relaxation, target reduction or blanket quality approval is
implied. Native fluency and future answer correctness remain unverified here.

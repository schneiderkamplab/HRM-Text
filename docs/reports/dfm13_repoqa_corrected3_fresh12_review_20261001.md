# RepoQA whole-answer review: corrected three and fresh twelve

2026-10-01, CPU-only independent manual review. No admission, upload, model
requests, repository execution, or changes to existing holds/candidates.

## Corrected drafts

Complete answers, original prompts and retrieved evidence were reviewed, not
only the edited claims. Exact hashes and full IDs are in
`data/dfm13/repochat-qa-next-20261001-v1/readiness/independent-corrected3-review.json`.

- **IDSHV-router: keep**, hash `b109f318079ce8e54df7ec5500cdfa99ae6a0cabc03ac4a91ec5c950b759ad92`.
  Algorithm correction and qualified OpenAPI statement are supported. Scope is
  overview, not proof of globally optimal transfers across mandatory-stop segments.
- **OneCode: keep**, hash `4ef099a9f8b098bc286c365542e91b75bec9832545efc28f3424867602e5e07f`.
  Complete server/client explanation remains supported and malformed options are
  now explicitly distinguished from effective configuration.
- **Agnai: repair**, hash `e7c5b9f95e24ea7618c047dfcef11c7ed80ee51ef035cef5576972e2391542bb`.
  Entrypoint fixed, but remaining `srv/db/` Redis ownership claim is wrong:
  clients are in `srv/api/ws/redis.ts:47-48`, exported by `ws/index.ts:2`.

No original/source-level hold is automatically cleared, including for the two
supported corrected hashes. These drafts are separate from filtered-55 originals.

## Fresh twelve

Packet `readiness/fresh-manual-sample-v2.json`, SHA256
`244132215f5014b592f1869bcc8a39d0fae22a7399e8471ccb08e15f3fc25997`.
All twelve IDs occur in current filtered-55. All prompts are English. Freshness
is relative to earlier manual packets; no claim of an untouched calibration set
after this review. Judgments below assess whole answers, not judge explanations.

| Repository | Disposition | Bounded finding |
| --- | --- | --- |
| stanford-oval/storm | keep | Research stages, perspective questioning and Co-STORM mind map supported; not a measured performance guarantee. |
| vedalai/neuro-game-sdk | repair | No schema-conformance guarantee: returned action JSON must be validated. Forced actions may wait during speech. Optional voice-chat input/output omitted. |
| edereynaldesaintmichel/mode_connectivity | repair | Loss uses squared cross-entropy and aggregate step norm, not stated plain CE/total distance. Tensor-construction regularizer needs intended-versus-effective gradient caveat. |
| jstrieb/urlpages | repair | Link content persistence is not unconditional availability; trusted/extant decoder host still required. |
| ultimatemember/ultimatemember | repair | `um_user('ID')` is selected profile context, not necessarily logged-in user. Correct function, wrong unconditional identity description. |
| cli/cli | needs clarification | Literal test-string matches are correct; runtime CLI-help interpretation is unresolved. |
| robertpakalns/VoxtulateClient | repair | Specific bridge/storage/security and swapping explanation exceeds retrieved README/listing. Actual request swapping is in `src/utils/swapper.ts`. |
| anuradhawick/kmertools | keep | Rolling two-bit representation and width dispatch supported. |
| SagerNet/sing-box | keep | Empty base pool, embedded Mozilla PEM and explicit additions supported. |
| yaohungt/Multimodal-Transformer | repair | Causal mask is not a padding mask; conclusion that padding cannot contribute is unsupported and contradicts acknowledged absent padding-mask implementation. |
| PeterDaveHello/url-shorteners | keep | Purpose, lists and stale-data caveat supported; inactive also includes false positives. |
| lucferreira-27/my-anime-back | keep | Wayback/Jsoup purpose and UI workflow supported. |

**5 keep, 6 repair, 1 needs clarification.** Repairs vary in severity: MulT's
central padding answer is materially misleading; URL Pages needs a narrow host
availability qualification. Do not equate every repair with a wholly fabricated
answer. No corrected text was generated or installed during this review.

Receipts in the same readiness directory:

- `independent-corrected3-review.json`: three exact corrected-answer hashes.
- `independent-fresh12-findings.json`: manual findings with source anchors.
- `independent-fresh12-review.json`: expanded full IDs, answer hashes, original
  trajectory/snapshot hashes, per-answer judgments and `admission=false`.

Verified 12 answer/tool-packet matches, 24 trajectory/snapshot hashes, and three
corrected-answer hashes. Supplemental source inspection is identified in findings.
No runtime tests were executed. Existing source evidence was read, not imported.

## Meaning of the claim pilot

The reported claim-level 8/8 result does **not** establish whole-answer
generalization: Agnai's corrected claim is valid while another claim remains
wrong, and fresh filtered candidates have the issues above. This manual review
did not run the claim checker on the twelve cases, so it supplies no new measured
checker accuracy or causal comparison against that pilot. Pass filtering alone
is insufficient evidence for scale/admission. Parent/Harvey must reconcile these
exact hashes with the existing hold mechanism; this report does not mutate it.

# Grounded RepoQA eight: independent terminal review

2026-10-01. **6 keep, 1 localized repair, 1 needs clarification.** Complete
current answers assessed against user questions and current pinned evidence.
CPU-only; no repository execution, model calls, admission or old hold mutation.

| Repository | Result | Assessment |
| --- | --- | --- |
| agnaistic/agnai | repair | Redis location corrected, but `ws/index.ts:2` re-exports messaging helpers, not the `clients` object. Correct this one new clause. |
| vedalai/neuro-game-sdk | keep | Speech-related waiting, malformed action data and optional bidirectional voice transport now covered. |
| yaohungt/Multimodal-Transformer | keep | Correctly distinguishes absent padding-mask support from causal masking and stale docstrings. |
| rswier/c4 | keep | Four functions, precedence climbing, declarations and opcode VM match complete source; no native-code or executed-test claims. |
| edereynaldesaintmichel/mode_connectivity | needs clarification | Squared CE and aggregate norm fixed; detached STD-gradient caveat still omitted. |
| jstrieb/urlpages | keep | Decoder-host availability requirement now explicit. Minor citation imprecision: README:28 describes Link Lock as static/distributed, not URL Pages. |
| ultimatemember/ultimatemember | keep | Correct logged-in-ID argument versus selected UM profile distinction. Not a guest authentication guarantee. |
| robertpakalns/VoxtulateClient | keep | Actual request interception, protocol handler, fetch cloning and DOM observer replace guesses; security assertion is attributed to README, not certified. |

MergePath `full_merge.py:164` constructs `torch.tensor` from scalar norms,
discarding their autograd history. Its STD term changes the loss value without
gradient through those norms to `alphas`. Constructor semantics are documented
in [PyTorch](https://docs.pytorch.org/docs/2.14/generated/torch.tensor.html).
No execution was used. Current answer no longer expressly promises uniform-step
optimization, so classify as a missing qualification in this targeted repair,
not repetition of the previous wrong formula. One caveat sentence suffices.
The automated review's `non_stop:length` is a technical non-verdict, not a
semantic rejection.

Receipts under `data/dfm13/repochat-qa-next-20261001-v1/grounded-repairs-v1/`:

- `independent-terminal-findings.json`: manual findings and prior-defect status.
- `independent-terminal-review.json`: full IDs, exact answer hashes, trajectory,
  snapshot and automated-review hashes, evidence digests and dispositions.

Packet SHA256: `6805808e4e824bac2e88b2c93611ab5635f575d450a911b272521cb3a6ecc547`.
Verified eight answer hashes, 24 artifact hashes and all 16 supplemental reads
against pinned source hashes and exact numbered text. Existing holds remain
unchanged, including for keeps; owner reconciliation must use current hashes.
Known-case repair evidence is not a fresh generalization/accuracy estimate.

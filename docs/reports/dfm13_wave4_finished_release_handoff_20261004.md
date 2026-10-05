# W4 finished export / integration handoff, 2026-10-04

## Actual complete recovery

`data/dfm13/wave4/empty-rationale-all-lb-release-20261004-v3/manifest.json`
is complete:646551 original accepted +144292 isolated recoveries =790843.
LB20372+70471=90843, all other ten languages70000 each. Residual shortfall0.
`independent-count-verification.json` verifies all66 group recovery counts,
144292 unique recovery fingerprints, original accepted totals and zero active
slots. No generation budget extension or GPU top-up is needed.

## Completed CPU pipeline

Final completion supersedes the running status below: all66 packages finished,
790843 conversations,1404259 assistant targets,974517843 stored tokens.
`tesla-ready.json` binds `complete.json` and the final isolated registry hashes.
Independent verification checked all66 export-manifest hashes, per-language and
aggregate counts, zero skipped/truncated targets in every completion, and exact
native token IDs for104 assistant targets (all targets of the first conversation
per package). This bounded native smoke is not a full-corpus token-ID replay;
the exporter separately performed full array integrity and target/token totals.
The combined focused suite passed41 tests. The pipeline progressed steadily
without retries or a pathological bottleneck; no GPU processes were touched.
Tesla's `dfm12/wave4_finished_assembly.py` adapter is present for the explicit
contract. Canonical assembly and HF upload remain separate, unclaimed steps.

Completed producer PID3434470, detached `dfm12.wave4_finished_release`, root
`data/dfm13/wave4-finished-release-20261004-v1`; adjacent `.launch.json` and `.log`.
Native tokenization uses16 workers, all assistant targets, full conversation and
tool history, no truncation or target-only shortcut. Conversation/target/rendered
token totals must match; original assembled token totals are checked against the
stored native arrays. Selected original and recovered fingerprints share one
dedup set. Source campaign databases remain read-only under terminal-owner locks.

Original rows reuse proven Baltic accepted validation in isolated W4 audit
globals (no shared-module patch). Recovered rows require exact release receipt
and candidate hashes plus fingerprint proof. Cards disclose automated audit,
the narrow technical recovery, pending HF upload, and source-specific rights;
they do not invent human/native certification or blanket licensing.

## Tesla integration contract

Registry is isolated: `<root>/registry.json`, `inherits=dfm12`, `additions`.
It grows only after each package has completed tokenization and array checks.
`complete.json` is the whole66-package completion gate; do not infer completeness
from an existing registry. No central registry is mutated by this owner.

Explicit new contract: `wave4-compact-recovered-full-history-v1`.
Names: `dfm13_wave4_synthetic_<language>_<family_with_underscores>`.
Status: `accepted_local_tokenized`, uploaded=false, hf_revision=null, repeat1.
These are not accepted_uploaded entries and must not be mislabelled to bypass
the assembler's publication contract.

Each entry provides full-conversation `output`/hash; `rows` conversations;
`training_targets`/`tokenized_rows` expanded assistant targets; stored
`tokenized_tokens`; `tokenized_path`; per-array pins; per-package
`accepted-evidence.jsonl`/hash; source-proof path/hash; export-manifest path/hash;
and proposed canonical HF repo `schneiderkamplab/dfm13-multilingual-<family>-<lang>`.
Data/card/source inventory reside under `packages/<name>/`.

Source proof differs from Baltic's one-snapshot shape: `source-proof.json` has
`pins` for all eight immutable terminal source ledgers and bundle/terminal/
supplement manifests, plus original/recovered/conversation counts. It does NOT
claim a nonexistent `accepted-snapshot.sqlite`. Evidence is per package and
contains `id,name,fingerprint,pins,basis`, where basis is `original_accepted` or
`technical_recovery`. Recovery receipt pins transitively bind complete raw
generation/review calls, source selection, render validation and global ownership.

Minimal adapter may reuse Baltic full-history array and native parity checks,
but must dispatch this explicit contract, pin the source-proof `pins` map, and
follow recovery proof pins rather than assume the Baltic snapshot filename.
Tesla owns that integration/central-registry step. Do not register twice or
combine the supplement as a second standalone source: this exporter already
combines originals plus selected recoveries exactly once.

13 focused exporter/schema/release tests pass, plus an actual original BE
grounded accepted-row validation smoke. The broader prior suite passed38.
No HF upload or full assembly completion is claimed until its actual receipt.

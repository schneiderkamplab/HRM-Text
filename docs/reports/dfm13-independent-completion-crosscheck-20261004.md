# Independent DFM13 Completion Cross-check

Read-only inspection, 2026-10-04. No registry, ledger, worker, GPU or training
changes. Handoff to parent/Tesla; no direct agent-message tool is available.

## Actionable Gaps

Update2026-10-04: the MATH package gap below is now fixed on CPU; see
`docs/reports/dfm13-math-package-tesla-handoff-20261004.md`. Upload remains
unclaimed; registry coordination stays with Tesla. Original inspection follows.

1. **MATH HF-ready package is missing.** `hendrycks_math_worked` is correctly
   registered, tokenized and included in the authoritative assembly at repeat5:
   7,496 rows /2,431,145 stored tokens. Its registry entry has no derivative
   `hf_repo_id`, `hf_revision` or publication receipt, and no MATH package was
   found under `exports_dfm13`. Local conversion is not missing. Assign a narrow
   CPU publisher/package owner to preserve the existing JSONL, MIT attribution,
   upstream revision, screening evidence and native tokens. Do not regenerate,
   change repeat5 or mistake the upstream HF repository for a published DFM13
   derivative. No isolated fix was made without ownership coordination.
2. **TLPC must reach the next authoritative assembly.** Both packages are
   uploaded, byte-verified, tokenized and in the central registry, and actual
   assembler verification passed. They are the only central-registry names
   absent from the current authoritative snapshot. Tesla's all-finished queue
   already documents intake of these entries at freeze. At inspection its
   progress was `release_ready=true, predecessor_ready=false`; do not claim
   successor promotion yet. Add180,000 targets /170,673,889 tokens, representing
   100,000 conversations, without redoing publication or tokenization.

## Confirmed Inventory

| Family | Published/registered conversations | Authoritative training-view rows | Stored training-view tokens |
|---|---:|---:|---:|
| Audited Arena,8 sources |199,678|191,136|165,625,986|
| jjzha,6 sources |170,348|169,148|115,935,166|
| Worked MATH,1 source |7,496 local, no derivative publication receipt|7,496|2,431,145|
| Baltic OPUS,43 sources |6,675,232|6,675,232|675,279,476|
| Static W4,364 sources in authoritative snapshot |local/published mixture|14,705,778|3,176,925,821|
| TLPC,2 sources |100,000|pending next snapshot:180,000 targets|pending next snapshot:170,673,889|

Arena/jjzha differences are documented whole-row4096-context selections, not
lost exports. Full published histories remain available. All14 source families
are represented; no non-wave tokenization gap found. jjzha release receipt says
`uploaded_and_integrated`; six registry revisions match its dataset receipts.

Central registry has311 entries:75 W3,219 W4,17 other. Authoritative snapshot
also carries145 local quota-held W4 packages, so central registry alone is not
the full inventory. Do not duplicate those145 exports or infer they are all
uploaded. Boole/Tesla retain W4/DaLA/Baltic work ownership.

All supplied output, token-root, token-receipt and export-manifest paths in the
central registry exist. Fresh payload/manifest/token-receipt SHA256 checks on
all17 non-wave entries checked45 pins with zero mismatches. This is not a fresh
remote re-download of all HF sources or a full replay of all token arrays.

## Deliberate Exclusions, Not Forgotten Sources

- PRISM is **not** one of the eight Arena entries. The exact checked names are
  `ai_arenaen_preferred`, `arena_human_preference_140k`,
  `arena_human_preference_100k`, `arena_human_preference_55k`,
  `comparia_preferred`, `helpsteer3_edit`, `helpsteer3_preference`, and
  `arena_expert5k`. All eight are registered; no PRISM entry exists in either
  central or authoritative registry. The wiki's explicit October1 follow-up
  holds PRISM from audit pending licensing, not merely from publication.
  `data/dfm13/pending-arena-eligibility-20261001/eligibility.json` corroborates
  `name=prism,status=held,reason=license_pending`. Its18,441 inspection
  candidates are not audited approved additions. No superseding clearance was
  found in the wiki/reports search. The TLPC-specific overlap waiver and
  DynaWord/DynaInstruct license authorization do not establish PRISM clearance.
  See `wiki/pages/dfm13-pending-arena-preparation.md` (Pinned Source Policy)
  and `docs/reports/dfm13_audited_replacement_handoff_20261001.md`, which
  explicitly says PRISM is not a ninth export.
- SearchArena, Mimir Search and RepoChat: explicit research-only user policy;
  no integration or publication work implied by the broad completion request.
- Two Baltic QA and two Latvian P3 packages: current assembler returns
  `quality_hold_source_fidelity`. Preserve holds.
- Fars `pn_sum` and `wiki_sum`: terminal source exclusions, not pending retries.
- Broad FinePDF/standalone Europarl rights-limited material: not automatically
  admitted. The six exact-rights FinePDF packages are already represented.
- CroCo tool-bearing and denied FLAN-derived material: documented exclusions,
  not missing accepted-source registration.

## Evidence And Snapshot Identity

- `config/dfm13_sources.json` SHA256:
  `854c4ed118aa4d024001d041dee5b7cd7b8a3642de127a0bc7eb08e3461b2757`.
- `data/dfm13/authoritative-additions.json` SHA256:
  `bcc74c71beb923f045ac18b418c421d93da4ad2aea087617ca92b70427f0f6e7`.
- Authoritative root:
  `data/dfm13/verified-finished-additions-dala9-20261004-v1`;
  468ready sources /34,449,485 rows /5,412,678,655 tokens. Four holds.
- Its `assembly.json` and `registry.snapshot.json` were inspected directly.
- Pending successor: `data/dfm13/verified-all-finished-additions-20261004-v1-control/progress.json`.
- Arena: `exports_dfm13_audited/20261001-v1/private/` receipts.
- jjzha: `data/dfm13/jjzha-finalize/release.json` and per-source receipts.
- Non-wave tokens: `data/dfm13/nonwave-tokenization-20261003-v1`;
  views: `data/dfm13/nonwave-context-fit-20261003-v1`.
- TLPC: `data/dfm13/tlpc/release-100k-v1/completion.json` and
  `integration-verification.json`.

Wiki approval/exclusion cross-check used DFM13 plan, jjzha native additions,
pending Arena preparation, verified additions assembly, local wave integration,
Baltic language sources and Search parallel-budget recovery pages. Older wiki
checkpoints saying jjzha is unprepared or no Baltic synthetic client has run
are historical, not current omission evidence. This is a bounded inventory
cross-check, not an assertion that every historical discovery candidate was
approved or that all remaining publication work is complete.

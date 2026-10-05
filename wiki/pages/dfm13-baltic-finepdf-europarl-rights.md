---
type: Research
title: Baltic FinePDF and Europarl Rights
description: Exact-document FinePDF publication evidence and the unresolved Europarl excerpt versus altered-task scope.
status: draft
confidence: high
last_updated: 2026-10-03
tags: [dfm13, baltic, rights, publication]
---
# Baltic FinePDF and Europarl Rights

## Scoped FinePDF Release

2026-10-03: two LT documents (GAMLEC game rules and CEMIVET VET factsheet)
and one LV article (DOI10.17770/er2021.1.6497) have explicit CC BY4.0 notices
verified in original publisher PDFs. FinePDF's ODC-By license is retained as
database attribution, not treated as covering individual document copyright.
The LV extraction omitted its license footer; original publisher evidence matters.

Exact source/document/row/URL/hash gates and existing positive audits produced
7 LT and2 LV conversations. All6 packages are uploaded/registry-integrated;
74 remote attachments verified. Existing CPU tokenizer completed9 rows and17,944
tokens. Original messages, audit IDs, sources and raw judgments are unchanged.
Three rejected candidates from those documents remain excluded. All other
53,736 LT and48,752 LV candidates remain outside this bounded rights whitelist;
this is not a claim that all lack rights or quality.

Implementation: `dfm12/finepdf_rights_subset.py`;15 focused tests,21 including
BLKT publication regressions. Evidence and exact publication pins are in the
[focused report](../../docs/reports/baltic-source-rights-20261003/report.md) and
its `verified-handoff.json`. No GPU calls or live audit writes were made.
Future document additions require new evidence and versioned output, not a
whole-domain allowlist. Do not overwrite these published package roots.

## Europarl Remains Scoped

The current [Parliament legal notice](https://www.europarl.europa.eu/legal-notice/en)
supports attributed reuse and linked partial reproduction, subject to item-specific
conditions. OPUS archive LICENSE merely defers to original-source terms; no CC
grant was discovered. Captured primary notice and both local archive pins are
preserved in the focused report's `evidence-europarl/` directory.

No Europarl release was made: per-sitting links are not yet verified, and applying
the general reproduction permission to deliberately corrupted/reordered inputs
remains unresolved. LT54,503/LV63,450 candidates stay intact. A narrow proposed
first scope is38,253 verbatim prefix-continuation candidates before positive-audit
selection; the other79,700 remain held. The report states the bounded choice
between this excerpt-only scope (after attribution verification) and seeking
explicit clarification for altered task forms. User inclusion approval must not
be described as rights-holder permission.

This supersedes the earlier statement that FinePDF had no published subset;
it does not lift the remaining FinePDF or Europarl source-wide unknowns. See also
[Baltic publication rights](dfm13-baltic-publication-rights.md).

## Sitting Attribution Follow-Up

2026-10-03: full local prefix coverage maps19,081 LT candidates to284 sitting IDs
and19,172 LV candidates to287 IDs; every ID has matching pinned OPUS XML members.
These are prepared, not accepted counts. Official per-sitting evidence remains
unavailable from bounded checks: two ordinary CRE URL requests returned empty
HTTP202 responses. Inferred URLs are not verified references. No antibot bypass
was attempted. The [sitting report](../../docs/reports/baltic-source-rights-20261003/europarl-sitting-links/report.md)
and hash-bound receipt separate local provenance from missing official evidence.
The existing scope question remains pending, without a repeated request. No
Europarl publication or source/audit mutation occurred; rights-held rows must not
be labeled external-model quality failures. Main can forward FinePDF's existing
`verified-handoff.json` to Poincare independently of this hold.

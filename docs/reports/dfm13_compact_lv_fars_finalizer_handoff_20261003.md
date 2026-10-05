# LV/Fars compact-audit finalizer handoff

Owner scope: accepted-only CPU selection/export of the completed compact source
audit, its invalid/interrupted retries and the running one-shot repair population.
No GPU/server changes or additional generation. No generic quality-hold clearing.

## Running staging

Module: `scripts.finalize_compact_lv_fars`; seven focused tests passed.
Detached PID2744627, start_ticks248068899, four CPU threads.
Log: `logs/dfm13/compact-lv-fars-finalizer-20261003-v1.log`.
Launch receipt: same prefix `.launch.json`.
Output: `exports_dfm13/compact-lv-fars-staging-20261003-v1`.
Progress: `progress.json`; on completion `receipt.json` plus `seal.json`.
`selection.sqlite` binds original/latest outcome, request, source and candidate
hashes per row; three component folders contain native conversation JSONL.
This is staging, not a claimed completed upload or approved training addition.

Original population96922 = LV7626 + Fars89296 (pn_sum58650/wiki_sum30646).
Original terminal decisions32556keep/25060repair/16515verification/14440reject/
7840invalid/511interrupted. Both technical retry populations are complete.
The one-shot repairs are still running; only durable completed keep re-audits
are eligible, and pending/failed newer stages cannot fall back to original text.

## Integrity and gate

Original LV records are revalidated against accepted ledger fingerprint/spec/
source. Original Fars packets validate candidate/upstream digests and unchanged
full user inputs. Review request payloads must exactly equal those records.
Retry parent-request hashes must match. Repaired candidates are reconstructed
from complete raw repair JSON, changing only the listed assistant indices, and
must exactly equal both saved repaired record and blind-review request.
Only complete noncontradictory raw keep verdicts pass; verification/repair/
reject/incomplete outcomes are not accepted. Four CPU threads re-render every
selected row using actual training metadata and native Gemma target extraction;
full context4096, no truncation, original user/source retained.

Five LV independent holds and seven Fars independent holds remain excluded by
source identity across candidate versions until exact new-hash clearance.
Staging outputs retain admission_authorized=false and publication_ready=false.
Do not treat a model keep or completion receipt as independent hold clearance.

## Poincare/parent coordination

Please relay the independent20 review receipt. For each known held row, clearance
must name the original audit ID (`lv-...` or `fars-...`), exact final-record or
messages digest and an explicit passed disposition. A general sampled pass does
not clear all holds. Other newly discovered held hashes must also be excluded.
The selection DB evidence has final_record_sha256 and final_messages_sha256 for
matching. No direct agent-message tool is available; this artifact/parent relay
is the coordination interface. The publisher must verify the review receipt
hash and select the latest exact reviewed version, never silently alter it.

Proposed canonical HF names (existence checked with cached auth; all absent):
- schneiderkamplab/dfm13-wave3-synthetic-lv-grounded-instruct
- schneiderkamplab/dfm13-wave4-ParsiAI-FarsInstruct-fa-pn_sum
- schneiderkamplab/dfm13-wave4-ParsiAI-FarsInstruct-fa-wiki_sum

LV is synthetic grounded generation from Wikipedia/Europarl, NOT the existing
`dfm13-wave3-baltic_lv_qa` source. Do not append to or replace that QA package.
Fars components follow existing wave_release naming. Parent should confirm no
other owner is publishing these component identities before remote creation.

Fars source attribution/license is pinned in the original download card and
packet provenance; preserve underlying dataset/template fields as in
wave_release. LV has3054Europarl/4572Wikipedia original rows; do not label all as
one permissive synthetic license. Preserve source-specific Wikipedia terms and
European Parliament attribution/partial-source-link conditions. Existing source
rights evidence is under docs/reports/baltic-source-rights-20261003. The staging
artifact does not assert that unresolved source-specific publication conditions
have been cleared.

Next: finish staging, reconcile final repair population, apply exact independent
hold dispositions, bind license/attribution and canonical package names, seal
accepted-only export, upload with remote revision/hash verification, then integrate
only verified packages under the registry lock. No upload/integration claimed yet.

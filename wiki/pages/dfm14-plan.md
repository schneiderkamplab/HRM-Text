---
type: Plan
title: DFM14 Plan
description: Research scope for language expansion, knowledge and commonsense enrichment, and additions deferred beyond DFM13.
status: draft
confidence: medium
last_updated: 2026-10-05
tags: [data, dfm14, multilingual, planning]
---
# DFM14 Plan

## Naming and Boundary

On 2026-10-05 the owner renamed the work previously called post-DFM13 to
**DFM14**. This supersedes the provisional name, not existing DFM13 decisions.
The label covers research and candidate assessment; it does not imply approval
of every candidate or a completed/downloaded/audited training mixture.
Do not alter the running DFM13 verification or sample for these candidates.

## Requested Language Scope

The 2026-10-05 requested expansion comprises **16 distinct additions**:

- Smaller European languages: Irish, Maltese, Macedonian, Basque, Galician,
  and Welsh.
- Russian, Turkish, Chinese, Arabic, Japanese, Indonesian, Korean, Hindi,
  Vietnamese, and Hebrew. Indonesian is counted once.

Plan initially for Simplified Mandarin Chinese and Modern Standard Arabic;
neither implies coverage of all Chinese varieties or Arabic dialects.
Adding these to the 34 DFM13 language variants would yield 50 planned variants,
not a claim of evaluated proficiency or completed preparation.

Irish and Maltese complete coverage of the EU's 24 official languages, but
not Europe's languages. Remaining gaps include Sami languages (Northern Sami
first for Nordic scope), Frisian varieties, Scots, Scottish Gaelic, Breton,
Cornish, Manx, Romansh, Friulian, Ladin, Sardinian, Corsican, Occitan, Asturian,
Aragonese, Sorbian languages, Romani varieties, Yiddish, Rusyn, Karelian and
Kven. Dedicated Montenegrin coverage is not implied by Serbian. Greenlandic is
relevant to Nordic scope, although geographically outside Europe; Armenian,
Georgian and Azerbaijani depend on the chosen Caucasus boundary. This is a
non-exhaustive backlog, not an additional generation authorization.

Reference lists: [EU official languages](https://european-union.europa.eu/principles-countries-history/languages_en)
and [Council of Europe language guides](https://www.coe.int/en/web/european-charter-regional-or-minority-languages/language-guides).

## Workstreams

Remote execution handoff: [DFM14 remote production](dfm14-remote-production-handoff.md).
The generation host is independent of the live DFM13 XL training host.

1. [Language priorities](dfm14-language-priorities.md): first research group
   Russian, Turkish, Chinese, Arabic and Japanese; other candidates ranked.
2. [Language source readiness](dfm14-language-source-readiness.md): concrete
   instruction/chat sources, text routes, evals and remaining gaps.
3. [Knowledge and commonsense](dfm14-knowledge-commonsense.md): English
   enrichment regardless of source country, Chinese reasoning, and the
   proposed 500K accepted-row pilot. It is not an authorized generation job.
4. [Potential additions](dfm14-potential-additions.md): Dyna source additions
   and replacements plus newly granted Matina Persian access.

## Shared Preparation Contract

Follow the [new-language expansion playbook](new-language-expansion-playbook.md)
for component quotas, audit/repair requirements and throughput-safe sharding.

Reuse the European-wave structure: existing instruction/chat data, four text
transformations, source-grounded synthetic conversations, translation pairs and
language-specific evaluations. Retain native Gemma rendering and source IDs.
Source availability alone is not row-level quality, corpus access, or proof of
enough unique accepted data. Pin/download/sample before committing token targets.

Use the prior 35K/70K synthetic targets as provisional planning brackets:
35K where accepted existing instructions cover the task families well; 70K
where native breadth remains thin. Assign after audit, not from raw row counts.
Validate native sentence boundaries, corruption rules, script variants,
multi-turn/tool structure and teacher/reviewer calibration separately.

Prefer high-quality English-aligned parallel corpora first. Check the actual
licence/domain/volume of each OPUS pair; do not assume every new language can
meet the previous all-to-all quotas. Record pivot-translated pairs separately.
DaLA additions are not automatically created by this planning work.

## Time Budget

See [DFM14 production estimate](dfm14-production-estimate.md) for measured
throughput references, volume-dependent scenarios and exclusions. No production
campaign is started by this plan.

## Success Criteria

Separate language coverage from transferable knowledge. Use native evaluation
plus English MMLU/ARC-C/MATH/HumanEval and Danish retention, with equal-token
ablations where feasible. Keep benchmark test items and translations out of
training. English improvement is a hypothesis, not a guaranteed side effect
of adding languages.

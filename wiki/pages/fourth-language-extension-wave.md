---
type: Research
title: Fourth Language Extension Wave Sources
description: Parallel, text and instruction source assessment for ten further EuroEval languages and Persian.
status: draft
confidence: medium
last_updated: 2026-10-03
tags: [multilingual, opus, persian, data, expansion]
---
# Fourth Language Extension Wave

## TLPC Access Restored, 2026-10-04

**Owner decision, 2026-10-04:** prepare 100,000 accepted Persian source-grounded
Q&A/chat conversations from TLPC for DFM13. This supersedes the recommendation
to add further TLPC four-task transformations: Persian already has four published,
filtered Wikipedia transformation datasets. Working allocation is 60,000
single-turn Q&A and 40,000 multi-turn conversations, with diverse questions and
follow-ups, source text in the conversation, and Gemma4-native rendering.
Count accepted conversations, not attempts or individual turns. Preserve source
URL/date/revision and fingerprints; retain attribution and distinguish historical
claims from current facts. Independently audit source fidelity, Persian fluency,
and conversation coherence before accepted-only export/integration. Preparation
is authorized; these targets are not a claim of completed generation. Reuse
shared servers without interrupting existing campaigns, queuing GPU work if
capacity is already occupied.

**Execution refinement:** use eight independent generation/audit shards, each
targeting 12,500 accepted conversations (7,500 Q&A and 5,000 chats). Partition
normalized source documents deterministically before generation, with separate
ledgers, progress files and output writers per shard. Avoid a central per-row
ledger, batch barriers and fixed per-request pacing. Merge only verified accepted
outputs, deduplicate across shards, and replenish any shortfall so the final
target is 100,000 unique accepted conversations. Measure actual throughput,
server queues and KV occupancy before asserting the pipeline is well-fed.

**Client allocation clarified by owner:** launch eight Q&A clients and eight
multi-turn chat clients, each with concurrency 64. Each of the eight servers
receives one Q&A client (7,500 accepted target) and one chat client (5,000
accepted target): 128 concurrent requests per server, 1,024 across this campaign.
Each client owns its own ledger and writer. This supersedes the initially
proposed single client per server sharing a 64-request limit.

**Launch and five-minute measurement, 2026-10-04:** all 16 clients launched at
`data/dfm13/tlpc/grounded-100k-v1`, with separate ledgers and 64 concurrency
each. The receipt `measurement-5min-20261004.json` contains eleven 30-second
samples. Across all shared campaigns, throughput was 21,722 requests/min,
74,503 generated tokens/s and 481,767 input tokens/s. Sampled GPU utilization
averaged 93.5% (68-100%); KV occupancy averaged 90.7% (87.2-93.9%). Aggregate
running requests ranged 4,694-4,802; waiting was zero except nine requests at
one sample. No preemptions or metric endpoint errors were observed. TLPC alone
added 10,962 accepted conversations in five minutes (2,192/min): Q&A 1,479/min,
chat 713/min, reaching 11,444 accepted. Server rates include the existing wave4
campaign, not just TLPC. Acceptance denotes automated audit, not manual semantic
certification; export/integration still require their recorded validation gates.

Actual authenticated payload downloads now succeed at revision
`e2fea1d2c4c0828a218c79d6806fe98f821ad8ce`, superseding the earlier403
deferral below. Six pinned shards (211,178 compressed bytes,127 records) matched
their LFS hashes; no credential blocker remains. Sample-local normalized bodies
contain five duplicate occurrences. Formal Persian articles are useful candidates,
but navigation, historical claims and health advice prevent blanket admission.
Recommend curated source-grounded transformations, not raw continuation or scraped
QA as gold. Inherited/evaluation overlap has not been screened by this check.
Owner approval remains valid; retain CC-BY-NC-SA-4.0 metadata.

See [bounded usability assessment](../../docs/reports/dfm13_tlpc_usability_20261004.md)
and the [pinned primary card](https://huggingface.co/datasets/Targoman/TLPC/blob/e2fea1d2c4c0828a218c79d6806fe98f821ad8ce/README.md).
Receipt and sample hashes are under
`data/dfm13/wave4/tlpc-usability-1791109046036714235/`.
No production, server or GPU changes were made.

## FarsInstruct Independent Accepted-Target Review, 2026-10-03

**Superseding publication policy (same day):** the user authorized a source-wide
hold for **pn_sum and wiki_sum**, not just the seven sampled candidate versions.
`dfm12.wave_publication_holds` now denies both components at `wave_release`
entry and in `advance_wave4_instructions` before the uploaded fast path or ledger
processing. Missing/deleted hold evidence cannot clear the gate. PersianQA,
farstail and parsinlu remain outside this hold. Existing GPU workers and source
quality ledgers were not changed; held components are skipped by the controller.

The separate hash-pinned receipt is
`data/dfm13/wave4/publication-holds/farsinstruct-source-fidelity-20261003.json`.
Release requires a stronger independent **31B full-source-record audit**, including
numerical fidelity, omissions, scope/modality and unsupported details, plus review
of the comprehensive-summary prompt adaptation versus original short summaries.
Any prompt adaptation needs a new version and fresh review, not silent edits to
sealed records. No new 31B audit was launched by this enforcement task.

The locked registry check found no uploaded entries for either held component;
its helper marks any matching existing upload `quality_hold_source_fidelity`
without altering files, repeat, counts or pins. Controller PID 2293017 was verified
idle with exact command/cwd identity and all instruction-component locks available,
then replaced by PID **2365731**, retaining command/environment/log. The replacement
completed a cycle reporting both holds. Receipt:
`data/dfm13/wave4/publication-holds/controller-restart-20261003.json`;
log: `logs/dfm13/wave4/advance-instructions.log`.

CPU-only 31B handoff: `dfm12.fars_summary_packets` prepares the separately sealed
`data/dfm13/wave4/fars-summary-31b-packets-v1` snapshot and resumable bounded
packet batches. It includes full original Parquet rows and final candidates,
with original prompts unchanged, and stage-separated repair/fresh-review builders.
The frozen population is 77640 targets, including 3965 completed repair outputs
not already materialized in accepted ledgers. Queue generation completion is
not audit completion: invalid/declined outputs and pending/running jobs are
preserved separately. New completions require a separately pinned delta.
Actual 31B tokenizer/context preflight and review remain pending; no GPU requests
or admission are authorized by packet creation. See
`docs/reports/dfm13_fars_summary_31b_cpu_packets_20261003.md` for Jason's gate
interface handoff, prompt-mismatch policy and proposed unclaimed-job deferral.
Initially the live queue was not changed: deferral was assessed and reported only.
CPU expansion completed all 77640 packets with zero blocked records (58648
pn_sum, 18992 wiki_sum); `cpu-complete-receipt.json` pins the output database.
This does not include later live generation completions and is not 31B review
completion. Packet/gate/Fars selection tests passed 15/15.

Subsequent explicit authorization: **10659** never-claimed held-source generation
jobs were conditionally moved to `deferred31B`; 204 proposed rows were skipped
after claim-state changes. Payloads/counters/events were preserved, with new
hash-bound authorization events. The separate receipt root is
`data/dfm13/wave4/fars-summary-deferral-20261003-v1`. They remain **unfinished31B**,
not reviewed. The actual transition readiness gate now permits only an exact,
contract-pinned authorized deferred set; all other nonterminal states still block.
No old comparison manifest pins were changed. New transition roots are required.

Completion delta `fars-summary-31b-delta-v1` adds 11656 packets (10659 deferred
originals and 997 newly completed corrections). Actual pinned 31B tokenizer
preflight covers all 89296 original+delta requests, zero errors or over-budget
requests, at planned 32768 context including 8192 output tokens; no truncation or
Mistral regex fix. Native template thinking is enabled. Live endpoint validation
and semantic review remain pending, and a few still-running retries need a final
delta. See the focused CPU-packet report for paths and caveats. Tests passed
25/25. No GPU/server lifecycle action or publication occurred.

Finalization: the exact remaining26B retry failed naturally on attempt4 (length),
without reset. Held-source generation is now quiescent: 75216 done, 37 failed,
10659 authorized deferred, zero pending/running. Tesla's sealed receipt is
`data/dfm13/wave4/fars-summary-deferral-20261003-v1/final-freeze-receipt.json`.
Use `fars-summary-31b-delta-final-v2` (supersedes the earlier delta) with the
original packet root. Final preflight covers all89296 audit requests, zero errors
or truncations. This is not semantic review completion or a global producer freeze.

`dfm12.fars_summary_consumer` now provides resumable review/conditional repair/
fresh-context whole-source re-audit. Its sealed root
`data/dfm13/wave4/fars-summary-31b-consumer-v1` preserves89296 candidate versions
and prior verdicts. No GPU run was launched; explicit manifest-bound owner handoff
and verified31B endpoints are required. Technical unknowns do not auto-retry or
become semantic rejects, and no result admits/exports data. See
`docs/reports/dfm13_fars_summary_31b_consumer_handoff_20261003.md` for commands,
state semantics, remaining exclusions and runtime limits.

A frozen, stratified assistant review read all sources and final answers for 20
accepted candidates: 10 repaired pn_sum, two original pn_sum, four original
wiki_sum, and four PersianQA (two repaired). Seven exact candidate versions need
publication holds: two repaired numerical/instruction fidelity errors, two
original comprehensive-summary omissions, and three original wiki_sum answers
with unsupported biographical specifics. This is not a population estimate or
native-Persian certification. All 20 candidate hashes matched live ledgers on
read-only recheck; no ledger or worker was changed.

See `docs/reports/dfm13_farsinstruct_independent20_20261003.md` and the hash-bound
`docs/reports/dfm13_farsinstruct_independent_holds_20261003.json`. The sidecar is
not automatically enforced: release owners must exclude these seven versions
pending resolution. Frozen inputs and per-row assessments are under
`data/dfm13/farsinstruct-independent20-20261003/`. Automated acceptance alone
does not supersede these independently observed source-fidelity defects.

## Active Implementation, 2026-10-03

**TLPC access recheck, 2026-10-04:** stored authenticated Hugging Face credentials
still return HTTP403 `GatedRepoError` for the selected15,888-byte payload
`wikiravan/2024-03.jsonl.gz`. Current metadata confirms the same pinned revision
`e2fea1d2c4c0828a218c79d6806fe98f821ad8ce` and a manual access gate;
the repeated current-revision payload check also failed. This confirms the prior
access blocker, not a quality rejection. Owner approval and original
**2026-10-05 superseding access update:** the owner reports access granted to
`MatinaAI/matina_persian_text_corpus`. Earlier Matina access failures below are
historical. Payload access has not been re-tested in this update; follow-up is
reserved for [post-DFM13](dfm14-potential-additions.md), not current assembly.

CC-BY-NC-SA-4.0 metadata remain intact. No Matina check, payload ingestion,
new candidate preparation, audit enqueue, or raw-continuation integration occurred.
Exact receipt: `data/dfm13/wave4/tlpc-access-20261004/receipt.json`.
The existing bounded plan covers64 shards/135,813,056bytes, not the full41B-token
corpus. After access, inspect actual formal/source-category quality and original
content boundaries before using the existing native-transform adapter; the
current plan's hashed site diversity alone does not establish high quality.

Runtime update: canonical Wikimedia text downloads for all eleven languages
are launched separately from instruction acquisition. Six instruction sources
downloaded; Matina and TLPC returned gated-repository HTTP 403 with the current
credentials. Owner approval remains valid but account access is still needed.
Rechecked later2026-10-03 with the same cached authentication that downloaded
Gemma31B: both still return authenticated payload HTTP403 `GatedRepoError`.
Matina revision `5a782d5a46f7646923644343bf8cfeac5f9c589c`; TLPC revision
`e2fea1d2c4c0828a218c79d6806fe98f821ad8ce`. Metadata/listing works, but17 Matina
content files and62,593 TLPC non-card files remain missing. No official ungated
equivalent was verified. The current downloader omits Matina's sevenZIP files;
fix explicit completeness/archive handling before post-approval resumption.
Neither source has declared train/test configurations or a wired preparation
adapter in the current Wikipedia-only transform/seed path. Exact probe evidence,
missing-file inventories, official-link checks and resume cautions:
`docs/reports/dfm13_persian_access_recheck_20261003.md` and
`data/dfm13/wave4/persian-access-recheck-20261003/`. No blind retries or server changes.

**Preparation gap superseded later2026-10-03, access still blocked:** isolated
`dfm12.wave4_persian_local` now provides explicit deterministic bounded local
ingestion into the existing four-transform/render/preflight/audit pathway.
Frozen `persian-local-v1` selects11 Matina files (1,015,840,100bytes) and64 TLPC
site shards (135,813,056bytes), not whole repositories. Missing files block before
candidate output; both sources currently have zero prepared/queued rows.
ZIP allow patterns corrected; generic downloader skips these repositories to
prevent unbounded/repeated gated downloads. Streaming archive safety and source
hash/license provenance implemented,11tests pass. Real payload/schema validation
and full-source work remain unfinished, no fabricated readiness. Bounds, candidate
allocation, limitations and commands:
`docs/reports/dfm13_persian_local_preparation_20261003.md`.
**Local-copy check, 2026-10-03:** bounded read-only DaLA/shared-cache inspection
found no verified Matina/TLPC payload: all11/64 selected paths remain absent,
with zero matches for74 available LFS hashes across1,344 dataset-cache directory
entries. Inspected DaLA Persian manifests instead reference hash-verified UD
Persian-Seraji. No network retries or new authorization requests were made;
this is not an exhaustive filesystem absence claim. Search bounds and evidence:
[local-copy investigation](../../docs/reports/dfm13_persian_local_copy_search_20261003.md).
**SL/SQ/SR spot review, 2026-10-03:** independent reading covered four accepted
rows per transform family for SL and SQ (32 total); SR's release ledger was
empty, so no pending row was counted as accepted. All32 replayed exactly from
pinned sources. Four concrete source-quality defects (missing formulas, broken
HTML/tables, garbled prose, empty continuation sections) and two separate
reordering-scope concerns are documented with exact IDs/hashes. No population
rate or broad exclusion follows; useful lists are distinguished from debris.
No live data changed. See the
[frozen review and narrow remedies](../../docs/reports/sl-sq-sr-transform-review-20261003/report.md).
**Exact four-row remedy authorized later 2026-10-03:** cases1/14/18/28 only.
Prepublication helper refused held locks; SL/SQ finished publishing, so no live
ledger status was changed. Four entry-level temporary holds protect SL/SQ
prefix/reordering until exact-ID same-repository successors pass remote hash,
new content-addressed tokenization and assembler verification. Old finalizer
guards cover only those four pairs; other tasks and the two list-scope concerns
are untouched. Original exports/reviews/arrays remain historical. See
[implementation and main/Poincare handoff](../../docs/reports/sl-sq-sr-transform-review-20261003/remedy.md)
and `exports_dfm13/sl-sq-exact4-subsets-20261003-v1/verified-handoff.json` for
completion state. Future assembly snapshots must use the corrected registry pins.
**Completed:** all four successors are uploaded, attachment/hash/token/assembler
verified and promoted; temporary holds cleared. Exactly4 rows removed,
139,038 retained,135,872,404 tokens;48 remote attachments verified. Handoff SHA256
`17849fb5af37777c5ff062fe2592118bef643d22f39bab36742c8ce3d79cc123`.
Original exports and ledger records/reviews remain unchanged;127 tests passed.
**SR availability superseded later the same day:**16 accepted examples (four per
family) are now independently read and source-replayed, completing48 across
SL/SQ/SR. Five SR exact-window/extraction/task defects are documented as findings
only; no SR exclusions or holds were applied. See
[SR follow-up](../../docs/reports/sl-sq-sr-transform-review-20261003/sr-followup/report.md).
**SR adjudication supersedes the five-case remedy suggestion, 2026-10-03:** main
independently selected only cases32/36/37/47 under the user's broad quality task.
Case45 is retained: meaningful native introduction/cast table/coherent gap;
markers or an empty heading alone are insufficient. While still unpublished,
four exact statuses changed under the component lock to `excluded_manual_review`
with append-only original-record/model-review/hash/authority evidence. Accepted
count254,271;22 retries still pending, export not ready. All16 sampled records
and model reviews remain unchanged; no SL/SQ artifact was repinned. See
[adjudication and applied proof](../../docs/reports/sl-sq-sr-transform-review-20261003/sr-followup/adjudication.md).
**SR finalization supersedes pending state later 2026-10-03:** the22 retries
were already terminal (17 accepted,4 rejected,1 exhausted length-output failure
excluded under existing policy). Existing finalizer preserved all4 manual
exclusions and published all4 tasks; existing CPU tokenizer completed254,288 rows,
251,293,446 tokens. All4 exact IDs are absent, case45 retained unchanged. Subsequent
metadata-only same-repo commits attach hash-bound manual evidence without changing
data/token arrays; all4 entries passed full assembler verification.137 tests pass.
Current main/Poincare receipt SHA256:
`b72410d3ba2def6e63bca3544bd313db9cbdea37efef502eea295e5c0fce204e`.
See [terminal report and current pins](../../docs/reports/sl-sq-sr-transform-review-20261003/sr-followup/finalization/report.md).
The first 455 Croatian canonical conversations passed native-template preflight
and were queued, not accepted. `dfm12.wave4_instructions` prepares canonical
train-only sources; format mirrors and Aya test/demographic files are excluded.
`dfm12.baltic_calibration` is running the existing 120 prepared Baltic synthetic
requests on the shared servers, with independent reviewer requests. Calibration
failures are saved and bulk approval is not manufactured automatically.

Operational finding: the first Baltic constrained-grammar calibration coincided
with all eight engines retaining roughly 400 active requests but near-zero
decode throughput. Stopping only calibration and its diagnostic request restored
100% GPU utilization and thousands of audit completions; servers were not
restarted. Treat expensive per-example grammar constraints as a suspected cause,
not a proven engine defect. A separate 12-example JSON-object calibration retains
the same strict post-generation and reviewer validation before any production
decision. Wave-four audits use the existing simple audit contract at 64 requests
per server alongside the Baltic 384/server client.

Further implementation evidence:

- `wave4_transforms` samples documents across complete native Wikipedia releases,
  builds all four families with native instructions, preserves original paragraph
  boundaries, records shortfalls, and queues only template-preflighted candidates.
- `wave4_seeds` builds unique-document synthetic grounding pools and reuses the
  already-modernized English OpenHermes seed selection, never raw OpenHermes.
- Aya's Albanian slice uses `als` (Tosk Albanian), not `sqi`: 120 train rows were
  found. The zero-row `sqi` receipt remains historical; the `-tosk` component
  makes the corrected selection explicit without mutating sealed audit inputs.
- `scripts.monitor_dfm13_wave_campaign` samples GPU/KV/request counters every
  120 seconds and restarts only an absent wave-four audit client when pending
  audit jobs exist. It never terminates servers or unrelated processes.
- `wave_repair` creates separate repair and fresh audit jobs for rejected
  instruction candidates. Nonassistant turns cannot change, no new tools can
  be invented, and unchanged repairs cannot pass. Translation/transformation
  rejections are not blindly rewritten without authoritative source evidence.
  Initial Croatian component: 439 original audit keeps and 16 repair candidates.
  No wave-four dataset has yet been published or registered as accepted.
- Removing string-length grammar constraints restored output throughput but did
  not establish Baltic generation quality: the first 12-example schema pilot
  had only four keeps. A second, separately preserved 24-example prompt/JSON
  calibration is under assessment. Do not approve bulk solely because outputs
  parse; native language and grounded correctness remain gates.

The owner now authorizes completing both Baltic wave 3 and wave 4 through
preparation, synthetic generation, audit, warranted repair/re-audit, accepted-only
export, HF upload and DFM13 integration. No final sampling is implied.
`dfm12.wave4_cpu` starts resumable pinned downloads and direct OPUS preparation
for 308 new pairs across 34 variants. Runtime root: `data/dfm13/wave4`;
logs: `logs/dfm13/wave4/{downloads,parallel}.log`. The separate transactional
`audit/jobs.sqlite` queue receives native-template-preflighted direct candidates.
This initial implementation does not yet complete transformations, instruction
conversion, institutional-source expansion, pivots or synthetic generation.
The research-stage non-launch statements below describe the earlier stage,
not a restriction on this newly authorized implementation.

Scope: sq, be, bs, bg, hr, hu, lb, sr, sk, sl and fa. See the
[wave history and common recipe](language-extension-waves.md). This is source
research, not approval of a final mixture or a claim that downloads, audits,
tokenization or sampling have run.

## Decisions and Evidence

- Prefer curated parallel data; do not fill quotas with CCMatrix/CCAligned or
  other web-mined pairs merely because they are large.
- **Owner decision, 2026-10-03:** Matina and TLPC are acceptable for this
  project. This supersedes the initial proposed license hold. Preserve their
  published CC-BY-NC-ND-4.0 and CC-BY-NC-SA-4.0 metadata respectively; the
  decision does not relabel either as unrestricted CC-BY or authorize changing
  their upstream metadata. Gated access and quality filtering still apply.
- MIZAN's OPUS page explicitly identifies CC-BY-4.0. This resolves the earlier
  unverified-license status in the Baltic source discussion.
- Counts below are source/API observations, not audited yield, native Gemma
  token counts or additive totals. Pin revisions before implementation.

## Parallel Supply

Checked English-pair availability through the [OPUS API](https://opus.nlpl.eu/opusapi/)
using `source=en&target=<code>&preprocessing=moses&version=latest`.
Alignment counts can include duplicates and many-to-many segments.

| Language | Strong direct English candidates and raw alignments | Assessment |
|---|---|---|
| Albanian | SETIMES 227,516; GlobalVoices 6,078; Tatoeba 1,104 | Substantial curated starting pool; news-heavy, diversify |
| Belarusian | Tatoeba 7,061; translatewiki 24,240 | Thin under the preferred quality/rights policy; localized UI is not general prose |
| Bosnian | SETIMES 138,387; Tatoeba 535 | Meaningful first tranche, avoid conflating Serbian/Croatian variants |
| Bulgarian | DGT 4,318,892; Europarl 408,290; SETIMES 213,160 | Ample raw supply; cap legal and institutional repetition |
| Croatian | DGT 1,416,461; SETIMES 205,910 | Ample raw supply; audit register and alignment |
| Hungarian | DGT 5,799,885; Europarl 625,178; GlobalVoices 15,362; Tatoeba 125,793 | Ample and somewhat more diverse supply |
| Luxembourgish | translatewiki 51,762; Tatoeba 420 | Very limited broad prose; smaller honest target or additional sources needed |
| Serbian | SETIMES 225,169; GlobalVoices 20,309; Tatoeba 22,596 | Substantial starting pool; retain script labels |
| Slovak | DGT 5,799,714; Europarl 639,958; JRC-Acquis 35,744 | Ample but institutional-heavy |
| Slovenian | DGT 5,801,309; Europarl 624,803; JRC-Acquis 53,390 | Ample but institutional-heavy |
| Persian | MIZAN 1,021,597; GlobalVoices 10,321 | Strong first tranche from literary parallel data; audit older register and alignment |

**Sufficiency:** nine languages have substantial curated candidate pools;
Belarusian and Luxembourgish do not yet have a demonstrated broad, large
approved pool. None of these raw counts promises the existing sampling quota
after deduplication and audit. Discover all cross-language pairs next, using
the established 0.25/0.0625 allocation rule and provenance-preserving English
pivots, not a blanket equal-sized Cartesian product.

### Corpus Gates

- [SETIMES](https://opus.nlpl.eu/legacy/SETIMES.php): CC-BY-SA declaration,
  editorial Balkan news. Preferred for sq/bs/bg/hr/sr; retain attribution.
- [MIZAN](https://opus.nlpl.eu/legacy/MIZAN.php): CC-BY-4.0 declaration;
  prioritize Persian. Preserve book/document identity for splitting.
- [DGT](https://opus.nlpl.eu/legacy/DGT.php), Europarl and
  [JRC-Acquis](https://joint-research-centre.ec.europa.eu/language-technology-resources/jrc-acquis_en):
  useful curated institutional translations; pin release-specific reuse terms,
  deduplicate recurring legal clauses, and cap domain share.
- [GlobalVoices](https://opus.nlpl.eu/legacy/GlobalVoices.php), Tatoeba and
  translatewiki: verify release terms and attribution; cap very short strings
  and preserve localization placeholders. Do not import benchmark holdouts.
- [TEP](https://opus.nlpl.eu/legacy/TEP.php) has 612,086 Persian alignments but
  describes research/non-commercial use, not unrestricted CC-BY. Separate
  permission decision needed. TED/QED also require source-specific terms;
  they are not approved merely because OPUS distributes them.
- TICO-19 is evaluation-oriented; exclude from the training shortlist.
- [LuxAlign](https://huggingface.co/datasets/fredxlpy/LuxAlign) offers about
  43.4K lb-en pairs but declares CC-BY-NC-4.0: permission hold. Investigate the
  [Luxembourg government parallel corpus](https://data.public.lu/en/datasets/meisproochegen-iwwersetzungskorpus-fir-dletzebuergescht/)
  separately; its roughly 150K source words must not be reported as 150K pairs.
- A [Belarusian parallel-data study](https://aclanthology.org/2025.acl-long.25/)
  found substantial noise in small samples of mined corpora. Its rates are not
  universal current quality estimates, but support not treating mined volume
  as sufficient usable supply.

## Text and Instruction Shortlist

For every language, inspect native configurations of
[wikimedia/wikipedia](https://huggingface.co/datasets/wikimedia/wikipedia)
and suitable Wikisource texts, retaining article/revision provenance and
paragraphs. [Common Corpus](https://huggingface.co/datasets/PleIAs/common_corpus)
is a source-filtered fallback, not Common Pile and not proof of abundant data
in every language. Review OCR and modern-language suitability. Use native
[ParlaMint](https://github.com/clarin-eric/ParlaMint) releases where available;
its English machine translations are not human parallel gold. Historical
[ELTeC](https://github.com/COST-ELTeC) releases are supplementary, not modern
instruction answers. Verify actual language release coverage before download.

| Language | Additional text priorities | Instruction/chat candidates and gates |
|---|---|---|
| Albanian | Native Wikipedia/Wikisource; selected public editorial sources | [alban-labs/Kapibara](https://huggingface.co/datasets/alban-labs/Kapibara), about 5.3K conversations, Apache-2.0 card; inspect English contamination and inherited identity. Aya `sqi` train slice |
| Belarusian | Native reference/literary text, careful standard/orthography separation | No large permissive native chat source verified. `saillab/alpaca-belarusian-cleaned` is translated Alpaca with NC terms: hold. Prioritize native-grounded synthetic conversations |
| Bosnian | Native parliamentary/reference documents | `saillab/alpaca-bosnian-cleaned` has NC terms; not default. Native synthesis and explicit Bosnian labels needed |
| Bulgarian | Native parliamentary/reference text; investigate CURLICAT/MARCELL source releases | EuroBlocks Bulgarian slice after inherited-source dedup; translated Alpaca is not automatically licensed or high quality. No verified public BgGPT training-data release assumed |
| Croatian | Native ParlaMint/reference text | [administraktor/hrvatski-dataset-v2](https://huggingface.co/datasets/administraktor/hrvatski-dataset-v2), 455 canonical examples, Apache-2.0 card; format copies are not extra examples. EuroBlocks Croatian slice |
| Hungarian | Native parliamentary/reference and selected literature | EuroBlocks and Aya `hun`. [SZTAKI-HLT/HunSum-1](https://huggingface.co/datasets/SZTAKI-HLT/HunSum-1) has about 1.14M train examples but NC-SA terms: separate approval needed |
| Luxembourgish | [Decima-Data/luxembourgish-parliamentary-corpus](https://huggingface.co/datasets/Decima-Data/luxembourgish-parliamentary-corpus), roughly 5.22M Luxembourgish words; multilingual portions must be separated and `other` license reviewed | [jvalline/LuxIT_wiki_subset](https://huggingface.co/datasets/jvalline/LuxIT_wiki_subset), CC-BY-SA card, inspect actual subset/schema. [fredxlpy/LuxInstruct](https://huggingface.co/datasets/fredxlpy/LuxInstruct), about 400K rows, NC license: hold |
| Serbian | Native parliamentary/reference text, both scripts explicitly labeled | Aya `srp`; [datatab/ultrachat_200k_serbian](https://huggingface.co/datasets/datatab/ultrachat_200k_serbian), about 207.6K, promising but translation provenance/license unresolved. Do not blindly admit translated OpenOrca/FLAN |
| Slovak | Native parliamentary/reference text | EuroBlocks. [mbenco/slovak-sft](https://huggingface.co/datasets/mbenco/slovak-sft), about 30K train rows: CC-BY card conflicts with NC Alpaca ancestry; hold until resolved, review SKQuAD splits |
| Slovenian | Native parliamentary/reference/literary text | EuroBlocks. [cjvt/GaMS-Instruct](https://huggingface.co/datasets/cjvt/GaMS-Instruct) is gated/NC: approval needed; inspect separately released GaMS synthetic subsets rather than assuming identical terms |
| Persian | Approved Matina/TLPC; native Wikipedia; selected news and culture sources below | Selective FarsInstruct, Aya `pes`, PerSpellData; native synthetic conversations for missing conversational/tool/reasoning breadth |

[CohereLabs/aya_dataset](https://huggingface.co/datasets/CohereLabs/aya_dataset)
contains relevant human-annotated sq/hu/sr/fa slices; measure actual train counts.
Do not replace it with the much broader benchmark-heavy Aya Collection.
[utter-project/EuroBlocks-SFT-2512](https://huggingface.co/datasets/utter-project/EuroBlocks-SFT-2512)
is already partly inherited: admit only new language/source IDs, verify actual
assistant language, and deduplicate against `dfm12-euroblocks`. By contrast,
the currently inspected EU-Instruct-Synthetic language list does not cover
these eleven languages. No wave-4 DynaWord/DynaInstruct release was verified
in this research; do not invent analogous repository names.

## Persian Pointers: Disposition

### Additional parallel candidates (2026-10-03)

The user suggested [shenasa/English-Persian-Parallel-Dataset](https://huggingface.co/datasets/shenasa/English-Persian-Parallel-Dataset)
and [persiannlp/parsinlu_translation_en_fa](https://huggingface.co/datasets/persiannlp/parsinlu_translation_en_fa).
These are candidates, not admitted sources. Shenasa lists 3,960,172 rows and MIT;
its preview contains subtitle-like fragments and clear literal mistranslations
(ship bow rendered as bowing), so sample/alignment audit and upstream provenance
review are necessary. The displayed CSV columns also appear to be a data pair
used as headers; inspect raw CSV before conversion.

ParsinLU lists about 1.62M training examples, separate dev/test splits and
CC-BY-NC-SA-4.0, confirmed by its loader. This is outside the current permissive
parallel-source policy. The preview contains GlobalVoices sentence misalignments;
do not treat the entire benchmark collection as high-quality parallel gold or
count it as wholly new supply. Review upstream component licenses and overlap
with existing OPUS selections before any inclusion. No automatic download,
GPU audit or training integration was authorized by this assessment alone.

| Source | Intended use and remaining checks |
|---|---|
| [SLPL/naab](https://huggingface.co/datasets/SLPL/naab) | About 130GB / 250M paragraphs / 15B words reported, not native tokenizer tokens. Mixed crawl/social constituents overlap other leads; source-select and deduplicate. Shuffled paragraphs cannot supply original paragraph order. Resolve card/body license ambiguity |
| [MatinaAI/matina_persian_text_corpus](https://huggingface.co/datasets/MatinaAI/matina_persian_text_corpus) | Owner-approved; upstream reports 72.9B tokens. Prioritize a domain-balanced, high-quality subset as transformation seeds. Preserve NC-ND metadata; access gate and document structure still need inspection |
| [Targoman/TLPC](https://huggingface.co/datasets/Targoman/TLPC) | Owner-approved; upstream reports over 41B tokens and 75M documents. Preserved paragraph/document metadata makes this particularly promising for all four transformations. Filter by formal/informal and source category, retain NC-SA metadata |
| [codersan/Persian-Wikipedia-Corpus](https://huggingface.co/datasets/codersan/Persian-Wikipedia-Corpus) | About 1.16M rows, not necessarily useful articles. Filter namespace, redirects, disambiguation and boilerplate; resolve mirror attribution or use canonical Wikimedia release |
| [Culture_Neurons data/fa](https://github.com/namazifard/Culture_Neurons/tree/main/data/fa) | Cultural/figurative seed candidate. Inspect actual files and rights; do not confuse multilingual project totals with Persian size or ingest research evaluation material unexamined |
| [MirasText](https://github.com/miras-tech/MirasText/tree/master/MirasText) | News text candidate; verify source permissions and size units rather than carrying forward the supplied 1.4M-word estimate. Preserve dates, article identity and dedup keys |
| [persiannlp/persian-raw-text](https://github.com/persiannlp/persian-raw-text) | Aggregation of crawl, MirasText, Wikipedia and other sources; explicitly not deduplicated. Secondary fallback, not additive to its components |
| [OSCAR-2301](https://huggingface.co/datasets/oscar-corpus/OSCAR-2301) | Broad crawl fallback only. Supplied 93.2GB Persian size not independently validated here; source-quality filtering needed |
| [uonlp/CulturaX](https://huggingface.co/datasets/uonlp/CulturaX) | Crawl-derived fallback overlapping OSCAR/mC4. Supplied 45B Persian-token figure not independently validated here; do not sum it with overlapping corpora |
| [RohanAiLab/persian_daily_news](https://huggingface.co/datasets/RohanAiLab/persian_daily_news) | About 1.98M rows with summaries; inspect rights, summary faithfulness and copied leads. Promising summarization seed, not verified gold automatically |
| [mostafaamiri/Persian_instruct_dataset](https://github.com/mostafaamiri/Persian_instruct_dataset) | Instruction seed repository; inspect scale, provenance and rights before treating it as ready large-scale chat |
| [ParsiAI/FarsInstruct](https://huggingface.co/datasets/ParsiAI/FarsInstruct) | About 9.37M train template instances, not unique conversations. Select native useful train tasks, deduplicate underlying examples and review inherited P3/benchmark sources; about 6M entries are directional translation templates. Apache card does not replace upstream source checks |
| [rominaoji/PerSpellData](https://github.com/rominaoji/PerSpellData) | About 6.4M noisy-clean pairs reported, MIT repository. Useful spelling supplement, not full grammatical correction. Split by clean sentence and validate synthetic mutations; preserve Persian half-spaces |
| [sbunlp/hmblogs-v3](https://huggingface.co/datasets/sbunlp/hmblogs-v3) | About 16.9M rows; colloquial supplement after null/boilerplate/PII filtering and rights review, not primary formal-language material |
| Unspecified 30K-conversation link | [xmanii/Maux-Persian-SFT-30k](https://huggingface.co/datasets/xmanii/Maux-Persian-SFT-30k) is a plausible match, not confirmed as the intended source; inspect license and actual conversations |
| Two unspecified grammar/spelling links | Unresolved: ellipsis URLs cannot be treated as identified or approved sources |

Published token counts use upstream tokenization and cannot establish DFM
epoch contributions. Estimate with our tokenizer only after candidate selection.
Matina/TLPC approval is not a blanket approval of unrelated NC datasets.

## Implementation Sequence, Not Yet Launched

1. Pin repository/config/revision, actual train splits, rights metadata and
   source overlap. Confirm gated access to Matina/TLPC and inspect samples.
2. Discover all direct pairs with the 23 existing variants and within wave 4;
   preserve direct-versus-pivot provenance and report shortages explicitly.
3. Deduplicate documents across Persian aggregations before broad stratified
   sampling. Retain source structure for genuine reordering tasks.
4. Build the four transformations and convert approved instruction sources
   to structured Gemma 4 messages. Do not inject external template tokens.
5. Assign each language a synthetic instruction target: **35K accepted
   conversations** for sufficient existing instruction volume and breadth,
   **70K** for scarce or narrow supply. Record the evidence for the tier;
   uncertain candidate availability must not count as usable coverage.
   Calibrate native-language generation/review per language before bulk;
   distinguish errors from legitimate orthographic/script variants. Persian
   requires controlled Arabic/Persian Yeh/Kaf handling and ZWNJ preservation;
   Belarusian needs Russian contamination checks; Serbian needs script tags.
6. Audit language, instruction/answer coherence and usefulness; track accepted,
   repaired, rejected and infrastructure-failed rows separately. Preserve
   document-level splits and source IDs across translated/template siblings.
7. Consume separately curated DaLA training outputs when available; do not
   duplicate that workstream. Tokenize accepted material and measure actual
   row/token/domain balance before proposing repeats and final sampling.

### Repair handoff monitoring (2026-10-03)

Moved to [operational history](fourth-wave-operational-history.md#repair-handoff-monitoring-2026-10-03).

### 2026-10-03 Continued campaign checks

Moved to [operational history](fourth-wave-operational-history.md#2026-10-03-continued-campaign-checks).

### Translation continuation and exhausted outputs (2026-10-03)

Moved to [operational history](fourth-wave-operational-history.md#translation-continuation-and-exhausted-outputs-2026-10-03).

### Baltic instruction release continuation

Moved to [operational history](fourth-wave-operational-history.md#baltic-instruction-release-continuation).

### Accepted translation selection

Moved to [operational history](fourth-wave-operational-history.md#accepted-translation-selection).

### Synthetic false-accept control set

Moved to [operational history](fourth-wave-operational-history.md#synthetic-false-accept-control-set).

### Automatic selection follow-up (2026-10-03)

Moved to [operational history](fourth-wave-operational-history.md#automatic-selection-follow-up-2026-10-03).

### Accepted release tokenization

Moved to [operational history](fourth-wave-operational-history.md#accepted-release-tokenization).

### Repair terminal-state correction

Moved to [operational history](fourth-wave-operational-history.md#repair-terminal-state-correction).

### Baltic transformation publication

Moved to [operational history](fourth-wave-operational-history.md#baltic-transformation-publication).

### Wave-4 translation release handoff

Moved to [operational history](fourth-wave-operational-history.md#wave-4-translation-release-handoff).

### Baltic EuroBlocks release adapter

Moved to [operational history](fourth-wave-operational-history.md#baltic-euroblocks-release-adapter).

### Synthetic control repair experiment

Moved to [operational history](fourth-wave-operational-history.md#synthetic-control-repair-experiment).

### Lithuanian QA metadata correction

Moved to [operational history](fourth-wave-operational-history.md#lithuanian-qa-metadata-correction).

### Native synthetic seed allocation

Moved to [operational history](fourth-wave-operational-history.md#native-synthetic-seed-allocation).

### Expanded production-path calibration

Moved to [operational history](fourth-wave-operational-history.md#expanded-production-path-calibration).

### W3/W4 Inventory Completion Check

The 2026-10-03 19:13 UTC metadata audit distinguishes two access-blocked Persian
sources (Matina/TLPC, zero prepared rows) from four prepared but unpublished W3
rights/release items (Europarl LT/LV and FinePDF LT/LV,220,453 audit-ready rows).
No dedicated live publisher covers those four. Aya Albanian's historical zero-row
alias is superseded by120 Tosk candidates/113 published rows. BLKT genuinely has
zero reordering supply, while its other three tasks are published. All43 W3
translation pairs have published entries; W4 has275/308 base pairs with supply,
and its live Slovak addition leaves only ca-sk,fo-sk,nn-sk without prepared supply.
QA/P3/Fars and synthetic quality work remains explicitly staged, not complete.
Counts, source-specific disposition, live owners and metadata-only evidence:
[completion audit](../../docs/reports/w3-w4-source-completion-20261003/report.md).

### Failed Audit Disposition Details

On 2026-10-03, a read-only rolling snapshot found 14,625 failed primary audit
jobs: 9,040 length stops, 5,584 JSON parse failures, one invalid-score schema
failure, and no explicit infrastructure-error signatures. Primary failures
persist after recovery: 339 already had accepted/accepted_repair ledger states.
The 13,344 without release ledgers span 68 direct-translation components, all
covered by the frozen manifest and requested selection pairs. All 369 pending
recovery ledger pointers already referenced terminal jobs, indicating pending
reconciliation rather than a reason for blind retry. Selection and repair-audit
clients were live. Another 251 ledger rows were busy and deliberately left
unknown. No queues or GPU processes were changed; no recoverable infrastructure
orphan was established. See the [counts, exact examples, retry contract and
limitations](../../docs/reports/wave4-failed-audit-disposition-20261003/report.md).

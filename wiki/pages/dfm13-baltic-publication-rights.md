---
type: Research
title: DFM13 Baltic Publication Rights
description: Pinned constituent rights, Lithuanian license partitions and privacy gates for Baltic publication.
status: draft
confidence: medium
last_updated: 2026-10-03
tags: [dfm13, baltic, licensing, provenance, privacy]
---
# DFM13 Baltic Publication Rights

## Synthetic Publication Packets (2026-10-04)

Later2026-10-04 scoped supersession: the official-per-sitting-fetch gate below
was stricter than the primary notice's actual source-link condition. A separate
six-package v2 supplies complete-sitting/archive-member attribution under the
captured reuse notice, without a new CC license or changing original data.
See [scoped resolution](../../docs/reports/baltic-europarl-scoped-reuse-resolution-20261004.md).
The v2 `handoff.json` is the terminal receipt; prior v1 flags remain historical.
This does not release unrelated corrupted-text transformations.
CPU process3488968 completed successfully: all six v2 packets are verified and
upload-ready,90,000 unchanged conversations including30,528 source-bound Europarl
rows.11tests passed. Tesla owns publication; no upload was performed here.

Eight external metadata/attribution packages were prepared without touching
sealed Baltic payloads or integration pins:
`exports_dfm13/baltic-source-attribution-20261004-v1/handoff.json`.
Both user-authorized OpenHermes packages (15K LT +15K LV) are ready for Tesla's
publication. No blanket source license was invented. The remaining six packages
preserve all90K rows and complete row/source bindings, but30,528 Europarl-derived
rows retain the documented item-attribution/scope evidence gap; no false full
readiness claim. Wikipedia terms and original source IDs are retained.
Seven tests passed; no GPU or uploads. See the
[exact handoff and source counts](../../docs/reports/baltic-synthetic-publication-attribution-20261004.md).

## Scope and Disposition

This 2026-10-03 review refines the pending-rights diagnoses in the
[Baltic source plan](dfm13-baltic-language-sources.md). It does **not** clear
publication holds or change any pipeline. Explicit owner inclusion resolves
project source selection, not upstream redistribution conditions. A positive
model audit is neither a rights clearance nor a privacy assessment.

In particular, the Lithuanian NewGenLTU licenses contain an **express conditional
redistribution grant**. Treating them simply as missing permission is superseded
by the conditions below. The existing operational holds remain until compliance
evidence and scoped export handling exist. Inspected text and local counts are
evidence; legal applicability and unresolved upstream scope are not certified.

## Pinned Evidence

Paths below are relative to the repository root. Source selection is recorded
in `config/dfm13_baltic_sources.json`.

| Source | Pinned revision | Local evidence | Existing hold |
| --- | --- | --- | --- |
| `matiss/P3-Latvian-translategemma-27b` | `f8d6ecba6fa51521db139c57de9b21870eed9b33` | `data/dfm13/baltic/p3/download/README.md`, `selection.json` and `receipt.json` under `data/dfm13/baltic/p3/` | `constituent_rights_review_before_export` |
| `VSSA-SDSA/LT_AI_BLKT` | `4fa6c3894fd9f1f9f8db773ae844e126fa61f61d` | `data/dfm13/baltic/downloads/baltic_lt_blkt/{README.md,LICENSE.txt}`; `data/dfm13/baltic/receipts/baltic_lt_blkt.json` | `custom_terms_and_source_stratification` |
| `VytautoDidziojoUniversitetas/LT_Summarisation_Corpus` | `42ff26844cd2b3d26880f631ab498da1568cda15` | `data/dfm13/baltic/downloads/baltic_lt_summary/{README.md,LICENSE.txt}`; `data/dfm13/baltic/receipts/baltic_lt_summary-converted.json` | `custom_terms_and_medical_privacy_review` |

Primary pinned cards: [translated P3](https://huggingface.co/datasets/matiss/P3-Latvian-translategemma-27b/blob/f8d6ecba6fa51521db139c57de9b21870eed9b33/README.md),
[BLKT](https://huggingface.co/datasets/VSSA-SDSA/LT_AI_BLKT/blob/4fa6c3894fd9f1f9f8db773ae844e126fa61f61d/README.md),
[LT summaries](https://huggingface.co/datasets/VytautoDidziojoUniversitetas/LT_Summarisation_Corpus/blob/42ff26844cd2b3d26880f631ab498da1568cda15/README.md).
The P3 card has no blanket `license` value. Upstream rights references below
were inspected on 2026-10-03; unlike the translated selection, their current
web pages are not locally revision-pinned legal archives.

## Latvian P3 Constituents

Exactly eight train configurations were selected, one canonical template per
source. Incorrect rank-expanded targets were rejected. Preparation recorded
20,256 input rows, 52 duplicates and 20,204 candidates; these are **not** current
accepted-export counts. Candidate SHA256:
`d2b54b14cd5209b2ec3cf3d468d1b44c52c9a3ce4ccb12d24180c868aa427e6c`.

| Selected configuration | Candidates | Explicit evidence and publication consequence |
| --- | ---: | --- |
| `ai2_arc_ARC_Challenge_pick_the_most_correct_option` | 1,118 | Publisher declares CC BY-SA 4.0. Preserve attribution, license, modification/translation notice and applicable ShareAlike; no additional restrictions. |
| `ai2_arc_ARC_Easy_pick_the_most_correct_option` | 2,251 | Same ARC terms. |
| `glue_mrpc_generate_paraphrase` | 2,472 | MSR-SSLA permits noncommercial redistribution, including derivatives, under the same terms. Commercial use/distribution is restricted. |
| `openbookqa_main_choices` | 4,952 | Dataset grant unresolved: publisher card says `unknown`; code Apache-2.0 is not proof of the separately hosted data's license. |
| `quarel_heres_a_story` | 1,941 | Original archive has no license/readme. A primary publisher grant was not established. Third-party CC assertions are insufficient. |
| `quartz_use_info_from_question_paragraph` | 2,696 | Publisher declares CC BY 4.0: attribution, license link and changes notice; no additional restrictions. |
| `web_questions_question_answer` | 3,736 | Stanford explicitly releases WebQuestions under CC BY 4.0. Do not substitute the SEMPRE code license. |
| `wiki_qa_Direct_Answer_to_Question` | 1,038 | Microsoft Research Data License permits research/technology-development use and distribution subject to its terms; direct commercial-product use requires Microsoft permission. |

Each selected path is `<configuration>/train-00000-of-00001.parquet` in
`selection.json`. Train-only selection does not itself establish rights or
benchmark independence.

Primary evidence and specific obligations:

- ARC: [publisher card](https://huggingface.co/datasets/allenai/ai2_arc) and
  [CC BY-SA 4.0 terms](https://creativecommons.org/licenses/by-sa/4.0/).
- QuaRTz: [publisher card](https://huggingface.co/datasets/allenai/quartz/raw/main/README.md).
  WebQuestions: [Stanford's data release](https://nlp.stanford.edu/software/sempre/).
  Both reference [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- MRPC: [Microsoft download page](https://www.microsoft.com/en-us/download/details.aspx?id=52398)
  and [official MSI containing MSR-SSLA](https://download.microsoft.com/download/d/4/6/d46ff87a-f6b9-4252-aa8b-3604ed519838/MSRParaphraseCorpus.msi).
  The embedded agreement was read without installing the MSI. It requires
  downstream same-term licensing, retained notices, prominent change notices
  **with dates**, warranty/liability disclaimers, and includes a grantback to
  Microsoft. Noncommercial redistribution is expressly possible; owner
  inclusion cannot waive the commercial restriction.
- WikiQA: [publisher's full license](https://huggingface.co/datasets/microsoft/wiki_qa/raw/main/README.md),
  [Microsoft download page](https://www.microsoft.com/en-us/download/details.aspx?id=52419),
  and [official archive](https://download.microsoft.com/download/e/5/f/e5fcfcee-7005-4814-853d-daa7c66507e0/WikiQACorpus.zip).
  `WikiQACorpus/LICENSE.pdf` was inspected and agrees with the publisher card.
  Preserve same terms, notices, dated modifications and no-endorsement terms;
  the agreement also contains a grantback and export conditions. Do not equate
  this research/technology-development scope with MRPC's wording or assume
  Wikipedia's license replaces it. The interaction of its transfer restriction
  with express distribution clauses warrants clarification if material to the
  proposed release.
- OpenBookQA: [publisher card](https://huggingface.co/datasets/allenai/openbookqa/raw/main/README.md),
  [code license](https://raw.githubusercontent.com/allenai/OpenBookQA/master/LICENSE),
  [repository README](https://raw.githubusercontent.com/allenai/OpenBookQA/master/README.md),
  [original data archive](https://s3-us-west-2.amazonaws.com/ai2-website/data/OpenBookQA-V1-Sep2018.zip).
  The archive contains data but no license/readme. Obtain publisher evidence
  covering data before clearing this uncertainty; absence is not a finding
  that redistribution is prohibited.
- QuaRel: [original data archive](https://s3-us-west-2.amazonaws.com/ai2-website/data/quarel-dataset-v1-nov2018.zip)
  contains train/dev/test JSON and JSONL without licensing text. Publisher
  grant remains unverified, rather than assumed CC BY from secondary tables.

## Lithuanian Conditional Grants

Both pinned licenses are NewGenLTU Open RAIL-D v1.0, dated `1/4/2026`:
[BLKT license](https://huggingface.co/datasets/VSSA-SDSA/LT_AI_BLKT/blob/4fa6c3894fd9f1f9f8db773ae844e126fa61f61d/LICENSE.txt)
and [summary license](https://huggingface.co/datasets/VytautoDidziojoUniversitetas/LT_Summarisation_Corpus/blob/42ff26844cd2b3d26880f631ab498da1568cda15/LICENSE.txt).
Local SHA256 values are respectively
`a8c692dbecb19e4822165afaa118247341067133156cfadd6668047b2ae55008`
and `d492ba6dacd136b822e2e19d0e6665e29c56a596c1fba86b49eed29bca5c2022`.
The substantive text matches; encoding/BOM and line endings differ.

- Section 2 grants access, reproduction, use, modification, annotation, display
  and distribution. Cleaned, filtered and reformatted data are derivatives.
- Sections 3 and 5(i) require Attachment A use restrictions to be passed to
  downstream recipients as enforceable conditions, with notice.
- Sections 5(ii)-(iv) require a full license copy, prominent modification
  notices and retained copyright/patent/trademark/attribution notices.
- Section 5(v) limits use to model training, language-technology development
  or producing model-training datasets. This is not unrestricted Apache/CC,
  but neither is it a blanket noncommercial license.
- Section 4 does not claim rights in model outputs, but output use must not
  contravene the license. Attachment A covers harmful uses, privacy, medical
  decisions and other restrictions. A4 includes disclosure conditions for
  autonomous interaction and publicly disseminated generated content.
- A6 restricts medical advice/clinical decision use with stated research and
  professional-oversight exceptions; medical source material is not itself
  a blanket training prohibition. A10 forbids personal-data extraction and
  requires adequate limitations preventing trained models from outputting
  personal information from the artifact.

These are concrete packaging/use safeguards, not a request for a new blanket
owner approval. This review does not infer that all model weights automatically
must be relicensed as Open RAIL-D or certify that model-level safeguards exist.

### BLKT Row-Level Separation

The card describes 36 sources acquired through permissions, licenses or other
lawful grounds; that is a publisher assertion, not an independent warranty.
All 25 selected-window JSONL files under
`data/dfm13/baltic/text-windows/baltic_lt_blkt/` were counted:

| Exact row `provenance.license` | Selected windows |
| --- | ---: |
| `NewGenLTU OpenRAIL-D` | 58,199 |
| `CC BY-SA 4.0` | 1,801 |

The latter have source name `Vikipedija`. These 60,000 are selected windows,
not final accepted rows or the full upstream corpus. `dfm12/baltic_transforms.py`
preserves source file/hash, row, document ID, URL, license, source name/ID and
document type. Do not overwrite this with a single card-level `openrail` label.
Applying Open RAIL restrictions to CC BY-SA adaptations risks its prohibition
on additional restrictions. Separate license scopes; if the intended interaction
of collection and row terms remains ambiguous, obtain publisher clarification
for that partition rather than silently resolving it in the exporter.

### Summary Privacy Evidence

`data/dfm13/baltic/audit-candidates/baltic_lt_summary.jsonl` contains 2,240
converted train candidates across IT, law, medicine and media. Card counts are
inconsistent; use the conversion receipt, not the card total. No test split was
imported. Provenance retains the pinned repository/revision, CSV path/hash and
row ordinal. The card describes medical material as anonymized State Data
Agency pharmacy documents/doctor diagnoses. This is **not** evidence that our
selected prompts and repaired outputs passed a privacy screen.

## Minimal Proposed Code Paths

The publisher integration below remains proposed, not publication approval.
The isolated BLKT preparation implementation is recorded next; it does not
change existing publishers or clear their holds.

### Implemented Local Preparation, 2026-10-03

`dfm12/blkt_export.py` implements accepted-only task/license partition preparation
without uploads, registry changes or live worker edits. It requires an existing,
completed `release/transform-baltic_lt_blkt/` ledger and obtains its existing
lock nonblocking. Read-only SQLite population must match the sealed candidate
IDs/counts and completion receipt. Unknown, pending and failed states fail
closed; rejected and explicitly excluded rows are not exported.

The source receipt, NewGenLTU license and official CC legal text have explicit
code pins. Referenced Parquet files are hashed, and original row ordinal,
license, URL, source/document IDs and source name are checked. Original title,
author, date and source-file attribution are recovered rather than discarded.
Each nonempty `(task, license)` package has data, exact license text, dated
modification notice, attribution JSONL and hash manifest. Messages are retained,
without retokenization or truncation; accepted repairs preserve the source
identity and non-target history. Per-record hashes bind the consumed payload.
Staging is removed on failure; an existing output directory is never overwritten.
Every package remains `admission_authorized=false`, `uploaded=false`, and
`publication_ready=false`. No GPU/API review calls are made.

Official CC text was fetched from
`https://creativecommons.org/licenses/by-sa/4.0/legalcode.txt` into
`data/dfm13/baltic/publication-evidence/CC-BY-SA-4.0.txt`, SHA256
`28a9529c7d0bb4dc51f4bf5c116a3d16ef247a052f7591466768ddf563fd1cf5`.
Run after the completed ledger exists:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.blkt_export \
  --root data/dfm13/baltic \
  --output exports_dfm13/blkt-license-preparation-v1 \
  --cc-by-sa-license data/dfm13/baltic/publication-evidence/CC-BY-SA-4.0.txt \
  --cc-by-sa-sha256 28a9529c7d0bb4dc51f4bf5c116a3d16ef247a052f7591466768ddf563fd1cf5
```

At implementation time the 51,510-candidate seal exists, but the BLKT release
ledger does not. The real command correctly failed with `Completed release
ledger absent; no preparation performed`; no production package was created.
**Superseded later the same day:** the parent completed `wave_repair`; the
command above then succeeded with 48,201 accepted rows, 3,307 rejected and two
excluded-unreviewed. The initial absence is historical, not a current blocker.
This is a concrete completion prerequisite, not a new license-approval demand.
The future publisher still needs downstream conditions/safeguard evidence and
scoped destination/partition wiring. Any unresolved collection-versus-CC-row
license interaction must be resolved for that partition, not covered by a
blanket grant.

Focused verification: `python -m pytest -q tests/test_dfm12_blkt_export.py`
using the `hrm` environment: **21 passed**. Tests cover all eight task/license
partitions, immutable inputs, source/pin drift, absent/incomplete ledgers,
unknown terms, rejected rows, repaired targets, concurrent locks and cleanup.
The added regression preserves upstream null URLs with verified document/source
IDs rather than inventing links or imposing a new license hold. There are 187
such accepted rows; attribution explicitly marks `upstream_url_missing`.

Actual preparation at `exports_dfm13/blkt-license-preparation-v1/`:

| Partition | Rows | Recorded rendered tokens |
| --- | ---: | ---: |
| `denoising--newgenltu` | 15,019 | 31,670,833 |
| `prefix-continuation--newgenltu` | 22,635 | 24,743,703 |
| `span-filling--newgenltu` | 10,547 | 11,009,609 |
| Total | 48,201 | 67,424,145 |

All 51,510 ledger rows, including rejected/excluded, carry NewGenLTU terms.
There are no CC BY-SA or paragraph-reordering rows in this completed ledger;
do not confuse the earlier 60,000 selected windows with audited candidates.
No empty CC package or unaudited selected-window export was manufactured.
The exporter supports those partitions when a completed, sealed ledger actually
contains them. Why selected CC windows did not reach this seal was not determined
by this publication preparation and is not a claim that their license forbids use.

The top manifest SHA256 is
`068974342030797c40f233a296c81e59072b3f0dffa2dd8c752cde5232b36587`.
All package manifests/payload hashes and the union of 48,201 unique IDs were
independently checked after preparation. Remaining work is the scoped publisher
integration/destination wiring and carrying the actual NewGenLTU downstream
conditions and applicable model privacy safeguards. No new blanket approval,
manual review of every row, or additional model audit is required by this
preparation module. No uploads, registry changes or admission occurred.

### BLKT Export Partitions

1. Add a scoped BLKT attribution resolver in `dfm12/wave_release.py`, checking
   original file hash/ordinal and retained row license against pinned provenance.
   Select only terminal accepted/accepted-repair rows with positive audit.
2. Partition by `(task, original license)`; unknown or conflicting terms remain
   held. Include the license bucket in output folder, manifest, publication
   receipt and destination identity. Keep the existing single-source/license
   invariant inside each partition; do not disable it to permit mixed terms.
3. Avoid repo/revision-only license caching for mixed-license rows. The existing
   generic cache cannot distinguish their terms. Carry article/source URLs,
   original attribution and transformation notices into each scoped package.
4. Add full `LICENSE`/`NOTICE` payloads and their hashes. The current upload
   allowlist is only `README.md`, `manifest.json`, `data/train.jsonl`; it must
   explicitly include required license/notice files. CC BY-SA and NewGenLTU
   packages must not receive one another's incompatible blanket restrictions.
5. After scoped compliance receipts exist, update only the BLKT release route
   and the task/bucket receipt lookup in `scripts/advance_baltic_transforms.py`.
   Preserve source/input pins, audit gates, target index and remote hash checks.
   Test disjoint/exhaustive partition counts, unknown terms, cache isolation,
   path collisions, hash drift and uploaded license attachments.

### Summary Privacy Gate

1. Build a CPU sidecar assessment of source prompts **and final accepted/repaired
   answers**, retaining domain, CSV hash/ordinal, conversation hash and target
   hash. Flag identifiers, contacts, addresses and contextual re-identification
   risks for review; no regex hit is not proof of anonymity. Prioritize medical
   material without treating every medical row as prohibited.
2. Record hash-bound keep/hold/reject decisions and reasons, with no sensitive
   snippets in public logs. Unresolved flags stay held. Redaction produces a
   new candidate requiring fresh quality/privacy checks, not ledger mutation.
3. Require that receipt for the exact released content in the scoped summary
   path of `wave_release.py`; a repair invalidates an old content clearance.
   Supply NewGenLTU license/notice files, downstream restrictions and explicit
   evidence or a remaining gap for applicable model-level privacy safeguards.
4. Only then enable the summary route used by
   `scripts/advance_baltic_instructions.py`. Test missing/stale receipts,
   repaired targets, flagged rows, domain provenance and count conservation.

Neither route should broaden unrelated component allowlists, weaken model
quality gates, mutate sealed inputs, or imply all rows were manually reviewed.

## Scoped NewGenLTU Publisher, 2026-10-03

The owner clarified the distribution/model distinction after rereading sections
3, 5 and Attachment A10: full-license, notice and downstream-condition compliance
permits dataset redistribution. A10(b) is an obligation on trained models, not
an additional prerequisite to publishing the compliant dataset artifact. This
supersedes any implication above that proof of future model safeguards alone
blocks these NewGenLTU packages. A10(a) and all other use restrictions still apply.

`dfm12/blkt_publish.py` is an isolated publisher for the three exact, hash-pinned
prepared NewGenLTU packages. It does not monkeypatch the shared publishers or
change workers. It creates new publication artifacts, preserving the preparation
unchanged. Messages and source provenance are unchanged; admission/audit metadata
is promoted in the new artifact. Both the original preparation data hash and
new published data hash are retained.

The HF card uses `license: other`, `license_name: newgenltu-openrail-d-1.0`, and
the pinned upstream HTTPS license link. Full `LICENSE.txt`, dated `NOTICE.txt`,
binding `USE_CONDITIONS.md`, original `SOURCE_README.md` and per-row
`attribution.jsonl` accompany the dataset. Section 3/Attachment A conditions are
explicitly incorporated as conditions precedent, not optional recommendations.
The registry records the permitted purposes, personal-data extraction restriction,
trained-model privacy obligations and model-output conditions. Publication does
not claim those obligations have been tested for a future model.

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.blkt_publish \
  --preparation exports_dfm13/blkt-license-preparation-v1 \
  --output exports_dfm13/blkt-publication-v1
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.blkt_publish \
  --output exports_dfm13/blkt-publication-v1 --upload
```

The second command verifies every uploaded file, including license, conditions,
attribution and manifest, at the returned HF commit before registering anything.
All three verified records are integrated under the existing registry lock;
unrelated entries are retained. A remote hash failure prevents registry integration.
Focused suite: **25 passed** across `tests/test_dfm12_blkt_export.py` and
`tests/test_dfm12_blkt_publish.py`, including fake-HF attachment verification and
no-registration-on-failure tests. No extra generic approval or manual-review gate
was introduced. There are no accepted CC rows in this scoped publication.

Publication completed successfully on 2026-10-03: all attachments were downloaded
at their returned commits and hash-verified, and all three records are now in
`config/dfm13_sources.json` with `publication_status=verified`, repeat 1 and
explicit `model_use_conditions`. Receipt:
`exports_dfm13/blkt-publication-v1/integrated.json`.

| HF repository under `schneiderkamplab/` | Verified commit | Rows |
| --- | --- | ---: |
| `dfm13-wave3-transform-baltic-lt-blkt-denoising-newgenltu` | `b86bf6c5ab610e2252048012812306cb26f68e1f` | 15,019 |
| `dfm13-wave3-transform-baltic-lt-blkt-prefix-continuation-newgenltu` | `aff0419bb62eadc7afe6464918e0b2daf29bad0f` | 22,635 |
| `dfm13-wave3-transform-baltic-lt-blkt-span-filling-newgenltu` | `7dfc788f21872131040c8fae98b5e356fe1dccb7` | 10,547 |

This supersedes the no-upload/no-admission state of the earlier preparation
stage for these three new publication artifacts only. Sealed preparation,
audit/repair inputs, GPU workers and existing publisher code remain unchanged.

### Tokenization and Assembly Compatibility

The initial scoped publisher omitted `status=accepted_uploaded`; although remote
publication was verified, this made the existing tokenization watcher ineligible.
Fixed the publisher and normalized only the three BLKT registry statuses under
the registry lock after checking local verified receipts, HF revisions and every
payload/attachment hash. Watcher-added fields and unrelated records were retained;
identical HF files were not uploaded again. Verified sidecar receipts now also
carry the standard status.

The watcher subsequently completed all three packages. The current assembler API
is `scripts.assemble_dfm13_additions.verify_entry` (not `verify_source`). A narrowly
scoped adapter validates BLKT's `.verified.json` receipt layout, pinned source and
preparation, exact task populations, remote revision, all license/notice/attribution
attachments, and matching `model_use_conditions` across registry/export/receipt.
The ordinary `accepted_uploaded` and tokenization readiness gates remain intact.
Verified additions carry the conditions into `assembly.json`; the adapter does
not discard them or substitute a generic license.

Actual sequential `verify_entry` calls passed for all three tokenized packages:
48,201 rows and 67,424,145 tokens. Checks included all token-array hashes and
structural bounds, zero skipped rows, source/template/tokenizer receipt pins and
bounded exact native prompt/response token parity. Machine-readable results:
`docs/reports/dfm13_blkt_assembly_verification_20261003.json`.
No full assembly or new tokenization was launched by this verification.
Combined exporter/publisher/assembler tests: **70 passed**. Tests additionally
cover preserving watcher fields during status repair, refusing mismatched remote
revisions, attachment drift, missing conditions and no missing-status bypass.

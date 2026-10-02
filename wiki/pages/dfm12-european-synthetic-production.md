---
type: Runbook
title: DFM12 European Synthetic Production
description: Separate twelve-language generation and independent audit campaign at the tenth milestone.
tags: [dfm12, synthetic, multilingual, production]
status: draft
last_updated: 2026-09-28
confidence: high
---
# European Synthetic Production

**2026-09-28 runtime update:** the separate 16-client launch below is superseded
by [joint nineteen-language production](dfm12-joint-synthetic-production.md).
Both original ledgers are retained under one dispatcher with a shared ceiling
of 512 requests per endpoint. Dataset quotas and quality contracts are unchanged.

## Applied Target Migration, 2026-09-28

**Supersedes the initial 420K allocation and the unapplied recommendation below.**
The user authorized 70,000 accepted conversations each for Estonian and
Catalan, retaining 35,000 for the other ten languages: **490,000 total**.
Exactly twelve language/family targets doubled; all other targets are unchanged.

The isolated helper `dfm12/european_synthetic_migrate.py` checked the full
command and runtime of PID 3686338, bound SIGTERM to its Linux pidfd, and
waited for a clean drain (zero active allocations or running jobs). Under the
controller lock it backed up config, manifest, seal, jobs SQLite and source
selection SQLite before applying the increase. It resealed the copied config,
manifest and SQLite manifest hash without changing implementation or external
pins. Logical before/after hashes confirmed unchanged jobs, fingerprints,
non-target group state, source selections and cursors. The drain preserved
4,744 accepted conversations and 9,665 candidate attempts. No shared servers
or seven-language client were signaled; pinned controller/spec/seed files
were not edited.

Migration receipts and backups:
`data/dfm12/european-synthetic-et-ca-migration-20260928/`:
`drain.json`, `backup/receipt.json`, and `resume.json`.
New manifest SHA256:
`0821aab59f67611ad9e6000ff576a1cf44ace5782770e4c44bbfa28079308b66`.
Replacement PID **3934004** uses the exact saved command, 16 clients/server,
600-second timeout and KV ceiling 0.90. Its log is
`data/dfm12/european-synthetic-tenth-20260928/client-et-ca-70k.log`.
The migration suite passed **16 tests**, including rollback, lock exclusion,
exact-process checks, clean-drain enforcement and state preservation; XML:
`data/dfm12/european-synthetic-et-ca-migration-tests-20260928.xml`.
490K is the target, not a claim of completed generation or quality certification.

## Authorization And Targets

On 2026-09-28 the owner authorized CPU preparation and GPU generation for the
twelve languages in the [European expansion](dfm12-european-expansion.md).
Use 35,000 accepted conversations per language where decent instruction data
has already been found, and 70,000 where it has not. All twelve currently
qualify for the former supply tier, so the target is **420,000 accepted rows**.
These are not raw candidate or generation-attempt counts.

| Language | Existing instruction sources supporting the 35K tier |
|---|---|
| German | EU-Instruct-Synthetic and translated DOLCI |
| French | EU-Instruct-Synthetic and translated DOLCI |
| Spanish | EU-Instruct-Synthetic, translated DOLCI and ALIA |
| Italian | EU-Instruct-Synthetic and translated DOLCI |
| Czech | EU-Instruct-Synthetic and translated DOLCI |
| European Portuguese | Amalia persona, instruction-following, Wikipedia conversation and summarization collections |
| Finnish | Poro2 instruction collection and translated DOLCI |
| Estonian | Magpie Gemma Estonian |
| Catalan | ALIA Catalan subset |
| Greek | EU-Instruct-Synthetic and translated DOLCI |
| Romanian | EU-Instruct-Synthetic and translated DOLCI |
| Ukrainian | EU-Instruct-Synthetic and translated DOLCI |

Supply evidence comes from the prepared source receipts under
`data/dfm12/european-expansion-20260926/progress`. For example Poro2 has
653,009 prepared Finnish candidates and Magpie 100,329 Estonian candidates.
These receipts establish source availability, not native-speaker quality
certification or automatic acceptance of every existing instruction row.

**Quota reassessment, 2026-09-28 (recommendation, not applied):** mere source
availability is too coarse a priority rule. Estonian's main prepared Magpie
source has 100,329 candidates and relatively light source-side filtering;
Catalan's ALIA source was reported at 87,011 Catalan rows before local filtering
(the 218,514 local candidate count combines Catalan and Spanish). Recommend
70K for Estonian and Catalan, keeping 35K for the other ten. That would total
490K accepted synthetic rows. Finnish has substantial Poro2/DOLCI supply;
European Portuguese has several Amalia task collections; Greek, Romanian and
Ukrainian have sizable EU-Instruct/DOLCI supply. This is a coverage-based
judgment, not proof of quality or an evaluation-derived optimal allocation.
Do not change the running sealed configuration without approval and a
checkpointed, locked migration that retains accepted rows and source cursors.

Configuration: `dfm12/european_synthetic_extension.yaml`.

| Family | Accepted per language | All twelve |
|---|---:|---:|
| Multi-turn | 7,500 | 90,000 |
| Grounded instruction | 10,000 | 120,000 |
| Modernized OpenHermes adaptation | 7,500 | 90,000 |
| Summary/rewrite | 5,000 | 60,000 |
| Math/code | 3,000 | 36,000 |
| Native tool dialogue | 2,000 | 24,000 |
| Total | 35,000 | 420,000 |

Existing family length estimates imply approximately **666.6M tokens** before
actual accepted-row tokenization. This is an estimate, not measured token yield.
Milestone expansion must preserve accepted records, provenance and row IDs.

## Isolation And Quality

The seven-language campaign and its sealed 385,000 target remain unchanged.
Use separate seed inventory, SQLite ledger, controller lock, atomic receipts
and immutable source selections. Do not edit pinned live production modules
to add language codes. European Portuguese must remain pt-PT rather than
generic Portuguese or a silent Brazilian variant substitution.

Reuse the established native Gemma tool trajectory assembly, deterministic
math/code references, strict generation validation and separate evidence-based
audit. Both teacher and auditor remain Gemma 4 26B A4B. Passing this automated
audit is not equivalent to native-speaker certification. Keep failure evidence
and do not count invalid or rejected rows toward quotas.

Borrow the existing eight localhost servers on ports 8600-8607. This campaign
must not restart, resize or tear down those servers, affect training, or change
evaluation scheduling. New admissions must respect measured KV pressure and
server waiting queues. Concurrent CPU seed preparation must expose only fully
committed records and keep bounded memory.

No final DFM12 sampling or automatic Hub upload is part of this launch.

## Verified Launch

On 2026-09-28, bounded CPU preparation started as PID 3668771:
`python -m dfm12.european_synthetic_seeds prepare --root
data/dfm12/european-synthetic-seeds-20260928 --native-target 60000
--oh-target 30000 --batch-size 32`.
The targets are eligible seeds, not accepted output rows. Wikipedia supplies
eleven native-language pools; approved CorEGe-PT supplies pt-PT with the
existing variant/rights filters. Only modernized `dfm8-openhermes-en` supplies
OpenHermes seeds. Preparation streams file/row-group inputs and publishes
committed SQLite records while generation is active. Sources never wrap to
fill quotas. Rejections can exhaust this initial supply; report shortfalls
and replenish deliberately instead of recycling sources.

Campaign root: `data/dfm12/european-synthetic-tenth-20260928`.
Detached controller launch PID: 3686338. Log: `<campaign-root>/client.log`;
live progress: `<campaign-root>/progress.json`; admission explanations:
`<campaign-root>/admission-status.json`. `launch.json` records the command.

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
TOKENIZERS_PARALLELISM=false \
/home/ucloud/miniforge3/envs/hrm/bin/python -B -u \
  -m dfm12.european_synthetic_campaign run \
  --root data/dfm12/european-synthetic-tenth-20260928 \
  --concurrency-per-server 16 --timeout 600 \
  --max-kv-cache-utilization 0.90
```

Use this only when no controller owns the campaign lock, and detach it for
production. The existing seven-language client retains its 64-per-server
ceiling; the new client adds 16 per server, with independent KV/waiting gates.
Both clients borrow the same eight servers without changing memory allocation.
The additional client ceiling is 32, not an authorization to force a larger
server queue. Implementation/config/tokenizer pins are checked before resume.

Initial verification found accepted rows in all twelve languages and all six
families, with around 120 candidates active. The original campaign continued
past 207K accepts. Neither server lifecycle nor existing campaign files were
changed. Independent pre-launch review found no blocker; 131 focused tests
passed. This establishes operational generation/audit, not completed quotas or
native-language quality certification. Final corpus-level overlap screening,
accepted-only packaging and token accounting remain later steps.

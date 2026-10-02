---
type: Runbook
title: DFM12 Second European Language Wave
description: Reusable preparation for twelve additional languages, missing instructions, and TrustLLM answers.
status: draft
confidence: high
last_updated: 2026-09-28
tags: [dfm12, multilingual, preparation, audit]
---
# DFM12 Second European Language Wave

## Synthetic Source Adapter, 2026-09-28

`dfm12.european_synthetic_specs` is an isolated CPU adapter for DE, FR, ES, IT,
CS, pt-PT, FI, ET, CA, EL, RO and UK. It does not change the running
seven-language task factory or its language registry. It binds the existing
v4 factory code to a private globals dictionary and retains all six task
families, deterministic references and native Gemma tool assembly with natural
final replies. Existing generation, source-only constraints, strict raw JSON
decoding, student template rendering and indexed review remain required.

Seed-owner contract: `seeds.sqlite` exposes
`available_seeds(language,pool,seq,source_id,payload)`, with positive increasing
sequence numbers and full JSON source payloads whose `id` equals `source_id`.
Native pools use the target language code; OpenHermes uses `openhermes`, with
eligibility scoped to each target language. Native payloads retain `text`;
OpenHermes payloads retain every user/assistant message. Source license and
revision evidence remain in the payload; this adapter grants no new licenses.
The seed owner is responsible for screening before making rows available.

`SourceProvider(seeds_root, root, config).next_spec(language,family,slot)` stores
immutable selections and source hashes in `spec-selections.sqlite`. Reopening a
slot returns its original specification. Native families share a per-language
consumption ledger; OpenHermes can be used once per target language, not recycled
within that language. Exhaustion raises `SeedUnavailable` without consuming a
slot. Growing inventories are read-only to this adapter. Use a new campaign root.

Runner integration APIs are `request(spec, endpoint_models=None)`,
`decode(spec, raw_content, finish_reason)`, `assemble(spec, output)`,
`audit_record(candidate)` and `review_request(candidate)`. The old v6 audit
builder has a seven-language lookup: extending its registry alone does not
forward this adapter's explicit pt-PT variant requirement. Route through the new
audit adapter as well. Portuguese generation and review require European, not
Brazilian Portuguese, assessed semantically in context rather than by a token
blacklist. Source quotations and tool identifiers remain unchanged.

Prepared candidates have `admission_authorized=false`; an assembly or source
selection is not an audit pass. The controller still owns strict acceptance
gates and must pin this adapter and its reused dependencies in a fresh manifest.
No GPU requests, model launches, export or training changes were performed by
this preparation. Initial focused CPU verification: 97 tests passed, including
actual Gemma template rendering and all six native-tool subtypes. This is not
12-language semantic calibration evidence.
The subsequent adapter-plus-multilingual regression run passed 682 tests with
two existing SWIG deprecation warnings. OKF validation passed without errors
or warnings. The seed module's shared `available_seeds` view was inspected and
matches the adapter interface; live generation remains a separate operation.

## Authorization and Scope

### Synthetic Campaign Extension Preparation, 2026-09-28

The owner requested preparation to extend the running seven-language synthetic
generation/audit campaign to the twelve languages below. This is preparation,
not authorization to interrupt existing work or silently enlarge its sealed
385,000-accepted-row target. Preserve the current ledger and use a separate
versioned campaign root for the new wave.

Reuse the six existing families: multi-turn, grounded instruction, OpenHermes
adaptation, summary/rewrite, math/code and native tool dialogue. Before bulk
generation, inventory language-specific seeds from the European preparation,
calibrate generation and independent review per language, and inspect a small
pilot. European Portuguese must remain explicitly pt-PT. Native Gemma tool
structure must remain language-independent; translate natural language only.
Final accepted targets and priority weights for this synthetic wave are not
yet assigned; the transformation quotas below are a separate workstream.

**Superseded later on 2026-09-28:** the owner authorized generation at the
tenth milestone with 35K per language where instruction supply exists, 70K
otherwise. All twelve have identified instruction supply. The separate
[European synthetic production campaign](dfm12-european-synthetic-production.md)
is now running toward 420K accepted rows; the transformation quotas below
remain a separate workstream.

Implementation gate: `multilingual_quarter.py` currently enforces exactly
42 groups (seven languages times six families), with sealed milestone totals
and implementation/input pins. Merely adding language codes to the live YAML
is not safe. Prepare a generalized, tested campaign configuration and separate
ledger without modifying the running process's pinned implementation. Existing
European source preparation/audits are inputs, not proof that synthetic
generation and reviewer calibration cover all twelve languages.

On 2026-09-26 the owner authorized German, French, Spanish, Italian, Czech,
European Portuguese, Finnish, Estonian, Catalan, Greek, Romanian and Ukrainian.
Czech was requested twice and is counted once. The existing nine languages
remain supported. DaLA correction/acceptability is owned by another thread.
This supersedes research-only status for the selected instruction candidates
in [the previous survey](dfm12-missed-instruction-candidates.md).

Implementation: `dfm12/european_expansion.py`, `european_texts.py`,
`european_opus.py`, and `trustllm.py`. These orchestrate existing catalog,
converters, transformation reservoir, Gemma renderer, OPUS preparation,
SQLite job leases, independent audit and accepted-only export functions.
The first-wave catalog, accepted exports and sampled training data are not modified.

## Quotas

Same measured Danish baseline and 25% targets, per added language:

| Family | Accepted target / cap |
|---|---:|
| Denoising/correction | 50,758 rows |
| Prefix continuation | 76,142 rows |
| Span filling | 44,795 rows |
| Paragraph reordering | 22,516 rows |
| Instructions | All relevant accepted unique rows; repeat 1 |
| English translation pair, both directions | 661,329,827 tokens/epoch maximum |
| Non-English translation pair, both directions | 165,332,456 tokens/epoch maximum |

Translation caps use the **per-epoch** EN-DA baseline of 2,645,319,308.5
tokens, not the old ten-epoch report sum. Caps are not fill mandates; report
shortfalls instead of manufacturing alignments or repetition. Preparation
does not itself enforce the later token sampling cap. Transformation candidates
use the existing 1.5x allowance; accepted shortages require later replenishment.

## Registered Sources

| Source | Selected scope |
|---|---|
| `openeurollm/EU-Instruct-Synthetic` | NL/PL additions; DE/FR/ES/IT/CS/EL/RO/UK |
| `openeurollm/Dolci-Instruct-SFT-translated` | DE/FR/ES/IT/CS/FI/EL/RO/UK |
| `CohereLabs/aya_dataset` | Supported language codes; train only, no demographics; generic PT excluded |
| `utter-project/EuroBlocks-SFT-2512` | Exact supported monolingual labels; generic Norwegian and Portuguese not relabelled |
| `BramVanroy/dolly-15k-dutch` | `train_sft` only |
| `HuggingFaceTB/smoltalk2` | Only no-think everyday conversations and systemchats; no whole-mixture ingestion |
| `LumiOpen/poro2-instruction-collection` | Finnish rows from train only |
| `tartuNLP/magpie-gemma-3-12b-it-100k-et` | Estonian instruction/response pairs |
| `BSC-LT/ALIA-2606-SFT` | Catalan and Spanish rows only |
| `amalia-llm/{persona_general,persona_instruction_following,wikipedia_conversations,smol_summarize_pt}` | Portuguese files only; quality-5 verified IF subset; pt-PT audited |
| `wikimedia/wikipedia` | `20231101.<language>` for the eleven non-PT new languages; all files, distributed document sampling |
| `amalia-llm/CorEGe-PT` | Both PT and PT-PT flags true, both confidences >=0.8, explicit adaptation-permitting CC URI; missing/ND rights excluded |
| `AnnikaSimonsen/TrustLLM-reformulation-prompts` | All released native prompts; generated answers and labelled adaptations below |

43 source registrations are pinned in the expansion catalog. Registration
means candidate preparation, **not** completed quality audit or training admission.
The Icelandic SmolTalk candidate remains a quality/provenance hold; unavailable
Aurora and deferred PLLuMIC-syn-ext were not silently admitted. Tool traces from
SmolTalk2 still need the native tool converter before any separate inclusion.

## TrustLLM

The pinned released schema has no answer field or OpenAssistant message ID.
The [released repository](https://huggingface.co/datasets/AnnikaSimonsen/TrustLLM-reformulation-prompts)
and [paper](https://aclanthology.org/2026.lrec-1.841/) did not provide a linked
answer release. Do not transplant an English answer onto a culturally changed
prompt. Generate answers with the existing configured Gemma teacher instead.

Actual rows: IS 998, FO 997, DE 250, DA 999, NL 697, NB 999, NN 998, SV 999.
All 6,937 native prompts are preserved exactly. For each of the other 13
languages, 1,000 deterministic seeds sampled across native languages are
queued for explicitly synthetic prompt adaptation and answering: 19,937 jobs.
This 1,000-row adaptation target is a starting preparation choice, not an
inherited transformation or translation quota.

Native prompt changes are rejected before audit. Independent audit compares
the seed, target language, factual grounding and task meaning. Missing context
must not be fabricated. Generation uses `trustllm.sqlite`; audited records
transfer to the common `jobs.sqlite` for the existing accepted-only exporter.
Audit responses are not training targets. Both stages retain source lineage.

## Operations and Remaining Gates

See [CPU follow-up operations](dfm12-european-cpu-preparation.md) for the newer
screening-first audit queue, replenishment gates and current progress. The
initial snapshot below is historical, not the latest count.

Work root: `data/dfm12/european-expansion-20260926`.
Logs: `logs/dfm12_european_expansion/{cpu,opus-discover,opus-prepare}.log`.
The CPU campaign was launched detached with four workers and GPUs hidden.
All eight GPUs were occupied by training; no training, scheduler or GPU server
was interrupted and **no expansion GPU generation/audit was started**.

Initial verified snapshot: 1,491,516 instruction candidates and 877,127
bidirectional OPUS pair candidates prepared, with 19,937 TrustLLM generation
jobs queued. OPUS discovery completed all 174 edges with no API errors:
215 corpus/pair entries approved, 2,196 quality-excluded, 3,815 still requiring
license/content review. These are **not** accepted training counts.

Schema smoke checks covered ALIA, EuroBlocks, SmolTalk2 and Dutch Dolly.
SmolTalk2 `chat_template_kwargs.custom_instructions` must become a system
message; dropping it loses the context for its assistant answers. Nonempty
tool metadata or thinking-mode metadata is rejected by the text-only adapter,
not silently stripped. CPU preparation was restarted with this fix before
SmolTalk2 conversion began. Focused tests: 109 passed; OKF validation clean.

```bash
python -m dfm12.european_expansion status
python -m dfm12.european_expansion cpu --workers 4
python -m dfm12.european_opus
python -m dfm12.european_expansion manifest
python -m dfm12.european_expansion queue-audits
python -m dfm12.trustllm generate --endpoint http://localhost:8400/v1 --concurrency 64
python -m dfm12.trustllm transfer
python -m dfm12.trustllm audit --endpoint http://localhost:8400/v1 --concurrency 64
```

Use the prepared Python environment, and start generation/audit clients only
against explicitly allocated servers. The new language reviewer calibration,
fresh inherited/benchmark screening, independent full audits, accepted-only
tokenization and final integration remain required. The manifest explicitly
records `benchmarks_clear=false` and `full_inherited_coverage=false`; the old
nine-language audit authorization must not be treated as clearance for 21.
No final sampling was requested or performed for this expansion.

OPUS discovery covers 174 new pair edges (12 English pairs plus 162 between
non-English languages). Existing named institutional corpus-version evidence
is reused; Tatoeba release license is checked. Mined/fragmentary exclusions
remain. Other corpora stay in license review, and absent supply is recorded.
Internal `pt_pt` maps to OPUS `pt` only for discovery: row audit must still
reject wrong/ambiguous variants. No automatic pivot translation is introduced.

Receipts are atomic; source workers and catalogs have exclusive locks.
Catalog additions can append sources without repinning existing revisions;
existing source/policy changes fail closed. Partial candidate writes are not
completion signals. Checksum mismatches stop processing, not silently reuse data.

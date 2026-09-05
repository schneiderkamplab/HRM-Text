---
type: Training Data Plan
title: DFM11 Plan
description: Deferred quality repair and task-aware admission plan derived from the completed DFM10 residual audit.
tags: [dfm11, data-quality, filtering, repair, audit, training-data]
status: draft
last_updated: 2026-09-04
confidence: medium
sources:
  - id: magpie-paper
    resource: https://arxiv.org/abs/2406.08464
    title: "Magpie: Alignment Data Synthesis from Scratch by Prompting Aligned LLMs with Nothing"
    author: org:Magpie-Align
  - id: magpie-code
    resource: https://github.com/magpie-align/magpie
    title: Magpie generation and filtering implementation
    author: org:Magpie-Align
  - id: magpie-gemma2-format-reference
    resource: https://huggingface.co/datasets/Magpie-Align/Magpie-Gemma2-Pro-200K-Filtered
    title: Magpie Gemma 2 filtered dataset card and schema reference only
    author: org:Magpie-Align
  - id: fineinstructions-nemotron-card
    resource: https://huggingface.co/datasets/fineinstructions/fineinstructions_nemotron
    title: FineInstructions Nemotron dataset card
    author: org:fineinstructions
  - id: fineinstructions-paper
    resource: https://arxiv.org/abs/2601.22146
    title: "FineInstructions: Scaling Synthetic Instructions to Pre-Training Scale"
    author: org:FineInstructions
  - id: nemotron-cc-paper
    resource: https://arxiv.org/abs/2412.02595
    title: "Nemotron-CC: Transforming Common Crawl into a Refined Long-Horizon Pretraining Dataset"
    author: org:NVIDIA
  - id: common-crawl-terms
    resource: https://commoncrawl.org/terms-of-use
    title: Common Crawl Terms of Use
    author: org:Common-Crawl
  - id: tinygsm-dataset
    resource: https://huggingface.co/datasets/TinyGSM/TinyGSM
    title: TinyGSM dataset
    author: org:TinyGSM
  - id: gsm8k-prolog-prover-dataset
    resource: https://huggingface.co/datasets/niklasm222/gsm8k-prolog-prover
    title: GSM8K Prolog Prover dataset
    author: person:Niklas-Mellgren
  - id: prolog-as-a-tool-code
    resource: https://github.com/aisilab/Prolog-as-a-Tool
    title: Prolog as a Tool reference implementation
    author: org:AISI-Lab
---
# DFM11 Plan

## Decision and boundary

DFM10's residual-quality scope is frozen for near-term training, but the final
DFM10 data snapshot is not yet frozen. The outstanding, already-approved
boundary operation is integration of the audited Danish Model Charter package
`dfm10-synthetic-values-model-charter-da`, followed by the authoritative DFM10
union rebuild and resampling. A separate workstream owns that operation. DFM11
work must not duplicate, modify, or race it.

The DFM10 freeze becomes effective only after that integration and resampling
complete and their metadata are validated. The residual-quality findings
completed on 2026-08-31 will not delay this finalization or the ensuing DFM10
training. After the boundary is reached, only a train-blocking integrity defect
such as a missing artifact, corrupt file, or invalid manifest may change the
DFM10 snapshot, and such a correction must be recorded explicitly rather than
presented as quality curation.

DFM11 starts from the exact finalized DFM10 source and sampling manifest, then
applies isolated replacements and exclusions. It must not overwrite DFM10
converted, tokenized, or sampled artifacts. The intended paths are:

- source policy: `config/data/dfm11.yaml` and DFM11-specific filter decisions;
- tokenized union: `data/tokenized_dfm11`;
- sampled corpus: `data/sampled_dfm11`;
- repaired sources: distinct DFM11 names until their admission gates pass.

Before DFM11 work starts, verify the Danish Model Charter receipt and record
hashes and row/token inventories for the resulting final DFM10 config, union
metadata, source inventory, and sampled metadata. This post-resampling snapshot
is the sole DFM11 baseline. It makes the DFM10-to-DFM11 delta reproducible and
prevents repairs from leaking into an already running DFM10 experiment.

## Evidence from DFM10

The completed [DFM10 residual quality audit](dfm10-residual-quality-audit-queue.md)
examined 46,872 exact training representations and found 39,605 usable (84.5%)
with no unresolved judge errors.

| Stratum | Audited | Usable | Main DFM11 concern |
|---|---:|---:|---|
| Sapient packages | 8,500 | 7,059 (83.0%) | Contract-sensitive math judging, QReCC-II corruption, and noisy large families |
| Native tool and agent | 5,900 | 5,589 (94.7%) | Generic judges misclassify valid intermediate tool calls; some real schema/coherence defects remain |
| Folketing error correction | 5,000 | 3,127 (62.5%) | No-op or negligible corrections, residual OCR damage, and truncated targets |
| Borderline Danish | 2,359 | 1,690 (71.6%) | Legacy back-translation grounding, truncation, and instruction/target mismatch |
| Borderline English | 19,113 | 16,287 (85.2%) | Concentrated bad Natural Instructions tasks and contract failures in one-pass SFT sources |
| Completed Mimir/persona packages | 6,000 | 5,853 (97.6%) | Small known-answer or schema-verification tail; no case for regeneration |

The audit is a triage signal, not a universal row-level admission oracle.
OpenMath direct answers failed the generic judge at 42.6%, versus 22.6% for CoT,
partly because the judge expected derivations from a direct-answer contract.
DeepDive intermediate assistant tool calls were similarly judged as incomplete
final responses. DFM11 must use task-aware verification before excluding either
family.

## FineInstructions Nemotron - excluded

**Decision, 2026-09-04:** DFM11 excludes
`fineinstructions/fineinstructions_nemotron`. Its Common-Crawl-derived
provenance, copyright, PII, and deliberate source-copy risks require more
review than its expected marginal value justifies for Mimir. It has a zero
token budget, is absent from the downloader manifest, and the retained
materializer refuses to run. The discussion below is the superseded candidate
assessment.

The source was considered as a fail-closed English instruction-pretraining
candidate. It is not ordinary post-training
SFT: the release contains more than one billion synthetic instruction/answer
pairs (approximately 300B tokens), generated from Nemotron-CC source documents.
The FineInstructions experiments used this representation for pretraining from
scratch and formatted each pair as an instruction and answer.

### Superseded cap and quality proposal

- cap the admitted source at **3.0B Gemma-rendered tokens per DFM11 epoch**;
- use `repeat: 1` and do not compensate for filtering by repetition;
- retain only upstream judge score 5, with no lower-score fallback to fill the
  cap; unused budget is preferable to weaker synthetic supervision;
- deterministically sample paired data/judge shards across the release;
- materialize approximately 3.45B upstream `synthetic_token_count` tokens, then
  enforce the exact 3.0B cap after Gemma-template tokenization;
- run exact/near deduplication, protected-eval decontamination, context-length
  validation, PII review, and source-copy review before admission.

The 3B cap is deliberately about 3% of a roughly 100B-token DFM epoch: large
enough to test the paper's instruction-pretraining effect without allowing one
English Common-Crawl-derived family to dominate Danish, math/code, native chat,
or agentic supervision. At the card's aggregate average of approximately 244
tokens per row, 3B tokens corresponds to roughly 12.3M rows before downstream
filtering. Revisit the cap only after source-stratified quality and capability
ablations; 5B tokens is the provisional hard ceiling for DFM11.

A local 12-shard sample covering 7,972,982 judge labels found 15.15% score 5,
43.09% score 4, 28.46% score 3, 10.61% score 2, and 2.46% score 1. This is why
the initial gate is score 5. The upstream score remains only a quality signal,
not a privacy, licensing, correctness, or decontamination decision.

### Exclusion rationale: license, provenance, and PII

Admission is permanently closed for DFM11. The Hugging Face card declares no dataset license.
FineInstructions says the rows derive from Nemotron-CC, which derives from
Common Crawl. Nemotron-CC is distributed under the Common Crawl Terms of Use;
those terms warn that crawled content may remain subject to source-owner terms
and place copyright, privacy, and lawful-use assessment on the user.

This transformation does not remove the underlying concern. FineInstructions
requires generated answers to contain at least 80% excerpts from source
documents, and its paper describes query moderation and benchmark
decontamination but no PII-removal stage. Therefore:

1. do not represent this source as permissively licensed;
2. obtain an explicit project-level copyright/provenance decision;
3. reject obvious emails, phone-like identifiers, IP addresses, credentials,
   addresses, and other personal identifiers, followed by a stratified semantic
   PII audit because regexes cannot reliably identify names or contextual PII;
4. measure long verbatim source spans and domain/source concentration;
5. fail closed if the source-copy and PII audits cannot establish an acceptable
   policy for the intended academic use.

An admitted materialization requires a receipt at
`data/receipts/dfm11_fineinstructions_nemotron_admission.yaml` affirming the
license decision, PII audit, source-copy audit, benchmark decontamination, and
task-quality audit. Review-only pilots remain segregated under `data/review/`:

```bash
python scripts/prepare_dfm11_fineinstructions_nemotron.py inventory
python scripts/prepare_dfm11_fineinstructions_nemotron.py materialize \
  --review-only --max-rows 100000
```

### FineInstructions-seeded multi-turn chats

FineInstructions can seed useful multi-turn generation, but semantic clustering
should control **coverage and sampling**, not mechanically concatenate or order
independent question/answer rows. Similar standalone questions rarely form a
conversation with genuine turn dependencies, and concatenation can combine
incompatible source contexts or repeat copied passages.

Use a hybrid method:

1. embed and cluster accepted score-5 instructions by domain, task, difficulty,
   and intent; cap large clusters and sample a broad seed distribution;
2. use one seed, or at most a few source-compatible seeds sharing provenance,
   to construct a latent conversation plan;
3. ask the pinned Gemma 4 31B teacher to generate a fresh 2-6-turn native chat
   with clarification, follow-up, correction, or elaboration dependencies;
4. do not copy the seed answer into the conversation and do not expose source
   text unless the task explicitly requires grounded context;
5. independently audit every assistant turn for coherence, factual support,
   PII, source reproduction, language, and native Gemma formatting;
6. deduplicate against both FineInstructions and the separate DFM11 Magpie
   corpus, and retain seed IDs and cluster IDs as provenance metadata.

Start with a 20,000-chat pilot and admit at most **100,000-200,000 accepted
English chats** after an ablation. Free, unseeded Gemma generation already
belongs to the bilingual Magpie workstream; the value of FineInstructions here
is coverage guidance, not another route to unconstrained free generation. Do
not translate these chats to manufacture Danish balance. Use native Danish
seeds or the independent Danish Magpie lane for matched Danish coverage.

**Superseded operationally on 2026-09-02 for dataset construction, not
admission:** the active DFM-owned FineInstructions campaign now targets exactly
1,000,000 English grounded pairs and 1,000,000 corresponding multi-turn chats.
This larger artifact remains outside every training mix until quality,
decontamination, source-copy, PII, and ablation gates pass. The campaign imports
19,479 stable-ID pilot templates and balances 500,000 document windows equally
across filtered Common Pile arXiv, Wikimedia, StackExchange, LibreTexts,
regulations, USGPO, DOAB, Project Gutenberg, PubMed, and news sources. The
source document is supplied to pair instantiation, chat generation, and the
independent chat audit, then stripped from final artifacts. This supersedes the
earlier instruction not to expose source text to chat generation because these
chats are explicitly source-grounded tasks.

The English campaign lives at `data/fineinstructions/dfm11-english-1m`, uses
`fineinstructions/configs/dfm11-english-1m.yaml`, and is launched by
`fineinstructions/scripts/run_dfm11_english_1m.sh`. It uses only GPUs 4-7 on
the isolated generation node. Grounding corpus admission here does not add raw
Common Pile continuation text to DFM training.

Query templatization uses the short-request operating point requested on
2026-09-02: 4,096 concurrent requests per GPU server, `max_num_seqs=4096`, and
90% vLLM memory utilization. This setting is stage-specific; document-heavy
instantiation and grounded chat generation retain lower concurrency until
measured KV-cache behavior supports increasing it.

**Superseded after the completed 2026-09-02 templatizer wave:** 4,096 is a
stress ceiling, not the selected throughput point. At 512 requests per server,
the four servers completed 61,617 requests in about 11 minutes (about 93
requests/s aggregate) while producing roughly 50K tokens/s/GPU. The 4,096-way
wave completed 20,930 requests in about 5.5 minutes (about 63 requests/s) and,
while KV cache was saturated, produced only about 23K-25K tokens/s/GPU. The
second wave contained later and retried rows, so this is not a controlled A/B,
but it is sufficient to reject blind maximization of request concurrency.
Future campaigns should sweep 1,024, 2,048, and 3,072 and select on committed
rows/s plus generated tokens/s, with KV occupancy below sustained saturation.

Retrieval was separately benchmarked because it is a SentenceTransformers plus
FAISS stage rather than vLLM. On the same 12,000-candidate arXiv slice, encoder
batches 32, 64, and 128 completed in 185, 194, and 196 seconds. Filling GPU
memory is therefore not a valid objective for this stage. The active campaign
uses batch 32 across four stable-hash document shards on GPUs 4-7, shares the
read-only legacy completed-document ledger, writes isolated shard ledgers and
candidate files, and atomically validates/deduplicates the merged output. Its
measured steady interval was about 72.5 documents/s aggregate, versus about 9
documents/s for the original single-GPU batch-16 process.

The Danish counterpart must not use LexDK or DBC. Its provisional grounding
families are public/admitted Danish DynaWord subsets, Folketing/Rigsarkivet,
and other admitted Danish legal/public-sector documents, with explicit source
caps. Before that lane starts, the published English-trained templatizer,
retrieval encoder, and instantiator must pass a native-Danish qualification;
otherwise Gemma 4 generation or newly distilled Danish artifacts replace the
failing stages.

### Danish FineInstructions qualification status

Update, 2026-09-02. The production Danish campaign has **not** started and no
production target has yet been approved. A deterministic qualification under
`data/fineinstructions/danish-artifact-qualification` contains 100 native
Danish AI Arena opening queries and 100 DynaWord Nordjyllandnews documents.
The published English query templatizer produced parseable templates for 93
queries and seven JSON-format failures. Parse acceptance is not quality
acceptance: inspection found mixed English variable labels, damaged Danish
spelling, and semantic errors such as interpreting `sengen` as a cooking device
and turning `nationalret` into a national symbol.

An exact index over those 93 templates yielded only 62 candidates across 44 of
the 100 documents at the published `0.865` threshold. Candidate scores ranged
from 0.866 to 0.938. This is not yet a controlled multilingual-retriever verdict
because the template bank is small and the query/document domains differ, but
the yield is insufficient for production. No candidate has yet passed through
the published instantiator, pair audit, chat continuation, or chat audit.

Remaining gates, in order:

1. Run an equal-sized English control to separate multilingual retrieval loss
   from small-bank/domain mismatch, and inspect below-threshold Danish matches.
2. Instantiate the 62 existing candidates and judge Danish fluency,
   instruction-answer coherence, grounding, excerpt reconstruction, source
   copying, and rendered token length.
3. Decide whether the published artifacts pass. If not, generate Danish
   template/instantiation labels with Gemma 4 and distill Danish-aware
   templatizer/instantiator models; fine-tune or recalibrate the multilingual
   BGE-M3 retriever only from verified positive pairs and hard negatives.
4. Define and pin the production source manifest and target. Query seeds may
   include admitted native Danish chat/instruction sources; grounding documents
   may include balanced Danish DynaWord, Folketing/Rigsarkivet, and admitted
   legal/public-sector sources, but must exclude LexDK and DBC.
5. Add a Danish campaign config/downloader/launcher, source caps, sharded
   retrieval, resumable generation, independent audits, exact finalization,
   decontamination, PII/source-copy checks, and publication receipts.

## Gemma 4 31B Magpie-style chat generation

DFM11 will use the Magpie self-synthesis method, not historical Magpie data.
No rows from `Magpie-Gemma2-Pro-200K-Filtered` or any other released Magpie
corpus are training inputs: those datasets were generated by older teacher
models and are consulted only for method, metadata, and filtering design.

The core Magpie observation is that an aligned model can generate a plausible
user query when decoding starts immediately after its native pre-user template.
The original work generated four million instructions and selected 300,000
high-quality instances; its public pipeline separately generates instructions
and responses, tags quality/difficulty/category/safety/language, and removes
near-duplicates. DFM11 adapts that process to the pinned fresh Gemma 4 31B IT
checkpoint at
`data/models/google/gemma-4-31B-it-fresh-20260604`.

### Language-balanced generation

Do not generate an uncontrolled pool and hope that half is Danish. Use two
independent, symmetric queues with separate seeds, counters, and receipts:

| Lane | Instruction-generation condition | Accepted quota |
|---|---|---:|
| Danish | A minimal native system condition requiring natural Danish, followed by the open native user-turn prefix | 50% |
| English | The equivalent minimal condition requiring natural English, followed by the open native user-turn prefix | 50% |

The condition controls only instruction synthesis. After extracting and
validating the generated user request, generate its assistant response from a
fresh native Gemma 4 conversation containing that user request but no repetitive
language-control system message. The final row therefore remains an ordinary,
self-contained Gemma-native `messages` conversation. Retain the exact
instruction-generation system condition in a separate top-level row field for
provenance and later stratified analysis; do not insert it into `messages`.

Enforce balance after filtering, not before it:

1. over-generate each lane independently and refill only the deficient lane;
2. require both the user request and assistant response to match the lane;
3. use Lingua as a high-confidence deterministic rejection gate, with a
   task-aware exception path for code, formulas, and very short outputs;
4. run an independent semantic language/coherence audit on uncertain rows;
5. stop only when both accepted-row quotas are met;
6. deterministically downsample the larger lane if necessary;
7. report both row balance and rendered-token balance, then adjust DFM11
   sampling weights so this Magpie slice is approximately 50% Danish and 50%
   English by tokens as well as exactly balanced by accepted rows.

Never fill a Danish shortfall by translating accepted English Magpie rows.
Translation would collapse the independently sampled intent distribution and
make the two halves paraphrastic rather than genuinely bilingual.

### Complexity-conditioned lanes

The same instruction-generation system condition may control linguistic
complexity, but keep four dimensions separate in metadata and sampling:

1. linguistic complexity of the user's wording;
2. cognitive difficulty of the requested task;
3. domain-expertise level;
4. requested response length and detail.

For example, a Danish instruction-generation prefix may say:

```text
<bos><|turn>system
Samtalen skal foregå på naturligt dansk. Den næste brugerbesked skal være
formuleret i enkelt, hverdagsnært sprog, men den må gerne stille et fagligt
krævende spørgsmål. Nævn ikke disse instruktioner.<turn|>
<|turn>user
```

Use symmetric English conditions and stable labels such as `accessible`,
`general`, `advanced`, and `specialist`. A provisional within-language mix is
20%, 50%, 20%, and 10%; freeze it only after the bilingual pilot measures
quality, diversity, and response-length effects.

The generation-only condition is removed before response generation. If the
generated user request happens to ask for a particular audience or response
style, Gemma 4 may follow it naturally, but the pipeline must not force response
complexity through a hidden system condition. The response teacher otherwise
chooses its own appropriate style, length, and complexity. Audit each
language-by-user-complexity cell independently and balance accepted rows, not
raw attempts.

### Native generation contract

- Verified locally on 2026-08-31: the pinned fresh Gemma 4 31B IT
  `chat_template.jinja` accepts an initial `system` or `developer` message and
  renders it as `<|turn>system`. Use exactly one initial system message for
  Magpie conditioning; do not inject system messages later in a conversation.
- Derive the pre-user prefix and stop-token IDs from the pinned Gemma 4
  tokenizer/template; do not hard-code a Gemma 2 or stale local template.
- Use raw token/completions generation for the unfinished user turn, stopping
  exactly at the native turn boundary. Reject leaked role/control tokens,
  missing boundaries, empty requests, and malformed Unicode.
- Render response generation through the pinned Gemma 4 native chat template.
- Preserve final data as native `messages`, not ShareGPT `from`/`value` rows.
- Store the exact generation-only condition separately, for example as
  `magpie_system_prompt`, alongside `language_lane` and
  `user_complexity_level`. This field is metadata and is not rendered as a
  training turn.
- Keep each complete rendered conversation within the active DFM11 context
  contract. Do not truncate either side to make a row fit.
- Record model revision, tokenizer hash, template hash, random seed, sampling
  parameters, lane, generation server version, and parent IDs in every row.

### Diversity and quality pipeline

Generate with a calibrated mixture of instruction temperatures rather than one
fixed decoding configuration. Select the final mixture only after a 10,000-row
pilot per language. Response temperature may be lower than instruction
temperature because intent diversity comes primarily from the generated user
turn.

Apply, in order:

1. structural, boundary, length, language, and special-token validation;
2. exact and normalized deduplication within and across languages;
3. embedding-neighbor deduplication against Magpie candidates, final DFM10
   instructions, and protected evaluation prompts;
4. intent, task-category, difficulty, safety, and required-knowledge tagging;
5. category-aware caps so generic advice and simple information questions do
   not dominate math, code, reasoning, writing, editing, planning, and Danish
   knowledge requests;
6. independent instruction-quality and response-coherence auditing;
7. stricter task-aware verification for math, code, exact-format, and factual
   claims;
8. a final stratified human-readable sample report before admission.

The initial production target is one million accepted conversations, 500,000
per language, subject to the pilot demonstrating sufficient diversity and
quality. Extend a calibrated subset into native multi-turn conversations of
2-6 user/assistant exchanges while preserving the same language and context
limit. Audit every supervised assistant turn and retain the complete native
history; do not flatten prior assistant turns into user text.

Based on observed local Gemma 4 31B throughput, a 20,000-row bilingual pilot is
roughly 4-12 B200 GPU-hours. One million accepted rows will likely require
1.5-3 million raw candidates after filtering and approximately 300-700 B200
GPU-hours for instruction generation, response generation, audit, retries, and
tail handling, or about two to five days wall time on eight B200s. Re-estimate
after the pilot rather than treating this range as a quota commitment.

### Implementation ownership

Implemented on 2026-08-31 as the reusable, self-contained Git submodule
`koolbardi`, with its own intended remote at
`https://github.com/schneiderkamplab/koolbardi.git`. It is not named after a
specific DFM version: DFM11 is its first consumer, but bilingual
self-synthesis, auditing, and dataset publication remain usable by later data
versions.

The upstream MIT-licensed code is checked out at commit `b734a368` under the
parent repository's ignored `external/magpie` path as a behavioral reference.
That checkout is deliberately not a submodule, dependency, import, vendored
component, or part of Koolbardi's history. The production implementation does
not use upstream's model-specific shell scripts, older serving assumptions,
notebook filters, or ShareGPT conversion path.

The intended repository structure is:

```text
koolbardi/
  README.md
  pyproject.toml
  src/koolbardi/
  configs/
  scripts/
  tests/
```

Runtime artifacts remain outside the source package under `data/koolbardi/`
and `logs/koolbardi/`. The initial implementation provides typed Pydantic/YAML
configuration, SQLite WAL `BEGIN IMMEDIATE` shard claims, full-shard retries,
atomic JSONL replacement, separate instruction/response/audit phases, native
template derivation, per-language post-audit quotas, deterministic language and
structure gates, semantic auditing, exact deduplication, native `messages`
output, token-limit rejection, and machine-readable receipts. Pilot and
provisional production configs target 10,000 and 500,000 accepted rows per
language respectively. Embedding-neighbor deduplication, protected-eval
matching, category-aware caps, richer task verifiers, and publication upload
remain admission work after the pilot; the current finalizer must not be
represented as completing those later gates.

### Koolbardi length contract before the pilot

Update, 2026-09-01. Confidence: high from direct inspection with the production
Gemma 4 template and the installed Transformers 5.12.1 API.

Do not launch the production pilot from commit `d891506` without correcting
token accounting. In this Transformers version,
`tokenizer.apply_chat_template(..., tokenize=True)` returns a
`BatchEncoding` by default. Calling `len()` on it returns the number of fields
(`2` here), not the number of tokens. Koolbardi's current finalizer therefore
does not enforce its intended 4K limit. Use `return_dict=False` and count the
returned token-ID list, or explicitly count `encoded["input_ids"]`. Add a
regression test that constructs both an accepted 4K-minus row and a rejected
4K-plus row with the pinned tokenizer/template.

The current implementation generates only one user/assistant exchange. The
runbook's 2-6-exchange multi-turn subset still requires a continuation phase;
it must not be inferred from the existing instruction/response phases. That
phase should use these controls:

1. Keep a hard, exact rendered limit of 4096 tokens and never truncate a turn.
2. Use a soft generation ceiling of 3968 tokens, leaving 128 tokens for API,
   tokenizer, and converter-version discrepancies. Final admission still
   re-renders with the pinned training tokenizer and rejects anything above
   4096.
3. Assign each candidate a rendered-token target band before generation. A
   suitable pilot mix is 20% at 512-1023, 35% at 1024-2047, 35% at
   2048-3071, and 10% at 3072-3968 tokens. Report and balance accepted rows by
   language, exchange count, and target band.
4. Sample a desired 2-6 exchange count, but before every user or assistant
   generation re-render the complete native history with
   `add_generation_prompt=True`. Set request `max_tokens` dynamically to the
   smaller of the row's remaining target budget and
   `3968 - prompt_token_count`; never reuse the one-turn fixed 3072-token
   response allowance.

### Koolbardi A4B pilot implementation update

Update, 2026-09-02. Confidence: high from direct end-to-end generation and
independent re-tokenization with the pinned Gemma 4 tokenizer.

The earlier 31B unfinished-user-prefix pilot specification above is
**superseded for the current 10,000-chat pilot**. The running pilot uses
`google/gemma-4-26B-A4B-it`, with 5,000 accepted Danish and 5,000 accepted
English chats. Direct completion from Gemma 4's unfinished native user turn was
tested with both rendered text and exact prompt token IDs. Both paths emitted
control-channel fragments such as `own-`, `way-`, and `thought` before or
instead of a usable request. Do not restore that path for this checkpoint.

Koolbardi now generates initial and follow-up user turns through explicit
generation-only native chat meta-requests. These prompts include the language,
complexity, length band, desired exchange count, and prior transcript where
applicable, but are retained only as hashes/metadata and never inserted into
the final training `messages`. Assistant turns similarly receive a temporary
budget-aware completeness instruction so Gemma closes each answer before its
per-turn cap; this instruction is also absent from final `messages`.

The exact 4K contract is now enforced in three places:

1. `apply_chat_template(..., return_dict=False)` extracts actual token IDs
   rather than taking `len(BatchEncoding)`, which was always `2` locally;
2. generation budgets distribute remaining tokens across all planned user and
   assistant turns instead of allowing the first answer to consume the row;
3. finalization independently re-renders the saved messages and rejects rows
   above 4,096 tokens rather than truncating them.

The final smoke generated and accepted one Danish and one English two-exchange
conversation. Stored and independently recomputed counts agreed exactly: 974
tokens for Danish and 887 for English. All four assistant turns passed the
per-turn judge. The production configuration is
`koolbardi/configs/dfm11-pilot-10k-a4b.yaml`; its 17,000 raw candidates are
organized in 512-row shards and balanced after audit to 10,000 accepted chats.

The original pilot runtime used one vLLM server on each of GPUs 0--3, ports
8100--8103, `gpu_memory_utilization=0.90`, `max_model_len=8192`, and
`max_num_seqs=128`. That concurrency setting is superseded by the measured
million-row campaign settings below.
The larger serving context is required because audit prompts include the
transcript; it does not relax the final 4,096-token data limit. vLLM must use
automatic heterogeneous attention selection because Gemma 4 has 256-dimension
local and 512-dimension global attention heads. Forcing FlashAttention selected
an incompatible FA2 path and failed on the 512-dimension heads. Use Triton only
for the MoE backend (`--moe-backend triton`), plus `--language-model-only` and
`--enforce-eager`; launch through the `audit` conda environment so CUDA tooling
is available.

Update, 2026-09-02. The million-row campaign preserves all 13,542 accepted
pilot rows and targets one million accepted conversations in each language.
The 4,096-way trial used `max_num_seqs=4096`, 32 instruction workers, and four
response and audit workers, each allowing 128 requests per server.
Initial-turn generation reached 4,090--4,095 live
requests per GPU, 81--83% KV-cache occupancy, and 21.6K--22.2K generated
tokens/s/GPU. The prior 512-request run peaked at 11.7% KV occupancy and about
9.8K generated tokens/s/GPU. Host available memory remained about 2.1 TiB.
The saturated first wave also caused approximately 1.3K--1.6K cumulative
preemptions per server, so compare sustained throughput and preemptions before
raising this limit further. Long response and audit phases intentionally retain
the lower aggregate 512 requests/server because their prompts and outputs use
substantially more KV per request.

The English pilot retained 8,421 of 8,500 audited rows (99.0706%), implying a
bare minimum raw factor of 1.00938. The preserved queue's 1.01 configuration
contained only 1,005,700 English candidates after overlapping pilot shard keys,
which projected below one million usable rows. English oversampling is therefore
1.05 for the million-row campaign. This adds only incremental shard keys and
does not discard or regenerate completed work.

Follow-up measurement showed that sustained 4,096-way instruction fan-out can
drive KV occupancy to 99--100%, create a waiting queue, and accumulate tens of
thousands of preemptions. Treat 4,096 as a measured upper-load bound, not the
normal target. A 182-second 3,072-way comparison using 24 workers sustained
18.3K generated tokens/s/GPU including shard-boundary idle periods and 55.4
completed 512-row shards/minute. It reached 78--80% peak KV occupancy with zero
waiting and zero preemptions. This matched the observed 4,096-way row throughput
(approximately 51--58 shards/minute) more efficiently, so 3,072 is the adopted
instruction setting. Optimize for sustained generated tokens/second and
completed rows, not `nvidia-smi` compute percentage or literal 100% KV
occupancy: A4B autoregressive decode uses only the active experts, consists of
many routing/small-GEMM kernels, and currently runs in eager mode without CUDA
graphs.

The resumable production command is:

```bash
cd /work/mimir/HRM-Text/koolbardi
scripts/run_campaign.sh configs/dfm11-pilot-10k-a4b.yaml
```

`reset-stale` recovers abandoned running claims. After correcting the root
cause of terminal failures, `reset-failed CONFIG --phase PHASE` resets only the
specified failed phase and its retry counter. The current campaign and its
four servers are isolated to GPUs 0--3; unrelated workloads on GPUs 4--7 must
not be inspected, signaled, or terminated.
5. Continue only when enough budget remains for one complete useful exchange.
   Reserve at least 64 tokens for the next user request, 192 tokens for its
   answer, and the native turn overhead. Otherwise end the conversation at the
   preceding complete assistant turn.
6. Treat generated length as an audit result, not merely a decoding setting.
   Reject or separately retry rows below their assigned band's minimum; do not
   use a large decoder `min_tokens`, which encourages padding and repetition.
   Prompts may request an appropriate detail level, but semantic completeness
   and absence of filler remain audit requirements.
7. Record prompt tokens, generated tokens per turn, final rendered tokens,
   desired/actual exchange count, target band, finish reason, and whether the
   row stopped for semantic completion or budget exhaustion.

With the native Gemma 4 template, direct measurement found approximately 11
template tokens for one complete exchange and about 10 additional template
tokens per further exchange. This overhead is small, but it must be counted
from the actual rendered history rather than approximated. The one-turn pilot
may retain instruction `max_tokens=512`, but response `max_tokens` should also
be derived from the rendered prompt and row target band so request-time context
overflow is impossible and the accepted length distribution is intentional.

## Workstreams

### 1. Folketing error correction

Keep DFM10's denoising, span-filling, and prefix-continuation families
unchanged. **Superseded, 2026-09-04:** the original error-correction workstream
required deterministic cleanup followed by only a 5,000-row admission gate.
The deterministic rebuild passed, but the user strengthened admission to a
strict-schema full audit whose finalizer removes every rejected row. Exact
requirements, counts, superseded generic-audit findings, recovery behavior,
paths, and commands live in
[DFM11 Folketing Error-Correction Repair](dfm11-folketing-error-correction.md).

### 2. Natural Instructions task selection

Convert the residual audit into a task-level policy rather than a global row
filter:

- exclude the 48 tasks with at least 50% sampled failures;
- re-audit the 74 tasks in the 25-49% band at 100 rows per task;
- retain cleaner tasks unless task-aware validation contradicts the generic
  judgment;
- preserve task definitions and expected output contracts in every audit.

Admission requires at least 85% usable examples per retained task, no systemic
prompt/target inversion, and exact validators for tasks with computable labels.
Estimated cost: 2-4 engineering hours and 0.2-0.8 B200 GPU-hours.

### 3. Legacy Danish back-translation cleanup

Retire legacy Tidsskrift BT, EUR-Lex BT/summary, and DOAB BT where grounded
replacements already provide the intended capability. Apply deterministic
completion and contract filters to DynaWord BT. Verify Kænguruen and Multi-Zebra
against their known answers rather than relying on free-form judging.

Each retained family must reach at least 90% usable under a task-aware delta
audit. Small sources that cannot meet the gate should be omitted rather than
regenerated. Estimated cost: 2-4 engineering hours and 0.2-1.0 B200 GPU-hours.

### 4. Native tool and agent trajectories

Re-audit DeepDive and repaired DOLCI with a trajectory-aware representation
that identifies whether the supervised assistant turn is an intermediate tool
call or a final natural-language response. The audit should see enough suffix
metadata to establish that an intermediate call receives a matching tool result
and eventually reaches a valid terminal answer, without training on future
turns in the prompt.

Native schema, call/result pairing, tool-name resolution, and JSON validity are
deterministic gates. Generic semantic judgment is secondary. Admission requires
100% structural validity and at least 90% usable sampled trajectories. Estimated
cost: 3-6 engineering hours and 0.4-1.6 B200 GPU-hours.

#### Proposed grounded arithmetic tool-use family

**Implementation and upload staging completed, 2026-09-03.** Add an offline-executed arithmetic tool-use family
derived from `TinyGSM/TinyGSM` and
`niklasm222/gsm8k-prolog-prover`. The purpose is to teach complete native tool
trajectories, not merely Python or Prolog code completion. Each admitted row has
this logical structure:

1. a user asks the original word problem;
2. an assistant emits exactly one Gemma-4-native structured call to either
   `execute_python` or `execute_prolog`;
3. a matching `role=tool` message contains a result computed before training;
4. a terminal assistant response uses that result and contains exactly one
   canonical `\boxed{...}` answer, with no prose outside the box.

The source program belongs in the tool-call argument. The tool result is
environment output and must never be rewritten as an assistant message. Calls,
results, IDs, declarations, and final responses use the repository's existing
OpenAI-shaped message schema and render through
`data_io/chat_templates/gemma4_native_chat.jinja`. This creates both a
tool-call target and a post-result final-answer target while avoiding loss on
the simulated environment response.

The user-visible contract should explicitly say that, after using the tool, the
assistant must return only `\boxed{...}`. This is the shared strict form: the
repository GSM8K scorer checks the last boxed value before numeric parsing, and
the MATH scorer extracts the last boxed expression. For example, a tool result
of `{"result": 4}` must lead to the terminal assistant target `\boxed{4}`,
not `The answer is 4`, `Final answer: 4`, or a second derivation. Retain exact
symbolic forms inside the box when they are authoritative; canonicalize
GSM8K-aligned results to their expected integer representation.

Implementation gate, 2026-09-03: the evaluation copy of the native template
currently handles mapping-valued `role=tool` content before its generic
sequence branch, while the `data_io` copy does not. A direct render with
`content: {"result": 4}` therefore succeeds under the evaluation template but
fails under the current training-data template. Reconcile the two template
copies and add an exact render regression test before tokenization; do not work
around the mismatch by changing structured results into assistant text or a
different response shape.

**Superseded on 2026-09-03:** the canonical `data_io` template now applies the
mapping check before the sequence branch and is byte-identical to the tested
Mathagentic template. The complete source was then tokenized through that
canonical path with zero rejected targets; the gate is satisfied.

The two sources require different admission policies:

- `gsm8k-prolog-prover` has 7,473 cleaned GSM8K-train programs. Join each
  question to the authoritative GSM8K-train numerical answer, execute
  `solve(X)` with SWI-Prolog under a timeout, canonicalize rational/decimal
  output, and retain only exact numerical matches. Reject any row that matches
  GSM8K test or another protected evaluation split. The HF derivative does not
  currently declare a dataset license, so publication/admission also requires
  an explicit provenance/license receipt even though the upstream GSM8K data
  is MIT-licensed.
- `TinyGSM` contains 11,846,109 MIT-licensed question/Python pairs and is a
  candidate reservoir, not an admit-all source. A seeded 200-row inspection
  found 200/200 syntactically parseable single-function programs, but also
  concatenated independent problems, irrelevant clauses, and incorrect
  implementations; one of the first five public rows computes the quadratic
  height with the wrong sign. Execute only in a locked-down, resource-limited
  worker after an AST allow-list. Require one coherent question, one finite
  scalar return value, source-question/docstring agreement, independent
  question/program/result verification, protected-eval decontamination, and
  duplicate removal. Never use captured `print` output as the answer when a
  return value exists.

Start with a stratified TinyGSM pilot, then cap the accepted TinyGSM contribution
at approximately 500,000 distinct trajectories or 0.5B rendered tokens,
whichever comes first. Revisit that cap only after held-out execution validity,
semantic correctness, duplicate rate, rendered-length distribution, and
tool-format smoke evaluations are reported. The Prolog family may use all
verified distinct train rows, but should not be inflated enough to dominate
general arithmetic or native-tool supervision.

Required converter receipts include upstream revision and file hashes, row-level
source IDs, executor version, exit status, timeout/error class, canonical tool
result, matched gold answer where available, all rejection counters, dedup and
decontamination reports, rendered token counts, and a deterministic rerun test.
No runtime executor is needed during pretraining; inference still requires an
orchestrator to execute calls and return real tool messages.

The standalone implementation is owned by the `mathagentic` submodule. It
provides pinned HF downloads, Python `solve()` normalization and restricted
execution, Prolog `solve/1` execution plus GSM8K-gold verification, atomic
sharded conversion, structural validation, a bundled Gemma 4 native template,
and direct HRM task-array tokenization. The capped 500,000-row TinyGSM
candidate audit completed with 367,749 semantic accepts, and all 7,473 Prolog
rows passed execution/gold verification. Separate upload-staging packages are
documented in [DFM11 Mathagentic Export Packages](dfm11-mathagentic-exports.md).
Manual project approval to publish both packages was recorded on 2026-09-03.
DFM11 samples all 7,473 Prolog rows at repeat 2 and deterministically caps
TinyGSM at 50,000 distinct rows per epoch with repeat 1. DFM11 must retain
`data.target_only=true`: only then are definitions and environment-owned tool
results masked as instruction context while assistant calls and boxed answers
remain response targets.

The complete published reservoirs were tokenized on 2026-09-03 into
`data/tokenized_dfm11`: 375,222 trajectories, 750,444 assistant targets, and
207,326,230 stored tokens across five shard-level tasks, with no 4,096-token
rejections. This is a complete backing reservoir only. DFM11 epoch sampling,
including the TinyGSM 50,000-row cap and Prolog repeat two, remains pending.

### 5. Sapient math and dialogue families

Audit math under separate `direct` and `cot` contracts:

- direct targets may be concise but must match the verified expected answer;
- CoT targets require coherent reasoning and exactly one canonical final answer;
- symbolic/final-answer verification remains authoritative where available;
- PRM or LLM judgments assess reasoning quality, not direct-answer verbosity.

Run a full task-aware audit of the small repaired QReCC-II family and drop it if
its observed 47% defect rate persists. For AMPS Mathematica, DMMath, FLAN
dialogue, and other very large families, identify defective task strata and
reduce caps or exclude strata rather than attempting wholesale regeneration.
Estimated cost: 4-8 engineering hours and 2-8 B200 GPU-hours for stratified
audits. Any proposal for full-family LLM auditing requires a separate compute
budget and expected-value argument.

### 6. Remaining one-pass English sources

Add task-specific deterministic checks for ASSET, IF-SFT, AESLC, CoEdIT, Tulu
algebra, TextbookReasoning, regular QReCC, and related retained sources. Re-audit
only rejected or borderline strata. Prefer dropping malformed rows to rewriting
authentic targets. Estimated cost: 4-8 engineering hours and 1-4 B200 GPU-hours.

### 7. Mimir and persona verification tail

Use known answers and structural validators for answer-contract calibration,
DROP, event/coreference, and IFEval. Preserve Danish persona chats unless a
deterministic structural issue is found. Their 97.6% aggregate usability does
not justify broad regeneration. Estimated cost: 2-4 engineering hours and
0.2-1.0 B200 GPU-hours.

## Execution sequence

### FineInstructions grounded-chat diversity update

The controlled-mode generation, safe truncation salvage, bilingual contract,
exact 500K quota, immutable release, and later balanced-extension procedure now
live in [DFM11 FineInstructions Grounded Chats](dfm11-fineinstructions-grounded-chats.md).

1. Wait for the owning workstream to integrate
   `dfm10-synthetic-values-model-charter-da`, rebuild the union as needed, and
   finish authoritative DFM10 resampling.
2. Validate and fingerprint that post-Model-Charter DFM10 snapshot.
3. Run the 20,000-row bilingual Gemma 4 31B Magpie pilot and freeze its
   generation, language-control, metadata, and filtering contracts.
4. Implement CPU-only source/task filters and produce a proposed DFM11 delta.
5. Run task-aware audits only for strata that cannot be decided
   deterministically.
6. Run Magpie production and materialize repairs under separate names;
   validate schema, provenance,
   deduplication, context length, and Gemma-native formatting.
7. Build `data/tokenized_dfm11` without modifying the DFM10 union.
8. Produce row/token deltas by source and category before assigning repeats or
   caps.
9. Sample a DFM11 pilot and compare source balance against DFM10.
10. Run format, tool-use, math-contract, Danish-language, and memorization smoke
   checks before full sampling.
11. Sample the intended epochs only after all admission receipts and the final
   DFM10-to-DFM11 delta report pass.

## Budget and stop conditions

The minimum practical DFM11 cleanup is workstreams 1-4 and 7: approximately
one to two engineering days and 1-5 B200 GPU-hours, excluding filesystem-heavy
token-tree rebuilding and sampling. The complete plan is approximately three
to five engineering days and 4-15 B200 GPU-hours if the targeted audits confirm
that deterministic filtering is sufficient. Magpie generation is a separate
major production budget: initially 4-12 B200 GPU-hours for the pilot and an
estimated 300-700 B200 GPU-hours for the proposed one-million-row corpus.

Stop and reconsider a workstream when:

- repair requires broad synthetic rewriting without retained provenance;
- projected generation exceeds 100 B200 GPU-hours without a measured capability
  benefit;
- a task-aware audit shows that the generic residual judge produced most of
  the apparent failures;
- the source contributes too few unique tokens to justify repair;
- the replacement worsens source diversity or creates benchmark contamination.

## DFM10 non-regression rule

Before the boundary, DFM11 work waits and does not inspect transient resampling
outputs as its baseline. After the Danish Model Charter integration and
resampling receipts are complete, DFM11 may read and fingerprint DFM10
artifacts but must not mutate them. DFM10 training proceeds from that finalized
snapshot while DFM11 curation is a separate successor effort. Any later
comparison must report both the exact data delta and whether observed changes
come from filtering, replacement, resampling, or additional training tokens.

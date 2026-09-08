# Knowledge Bundle Update Log

## 2026-09-08 - Origin reconciliation audit

- Restored local work after fast-forwarding main; retained the recovery stash.
- Preserved the superseded upstream Nemotron assessment in a separate historical
  concept instead of losing it when restoring the local replacement plan.
- All pinned submodule revisions are now available and checked out, including
  Mathagentic `00f3ded`; existing dfm-evals working changes remain intact.

## 2026-09-08 - DFM11 portability boundary

- Added a focused DFM11 machine-to-machine bootstrap runbook: Git transfers
  code and pinned submodules, while training requires either the authoritative
  sampled corpus or the exact DFM10 tokenized base plus DFM11 additions.
- Recorded that this host currently has the 44 GB DFM11 additions but not the
  DFM10 tokenized base, final DFM11 union, or sampled DFM11 corpus.

## 2026-09-07 - Danish FineInstructions publication and DFM11 admission

- Published all 503,740 accepted Danish grounded chats and their matching
  portable pairs as `schneiderkamplab/dfm11-fineinstructions-da`; admitted all
  chats at repeat one and tokenized them into 663,788,470 stored tokens.
- Published and remotely verified the selected Danish 2B query templatizer,
  4B template instantiator, and both exact helper-training datasets. The local
  aggregate DFM11 union remains blocked only by the absent DFM10 tokenized base.

## 2026-09-07 - DFM10 XXL diagnostic findings

- Analysis of the 100 step-450500-to-451000 snapshots found finite but severely
  ill-conditioned behavior: very large internal L residual streams are hidden
  by final RMS normalization, backward amplification is concentrated in early
  physical blocks, and L attention gates and Q/K scales are strongly
  saturated. Recurrent injection itself is stable and is not the leading
  intervention target.

## 2026-09-07 - Recurrent-depth stability diagnostics

- Corrected Danish chat capacity for the measured controlled-mode tail: the
  top-80/560K-pair pass cannot fill the least-represented mode, so completion
  now uses the planned top-112 expansion and a 700K audited-pair target.
- Replaced modulo-based balanced chat assignment with deterministic
  deficit-targeted assignment. Existing unused audited pairs now fill only
  underrepresented modes; deeper retrieval remains a true capacity fallback.
- Added a focused technical reference for the XXL effective backward depth,
  Jacobian-growth hypothesis, residual and recurrent-injection scaling options,
  trainable and scheduled gates, operational safeguards, and controlled
  experiment order.
- Documented the null-by-default per-cycle/per-layer diagnostics for activation,
  residual, gradient-amplification, parameter, and optimizer-state statistics.

## 2026-09-06 - Optimized Qwen3.5 helper-training runtime

- Recorded the initial Danish production yields (665,698 raw pairs, 231,941
  audited pairs, 214,504 chats), replaced the stale 700K and optimistic 525K
  planning estimates with a measured 560K audited-pair capacity target for 500K
  chats, and added resumable top-80 retrieval with a top-112 fallback.
- Added structured JSON instantiation and a Danish-specific independent pair
  audit after held-out tests exposed malformed output and an overly permissive
  generic judge. The initial eight-GPU Danish production pass is running, while
  the final 500K chat release remains fail-closed on its audited-pair minimum.
- Changed the Danish handoff to extend and inline-audit every currently accepted
  pair immediately. The audited-pair minimum still gates final 500K release
  completion, not incremental resumable chat generation.
- Increased the Danish instantiation queue to 32,768 aggregate requests after a
  production measurement showed underfeeding. The resumed run saturates GPU
  compute and skips prior deterministic decisions while retrying only transport
  failures.
- Qualified the final 100,000/5,000 Danish instantiator labels as suitable for
  helper distillation but not direct general SFT, and recorded the verified
  FSDP1 activation-checkpointed native-BF16 batch-two training path.
- Recorded that the instantiator early-stopped after epoch four and exported
  the restored epoch-two best checkpoint rather than the overfit final epoch.
- Resumed Danish Qwen3.5-4B instantiator SFT from complete epoch-1
  `checkpoint-12868` with full Trainer state in `qwen`; measured approximately
  0.39 s/step instead of 2.3 s/step. The resumable wrapper now skips completed
  generation/audit stages before validating the final mix and selecting the
  latest complete checkpoint.
- Created and verified the dedicated `qwen` environment: Conda owns CUDA 13.2
  and native build/runtime libraries, `uv pip` owns Python packages, and both
  FLA gated-delta and source-built causal-convolution kernels pass B200
  forward/backward smokes. The reproducible installer is
  `fineinstructions/scripts/create_qwen_conda_env.sh`.

## 2026-09-05 - Danish FineInstructions audited-target recovery

- Implemented `independent-v3` full-pool filtering and launched the resumable
  production supervisor. The calibrated replay accepted 315/475 positives and
  25/25 negatives; final helper supervision now requires exactly 100,000/5,000
  independently accepted in-limit rows with per-row audit provenance.
- Qualified the 70.6% independent-gate result: it mixes genuine defects with
  systematic Qwen rubric errors. The revised plan is calibrated full-pool
  independent filtering plus closed-loop expansion to 100,000 accepted
  in-limit positives, followed by a separate 95% release sample.
- Corrected the Danish FineInstructions production runbook: a fixed raw-label
  target cannot substitute for the audited-positive target. The supervisor now
  generates and incrementally audits additional unique candidates until the
  required 120,000 positives are retained.
- Recorded the subsequent exact 100,000/5,000 materialization and independent
  quality failure: Qwen2.5-14B accepted 353/500 rows (70.6%), so helper training
  remains blocked on semantic remediation rather than a lowered threshold.

## 2026-09-05 - Danish FineInstructions qualification correction

- Fixed direct excerpt validation, terminal deterministic-failure handling, and
  process-all qualification semantics after the v4 run repeatedly reported
  misleadingly low compatibility.
- Recorded the clean v5 receipt: 19,827 candidates, 23.29% valid positive yield,
  and 67.77% document coverage. Both gates passed and production retrieval was
  released; semantic gate failures now stop rather than retry unchanged work.

## 2026-09-04 - Danish FineInstructions retrieval recovery

- Recorded two failed 2,000-document qualifications against the undersized
  50,000-template silver bank and restored the omitted 500,000-template
  production-templatization stage.
- Separated positive and negative silver quotas, corrected negative-label audit
  semantics and terminal resumability, and added best-checkpoint helper-model
  training before restarting the gated pipeline on GPUs 4-7.
- Replaced an OOMing templatizer microbatch of eight with microbatch four and
  two-step accumulation, preserving the effective global batch of 32 while
  retaining at least 47 GiB of observed B200 headroom.
- Verified power-loss recovery after the templatizer had completed: its best
  checkpoint and 265,669 clean production templates survived, and the resumed
  append-only stage skipped durable successes and returned to normal throughput.
- Reassigned all eight B200s to Danish FineInstructions and expanded every
  parallelizable remaining inference, retrieval, generation, audit, and 4B SFT
  stage while preserving the completed templatizer receipt.

## 2026-09-04 - Controlled Koolbardi publication and DFM11 admission

- Finalized 535,930 Danish and 528,926 English audited controlled chats,
  totaling 2.313B native rendered tokens, while retaining all qualifying
  surplus rows and preserving minimum complexity-by-length quotas.
- Published 32-shard language-specific packages as
  `schneiderkamplab/dfm11-koolbardi-da` and
  `schneiderkamplab/dfm11-koolbardi-en`, recorded exact Hub revisions, and
  admitted both complete releases to DFM11 at repeat one.
- Added an independently validated package builder and documented the compact
  public schema, provenance, residual risks, and incremental native-template
  tokenization path.
- Tokenized all 64 release shards into 3,366,675 assistant targets and 5.316B
  stored prompt-plus-target tokens with no 4K skips. Hardened incremental input
  discovery to ignore package metadata and avoid spawning workers for already
  complete outputs.

## 2026-09-04 - English FineInstructions publication and DFM11 admission

- Published the complete 500K-pair/500K-chat English grounded
  FineInstructions release as `schneiderkamplab/dfm11-fineinstructions-en`.
- Materialized the approved 316,022 controlled plus source-balanced 100,000
  legacy chat selection and tokenized it into 1.034B stored tokens at repeat 1.
- Recorded that this host lacks the inherited DFM10 tokenized base needed to
  construct and sample the aggregate DFM11 union.

## 2026-09-04 - Full DFM11 Folketing error-correction audit

- Deterministically validated all 3,105,440 DFM10 Folketing error-correction
  rows and retained 2,548,956 whose complete source/target relationship is
  exactly explained by 1-8 declared OCR substitutions and whose targets pass
  conservative text-quality filters.
- Superseded the generic 60.24%-usable sample judgment after establishing that
  it incorrectly rejected intentionally sparse corrections. A task-aware,
  strict-JSON-schema 5,000-row audit passed at 97.7% with no judge errors.
- Started a resumable full audit on four Gemma 4 26B A4B vLLM servers. The
  launcher now defaults to stopping after decision generation. Materializing
  the rejection-filtered package and tokenizing it remain explicitly deferred.
- Superseded that temporary deferral after explicit user approval. Added and
  launched a post-audit pipeline that materializes only accepted rows, creates
  and validates a self-contained HF package, uploads and remotely verifies it,
  pins its revision, and tokenizes it into the DFM11 additions store.
- Replaced the inherited Folketing error-correction prefix in DFM11 policy and
  capped the 13-shard replacement at 75,000 rows per shard, repeat one: at most
  975,000 rows per epoch. Final union construction remains conditional on the
  absent `data/tokenized_dfm10` base.

## 2026-09-03 - DFM11 Mathagentic upload staging

- Completed the strict-schema semantic audit of 500,000 TinyGSM candidates:
  367,749 accepted and 132,251 rejected, with no unresolved request failures.
- Materialized two deterministic, checksummed packages under `exports_dfm11/`:
  367,749 audited TinyGSM-Python trajectories and 7,473 execution/gold-verified
  GSM8K-Prolog trajectories.
- Validated every packaged row and verified both nested tool schemas through
  the Hugging Face streaming JSON loader.
- Recorded manual approval to publish both packages. DFM11 uses every Prolog
  row at repeat 2 and caps TinyGSM at 50,000 distinct rows per epoch with
  repeat 1; publication still contains every accepted source row.
- Uploaded and byte-for-byte verified both packages at final Hub commits
  `1d32034d3b2467e51a6128b2cb249852969f17d0` (Prolog) and
  `17a3df5ccdd70ce71983485c6c48cce54b60f05e` (TinyGSM), with receipts under
  `logs/dfm11_mathagentic_upload_receipts.jsonl`.
- Added direct compressed-shard and bounded parallel tokenization to
  Mathagentic, then tokenized both complete reservoirs into
  `data/tokenized_dfm11`: 375,222 rows, 750,444 assistant targets, and
  207,326,230 stored tokens with no 4K skips. Sampling remains pending.
- Reconciled the canonical and package-bundled Gemma templates for structured
  mapping-valued tool results. Exhaustive verification found exactly one call
  target and one post-result boxed-answer target for every Mathagentic row and
  recorded the conventions of the other structured tool families inherited by
  DFM11.
- Identified Glaive duplicate `call_0` handling and ToolACE last-call-only
  response binding as high-priority DFM11 re-conversion risks. Added lower-risk
  canonicalization and validation actions for Nemotron Agentic, DFM8 synthetic
  tool calls, OpenHermes, xLAM, and terminal-agent data.

## 2026-09-03 - DFM11 grounded arithmetic tool-use proposal

- Proposed an offline-executed Gemma-4-native tool trajectory family from
  TinyGSM Python programs and the cleaned GSM8K Prolog corpus.
- Required exact execution/gold checks for Prolog and a capped, independently
  verified admission path for noisy TinyGSM rather than wholesale ingestion.
- Defined the canonical assistant-call, tool-result, terminal-answer structure,
  sandboxing, decontamination, and reproducibility receipts.
- Implemented the independently versioned `mathagentic` package with pinned
  downloads, converters, validators, native rendering, direct HRM array
  tokenization, tests, and its own OKF bundle. Full conversion remains pending.

## 2026-09-03 - FineInstructions controlled continuation modes

- Froze the existing 183,978 English grounded chats as the intentionally
  reading-comprehension-heavy first segment and enabled balanced, deterministic
  assignment of 20 interaction modes for the remaining campaign.
- Kept the mode implementation independent of Koolbardi while adapting its
  documented ontology, supplied-material safeguards, retained metadata, and
  explicit adherence audit.
- Added safe complete-exchange salvage for token-capped structured chat output,
  avoiding whole-row rejection when earlier exchanges are complete and valid.
- Set FineInstructions output to 500K English plus 500K Danish, with exact
  accepted mode quotas for controlled rows, immutable named final releases,
  and append-only state that supports later balanced expansion.
- Split the executable FineInstructions balance and extension contract from the
  oversized DFM11 aggregate plan into its own indexed OKF concept.

## 2026-09-04 - FineInstructions English 500K finalized

- Finalized the immutable balanced English release at exactly 500,000 aligned
  pairs and chats. Recorded that DFM11 conversion/tokenization/sampling and Hub
  packaging remain pending, including removal of local absolute provenance
  paths and creation of a dataset card, checksums, and upload receipt.
- Compared every legacy and controlled chat structurally. Controlled chats have
  exact mode diversity and substantially less repeated turn text, but are much
  shallower and retain the initial pair's defects; same-checkpoint audit scores
  do not establish better semantic quality, so independent stratified review is
  still an admission and upload gate.
- Proposed an initial non-duplicating DFM11 mix of all 316,022 controlled chats
  plus 100,000 source-balanced legacy chats at repeat one. Corresponding pairs
  remain excluded; only a separately audited 50K-100K unmatched-pair ablation
  should test whether pair-only coverage adds value.

## 2026-09-02 - FineInstructions templatizer concurrency result

- The completed 4,096-request/server wave saturated KV cache and was slower
  than the earlier 512-request/server wave: about 63 versus 93 completed
  requests/s aggregate, and about 23K-25K versus 50K generated tokens/s/GPU.
- Marked 4,096 as a stress ceiling rather than a production default. A future
  controlled sweep should compare 1,024, 2,048, and 3,072 using committed
  rows/s, generated tokens/s, and sustained KV occupancy.
- Benchmarked retrieval batches 32/64/128 at 185/194/196 seconds for the same
  12K candidates. Replaced the single-GPU batch-16 retrieval with four
  deterministic batch-32 shards and an atomic validated merge; steady aggregate
  throughput increased from about 9 to 72.5 documents/s.
- Recorded the incomplete Danish artifact qualification: 93/100 parseable
  templates but visible Danish/semantic defects, only 62 retrieval candidates
  covering 44/100 documents, and no completed instantiation or end-to-end
  audit. The Danish production campaign remains gated.

## 2026-09-02 - Koolbardi A4B bilingual pilot

- Promoted the campaign to one million accepted chats per language without
  discarding the 13,542 accepted pilot rows. Measured phase-specific
  concurrency reached 4,090--4,095 short requests/GPU, 81--83% KV occupancy,
  and 21.6K--22.2K generated tokens/s/GPU; long response/audit phases remain
  at an aggregate 512 requests/GPU.
- Raised English oversampling from 1.01 to 1.05 after the measured 99.0706%
  usable rate and preserved shard overlap projected fewer than one million
  usable rows. Initialization adds only new shards.
- Replaced the preempting 4,096-way instruction setting with 3,072. A
  182-second comparison sustained 18.3K generated tokens/s/GPU and 55.4
  shards/minute, peaked at 78--80% KV occupancy, and had no waiting or
  preemptions.
- Recorded that sustained 4,096-way instruction concurrency eventually filled
  KV cache to 99--100% and caused preemption. Future tuning should compare a
  3,072-request target and optimize generated-token throughput at 70--85% KV
  occupancy rather than maximizing cache occupancy itself.
- Recorded the verified Gemma 4 26B-A4B 10K bilingual pilot contract,
  superseding unfinished-user completion for this checkpoint.
- Documented exact 4K accounting, distributed per-turn budgets, vLLM runtime
  settings, smoke results, and terminal queue recovery.
## 2026-09-01 - Koolbardi operational runbook

- Added the verified end-to-end Koolbardi procedure covering submodule setup,
  `uv pip` installation, eight-server vLLM launch, atomic instruction/response/
  audit phases, status and stale-claim recovery, balanced finalization, output
  receipts, and the remaining DFM11 admission boundary.

## 2026-09-01 - DFM11 FineInstructions operating runbook

- Added a focused OKF runbook for the DFM-owned FineInstructions submodule,
  covering initialization, dependency installation, fail-closed query/document
  manifests, canonical extraction, the DFM-owned Gaussian retrieval index,
  instantiation contracts, audit gates, token budgeting, and current pending
  implementation stages.
- Recorded the required `--base-dir ..` extraction argument, the local-only
  `a4442c2` submodule commit and push ordering, and the separate model-artifact
  use decision required before production.

## 2026-09-01 - DFM-native FineInstructions replacement

- Superseded and removed the proposed upstream FineInstructions Nemotron
  admission, including its downloader entry, materializer, config, and tests.
  DFM11 retains no upstream Nemotron rows, real-query rows, FineTemplates, or
  prebuilt FineTemplates index.
- Added `schneiderkamplab/fineinstructions` as an Apache-2.0 submodule. Its
  initial package enforces approved query/document source manifests, canonical
  streaming extraction, pinned released model revisions, strict excerpt
  expansion, and a new DFM-owned FAISS index using global-plus-five Gaussian
  document representations.
- The learned artifacts remain subject to a model-use decision because their
  Hugging Face cards declare no licenses. Production generation and judging
  are not yet represented as complete.

## 2026-09-01 - DFM11 FineInstructions Nemotron admission policy

- Registered the pinned FineInstructions Nemotron metadata without exposing
  the generic downloader to its roughly 2TB payload, and added a deterministic
  score-5 selective materializer with separate review/admitted outputs.
- Set an initial 3B rendered-token cap, repeat one, and fail-closed license,
  PII, source-copy, and benchmark-decontamination admission gates. Recorded
  that the source has no declared dataset license and preserves substantial
  excerpts from Common-Crawl-derived documents.
- Defined FineInstructions clustering as a diversity/sampling mechanism for a
  20K seeded-chat pilot, not a method for concatenating independent questions;
  any admitted chats must be freshly generated and turn-wise audited.

- 2026-08-31: Implemented the standalone `koolbardi` package for the DFM11
  bilingual Magpie-style campaign. Koolbardi is an independently versioned
  submodule targeting `schneiderkamplab/koolbardi`; the ignored upstream
  Magpie checkout remains reference-only. Added native Gemma-template
  derivation, atomic SQLite shard claims, all-or-nothing retries, separate
  generation/response/audit phases, bilingual post-audit quotas, configs,
  launchers, finalization receipts, and tests.

- 2026-08-31: Started the DFM10 XL continuation from the verified DFM9
  2,127,489-step epoch-8 boundary using DFM10's ninth sampled index set. The
  exact 354,595-step epoch ends at 2,482,084; full evaluations are scheduled
  every 50K steps and at the endpoint.

- 2026-08-31: Finalized DFM10 at 72 published packages and 15,746 tokenized
  tasks. The ten-epoch production sample contains 92,658,813,451 tokens per
  epoch; a resumable transfer of its 878 GB training directory was launched to
  the Mimir workspace.

- 2026-08-31: Added a DFM11 Magpie-style chat program using only the
  self-synthesis method, never historical Magpie rows. The pinned Gemma 4 31B
  teacher generates separate Danish and English lanes; accepted quotas are
  balanced 50/50 after language, quality, diversity, deduplication, and
  task-aware audits, with a 20,000-row pilot before a proposed one-million-row
  production corpus.

- 2026-08-31: Deferred residual quality cleanup to DFM11 so DFM10 training can
  start without another curation cycle. The DFM10 freeze boundary occurs only
  after the separate workstream integrates the audited Danish Model Charter
  package and completes authoritative resampling. The DFM11 plan covers
  Folketing gates, Natural Instructions selection, legacy Danish BT retirement,
  task-aware tool/math audits, English filters, and Mimir verification tails.

- 2026-08-31: Recovered the MedQuAD English/Danish campaign after its original
  corpus-level completeness gate rejected 16,027 fully translated and audited
  pairs because 269 of 16,296 candidates remained incomplete. Candidate
  coverage is now informational; 12,472 independently accepted pairs are being
  tokenized in both languages, while row-level structural and quality gates
  remain fail-closed.

- 2026-08-31: Compared the DFM8 XL 1.65M EMA checkpoint with the completed
  DFM9 2,127,489-step endpoint using finalized W&B averages. Standard remained
  flat, but DFM, EuroEval, and every headline section regressed; recorded 1.65M
  as the recommended DFM10 continuation baseline, with DFM9 retained only as
  an optional short A/B branch.

- 2026-08-30: Added a detached, lock-safe finalization and publication chain
  for the four Mimir benchmark campaigns. It waits for all 1,024
  generation/audit shards, applies normalized-exact decontamination and
  validation, reports rather than blocks on quota shortfalls, validates and
  remotely verifies four independent Hugging Face packages, then tokenizes and
  integrates them into DFM10.

- 2026-08-30: Applied equal `max_per_file: 1000000` sampling caps to all four
  Folketing-derived task families. Deferred regenerating the ten DFM10 epochs
  until the active Mimir IFEval/BoolQ/DROP/event campaigns and queued
  English/Danish MedQuAD adaptation finish; the current sampled corpus remains
  the explicitly documented uncapped snapshot.

- 2026-08-30: Implemented and queued the pinned MedQuAD English/Danish medical
  QA campaign. The 16,296 candidate pairs preserve official source URLs and
  medical metadata; a guarded eight-GPU Gemma 4 31B translation and independent
  audit pass will produce separately selectable repeat-1 English and Danish
  subsets before tokenization and lock-protected DFM10 integration.

- 2026-08-30: Queued six ordered post-reconciliation DFM10 quality-audit
  stages behind the active Mimir campaign. Added exact token-array sampling,
  per-task stratification, persistent eight-GPU judging, atomic status,
  resumable partitions, source-completeness gates, and final admission gates
  for the six unfinished persona/Mimir packages. Subsequently made the
  combined English/Danish MedQuAD campaign an explicit predecessor so the two
  waiters cannot race for GPUs after Mimir exits.

- 2026-08-30: Finalized, tokenized, published, and integrated the 150,000-row
  Mimir answer-contract corpus after a 1,596/1,600 usable E4B audit with zero
  judge errors. Added a production runbook and launched the verifier-backed
  IFEval, BoolQ, DROP, and event/coreference programs through a resumable shared
  1,024-shard queue containing 990,000 grounded candidate requests.

- 2026-08-30: Staged DFM10's first narrow medical tranche for the next union
  rebuild: 13,203 pinned
  CC-BY-4.0 ELRC English-Danish pairs became 26,406 bidirectional rows, and
  1,602 MIT synthetic NHS notes became 4,756 grounded classification/span
  rows after identifier redaction and encoding repair. The two sources add
  about 6.68M sampled Gemma-native tokens per epoch. Real-row inspection also
  established that ELRC contains substantial generic EU-policy prose, so its
  prompts no longer claim every row is medical and its weight remains modest.

- 2026-08-30: Added a license-gated DFM10 medical-data plan. It records the
  explicit Laegehaandbogen/Patienthaandbogen TDM exclusion, identifies the
  already-local 27.07M-token CC0 Health Hovedstaden corpus, and ranks Danish
  and English Hugging Face candidates with provenance, privacy,
  decontamination, and medical-safety gates.

- 2026-08-30: Finalized and published the 4,438-row Domsdatabasen grounded-chat
  package and the expanded 37,119-row FrameNet and 13,055-row Danish lexical
  sentiment packages. All three passed local validation and complete remote
  file-set verification. The DFM10 export inventory now records 61 uploaded,
  zero ready-for-upload, and six work-in-progress packages; lock-protected
  union watchers serialize Doms and eventual persona activation behind older
  tokenization work.

- 2026-08-30: Reconciled all 61 materialized DFM10 exports against their live
  Hub package manifests. Republished the final 37,135-row FrameNet, 13,698-row
  lexical-sentiment, and unchanged-count 49,787-row Danish Wikipedia chat
  builds after detecting stale remote shard hashes. All 61 now match local row,
  source, shard-size, and shard-SHA metadata exactly.

- 2026-08-30: Kept Danish persona chats fail-closed after the first complete
  campaign pass retained 1,834 seven-turn chats against its 2,000-row minimum.
  The resumable retry fills only incomplete generation/audit records; if that
  does not close the 166-row deficit, production requires a separately audited
  deterministic seven-turn top-up rather than weakening the distribution gate.

- 2026-08-30: Superseded the persona seven-turn top-up requirement by explicit
  owner approval. The final floor is 1,850 independently accepted rows, met by
  the existing 1,852; all other per-length gates and the original 25,000
  deterministic candidates remain unchanged.

- 2026-08-30: Finalized, tokenized, published, and integrated the approved
  22,284-row Danish persona package. It contributes 110,290 supervised turns
  with zero tokenization skips; remote revision
  `ed6f54ad347a6e2d0ced84abafaa5d46bae83198` matches the local package
  manifest and shard checksum. The canonical union now has 15,734 tasks.

- 2026-08-30: Promoted the completed Tidsskrift campaign from stale WIP state.
  Published and remotely verified 132,444 grounded SFT rows and 23,213 grounded
  chats; all 64 materialized DFM10 packages now match their Hub manifests.
  The Mimir answer-contract stratified audit also completed with 1,596/1,600
  usable samples and no judge errors, leaving final admission/build pending.

- 2026-08-30: Superseded partial terminal closure for grounded Tidsskrift
  SFT/chats. All shards now require 100% structural generation/audit coverage;
  retained responses are repaired and incomplete done markers are requeued
  without weakening row-level quality gates.

- 2026-08-30 (**superseded later the same day**): Completed all 256 Tidsskrift chat shards after introducing
  non-destructive terminal closure floors of 97.5% for chat and 97% for SFT.
  The floors exclude persistent malformed or audit-incomplete requests rather
  than admitting them: 161/165 chat rows and 270/277 SFT request batches were
  retained from five threshold-edge shards. The active SFT campaign reached
  108/256 shards with eight workers active and no failed queue entries.

- 2026-08-30: Completed the Danish research-source campaign and released all
  eight GPUs. Zero-error E4B samples accepted Bornholmsk 94%, COR.SEM 100%,
  checked book ads 98%, and SKS commentary 94%. DiEm generated 1,258/1,259
  targets and retained 1,167 independently accepted rows (1,658,595 tokens per
  pass). All five slices are integrated in the 15,728-task DFM10 union and
  remain export-manifest WIP only because resampling/publication are pending.

- 2026-08-30: Superseded destructive exact-eight validation for Tidsskrift SFT
  generation. The pipeline now salvages individually valid examples from short,
  mixed-validity, and truncated batches, records partial-recovery counts, and
  reparses stored raw responses before new inference. Offline recovery restored
  6,272 paid-for request batches and 35,379 valid examples; the resumed queue
  prioritizes the two missing chat shards before continuing SFT generation and
  audit.

- 2026-08-30: The project owner approved public upload of all 22 technically
  validated `ready_for_upload` DFM10 packages, including the 13 policy-filtered
  Sapient provenance partitions, after the recorded redistribution cautions
  were presented. Added a resumable manifest-driven uploader with exact remote
  file-presence verification; upload receipts are retained under
  `logs/dfm10_ready_upload/`.

- 2026-08-30: Completed the 384-shard Danish Wikipedia and OpenStax grounded
  chat campaign with zero failed shards. Materialized and fully validated
  49,787 Danish Wikipedia and 158,605 OpenStax upload rows; OpenStax contributes
  847,838 supervised turns and tokenized with zero skips. Activated both in the
  15,721-task DFM10 union and moved the OpenStax package from work in progress
  to ready for upload.

- 2026-08-30: Marked all five admitted Danish research-source packages as
  work in progress in `exports_dfm10/manifest.json`. Materialized and tokenized
  13,570 Bornholmsk, 130,111 COR.SEM, 73,301 checked book-ad, and 39,007 SKS
  commentary rows. COR.SEM.EXT and raw SKS author text remain excluded. Queued
  a shared-lock-safe campaign behind Tidsskrift for DiEm 31B generation,
  independent E4B audits of all admitted sources, DiEm packaging/tokenization,
  and final tokenized-union integration. Unfinished research roots are now
  optional in generic union rebuilds; their dedicated finalizer remains
  fail-closed.

- 2026-08-30: Implemented the queued DFM10 Danish persona and Domsdatabasen
  grounded-chat campaigns. Prepared 25,000 persona and 4,500 legal candidates
  across 96 atomic shards; production retains every accepted row after strict
  generation/audit gates. Added repeat-two persona and repeat-one legal union
  policy, optional tokenized-tree wiring, local HF export specs, tests, and an
  eight-GPU runner that waits behind the active lexical campaign without
  rebuilding or resampling DFM10.

- 2026-08-30: Implemented the queued DFM10 Danish persona and Domsdatabasen
  grounded-chat campaigns. Prepared 25,000 persona and 4,500 legal candidates
  across 96 atomic shards; production retains every accepted row after strict
  generation/audit gates. Added repeat-two persona and repeat-one legal union
  policy, optional tokenized-tree wiring, local HF export specs, tests, and an
  eight-GPU runner that waits behind the active lexical campaign without
  rebuilding or resampling DFM10.

- 2026-08-30: Versioned the native DFM10 DeepDive, repaired DOLCI, Terminal,
  and provenance-partitioned Sapient export set in the root export manifest.
  The DFM10 union now excludes legacy Terminal and both direct/native legacy
  DOLCI tool-use task families, records their replacement sources, and fails
  if a superseded prefix leaks into a rebuilt union; sampler zero-caps remain
  as a second guard.

- 2026-08-30: Admitted `alexandrainst/domsdatabasen` to DFM10 only through the
  `dfm10-domsdatabasen-grounded-chats` derivative: nonempty pseudonymized text,
  no raw continuation, 3,000--4,500 accepted chats, 15,000--20,000 assistant
  turns, repeat one, and mandatory privacy/grounding audit before tokenization.

- 2026-08-30: Refined the Danish research-source decisions. Added all 6,785
  official Bornholmsk parallel pairs from train, validation, and test in both
  translation directions, preserving original split provenance while treating
  none as held-out evaluation. Added a fail-closed DiEm historical-modernization
  path using ALTO-only extraction, Gemma 4 31B target generation, and independent
  E4B auditing. Marked CoRal out of scope and documented concrete COR.SEM,
  Danish book-ad, and SKS TEI task contracts; COR.SEM.EXT remains excluded from
  derived training under CC BY-NC-ND.

- 2026-08-30: Registered the two research additions in DFM10 export staging.
  `dfm10-bornholmsk-parallel` is a validated 13,570-row CC BY 4.0 package ready
  for upload; `dfm10-diem-historical-modernization` is an explicit WIP record
  for 1,259 prepared requests and cannot materialize before generation/audit.

- 2026-08-30: Made DFM10's 4K boundary explicit. Native Nemotron Terminal,
  DeepDive, and repaired DOLCI tokenization now removes only complete older
  turns and never clips assistant targets; the DFM10 sampler drops all other
  overlength examples by default so their source rows can be revisited in
  dedicated long-context epochs.

- 2026-08-30: Consolidated the DFM9/DFM10 long-context source record into a
  dedicated 8K/16K/32K inventory. It separates public training candidates,
  project-derived document objectives, measured DFM9 long-example families,
  and evaluation-only datasets, including explicit LongAlign contamination
  handling.

- 2026-08-30: Registered `dfm10-danish-persona-chats` as an unmaterialized
  DFM10 export work item targeting 20,000 accepted chats and about 100,000
  assistant turns at repeat two. Measured Domsdatabasen's pseudonymized corpus
  at 33.37M Gemma tokens and specified a rights-gated 3,000--4,500-conversation
  grounded legal target rather than raw continuation.

- 2026-08-30: Broadened the Danish data-source scan from model-building Hub
  namespaces to linguistics, lexicography, archives, historians, literary
  scholarship, and digital humanities. Added a ranked training/evaluation
  survey, identified COR.SEM and structured historical sources as the strongest
  gaps, and recorded which large humanities corpora already overlap DynaWord.

- 2026-08-30: Implemented the DFM10 Danish Hub gap decisions without rebuilding
  or resampling DFM10. Converted and tokenized all 1,360 Synthetic Values
  Model Charter SFT rows (432,223 tokens; repeat 10 planned), exported all 1,360
  preference pairs separately, and admitted no nominal holdout. The Croco-Munin
  audit found only seven candidate-only prompts and excluded the second 50K
  repository. Set Danish persona chat generation to five assistant turns on
  average and deferred Domsdatabasen after a rights/privacy/impact review.

- 2026-08-30: Added a concrete DFM10 Danish Hub gap-integration plan. It removes
  four composite duplicate routes, separates model-charter SFT and DPO use,
  gates the second Croco-Munin set on overlap and quality, defines a
  persona-seeded 20k-chat campaign, and defers legal text pending rights and
  privacy review.

- 2026-08-30: Scanned nine Danish-researcher Hugging Face namespaces for DFM10
  gaps. Prioritized the new model-charter SFT/DPO dataset, made the additional
  Croco-Munin preference set conditional on overlap analysis, and recorded why
  raw continuation, benchmark, hallucination, prompt-only, and redundant
  sources should not be added directly.

- 2026-08-30: Quantified duplicate DFM10 exposure for Wiki Instruct, Danish
  verifiable reasoning, IFBench train, and Translation 100k through their
  direct routes and `dfm-dyna-instruct`. The composite adds 273,022,333 tokens
  per epoch above 1,117,174,612 configured-direct tokens; recorded a future
  single-lineage rebuild requirement.

- 2026-08-30: Uploaded the validated 213,354-row
  `dfm10-arxiv-paper-summarization-sft` package publicly to
  `schneiderkamplab/dfm10-arxiv-paper-summarization-sft`. Verified Hub commit
  `f8b5b81d54e2ace242916b8f1dbd7dcc5248cb09`, all expected package files, and
  the exact 217,828,007-byte compressed data shard; added it to the explicit
  verified-upload inventory.

- 2026-08-30: Materialized the exact 213,354-row inherited arXiv
  excerpt-to-abstract task as the provenance-preserving, upload-ready
  `dfm10-arxiv-paper-summarization-sft` package. Every training row matched a
  unique Common Pile source record, retained row-level attribution and licence,
  and passed complete row and canonical-content-hash validation. Recorded the
  remaining exact-artifact materialization backlog.

- 2026-08-30: Audited the complete DFM10 tokenizer lineage through inherited
  DFM2--DFM9 sources. DFM2--DFM5 remain intentionally legacy-tokenized but are
  not inherited as token arrays; DFM6 retokenized the active lineage with the
  Gemma tokenizer. All 15,712 active DFM10 tasks resolve to Gemma-native roots,
  sampled array checks found no vocabulary or index corruption, and key
  multi-turn target counts agree with tokenized example counts. Recorded the
  negligible fail-closed OpenHermes targets and the non-impacting grounded
  Mimir length-check default as explicit limitations.

- 2026-08-30: Materialized and structurally validated the first 150,000-row
  Mimir answer-contract calibration candidate with 150,000 unique source rows,
  no holdouts, and exact family quotas. Prepared a 1,600-row stratified E4B
  audit and queued its eight-GPU runner behind the active Open Chats and
  Tidsskrift campaigns; DFM10 integration remains gated on the audit.

- 2026-08-30: Registered five planned Mimir benchmark augmentation datasets as
  non-materialized work-in-progress records in the generated DFM10 export
  inventory: IFEval verifier SFT, answer-contract calibration, event
  coreference, DROP reasoning, and BoolQ entailment. Stable export identities
  now survive inventory refreshes without presenting zero-row plans as
  uploadable packages.

- 2026-08-30: Verified DFM10 multi-turn supervision end to end for the Danish
  Wikipedia chats. Chat tokenization expands every assistant turn into its own
  prompt/response index pair with all preceding turns as context; canonical
  Gemma tokenization produced 261,588 examples and 213,380,681 tokens with no
  skips. Recorded and superseded the rejected legacy-tokenizer attempt.

- 2026-08-30: Refined the post-integration Mimir benchmark-data plan. MMLU and
  ARC-C capability augmentation is deferred until corrected post-DFM10
  per-subject diagnostics exist; decontamination remains normalized-exact only.
  Promoted answer-contract calibration to a primary 100k--200k slice after
  auditing the distinct bare-letter, prefixed-letter, localized-label,
  short-span, numeric/boxed, and structured-payload contracts used by the
  standard, DFM, EuroEval, and current training paths.

- 2026-08-30: Marked the Danish lexical sentiment and FrameNet export packages
  as `work_in_progress` in the generated `exports_dfm10/manifest.json` until
  additive natural-question generation, audit, tokenization, and package
  refresh finish. The marker is generated, not a one-off manifest edit.

- 2026-08-30: Cleared a stale Mimir campaign lock after verifying complete
  640/640 main and 128/128 top-up state and no child workers or servers. The
  queued natural Danish lexical campaign now waits on its all-GPUs-free gate;
  the unrelated DFM10 Open Chats vLLM campaign was not disturbed.

- 2026-08-29: Superseded the nine-row standalone Tidsskrift packaging plan.
  The nine gold summaries now form an explicit subset of the unified
  `dfm10-tidsskrift-open-sft`, alongside at least 200,000 independently audited
  Gemma 4 31B grounded rows. Added the separate
  `dfm10-tidsskrift-open-chats` contract for audited 2–10 exchange student
  inquiry conversations below 4,096 rendered tokens, plus the all-article,
  resumable eight-GPU production runbook.

- 2026-08-29: Added a resumable Gemma 4 31B generation and independent-audit
  pipeline for 47,854 natural Danish lexical interactions: 14,008 sentiment
  and 33,846 FrameNet rows. These are additive to, rather than replacements
  for, the 5,982 existing batched gold rows. Exact signed polarities and frame
  labels are deterministically enforced; the queued eight-GPU campaign waits
  for the active Mimir campaign and owns only its own vLLM server PIDs.

- 2026-08-29: Placed `dfm10-tidsskrift-open-article-summaries` under an
  explicit publication hold. Its nine validated, openly licensed rows remain
  local until the hold is explicitly lifted; the hold does not cover the
  Danish FrameNet or lexical-sentiment SFT packages.

- 2026-08-29: Completed the strict-open Tidsskrift.dk OAI inventory with
  127,510 unique records across 232 journal sets. After explicit-license and
  overlap gates, 2,173 new candidates remain and 758 have usable author
  abstracts. Added abstract-removal and residual target-leakage checks.

- 2026-08-29: Integrated 5,982 deterministic Danish lexical SFT rows
  (2,389,573 Gemma tokens) from the explicitly licensed DSL sentiment and
  FrameNet resources, and started strict 100-row DynaWord modernization and
  spoken-normalization pilots.

- 2026-08-29: Finalized the DynaWord pilots. Kalliope retained 60/99
  successfully generated rows with substantive edits and remains a viable
  production candidate behind full audit. VoxPopuli retained 79/100, but 67
  accepted rows were near-copies, so it is not admitted to DFM10.

- 2026-08-29: Materialized the strict-open Tidsskrift instruction package.
  Structural conversion yielded 24 candidates; a Gemma 4 31B grounding and
  usefulness audit plus duplicate-target filtering retained 9 rows (5 English,
  4 Danish). The final tokenized source has 21,376 Gemma tokens and is linked
  into the 15,708-task DFM10 union at repeat one.

- 2026-08-29: Clarified the Tidsskrift.dk holding: DFM10 contains the 62,934-row
  train split of the CC-BY-derived backtranslation corpus (38.33M tokens from
  3,359 source articles), while the raw article corpus and BT eval split are not
  locally downloaded.

- 2026-08-29: Completed the expanded OpenStax grounded-SFT run and DFM10
  integration. All 64 shards succeeded; the final corpus has 50,000 audited
  rows, 8,592,140 Gemma-rendered tokens, a maximum 859-token row, and 16
  tokenized tasks linked into the canonical DFM10 union at repeat one.

- 2026-08-29: Materialized and fully validated 25 upload-ready DFM10 dataset
  packages under `exports_dfm10/` without uploading them. The 26 GB staging
  tree contains 69,364,759 chat-normalized rows with cards, checksummed
  manifests, provenance, and standalone validators. Hub API checks resolved
  all 159 inherited DFM8 repositories and all nine DFM9 additions; agreement-
  backed Lex.dk and DBC remain deliberately excluded from public staging.

- 2026-08-29: Added a fail-closed DFM10 integration path for the expanded
  OpenStax grounded-SFT run. Only rows from the 61 immutable historical CC BY
  artifacts can enter; all 64 shards must complete with zero failures, every
  row must pass the independent 4/5 audit and 4,096-token gate, and the source
  is sampled once under `openstax_mimir_sft__`. The 10,000-row pilot remains a
  separate baseline and is not linked into DFM10.

- 2026-08-29: Activated the English OpenStax relevance allowlist for the Mimir
  augmentation pipeline using only immutable official artifacts. The corrected
  text-only pool contains 61 books, 20,047 unique passages, and 95,979,948
  characters; media, third-party permission-only modules, and the
  provenance-poor Hugging Face repack are excluded. The initial Additive
  Manufacturing pin was superseded by the internally consistent CC BY commit
  `26653ddb1048708bd974e8c11471e426b1ff5520`. The initial pilot completed with
  10,000 accepted rows; all were below 4,096 rendered training tokens. It was
  preserved and followed by an expanded 65,000-request run targeting 50,000
  accepted rows. Expanded-run rows are checked with the DFM8 Gemma
  tokenizer/template and rejected above 4,096 rendered training tokens.

- 2026-08-29: Audited OpenStax's official source history and retained editions,
  producing `docs/openstax_cc_by_inventory.csv` with 107 independently
  retrievable CC BY 4.0 editions/volumes. The inventory pins 75 source trees to
  immutable commits, records version identifiers or hashes for other artifacts,
  and quarantines overwritten nursing PDFs and conflicting Business Law
  metadata pending recovery and verification.

- 2026-08-29: Corrected the DFM10 completion assessment after reconciling the
  178-source audit with active prefixes. Scientific Summaries is repaired but
  not integrated; DA-AR and DA-UK remain enabled contrary to their documented
  exclusion decision; and several lower-priority `Filter`/`Repair` families
  still require explicit disposition before final sampling.

- 2026-08-29: Added a detailed Mimir v1 (DFM8 XL step 1,650,000)
  evaluation-gap analysis. It identifies technical science, professional
  knowledge, compositional reasoning, and grounded factual QA as credible data
  priorities, while recording that MMLU high-school mathematics is invalid as
  a capability signal because 98.9% of outputs violated the one-letter answer
  contract. Follow-up reproduction identified immediate Gemma `<turn|>` output
  under a legacy HRM prompt. The evaluator now validates tokenizer/template
  compatibility, derives legacy termination IDs, supports safe automatic prompt
  selection, and gives malformed MCQ output zero rather than chance credit.

- 2026-08-29: Completed source-grounded recovery for Danmarks Statistik BT
  (5,627 final rows) and Danish university portals (3,049 final rows), deferred
  complete-report GovReport recovery to a future 8K+ DFM10 variant, and started
  additive 31B-generation/E4B-audit recovery for WikiCatSum without weakening
  its existing strict corpus.
## 2026-08-31

- Verified the transferred 92.66B-token DFM10 sample, repaired its relocatable
  tokenizer metadata, and extended the active DFM8 XXL campaign through a full
  epoch-one evaluation and one DFM10 continuation epoch. The DFM10 phase keeps
  the optimizer/EMA/global step and evaluates every 50K steps plus `epoch_2`.

- Replaced machine-specific DFM7/8/10 tokenizer metadata defaults with
  repository-relative paths, fixed HF conversion to propagate the tokenizer
  override through checkpoint loading, and recovered the DFM8 XXL 250K export
  and evaluation campaign before automatic resume from step 252500.

## 2026-08-30

- Added a reusable 30-minute W&B training-stability watcher and launched it
  for the resumed DFM8 XXL run, with append-only JSONL snapshots and a visible
  tmux window.

- Added null-default skip-before-moments protection with distributed consensus,
  exact optimizer/EMA preservation, immediate metrics, and clean checkpointed
  exit after a configurable consecutive-skip limit. Enabled it only for the
  pending post-250K DFM8 XXL segment without interrupting active training.

- Ruled out the suspected FSDP2 clipping-scale/DTensor malfunction with a
  retained two-rank `fully_shard` regression test, and documented why
  AdamATan2 needs proposed-update clipping or an anomaly skip-step guard for
  stronger protection.

- Simulated single and sustained AdamATan2 gradient spikes under raw clipping,
  skip-step, global update-RMS clipping, and LR backoff. The results refine the
  recommendation toward skip-before-moments and local/history-aware methods;
  a calibrated model-global post-`atan2` RMS cap did not detect scale spikes.

- Added the optional global-gradient-clipping technical reference, including
  null-default behavior, FSDP2 mean-gradient scaling, logged metrics, and the
  eight-GPU XXL parity measurement.

## 2026-08-29

- 2026-08-29: Merged `origin/main` through `7bf17c8` into the active
  `multinode` branch without interrupting the DFM8 XXL 178K-to-200K process.
  The next scheduler-launched 200K-to-250K process will inherit optimized FA4
  seqused/Triton defaults while retaining the production transformer-block
  FSDP wrap policy; documented the intentional implementation boundary.

- 2026-08-29: Added the post-profile strategic performance roadmap for DFM8
  XXL. It separates measured bottlenecks from estimated opportunities and
  prioritizes FP8 compute with FP32 state, larger fusion boundaries, reduced
  GAS, static recurrent execution, recurrent-aware distribution, and
  time-to-quality improvements. No new experiment was approved by this entry.

- 2026-08-29: Added an exact production inventory for all 13 DFM10 repaired
  replacement families, measured from the disabled legacy and active repaired
  token arrays. The inventory distinguishes stored pre-sampling rows/tokens
  from caps, repeats, packing, and epoch sampling. The DOLCI baseline counts
  only the DFM9-active native conversion, not two older already-disabled
  representations; GovReport's complete-input repair explains its higher
  token count despite fewer rows.

- 2026-08-29: Fused seqused FA4 prefix/causal output selection and padding
  zeroing in a NaN-safe custom-autograd Triton boundary. Direct FA4 outputs
  and gradients are bit-identical; a 100-step XXL A/B reduced median step time
  by 4.01% and mean step time by 3.39%.

- 2026-08-29: Completed the NordjyllandNews production repair. The exhaustive
  Gemma 4 31B audit retained 47,120/73,097 candidates (64.46%); an independent
  800-row post-filter gate passed 797/800 (99.625%). The strict replacement is
  tokenized as 26,590,391 Gemma-native tokens and is eligible at repeat one.

- 2026-08-29: Materialized the completed Folketing audit into four accepted
  source families with 13,225,678 rows total: 3,636,825 denoising, 3,105,440
  error-correction, 3,573,233 prefix-continuation, and 2,910,180 span-filling.
  Added a fail-closed finalizer that verifies exact full-audit counts before
  tokenization. Production tokenization completed with zero skipped rows and
  17,498,229,889 tokens. Rebuilt the DFM10 union with 11,719 task directories,
  including all four Folketing families and the grounded Nordjylland repair.

- 2026-08-29: Replaced the raw `oliverkinch/danish-university-portals-bt`
  sampling path with a deterministic structural filter and exhaustive Gemma 4
  E4B audit. Exact no-error coverage retained 2,147/4,505 rows and 1,034,131
  unique Gemma-native tokens. DFM10 now disables the legacy prefix and samples
  the strict replacement at repeat 10, reducing its per-epoch contribution
  from 21,765,750 to 10,341,310 tokens.

- 2026-08-29: Completed a checkpoint-based 1,000-step eight-B200 comparison of
  `main` against FA4 `seqused+triton`. The optimized path reduced median step
  time by 16.75% and mean step time by 18.89%, while aligned mean loss and
  accuracy showed no adverse trajectory. Documented exact row-cursor resume,
  benchmark artifacts, memory use, and an excluded vLLM-contaminated launch.

- 2026-08-29: Added the DFM10 DST table-prompts repair. The inherited prefix is
  disabled. Exhaustive Gemma 4 31B review accepted only 133/3,016 cleaned
  authentic targets and identified unsupported claims in 2,739 rows. The
  replacement now preserves those 133 rows, regenerates only the 2,883 rejects
  from their exact tables, and requires a second exhaustive grounding audit
  before final filtering and Gemma-native tokenization. The independent audit
  accepted 2,909/3,016 rows (96.45%); the 4,111,556-token result contributes
  41,115,560 tokens per epoch at repeat ten. Its production marker now
  satisfies the DFM10 union gate.

- 2026-08-29: Added the Danmarks Statistik BT answer-matched prompt repair,
  exhaustive E4B coherence gate, fail-closed DFM10 replacement prefix, and
  GPU-idle orchestration. The source targets remain authoritative; only prompts
  are regenerated, and indirect or context-dependent pairs are filtered.
  Completion retained 3,086/7,154 original rows and tokenized 762,189 unique
  tokens, contributing 7,621,890 tokens per DFM10 epoch at repeat ten.

- 2026-08-29: Paused the additive Danmarks Statistik full-article recovery
  after its generation pass and before merge/audit. Of 3,932 prepared requests,
  2,156 generated valid records and 1,776 remain explicit retryable
  structured-output truncation errors. All owned E4B servers were released.

- 2026-08-28: Added the fail-closed WikiCatSum production finalizer, exact
  full-audit coverage gate, and DFM10 replacement-prefix policy. **Superseded
  detail:** a first merge trusted contradictory usable/complete booleans and
  counted 263/300 pilot and 12,854/14,479 production rows. The authoritative
  criterion also requires `primary_problem: none`: 244/300 pilot and
  11,791/14,479 production rows pass. The 48 tokenized shards contain
  2,317,983 tokens, or 4,635,966 per epoch at repeat two.

## 2026-08-28

* **OPUS DA-EN deterministic repair started**: Sharded 29,261,517 canonical
  bilingual pairs into 64 balanced Parquet files, calibrated Lingua direction
  checks and LaBSE alignment filtering against the prior E4B audit, removed
  OPUS provenance from the user-visible translation contract, and added
  resumable scoring, conversion, re-audit, validation, tokenization, and DFM10
  union hooks. Sampling activation remains gated on full scoring and the new
  1,000-row accepted-pair audit.

  **Completed 2026-08-28:** Accepted 20,577,773 pairs (70.32%), emitted and
  tokenized 41,155,546 directional rows (3,629,237,788 tokens), and passed the
  independent 1,000-row E4B gate at 97.3% usable and 87.2% strict with zero
  judge errors. DFM10 now samples exactly 30M rows from the repaired 64-shard
  prefix and samples zero rows from the legacy OPUS conversion.

* **WikiCatSum grounding repair staged**: Replaced the inherited noisy-prefix
  conversion with a 16-process, 48-shard evidence selector. A permissive
  68,624-row draft failed its 300-row pilot at 33.67% strict usability and is
  superseded. The calibrated version retains 14,479 title-anchored candidates
  at 90% content and 50% bigram support; its row-level E4B grounding gate is
  queued behind unrelated GPU work. **Superseded 2026-08-28:** the old-prefix
  activation statement no longer applies; DFM10 now disables the old prefix
  immediately and fails closed until the replacement passes completely.

* **NordjyllandNews grounding repair prepared**: Replaced the one-shape summary
  instruction with a headline-aware, exact-template conversion, deterministically
  reduced 75,219 source rows to 73,097 complete candidates, and disabled the
  inherited prefix. An E4B pilot was superseded after inconsistent judgments;
  the authoritative Gemma 4 31B pilot accepted 493/800 under the strict gate.
  Full-corpus audit, strict filtering, and post-filter validation are required
  before the new repeat-one prefix can enter DFM10.

* **Code Meta-Reasoning structured repair completed**: Replaced the flattened
  empty-prompt interpretation with the authoritative structured AllenAI source,
  restored six explicit task-family contracts, removed deliberately bad-code,
  wrong-function, missing-image, recursive meta-task, malformed, and over-4K
  rows, and retained 429,301 Gemma-native examples. The 600-row family-stratified
  E4B quality gate passed 575/600 examples under the strict criterion. All rows
  were tokenized into 667.31M tokens, the broken inherited prefix was disabled,
  and the repaired prefix was capped to exactly 249,999 sampled rows.
* **GovReport grounding repair completed**: Replaced the design that paired
  truncated report prefixes with full summaries by an isolated exact-template
  4K converter, audited all 1,845 complete candidates, and published 891 rows
  passing strict completeness and grounding thresholds. The 2.99M-token
  corpus passed its independent 200-row E4B audit at 99.5% usable; DFM10 now
  disables the old prefix and samples the repaired corpus twice.
* **DFM8 XXL one-node return at step 178000**: Restarted the existing
  coordinator/worker campaign on a fresh eight-B200 node and resumed W&B run
  `DFM5/40j5y877` from the protected regular checkpoint. The first attempt
  correctly failed before training because the new node lacked W&B
  credentials; restored its netrc, reset only the failed training row, and
  verified forward progress beyond step 178020 under the original GBS
  262144/GAS 4/full-FSDP configuration.
* **Two-node FSDP/HSDP validation**: Passed launcher preflight, 16-rank NCCL
  all-reduce, changed-world DFM8 XXL `step_178000` resume, and ten optimizer
  steps on two eight-B200 nodes without W&B or checkpoint tensor writes.
  Full-world FSDP measured 13.424 s/step median; degree-8 HSDP measured 4.227
  s/step versus the roughly 3.6 s one-node baseline. NCCL fell back to
  `NET/Socket` because both containers lacked `/dev/infiniband` despite active
  ConnectX-7 links, so RDMA enablement remains the production blocker.
* **One-node multi-node scheduler deployment**: Migrated the active DFM8 XXL
  campaign from the legacy runner to one coordinator plus one local eight-GPU
  worker, resuming from `ephemeral_step_176000`. Fixed cluster handoff so
  independent future `wait_checkpoint` control jobs coexist with training
  instead of holding the coordinator in `draining`; added a regression test.
* **Cluster training monitor attribution**: Fixed plain and Rich aggregate
  monitors to attribute coordinator-owned cluster training to every worker GPU
  instead of labeling heavily utilized training devices as idle.
* **Protected DFM8 XXL step 178000**: Stopped the one-node multi-node campaign
  after verifying the complete ephemeral checkpoint, promoted its shards by
  hard link to regular `step_178000`, validated the regular sidecar, and left
  the pending training row prepared to resume from that protected tag.
* **Multi-node scheduler implementation**: Implemented the coordinator-worker
  scheduler, node-qualified fenced leases, authenticated heartbeats, SSH
  worker lifecycle, node-local persistent-vLLM reuse, cluster training drain
  and handoff, restart reconciliation, and aggregate Rich/plain monitoring.
  The 47 local scheduler tests pass; real two-node validation remains gated on
  an allocation.
* **Multi-node evaluation scheduler plan**: Chose a single authoritative
  coordinator with capability-limited per-node workers, node-qualified GPU
  leases, fencing tokens, local persistent-vLLM pools, cluster drain/training
  handoff, and heartbeat-backed aggregate monitoring. Defined phased delivery
  and two-node through eight-node acceptance gates while preserving the
  existing single-node scheduler path.

* **Scientific Summaries grounded rebuild**: Replaced the truncating DFM4
  conversion with an atomic 16-process, Gemma-token-aware rebuild from complete
  structured fields. Added a deterministic eight-GPU E4B audit with exact
  merge and constrained-decoding recovery; its 320-row pilot passed at 91.88%
  usable. The 3.31M-row rebuild and 40,044-row production audit then completed
  at 99.63% deterministic retention and 91.04% judged usability.
* **Nemotron SWE structural repair**: Replaced the duplicated/contextless
  inherited windowing design with complete Gemma-native next-action examples
  and one explicitly selected assistant target per row. Preserved matched
  shell/editor call-result cycles, removed obsolete `think` actions, normalized
  `finish` as text, and separated agentless file-location supervision from
  interactive tool use. Corrected an over-broad phase-heading cleanup before
  tokenization, added exhaustive validation and a deterministic 1,000-row
  behavior-stratified E4B audit, and wired the repaired prefix into DFM10 while
  disabling the superseded prefix.
  **Superseded detail:** converter v3 had 2,466,262 rows and 6.615B rendered
  tokens, but its agentless fit check unnecessarily included interactive tool
  schemas. Converter v4 uses each task's actual tools and is authoritative:
  2,472,316 structurally valid rows and 6,597,089,585 exact rendered tokens.
  Its fresh 1,000-row audit completed with zero judge errors and 100% usable
  decisions; manual review retained four mild agentless output-format
  deviations and a few weak exploratory actions as useful supervision.

* **DOLCI native tool-use repair**: Identified that the inherited converter
  dropped all `environment` tool results and reused call IDs, then added an
  isolated validated converter, a conservative Gemma mapping-response template
  fix, deterministic tokenized-target audit tooling, and DFM10 union hooks. The
  repaired corpus contains 996,180 targets/1.531B stored tokens; its E4B audit
  passed at 674/700 usable with zero judge errors, so DFM10 now samples it in
  place of the old native conversion.
* **OpenMathInstruct-2 repair completed**: Verified 13.97M canonical rows,
  scored 13.96M with Qwen2.5-Math-PRM-7B, calibrated thresholds against E4B,
  built 7.49M deduplicated/decontaminated CoT and direct rows, passed exhaustive
  format validation, and completed a zero-error 4,000-row E4B quality audit.
* **PrefixLM device-synchronization fix**: Removed the two CUDA
  `max().item()` reductions from each FA4 causal PrefixLM attention call by
  reusing the packed batch's safe maximum-length bounds. Applied the same fix
  to ROCm and added focused conservative-bound tests. Corrected the profile
  interpretation: the other five metadata `.item()` calls consume CPU tensors.
  An order-controlled XXL A/B benchmark measured a 2.04% median step-time
  improvement (`3.5138 -> 3.4420 s`).
* **DFM8 XXL Nsight profile**: Captured a checkpoint- and W&B-disabled
  steady-state eight-B200 profile. Identified repeated four-byte `.item()`
  synchronization in PrefixLM attention and extreme short-kernel launch
  fragmentation as the first optimization targets; NCCL was substantial but
  mostly overlapped, and FA4 represented under 10% of summed kernel time.

## 2026-08-27

* **DFM8 XXL MFU baseline**: Calculated a recurrence-aware 25--29% estimated
  MFU at 3.56 seconds per step on eight B200s, documented the 23.5--32.4%
  attention-density bounds, and separated this from the misleading 9.8%
  conventional `6ND` estimate.
* **DFM8 XXL to DFM10 multi-node transition**: Recorded the planned clean
  epoch-boundary dataset change, four/eight-node GBS geometry, HSDP topology,
  DFM10 readiness blockers, validation gates, and checkpoint-cadence concerns.
* **DFM8 XXL production resume at 161K**: Repaired the existing epoch-one
  scheduler row under lock, resumed its existing W&B run from the latest fully
  written ephemeral, and verified forward progress on the measured fastest
  single-node FSDP2 path.
* **Fixed-membership SSH TorchRun launcher**: Added ordered-host SSH launch,
  cross-node software/path/interface/clock preflight, NCCL all-reduce smoke,
  atomic manifests, per-node logs, and exact process-group teardown. Added a
  focused runbook; real two-node validation remains pending.
* **FSDP2/HSDP implementation and XXL parity**: Added configurable local shard
  degree, explicit/preserved resharding behavior, communication-efficient GAS,
  run-aware no-carry checkpoints, and row-cursor world-size resume. Recorded
  deterministic DDP/FSDP/HSDP GAS parity plus the full XXL degree-8/4/2 timing
  and memory matrix.

## 2026-08-26

* **Distributed long-context implementation matrix**: Documented main-branch
  complexity and risk for activation checkpointing, TP, CP, generic pipeline
  parallelism, and tied recurrent L/H pipelines.
* **DFM8 XXL loss excursion**: Attributed the isolated step-150.7K loss spike
  against exact sampled rows, ruled out a source-family or sequence-length
  distribution shock, and recorded its healthy self-recovery and telemetry
  gaps.
* **DFM8 XXL epoch-one resume**: Repaired the stopped scheduler campaign to
  resume from the complete 151K ephemeral checkpoint, retain W&B run
  `DFM5/40j5y877`, evaluate 200K and 250K without long-context tasks, and
  recognize natural `epoch_1` completion. Added a delayed GPU-release watcher
  and recorded the verified `hrm` versus currently broken `hrm-cu132` state.
* **DFM8 XXL pause at 152.5K**: Soft-stopped the scheduler and interrupted
  training only after the complete eight-rank `ephemeral_step_152500`
  checkpoint was written. Recorded the intentional `-15` row state and the
  required resume-row update.
* **Review hardening fixes**: Made Folketing audit partitions independent of
  physical GPU IDs and cleanup process-owned, keyed long-context caches by
  example cap, and prepared transactional/fail-closed long-context pipeline
  fixes with numerical Transformers YaRN parity tests on the long-context
  branch.
* **DFM9 XXL-32 20K EuroEval assessment**: Recorded 18 completed and synced
  task results, the intentional VaLEU-da skip, the all-invalid VaLEU-en
  failure, and the zero/near-chance pattern indicating early output collapse.
* **Laerebogen alignment spot audit**: Reviewed a reproducible uniform sample
  of ten converted assistant-turn examples. Eight latest answers were aligned,
  one was partially aligned with material factual errors, and one was
  misaligned; four serialized histories contained cross-topic conversation
  splices.
* **DFM9 rights and memorisation framework**: Expanded the generated DFM9
  source-rights appendix with the copyright/TDM and GDPR decision process, the
  status and interpretation of EDPB Opinion 28/2024 and the 2026 consultation
  guidelines, the AI Act open-source release strategy and compute analysis, and
  the published Mimir memorisation-audit methods, results, and limitations.
* **Repository validation and OKF refactor**: Split the oversized DFM9 plan
  into focused OKF concepts while preserving its parent path, restored missing
  page-index coverage, and documented capability-gated 8K evaluation planning
  plus the retained long-context metric caveats.
* **Eval monitor live progress**: DFM tasks now read exact totals and completed
  samples from active Inspect `.eval` journals; standard and batched-EuroEval
  tasks use native tqdm rolling ETAs. Verified the change against the live
  XXL-32 step-20K campaign and restarted its Rich monitor.
* **DFM9 XL 8K pause at 2.164M**: Soft-stopped scheduler dispatch, verified a
  complete eight-rank ephemeral checkpoint at step 2,164,000, then terminated
  training and reset its plan row to resume from that checkpoint. The stop
  request remains active while XXL checkpoints are evaluated.
* **XXL-32 checkpoint inventory**: Verified complete 256-rank regular
  checkpoints at every 10K step through 100K plus epoch 1 at step 89,665. The
  newest 106,250 ephemeral is incomplete locally and must not be evaluated.
* **XXL-32 20K--100K evaluation campaign**: Queued full standard, DFM, and
  EuroEval graphs for all nine regular checkpoints, with serialized 256-rank
  exports and opportunistic cross-checkpoint GPU scheduling into the existing
  `DFM5/dfm9-xxl-32` W&B run.
* **DFM10 DeepDive integration**: Added the 858 successful Apache-2.0 Z.ai
  DeepDive search trajectories through a dedicated converter. It removes old
  ReAct/XML and visible thinking, emits Gemma4-native search/click/open calls
  with matched tool responses, replaces terminal `finish` calls with gold
  answers, and uses strict no-truncation sampling.
* **Production 8K RULER**: Replaced the production use of the eight-example
  4K smoke with a 416-example, 13-variant, eight-shard 8K suite; added
  per-variant merging and the `long_context_headline_v3` aggregate. Recorded
  exact-tokenizer loading, the 512-token Gemma-template reserve, and the
  low-memory sidecar campaign for epoch 8 versus step 2.15M.

## 2026-08-24

* **`hrm-cu132` runtime repair**: Pinned CUTLASS DSL/CUDA 13 libraries to
  `4.5.2` for FlashAttention 4 compatibility, persisted compiler settings, and
  recorded the explicit `CC`/`CXX` requirement for scheduler-launched Triton
  compilation. The repair was performed with `uv pip`.

## 2026-08-22

* **Source-rights appendix compiled**: Installed `texlive-latex-extra`,
  changed long identifiers and evidence paths to break-aware LaTeX rendering,
  and produced a clean 54-page PDF with no box or reference warnings.
* **Manual decisions added to source-rights appendix**: Extended the
  deterministic DFM9 LaTeX renderer with linked manual-decision columns on
  effective-source and dependency rows plus a complete 22-row decision
  register covering scope, rationale, residual issues, and future testing
  targets. Generation now fails on undefined or disconnected decisions.
* **Source-rights LaTeX appendix**: Added a deterministic renderer joining the
  161-source copyright register to the 424-node/556-edge declarative DAG. The
  self-contained appendix lists every effective dataset and all 286 referenced
  dependency nodes with stable linked IDs, typed edges, terms, status,
  completeness, exposure, evidence, and authoritative input hashes.

* **DFM10 Folketinget integration**: Added the CC-BY-4.0, pseudonymized
  Rigsarkivet handover 14004 as a dedicated Danish raw-text source. The
  preparation pipeline now emits bounded Gemma-template-ready prefix
  continuation, word-denoising, OCR/character-error-correction, and span-fill
  candidates, with provenance side fields and existing judge-audit support.
  Older OCR text is retained conservatively and quality-filtered by the judge;
  no synthetic QA framing or validation/test split is introduced.

* **DFM10 LMSYS decision**: Raw multilingual LMSYS chat remains excluded, but
  a local-only, aggressively filtered Danish subset is now considered a
  plausible small DFM10 addition. English is optional and capped because it is
  largely redundant with existing chat sources. Any subset must pass language,
  PII, moderation, quality, and benchmark-contamination filters and must not be
  redistributed under the LMSYS agreement.

* **DFM10 LMSYS audit plan**: Defined a Gemma 4 31B local-only audit for the
  English and Danish subsets, separating language, usefulness, instruction
  following, safety, privacy, benchmark contamination, and retention. The
  plan requires deterministic hard filters, structured judge records,
  stratified manual review, and no redistribution of accepted derivatives.

## 2026-08-20

* **A-D exact-match adjudication**: Classified all 5,562 exact-64 occurrences
  from the exhaustive memorisation probes with Gemma 4 31B, retaining 3,423
  unique evidence pairs and every protocol occurrence. Strict review found 61
  coherent-prose occurrences, one predictable traditional-song expressive
  occurrence, and no high-priority copyright-expression result; this
  supersedes the overly broad lexical `prose` estimate.

## 2026-08-18

* **Agreement/Article-3 extraction probe**: Ran a reusable 64-prefix/64-target
  raw and Gemma-chat attack over 65,504 stratified unique source texts. Category
  A had no exact extraction; Category B's seven unique exact continuations were
  all low-entropy whitespace, numbering, table-of-contents, repeated-digit, or
  grid structures. Added stable request keys and exhaustive-resume support.
* **DFM Mimir public demo**: Added and deployed a bilingual Gradio demo at
  `peter-sk/DFM-Mimir-Demo` on ZeroGPU. It uses the native Mimir chat template
  and prefix-LM token types, requires per-visitor Hugging Face OAuth access to
  the gated model, and stores no shared Hub credential. Recorded the org
  ZeroGPU entitlement limitation, deployment fallback, and verification state.

* **Memorisation source-material assembly**: Narrowed the non-Article-3/4
  cohort by excluding Common Pile, DynaWord, OPUS pairs, Wikipedia, EUR-Lex,
  GovReport, filtered arXiv, contributor-created Giannor/Oliverkinch/Synquid,
  and from-scratch DFM8 material. Added a reproducible symlink assembly with
  original/proxy labels, exact selectors, audit evidence, and explicit gaps
  for all locally available A-D source material.
* **ShareGPT MAN-022 decision**: Superseded the open ShareGPT boundary by
  accepting deliberate one-click public publication and public-API access as
  participant permission for current academic/non-commercial research
  training. Recorded the distinction from WildChat's explicit consent and the
  historical Apache mirror/MIT software licence boundaries. This clears Tulu
  v2 SFT, Tulu v2 SFT Long, and SciRIFF Train Mix for the current purpose.
* **ShareGPT boundary audit**: Traced AllenAI's exact Tulu-v2 preparation from
  the anonymous HTML-cleaned mirror, corrected the split/Long relationship to
  74,159 shared original IDs plus small source-set differences, and documented
  public-sharing/API, first-day robots exclusion, official Vicuna legal
  non-release, licence-authority, Article 3/4, and aggregate privacy/credential
  evidence. The boundary remains open for institutional Article 3 approval.
* **Tulu v2, SciRIFF mix, and IF-SFT decomposition**: Mapped both local Tulu-v2
  artifacts across all 16 labels, verified the exact 35,000/35,714 SciRIFF
  Train Mix split, and joined every IF-SFT row to all 19 Tulu-3 components.
  IF-SFT is cleared by inheritance; Tulu v2, Long, and SciRIFF Train Mix are
  partial only through one shared ShareGPT participant-expression boundary.
  Reconciled MAN-021 in the generated copyright register.
* **Sapient instruction-family rights audit**: Reconciled all 3,644 retained
  non-factual FLAN files, 161 Tasksource files, and eight Platypus files to
  exact DFM9 exposure. Extended the recorded FLAN Article 4 decision to the
  equivalent Sapient materialization, resolved Platypus through four direct
  component terms, and approved the 69.759M-token/epoch Tasksource residual
  under Article 3 for current research. The Sapient aggregate now computes as
  cleared; 89/161 effective datasets and 46.972B tokens/epoch are cleared
  without Article 3.
* **Source-filter semantics correction**: Recorded that the implementation is
  default-allow after override and deny checks, so the documented FLAN and
  Tasksource override lists are not exhaustive allowlists. Privacy controls
  remain independent of the copyright resolution.

## 2026-08-17

* **FLAN v2 and SciRIFF Article 4 decision**: Superseded the narrow Article 3
  fallback for uncovered retained expression with a project-owner Article 4 /
  Danish section 11 b determination. Direct component terms still apply,
  provenance and acquisition-time reservation evidence remain partial, and
  both decisions were added to the standing manual-decision/memorisation-test
  register.

* **Apertus rights audit**: Resolved all fourteen former unresolved leaves for
  the current research purpose. Nine use captured direct terms; SmolTalk,
  Mixture-of-Thoughts, OpenHermes, LongAlign, and uncovered EuroBlocks seeds
  retain narrow Article 3 fallbacks and partial provenance. Apertus and the DFM
  Dyna branch now compute as cleared for current research, not blanket
  commercial use.
* **Manual decision register**: Consolidated every discretionary project-owner
  acceptance and rights-basis override into one review file, including
  subdataset scope, rationale, residual caveats, and future
  memorisation/propensity-test targets.

* **Tulu 3 Persona family audit**: Traced 251.016M directly sampled
  tokens/epoch plus shared aliases and filtered variants to PersonaHub,
  GPT-4o, Claude 3.5 Sonnet, Ai2-authored IF seeds, and the open IFEval
  taxonomy. Cleared the family for current non-commercial research without
  Article 3 reliance, retaining attribution/ShareAlike/NonCommercial duties
  and an account-specific generator-contract evidence caveat.
* **DOLCI Tool Use manual acceptance**: Recorded Professor Peter
  Schneider-Kamp's project-owner acceptance of the four remaining Tool Use
  residual layers as low risk for current academic/non-commercial
  scientific-research training. The policy DAG clears the Tool Use branch;
  detailed findings remain, no Article 3 reliance is asserted, and Article 4
  remains conditional on lawful access and absence of an effective reservation.
* **DOLCI Tool Use rights audit**: Decomposed all 227,579 non-SA rows into
  SimFC (200,000), Science QA (22,576), and DeepResearch (5,003). SimFC has
  93,593 rows touching xLAM schemas, at least 45,577 touching ToolACE schemas,
  and 92,800 without a local match to either. Science QA retains abstracts in
  1,580 M3, 8,838 M4v2, and 5,304 M5v2 rows. Every DeepResearch prompt was
  traced: 2,572 SearchArena, 1,685 OpenSciLM, 692 TaskCraft, 49 WebWalkerQA,
  and five residual rows. Generated and named licensed layers are cleared;
  unassigned schemas, scholarly expression, residual prompts, and web snippets
  retain Article 3 fallback.
* **RLVE prompt-expression audit**: Reconciled all 250 variants in both
  AllenAI filtered verifiable-reasoning releases and reviewed each retained
  prompt template against its cited source where applicable. The resulting
  bins are 124 native/no-comment, 61 functional rewrites, 45 close/constrained
  restatements, 15 source-specific/expressive carryover, one unavailable
  source, and four unmatched variants. Corrected the earlier cited/unmatched
  row counts and retained the strongest concern for four prompts with diagrams,
  worked examples, coined structure, or a distinctive rewrite system. The
  project owner then manually accepted the complete RLVE prompt family for
  current academic/research training and downstream-mixture consideration,
  while retaining the findings and Article 3 fallback rather than
  misclassifying the sources as open licensed.
* **AllenAI math/reasoning lineage correction**: Reclassified Open Math 2 50K
  through NVIDIA OpenMathInstruct-2 CC-BY-4.0, GSM8K MIT, and DeepSeek-R1 MIT
  distillation terms rather than Article 3. Mapped the two filtered verifiable
  reasoning corpora to MIT-licensed RLVE-Gym; the later prompt-level audit
  supersedes the initial blanket treatment of all source-commented variants.
* **DOLCI and transformation decomposition**: Decomposed the effective DOLCI
  SFT roots into 21 non-tool families and five ToolU mixtures, resolved the
  Ai2-authored logic-puzzle layer, documented the remaining AllenAI evidence
  gaps, cleared Salesforce xLAM from CC-BY/APIGen evidence, and decomposed all
  four `transformations-*` roots through exact accepted-row seed provenance.
* **WildChat privacy evidence reconstruction**: Located the historical
  99,688-row regex-screening summary and its introducing commit, verified that
  the scanned source remains local, and recorded that the scanner, exact
  patterns, row-level hits, adjudication, and removal evidence are absent. A
  fresh broad-regex check reproduced the scale but not the exact counts; the
  historical result is therefore classified as risk screening rather than a
  reproducible anonymisation audit.
* **WildChat consent scope**: Recorded the original two-step affirmative
  collection/use/publication consent described by the ICLR paper, while
  preserving the unresolved distinction between broad research/product
  development consent and explicit downstream third-party model-training
  consent under GDPR.
* **WildChat permission decision**: The project owner accepted the documented
  affirmative WildChat consent as express permission for current research
  model training. The rights DAG now clears the retained WildChat prompt node
  and direct Synquid derivatives while keeping GDPR/PII controls independent.

## 2026-08-16

* **AESLC dependency resolution**: Resolved the shared AESLC task-provenance
  leaf for four independently regenerated FLAN variants. The official source
  is CC BY-NC-SA 4.0 and the current academic/non-commercial use is directly
  licensed; the distinct Apache synthetic layer, low-overlap/PII audit, and
  remaining attribution, ShareAlike, commercial-use, and privacy scope are
  recorded separately.
* **QReCC dependency resolution**: Resolved four FLAN normal/input-inversion
  and few-shot/zero-shot variants against Apple's CC BY-SA 3.0 dataset terms
  and the retained Gemma-generated low-overlap/PII audit. Raw QReCC component
  and web lineage remains documented without treating it as retained verbatim
  expression in the synthetic DFM rows.
* **Declarative rights DAG**: Moved the complete DFM9 source-rights node and
  edge specification out of Python seed conditionals into authoritative CSVs.
  The Python tool now validates and resolves the graph, materializes dossier
  mirrors, and atomically updates declarative node status.
* **DFM9 copyright/TDM triage**: Added a token-reconciled review of all 168
  effective top-level DFM9 repository/agreement sources, distinguishing direct
  terms, Article 3 reliance, conditional Article 4 paths, mixed derivatives,
  and unresolved terms. The 93.93B-token register preserves acquisition and
  current HF metadata evidence and identifies component-level counsel work.
* **Synthetic seed clarification**: Recorded the project-owner confirmation
  that DynaWord/Common Pile passages used by project-generated DFM8 synthetic
  data are public domain or open licensed; these rows use direct source/project
  rights rather than a TDM exception, subject to licence obligations.
* **DFM9 exposure correction**: Superseded the 168-source/93.93B-per-epoch
  claim. The effective sample has 161 sources and 399,693,515,389 covered
  tokens across five index sets (79,938,703,077.8 average tokens/epoch); seven
  prospective tokenized additions are absent from sampled coverage.
* **Article 3 candidate audit**: Added component and row-level evidence for
  DFM Dyna, DOLCI, Sapient, Tulu, Nemotron, OpenHermes, Oliver derivatives,
  TV2R, WildChat, SciRIFF, AllenAI reasoning/math/IF sources, AI Arena,
  translation, DynaWord-grounded MT, MATH, and GovReport. Reclassified only
  sources with traceable direct terms/status; retained explicit fallbacks for
  unresolved components.
* **DBC/Lex.dk agreement scope**: Recorded the project-owner confirmation that
  both agreements permit model training and model release. Article 3 is not
  needed for those acts; Commission-template categorisation and any unconfirmed
  retention, source-redistribution, attribution, duration, security, and
  broader downstream-use terms remain for confidential contract review.

## 2026-08-15

* **Mimir compliance readiness**: Added a provisional EU AI Act scope and
  Article 53 documentation-gap assessment based on the authenticated model
  card, MIMIR License v1.0, technical report, and current Commission guidance.
* **Mimir legal dossier**: Started `legal/` with Commission-template public
  training disclosure, scope/provider analysis, copyright policy, Annex XI and
  XII drafts, GDPR and governance workstreams, and structured evidence/action
  registers. Historical DFM6/DFM7/DFM8 corpus reconciliation is a P0 gate.
* **Mimir evidence reconstruction**: Recovered exact DFM6/DFM7/DFM8 checkpoint
  boundaries and nominal token exposure; generated complete final-DFM8,
  synthetic-method, HF-snapshot, evaluation, release-hash, dependency, compute,
  and energy-estimate records. Confirmed that the release run used no dedicated
  validation corpus. Historical source-version union and human/legal approvals
  remain open.
* **DFM10 Alexandra integration**: Added train-only original Nordjylland
  summarization, Danish ScandiQA, selected Danish/English MultiZebraLogic,
  DaNE, and DaCoref conversions, Gemma 4 tokenization, and sampling policy.
* **Training compute**: Added a recurrence-aware HRM-Text XL FLOP reference,
  including the five-BP-step and maximum-attention upper bound.
* **LexDK memorization probe**: Added a reproducible original-source
  prefix-extraction test for the DFM8 XL 1.65M EMA HF export. The exhaustive
  1,058,010-generation follow-up found no exact 64-token extraction. Its maximum
  LCP was 55 tokens in a constrained mathematical formula; the 20-token tail is
  dominated by duplicated listed-building prose.

## 2026-08-13

* **DFM10**: Added the verified Andersen modernization train/eval split, repeat-20 training integration, token accounting, zero-shot evaluation contract, and document-overlap caveat.

## 2026-08-11

* **Migration**: Upgraded the repository knowledge corpus from its lightweight LLM-wiki convention to an OKF v0.2 bundle.
* **Structure**: Added YAML concept metadata, directory indexes, standard Markdown links, lifecycle metadata, and local conformance validation.
* **Superseded Refactoring Decision**: Initially classified mature aggregates as staged split candidates; superseded later the same day by semantic heading and chronology splitting.
* **Validation**: Added regression-tested enforcement that every knowledge directory has an index covering its immediate concepts and subdirectories.
* **Refactoring**: Split nine oversized collections and four nested chronology records into focused heading- or date-bounded concepts while preserving compatibility paths and anchors.
* **Scale**: The refactored bundle contains 461 concepts and 18 indexes; no concept exceeds the enforced 50,000-byte boundary.

## 2026-05-20

* **Initialization**: Created the original Markdown knowledge corpus and agent maintenance rules.
## 2026-08-16 - Mimir licence classification

- Moved the DFM9 source-rights DAG's source-specific facts from Python into
  authoritative declarative CSV specifications under
  `legal/specs/dfm9-source-dag/`; register CSVs are now validated generated
  mirrors and the resolver contains only generic graph logic.
- Completed provenance and synthetic-output audits for the eight Opinion
  Abstracts variants. Their two crawled upstream source works remain Article 3
  candidates because no direct source-content licence was found; the generated
  rows are low-overlap, PII-audited recreations rather than raw redistribution.
  Recorded the original NAACL 2016 task structure: professional movie-review
  snippets to editorial consensus, and supporting debate arguments to an
  editorial central claim.
- Clarified that Article 4 / Danish section 11 b is a plausible alternative for
  the later Opinion Abstracts TDM, but remains conditional because the dossier
  lacks acquisition-time evidence of lawful access and absence of an
  appropriate machine-readable rights reservation.
- Audited current Opinion Abstracts opt-out signals. Rotten Tomatoes currently
  expressly prohibits data mining and AI training in online terms; iDebate has
  restrictive general reuse terms but no explicit TDM/AI signal. The academic
  ZIP/README and TFDS packaging expose no reservation, which does not waive
  underlying rights. Added a structured observation register and propagated
  the differentiated Article 4 status into the DFM9 legal outputs.
- Recorded the project decision to rely on Article 3 / Danish section 11 c for
  both Opinion Abstracts source works rather than Article 4. Marked those two
  DAG leaves resolved for the current research purpose while preserving all
  statutory conditions and non-research limitations.

- Added a canonical source-rights dependency DAG for DFM9. The first detailed
  subtree maps DFM Dyna through Apertus, Tulu, SmolTalk2, EuroBlocks, DOLCI
  puzzle, WildChat, and agentic-code dependencies; all 161 effective sources
  are present as roots for incremental expansion. Recursive status propagation
  prevents shared upstream decisions from drifting across derived datasets.
- Added a purpose-specific rights-basis algebra and generated DFM9 projection,
  separating overlapping factual atoms from one conservative current-research
  headline. At that stage Article 3 dominated mixed direct/exception coverage
  and no source had an affirmative Article 4 determination; the 2026-08-17
  FLAN v2/SciRIFF decision supersedes that latter state.

- Reclassified `oliverkinch/instruct-bt` on 2026-08-17 after the project owner
  confirmed that DynaWord and the `dkmedier`, `odense`, and `danskerhverv`
  components are covered by source terms or DFM/data-owner agreements that
  permit training and model release.
- Reclassified `oliverkinch/danish-summarization` on 2026-08-17 after the
  project owner confirmed that EUR-Lex Sum is public-domain/CC-BY derived and
  the Nordjylland component belongs to the accepted DynaWord source family.

- Documented the legal-work consequence of an approved non-GPAI determination:
  preserve the GPAI dossier as contingency evidence, prioritise scope/compute
  sign-off, and continue independent copyright, contract, GDPR, release, and
  downstream-system work.
- Added the primary Mimir v1 non-GPAI route under the Commission's current
  conjunctive criterion: independently approve and freeze the version-specific
  `1.19e22` FLOP bound, qualify public wording, and reassess on further training
  or guidance changes rather than relying on licence exemptions.
- Documented a prospective Article 2(6) alignment route: narrow the licence
  and release to sole scientific R&D, exclude standalone teaching and
  operational use, align derivatives/outputs/repository controls, and treat
  changes as a new version because v1.0 release facts and accepted rights
  cannot simply be rewritten retroactively.
- Clarified that Article 2(6), if established, excludes Mimir and its output
  from the AI Act as a whole, while Article 2(8) only covers pre-release R&D;
  neither affects copyright, GDPR, contracts, or other applicable law.
- Confirmed against Commission GPAI scope-guideline section 4.2.1 that the
  MIMIR License's non-commercial/research-only restriction and separate
  commercial licensing disqualify it from the AI Act's free/open-source GPAI
  exemption; retain the `open-weight` description.

## 2026-08-15 - Mimir compliance engineering closure

- Recorded Professor Peter Schneider-Kamp, University of Southern Denmark, as
  accountable technical/compliance decision owner; recorded the 2026-08-15
  open-weight Hugging Face release and attestation that no source was acquired
  after 2026-07-14. Provider identity and legal scope remain under review.
- Reconstructed exact DFM6/DFM7/DFM8 sampled source exposure for the release
  checkpoint: 1.351B rows and 431.833B non-padding source tokens across 31,868
  phase/task records.
- Froze 1,252 release-evaluation artifacts and consolidated synthetic pipeline
  generation/audit evidence.
- Added explicit data/content-control and safety-coverage assessments.
- Superseded the claimed 125,091-token DFM8 discrepancy: the two values measure
  per-epoch sampled source tokens and concatenated token-store length.
- Reclassified the legal action register so all remaining rows require human
  authority, counsel/DPO review, partner attestation, contracts, telemetry, or
  risk acceptance.

## 2026-08-17 - Sapient synthetic/math rights decomposition

- Reconciled all eight retained broad Sapient families to exact DFM9
  per-epoch exposure and added them as declarative source-rights DAG children.
- Cleared PleIAs SYNTH under CC-BY-4.0/open-seed terms, DeepMind Mathematics
  under Apache-2.0, and AMPS Mathematica under the authors' MIT release.
- Limited Sudoku Extreme's unresolved issue to possible compilation/database
  rights in unlicensed community collections; individual puzzle and solution
  grids are functional records rather than expressive prose.
- Kept the aggregate Sapient Article 3 fallback for Sudoku's narrow caveat and
  unresolved Platypus, FLAN/factual-FLAN, and Tasksource branches.
- Superseded the initial Sudoku fallback later on 2026-08-17: the project owner
  manually accepted the residual compilation/database-right risk for current
  academic/non-commercial research use. All four Sapient synthetic/math
  families are now clear without Article 3; the aggregate fallback remains
  only for Platypus, FLAN/factual FLAN, and Tasksource.
- Decomposed all 266 factual-FLAN files into 13 canonical source families and
  exact per-epoch exposure. Direct/open terms cover eight families; RACE,
  DREAM, TriviaQA, WebQuestions, and part of CoQA use Article 3 for current
  research. Recorded Article 4 as conditional rather than cleared because
  acquisition-time reservation evidence is incomplete.
- Superseded that initial conservative classification by project-owner
  decision: RACE, DREAM, WebQuestions, and uncovered CoQA material use Article
  4 based on lawful long-running public distribution and no known reservation
  or challenge. Decomposed retained TriviaQA questions into 14 web-source
  groups: twelve use Article 4; JetPunk and TriviaCountry remain Article 3 due
  current machine-readable reservation signals or ambiguity.
- Superseded the TriviaQA source-group basis by project-owner decision: rely on
  the official repository's express Apache-2.0-for-code-and-data statement for
  the sampled question/answer rows. Source-site and UW-ownership caveats remain
  as non-blocking evidence; evidence documents are outside the sampled scope.
- Decomposed all 939,343 local Tulu 3 mixture rows into 19 source labels,
  including a 50,000-row OpenMath2 component omitted from the card's prose
  list. Initially retained Article 3 for uncovered FLAN v2 and SciRIFF source
  expression, then superseded that basis by project-owner decision in favor of
  Article 4 / Danish section 11 b. The shared decisions also clear the DOLCI
  and DOLCI-No-Tools DAG nodes, while Apertus remains partial at five other
  provenance boundaries.
- Established `legal/reports/dfm9-manual-acceptances-and-overrides.md` as the
  standing register for project-owner acceptances, overrides, and statutory
  route selections. Future manual decisions must be added there in the same
  turn without requiring a separate request.
## 2026-08-17 - Apertus copyright boundary decomposition

- Decomposed SmolTalk into 13 train subsets and SmolTalk2 into all 25 SFT
  recipe components; narrowed SmolTalk's Article 3 dependence to imported
  OpenHermes and LongAlign material.
- Reconstructed all 1,001,551 OpenHermes 2.5 rows into 19 source blocks and
  narrowed Article 3 to four residual source families.
- Assessed MoT prompt/editorial expression risk, grouped all 9,888 LongAlign
  rows for review, and separated EuroBlocks full-seed from seed-derived rows.
- Added reproducible component registers and expanded the declarative DFM9
  rights DAG accordingly.
- Recorded project-owner decision MAN-015 accepting Mixture-of-Thoughts'
  residual prompt/editorial risk without Article 3 reliance and MAN-016
  selecting Article 4 for four uncovered OpenHermes source families.
- Stratified the original 1,572 LongAlign marker cohort and superseded it as a
  full-document count: 49 additional late-marker rows produce 1,621 total.
- Reduced EuroBlocks' 5,169 source-retaining rows to 2,607 unique embedded
  documents and recorded marker, language, content, duplication, and domain
  strata without redistributing source text.
- On 2026-08-18, recorded MAN-017 and MAN-018 project-owner approval of the
  remaining LongAlign and EuroBlocks leaves under Article 3 for the current
  scientific-research purpose. The approvals preserve restrictive notices,
  provenance gaps, and memorisation-test cohorts and do not authorize raw
  redistribution or commercial use.
- Recorded an effective-source audit snapshot: 102/161 datasets and 56.932B
  tokens/epoch are DAG-cleared; 55 datasets/21.409B are partial and four
  datasets/1.597B unresolved. The next largest clearance targets are Sapient's
  retained FLAN/Tasksource/Platypus and the shared Tulu v2 family.
## 2026-08-18 - Split DFM9 Article 3 boundary accounting

- Added `pages/dfm9-article3-boundary-accounting.md` to keep narrow-boundary,
  top-level provenance, and counterfactual accounting separate from the large
  source-by-source copyright review.
- Linked the new concept from the main review and page index.

## 2026-08-18 - Define DFM9 memorisation source cohorts

- Added a deduplicated source-text plan grouped into agreement, Article 3,
  Article 4, and other operative bases.
- Required canonical source hashes across transformed/translated descendants
  and explicit proxy labels where original source text is unavailable.

## 2026-08-24 - Add gated long-context evaluation plan

- Added an opt-in 4K RULER smoke task to the evaluation scheduler, kept out of
  headline averages.
- Recorded the 4K serving limitation and the gated 8K+ RULER plan.
- Measured GovReport and NordjyllandNews source lengths and specified an
  English long-document summarization task plus a Danish multi-document
  retrieval/summarization task.

- Audited the active 8K extension run: 8,193-token data and global H attention
  are active, while the configured H-layer YaRN keys require correction before
  a future restart. Added the opt-in GovReport long task and recorded HF
  long-context candidates.

## 2026-08-24 - Implement 8K long-context evaluation headline

- Added capped LongBench English, LongAlign English/Danish, Marathon,
  validation-split QMSum, Danish Nordjylland summarization, and Danish EUR-Lex
  summarization tasks.
- Added independent merges and a `long_context_headline/*` aggregate; Marathon
  is format-only because its public HF conversion lacks answer keys.
- Corrected QMSum to use the validation split, which contains usable reference
  summaries, and propagated per-job 8K limits to the vLLM server.

- Measured the isolated 8K XL run with YaRN factor 2.0 at BP=5. A minimal
  device-placement fix was required for YaRN initialization; peak memory was
  effectively unchanged from the no-YaRN measurement (`107.5--109.0 GiB`
  allocated, `111.4--129.9 GiB` reserved per GPU).

## 2026-08-24 - Benchmark 4K versus 8K attention windows

- Completed matched 100-step XL benchmarks for 4K L-window/H-global, 8K
  L-window/H-global, and 8K L-global/H-global attention.
- Used fixed global batch 262,144, gradient accumulation 2, BF16 compute,
  FP32 FSDP parameters, BP=5, and excluded two compiler warm-up steps.
- The full 8K L+H run completed without OOM. Median step times were 1.102 s,
  1.235 s, and 1.253 s respectively; peak allocated memory stayed near
  106--107 GiB and reserved memory near 120--127 GiB per GPU.

## 2026-08-24 - Benchmark 16K and 32K attention windows

- Completed matched 100-step 16K benchmarks: median step times were 1.435 s
  for L-window/H-global and 1.643 s for L-global/H-global.
- At 32K, accumulation 2 made the local pack too small for 32K rows; those
  runs exited cleanly after sampler exhaustion. The valid accumulation-1
  configuration produced explicit CUDA OOMs on the first step for both
  attention layouts, at roughly 172--176 GiB allocated on 178.34 GiB GPUs.
  A trustworthy 100-step result is not feasible at this batch.

## 2026-08-26 - Replace the RULER smoke signal

- Added the production `ruler_8k` suite: all 13 implemented variants, 32
  examples per variant, eight scheduler shards, per-variant merge metrics, and
  the `long_context_headline_v3` aggregate.
- Matched low-level token counting to the export's
  `fix_mistral_regex=true` behavior, eliminating the 8,193-token requests seen
  in number-heavy variants.
- Replaced RULER's unavailable HotpotQA HTTP source with the official Hugging
  Face distractor-validation Parquet conversion and an atomic local cache.
- Completed the epoch-8 versus step-2.15M comparison and synced both points to
  `DFM5/dfm9-xl-8k`: RULER `0.76182 -> 0.57548` and nine-task long-context v3
  average `0.43326 -> 0.40624`.
- Audited actual vLLM input lengths. Eight suites are predominantly above 4K,
  while plain Danish summarization is entirely below 4K and LongAlign DA has
  only five examples; recorded these as limitations of the v3 headline.
- Compared short-context averages at epoch 8 versus 2.15M: standard
  `0.72830 -> 0.65960` and DFM `0.62751 -> 0.54625`. Synced the 2.15M suite row
  to `DFM5/dfm9-xl-8k` and recorded the 4K-versus-YaRN baseline caveat.
## 2026-08-26 - DFM10 source-level quality audit

- Added a deterministic 178-source inventory and exact tokenized-example
  sampler covering inherited DFM8/DFM9 data and DFM10 additions.
- Added an eight-server E4B audit with disjoint resumable partitions, task-aware
  language/coherence/training-value judgments, locked validation, and atomic
  publication of one JSONL result.
- Queued execution behind the active Folketing acceptance audit because its
  eight E4B servers leave insufficient headroom for a second server set.

## 2026-08-26 - Full recurrent-call activation checkpointing

- Added opt-in `activation_checkpointing=full` training support while keeping
  `none` as the default and preserving existing checkpoint/EMA formats.
- Full mode applies non-reentrant PyTorch checkpointing only to differentiable
  recurrent calls. At BP=5 these are `H0`, `L3`, `L4`, `L5`, and `H1`; the
  detached `L0--L2` calls are not checkpointed.
- Added CPU parity, recomputation-count, evaluation-inactivity, and compile
  checks. CUDA FSDP2/FA4 memory and throughput benchmarking remains pending.

## 2026-08-26 - FSDP2 composable activation checkpointing validation

- Superseded functional recurrent-call checkpointing after CUDA validation
  exposed an FSDP2 BF16-versus-FP32 recomputation metadata mismatch.
- Switched full mode to composable per-Transformer-block checkpoint wrappers
  applied before FSDP2 wrapping and resumed DFM8 XXL from step 152500.
- Measured 41984 MiB peak allocated and 49970 MiB reserved per GPU, versus
  143027 MiB and 165168 MiB without checkpointing; recorded the approximately
  1.8x observed step-time cost of the current uncompiled checkpointed path.
- Kept vanilla RoPE for the next longer-context experiment because the prior
  YaRN comparison was confounded by an incorrectly exported checkpoint.
- Added and measured L-only selective checkpointing on DFM8 XXL: 90228 MiB
  allocated, 105344 MiB reserved, and 5.59 seconds per optimizer step. The
  production campaign resumes from step 153500 without checkpointing.
- Audited multi-node readiness: core rank/device/data/DCP handling is present,
  but scheduler launch, carry/world-size handling, accumulation synchronization,
  and hybrid sharding remain production gaps. FSDP is the safe existing choice
  for XXL; hybrid within-node sharding is the recommended multi-node design.

## 2026-08-27 - XXL pause and multi-node audit refinement

- Stopped DFM8 XXL against complete `ephemeral_step_161000`; discarded the
  unsaved tail through approximately step 161115 and left the scheduler stopped.
- Verified HRM carry files contain `None`, making same-checkpoint world-size
  changes substantially simpler than for stateful recurrent carries.
- Confirmed native FSDP2 2D-mesh HSDP and accumulation synchronization APIs;
  neither is wired into the trainer yet.
- Verified LUMI XXL-32 used valid 4096-token local batches at 99.44% packing
  utilization. Recorded LR `1e-3`, BP max 3, update count, and absent clipping
  as more plausible divergence factors than batch geometry alone.
- Added the implementation-gated multi-node and 32K plan: fixed-membership SSH
  TorchRun, run-derived carry/checkpoint contracts, efficient accumulation,
  native FSDP2 HSDP, world-size resume parity, and a 64/32/16/8-GPU staged
  4K/8K/16K/32K curriculum at constant 262,144-token global batch.

## 2026-08-27 - DFM10 source-quality report

- Added a reproducible LaTeX/PDF report over the completed 17,455-row,
  177-source audit, ranked most-severe first with quantitative scores and
  recurring qualitative findings.
- Superseded the initial combined post-training label after review. The initial
  177-source report independently classified task role (169 SFT, 6 auxiliary SFT, 2
  midtraining) and measured quality (135 use, 32 filter, 10 repair), so a broken
  SFT conversion is no longer conflated with a sound midtraining source.
- Extended the report to 178 sources and 17,555 judgments with a balanced
  100-row sample of accepted Folketing transformations from completed audit
  partitions 0--5. Added the DFM-Mimir category taxonomy and a source-specific
  remediation table with full-row B200 repair/re-audit GPU-hour estimates. The
  combined report has 169 SFT, 6 auxiliary SFT, 2 midtraining, and 1 mixed
  source, independently of 136 use, 32 filter, and 10 repair dispositions.

## 2026-08-28 - PrefixLM routing reuse

- Precomputed data-dependent PrefixLM routing tensors once per microbatch and
  reused them across recurrent FA4/ROCm attention calls while preserving the
  existing backend fallback API.
- Marked routing dimensions dynamic before compilation to prevent packed-shape
  graph specialization, and guarded disabled resume-trace `.item()` calls.
- Verified bit-exact real-B200 FA4 forward and gradient parity plus focused
  FA4/ROCm tests. Production-geometry XXL timing improved by 11.5--12.4%.
- Reprofiled the optimized path: D2H copy rate fell 99.66%, kernel launch rate
  fell 26.7%, and index/gather/scatter share fell from about 10.2% to 8.3%.
- Added a shorter post-commit profile with four complete rank traces. GPU
  kernel-active time is 95--96%, NCCL-only time is 9--12%, and PrefixLM
  indexing plus radix sort is about 10.4% of summed kernel time. Prioritized an
  FA4 `seqused_q`/`seqused_k` prototype and recurrence-aware H/L-level FSDP
  wrapping as the next performance experiments.
- Added an explicit compile-mode selector with an unchanged `default` and a
  safe `max-autotune-no-cudagraphs` diagnostic. Two autotuned XXL runs were
  neutral versus default (`2.982--2.986 s` versus `2.987 s` median), so default
  remains recommended. Graph-enabled max-autotune exposed an output-lifetime
  error and remains a separate CUDA-graph integration task.
- Added an opt-in SM100 FA4 PrefixLM path using `seqused_q`/`seqused_k` over
  original packed Q/K/V storage. Direct B200 tests are bit-identical for
  forward and all gradients, including prefix-only and padded batches.
- Documented FA4's undefined gradients for `seqused`-excluded storage rows and
  the required prefix/causal/padding masks. A corrected 40-step XXL run stayed
  finite at 2.865 s median and 154148 MiB observed peak memory, about 4.1%
  faster than the earlier controlled gather result. `gather` remains default
  pending a clean bracketed A/B and longer resumed-checkpoint run.
- Completed a clean same-tree gather control at 2.978 s median and 3.035 s
  mean. The corrected `seqused` path is 3.79% faster by median, 4.08% faster by
  mean, and used 7,376 MiB less observed peak GPU memory. Both runs remained
  finite with nearly identical final loss and accuracy.
- Reprofiled the corrected `seqused` path. Kernel launch rate fell about 31%,
  index/radix work fell from 11.01% to 0.70%, and no radix-sort kernels remained.
  Six full-QKV undefined-gradient masks per FA4 backward are now the clearest
  target at 8.22% of summed kernel time; exposed NCCL is mostly 5--6%, so FSDP
  restructuring moves behind mask fusion/pre-zeroed backward buffers.

## 2026-08-28 - DynaWord instruction repair

- Audited all 70,081 rows in the four `oliverkinch/da-instruct-dynaword*`
  sources, conservatively dropping one repeated judge failure and damaged or
  incomplete authentic targets.
- Regenerated only 4,303 mismatched Danish prompts with Gemma 4 31B IT and
  re-audited every repaired pair with E4B; no authentic target was rewritten.
- Built and exhaustively validated a 65,548-row replacement with 39,422,832
  Gemma-rendered tokens, disabled the four legacy prefixes, retained repeat
  four for the repaired prefix, and rebuilt the DFM10 tokenized union.

## 2026-08-29 - Mimir v1 evaluation contract audit

- Audited the DFM8 XL 1,650,000-step EMA MMLU artifacts and corrected the
  causal record: production used the Gemma chat template, while the
  reasoning-prone subjects conflict with the historical one-token direct-answer
  contract. A separate legacy-token probe exposed a real fail-closed requirement
  but did not reproduce the production prompt path.
- Made invalid standard MCQ outputs score zero, added strict unambiguous choice
  extraction, explicit Gemma MCQ answer instructions, and tokenizer-contract
  validation that rejects legacy HRM markers for Gemma exports.
- Added MMLU-aware shard aggregation. A remerge of the historical artifacts now
  reports 57 subjects and reconstructs all 14,042 subject-level examples instead
  of the misleading aggregate `n=228`.
- Confirmed two independent result artifacts: expanded PIQA EN rejected correct
  bare letters because its wrapper contract differed from the scorer, and the
  Generative Talemaader judge was truncated before every required grade line.
- Queued a four-shard corrected MMLU rerun under
  `logs/scheduler/mimir_v1_mmlu_corrected_20260829`, gated on fully free GPUs and
  configured to retain generations and merge locally before any W&B overwrite.
* **2026-08-29 - English OpenStax relevance allowlist:** Classified the 91
  recoverable English CC BY editions into 51 primary Mimir grounding sources,
  10 overlap-capped supplements, and 30 superseded/duplicate editions. Recorded
  exact inventory slugs and retained the existing pinned-artifact and legal
  activation gates.
* **2026-08-29 - DFM10 final source reconciliation:** Disabled DA-AR and the
  inherited DA-UK source, queued an eight-shard language/alignment-filtered
  DA-UK rebuild, integrated the validated Scientific Summaries repair, and
  rebuilt QReCC-II/SciBench with explicit complete response contracts. Added a
  measured reconciliation for all 32 audited Filter sources, removed aggressive
  repeats from borderline Danish sources, and recorded the final production
  gates before union rebuild and ten-epoch sampling.
# 2026-08-30

- Completed Danish Wikipedia grounded-chat generation/audit: all 128 shards,
  49,787 accepted chats, and 261,588 supervised assistant turns. Downstream
  materialization, export staging, tokenization, union activation, and DFM10
  resampling remain pending behind the shared OpenStax runner.
- Registered the active Danish Wikipedia, OpenStax, and Tidsskrift generation
  efforts in `exports_dfm10/manifest.json` as four package-level WIP records.
  Added an inventory-only refresh command so pending packages do not require
  empty or misleading upload-ready directories.
- Reconciled Tidsskrift production with the completed strict-open harvest:
  audit all 189,392 available SFT candidates, require at least 125,000 accepted
  rows, and require 18,000 chats/100,000 supervised assistant turns. Added a
  lock-based handoff that starts generation after the active Wikipedia/OpenStax
  campaign releases all eight GPUs.
- Corrected the open grounded-chat shard gate after production showed that
  requiring every one of 400--650 requests to survive malformed-output retries
  incorrectly failed otherwise complete shards. Shards now require 98% valid
  generated-and-audited coverage; failed rows remain excluded and the global
  accepted-chat and assistant-turn gates remain fail-closed.

# 2026-08-29

- Prepared and queued two fail-closed DFM10 grounded-chat campaigns: 50,000
  Danish Wikipedia candidates with a 150,000-assistant-turn gate, and 160,376
  requests over 20,047 verified OpenStax passages with a 500,000-turn gate.
  Both retain source attribution, use independent Gemma 4 31B generation and
  audit, tokenize one target per assistant reply, and wait behind the active
  Tidsskrift campaign rather than competing for GPUs.
- Added a resumable, rate-limited, article-rights-gated Tidsskrift.dk OAI
  harvester; prepared audited-generation candidates from new DynaWord
  VoxPopuli and Kalliope sources while excluding DaKultur contamination; and
  integrated 5,982 gold DSL sentiment/FrameNet rows totaling 2,389,573 Gemma
  tokens at one pass.
- Surveyed Andersen/DSL-related Danish corpus candidates, recording explicit
  license gates for diaries, letters, literary editions, and annotation data.
  Reconciled local DynaWord 1.2.16 with Hub release 1.2.22 and identified six
  added configs totaling about 2.985B text tokens. Corrected the local
  Tidsskrift holding record and specified a fail-closed OAI-PMH harvest for a
  larger article-level openly licensed corpus.
- Added the completed 50,000-row OpenStax Mimir SFT corpus to DFM10 Hugging
  Face export staging under CC BY 4.0. Corrected Andersen provenance to the
  public AGPLv3 `ogierMontanus/hcandersenDk_data_2024` TEI corpus and recorded
  the Folketing/Rigsarkivet handover 14004 CC BY 4.0 terms. Published the
  validated 1,068-row Andersen training package to
  `schneiderkamplab/dfm10-andersen-modernization`; the held-out 119-row
  evaluation split was not uploaded. **Superseded publication scope:** all 26
  prepared DFM10 packages were subsequently uploaded publicly under
  `schneiderkamplab/dfm10-*`. A complete remote file, size, and LFS-hash audit
  verified 69,414,759 rows and 27,163,247,201 compressed data bytes without a
  mismatch.
- Ranked additional open-book sources for grounded SFT. Prioritized the already
  downloaded CC BY Open Logic source, then exact-edition Open Textbook Library
  and BCcampus pilots, with OAPEN/DOAB behind stricter per-book license and
  retrieval gates; recorded existing Gutenberg and Danish DOAB overlap.
- Completed the repaired 15,689-task DFM10 union and ten production epochs at
  101,731,426,509 tokens per epoch, with exact row and index-bound validation.
- Validated the repaired DA/UK translation output with a source-weighted E4B
  audit: 95/100 rows usable at one-pass sampling weight.
- Made final DFM10 production recovery-safe: WikiCat can resume at its E4B
  audit after completed generation, model phases wait for stable idle GPUs, and
  final sampling gates on fully-written artifacts instead of historical PIDs.
- Materialized the Mimir English OpenStax allowlist from 61 immutable official
  CC BY artifacts, with no `izumi-lab/open-text-books` rows, and prepared a
  provenance-preserving 13,000-request pilot targeting 10,000 accepted SFT
  rows. The pilot is queued behind the active WikiCat recovery workload.
- Invalidated the first MMLU failure-ontology aggregate after finding 4,896
  malformed JSON classifications among 5,630 requests. Updated the classifier
  to preserve and recover constrained output and to retry failed rows correctly;
  the invalid aggregate is quarantined until a complete rerun succeeds.
- Implemented and queued the separate Mimir five-by-100k campaign: 130k
  candidates per category across 640 atomic shards, eight restart-safe Gemma 4
  31B generation/audit workers, strict category and MCQ contracts, and a
  fail-closed final build requiring exact quotas and benchmark decontamination.
- Corrected the Mimir 500k structural checker after a 40-shard sample showed
  that valid substantive verification strings were being rejected. Requeued
  all affected shards without interrupting workers and retained superseded done
  markers for auditability.
- Narrowed Mimir 500k benchmark decontamination to reproducible normalized exact
  matching only. Added the canonical benchmark manifest and report generator;
  finalization now verifies the exact-mode marker and performs no lexical or
  semantic similarity screening.
- Superseded the Mimir 500k output cap: finalization now retains all accepted
  unique rows and combines a separately versioned 130k-candidate Technical/STEM
  top-up that must contribute at least 100k additional accepted rows. The
  exact-only decontamination report and final builder cover both roots.
- Completed the expanded Mimir campaign on 2026-08-30: 640/640 base and 128/128
  top-up shards passed with no failed shards, yielding 732,763 unique accepted
  rows and about 164.7M training tokens. Exact decontamination found zero
  matches among 736,127 accepted candidates against 44,982 benchmark units.
  Replaced the incompatible PIQA legacy dataset-script loader with the
  canonical static AI2 validation artifact and recorded its archive SHA-256.
- Staged the completed 732,763-row augmentation as the upload-ready local DFM10
  package `dfm10-mimir-grounded-expanded-sft`: three deterministic checksummed
  gzip shards, complete row-level provenance, dataset card and license notice,
  standalone validator, successful validation receipt, and matching root
  export inventory. No Hugging Face upload was performed.
- Integrated the expanded Mimir package into the DFM10 preparation path at
  repeat one. All 732,763 rows tokenized without skips into three tasks and
  138,161,296 Gemma-native tokens; the 15,711-task tokenized union includes
  them. Marked the older sampled DFM10 epochs as predating this addition rather
  than silently treating their unchanged indices as current.
- Published and remotely verified all 24 DFM10 packages marked
  `ready_for_upload` on 2026-08-30 (122,249,521,523 local bytes). Added a
  receipt-backed resumable upload runner, corrected the AI Arena card language
  marker from invalid `mixed` to `multilingual`, and promoted the exact
  verified set into the canonical uploaded-package inventory.
- The first DFM10 persona/Domsdatabasen production launch prepared all 29,500
  requests but stopped before generation when the GPU 0 vLLM server failed to
  become ready. No campaign server remains active and both export packages
  remain non-materialized WIP entries; the prepared requests are reusable.
- Lifted the publication hold on the five completed Bornholmsk, COR.SEM,
  Danish Book Ads, DiEM modernization, and SKS TEI packages. All five were
  uploaded to `schneiderkamplab`, remotely file-set verified, and added to the
  canonical uploaded inventory. Corrected the Bornholmsk dataset-card language
  field from the invalid dialect tag `da-bornholm` to ISO `da` before upload.
- Replaced the standalone Mimir answer-contract waiter with a retrying DFM10
  shortest-work-first queue. It waits for Tidsskrift, then runs Doms/persona
  (Doms shards first), Danish lexical generation/audit, and the answer-contract
  audit; one exhausted stage no longer strands all later work.
- Recovered the DFM10 shortest-work-first queue after its persona/Doms clients
  failed before inference because `pyarrow` was absent from the `audit` conda
  environment. Installed `pyarrow==25.0.1` using `uv pip`, added dependency
  preflight and per-stage log isolation, reset the queue, and verified all eight
  GPUs serving and processing Doms generation at 100% utilization.
- Added a separate post-integration benchmark-data plan for Mimir. It
  prioritizes deterministically verified instruction following,
  event/coreference commonsense, and executable passage arithmetic before
  measured MMLU/ARC and BoolQ top-ups, with explicit shadow-eval and
  contamination firewalls.
- Started the validation-gated ten-epoch DFM10 resample from the current
  Gemma-native tokenized union. Added `scripts/resample_dfm10_current.sh` to
  stage, validate, preserve the prior snapshot, and promote safely; also made
  the Filter reconciliation report tolerate audit-only unmatched records that
  have no sampled-row estimate.
- Completed and promoted the current ten-epoch DFM10 sample: 15,737 tokenized
  tasks, 232,138,339 rows and 103,143,215,009 tokens per epoch over a
  212,996,621,848-token backing array. All spans passed bounded validation and
  the 2026-08-29 sample remains available as
  `data/sampled_dfm10_pre_20260830`. Recorded the exact DFM8 comparison and the
  exclusion of four still-running Mimir campaigns from this snapshot.
- Assessed the sampled Folketing weight. Its four correlated reconstruction
  families provide valuable formal/historical Danish coverage but occupy
  17.497B tokens (16.96%) per epoch from 3.66M underlying windows; recorded the
  independent 87/100 usability result, the weaker 18/25 error-correction slice,
  and a non-binding approximately 4.97B-token capped diagnostic mix.
- Refined the proposed Folketing remediation to a strict quality decision per
  3.66M underlying source windows followed by equal 1M-row caps on all four
  task families. The cap alone is approximately 5.36B tokens/epoch; the
  independent no-issue criterion retained 59/100, but its row labels cannot be
  applied to the full corpus without a new window-level filter.
- Clarified DFM9/DFM10 scale: current DFM10 is 9.81% larger by tokens but 4.42%
  smaller by rows; the proposed equal Folketing caps would make it roughly
  91.00B tokens/epoch, 3.12% below DFM9, solely because they remove about
  12.14B tokens of correlated Folketing exposure.
- Recorded the DFM9 quality comparison: DFM10's repaired representations and
  grounded/native additions are materially better engineered, but downstream
  superiority remains unproven for the uncapped 17%-Folketing mix. The
  filtered/capped mix is expected to be broadly stronger and should be tested
  by an equal-token continuation A/B from one checkpoint.
- Corrected “less math” to the precise claim: DFM10 has 4.463B fewer
  OpenMathInstruct2 tokens because it retains 7.49M verified, PRM-filtered,
  deduplicated, and decontaminated rows instead of DFM9's 25.02M duplicated
  CoT/direct rows. This does not establish that total math supervision is lower.

## 2026-08-30 - DFM8 XXL skip-only production boundary

- Rolled the DFM8 XXL run back to complete `ephemeral_step_229500`, disabled
  clipping, and enabled pre-moment gradient skipping at norm 1.0.
- Verified that skipped batches leave parameters, AdamATan2 state, weight
  decay, and EMA untouched; added exact skipped-gradient norms to console
  diagnostics.
- The guard saved protected regular checkpoints at steps 229505, 229508, and
  229528. The final bounded trial skipped twenty consecutive batches with
  norms from 8.50684 to 1375.56, so the scheduler remains stopped at this
  boundary rather than silently consuming more training data.
- Direct DCP tensor hashes were identical at steps 229508 and 229528 for a
  production model weight and its Adam step, first moment, second moment, and
  EMA, confirming that skip-only steps made no hidden optimizer update.
- The skip-only losses were normal rather than elevated: mean 1.075978 over
  steps 229506--229528 versus 1.096311 for sparse clipped samples at
  229400--229505. This localizes the event to backward/recurrent sensitivity,
  not forward cross-entropy divergence.
- Superseded the assumption that skip-before-moments at the same threshold is
  a drop-in replacement for clipping. A separately calibrated catastrophic
  threshold, a hybrid policy, or source-region filtering must be selected
  before continuation.
- Ran same-checkpoint non-W&B comparisons of clipping-only and hybrid skip
  thresholds 10, 100, and 1000. Clipping completed 50 steps; every hybrid
  entered a skip cascade and stopped after only 9--14 steps. The retained
  results are under
  `logs/training/dfm8_XXL_1epoch/gradient_guard_ab_229500`.
- Resumed production from untouched `ephemeral_step_229500` at LR `2.5e-4`
  with norm-1 clipping and skipping disabled. Both remaining training rows use
  this fallback configuration.
- Through step 229730 the fallback remained operationally stable at about 2.8
  seconds/step. Four sampled gradients clipped, including two extreme raw
  norms, but the latest norm recovered to 0.213 and median loss remained 1.073;
  this is contained instability rather than divergence.
## 2026-09-02 - Source-grounded English FineInstructions 1M campaign

- Started a detached English campaign targeting exactly 1M accepted grounded
  pairs and 1M corresponding multi-turn chats on owned GPUs 4-7.
- Imported 19,479 pilot FineTemplates and extracted ten equal 50,000-window
  grounding lanes from pinned filtered Common Pile sources.
- Added round-robin source balancing, batched HNSW retrieval, resumable
  per-document retrieval progress, exact final materialization, and full source
  context for chat generation and independent chat audit. Final artifacts omit
  the teacher-only grounding documents.
- Recorded that a future Danish lane excludes LexDK and DBC and must qualify
  the published English-trained FineInstructions artifacts before use.

## 2026-09-03 - DFM11 tool-source remediation sizing

- Estimated the outstanding tool-source cleanup as primarily a 16-32-core,
  64-128-GiB CPU/storage workload. A stratified semantic audit needs about
  0.5-1.5 B200 GPU-hours; exhaustive LLM judging is neither needed nor advised.
- Superseded the initial execution envelope for the active remediation: use up
  to 128 CPU workers and reuse the existing GPU 0-3 vLLM endpoints at
  concurrency 64 per endpoint (256 aggregate), without managing their servers.
## 2026-09-04 - DFM11 repaired tool-source packages

- Rebuilt Glaive and ToolACE with source-specific native call/result pairing;
  canonicalized Nemotron Agentic tool-calling and DFM8 synthetic native calls.
- Exhaustively structure-validated 926,872 repaired source rows and audited a
  deterministic 2,000-row sample per package with four existing Gemma 4 26B
  A4B endpoints at 64 concurrent requests per endpoint (256 aggregate).
- Retried both truncated audit responses; final result is 7,876 accepted and
  124 rejected, with zero unresolved request errors.
- Tokenized the repaired packages plus Mathagentic with 128 CPU workers into
  `data/tokenized_dfm11_additions`: 2,822,887 training samples and 924,048,714
  tokens. The final DFM11 union remains blocked on the absent
  `data/tokenized_dfm10` base store; sampling additions alone is prohibited.
- Re-tokenized the same complete additions store with the requested 64-worker
  setting in 267.4 seconds; counts and token totals were unchanged.
- Uploaded all four repaired replacement packages to `schneiderkamplab/*`,
  verified every expected remote file and manifest, recorded the final Hub
  revisions in `config/data/dfm11_tool_replacements.yaml`, and retained the
  receipt at `logs/dfm11_tool_replacements_upload_receipts.json`.

## 2026-09-04 - FineInstructions score-5-only policy reaffirmed

- Confirmed that DFM11 must not use upstream FineInstructions Nemotron rows
  scored 1-4, even to fill unused token budget. A stronger target model should
  not be trained on weaker synthetic supervision merely because it is abundant.
- Score 5 remains only an eligibility gate; independent correctness, source
  copying, PII, decontamination, diversity, and licensing checks still apply.

## 2026-09-04 - FineInstructions Nemotron excluded from DFM11

- Superseded the score-5-only candidate policy and excluded the upstream
  `fineinstructions/fineinstructions_nemotron` corpus from DFM11. Its unresolved
  Common-Crawl provenance, copyright, PII, and source-copy risks outweigh the
  expected marginal value for Mimir.
- Set its cap and repeat to zero, removed it from the downloader manifest, and
  made its retained selective-materialization script fail closed. No source
  rows had been downloaded, converted, tokenized, or sampled.

## 2026-09-04 - Folketing full-audit server recovery

- Diagnosed idle GPUs 0-3 as four audit-owned vLLM servers having received
  `SIGTERM`; the resumable audit clients and partial decisions remained intact.
- Relaunched only those servers with the `audit` Conda environment's explicit
  `CUDA_HOME` and `PATH`, restoring audit throughput. The resume pass will drop
  and retry transport-error decisions created while the endpoints were down.

## 2026-09-05 - Folketing full-audit retry after power interruption

- Confirmed complete first-pass coverage of all 2,548,956 deterministic rows;
  partial files and completed verdicts survived the cluster interruption.
- Restarted four audit-owned vLLM servers and the post-audit pipeline. Raised
  the constrained verdict response ceiling from 256 to 1,024 tokens for 24
  stubborn rows that did not emit JSON within the smaller budget. This resolved
  20 rows; a 2,048-token ceiling did not resolve the final four. Acceptance
  criteria and the strict schema remained unchanged.
- Superseded later the same day: audit-owned vLLM servers on GPUs 0-3 are
  stopped after all partition audits finalize. Four repeatedly unresolved rows
  were preserved in a sidecar and excluded fail-closed; no further retries are
  performed. The post-audit pipeline now skips endpoint checks when all four
  final decision files already exist.
- Manually reviewed all four sidecar rows and confirmed rejection: every target
  retains material OCR corruption, and all contain incomplete or page-derived
  structure; one is additionally too garbled to provide useful supervision.

## 2026-09-05 - Danish FineInstructions silver gate failed

- Recorded that Danish retrieval qualification passed but production
  instantiation quality did not: 17.45% of the first 3,736 positive labels
  retained unresolved `<fi>` markers, and the same-model audit accepted all 17
  such rows in a deterministic 100-row sample. Danish instantiator training is
  blocked pending deterministic structural rejection and a stronger semantic
  audit.
- Resumed raw generation as eight race-free per-GPU workers with 1,024 requests
  in flight each and an 8,192-row work window. Raised the raw-positive target
  from 130,000 to 180,000; measured mean KV-cache occupancy was 91.4% and mean
  GPU utilization was effectively 100% over 30 seconds.
- Added and launched a fail-closed post-generation supervisor. It requires the
  strengthened full audit plus at least 95% acceptance and zero structural
  defects in an independently judged deterministic 500-row sample before the
  Danish Qwen3.5-4B instantiator training can start.
- Prevented silent helper-data attrition at the 4,096-token limit: audit targets
  are now 120,000 positives and 6,000 negatives, followed by exact
  100,000/5,000 in-limit materialization. A 1,000-row sample had shown 12.5%
  overlength rows.

## 2026-09-07 - DFM10 XXL per-layer diagnostic interval completed

- Stopped only after the fully written eight-rank `ephemeral_step_450500`, ran
  100 opt-in per-layer/cycle diagnostic snapshots through a fully written
  `step_451000`, and resumed the normal compiled continuation toward 500,000.
- Bounded large-tensor statistics before FP32 conversion and limited only the
  extra shadow replay to complete leading packed sequences totaling at most
  4,096 tokens per accumulation microbatch. The production updates retained
  the full 262,144-token global batch.
- Stored 456,390,354 bytes of detailed measurements at
  `logs/stability/dfm10_XXL_step450500_to_451000.jsonl`; diagnostics remain off
  by default and are explicitly disabled in the continuation row.
- Analysis found finite but severely ill-conditioned behavior: very large
  internal L residual streams are hidden by final RMS normalization, backward
  amplification is concentrated in early physical blocks, and L attention
  gates and Q/K scales are strongly saturated. Recurrent injection itself is
  stable and is not the leading intervention target.
- From the complete `ephemeral_step_452500`, ran matched ten-step, W&B-disabled
  BP=3 and BP=4 replays. BP=4 introduced a second differentiable L layer-0
  amplification hotspot (median 62.4x) while BP=3 exposed only the final L
  hotspot (median 44.3x). The sampled batches were benign, so this establishes
  a depth-dependent local mechanism but not the reduction in rare-event tails.
  Normal BP=5 production resumed from the untouched 452500 checkpoint.

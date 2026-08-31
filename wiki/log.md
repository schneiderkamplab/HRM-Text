# Knowledge Bundle Update Log

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

- 2026-08-29: Fused seqused FA4 prefix/causal output selection and padding
  zeroing in a NaN-safe custom-autograd Triton boundary. Direct FA4 outputs
  and gradients are bit-identical; a 100-step XXL A/B reduced median step time
  by 4.01% and mean step time by 3.39%.

- 2026-08-29: Completed a checkpoint-based 1,000-step eight-B200 comparison of
  `main` against FA4 `seqused+triton`. The optimized path reduced median step
  time by 16.75% and mean step time by 18.89%, while aligned mean loss and
  accuracy showed no adverse trajectory. Documented exact row-cursor resume,
  benchmark artifacts, memory use, and an excluded vLLM-contaminated launch.

## 2026-08-28

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
  usable, and the full rebuild/audit campaign was launched.
* **Nemotron SWE structural repair**: Replaced the duplicated/contextless
  inherited windowing design with complete Gemma-native next-action examples
  and one explicitly selected assistant target per row. Preserved matched
  shell/editor call-result cycles, removed obsolete `think` actions, normalized
  `finish` as text, and separated agentless file-location supervision from
  interactive tool use. Corrected an over-broad phase-heading cleanup before
  tokenization, added exhaustive validation and a deterministic 1,000-row
  behavior-stratified E4B audit, and wired the repaired prefix into DFM10 while
  disabling the superseded prefix.

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

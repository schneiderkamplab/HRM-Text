# Operational Knowledge and Plans

## Operations

* [Current State](current-state.md) - Local repository state, active operations, and verified commands.
* [Open Issues](open-issues.md) - Known blockers, risks, and future improvements.

## Data Policies and Pipeline

* [Data Mix Policy](data-mix-policy.md) - Dataset inclusion, licensing, provenance, and privacy policy.
* [Source Filtering](source-filtering.md) - Filtering rules applied before conversion and tokenization.
* [DFM9 Copyright and EU TDM Review](dfm9-copyright-tdm-review.md) - Token-reconciled source-level rights classification and Article 3/4 conditions.
* [DFM9 Article 3 Boundary Accounting](dfm9-article3-boundary-accounting.md) - Narrow component estimate, provenance-split triage, and no-override counterfactual.
* [DFM9 Memorisation Source-Text Plan](dfm9-memorisation-source-text-plan.md) - Deduplicated original-source cohorts grouped by legal basis for extraction testing.
* [DFM9 Source-Rights LaTeX Appendix](dfm9-source-rights-latex-appendix.md) - Deterministic linked appendix tables generated from the copyright register and provenance DAG.
* [Apertus Copyright Boundary Decomposition](apertus-copyright-boundary-decomposition.md) - Component and row-group findings for SmolTalk, OpenHermes, MoT, LongAlign, and EuroBlocks.
* [Download, Convert, Tokenize, Sample](download-convert-tokenize.md) - Data-pipeline runbook.

## Dataset and Training Plans

* [DFM6 Plan](dfm6-plan.md) - DFM6 data, training, and evaluation decisions.
* [DFM7 Plan](dfm7-plan.md) - DFM7 data, training, and evaluation decisions.
* [DFM8 Plan](dfm8-plan.md) - DFM8 dataset, synthesis, post-training, and execution plan.
* [DFM9 Plan](dfm9-plan.md) - DFM9 factual-knowledge, code, and instruction expansion.
* [DFM9 Plan Concepts](dfm9-plan/) - Focused DFM9 measurements, implementation records, and continuation operations.
* [DFM10 Plan](dfm10-plan.md) - DFM9 plus train-only Andersen and Alexandra Institute additions.
* [DFM11 Plan](dfm11-plan.md) - Deferred task-aware quality repairs from the frozen DFM10 residual audit.
* [DFM10 Publication and Sampling State](dfm10-publication-state.md) - Final 72-package Hub inventory, sampled corpus, and transfer state.
* [DFM10 XL Epoch-9 Continuation](dfm10-xl-epoch9-continuation.md) - Exact DFM9 endpoint resume into DFM10 and 50K evaluation campaign.
* [DFM10 Medical Data Plan](dfm10-medical-data-plan.md) - License-gated Danish and English medical training and evaluation candidates.
* [DFM10 Persona and Domsdatabasen Chats](dfm10-persona-doms-chats.md) - Audited Danish multi-turn generation runbook.
* [Long-Context Dataset Inventory](long-context-dataset-inventory.md) - Training candidates, project-derived sources, and evaluation-only corpora for 8K, 16K, and 32K stages.
* [DFM10 OpenStax Grounded SFT](dfm10-openstax-sft.md) - Audited derivative SFT from immutable historical CC BY artifacts and its DFM10 production gate.
* [DFM10 Open Grounded Chats](dfm10-open-grounded-chats.md) - Danish Wikipedia and OpenStax multi-turn grounded-chat production with assistant-turn size gates.
* [Open Book Corpus Candidates](open-book-corpus-candidates.md) - Ranked open-book sources, existing overlap, and provenance-preserving admission gates.
* [Danish Corpus Expansion Candidates](danish-corpus-expansion-candidates.md) - Andersen/DSL candidates, the current DynaWord delta, and a license-first Tidsskrift.dk expansion design.
* [Danish Research Data Landscape](danish-research-data-landscape.md) - Ranked NLP, linguistics, historical-text, archive, and digital-humanities sources with overlap and rights gates.
* [DFM10 Production Replacement Inventory](dfm10-repaired-datasets.md) - Exact original and repaired row/token totals for all disabled inherited sources.
* [DFM10 Source Quality Audit](dfm10-source-quality-audit.md) - Deterministic E4B inspection of every inherited and new DFM10 source.
* [DFM10 Residual Quality-Audit Queue](dfm10-residual-quality-audit-queue.md) - Ordered post-reconciliation audits over active tokenized and pending package representations.
* [DFM10 Final Source Reconciliation](dfm10-final-source-reconciliation.md) - Explicit Repair/Filter decisions and production sampling gates.
* [DFM10 Danish Hub Gap Integration](dfm10-danish-hf-gap-integration-plan.md) - Concrete duplicate cleanup and admission plan for newly identified alignment, preference, persona, and legal sources.
* [DFM10 Hugging Face Export Staging](dfm10-hf-export-staging.md) - Upload-ready local packages, inherited Hub availability, and redistribution boundaries.
* [Mimir v1 Evaluation Gap Analysis](mimir-v1-evaluation-gap-analysis.md) - Subject-level and cross-suite gaps in the DFM8 XL 1,650,000-step checkpoint, with targeted data-generation priorities.
* [Mimir Benchmark Data Priorities](mimir-benchmark-data-priorities.md) - Marginal curation and generation priorities for standard reasoning, commonsense, reading-comprehension, and instruction-following benchmarks after the expanded Mimir integration.
* [Mimir Benchmark Campaign Runbook](mimir-benchmark-campaign-runbook.md) - Reproducible request preparation, deterministic verification, shared GPU queue, and recovery procedure for the IFEval, BoolQ, DROP, and event/coreference campaigns.
* [DFM10 Danish University Portals Repair](dfm10-danish-university-portals-repair.md) - Full-corpus structural filtering and E4B audit of the Danish university-portals source.
* [DFM10 DynaWord Instruction Repair](dfm10-dynaword-instruct-repair.md) - Full-row audit and prompt-only repair of four Danish DynaWord instruction sources.
* [DFM10 Danish Corpus Expansion](dfm10-danish-corpus-expansion.md) - License-gated Tidsskrift harvesting, DynaWord transformation candidates, and DSL lexical SFT.
* [DFM10 OPUS DA-EN Quality Repair](dfm10-opus-da-en-repair.md) - Scalable language, direction, and bitext-alignment filtering for permissive OPUS pairs.
* [DFM10 DOLCI Tool Use Repair](dfm10-dolci-tool-use-repair.md) - Native Gemma call/result reconstruction and validation for DOLCI tool trajectories.
* [DFM10 GovReport Repair](dfm10-govreport-repair.md) - Complete-report 4K summarization conversion and grounding audit.
* [DFM10 WikiCatSum Repair](dfm10-wiki-cat-sum-repair.md) - Evidence-selected WikiCatSum rebuilding and row-level grounding filtering.
* [DFM10 NordjyllandNews Repair](dfm10-nordjylland-news-repair.md) - Headline-aware conversion and full-corpus grounding filter.
* [DFM10 DST Table Prompts Repair](dfm10-dst-table-prompts-repair.md) - Exact table extraction, target cleanup, and exhaustive grounding filter.
* [DFM10 Danmarks Statistik BT Repair](dfm10-danmarks-statistik-repair.md) - Answer-matched prompt regeneration and strict full-corpus coherence filtering.
* [Original L Reproduction](original-l-reproduction.md) - Sapient original-mix L reproduction runbook.

## Model and Runtime

* [Model Architecture](model-architecture.md) - HRM/CRM variants, checkpoint formats, serving, and resume behavior.
* [FlashAttention on B200](flashattention-b200.md) - NVIDIA B200 attention and CUDA integration reference.
* [CUDA 13.2 FA4/Triton Recovery](hrm-cu132-fa4-triton-recovery.md) - Reproducible evaluation-runtime recovery after CUDA/compiler loss.

## Detailed Collections

* [Current-State Records](current-state/) - Individually retrievable operational records.
* [Data-Mix Policy Records](data-mix-policy/) - Individual policy decisions and analyses.
* [DFM6 Plan Records](dfm6-plan/) - Focused DFM6 planning and execution concepts.
* [DFM7 Plan Records](dfm7-plan/) - Focused DFM7 planning and execution concepts.
* [DFM8 Plan Records](dfm8-plan/) - Focused DFM8 planning and execution concepts.
* [FlashAttention B200 Records](flashattention-b200/) - Focused platform and build findings.
* [Model-Architecture Records](model-architecture/) - Focused architecture and runtime concepts.
* [Original-L Reproduction Records](original-l-reproduction/) - Focused reproduction procedures and observations.

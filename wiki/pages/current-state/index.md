# Current State Concepts

* [DFM11 MixedLM experiments](2026-11-15-dfm11-mixedlm.md) - Fork-style target-only B/Transformer preparations, attention contract and verification.

* [DFM11 B/Transformer alternating training](2026-11-10-dfm11-architecture-comparison.md) - Full-backprop causal B, 150K disk stop, and alternating 50K eval intervals.

* [DFM8 XXL 200K Eval Recovery](2026-08-29-dfm8-xxl-200k-eval-recovery.md) - Verified 201K pause, 200K export/eval, worker-race fix, and training continuation.
* [Mimir HF Export Tokenizer Path](2026-08-29-mimir-hf-export-tokenizer-path.md) - Explicit tokenizer override for exports after the `/work/dfm` to `/work/mimir` migration.
* [DFM9 XXL-32 20K EuroEval](2026-08-26-dfm9-xxl32-20k-euroeval.md) - Completed and synced task metrics, failed VaLEU boundary, and early-checkpoint interpretation.
* [DFM8 XXL Step 150.7K Loss Excursion](2026-08-26-dfm8-xxl-loss-excursion.md) - Source attribution and interpretation of the isolated self-recovering training instability.
* [2026-08-26 Eval Monitor Live Progress Sources](2026-08-26-eval-monitor-inspect-progress.md) - Exact Inspect-journal progress for DFM tasks and native rolling ETAs for tqdm-based evaluators.
* [Mimir EU AI Act Documentation Gap](mimir-eu-ai-act-documentation-gap.md) - Provisional scope and Article 53 documentation gap assessment for the Mimir v1 research release.
* [2026-07-11 DFM8 Pre-Training Gate](2026-07-11-dfm8-pre-training-gate.md) - Part of Current State: 2026-07-11 DFM8 Pre-Training Gate.
* [2026-07-11 DFM8-XL W&B Preparation](2026-07-11-dfm8-xl-w-b-preparation.md) - Part of Current State: 2026-07-11 DFM8-XL W&B Preparation.
* [2026-06-18 Clean DFM5-L 650K/700K vLLM Eval Scheduler](2026-06-18-clean-dfm5-l-650k-700k-vllm-eval-scheduler.md) - Part of Current State: 2026-06-18 Clean DFM5-L 650K/700K vLLM Eval Scheduler.
* [2026-06-18 Batched vLLM IFEval Scheduler Path](2026-06-18-batched-vllm-ifeval-scheduler-path.md) - Part of Current State: 2026-06-18 Batched vLLM IFEval Scheduler Path.
* [2026-06-18 DFM5-L 650K vLLM Full Eval Launch](2026-06-18-dfm5-l-650k-vllm-full-eval-launch.md) - Part of Current State: 2026-06-18 DFM5-L 650K vLLM Full Eval Launch.
* [2026-06-16 Eval Scheduler EuroEval Monitor Progress Fix](2026-06-16-eval-scheduler-euroeval-monitor-progress-fix.md) - Part of Current State: 2026-06-16 Eval Scheduler EuroEval Monitor Progress Fix.
* [2026-06-16 DFM5 L 350K/400K Wait-Based Full Eval Scheduler](2026-06-16-dfm5-l-350k-400k-wait-based-full-eval-scheduler.md) - Part of Current State: 2026-06-16 DFM5 L 350K/400K Wait-Based Full Eval Scheduler.
* [2026-06-16 DFM5 L 300K Full Eval](2026-06-16-dfm5-l-300k-full-eval.md) - Part of Current State: 2026-06-16 DFM5 L 300K Full Eval.
* [2026-06-15 Original Sapient L Backfill Into DFM5](2026-06-15-original-sapient-l-backfill-into-dfm5.md) - Part of Current State: 2026-06-15 Original Sapient L Backfill Into DFM5.
* [2026-06-15 GSM8k Smoke Error Analysis](2026-06-15-gsm8k-smoke-error-analysis.md) - Part of Current State: 2026-06-15 GSM8k Smoke Error Analysis.
* [2026-06-15 DFM5 L 250K Full Eval](2026-06-15-dfm5-l-250k-full-eval.md) - Part of Current State: 2026-06-15 DFM5 L 250K Full Eval.
* [2026-06-14 DFM5 L 50K Full Eval](2026-06-14-dfm5-l-50k-full-eval.md) - Part of Current State: 2026-06-14 DFM5 L 50K Full Eval.
* [2026-06-12 HRM DFM Headline Workspace](2026-06-12-hrm-dfm-headline-workspace.md) - Part of Current State: 2026-06-12 HRM DFM Headline Workspace.
* [2026-06-12 Original Sapient L EuroEval](2026-06-12-original-sapient-l-euroeval.md) - Part of Current State: 2026-06-12 Original Sapient L EuroEval.
* [2026-06-14 EuroEval Scheduling Fix](2026-06-14-euroeval-scheduling-fix.md) - Part of Current State: 2026-06-14 EuroEval Scheduling Fix.
* [2026-06-12 DFM4 XL-DDP Corrected W&B History](2026-06-12-dfm4-xl-ddp-corrected-w-b-history.md) - Part of Current State: 2026-06-12 DFM4 XL-DDP Corrected W&B History.
* [2026-06-10 DFM4 XL-DDP Step 700K EMA Lite Eval Grooming](2026-06-10-dfm4-xl-ddp-step-700k-ema-lite-eval-grooming.md) - Part of Current State: 2026-06-10 DFM4 XL-DDP Step 700K EMA Lite Eval Grooming.
* [2026-06-08 DFM4 XL-DDP BoolQ/PIQA EMA Gap](2026-06-08-dfm4-xl-ddp-boolq-piqa-ema-gap.md) - Part of Current State: 2026-06-08 DFM4 XL-DDP BoolQ/PIQA EMA Gap.
* [2026-06-08 DFM4 XL-DDP Full Eval W&B Prefixes](2026-06-08-dfm4-xl-ddp-full-eval-w-b-prefixes.md) - Part of Current State: 2026-06-08 DFM4 XL-DDP Full Eval W&B Prefixes.
* [2026-06-09 Posttrain Generated Dataset Size](2026-06-09-posttrain-generated-dataset-size.md) - Part of Current State: 2026-06-09 Posttrain Generated Dataset Size.
* [2026-06-08 Ephemeral Training Checkpoints](2026-06-08-ephemeral-training-checkpoints.md) - Part of Current State: 2026-06-08 Ephemeral Training Checkpoints.
* [2026-06-08 DFM4 XL-DDP Step 650K Lite Eval Launch](2026-06-08-dfm4-xl-ddp-step-650k-lite-eval-launch.md) - Part of Current State: 2026-06-08 DFM4 XL-DDP Step 650K Lite Eval Launch.
* [2026-06-08 DFM4 XL-DDP Lite Eval Step 600K Talemaader Rerun](2026-06-08-dfm4-xl-ddp-lite-eval-step-600k-talemaader-rerun.md) - Part of Current State: 2026-06-08 DFM4 XL-DDP Lite Eval Step 600K Talemaader Rerun.
* [2026-06-04 Post-Training Transformation Refine Dataset](2026-06-04-post-training-transformation-refine-dataset.md) - Part of Current State: 2026-06-04 Post-Training Transformation Refine Dataset.
* [2026-06-04 DFM4 XL-DDP Step 250K Lite Eval](2026-06-04-dfm4-xl-ddp-step-250k-lite-eval.md) - Part of Current State: 2026-06-04 DFM4 XL-DDP Step 250K Lite Eval.
* [2026-06-06 DFM4 XL-DDP Step 400K No-EMA Lite Eval](2026-06-06-dfm4-xl-ddp-step-400k-no-ema-lite-eval.md) - Part of Current State: 2026-06-06 DFM4 XL-DDP Step 400K No-EMA Lite Eval.
* [2026-06-06 DFM4 XL-DDP Step 450K No-EMA Lite Eval](2026-06-06-dfm4-xl-ddp-step-450k-no-ema-lite-eval.md) - Part of Current State: 2026-06-06 DFM4 XL-DDP Step 450K No-EMA Lite Eval.
* [2026-06-04 DFM4 XL-DDP Step 300K No-EMA Lite Eval](2026-06-04-dfm4-xl-ddp-step-300k-no-ema-lite-eval.md) - Part of Current State: 2026-06-04 DFM4 XL-DDP Step 300K No-EMA Lite Eval.
* [2026-06-04 DFM4 XL-DDP Step 200K Diagnostics](2026-06-04-dfm4-xl-ddp-step-200k-diagnostics.md) - Part of Current State: 2026-06-04 DFM4 XL-DDP Step 200K Diagnostics.
* [Environment](environment.md) - Part of Current State: Environment.
* [Dependency State](dependency-state.md) - Part of Current State: Dependency State.
* [Code Adaptation State](code-adaptation-state.md) - Part of Current State: Code Adaptation State.
* [Data State](data-state.md) - Part of Current State: Data State.
* [Active Work](active-work.md) - Part of Current State: Active Work.
* [Filesystem / Scratch State](filesystem-scratch-state.md) - Part of Current State: Filesystem / Scratch State.
* [Possible `data_io` Relocation](possible-dataio-relocation.md) - Part of Current State: Possible `data_io` Relocation.
* [`dfm-evals` Location](dfm-evals-location.md) - Part of Current State: `dfm-evals` Location.
* [Mixed Corpus Next Commands](mixed-corpus-next-commands.md) - Part of Current State: Mixed Corpus Next Commands.
* [DFM Mix Sampling](dfm-mix-sampling.md) - Part of Current State: DFM Mix Sampling.
* [DFM L Training](dfm-l-training.md) - Part of Current State: DFM L Training.
* [DFM L CP1 Evaluation Queue](dfm-l-cp1-evaluation-queue.md) - Part of Current State: DFM L CP1 Evaluation Queue.
* [DFM L CP2 Evaluation Queue](dfm-l-cp2-evaluation-queue.md) - Part of Current State: DFM L CP2 Evaluation Queue.
* [DFM L CP2 and Follow-On Records](dfm-l-cp2-evaluation-queue/) - Chronological evaluation and training records recovered from the aggregate queue entry.
* [2026-06-06 Posttrain Synthetic Audit Plan](2026-06-06-posttrain-synthetic-audit-plan.md) - Part of Current State: 2026-06-06 Posttrain Synthetic Audit Plan.
* [2026-06-10 Expert Dataset Export Package](2026-06-10-expert-dataset-export-package.md) - Part of Current State: 2026-06-10 Expert Dataset Export Package.
* [2026-06-10 Reordering Expert Audit Plan](2026-06-10-reordering-expert-audit-plan.md) - Part of Current State: 2026-06-10 Reordering Expert Audit Plan.
* [2026-06-11 DBC Author/Article Audit Plan](2026-06-11-dbc-author-article-audit-plan.md) - Part of Current State: 2026-06-11 DBC Author/Article Audit Plan.
* [2026-06-11 Export Dataset Audit/Recreation Setup](2026-06-11-export-dataset-audit-recreation-setup.md) - Part of Current State: 2026-06-11 Export Dataset Audit/Recreation Setup.
* [2026-06-11 Transformation Export Self-Contained Assessment](2026-06-11-transformation-export-self-contained-assessment.md) - Part of Current State: 2026-06-11 Transformation Export Self-Contained Assessment.
* [2026-06-11 Transformation Export Reproducibility Update](2026-06-11-transformation-export-reproducibility-update.md) - Part of Current State: 2026-06-11 Transformation Export Reproducibility Update.
* [2026-06-11 Export Audit Rebalance Plan](2026-06-11-export-audit-rebalance-plan.md) - Part of Current State: 2026-06-11 Export Audit Rebalance Plan.
* [2026-06-12 Exact Epoch Checkpoint Steps For Relogging](2026-06-12-exact-epoch-checkpoint-steps-for-relogging.md) - Part of Current State: 2026-06-12 Exact Epoch Checkpoint Steps For Relogging.
* [2026-06-12 HRM DFM Clean W&B Relog Project](2026-06-12-hrm-dfm-clean-w-b-relog-project.md) - Part of Current State: 2026-06-12 HRM DFM Clean W&B Relog Project.
* [2026-06-12 Export Audit Generation Status](2026-06-12-export-audit-generation-status.md) - Part of Current State: 2026-06-12 Export Audit Generation Status.
* [DFM5 XXS Runtime Observation](dfm5-xxs-runtime-observation.md) - Part of Current State: DFM5 XXS Runtime Observation.
* [DFM5 XXS Step-50K Full Eval](dfm5-xxs-step-50k-full-eval.md) - Part of Current State: DFM5 XXS Step-50K Full Eval.
* [DFM5 XXS and Later Evaluation Records](dfm5-xxs-step-50k-full-eval/) - Recovered focused records from the historical aggregate section.
* [DFM9 8K Resume From Step 2137000](2026-08-25-dfm9-8k-resume.md) - Verified scheduler resume and separate Rich monitor.
* [vLLM FlashInfer Version Mismatch](2026-08-25-vllm-flashinfer-mismatch.md) - Root cause of persistent vLLM startup status 71.

* [B DFM15 second-epoch schedule and assessment](2026-11-04-epoch2-wsd-extension-b-dfm15-gemma4.md) - Staged delayed cooldown and progress evidence through 400K.

* [Transformer48 DFM11 causal baseline](2026-11-09-transformer48-dfm11-causal.md) - Prepared baseline, smoke status, and B final publication repair.

* [DFM11 attention and loss ablations](2026-11-14-dfm11-objective-ablation.md) — three-run rotation followed by Transformer causal/target-only.

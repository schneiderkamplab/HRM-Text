# Model Architecture Concepts

* [Engram preparation](engram-preparation-20261020.md) - Contextual n-gram export/serving, CPU state/parity tests, actual-token collisions and pending GPU qualification.
* [Biased expert pilots](biased-expert-pilots-20261020.md) - Source-biased dense 2/2 MoE and MoS continuations, unchanged data order and memory qualification.

* [HRM v2 Implementation](hrm-text-v2-implementation.md) - Opt-in sparse experts, optimizer/EMA-preserving upcycling, metadata routing, recurrent memory, n-grams and Muon.

* [HRM-Text-v2 Architecture Candidates](hrm-text-v2-plan.md) - Gated H/L communication, branched recurrent states, DeltaNet hybrids and controlled architecture experiments.
* [HRM-Text-v2 Gated XL Pilot](hrm-text-v2-gated-pilot.md) - Independent invocation gates, low-BP update sharing, migration and the prepared 3.8M XL experiment.
* [HRM-Text-v2 Expert Mixtures](hrm-text-v2-experts.md) - Reference k-of-n MLP/L-stack routing, shared or separate states, frozen references and qualification limits.
* [HRM-Text-v2 Residual Branches](hrm-text-v2-residual-branches.md) - Optional m-stream residuals inside stacks and exact v1-equivalent defaults.

* [Portable App Packaging History](mimir-app-packaging-history.md) - Platform integration, feedback and compaction history.
* [App Model Catalog and Release History](mimir-app-model-catalog-history.md) - Model discovery, tokenizer fixes and releases.
* [App UI and Generation Defaults](mimir-app-ui-defaults.md) - Sampling, branding and presentation defaults.
* [Native CLI Distribution](mimir-native-cli-distribution.md) - Native and llama.cpp packaging and qualification.

* [SQLite and Request-Shared Evaluation Scheduler](request-shared-eval-scheduler.md) - Opt-in durable job storage, CPU-limited clients, async inference sharing, and migration safety.
* [B DFM15 Gemma-4 Epoch-1 Launch](b-dfm15-gemma4-epoch1-launch.md) - Managed B-size Gemma-4 training plan: step-count derivation under GAS, fresh-start cooperative rows, reset/import cycle.
* [Eval-Block Dependency Structure](eval-block-dependency-structure.md) - One-training/many-suspensions model, the eval-block dependency shape between suspensions, and the pre-launch row audit.
* [Local XXL-wide Scheduler Handoffs](xxl-wide-scheduler-handoffs.md) - Local migration, evaluation repairs, verified suspension and restore history.

* [Mimir Apple OS-only TLS packaging](mimir-apple-os-tls-packaging.md) - Custom engine integration, headless-runtime packaging, audits and qualification evidence.

* [Wide Model Size Presets](wide-model-size-presets.md) - XXXL-wide and XXXXL-wide presets and parameter comparison of all sizes.
* [Vocabulary Pruning for English, Danish and Chinese](vocab-pruning-en-da-zh.md) - Measured 262k-to-65k pruning frontier, compression costs and per-size parameter impact.

* [HF Export and Eval Loader Compatibility](hf-export-and-eval-loader-compatibility.md) - Part of Model Architecture: HF Export and Eval Loader Compatibility.
* [Current Two-Level Relation](current-two-level-relation.md) - Part of Model Architecture: Current Two-Level Relation.
* [vLLM DFM Judge-Backed Eval Memory](vllm-dfm-judge-backed-eval-memory.md) - Part of Model Architecture: vLLM DFM Judge-Backed Eval Memory.
* [Schedule](schedule.md) - Part of Model Architecture: Schedule.
* [Compression](compression.md) - Part of Model Architecture: Compression.
* [One-Level Recurrent Baseline](one-level-recurrent-baseline.md) - Part of Model Architecture: One-Level Recurrent Baseline.
* [Three-Level No-Compression Experimental Path](three-level-no-compression-experimental-path.md) - Part of Model Architecture: Three-Level No-Compression Experimental Path.
* [CRM2 Latent-Compressed Experimental Path](crm2-latent-compressed-experimental-path.md) - Part of Model Architecture: CRM2 Latent-Compressed Experimental Path.
* [CRM3 Latent-Compressed Experimental Path](crm3-latent-compressed-experimental-path.md) - Part of Model Architecture: CRM3 Latent-Compressed Experimental Path.
* [vLLM HRM-Text Serving Status](vllm-hrm-text-serving-status.md) - Part of Model Architecture: vLLM HRM-Text Serving Status.
* [In-Epoch Resume Cursors](in-epoch-resume-cursors.md) - Part of Model Architecture: In-Epoch Resume Cursors.
* [Local-Global Attention Path](local-global-attention-path.md) - Part of Model Architecture: Local-Global Attention Path.
* [Sparse Attention Path](sparse-attention-path.md) - Part of Model Architecture: Sparse Attention Path.
* [HRM-Text XL Training FLOPs](hrm-xl-training-flops.md) - Recurrence-aware upper-bound calculation for XL training compute.
* [DFM8 XXL MFU Baseline](dfm8-xxl-mfu-baseline.md) - Recurrence-aware single-node B200 utilization estimate and realistic throughput target.
* [XL Parameter and Export Size](xl-parameter-and-export-size.md) - Parameter-count and export-size reference for the XL model.
* [Mimir Apple Chat Feasibility](mimir-apple-chat-feasibility.md) - Native runtime options, PrefixLM correctness, recurrent cache memory, and device validation gates.
* [Safe PrefixLM Support in llama.cpp](llama-cpp-prefixlm-plan.md) - Pinned source audit, phase-aware prefill/decode design, cache and batching safeguards, and parity gates.
* [PrefixLM Patch Revision Proposal](llama-cpp-prefixlm-patch-proposal.md) - Hunk-by-hunk reuse of the existing proposal, minimal replacement design, server invariants, and regression cases.
* [PrefixLM Comparative Correctness Results](llama-cpp-prefixlm-comparison.md) - Reproducible CPU/Metal comparisons of the baseline, historical proposal, and phase-aware prototype with real Mimir smoke tests.
* [Minimal Mimir Native Session Runtime](mimir-native-session.md) - Owned context lifecycle, full-turn prefill, cancellation/failure recovery, and CPU/Metal integration tests.
* [Native Mimir Text Chat](mimir-native-text-chat.md) - GGUF tokenizer/template parity, native streaming chat, cancellation, and CPU/Metal end-to-end validation.
* [Engine-Level PrefixLM in llama.cpp](llama-cpp-prefixlm-engine.md) - Native attention/API semantics, shared CLI/server scheduling, cache safety and engine regression tests.
* [DFM Mimir Hugging Face Space Demo](dfm-mimir-space-demo.md) - ZeroGPU deployment, gated-model OAuth, and inference contract for the public Mimir demo.
* [Distributed Long-Context Implementation Options](distributed-long-context-options.md) - Main-branch difficulty, risks, and recommended ordering for activation and model-parallel approaches.
* [Multi-Node and 32K Training Plan](multinode-32k-training-plan.md) - Direct-SSH TorchRun, run-aware checkpoints, efficient GAS, HSDP, world-size resume, and staged B200 context extension.
* [Fixed-Membership SSH TorchRun Launcher](multinode-ssh-launcher.md) - Host contract, preflight, NCCL smoke, launch, logging, and coordinated failure handling without Slurm.
* [Multi-Node Evaluation Scheduler Plan](multinode-eval-scheduler-plan.md) - Coordinator-worker resource leasing, distributed eval execution, persistent vLLM reuse, cluster training handoff, and aggregate monitoring.
* [DFM8 XXL to DFM10 Multi-Node Transition](dfm8-xxl-to-dfm10-multinode-transition.md) - Epoch-boundary data/topology change, batch geometry, readiness gates, and checkpoint cadence.
* [Optional Global Gradient Clipping](gradient-clipping.md) - Null-by-default clipping, verified FSDP2/DTensor semantics, and AdamATan2-native stability options.
* [Training Stability, Jacobian Growth, and Residual Scaling](training-stability-jacobian-and-residual-scaling.md) - Recurrent-depth diagnosis, mitigation options, and opt-in per-cycle/per-layer instrumentation.
* [XL BP-Depth Memory Benchmark](xl-bp-depth-memory-benchmark.md) - Matched BP 6-8 memory and throughput measurements for the DFM10 XL geometry.
* [MLP Energy Replay Layer Diagnostics](mlp-energy-replay-layer-review.md) - Remaining amplification, downstream changes, and measurement limits in the completed matched replay.
* [Regularization Alternatives from 453K](mlp-energy-regularization-experiments.md) - Candidate penalties, tail-focused aggregation, and matched replay controls.
* [Actual AdamATan2 Update Calibration](parameter-update-calibration.md) - Default-off update measurements and isolated 10-step comparisons before nested RMS.
* [H and L Learning Rates](module-learning-rates.md) - Optional scheduled module rates with unchanged optimizer checkpoint groups.
* [XXL Restart from 520K](xxl-520k-restart.md) - Isolated half-rate continuation with a cutoff history clone and preserved original trajectory.
* [Mimir Apple Chat MVP](mimir-apple-mvp.md) - Shared SwiftUI app, Metal bridge, local conversations and device validation gaps.

* [DFM Mimir App and Portable Backends](mimir-app.md) - Shared C ABI, Apple-first Flutter client and backend qualification matrix.

* [DFM Mimir Optional Chat Feedback](mimir-feedback.md) - Opt-in feedback, private EU D1 intake, authenticated review and test evidence.

* [Optional Mimir web search](mimir-search.md) - Search consent, private key mapping, app focus and stock-prompt updates for unreleased 0.1.4.

* [DFM Mimir v1.5 GGUFs](mimir-v1.5-ggufs.md) - Conversion, tokenizer/template checks and official GGUF publication.

* [PrefixLM and MixedLM upstream integration](prefixlm-upstream-integration.md) - Scoped upstream port, extended batch API, regression evidence and release gates.

* [Mimir native binary distribution](mimir-native-binaries.md) - Packaging matrix and native wrapper/llama.cpp release history.
* [Mimir2 Transformers implementation](mimir2-transformers.md) - Full upstream clone, modular v2 architecture/configuration, strict conversion and CPU parity qualification.
* [Mimir2 vLLM integration](mimir2-vllm.md) - Fresh mimir2 conda environment, recurrent-cache serving, loading contracts and qualification limits.
* [Full XL control serving parity](mimir2-control-serving-parity.md) - Independent 3.82M exports, tokenizer corrections and full-weight compiled vLLM comparison.

* [Mimir app appearance and settings](mimir-app-appearance.md) - Text scaling and settings organization.

* [Budget-bounded mixed recurrence](cycle-variant-recursion.md) - Default-off per-microbatch H/L sampling, LR accounting, resume contracts and memory qualification.

- [Single-state sandwich recurrent architecture](sandwich-looped-model.md) — paper-derived alternative, validation and DFM11 queue.

- [Fixed-loop Ouro-style Transformer](ouro-fixed-loop.md) — four-loop matched-objective DFM11 experiment after Sandwich B.

* [Embla experiments](embla-experiments.md) — Agreed variants and implementation status.
* [Supervised-position output heads](supervised-output-head.md) — Avoid ignored vocabulary projections; Transformer/B and Embla benchmarks.
* [Embla optimized kernels](embla-optimized-kernels.md) — FA4, fused ReLU²/sparse attention and qualification evidence.

* [Embla mechanisms for HRM](embla-hrm-efficiency.md) — Cache accounting and architecture tradeoffs.

- [Dedicated232K validation](validation-232k-20261116.md) — full-size capacity checks, sampled BP16 selection, Embla repairs and restoration status.

- [Additional B200 node deployment](node2-deployment.md) — source review, transfers and experiment ownership.

# Model Architecture Concepts

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

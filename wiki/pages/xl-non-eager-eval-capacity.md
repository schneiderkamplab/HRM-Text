---
type: Runbook
title: XL Non-Eager Evaluation Capacity
description: Bounded real-prompt throughput and KV calibration on the original XL3100K export, isolated from evaluation scoring and W&B.
status: draft
confidence: high
last_updated: 2026-10-05
tags: [evaluation, xl, vllm, calibration]
---
# XL Non-Eager Evaluation Capacity

The user authorized a bounded eight-GPU calibration after the parent stopped XL
at3142000 and released all compute processes. This is independent of the
[DFM13 handoff](dfm13-xl-3150k-handoff.md); it does not edit the scheduler plan,
write W&B metrics, score model quality, or resume training.

## Preparation and Launch

`scripts/calibrate_xl_eval_capacity.py` reads real completed3100K evaluation
logs. Each of standard, short DFM, summaries and IFEval has128 prompts. Standard
tasks are round-robin GSM8k/ARC/MATH/HellaSwag/DROP with production configured
output allowances; DFM families retain the original first model-call messages
and output limits. Source files, inputs, tokenizer/template and implementation
are pinned. No source text is truncated, padded or replaced; EOS is respected.
Repeated prompts are replayed at increasing concurrency. The launch defaults
request prefix caching/chunked prefill, but vLLM explicitly disables both for
this HRM export's non-causal attention layers, as recorded in server logs.
This is a finite replay workload, not a fresh quality
evaluation or proof that every evaluation task has identical capacity.

The initial CPU-only v1 packet had a tokenizer-return-type counting bug and
was never launched. Superseding v2 explicitly encodes the rendered prompt:
512 prompts,18--2384 input tokens, with prompt plus output allowance within4096.
The export explicitly has `fix_mistral_regex=false`. CUDA uses the verified
`/home/ucloud/miniforge3/envs/hrm-cu132` compiler with the `hrm` Python runtime.

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m scripts.calibrate_xl_eval_capacity prepare \
  --root data/dfm13/xl3100-eval-capacity-20261005-v2
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m scripts.calibrate_xl_eval_capacity run \
  --root data/dfm13/xl3100-eval-capacity-20261005-v2 --execute
```

Only after explicit go and free-GPU checks, detached PID842368 started eight
owned servers on59100--59107. Log: `logs/xl3100-eval-capacity-20261005-v2.log`.
The source export is `exports/dfm12_XL_epoch11_step_3100000_ema_hf`.
Server logs confirm non-eager execution and FlashAttention4. Eight focused
tests passed. Preparation/launch receipts and raw per-stage outputs live in
the root above; old artifacts remain intact.

## Measurement Contract

GPUs0--3 test the four families at memory utilization.95; GPUs4--7 repeat them
at.85. **The.85 arm reserves judge capacity but does not launch a judge. Keep
judged concurrency16 unchanged unless separately tested.** The sweep uses
32/64/128/256/512 concurrent requests, maximum512 server sequences and16384
batched tokens. Each measured submission window lasts30 seconds; real request
latency may extend it, subject to a20-minute overall deadline. A short warmup
is recorded separately. Pressure at90% KV, any preemption or request error stops
further escalation on that endpoint.

Metrics include peak and median KV occupancy, steady-window median and fraction
of samples above50%, running/waiting requests, preemptions, wall-clock and steady
output throughput, latency percentiles and finish reasons. A50% spike alone is
not reported as steady target attainment. Lower occupancy is a result, not a
reason to pad prompts or ignore EOS. Recommendations remain suggestions for the
parent to inspect and apply, never automatic plan changes.

SIGTERM, deadline and exceptions clean up only process groups created by this
script; `cleanup.json` records exit codes. Startup/runtime failure is recorded
in `failure.json`; completed endpoint results survive a partial overall run.

## Measured Result (2026-10-05)

The first campaign completed78,476 measured requests and5,891,750 generated
tokens, with zero HTTP errors and zero preemptions. All eight owned API servers
exited0; `cleanup.json` binds their PIDs. Results are in `report.json` and
`reviewed-recommendations.json` under the v2 root above. The latter uses steady
throughput/latency and pressure margin, rather than the automatic wall-clock
ranking, which is sensitive to long math-response draining tails.

| Student prompt family | Suggested concurrency | Steady KV .95 / .85 | Steady output tokens/s .95 / .85 |
| --- | ---: | ---: | ---: |
| Short DFM | 256 | 14.4% / 16.1% | 6485 / 6492 |
| Summaries | 64 | 56.5% / 63.5% | 2298 / 2299 |
| Danish IFEval | 256 | 33.0% / 37.2% | 7835 / 7852 |
| Mixed standard replay | 256, provisional scope only | 27.3% / 30.0% | 5063 / 5065 |

Summary128 exceeded90% KV and stopped escalation; do not select it from its
higher throughput alone. IFEval512 was slower than256 and the.85 arm exceeded
90% KV. Standard512 had only35.1%/.95 and39.5%/.85 steady KV despite51.7%/57.0%
peaks, and its steady throughput fell to4186 tokens/s. It is not a universal
512 recommendation. No MMLU-specific or math-only concurrency bound was measured.

Source membership: short DFM43 DaLA,43 GEC-DaLA,42 generative idioms; summaries
64 NordjyllandNews and64 GovReport; IFEval4 samples from each of32 Danish shards;
standard26 GSM8k,26 ARC,26 MATH,25 HellaSwag,25 DROP. The idiom prompts measure
student generation only: actual judged concurrency16 remains unchanged.

User-authorized targeted follow-up uses
`scripts/calibrate_xl_eval_short_followup.py`, root
`data/dfm13/xl3100-eval-short1024-20261005-v1`, PID847927, GPUs1/5 only, after the
first cleanup. It reuses the compile caches, sets1024 sequences but caps CUDA
graph capture at512, and has a480-second deadline. It scans all3,880 recorded
short-task prompts: longest279 input tokens, no context exclusions. The extra
stress arm uses the32 longest recorded prompts, not padded4K synthetic inputs.
At1024, steady KV reached58.2%/.95 and65.3%/.85, but wall-clock output throughput
fell to5072/5124 tokens/s compared with approximately6380/6389 at256 in the first
campaign. Higher occupancy alone therefore does not justify a higher setting.
Nine focused harness tests passed; no calibration script edits the plan or W&B.
The follow-up subsequently completed and both owned servers exited0; no GPU
compute processes remained at verification. Its ordinary512/1024 sweeps had
zero errors/preemptions. The longest-recorded-prompt32 probe was **inconclusive**:
four immediate `ServerDisconnectedError` events stopped submission early
(three onGPU1, one onGPU5), with no preemptions. No semantic or capacity failure
is established by these transport errors, and no worst-case pass is claimed.
`final-recommendation.json` binds both reports and cleanup evidence. Standard768
was not run: standard steady throughput had already declined at512. The optional
probe is handed back to the parent; no further GPU work is queued here.

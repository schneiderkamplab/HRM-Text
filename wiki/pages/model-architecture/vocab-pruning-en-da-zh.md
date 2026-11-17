---
type: Technical Reference
title: Vocabulary Pruning Potential for English, Danish and Chinese
description: Measured pruning frontier for the 262,144-token Gemma vocabulary when only English, Danish and Chinese must be encoded well, with parameter-impact estimates per size preset.
tags: [tokenizer, vocabulary, architecture, multilingual, parameters]
status: stable
last_updated: 2026-11-02
confidence: high
---

# Vocabulary Pruning Potential for English, Danish and Chinese

Question: how much could the 262,144-token Gemma vocabulary shrink if only
English, Danish and Chinese had to be encoded well? Answer, from measurement:
**to about 65,536 pieces (a 4x reduction) with almost no compression loss in
any of the three languages**; the practical safe range is roughly 48k-96k,
while 32k already costs 22% English compression.

## Method

- Tokenizer: production Gemma-style BPE, 262,144 pieces, byte fallback enabled
  (`exports/dfm11_XXL_wide_step_450000_ema_hf/tokenizer.json`), 24 special
  tokens, byte tokens occupy IDs 238-493.
- Samples: English 5.74M chars (Common Pile wikimedia JSON), Danish 5.00M chars
  (Alexandra Nordjylland news parquet), Chinese 0.36M chars (zh.wikipedia
  plain extracts, 279k CJK chars, mixed simplified/traditional).
- Pruning: keep 24 specials + 256 byte tokens, then the smallest union of
  per-language token sets reaching a shared occurrence-coverage threshold;
  drop `<unused*>`. Merges are filtered so both parts and the result stay in
  the kept vocabulary; the filtered tokenizer is re-encoded on the same
  samples, so the reported compression numbers are real tokenizer behavior,
  not extrapolation.
- Scratch scripts: `.tmp_vocab_probe/analyze.py` and `.tmp_vocab_probe/prune.py`
  (untracked; regenerate samples if the directory is cleaned). Reference
  artifacts kept there: `pruned_66749_content_pieces.json` (99.9% union) and
  `pruned_total_65536.json` (exact 65,536-total target).

## Full-vocabulary baselines

| Sample | Tokens | tok/char | Distinct tokens | Byte-token share |
| --- | ---: | ---: | ---: | ---: |
| English | 1,387,085 | 0.242 | 51,588 | 0.02% |
| Danish | 1,482,303 | 0.296 | 16,453 | 0.57% |
| Chinese | 283,378 | 0.781 | 10,782 | 0.49% |

Occurrence-coverage needs under the full tokenizer: English 37,718 tokens for
99%, 50,201 for 99.9%; Danish 8,160 / 14,971; Chinese 8,127 / 10,499.

## Pruning frontier (measured by re-encoding)

| Per-language coverage | Pruned pieces (+24 specials) | English | Danish | Chinese |
| --- | ---: | ---: | ---: | ---: |
| 95% | 22,661 | x1.33, bytes 0.6% | x1.07 | x1.12, bytes 8.7% |
| 97% | 31,486 | x1.22, bytes 0.5% | x1.04 | x1.08, bytes 5.7% |
| 98% | 38,566 | x1.17, bytes 0.4% | x1.03 | x1.06, bytes 4.5% |
| 99% | 49,767 | x1.11, bytes 0.3% | x1.01 | x1.04, bytes 3.0% |
| 99.9% | 66,773 | x1.06, bytes 0.25% | x1.01 | x1.02, bytes 1.1% |
| 99.95% | 67,835 | x1.06 | x1.01 | x1.02 (no further gain) |

Ratios are tok/char relative to the full tokenizer on the same sample.

The coverage curve has a cliff between 99% and 99.9% for English (50.2k -> 66.8k
union) and beyond 99.9% nothing changes. Trimming the 66,773-piece union down
to exactly 65,536 total pieces (65,256 content pieces + 256 byte tokens +
24 specials) only removes the lowest-frequency remainder and reproduces the
66.8k profile.

## Exact 65,536-total measurement (2026-11-02 follow-up)

Building a tokenizer with exactly 65,536 total entries (24 specials + 256 byte
tokens + 65,256 learned pieces), selecting pieces by best per-language
frequency rank (a piece is claimed by whichever language ranks it highest),
gives:

| Language | tok/char (full -> pruned) | Piece-encoded | Byte fallback |
| --- | --- | ---: | ---: |
| English | 0.242 -> 0.258 (x1.07) | 99.69% | 0.31% |
| Danish | 0.296 -> 0.297 (x1.00) | 99.42% | 0.58% |
| Chinese | 0.781 -> 0.791 (x1.01) | 98.94% | 1.06% |

4,780 single-hanzi pieces survive; Chinese compression is within 1% of full.
The same min-rank selection at other totals: 49,152 -> EN x1.13 / DA x1.01 /
ZH x1.01 (4,742 hanzi); 32,768 -> EN x1.27 / DA x1.01 / ZH x1.01 (4,731
hanzi). Danish and Chinese are essentially insensitive from 65k down to 32k;
the entire cost curve is the English long tail.

The 24 special/template tokens (`<pad>`, `<eos>`, `<bos>`, `<unk>`, `<mask>`,
tool-call/think/turn channel wrappers, audio/image markers) and the 256 byte
tokens must be preserved in any pruning: they are added tokens referenced by
the chat template, export and GGUF validation paths, never learned, and byte
fallback is what keeps arbitrary text encodable.

## Mimir Mini tokenizer (built 2026-11-02)

The pruned 65,536-total tokenizer exists as **Mimir Mini** at
`data_io/trained_tokenizers/mimir_mini/` (`tokenizer.json` + `config.json`,
built by `.tmp_vocab_probe/build_mimir_mini.py`). Scheme:

- Kept set is the measured 65,536-total selection (min-rank over the EN/DA/ZH
  samples), all 24 special/template tokens and 256 byte tokens preserved,
  `<unused*>` dropped.
- Dense renumbering: `<pad>/<eos>/<bos>/<unk>/<mask>` stay 0-4, remaining
  specials 5-23 in original-id order, byte tokens 24-279, learned pieces
  280-65535 in original-id order. Gemma 4's real turn/channel tokens are
  `<|turn>`/`<turn|>` and `<|channel>`/`<channel|>`; the TemplateProcessing
  post-processor keeps working because `<bos>` retains ID 2.
- 120,342 merges survive; 4,780 single-hanzi pieces.
- Measured compression on the same samples: EN 0.258 tok/char (x1.07),
  DA 0.297 (x1.00), ZH 0.791 (x1.01); byte fallback 0.31%/0.58%/1.06% of
  occurrences. Sequence lengths are identical to the sparse-ID probe
  tokenizer, confirming renumbering changed no tokenization behavior.
- Validation receipts: exact round-trip decode of EN/DA/ZH plus non-kept
  scripts (Cyrillic, Arabic, emoji, runic) via byte fallback; special-token
  splitting; `data_io/tokenizer` release build consumed the directory with
  `--template-mode gemma4-chat` and produced `tokenizer_info.json` with
  `vocab_size: 65536`; the emitted `tokens.npy` decodes back to correct
  Danish/Chinese/English rows.
- Caveat: the Rust tool's default `hrm` template mode references Sapient-era
  tokens (`<|im_start|>` etc.) that Mimir Mini does not contain; use
  `--template-mode gemma4-chat`, or override `--boq/--eoq/--eoa` with tokens
  that exist in Mimir Mini.

## Training smoke: B + Mimir Mini (2026-11-02)

End-to-end training receipt at
`.tmp_vocab_probe/b_smoke_run_fsdp2.log` (W&B disabled, 20 optimizer steps,
GBS 16384 / GAS 4, single B200 co-resident with the GLM replicas):

- Dataset: 900 real EN/DA/ZH instruction-response rows (548k tokens) built
  from the same pruning samples via the Rust tokenizer in
  `gemma4-chat` mode, arranged as a V1 dataset at
  `.tmp_vocab_probe/b_smoke_mimir_mini_data/` (`metadata.json` with
  `vocab_size 65536`, `max_seq_len 4097`; rows ~700-1000 tokens).
- Recipe: FSDP, `fsdp_params_precision=fp32`, bf16 fwd/bwd, FA4 sm100,
  `reshard_after_forward=false`, compile off.
- Result: 20/20 steps, finite loss (11.58 -> 11.58 at warmup LR), no NaN.
  Per-step (4x4096-token microbatches): median 0.461 s, mean 0.469 s,
  ~35.5k tokens/s. Memory: torch peak allocated 15.77 GiB, reserved
  18.05 GiB, device delta ~22.6 GiB against the GLM replica baseline.
- Gotcha: `distributed_strategy=none` runs fully fp32 (no autocast is wired
  for it, pretrain.py:533-537) and FA4 asserts on fp32 inputs; single-GPU
  smoke runs should use `ddp` (autocast) or `fsdp` (mixed precision).

## Full-geometry 8-GPU smoke: B + Mimir Mini, BP 8 / GAS 1 / GBS 262144 (2026-11-02)

Same B + Mimir Mini setup at production batch geometry, all eight B200s free
(GLM replicas drained), FSDP fp32 params + bf16, `reshard_after_forward=false`,
4K context, compile off, W&B disabled, `max_steps=20`, `epochs=12` (the 548k-token
dataset re-iterates; dataset needs an `epoch_N` index dir per epoch). BP 8 via
`arch.bp_max_steps=8 arch.bp_warmup_ratio=0.0` (`bp_warmup_ratio=0` is safe in
current code: it selects `bp_max_steps` directly).

BP semantics (per the forward in `hrm_nocarry_bp_warmup.py`): one pass applies
8 stacks in order L0 L1 L2 H0 L3 L4 L5 H1 (H2xL3 = 2 + 2x3). BP steps
differentiate the last applications, H-prioritized: BP 8 differentiates all
eight; BP 5 differentiates 2 H + last 3 L, i.e. the differentiated chain is
[1st H -> 3x L -> 2nd H] and the leading L0-L2 are detached. BP 5 and BP 8 are
NOT memory-equivalent; BP 8 stores all eight applications' activations.

Results: 20/20 steps, finite loss 11.607 -> 11.493. Steady per-step time
median 0.345 s (min 0.343; max 2.02 s on epoch-boundary dataloader restarts,
which inflate the mean to 0.976 s) -> 262144/0.345 = ~759k tokens/s aggregate,
~94.9k tokens/s per GPU, consistent with the single-GPU smoke despite FSDP
communication. Memory per rank: torch peak allocated 104.6 GiB, max reserved
109.3 GiB; device-level peak 111.8-114.0 GiB per GPU (~64-67 GiB free) with no
activation checkpointing. By contrast XXL (3.98B) at the same geometry OOMs
uncheckpointed (176.2 GiB PyTorch-allocated at step 1 vs 178.4 GiB usable) and
needs `activation_checkpointing=l_only` per the XL BP-depth benchmark.

## Where the 262,144 pieces go

Unicode-category composition of the full vocabulary: ASCII 150,522; other
Latin 32,791; mixed ASCII/Latin 12,476; CJK 19,248 (+1,320 mixed CJK/kana);
Devanagari 13,684; Cyrillic 13,395; Arabic 8,250; Hangul 4,561; Kana 3,558;
Thai 2,177; other mixed/space ~100. About 46k pieces serve scripts outside
English/Danish/Chinese, and a further ~130k of ASCII/Latin pieces are merge
variants that a three-language frequency union does not need.

Chinese detail at the 99.9% union: 9,738 CJK pieces kept, of which 4,659 are
single-hanzi pieces covering 4,485 of the sample's 4,707 distinct CJK chars;
uncovered chars are 0.28% of CJK occurrences (rare names/classical chars) and
fall back to 3 bytes each. This matches standard Chinese coverage statistics
(~3,500 chars cover ~99.5% of running text).

## Parameter impact (untied embeddings + LM head, 2 x V x hidden)

| Preset (hidden) | Emb+head at 262,144 | Emb+head at 65,536 | Total saved | New total |
| --- | ---: | ---: | ---: | ---: |
| B (1024) | 536,870,912 | 134,217,728 | 402,653,184 | 300,941,312 |
| L (1280) | 671,088,640 | 167,772,160 | 503,316,480 | 694,681,600 |
| XL (1536) | 805,306,368 | 201,326,592 | 603,979,776 | 1,182,793,728 |
| XXL (1792) | 939,524,096 | 234,881,024 | 704,643,072 | 3,273,654,272 |
| XXL_wide (2560) | 1,342,177,280 | 335,544,320 | 1,006,632,960 | 3,082,813,440 |
| XXXL (2048) | 1,073,741,824 | 268,435,456 | 805,306,368 | 5,603,590,144 |
| XXXXL (2560) | 1,342,177,280 | 335,544,320 | 1,006,632,960 | 11,324,620,800 |
| XXXXL_wide (4096) | 2,147,483,648 | 536,870,912 | 1,610,612,736 | 11,056,185,344 |

Share of total removed is largest for small/medium models (L -42%, XL -34%)
and smallest for deep large models (XXXXL_wide -13%). The XXXL total at
65,536, `5,603,590,144`, matches the `5.604B` "physical params" figure in
[residual risk](/pages/flashattention-b200/residual-risk.md), which
implicitly used the original 65,536-token Sapient vocabulary.

Secondary operational benefit: full-vocabulary FP32 logits that peaked near
168 GiB on a B200 with 262,144 entries
([fineinstructions grounded chats](/pages/dfm11-fineinstructions-grounded-chats.md))
scale down to roughly 42 GiB at 65,536 entries.

## Interpretation and caveats

- **Recommendation**: 262,144 -> 65,536 keeps >=99.9% occurrence coverage in
  all three languages with x1.06 English, x1.02 Chinese and x1.01 Danish
  compression loss. If Classical/Traditional Chinese, heavy proper-name
  coverage or other scripts (Cyrillic/Arabic/Devanagari) matter, stay nearer
  96k; do not go below ~48k.
- **Pruned-Gemma vs retrained tokenizer**: the numbers above prune Gemma's
  merge tree in place (a zero-training upper bound on cleanliness). A BPE
  retrained from scratch on an EN+DA+ZH mix at 64k-96k would allocate budget
  more evenly and likely beat these ratios slightly; the pruned tokenizer is
  the safe instant path.
- **Byte fallback**: any input remains encodable; unsupported scripts degrade
  to ~3 tokens/char instead of failing.
- **Sample skew**: English is Wikipedia-derived (long typo/URL tail kept by
  occurrence coverage), Danish is news text, Chinese is Wikipedia. Web-scale
  English may push the 99% threshold somewhat higher.
- **From-scratch decision**: changing the vocabulary invalidates all existing
  checkpoints (embedding and LM head shapes); this is a new-pretraining
  choice, not an adaptation.

## Performance-optimized 200-step smoke (2026-11-02)

Same geometry (8 GPUs, FSDP fp32 params + bf16, GBS 262144 / GAS 1, BP 8,
4K ctx) with `compile_train_batch_mode=default` (inductor), light
instrumentation (`log_interval=5`, `memory_log_interval=20`), W&B disabled,
and a 7.38M-token dataset (12.5k rows) so all 200 steps run without
epoch-boundary dataloader restarts (8 epochs pre-permuted in
`.tmp_vocab_probe/b_opt_data/`).

Results: median 0.234 s/step (min 0.226) -> ~1.119M tokens/s aggregate
(~140k/GPU), 1.47x faster than the unoptimized 0.345 s baseline; torch peak
allocated 73.5 GiB, max reserved 76.0 GiB per rank. Loss 11.59 -> 7.67 over
200 steps (dataset cycled ~7x; benchmark only). One 7.45 s outlier from an
epoch-boundary restart; the mean (0.438 s) is inflated by those.

`reduce-overhead` was implemented (Literal + registry entry in pretrain.py)
and tested: cudagraph trees re-record nearly every step (~7 s/step) because
packed `cu_seqlens` lengths change between batches and CUDA graphs cannot
generalize shapes; repeats of seen shapes did not replay either (suspected
`dynamic=False` vs `mark_dynamic` conflict plus FSDP NCCL in the graph pool).
Abandoned for training; kept available for fixed-shape use cases.

### nsys steady-state attribution (2026-11-02)

Nsight Systems 2026.5.1 installed into the hrm env via pip wheel
(`nvidia_nsys_cli` from developer.download.nvidia.com; no apt package).
Gotchas: `nsys profile --delay/--duration` silently produces no report on the
real torchrun+compile run (works on tiny probes) — use full capture of a
short run instead; an env-gated torch.profiler hook added to pretrain.py
(`PROF_START_STEP`/`PROF_STOP_STEP`/`PROF_TRACE_DIR`) SIGABRTs under 8-rank
FSDP and is left disabled by default.

Full-capture profile of a 30-step B+Mimir run, steady window located by
ReduceScatter cadence (13 grad-bucket RS per step, ~0.234 s cadence), per
GPU per step (wall 243 ms): GEMM (nvjet) ~102 ms across ~580 launches
(avg 0.18 ms each), other kernels (FA4 attention + elementwise) ~68 ms,
inductor triton fused ops ~57 ms, NCCL ~43 ms spread unevenly across ranks
(33-53 ms) but ~89% overlapped with compute on rank 0 (exposed comm only
~5-15 ms), explicit gaps ~15 ms mostly in the eager optimizer/elementwise
region (largest 27 ms). Conclusion: the small-model regime is
compute-kernel-bound — hundreds of tiny GEMMs where B200 SMs sit far below
peak — NOT NVLink-bound; further per-step gains need kernel-count/fusion
reduction (fixed-shape collate + cudagraphs, larger effective tiles) rather
than communication tuning. The follow-up 200-step control with
`compile_train_batch_mode=max-autotune-no-cudagraphs` confirmed this:
median 0.2345 s/step (min 0.227, loss 7.665) — statistically identical to
the default-mode 0.234 s, after several minutes of one-time autotune search
(the `No valid triton configs` OOM-reject spam during search is benign).

### FA4 compileop + fixed-shape collate for cudagraph replay (2026-11-02)

Root causes of the `reduce-overhead` re-record storm, established by unit
probes: dynamo traces into `flash_attn.cute`'s python (fabricating int64
tensors that hit FA4's int32 asserts under compile) and emits value guards
on the `numseqs`/`max_seqlen_*` `.item()` scalars (46-61 rows per batch) —
every distinct combination recompiles and re-records.

Two env-gated mechanisms were added (default behavior unchanged):
- `FIXED_NUMSEQS` + `FIXED_MAXSEQ_PREFIX/CAUSAL/ALL` in
  `compute_aux_seq_tensors_scalars` (models/flash_attention_prefixlm_v2.py):
  pin row count with zero-length dummy rows (cu_seqlens edge-padded to the
  final boundary) and pin max_seqlen to dataset-truth caps (FA4 accepts
  upper bounds). For the Mimir Mini B dataset: 64 / 867 / 277 / 1077.
- `FA4_COMPILEOP=1` (models/flash_attention_prefixlm_fa4.py): the FA4
  PrefixLM seqused path is exposed as registered custom ops
  (`flash_attn::fa4_prefixlm_seqused_fwd/_bwd`) with fixed-shape fake
  kernels behind a `torch.autograd.Function`, mirroring the sm90 compileop
  pattern. Slicing and `.item()` happen inside the op at runtime; dynamo
  never traces into flash_attn.cute. `FA4_DYNAMO_DISABLE=1` is a simpler
  fallback (plain graph break around the wrapper).

Small-scale verification (1 GPU): FA4 accepts zero-length varlen segments
bit-exactly (fwd + dq/dk/dv, dummy rows + upper-bound caps); the op path
matches the original eager path exactly in eager AND compiled mode
(fwd + all grads 0.0); four varied-content batches compile once with zero
dynamo recompilations. Pitfall found: a fake kernel must NOT return the
same tensor object twice — functionalization treats repeated fake outputs
as aliases and inductor reuses one buffer, silently corrupting the second
output (here: pass-2 LSE overwriting pass-1's, wrong grads only when
compiled). A second pitfall bit the first 8-GPU run: NumPy 2 removed
value-based casting, so `np.concatenate(([0], np.cumsum(x, dtype=np.int32)))`
promotes the result to int64 and FA4's int32 assert rejects the batch's
`cu_seqlens`; the leading zero must be `np.zeros(1, dtype=np.int32)`.

At full 8-GPU FSDP scale the fixed+compileop config trains loss-identical
to the control (steps 0-25 match to ~1e-4: 11.5634, 11.5592, 11.5169,
11.4583 vs 11.5635, 11.5590, 11.5168, 11.4583; min step 0.2375 s).
`reduce-overhead` was then tested and **rejected**: with
`TORCH_LOGS=cudagraphs` the run showed 498 tree recordings, zero replays,
and thousands of `Running eager function=partition_N` fallbacks per rank —
cudagraph trees re-record every step because CPU scalar inputs to the FA4
op force eager partitions and FSDP2/optimizer allocations interleave with
the recorded pool. min step 0.475 s vs 0.2375 s default. Given the nsys
attribution (gaps ~6-15% at best), cudagraph replay does not pay for this
loop shape; keep `compile_train_batch_mode=default` with the compileop
path as a robustness win (zero dynamo recompiles, bit-exact parity).

### Full-scale 200-step results and final config (2026-11-02)

Unprofiled 200-step 8-GPU B + Mimir runs (median/min s/step, final loss):

| config | median | min | loss |
|---|---|---|---|
| control (dynamic, original) | 0.2342 | 0.2263 | 7.6653 |
| FIXED_* only | 0.2404 | 0.2242 | 7.6654 |
| FIXED_* + `TORCH_DYNAMO_CACHE_SIZE=64` | **0.2339** | 0.2257 | 7.6653 |
| FIXED_* + `FA4_COMPILEOP=1` | 0.2508 | 0.2374 | 7.6653 |
| reduce-overhead (FIXED_+compileop) | 5.908 | 0.475 | 7.6465→ |

All configs are semantically inert (loss identical to control). Findings:
- Even with FIXED_* scalars, the traced-cute path still hits
  `torch._dynamo hit config.recompile_limit (8)` — guard churn originates
  inside flash_attn.cute tracing, not only the .item() scalars. Raising
  `cache_size_limit`/`accumulated_recompile_limit` via the env-gated
  `TORCH_DYNAMO_CACHE_SIZE` knob (pretrain.py) lets all variants compile
  once: zero limit-hits and control-speed steady state.
- `FA4_COMPILEOP=1` costs +7% (0.2508 vs 0.2342): inductor cannot fuse
  across the ~26 custom-op attention boundaries — the 200-step nsys
  profile shows ~465 extra non-vectorized `elementwise_kernel` +
  `CatArrayBatchedCopy` launches per GPU-step, while the FA4 cutlass
  kernels themselves are unchanged (211.4 vs 216.8 ms/window). Under nsys
  the extra launches are amplified (wall 306 vs 243 ms); unprofiled cost
  is the honest +16.6 ms/step.
- Decision: default config = `FIXED_NUMSEQS/FIXED_MAXSEQ_*` +
  `TORCH_DYNAMO_CACHE_SIZE=64`, original traced-cute FA4 path,
  `compile_train_batch_mode=default`. The int64-cu fix is mandatory;
  `FA4_COMPILEOP` and `FA4_DYNAMO_DISABLE` remain available behind env
  flags for future cudagraph/robustness work.

### Below 0.23 s/step: FSDP unit granularity and foreach optimizer (2026-11-02)

Two structural changes were tested on the 200-step B + Mimir probe
(baseline 0.2339 s/step median, 0.2257 min, loss 7.6653, config above):

- **`fsdp_wrap_policy=single_unit`** (new option in `fsdp_wrap_modules`,
  pretrain.py): skips per-block FSDP units so only the root wrap remains —
  13 ReduceScatters + ~49 AllGathers per step collapse into one
  collective pair. **median 0.2245, min 0.2184 (−4.0%), loss 7.6654.**
  Memory stays fine for B (73 GiB peak); for larger models the whole-model
  unsharded all-gather buffer may not fit, so the default remains
  `transformer_block` and this is opted in per run.
- **`ADAM_FOREACH=1`** (env-gated foreach path in `models/adam_atan2.py`):
  buckets params by (lr, wd, betas, ema, state presence) and uses
  `torch._foreach_*` (verified to dispatch correctly on DTensor) for
  weight decay/lerp/second-moment/sqrt; per-param residual is div+atan2+add
  because `_foreach_atan2` does not exist. NOTE: `atan2(y, x/c) ≠
  atan2(y, x)` — the `bias_correction2_sqrt` division must stay (scaling
  only one atan2 argument changes the angle; only scaling BOTH preserves
  it). Bit-exact parity test vs the per-param loop passes (mixed
  dtypes/shapes, EMA, per-param lr scales, grad-less skips, step
  counters). **Measured gain at B scale: none** (0.2342 vs 0.2339 median;
  the optimizer region was already small after the fixed-shape env) —
  kept default-off for future larger models where the ~600-launch loop
  matters more.

Combined result: 0.2245 s/step median (−4.0% vs 0.2339, −8.2% vs the
original 0.244-era baseline), loss parity throughout.

### L-size probes with both tokenizers (2026-11-02, corrected same day)

Initial L probes mistakenly used `gradient_accumulation_steps=1` (32k
tokens/GPU microbatch, copied from the B probes). That OOMs L at 173 GiB
(genuinely out of memory — allocation fails in the compiled
[32768, 65536] logits buffer with only 204 MiB fragmentation slack), and
the workaround detour (activation_checkpointing=full + compile off,
1.2554/1.4398 s/step) is a **superseded wrong-regime result**. Production
L/XL runs use `gradient_accumulation_steps=2` (16k microbatch),
`activation_checkpointing=none`, compile on, `ema=0.9999` — per
`scripts/schedule_dfm12_xl_epoch11.py`. With that config plus all B-winner
settings (`single_unit`, FIXED_* collate, `TORCH_DYNAMO_CACHE_SIZE=64`,
default compile mode), L runs compiled and clean:

| L, 200 steps, GAS=2, compiled, single_unit, ema=0.9999 | median | min | loss | acc |
|---|---|---|---|---|
| Mimir Mini 65k (b_opt_data) | 0.6355 | 0.6186 | 6.5864 | 0.1780 |
| Gemma 4 262k (sampled_dfm6) | 0.7825 | 0.7699 | 7.0135 | 0.1775 |
| Mimir Mini + `ADAM_FOREACH=1` | 0.6344 | 0.6170 | 6.5865 | — |

The 4× vocab costs +0.147 s/step (+23%) at L (vs +35% at B — backbone
dominates more as models grow). `ADAM_FOREACH` remains noise-level even
with EMA active. Known limitation kept for the record:
`compile_train_batch=true` + `activation_checkpointing=full` fails
reproducibly with `torch.utils.checkpoint.CheckpointError` (recompute
metadata mismatch: weight [5120,1280]→[1280,5120]; rope tensors gain a
size-1 dim) under both wrap policies and both reshard settings — but the
resolution is GAS=2 without checkpointing, not compile-off.

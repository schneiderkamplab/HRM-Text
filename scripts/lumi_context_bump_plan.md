# Plan: Increase Context Length for HRM-Text on LUMI

Status: not started. Prereq for any context > 4096.

## Current state (verified 2026-06-18)

- The training context length is **4096** (the dataset is tokenized/sampled at
  `max_seq_len = 4097`; the dataloader subtracts 1 for the autoregressive shift).
- The model uses **RoPE** (`pos_emb_type: rope`, `rope_theta: 10000.0`), so there
  is **no architectural context cap** — context length is determined by the data
  and by the per-GCD token budget, not by a model config field.
- Hard constraint in `pretrain.py` / `dataset_new.py`: the per-GCD packing budget
  `batch_max_length = global_batch_size / world_size / gradient_accumulation_steps`
  must be **>= context length**, or long sequences cannot be packed into a
  microbatch and the sampler yields nothing.
- On LUMI only the pre-sampled `sampled_original_sapient` (4096) exists. The raw
  Sapient source data, the tokenized intermediate, and the Rust tokenizer
  (`data_io/tokenizer`) are **NOT on LUMI**. So increasing context is a
  data-pipeline job, not a training flag.

## What "increase context" requires

To train at context C (e.g. 8192) you must rebuild the dataset so each sample can
be up to C tokens, then ensure the run's per-GCD budget >= C.

### Step 1 — Stage source + tokenizer to LUMI
Bring to `/scratch/project_465002606`:
- The original Sapient cleaned source roots (`data_clustered/`, `data/`) — this is
  the large download (~324 GB per the wiki) OR the already-tokenized intermediate
  if it can be re-sampled at a longer length.
- The Rust tokenizer binary + `data_io/trained_tokenizers/bpe/tokenizer.json`, or
  build the tokenizer on LUMI (`cd data_io/tokenizer && cargo build --release`).

NOTE: confirm `/scratch` quota headroom first (`lumi-quota`). The source + a
longer-context tokenized tree + sampled output can be ~1 TB combined.

### Step 2 — Tokenize at the longer max_seq_len
Re-run the tokenizer with the larger sequence cap (the tokenizer/sampler chunk to
`max_seq_len`). Output to a new tree, e.g.
`/scratch/project_465002606/data/tokenized_original_sapient_8192`.
Do NOT overwrite the 4096 tree.

### Step 3 — Sample at the longer length
Run `data_io/sample_tokenized.py` against the new tokenized tree with the longer
`max_seq_len`, producing e.g.
`/scratch/project_465002606/data/sampled_original_sapient_8192/` with a
`metadata.json` reporting `max_seq_len = 8193`.
Inspect the analytics output (token counts per source) before training.

### Step 4 — Point training at the new dataset and size the batch
- `data.path=/scratch/project_465002606/data/sampled_original_sapient_8192`
- Ensure `global_batch_size / world_size / gradient_accumulation_steps >= 8192`.
  Example at 4 nodes (32 GCDs): need >= 8192 tokens/GCD, so
  `global_batch_size >= 32 * 8192 = 262144` at `grad_accum=1`, or raise
  `gradient_accumulation_steps`.
- Memory: doubling context roughly doubles attention activation memory. At 64 GB/
  GCD this may need a larger `gradient_accumulation_steps`, `reshard_after_forward`,
  or activation checkpointing. Validate with a dev-g smoke before a full run.

## Quick checks before committing to a longer-context run
- [ ] Source data + tokenizer present on LUMI scratch, quota OK.
- [ ] New tokenized + sampled trees built; `metadata.json` shows the intended
      `max_seq_len`.
- [ ] `batch_max_length >= context` for the chosen node count / batch / grad-accum.
- [ ] dev-g single-GCD then 8-GCD smoke at the new context with no OOM.
- [ ] RoPE: consider raising `rope_theta` for much longer contexts (4096 -> 8192
      is usually fine at theta 10000; very long contexts may want a larger theta
      or scaling). Decide before training; it changes positional behavior.

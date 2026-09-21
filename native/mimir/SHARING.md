# PrefixLM shared ownership and bounded copies

2026-09-18. This working-tree follow-up supersedes the one-owner/full-sequence-only
restrictions in [RESUMPTION.md](RESUMPTION.md). No patch packaging or submission.

## Implemented contract

- Multiple sequence IDs may own one input row with **unified KV**, matching the
  existing backend's coupled-sequence layout. Each owner advances its phase and gets
  the same requested output row. Both new prefixes and answer chunks are supported.
- Admission verifies matching prefix boundaries, shared cached dependencies and
  matching preceding input rows. For prefix queries it also verifies the entire
  bidirectional future prefix. Duplicate owners and divergent dependencies reject
  before mutation. Matching lengths or token IDs alone do not prove shared hidden states.
- Physical capacity counts shared input rows once; boundary logits from one shared
  output are retained through a shared immutable row. Dependency comparisons check
  cached ownership once per sequence pair and each new row segment once, rather than
  comparing the whole prefix again for every token.
- `llama_memory_seq_cp(src, dst, 0, end)` now replaces the destination with a bounded
  source prefix/answer head, provided `end` includes the complete bidirectional prefix.
  This works with unified and separate KV. Separate KV reuses its full-buffer copy
  followed by metadata trimming; it does not yet optimize copied byte volume.
- An answer-only range `[begin, end)` is allowed when destination history before
  `begin` is already physically shared with the source and prefix boundaries match.
  This proof currently requires unified KV. The destination ends at `end`; its later
  suffix is discarded because it could depend on replaced states.
- Shortened copies invalidate boundary logits: the source's final logits do not
  belong to an earlier boundary. Full-boundary copies preserve them. Empty ranges and
  self-copies are no-ops. Rejected copies preserve both sequences.

No new state format, token-history ledger or attention kernel was introduced. Full
context persistence already records physical cell ownership, so sharing survives
that round-trip. Independently recomputed or separately restored sequences are not
assumed equivalent; fork them or submit a shared complete prefix to establish common
ownership. Separate-stream shared rows still fail before execution, as the existing
sequential batch splitter does not support coupled sequences; use separate rows or
copy a complete evaluated prefix instead.

## Validation

Release passes 7/7 with 4,264 CPU/Metal engine checks. CPU UBSan passes 7/7 with
2,132 engine checks and no sanitizer diagnostics. Stock Q8 server passes 104/104
checks across separate/unified KV and fresh-process resumption. Ordinary HRM/Llama
architecture regressions pass. Independent CPU and UBSan oracles pass 31/31; the
new shared-owner cases also pass on fused/unfused Metal. Metal totals are 28/31 and
29/31 respectively, retaining exactly the previously documented numerical failures.

Final counts, source hashes and reports are in [sharing-results.json](sharing-results.json).
Logs are under `logs/mimir-sharing/`. The bounded suite covers shared prefix/answer
parity, owner order, all-owner logits, persistence, duplicate IDs, differing future
prefix dependencies, differing cached histories, shared physical capacity, and bounded
copies followed by answer continuation on both layouts. Existing regression tests remain.
The independent HF reader/generator now adds shared-owner prefix and answer steps.
The Linux/CUDA execution plan remains [linux-testing.md](../../linux-testing.md).

## Which restrictions to lift next

These are priorities and implementation assessments, not additional features claimed
implemented in this follow-up.

| Priority | Extension | Difficulty and concrete work |
| --- | --- | --- |
| Next | Grammar persistence | Moderate, bounded. Encode grammar stack pointers as validated rule/element offsets; save partial UTF-8 and lazy-trigger buffers/positions. Reconstruct regex/configuration from matching grammar definitions. Clone-before-commit and malformed-state tests matter; dumping raw structs is wrong. |
| Next | Reasoning-budget persistence | Low-to-moderate. Save state-machine phase, remaining budget, matcher states, forced-token cursor and end-match state; validate against matching configuration. Include boundaries mid-delimiter, forced closure and incomplete UTF-8. |
| Next integration step | OpenAI response/parser continuation | Moderate. Retain parser input/state, emitted content/reasoning/tool-call offsets and stable tool IDs. Define continuation as a new HTTP response with explicit resume metadata; a closed network stream itself cannot be restored. Parser replay may reduce custom serialization where deterministic. |
| Next, separately reviewed API | Custom sampler opt-in | A small API change with compatibility/ownership consequences. Provide optional save/load callbacks (or a registration mechanism), version/configuration identity and transactional restore. Unknown user-defined state cannot be serialized automatically; unsupported remains correct when callbacks are absent. |
| After single-generation parser support | Parent/child retention | Moderate-to-high. Snapshot the group, child samplers/pending tokens, shared KV and completion statuses consistently; restore slot mappings, group IDs and result aggregation atomically. Saving independent slots alone does not preserve group scheduling. |
| If backend sampling is an intended supported deployment | Backend sampler persistence | Moderate-to-high. Synchronize GPU work and preserve committed vs speculative RNG draws, device-resident adaptive state and graph lifetime. Host serialization by itself does not capture that contract. Validate on CUDA, not only CPU. |
| Useful optimization after correctness | Exact-complete-prefix prompt caching | Moderate. Cache the whole bidirectional prefix with its boundary logits and immutable model/adapter identity. Restore exact matches. Ordinary longest-common-prefix trimming/replay remains invalid when a new prefix changes prior hidden states. |
| Later | Ordinary causal draft/verify speculation after prefix initialization | Medium-to-high. Prefill target/draft with their proper complete prefixes, then handle causal verification, accepted/rejected suffixes, rollback and sampler accounting. More plausible than speculative prefix construction; architecture-specific draft methods add work. |
| Later, demand-driven | Multimodal PrefixLM | High. Admit embedding inputs and modality positions, preserve whole-prefix dependencies through projector/chunking paths, and validate actual trained multimodal PrefixLM models. Text success is insufficient. |

The first two are sensible PR-scope additions if production resumption is advertised.
OpenAI parser continuation is also useful for the planned chat app. Parent/child,
backend sampler and custom callback support are distinct contracts; do not bundle them
as a trivial JSON serialization change. Generic sampler persistence may deserve a
separate preparatory PR to reduce PrefixLM-specific review scope.

## Architecture and restore priorities

1. **Broaden qualification of ordinary full-attention transformer decoders**, including
   one dense and one MoE architecture already using the same KV/mask machinery.
   Much of this is fixture/qualification work, not a new PrefixLM architecture. Start
   with models actually intended for deployment; causal checkpoints are semantic
   controls, not evidence of PrefixLM training quality. HRM-Text and Llama are covered now.
2. **Device-resident snapshots** are the next restore extension if prompt caching or
   beam/fork throughput needs them. Audit the device reader's deferred-copy/destructor
   behavior, stage and validate metadata, synchronize failures and commit atomically.
   These are in-process GPU snapshots, not portable durable files. CUDA testing is essential.
3. **Sliding-window/hybrid attention** only with a concrete PrefixLM-trained model and
   an explicit policy for prefix retention versus window eviction. Complete bidirectional
   visibility and a finite sliding window cannot simply be assumed compatible.
4. **Partial-only state flags** are mainly useful for supported recurrent/SWA memory
   contracts; they are not a missing spelling of bounded token-range copying. Do not
   implement them for plain full-KV PrefixLM just to clear a checkbox.
5. **Temporal recurrent/SSM models (e.g. Mamba/RWKV), diffusion and encoder-decoder
   cross-attention** require different state/attention semantics. Do not add them to this
   initial decoder-KV PR without a real model requirement. HRM's repeated transformer
   depth is already supported and is different from a temporal recurrent cache.
   Encoder-only bidirectional inference already has its own mode and does not need
   an autoregressive PrefixLM answer lifecycle bolted onto it.

Keep the correctness restrictions: complete prefix evaluation, no arbitrary edits to
retained dependency history, no changing context-wide weights under live KV, and
explicit compatibility checks on restore. Some can gain specialized algorithms later;
removing checks alone would silently return incorrect results.

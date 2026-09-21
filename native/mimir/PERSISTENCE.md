# PrefixLM persistence and exact-prefix cache follow-up

**Superseded in part (2026-09-18):** ordinary causal activation, version-3 server
envelopes, test relocation and the two-patch split are now documented in
[DECODER-RESUMPTION.md](DECODER-RESUMPTION.md). The measurements below describe the
preceding revision; use `decoder-results.json` for current source identity.

2026-09-18. Working-tree implementation; no final patch packaging or submission.
This supersedes the proposed-only grammar/reasoning/parser/cache/backend sections in
[SHARING.md](SHARING.md) and the older host-only resumption limits in
[RESUMPTION.md](RESUMPTION.md). Source identity and evidence are recorded in
[persistence-results.json](persistence-results.json).

## Implemented behavior

- Built-in grammar snapshots store stacks as rule/element offsets, partial UTF-8,
  lazy-trigger buffers/positions and trigger activation state. Configuration must match.
- Common sampler snapshots include the complete reasoning-budget state machine:
  phase, remaining budget, partial delimiter matches, forced-token position and matched
  end delimiter. This preserves manual forcing as well as token-driven transitions.
- Backend sampler snapshots preserve committed and transactional RNG/history. Restore
  uses the existing graph-safe copy hooks, preserving tensor bindings. Synchronize an
  attached context before snapshot/restore. Generated graph output buffers are not saved.
- Native completion, OpenAI Chat and Responses resume through the existing explicit
  slot protocol, including file save/restore, fresh process and destination remapping.
  Parser state is reconstructed from saved emitted text plus matching parser settings.
  Generated tool-call IDs remain stable across replay; a new HTTP request gets fresh
  response framing/IDs. Streaming emits continuation deltas. Nonstream OpenAI messages
  and final Responses objects are cumulative; native completion text remains incremental.
- `cache_prompt: true` enables one complete-prefix host cache entry per slot. Identical
  full token input restores KV and boundary logits with a fresh sampler and accepted
  prompt history; changed or extended input misses. This never re-decodes a prefix's
  last token as an answer. Erase drops the cache. Boundary probabilities match cold runs.
- Cache-enabled requests consistently use host sampling, including when backend sampling
  was requested; n>1 uses normal prefill/fork scheduling rather than this cache fast path.
  Grammar/reasoning constraints retain the ordinary host-sampling fallback. Resumption
  checks cache and probability settings as well as sampler configuration, preventing an
  unnoticed switch of sampling execution path.

The library sampler format is now SMP2, the common sampler bundle version is 2, and
server retained metadata version is 2. Old development snapshots are rejected. These
are same-runtime snapshots, not portable cross-version checkpoints or a guarantee of
bit-identical sampling across different hardware, precisions or C++ standard libraries.
Use the same model, vocabulary, adapters and effective sampling configuration.

Regression testing exposed an existing adaptive-probability clone bug: it reset RNG
state and omitted original probabilities. The clone now preserves both. XTC/Mirostat
clones also preserve their resolved default seed. A token-triggered grammar now clears
obsolete trigger positions with its trigger buffer, keeping saved state consistent.

## Ordinary encoder/decoder parity

At base `c9a5eeeb34ab8f794ea7510ca52d25da13728a5b`, the public sampler interface offers
clone/copy hooks, including graph-safe `copy_state`. It does not provide automatic disk
serialization for arbitrary custom samplers or user-owned application objects. The
new built-in sampler snapshot APIs are attention-mode independent; custom owners still
serialize their own state and use the existing hooks. Unknown custom sampler snapshots
fail explicitly rather than dropping state or guessing how to serialize pointers.

Likewise, ordinary server slot save/restore persists idle prompt/KV state, not an
in-flight parent/child scheduling group, HTTP streams or arbitrary task graphs. PrefixLM
already supports live child forks and cross-sequence KV copies. Retained n>1 groups stay
outside the new single-generation resumption protocol; this is not a missing ordinary
encoder/decoder group-checkpoint feature. A generic group format would be new work for
all attention modes, including task identities, child RNGs, queue/cancellation state and
atomic group admission.

## Local evidence

| Check | Result |
| --- | --- |
| macOS Release CTests, CPU + Metal | 8/8; 4,280 PrefixLM assertions across HRM/Llama |
| macOS CPU UBSan, fatal errors | 8/8; 2,140 PrefixLM assertions |
| Graph-bound backend sampler transaction/restore | CPU, Metal and CPU UBSan pass |
| Parser continuation | Four splits across reasoning, closing delimiter, content and tool arguments; Responses tool reannouncement passes |
| Q8 Mimir server, separate/unified KV | 77 + 77 checks pass |
| Fresh-process restore and destination remap | 14 + 14 checks pass |
| Independent F32 CPU oracle | 31/31 steps at max-absolute tolerance 1e-4 |

The 182 HTTP checks include stochastic native continuation, grammar, forced reasoning
budget, backend sampling, OpenAI Chat/Responses state, streaming Chat deltas, rejection
of changed sampling paths, exact cache cold/hit/extended-prefix miss, and cached boundary
probabilities. All real model prompts use the pinned Mimir chat template, directly or
through the server chat endpoint. Reasoning state tests additionally cover all five
phases, partial delimiters, manual forcing, rearming and malformed snapshots. Generic
sampler tests cover ordinary distribution, Mirostat, adaptive probability, DRY/XTC,
resolved random seeds and failure preservation. Logs live in `logs/mimir-persistence/`.

This run does not reclassify earlier strict Metal oracle deviations as passes. See
SHARING.md for the previous fused 28/31 and unfused 29/31 outcomes, also seen in causal
controls. No attention kernel or arithmetic was changed by this follow-up. BF16/Q8/Q4
Linux CPU/CUDA qualification, ASan, CUDA memcheck and controlled timing remain pending.

## Reproduction and remaining boundaries

Use [linux-testing.md](../../linux-testing.md) for the complete source-transfer and
CPU/CUDA commands. Existing upstream test files carry the generic tests:

- `test-reasoning-budget` and `test-llama-archs --prefix-lm -a hrm_text -s 42` (also llama).
- `test-backend-sampler --model <generated hrm-false.gguf> --device cpu --test multi_output_dist_transaction`;
  repeat with `--device gpu`, and under Compute Sanitizer on Linux CUDA.
- `test-chat --parser-continuation` with server/test targets enabled.
- `native/mimir/tests/server_e2e.py --parallel --resumption`, followed by server restart
  and `--parallel --resume-only`. Preserve its `extended-reference.json` alongside the
  output and all slot files. Repeat separate/unified KV and the required model formats.

CI now includes sampler persistence in CPU release/ASan+UBSan and optional trusted
self-hosted CUDA/memcheck lanes, plus bounded parser tests in the CPU lanes. It checks
the source manifest rather than applying stale packaged patches. A clean checkout
cannot pass that preflight until the qualified source is recorded in the submodule.
Workflow syntax was checked locally; Linux/GitHub CI was not executed here.

Other boundaries remain: complete prefixes must fit a physical batch; full host state
only; fixed rather than mutable live adapters; dependency-checked shared rows need
unified KV; generic partial prompt reuse, speculation, multimodal, Anthropic retained
transport state and other memory architectures need their own contracts/tests. These
are separate from the implemented persistence extensions. Linux qualification still
precedes final packaging and review.

Documentation checks: workflow YAML, harness Python syntax and diff whitespace pass.
The OKF validator still reports its two pre-existing benchmark-charts indexing/frontmatter
errors; this update introduces no additional wiki validation errors.

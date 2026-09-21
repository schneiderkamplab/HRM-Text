# Ordinary decoder resumption and patch separation

2026-09-18. Local implementation and review drafts, not Linux qualification or
final PR packaging. [decoder-results.json](decoder-results.json) records source,
patch and evidence hashes. This supersedes the PrefixLM-only activation and
version-2 server metadata described in [PERSISTENCE.md](PERSISTENCE.md).

## Behavior and scope

Ordinary text causal decoding now supports the same retained-generation protocol
as PrefixLM: explicit slot, `retain_state: true`, save, restart, restore/remap, then
`resume: true`. The snapshot preserves the pending sampled token, sampler and
output bookkeeping, including OpenAI parser replay. Original prompt and effective
sampling/parser settings must match. Native text and streaming deltas are incremental;
nonstream OpenAI messages and final Responses objects are cumulative. Transport IDs
and stream framing are new for each HTTP request.

Ordinary completed requests retain their existing idle prompt/KV behavior. A retained
slot is protected from automatic assignment and idle-cache eviction. Explicitly
replacing or consuming it clears stale generation metadata. Legacy prompt/KV-only
slot files still save/restore, but cannot be resumed as retained generations. A tagged
version-3 envelope distinguishes retained generations from legacy token metadata;
old development generation envelopes are not upgraded. LoRA mutation is blocked while
retained state exists. Restore requires the same runtime/model/configuration.

The [review drafts](patches/review-drafts/README.md) contain two logical features:

- **Main PrefixLM patch:** attention/masks, decode API and scheduler, ownership/copies,
  KV/phase/logit snapshots, fixed adapters/control vectors, exact complete-prefix
  caching, custom-state parity and ordinary live parent/child forks.
- **Separate persistence patch:** built-in/common sampler snapshots, grammar,
  reasoning-budget and backend state, plus retained server generations and OpenAI
  parsing. An alternate standalone patch applies this feature without PrefixLM.

Custom objects remain caller-owned in every attention mode. Neither the base decoder
server nor this extension serializes complete parent/child scheduling groups. Those
are parity decisions in the main patch, not extra serialization implementations.
Library KV snapshots remain in the main patch independently of optional sampler/server
persistence. Main-only PrefixLM slot-file endpoints reject because generic generation
bookkeeping is absent; exact-prefix cache and library KV snapshots still work.

The generic host sampler tests moved from the PrefixLM engine test into the existing
`test-backend-sampler --test host_persistence` target. CI invokes it explicitly.
Both features retain their own documentation and bounded tests.

## Measured local results

macOS M2 Max; real-model HTTP tests use Mimir Q8_0, its own checkpoint chat template,
Metal offload and separate/unified KV. Ordinary decoder tests use HRMText with causal
attention: this establishes attention-mode parity, not every decoder architecture.

| Configuration | Result |
| --- | --- |
| Combined patches, ordinary decoder | 118/118 HTTP checks: 45 initial + 14 fresh-process checks per layout |
| Combined patches, PrefixLM | 182/182 HTTP checks: 77 initial + 14 fresh-process checks per layout |
| Main-only PrefixLM | 3,880 engine checks across HRM/Llama and CPU/Metal; 72/72 HTTP/cache checks |
| Standalone persistence, ordinary decoder | 118/118 HTTP checks, same separate/unified restart matrix |
| Standalone persistence, sampler/parser | Host sampler, CPU/Metal backend transactions, reasoning-budget and parser-continuation tests pass |
| Combined release regression | 8/8 CTests; 3,880 PrefixLM engine checks |
| Combined CPU UBSan regression | 8/8 CTests; 1,940 PrefixLM engine checks; explicit host sampler persistence passes |
| Draft application/reconstruction | Main + persistence exactly reconstruct current llama.cpp changes; standalone exactly reconstructs its isolated tested tree |

Main-only's 72 HTTP checks are 32 ordinary PrefixLM checks plus four exact-cache
checks per layout; filenames containing `restart` in that directory label fresh
cache-only runs, not retained-generation restart tests. Engine counts decreased
because generic sampler assertions moved to their own target, not because coverage
was dropped. The HTTP suite checks pending-token continuity, stochastic continuation,
stop-string boundaries, grammar/reasoning/backend sampling, OpenAI Chat/Responses,
slot remapping, eviction protection and legacy prompt files. Synthetic parser tests
cover reasoning/tool argument splits and stable tool IDs separately.

The standalone run initially exposed an outdated tokenizer prerequisite: the historical
codec patch lacked `spm-bpe-mistral`. The refreshed independent codec draft includes it;
both feature patches remain free of tokenizer changes. Reconstruction is byte-compared,
not inferred merely from `git apply` returning success.

## Remaining qualification

Run [the Linux hand-off](../../linux-testing.md) before final packaging/review:
CPU release + ASan/UBSan, actual CUDA + Compute Sanitizer, bounded real-model
BF16/Q8/Q4 checks, independent logits and controlled timings. Qualify both isolated
patches as well as their combined build. The workflow was updated locally; no GitHub
CI run is claimed. The implementation is now committed for Linux hand-off; the
source-hash preflight verifies that pinned checkout. See `linux-handoff.json`.

Prior strict Metal oracle deviations remain historical unresolved numerical evidence;
this server/persistence work does not establish a new oracle pass. Device/partial
snapshots, activated or mutable live adapters, speculative/multimodal retention and
persistent scheduling groups remain outside this qualified contract. Full runtime
snapshots are not portable cross-version/model/hardware checkpoints.

Repository diff whitespace checks, HTTP harness syntax, workflow YAML and source
manifest verification pass. OKF validation still reports the two pre-existing
`benchmark-charts.md` issues (missing frontmatter and parent-index link); no new
wiki validation errors were introduced.

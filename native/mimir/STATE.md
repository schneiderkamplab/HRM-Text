# PrefixLM persistence, forks and fixed LoRA

Historical report: the 2026-09-18 [resumption follow-up](RESUMPTION.md) supersedes
its no-logits/sampler, control-vector, mixed-phase, server-resumption and logical-capacity
restrictions. Test counts below describe the preceding implementation.

Date: 2026-09-18. Working-tree implementation against llama.cpp base
`c9a5eeeb34ab8f794ea7510ca52d25da13728a5b`. This supersedes the blanket
persistence/cross-sequence-copy/adapter restrictions in the earlier
[sequence qualification](SEQUENCES.md). Packaged patches remain the older
snapshot until Linux qualification and subsequent packaging/review.

## Implemented behavior

- Context and per-sequence persistence use the existing byte-buffer and file
  APIs. The PrefixLM envelope carries each sequence's prefix boundary and next
  position, plus an adapter-weight/scale fingerprint. Sequence restore remaps
  IDs; restoring an empty sequence clears its destination. Format identifiers
  distinguish PrefixLM from ordinary state without changing ordinary formats.
- Header validation precedes KV mutation. Malformed/truncated KV invalidates
  the destination, or the whole context for context restore. Unrelated sequences
  survive a sequence-restore failure. Restored positions must be unique,
  contiguous, start at zero and match metadata. A backend failure while flushing
  pending cross-stream copies invalidates the context because several sequences
  may be affected; that backend-failure branch was not fault-injected locally.
- Full-sequence copy/fork replaces the destination and copies phase metadata.
  It reuses shared cells or deferred stream copies. Saving immediately after a
  fork flushes pending copies first. Server `n > 1` uses this same operation;
  independent branches retain separate subsequent answers and cancellation.
- Fixed ordinary LoRA uses existing graph operations. Install before prefill;
  clear all live KV before changing/removing adapters or scales. Reapplying the
  same configuration is allowed. State restore checks weights/scales, not
  pointer identity. Server startup LoRA is supported, and rejected adapter
  configuration is no longer silently ignored by the common helper.

The state is a runtime snapshot, not a model checkpoint. The caller loads the
same model weights and compatible KV configuration first. Logits and sampler
state are not serialized; retain the boundary logits or an already selected
answer token separately. Replaying the last prefix token causally is invalid.
The adapter fingerprint detects accidental mismatch, not malicious tampering;
no cryptographic or untrusted-input security claim is made.

The sparse-ID tests exposed a pre-existing ordinary KV serialization issue:
writer/reader used the active sequence count as an ID bound. They now use the
actual sequence-ID mapping range. The regression also verifies ordinary causal
state with a sparse ID. Other new validation is specific to PrefixLM, apart
from bounding restored cell count by cache capacity before allocation.

## Evidence

Final measured results are recorded in [state-results.json](state-results.json).
Raw build/test logs, reference specifications and server JSON are under
`logs/mimir-state/`. Essential state/fork/adapter tests are in the existing
upstream architecture test, without dependency on the native application.

| Check | Result |
| --- | --- |
| Release integration | 7/7; 1,518 engine checks per architecture, 3,036 total |
| CPU UBSan integration | 7/7; 759 engine checks per architecture, 1,518 total; no sanitizer finding |
| Stock Q8 server | 24 one-slot + 33 separate-KV + 33 unified-KV + 35 fixed-LoRA checks = 125 passed |
| Independent CPU / CPU UBSan / unfused Metal reference | 27/27 steps each |
| Independent fused Metal reference | 26/27; unchanged causal-control maximum error 0.00010558962821960449 versus 0.0001 |
| Ordinary HRM / Llama architecture regressions | Both pass; include existing CPU/GPU comparison and model round trips |

Host-state engine tests use F32 KV. The earlier BF16/Q8/Q4 model-weight
qualification is retained separately; this is not a claim that every KV
quantization/layout/backend combination has been qualified. The added final
fork case includes an already-generated answer and independently trims/regenerates
the destination's answer while preserving the source boundary and positions.

The bounded matrix covers HRM and Llama, CPU/Metal, flash on/off and separate/
unified KV. It tests pending-copy saves, branch isolation, ID remapping,
independent phases, fresh contexts, context/sequence files, empty state,
malformed boundaries/magic, duplicate interior KV positions, truncated KV,
ordinary-format compatibility, and nonzero fixed LoRA plus mutation rejection.
An equivalent adapter object verifies pointer-independent restoration.

Server chat experiments use Mimir's checkpoint chat template and pinned HF
answers. The fixed-startup-LoRA server fixture has zero weights, so it verifies
loading and scheduling with unchanged reference answers; nonzero adapter
semantics are tested in the engine suite. It is not a trained-adapter quality
evaluation. The retained BF16/Q8/Q4 quality/drift evidence is in
[QUALIFICATION.md](QUALIFICATION.md); this turn does not rerun that entire matrix.

The first server driver used the system Python, which does not support the
harness's `zip(strict=True)`. Final runs use the established Python 3.12 virtual
environment. An initial UBSan-build test failure exposed an uninitialized alpha
in the synthetic adapter fixture, not a sanitizer finding in production code.
Both fixture objects now initialize it explicitly; the failed log is retained
as `ubsan-fixture-failure.log`.

## Reproduction

Use the current working tree, not the old packaged patch files:

```sh
cmake --build logs/mimir-engine/build --target test-llama-archs llama-server -j8
logs/mimir-engine/build/bin/test-llama-archs --prefix-lm -a hrm_text -s 42
logs/mimir-engine/build/bin/test-llama-archs --prefix-lm -a llama -s 42
cmake --build logs/mimir-runtime/build -j8
ctest --test-dir logs/mimir-runtime/build --output-on-failure
cmake --build logs/mimir-runtime/ubsan -j8
ctest --test-dir logs/mimir-runtime/ubsan --output-on-failure
```

The independent reference generator and reader are documented in
[the library contract](../../llama.cpp/docs/development/prefix-lm.md).
For server tests, use the commands in [SEQUENCES.md](SEQUENCES.md), writing new
output paths. Add `--lora <adapter.gguf>` to the server and `--fixed-lora` to the
harness for the fixed-startup-adapter fixture. Preserve the fixture's zero
weights if comparing against the unchanged HF answers.

## Remaining restrictions and their justification

| Restriction | Reason and priority |
| --- | --- |
| Complete prefix in one physical batch; prefix and answer calls separate | Bidirectional prefix states need the whole prefix at every recurrent invocation. Ordinary causal chunking is wrong. Mixed phases need a different mask/scheduler design. Keep for the minimal implementation. |
| No editing/shifting a retained prefix or creating answer holes | Retained hidden states depend on the removed/changed tokens. Recompute a complete prefix instead. This is a correctness rule, not a feature omission. Answer suffix trimming remains supported. |
| Full-sequence forks only; one sequence ID per input token | Full forks preserve every dependency and work with existing cross-stream copies. Fork then trim an answer suffix to branch earlier. Partial-prefix forks are invalid; shared ownership in input batches needs additional admission/phase rules. |
| Fixed adapters per context while KV is live | KV was computed under those weights. Changing them requires clearing/recomputing all dependent sequences. Activated LoRA needs bidirectional activation semantics. Control vectors are a lower-priority integration/qualification gap, not fundamentally incompatible. |
| Complete host snapshots only | Partial-memory flags concern unsupported recurrent/SWA caches. On-device readers currently commit tensor copies in their destructor; safe restore failures need a separate audit. Host persistence already provides durable save/restore. This is an implementation limit, not a PrefixLM property. |
| No server prompt-cache/idle-slot restore or dynamic per-request adapters | Existing cache reuse can trim/replay the last prefix token; idle PrefixLM slots release KV. Proper server resumption needs phase/logit/sampler bookkeeping. Library persistence works. Startup LoRA works; mixed per-request weights need context/sequence scheduling. These are the most useful remaining integration extensions when applications need them. |
| Decoder token-input KV models only; no encoder, hybrid/recurrent, SWA, diffusion, multi-position or embedding-output mode | Those paths have different memory, masks or outputs. They require architecture-specific validation and sometimes algorithms; decoder PrefixLM support does not establish it. |
| No speculative or multimodal scheduling | Existing callers have no adapted prefix-boundary lifecycle for these combinations. Keep out of the minimal PR; multimodal was explicitly deprioritized. |
| Serialize operations on each context; shared forks count toward logical capacity | Context thread-safety follows the existing API. Conservative capacity accounting enforces requested limits even when physical cells are shared. Optimizing shared-capacity accounting is optional. |

Persistence also retains ordinary runtime-state compatibility constraints:
matching model weights, compatible KV layout/types and matching fixed adapters.
It is not a cross-version interchange format or a saved chat transcript.

## Before a production PR

1. Run Linux CPU release and ASan/UBSan on this version, and repeat the controlled
   causal/bidirectional performance check. Mac timing drift from prior runs is
   not clearance for performance regression. Reminder: do this **before
   packaging and review**, as requested.
2. Resolve the public API/state-format contract and numerical tolerance policy
   in review. Keep the known small fused-Metal causal-control miss visible;
   do not relax thresholds just to report a clean matrix.
3. After Linux evidence, rebase/trim/package and conduct human review, keeping
   unrelated ggml/tokenizer fixes separate or explicit prerequisites. No package
   regeneration, commit, push or PR submission was performed here.

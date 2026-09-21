# PrefixLM multi-sequence implementation

Historical multi-sequence qualification snapshot. Cross-sequence copy, persistence and
fixed LoRA restrictions below are superseded by [STATE.md](STATE.md) (2026-09-18).

Date: 2026-09-17. Working-tree change against llama.cpp base
`c9a5eeeb34ab8f794ea7510ca52d25da13728a5b`.

## Behavior

Prefix boundaries and next-answer positions now belong to sequence IDs rather
than the context. A complete-prefix call replaces only its supplied sequences;
other sequences retain KV and phase. Prefix calls can include multiple complete
prefixes in one physical batch. Answer calls can interleave causal tokens from
several sequences, with positions validated or inferred independently.

The implementation reuses existing masks, KV streams and sequence operations.
It adds no attention kernel or public entry point. Unified KV supports sparse
IDs and a shared requested capacity, with `n_seq_max` limiting live sequences.
Separate KV streams enforce the requested capacity per sequence before padding.

Invalid admission preserves all sequences. Execution failure or abort clears
every sequence participating in that call, preserving unrelated sequences.
Admission allocation exceptions are caught before mutation. As with ordinary
llama.cpp batching, callers serialize operations on a context and retain any
logits needed after a subsequent call.

Suffix removal and wildcard removal keep phase metadata consistent with KV.
Wildcard validation completes before mutation. `seq_keep` follows existing
backend stream behavior: unified KV removes other sequences, whereas separate
KV streams retain unrelated streams. Metadata follows the KV actually retained.
Cross-sequence copies and shared token ownership remain unsupported.

The server supports multiple active slots. Pending prefixes get a separate
prefill batch; answers can then share causal batches. Cancellation removes only
the cancelled slot. Finished/idle PrefixLM slots release KV because prompt reuse
is disabled; they must not consume shared capacity. Decode errors release only participating slots and do not
retry by splitting a prefix. A focused overlap test caught and fixed an empty
answer slot incorrectly claiming a pending-prefix batch.

## Validation

Results and source hashes are recorded in `sequence-results.json`; raw evidence
is under `logs/mimir-sequences/`. No performance conclusion is drawn from these
runs, which overlapped builds and other workstation activity.

- Direct HRM and Llama tests pass 826 checks each (1,652 total), covering
  CPU/Metal, flash on/off, unified/separate KV,
  interleaved answers, batched prefixes, local reset and abort, rollback,
  wildcard validation, sparse IDs, implicit positions and requested capacity.
- Independent HF full-forward reference adds another distinct prefix/answer and
  an interleaving/reset/rollback scenario. All new reference steps pass; fused
  Metal retains the unchanged causal-control tolerance miss.
- Stock Q8 Mimir server tests use the checkpoint chat template and HF token
  references. One slot passes 24 checks. Two slots pass 33 checks with separate
  KV and 33 with unified KV, including actual overlapping requests, new prefill
  during an answer, and cancellation preserving the other answer's tokens.
- Release and CPU UBSan integration suites pass 7/7 each; UBSan includes
  413 direct engine checks per architecture (826 total).
  Linux release and ASan/UBSan execution remain deferred.

The initial two-slot server rerun lacked `--slot-save-path`: the endpoint
returned 501 before exercising the PrefixLM save/restore guard. The corrected
runs enable the endpoint and verify its rejection. No rejection expectation was
weakened.

## Reproduction

Use the current working tree, not the older packaged patch files. Existing
build prerequisites are in `ENGINE.md` and the independent reference procedure
is in `llama.cpp/docs/development/prefix-lm.md`.

```sh
cmake --build logs/mimir-engine/build --target test-llama-archs llama-server -j 8
logs/mimir-engine/build/bin/test-llama-archs --prefix-lm -a hrm_text -s 42
logs/mimir-engine/build/bin/test-llama-archs --prefix-lm -a llama -s 42
PYTHONPATH=llama.cpp/gguf-py logs/prefixlm-comparison/venv/bin/python \
  llama.cpp/scripts/prefix-lm-reference.py --output logs/mimir-sequences/reference
logs/mimir-engine/build/bin/test-llama-archs \
  --prefix-reference logs/mimir-sequences/reference/reference.json
```

For the two-slot server, start a local server in another terminal (choose an
unused port), then run the harness. Repeat with `--kv-unified` on the server.
The harness also accepts the single-slot case without `--parallel`.

```sh
logs/mimir-engine/build/bin/llama-server \
  -m logs/mimir-review/mimir-q8_0.gguf -ngl 999 -c 512 -b 224 -ub 224 \
  -np 2 -fa on --host 127.0.0.1 --port 18181 \
  --slot-save-path logs/mimir-sequences
logs/prefixlm-comparison/venv/bin/python native/mimir/tests/server_e2e.py \
  --parallel --url http://127.0.0.1:18181 \
  --output logs/mimir-sequences/server-separate.json
```

## Production PR priorities

1. Run Linux CPU release and ASan/UBSan on this working-tree version. Repeat the
   bounded causal/bidirectional performance control there: the prior Mac result
   did not distinguish the apparent causal slowdown from baseline drift.
2. Settle and review the public contract: explicit complete-prefix admission,
   per-sequence failure semantics, capacity, and unsupported combinations.
   Persistence, cross-sequence copy/forking and fixed adapters need explicit
   scope decisions; they are deferred features, not intrinsic PrefixLM limits.
3. Make the essential numerical/server evidence reproducible within the upstream
   checkout and its CI. Document backend-aware numerical tolerances; preserve
   the BF16/Q8/Q4 drift results instead of claiming all strict thresholds pass.
4. After Linux testing, rebase/trim/package and conduct human review. Separate
   unrelated ggml/tokenizer fixes or document them as prerequisites. Upstream
   API/scope agreement and maintainer feedback remain necessary.

Multimodal, speculation, shifted/edited prefixes and additional model memory
architectures can remain outside the initial documented support contract.
Full-prefix physical batching remains an algorithmic constraint of this design.

**Reminder before packaging/review:** complete Linux qualification first.
Existing `native/mimir/patches/` files intentionally remain the earlier snapshot.

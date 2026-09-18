# PrefixLM release-candidate patch package

Base: `c9a5eeeb34ab8f794ea7510ca52d25da13728a5b`.
Combined runtime: `8f4f4ef8f3139d7d262763936f1f34e48ad46d9c`.
Final Linux execution of the sanitizer policy runner and human review are pending.
This package does not claim upstream approval or a successful GitHub CI run.

Apply the numbered patches in order from a clean llama.cpp checkout at the base:

1. `01-ggml.patch`: graph-size undefined-behavior fix.
2. `02-text-codec.patch`: Mimir tokenizer, byte fallback and Unicode template support.
3. `03-prefixlm.patch`: main PrefixLM feature, including the Linux GCC include and
   causal-mask performance fix, exact-prefix caching and ordinary custom-state/live-fork parity.
4. `04-generation-persistence.patch`: independent built-in sampler persistence and
   server continuation for ordinary causal decoding and PrefixLM.

For main-only qualification, stop after 03. For standalone persistence, apply 01,
02 and `generation-persistence-standalone.patch`; omit 03 and 04. Never apply both
persistence variants. Historical drafts and the separate Linux fix must not also
be applied to these candidates: the fix is already folded into 03.

The split changes patch organization only, not runtime source or commit history.
`manifest.json` records hashes and Git trees after each application. From the
parent repository, verify or deliberately regenerate the package with:

```bash
python3 native/mimir/tools/package_patches.py
python3 native/mimir/tools/package_patches.py --write
```

Verification uses a temporary Git index, applies each patch with whitespace checks,
compares the combined tree to the Linux-qualified commit, and checks that the
main-only header has no sampler snapshot API while standalone persistence has no
PrefixLM API. It does not modify the checkout or real index. The pinned commit
objects must exist locally (`git submodule update --init llama.cpp`).

See [final qualification](../../FINAL-QUALIFICATION.md) and the
[Linux report](../../LINUX-TESTING-REPORT.md) for evidence, accepted limitations and
the final bounded checks. The latter include matching the candidate's source hashes,
CPU ASan/UBSan and graph-enabled CUDA memcheck; no new broad feature work is required.

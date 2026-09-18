# Two independent feature patches (review drafts)

Base: `c9a5eeeb34ab8f794ea7510ca52d25da13728a5b`.
These drafts establish the requested scope split. Linux qualification and final
packaging/review are still pending. Older patches one directory above remain
historical; do not mix their feature implementations with these drafts.

| Logical patch | Contents |
| --- | --- |
| `prefixlm-main.patch` | Attention mode, complete-prefix and mixed decode APIs, sequence ownership/copies, KV/phase/logit persistence, fixed adapters/control vectors, exact complete-prefix caching, ordinary live parent/child forks and custom-state parity. |
| `generation-persistence.patch` | Built-in/common sampler snapshots, grammar/reasoning/backend state, server retained generations including pending token and OpenAI parser continuation. Applies after the main patch. |
| `generation-persistence-standalone.patch` | Alternate application of the same persistence feature to the base plus prerequisites, without PrefixLM. Do not apply both persistence variants. |

Independent prerequisites are `../ggml-graph-size.patch` and this directory's
refreshed `text-codec.patch`. The latter includes the current Mimir
`spm-bpe-mistral` tokenizer, byte fallback and Jinja Unicode fixes. The old codec
patch does not suffice to load the current Q8 fixture. Neither prerequisite is
part of the logical PrefixLM/persistence feature split.

Apply from the root of a clean llama.cpp checkout at the base above. With
`DRAFT` set to this directory's absolute path:

```bash
git apply "$DRAFT/../ggml-graph-size.patch"
git apply "$DRAFT/text-codec.patch"
git apply "$DRAFT/prefixlm-main.patch"
git apply "$DRAFT/generation-persistence.patch"
```

For PrefixLM alone omit the last command. For persistence alone replace the
last two commands with:

```bash
git apply "$DRAFT/generation-persistence-standalone.patch"
```

The standalone variant removes the adjacent PrefixLM context in shared files;
it contains no PrefixLM API dependency. Tests were built and run in isolated
main-only and persistence-only source trees. Applying main plus persistence
reconstructs every current llama.cpp source change byte for byte. Both application
paths were independently apply-checked and compared against their source trees.
[manifest.json](manifest.json) records patch hashes and reconstruction results.

See [DECODER-RESUMPTION.md](../../DECODER-RESUMPTION.md) for bounded results and
[the Linux hand-off](../../../../linux-testing.md) for the remaining qualification.

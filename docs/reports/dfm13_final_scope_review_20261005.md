# DFM13 Final Scope Review

## Handoff to Parent and Tesla

The single sampler is `scripts.sample_dfm13_final` (Tesla, PID477498 at review).
Do not start another sampler. Reconciler PID482672 is detached; launch, progress,
full inherited index validation and staged enumeration are under
`data/dfm13/specification-reconciliation-20261005-v1/`.

It automatically writes the final inventory and sampler contracts:

- `data/dfm13/all-source-finalization-20261004-v1/reconciliation.json`
- `data/dfm13/all-source-finalization-20261004-v1/sampling-reconciliation.json`

Release requires the exact final successor root, matching composition, actual
specification dispositions, publication evidence and inherited coverage. No
canonical assembly or live training input was changed. The current predecessor
has468ready sources and4explicit holds; it is not the final scope. Missing
finished components remain pending until Tesla's successor includes them.

## Scope and Replacements

Use DFM11 plus latest381 DFM12 packages plus final approved DFM13 additions.
Never append381 to historical sampledDFM12: that duplicates80unchanged packages
and retains nine superseded XL identities. The approved repeat mapping is XL
identity10, MATH5, others1. The separate21XXL-wide persona sources remain excluded.
One epoch is explicitly chosen; ten is only the sampler default.

DaLA v2 is incremental. Producer prior indices cover modern inherited releases;
the finalizer excludes exact prior clean controls and noisy pairs. The Danish
index also pins recovered historical TV2R correction raw files. DFM11's six TV2R
arrays are Danish instruction variants, not Italian, and preserve the documented
all-split historical inclusion (thus contaminated as evaluation). This is not a
claim of whole-corpus semantic deduplication. Detailed index files/revisions and
six source-map entries are included in the staged machine-readable report.

The12old producer HF repos are reused at verified pinned revisions under explicit
Option1, not uploaded again. New grouped34language DaLA publications bind exact
integration pins and files; local packaging differences are not new training rows.
Four Baltic QA/P3 source-fidelity holds, Fars summaries and user-excluded RepoChat
and both search datasets remain excluded/held. Raw OpenHermes remains excluded.

## Sampler Safety

Full inherited index scan:381sources,1325parts,48949524rows, maximum4096tokens,
zero response lengths below2 and zero bounds/context violations. Token payload
arrays were not rehashed/scanned by this review. Tesla's sampler separately
requires all new and inherited weighted row/token totals to match exactly and
fully scans the sampled output.

The established command inside Tesla's wrapper is:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python data_io/sample_tokenized.py \
  tokenized_path=<FINAL_COMPOSITION>/tokenized_additions \
  output_path=<FRESH_SAMPLED_ADDITIONS> \
  prefix_config_path=<SEALED_PREFIX_YAML> epochs=1 concat_workers=1 \
  skip_unmatched=true default_long_context=drop context_size=4097
```

The wrapper converts the sealed JSON repeat mapping to YAML, rejects missing or
ambiguous prefixes, verifies no dropped targets, and combines with DFM11 epoch0.
Do not run the snippet concurrently; the existing wrapper owns execution.

Six CPU tests pass. No GPU work, training change, assembly write or sampler launch
was performed by this reviewer.

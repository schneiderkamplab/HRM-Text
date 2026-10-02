# DFM12 component preparation

CPU-only preparation campaigns: `python -m dfm12.cpu_prepare` downloads
DynaWord sources and converts/pre-tokenizes the six ready instruction sources;
`python -m dfm12.cpu_transforms` recovers the Danish accepted baseline and
prepares selected multilingual transformation candidates after downloads.
Instruction tokenization here is explicitly `tokenized_unaudited`, not an
accepted training component. Both commands hold single-writer locks and never
launch GPUs or perform final sampling. Logs are normally redirected into
`data/dfm12/cpu-{preparation,transforms}.log`.

This package prepares independent additions. **There is deliberately no final
sampling command, no inherited-corpus rebuild, and no scheduler integration.**
Other threads can supply further DaLA-like and other components before the
eventual DFM12 assembly.

All commands run from the repository root, in the existing data-preparation
environment. Use `uv pip install ijson` if an upstream JSON-array source needs
the optional streaming reader. No GPU work occurs unless `work` is explicitly
given a server endpoint. No servers, training processes or evaluation jobs are
started or stopped by this package.

## Source inventory and conversion

```bash
python -m dfm12 inventory
python -m dfm12 status
python -m dfm12 download ultrachat-nl
python -m dfm12 convert ultrachat-nl --limit 200
python -m dfm12 audit-jobs ultrachat-nl-pilot --limit 100
```

The source registry is `config.yaml`. Resolution pins revisions and exact files
in `data/dfm12/sources.lock.json`. The six initially downloadable components are
English/Dutch DaLA, Dutch UltraChat, and Dutch/Polish/Swedish translated Dolci.
Review-held sources cannot be downloaded by the CLI until explicitly approved:

```bash
python -m dfm12 approve SOURCE 'Documented rights, quality and overlap review' \
  --file data/SELECTED/train.parquet
python -m dfm12 download SOURCE
python -m dfm12 convert SOURCE
```

Approval selects literal paths from the pinned inventory, not broad globs.
Re-review when revisions change. Keep validation/test splits out. Norwegian
NorQuAD and FLEURS components are not selected. Generic `nor` is **not** treated
as Bokmal. Unknown or mixed variant labels are rejected rather than guessed.

DaLA keeps explicit language instructions and canonical yes/no labels. Tools
and embedded legacy template tokens are quarantined, not silently flattened.
Conversion keeps all dialogue turns and drops overlength conversations rather
than shortening answers. Rendering uses the raw tokenizer JSON and template
from `data/sampled_dfm11/metadata.json`; it does not enable Mistral regex fixes.
`--tokenizer-metadata PATH` can select an equivalent relocated tokenizer.

The Danish composite route requires `--exclude-index PATH`. Build this index
from inherited normalized chats with `fingerprint-index --input FILE ...`.
It is exact normalized-message deduplication, **not semantic decontamination**.
Source-level benchmark reviews remain necessary, especially for Aya/FLAN-derived
data. Do not approve a whole collection merely because it has a train split.

## Identity and pilot

`identity_facts.yaml` separates historical v1 claims from the owner-specified
new XL/full-backprop profile. The v1 paper says BP5; the new profile must not
rewrite that history. Architecture facts for XL must not be taught as facts
about L/XXL. Select `--profile generic` for family-only identity supervision.

```bash
# 20 requests per language: 180 pilot conversations, no GPU execution yet.
python -m dfm12 identity-jobs
python -m dfm12 work generate --endpoint http://localhost:8400/v1 --concurrency 32
python -m dfm12 identity-audits
python -m dfm12 work audit --endpoint http://localhost:8400/v1 --concurrency 32
```

Use `google/gemma-4-26B-A4B-it`, with the server served-model-name matching that
ID. Repeat `--endpoint` for multiple independently provisioned servers. Client
concurrency is per endpoint; start at 32 and measure KV cache/queueing before
raising it. An optional API key is read from `DFM12_API_KEY`, never persisted.
Generation and audit have independent prompts; both disable thinking output.

Review the pilot for every language, especially NB/NN, Icelandic and Faroese.
Only then create `data/dfm12/pilot-approval.json` with `approved: true`, `model`,
the nine `languages` codes, and substantive `evidence`. This is an explicit
review record, not an automatic consequence of a judge giving high scores.
Bulk requests/audits require it. After approval:

```bash
python -m dfm12 identity-jobs --count 1230 --start 20
```

This gives 1,250 candidates per language for a target of 1,000 accepted unique
conversations. Add further slots if rejection leaves a shortfall. Never repeat
accepted conversations to disguise a shortage. Every candidate has a stable
ID, fact-registry hash, profile and separate audit context.

The owner-selected DFM12 identity sampling repeat is **10** (`identity_repeat`
in `config.yaml`). This weights audited unique conversations at final sampling;
it does not duplicate exports, fill generation shortfalls, or alter audit counts.
Accepted identity component manifests carry this repeat. Final corpus sampling
is still deferred.

## Transformation and translation preparation

```bash
python -m dfm12 baselines /path/to/full/inherited/accepted-transform-root
python -m dfm12 transformations dynaword-nl
python -m dfm12 audit-jobs dynaword-nl --limit 100
python -m dfm12 opus-inventory
python -m dfm12 opus-pair da-fo
python -m dfm12 translation-budget /path/to/dfm11-sampler-report.log
```

The accepted root contains `danish-dynaword-{denoising,prefix-continuation,
span-filling,paragraph-reordering}` directories. Use the **expanded inherited
accepted corpus**, not stale HF card counts or repeated sampled rows. Unique
conversation counts and file hashes establish the 25%-per-task targets.

DynaWord sampling scans all approved files, takes deterministic random windows,
and stratifies candidates across files. It does not take the first rows from
each file. Targets are accepted examples; a 1.5x candidate allowance is a first
pass, not a guarantee. Shortfalls and unclear language labels remain visible.

OPUS covers five English pairs and 28 pairs among the eight non-English
languages. Both directions are audited together and exported together.
Tatoeba's release license is checked against the archive README; other corpus
versions remain on review hold. To approve another, record its exact inventory
entry's `status: approved`, canonical `license`, and `license_evidence` after
review, while no OPUS preparation command is running. Only public-domain,
CC0, CC-BY and CC-BY-SA are accepted. Archives/README/LICENSE and attribution
references are retained. No pivoting, synthetic fill or aggressive repetition.

Future per-pair caps are measured from repaired OPUS **sampled token** coverage:
one quarter for new English pairs and one sixteenth for non-English pairs.
These are recorded budgets, not caps applied to the component exports yet.

## Accepted exports and resumability

For the separately authorized full-corpus audit, build local HF packages for
finished components (no upload):

```bash
python -m dfm12.export_finished \
  --run data/dfm12/full-audit-20260924-v1 \
  --crossscreen data/dfm12/scandi-cross-component-20260924-v1/audit-manifest.json \
  --output exports_dfm12 \
  --authorize-local-accepted-export
```

The exporter requires completed source preparation and terminal audit jobs.
Only valid kept decisions passing screening enter `data/train-*.jsonl.gz`.
Failed requests remain unresolved exclusions. OPUS pairs expand into two
directional chats. Each package includes attribution, audit metadata, checksums,
a dataset card, and a standalone `validate_dataset.py`. Empty accepted subsets
are marked not upload-ready. Existing package directories are never overwritten.
Append `--incremental` on subsequent builds: existing package checksums and
source pins are verified, only newly finished components are frozen, and the
root inventory is extended without replacing prior packages.
**Do not upload the root `exports_dfm12/metadata/` directory:** it contains local
snapshots including excluded records. Upload only individual validated nonempty
package directories when separately authorized.

```bash
python -m dfm12 export identity-xl-full-bp
python -m dfm12 tokenize identity-xl-full-bp --workers 16
```

Exports live in `data/dfm12/accepted/COMPONENT/{data,metadata}` and can later be
packaged for HF. Only explicit accepted audits enter `data/`. Attribution,
judge scores and source IDs stay in `metadata/`. Existing exports cannot be
overwritten accidentally. Read manifest counts and shortfalls before inclusion;
an export is a component snapshot, not certification that all DFM12 is ready.

Jobs live in SQLite with transactional leases. Multiple clients can share the
queue without claiming the same job. A lost client lease expires after 15
minutes; stale owners cannot overwrite newer results. Requests have four total
attempts with persisted errors. Re-running work resumes pending jobs; exhausted
failures remain visible and are never accepted automatically.

CPU candidate files use single-writer locks and atomic replacements. Do not
reprepare a component with changed settings while its audit is running; use a
separate work root for a revised component. Tokenization is component-only,
uses at most 16 workers, and never touches existing sampled DFM11 indices.

```bash
python -m pytest tests/test_dfm12.py -q
```

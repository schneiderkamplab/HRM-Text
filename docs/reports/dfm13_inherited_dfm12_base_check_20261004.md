# Independent DFM13 Inherited-Base Check

CPU/read-only, 2026-10-04. Training and assembly inputs unchanged.

## Result

The latest completed assembly inspected,
`data/dfm13/verified-finished-additions-dala9-20261004-v1/assembly.json`,
explicitly references `data/sampled_dfm12`, not the active XL no-identity corpus.
The referenced base is available and passes targeted integrity checks. This is
not certification that all later DFM12 packages are already included.

- Ten epochs, each252179463 rows; all40index references and token-file stat
  signatures match the assembly. Build/merge receipts agree.1024deterministic
  sampled rows per epoch pass pointer bounds and4097length checks.
-227144019403stored int32tokens; build receipt average106799766039tokens/epoch.
  DFM11 base/addition token lengths and six64-token copy probes agree.
- Native Jinja contract:4096student positions (`max_seq_len=4097`), vocabulary
  262144, thinking disabled. Tokenizer/template hashes match assembly pins.
- All89DFM12 source manifests match inventory hashes;387staged input paths
  resolve, with no broken dependency found.
- Recovered DFM11 source-map hash matches its transfer receipt:16023tasks,
  223595843215tokens.20repaired EN/DA OpenHermes shards, zero raw
  `openhermes_2_5`/`teknium` task entries. All60stored OpenHermes token probes
  match the inherited backing array. Raw OpenHermes remains excluded; repaired
  OpenHermes is intentional and is not equivalent to raw inclusion.

## Coverage Omissions to Reconcile

The inherited base's build has89DFM12 source names, whereas the later
`training-build-completed-campaign-20260929/sources.json` has381. There are
292additional names and nine same-name identity replacements (da,en,fo,is,nb,
nl,nn,pl,sv) with different manifest hashes. The inspected assembly has no
`dfm12-*`-named ready additions. Thus do not describe this base reference as
automatically inheriting all subsequently finished DFM12 packages or the newer
21-language identity replacement set. Parent must reconcile these with explicit
additions/replacement policy before claiming complete coverage; no merge,
resampling, tokenization or training change was made here.

The old `data/tokenized_dfm11` source tree is absent locally. It is not needed
to read the self-contained sampled base; provenance is supplied by the pinned
recovered source map. Rebuilding from original per-source tokenized files would
need that tree restored. Arrays were not fully scanned or rehashed: checks used
existing receipts/stat signatures, headers and bounded probes.

Machine-readable evidence and exact292/9name lists:
`docs/reports/dfm13_inherited_dfm12_base_check_20261004.json`.

---
language:
- da
task_categories:
- text-generation
---
# Historical DFM2 deterministic transformations

Exact historical reconstruction, not a newer filtered/expanded release. All generated rows and sampled token/index arrays were compared to the preserved corpus.

Original task-relative paths and row order are preserved under `data/`. The manifest contains SHA-256 checksums; provenance includes source locks, the generator and sampling recipe. Regeneration uses `--max-chars 3000 --historical-full-reconstruction` and the seed in the manifest. No model generation or new audit is required.

Upstream source licenses and attribution requirements continue to apply; this package does not grant a blanket replacement license. See source repository identifiers/revisions in provenance.

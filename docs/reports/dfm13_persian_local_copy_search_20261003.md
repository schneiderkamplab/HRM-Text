# Bounded local Matina/TLPC search

Date: 2026-10-03. CPU/read-only inspection of source locations; no network
requests, credential inspection, downloads, process actions or source changes.

## Result

No verified local payload was found within the inspected locations. This does
not establish absence from every filesystem or backup. The agreed bounded
preparation remains blocked: **0/11 Matina and 0/64 TLPC selected files present**
at their frozen local paths. No new authorization request is needed or made.

Frozen plan: `data/dfm13/wave4/persian-local-v1/plan.json`, SHA256
`b0f005861fc760bd032223803e43f07cccdbe44893f92dca5dfd3ee4965727f4`.
Selected compressed totals are 1,015,840,100 bytes and 135,813,056 bytes,
respectively. Both `data/dfm13/wave4/downloads/` repository directories contain
cards/download receipts/cache metadata, not the selected payloads.

## Inspection bounds

- Searched DaLA config, source-loader code, wiki, documentation and scripts for
  Matina/TLPC/Targoman references and cache/source-root settings.
- Name searches to depth 3 covered `/work/mimir/DaLA/la_output/cache`,
  `/work/mimir/DaLA/la_output/resources`, HRM `data/downloads/datasets`, and
  `/home/ucloud/.cache/huggingface/hub`.
- Name searches to depth 4 covered HRM `data/dfm11_source_cache`, `data/dfm12`,
  `data/converted_sources`, `data/converted_dfm11`, and
  `/work/mimir/.home/.cache`. No matching source names were found.
- Checked all 75 exact selected paths directly, independently of name searches.
- Checked direct `blobs/<sha256>` paths for all 74 non-null selected LFS hashes
  across 1,344 dataset-cache directory entries in the two existing HF hubs:
  `/home/ucloud/.cache/huggingface/hub` and
  `/work/mimir/.home/.cache/huggingface/hub`. Zero matches; neither hub contains
  a Matina/TLPC/Targoman-named dataset repository. Directory entries may alias
  storage; this is not a count of distinct datasets. One selected file lacks
  an LFS hash in the plan, so this hash check does not cover that file.
- Cache-path environment variables were unset; no secrets were inspected.
  `/work/mimir/.cache/huggingface/hub` and `/data` do not exist.

## DaLA provenance

`config/european/fa-sources.json` and
`la_output/resources/wave4/persian-admission-v3/fa/reference-fa-sources.json`
identify UD Persian-Seraji, not Matina/TLPC. The referenced local
`la_output/resources/european/fa/fa_seraji-ud-train.conllu` exists and its SHA256
matches the manifest:
`fce94c19557f6cdc188068fab4ff36783a03816d161fa596cfa621bb83e32e7b`.
Its pinned upstream revision is `f993cdd1189448b71f6dfa4fa537618ea46df10a`.
Other visible Persian resource names include Wikipedia, UniMorph and language
rules. These are not substitutes for the approved Matina/TLPC selections.

No arbitrary archive-content scan or exhaustive backup/worktree search was
performed. Any later-discovered copy still requires origin verification and
the frozen preparation's size/hash checks before admission. Existing blocked
receipts and prepared/queued row counts were not modified.

# Matina/TLPC authenticated access recheck

CPU/network only; no serving processes, live queues or existing receipts changed.
The same cached HF authentication that successfully downloaded31B was used with
`get_hf_file_metadata(..., token=True)` on one real payload per source. Metadata
listing succeeded, but both payloads returned `GatedRepoError`, HTTP403. No
payload retries, alternate credentials, gate acceptance or gate bypass attempted.
No credential/header values were printed or saved.

| Configured repository | Resolved revision | Authenticated blocked payload |
| --- | --- | --- |
| MatinaAI/matina_persian_text_corpus | 5a782d5a46f7646923644343bf8cfeac5f9c589c | baznashr.zip |
| Targoman/TLPC | e2fea1d2c4c0828a218c79d6806fe98f821ad8ce | aa/2024-03.jsonl.gz |

Both API records report manual gates. Public file listings do not grant content
access. Project approval is preserved, but authenticated access approval remains
unavailable to the current credential; model approval is repository-specific.
The403 alone does not establish whether a pending request, account permission,
or fine-grained token permission needs changing. No identity details collected.

## Actual layout and missing files

Configuration is `dfm12/wave4_cpu.py:SOURCES`; the downloader resolves the current
commit dynamically, rather than reading a dedicated source lock. Historical
blocked receipts dropped revision metadata; this recheck records exact revisions
in separate artifacts, preserving history.

Neither dataset card declares HF `configs` or `dataset_info` split definitions.
These are source archives/site-month partitions, not verified train/test splits.
Do not infer a train split from all repository files.

* Matina:19 files,109,331,313,075 bytes including metadata;17 content files
  (sevenZIP archives and tenJSONL.GZ). All17 missing locally. Only README and
  download/cache bookkeeping exist locally.
* TLPC:62,595 files,98,618,184,311 bytes including metadata;60,785JSONL.GZ,
  208JSONL,804CSV category files,796JSON statistics files. All62,593 non-card
  files missing locally. Site/month organization, e.g. `aa/2024-03.jsonl.gz`.

Complete path/size/upstream-LFS-hash/local-presence inventories and sanitized
blocker receipts: `data/dfm13/wave4/persian-access-recheck-20261003/`.
The receipt records the first authenticated probe from this turn; subsequent
inventory collection used metadata APIs only, not repeated gated payload calls.

## Legitimate official alternatives

[Matina's official preprocessing repository](https://github.com/FTaheriN/Matina-Text-Preprocessing)
links its dataset back to the same gated HF repository. It supplies processing
code, not a verified alternate corpus download. The
[official paper](https://aclanthology.org/2025.naacl-long.462/) points to that code.
No official ungated equivalent or alternate split was found. Matina includes
processed CulturaX/MADLAD/Wikipedia material; original component corpora are not
equivalent copies and must not silently substitute for this approved source.

[TLPC's official card](https://huggingface.co/datasets/Targoman/TLPC) links
`https://oss.targoman.ir/TLPC/` and its
[scraper implementation](https://github.com/Targoman/PersianWebScraper).
The official project URL was inaccessible through the web tool and a bounded
local HTTPS request ended in `ConnectionError` (no HTTP status received).
The scraper is code, not an alternate release. No verified official ungated
payload URL found. Third-party mirrors were not used to evade the gate.

## Resume hazards and next action

The existing snapshot allowlist omits ZIP archives. After access approval it
would silently omit `baznashr.zip`, `cultralx.zip`, `madlad.zip`,
`other_crawls.zip`, `papers_v4.zip`, `social.zip`, `ut_papers.zip` yet could mark
the source downloaded. A source-specific explicit inventory/completeness check
and safe archive handling are required before successful readiness publication.
Do not unpickle archive members or assume arbitrary archive schema is safe.

Current `wave4_transforms`/`wave4_seeds` read Wikipedia sources only; approval and
snapshot download alone do not connect either Persian corpus to preparation.
Once access changes, inspect actual documents, preserve TLPC paragraph/type and
formal/informal metadata, add bounded source-specific adaptation, deduplicate
against inherited/source overlap, and preserve original licenses. Matina remains
CC-BY-NC-ND-4.0 and TLPC CC-BY-NC-SA-4.0 under existing owner approval.

No download worker was launched because both payload gates remain closed. No
background retry watcher is left running. No preparation/admission claims made.

# Baltic Europarl Scoped Reuse Resolution

**Completed:** CPU process3488968 exited successfully. All six successor
packets verify and report `upload_ready=true`:90,000 unchanged conversations,
including30,528 source-bound Europarl excerpts. Terminal `handoff.json` is present.
No external permission wait remains under the scoped basis below. Tesla may
perform the publication/remote-verification stage; this worker uploaded nothing.

## Evidence and Dated Supersession

2026-10-04: re-read the captured primary Parliament legal notice and checked
the current indexed primary text, OPUS attribution/license files and the corpus
producer page. The notice provides attributed reuse, including commercial
dissemination, and an additional source-link condition for excerpts. It does
not require the project to fetch every official sitting page successfully.
The exact wording allows a complete-item link OR the webpage used as source.
Requiring a separately verified official URL for each sitting was our additional
gate, not an express condition in that notice.

Primary references:
- [European Parliament legal notice](https://www.europarl.europa.eu/legal-notice/en).
- [Europarl corpus producer](https://www.statmt.org/europarl/).
- [OPUS Europarl distribution](https://opus.nlpl.eu/datasets/Europarl).

The producer's statement that it knows of no restrictions is supporting corpus
context, NOT a replacement permission grant. OPUS LICENSE defers to original
source terms; no CC/public-domain designation is invented. The captured Parliament
notice remains the scoped reuse basis, with source-specific exceptions retained.
This is an operational publication assessment, not legal certification.

## Essential Versus Optional Evidence

Essential and now supplied: unchanged source excerpts; complete sitting identity;
actual source distribution/page URLs; source attribution and original corpus
citations; captured terms; clear distinction between generated text and official
Parliament statements. Every Europarl source excerpt matches the complete pinned
sitting text after whitespace normalization:12,119 LT +18,409 LV =30,528 rows,
zero mismatches. Archive SHA256s are checked and original XML member paths are
mapped to each sitting. Generated answers are separately labelled model output,
not official translations or Parliament-endorsed text.

Optional extra gate removed: a successful live HTTP fetch of each individual
official sitting page. No guessed link is relabelled verified. Archive links
and corpus source pages are actual provenance rather than invented official
references. The prior altered-denoising/reordering question does not establish
a blanket prohibition for these unchanged excerpt plus separately generated
QA/summary/chat packages. The scoped basis is the notice's reuse/use permission,
not an assertion of unlimited adaptation rights. Existing item-specific terms
and third-party rights still apply; no separate restriction was found in the
pinned distribution evidence. This does not resolve every historical Europarl
task or retroactively release held corrupted-text transformation packages.

## External Successor Handoff

Six-package successor root:
`exports_dfm13/baltic-source-attribution-20261004-v2`.
Its `handoff.json` is the completion/readiness receipt; without that receipt a
partially populated directory is not complete. Each child has
`publication-manifest.json` binding all attachments and unchanged train bytes.
Publish only after checking that receipt and manifests. Tesla owns all uploads.

Two OpenHermes packages remain ready at v1; do not duplicate/reupload them if
Tesla has already published them. Four math/tool packages are outside this task.
The earlier six conditional flags in v1 remain immutable historical evidence,
superseded only by this scoped successor decision. No sealed release payload,
token arrays, integration pins, registry entries or previous manifests are edited.

Implementation: `scripts/resolve_baltic_europarl_attribution.py`.
Tests:11 passed across the original and successor attribution modules.
No network access bypass, GPU calls, training changes or uploads. Bounded primary
web checks did not contact a rights holder. No external permission request is
required by this scoped operational assessment; remaining work is CPU verification
then Tesla's publication/remote byte verification, not a fabricated external wait.

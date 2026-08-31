---
type: Dataset Survey
title: Danish Corpus Expansion Candidates
description: Andersen and DSL-related sources, the post-1.2.16 DynaWord delta, and a license-first Tidsskrift.dk expansion design.
tags: [danish, datasets, andersen, dynaword, tidsskrift, licensing]
status: stable
last_updated: 2026-08-29
confidence: high
sources:
  - id: dynaword-current
    resource: https://huggingface.co/datasets/danish-foundation-models/danish-dynaword
    title: Danish DynaWord
  - id: tidsskrift-oai
    resource: https://tidsskrift.dk/index/oai?verb=Identify
    title: Tidsskrift.dk OAI-PMH endpoint
  - id: hca-github
    resource: https://github.com/ogierMontanus
    title: Holger Berg GitHub repositories
  - id: dsl-github
    resource: https://github.com/dsldk
    title: Society for Danish Language and Literature GitHub organization
---
# Danish Corpus Expansion Candidates

Implementation status, 2026-08-29: the Tidsskrift inventory, DynaWord
candidate preparation, and licensed DSL lexical integration described here are
implemented in the
[DFM10 Danish Corpus Expansion](/pages/dfm10-danish-corpus-expansion.md)
runbook. That runbook supersedes this survey for operational commands and
measured output counts; this page remains the source-selection rationale.

## H.C. Andersen and related research sources

The existing DFM10 Andersen modernization source comes from
`ogierMontanus/hcandersenDk_data_2024`. Its owner is Holger Berg of the H.C.
Andersen Centre at SDU. Related repositories expose potentially valuable
material, but most do not declare a repository license and are not approved for
DFM ingestion yet.

| Source | Content and possible use | Admission status |
| --- | --- | --- |
| `ogierMontanus/hca-open-repo` | Normalized H.C. Andersen diaries, correspondence registers, entities, references, and source spreadsheets | Highest-value expansion candidate; require an explicit source/repository license and map rights by component before use |
| `ogierMontanus/hca2modernDanish` | Corrected and modernized XML for Andersen tales | Resolve license and overlap with the existing 1,187 aligned modernization pairs before inclusion |
| `ogierMontanus/NER4andersen` | Entity registers, distillation/evaluation data, and NER tooling | Small auxiliary or held-out Danish NER/entity-linking resource; no declared license |
| `ogierMontanus/hca-tales-segmented` | GPT-4 classifications of Andersen tales for economics and poverty themes | Niche labels with substantial text overlap; no declared license |
| `dsldk/herman-bang` | 8,429 TEI XML files of Herman Bang correspondence | Strong Danish correspondence candidate; request an explicit dataset license |
| `dsldk/diplomatarium-danicum` | Large medieval charter/OCR/editorial corpus | Potential historical-language source; mixed Latin/Old Danish and no declared repository license |
| `dsldk/tycho-brahe`, `middelaldertekster`, `brandes_xml` | Letters and historical/literary editions | Potential bounded historical/literary tasks; resolve per-edition rights and repository licenses first |
| `dsldk/danish-sentiment-lexicon` | 14,008-headword Danish sentiment lexicon | License-clear CC BY-SA 4.0; useful for a small lexical/sentiment supervision slice |
| `dsldk/dansk-frame-net` | Danish semantic-frame lexicon | Potential semantic-role/frame tasks; inspect and resolve the currently unclear license first |

The most productive next action is a coordinated license request to the H.C.
Andersen Centre/DSL for the corpus repositories, rather than assuming that
public GitHub access grants reuse rights. Official `hcandersen.dk` work pages
do expose CC BY 4.0 notices, but that does not automatically license every
repository component, annotation, or edition.

## DynaWord expansion since the local snapshot

The local snapshot is DynaWord `1.2.16`, with 46 declared configs and 45 text
source directories. The current Hub release is `1.2.22`, with 52 configs, 7.40
million source documents, and approximately 9.81 billion Llama-3 tokens. Six
configs were added and none were removed:

| Added config | Approximate tokens | License | Decision note |
| --- | ---: | --- | --- |
| `meta` | Annotation sidecar | MIT | High operational value for quality, safety, PII, content-type, audience, and educational-level filtering; not source text |
| `dakultur` | 5.49K | MIT | Tiny culture-oriented material; inspect for evaluation overlap and likely reserve for eval rather than training |
| `mosel_voxpopuli` | 161.33M | CC BY 4.0 | Valuable spoken Danish; audit transcript quality and deduplicate against existing Europarl-like material |
| `mosel_youtubecommons` | 7.09K | CC BY 4.0 | License-clear but negligible volume |
| `folketingets-dokumenter` | 2.81B | CC BY 4.0 | Dominant addition; compare hashes/IDs against the separately integrated DFM10 Folketing source before admitting it |
| `kalliope` | 14.01M | Public domain | Danish poetry/literary style; include only at a bounded weight or derive constrained literary tasks |

The added text is approximately 2.985 billion Llama-3 tokens, overwhelmingly
Folketing documents. Updating DynaWord is worthwhile, but the source must not
be blindly unioned with DFM10: first reconcile Folketing overlap, then audit
VoxPopuli and Kalliope. The `meta` sidecar should be retained even when a text
component is excluded because it enables more principled sampling.

## Larger openly licensed Tidsskrift.dk corpus

The local raw corpus has 4,121 CC BY 4.0 article rows and approximately 50.01
million Llama-3 tokens. The local BT source adds 62,934 derived passages from
3,359 distinct article rows. Current DynaWord still points to the same
`oliverkinch/tidsskrift-dk` source, so it is not an expansion.

A materially larger corpus is technically feasible. Tidsskrift.dk reports more
than 230 journals/yearbooks and more than 120,000 articles. Its OAI-PMH 2.0
endpoint exposes 1,847 journal/section sets, paginated records, Dublin Core and
JATS metadata, and article-level `dc:rights` values. A sampled record correctly
exposed both its copyright statement and a Creative Commons URL. Therefore a
metadata-first, fail-closed license harvest is practical.

The expansion pipeline must:

1. Harvest metadata only through `https://tidsskrift.dk/index/oai` and retain
   the OAI identifier, canonical URL, DOI, title, authors, journal, date,
   language, rights statement, and exact license URL.
2. Admit only an explicit allowlist. For a strict open corpus use CC0, CC BY,
   and CC BY-SA; place CC BY-NC variants in a separate non-commercial policy
   partition if desired, and exclude ND/no-license/free-access-only records.
3. Fetch JATS/full text or PDF only after the article passes the rights gate.
   Preserve attribution and license metadata in every resulting row.
4. Detect Danish, remove navigation/references-only/OCR-failure records, and
   audit a source-stratified sample before full conversion.
5. Deduplicate against the existing 4,121 raw articles and all Tidsskrift BT
   rows using OAI ID, DOI, canonical URL, and normalized-text hashes.
6. Keep raw Danish continuation admission consistent with the DynaWord policy;
   otherwise convert the licensed articles into grounded summarization, QA,
   rewriting, or retrieval tasks rather than adding another raw-text path.

The final obtainable size cannot be inferred from “freely available”: many
articles use restrictive licenses such as CC BY-NC-ND, and older records may
have no machine-readable rights. Run a complete metadata inventory first and
report counts and full-text bytes by exact license before downloading content.

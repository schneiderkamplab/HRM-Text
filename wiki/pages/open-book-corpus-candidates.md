---
type: Decision
title: Open Book Corpus Candidates
description: Ranked candidates for extending DFM training with provenance-preserving open books and grounded SFT.
tags: [datasets, dfm10, books, oer, licensing, sft]
status: stable
last_updated: 2026-08-29
confidence: high
sources:
  - id: otl-criteria
    resource: https://open.umn.edu/opentextbooks/books
    title: Open Textbook Library inclusion criteria
    author: org:University of Minnesota
  - id: bccampus-collection
    resource: https://collection.bccampus.ca/
    title: B.C. Open Collection
    author: org:BCcampus
  - id: doab-faq
    resource: https://www.doabooks.org/en/researchers/full-faq
    title: Directory of Open Access Books FAQ
    author: org:DOAB Foundation
  - id: oapen-metadata
    resource: https://www.oapen.org/article/metadata
    title: OAPEN Library metadata
    author: org:OAPEN Foundation
  - id: open-logic-license
    resource: https://openlogicproject.org/olp-license/
    title: Open Logic Project license
    author: org:Open Logic Project
  - id: pressbooks-directory
    resource: https://pressbooks.com/open-education/introducing-pressbooks-directory/
    title: Introducing Pressbooks Directory
    author: org:Pressbooks
  - id: ncbi-bookshelf-copyright
    resource: https://www.ncbi.nlm.nih.gov/sites/books/NBK554842/
    title: NCBI Bookshelf copyright notice
    author: org:US National Library of Medicine
  - id: wikibooks-copyright
    resource: https://en.wikibooks.org/wiki/Wikibooks%3ACopyrights
    title: Wikibooks copyright policy
    author: org:Wikimedia Foundation
---
# Open Book Corpus Candidates

## Objective

Extend the successful OpenStax grounded-SFT approach with modern, attributable
open books. Preserve the exact edition, source URL, content hash, title,
authors, license, and attribution in every derived artifact. A catalog's open
metadata license does not establish the license of each book.

## Ranked Candidates

| Priority | Source | Best contribution | Admission rule | Local overlap |
|---|---|---|---|---|
| 1 | Open Logic Project | Formal logic, proofs, countermodels, computability, set theory | Use the pinned LaTeX source under CC BY 4.0; mechanically validate symbolic answers | Source already downloaded and used for grounding, but not a first-class DFM10 SFT source |
| 2 | Open Textbook Library | Modern college material in business, social science, education, computing, and STEM beyond OpenStax | Admit exact editions with derivative-permitting licenses; retain book-level attribution and deduplicate OpenStax and BCcampus mirrors | No production corpus identified |
| 3 | BCcampus Open Collection | Curated textbooks, exercises, course packs, trades, applied and Canadian material | Check the metadata/license of every book; prefer CC BY/CC0 and retain source-edition identity | No production corpus identified |
| 4 | OAPEN/DOAB | Peer-reviewed academic monographs, humanities/social science breadth, multilingual and Danish books | Harvest metadata first; admit only selected license classes and downloadable exact editions; do not equate free-to-read with reusable | DFM10 has only the tiny `oliverkinch/doab-da-bt` derivative, not a broad book corpus |
| 5 | NCBI Bookshelf Open Access subset | Biomedical reference, clinical concepts, public-health and life-science explanations | Restrict to the OA/public-domain subset and inspect title- and asset-level licenses; exclude third-party figures/tables unless covered | No production corpus identified |
| 6 | Pressbooks Directory | Discovery of thousands of independently published OER books | Treat as a discovery index, not one corpus; require per-book license, quality, provenance, and cross-catalog deduplication | No production corpus identified |
| 7 | LibreTexts | Broad STEM modules and worked examples | Second-wave candidate only: preserve page/module attribution and resolve remix-level licensing and duplication | No production corpus identified |
| 8 | Wikibooks | Broad procedural and introductory material | Use only coherent, mature books; preserve revision provenance and satisfy CC BY-SA/GFDL attribution/share-alike obligations | No production corpus identified |

## Existing Sources

- `common-pile/project_gutenberg_filtered` is already downloaded locally
  (approximately 7.2 GB). It is useful for literature, style, historical
  language, and derived reading tasks, but is not the highest-value expansion
  for modern technical or professional knowledge. Copyright status must also be
  valid in the operating jurisdiction, not merely the United States.
- `oliverkinch/doab-da-bt` is active but tiny. It does not substitute for a
  license-filtered Danish or English DOAB/OAPEN program.
- `data/downloads/datasets/open_text_books` remains quarantined. Do not use the
  repack as a shortcut around edition-level provenance.

## Recommended Execution

1. Convert Open Logic into a small, high-confidence formal-reasoning corpus.
   Generate explanatory, proof-step, countermodel, equivalence, and
   misconception-correction tasks; verify formal targets independently.
2. Build a metadata-only inventory for Open Textbook Library and BCcampus.
   Select a 30--60 book pilot that fills measured Mimir subject gaps and does
   not duplicate retained OpenStax editions.
3. Harvest OAPEN/DOAB metadata and rank exact books by language, subject,
   license, extractability, and relevance. Pilot a compact CC BY/CC0 subset
   before considering NC or SA material.
4. Use Pressbooks only to discover books absent from the curated catalogs.
5. Apply the OpenStax production gates to every derivative: immutable source
   manifest, grounded generation, independent audit, decontamination,
   tokenizer-length validation, source-balanced sampling, and attribution.

## Decision

The next practical addition should be Open Logic, followed by a combined
Open Textbook Library/BCcampus pilot. OAPEN/DOAB offers the largest breadth but
has greater retrieval, edition, and license heterogeneity. Broad Gutenberg,
Pressbooks, LibreTexts, Wikibooks, or all-of-NCBI ingestion is not recommended.

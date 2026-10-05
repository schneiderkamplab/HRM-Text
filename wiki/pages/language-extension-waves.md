---
type: Reference
title: Language Extension Waves and Data Recipe
description: Language membership and the common parallel, instruction, transformation and separately curated DaLA expansion recipe.
status: draft
confidence: high
last_updated: 2026-10-03
tags: [data, multilingual, dfm12, dfm13, expansion]
---
# Language Extension Waves

## Membership

These are language variants, so Norwegian Bokmal and Nynorsk count separately.
Wave membership describes the expansion campaign, not a claim of equivalent
model quality or that every candidate source has been admitted.

| Wave | Added | Languages | Cumulative variants | Context |
|---|---:|---|---:|---|
| 0 | 2 | Danish (da), English (en) | 2 | Original bilingual foundation and instruction mixture inherited by DFM12 |
| 1 | 7 | Dutch (nl), Norwegian Bokmal (nb), Norwegian Nynorsk (nn), Swedish (sv), Icelandic (is), Faroese (fo), Polish (pl) | 9 | First DFM12 multilingual expansion, initially emphasizing Nordic languages plus Dutch and Polish |
| 2 | 12 | German (de), French (fr), Spanish (es), Italian (it), Czech (cs), European Portuguese (pt-PT), Finnish (fi), Greek (el), Romanian (ro), Ukrainian (uk), Estonian (et), Catalan (ca) | 21 | Broader European DFM12 instruction, transformation and synthetic campaign |
| 3 | 2 | Lithuanian (lt), Latvian (lv) | 23 | DFM13 Baltic extension; parallel/text/instruction preparation and audits, with DaLA owned separately |
| 4 | 11 proposed | Albanian (sq), Belarusian (be), Bosnian (bs), Bulgarian (bg), Croatian (hr), Hungarian (hu), Luxembourgish (lb), Serbian (sr), Slovak (sk), Slovenian (sl), Persian (fa) | 34 planned | Ten further EuroEval languages plus Persian; source research, not yet an assembled training mixture |

**Count clarification (2026-10-03, confirmed by the owner):** wave 2 has twelve
languages. The initial request said nine; nine is the cumulative
coverage after wave 1. The twelve codes are explicitly recorded in
[identity extension](dfm12-identity-extension.md) and implemented in
`dfm12/european_synthetic_campaign.py`. Do not silently omit three languages.

## Common Data Recipe

The [new-language expansion playbook](new-language-expansion-playbook.md)
consolidates exact quota bases, audit requirements, sharded execution,
publication and completion checks. This page remains the wave-membership
reference and concise recipe summary.

### Parallel Translation

Seek direct, high-quality parallel corpora between each new language and all
other supported languages, including other languages in the same wave.
Prefer curated institutional, editorial and human-translated sources over
web-mined alignments. Preserve source/version, alignment IDs and licenses.

`dfm12/config.yaml` defines English-pair allocation as **0.25** of the
English-Danish reference allocation and other-language pairs as **0.0625**
of that reference, i.e. one quarter of the new English-pair allocation.
These are intended allocation fractions, not claims of available accepted
rows or token counts. Apply them on the same basis as the existing sampler;
record both unique pairs and directional examples. Render both directions
with explicit source/target languages. Avoid doubling reported unique pairs.

For insufficient direct supply, the Baltic policy allows English-pivot
matching. Require matching English content with reliable provenance and
disambiguation; preserve both source legs. Do not join unrelated short generic
sentences. Audit both target languages and meaning equivalence. Explicitly
label model-generated bridging translations as synthetic. Do not pad a scarce
pair with low-quality data merely to hit its cap.

### Existing Instruction Data

Select native instruction/chat data and useful structured tasks, retaining
source splits, provenance and benchmark exclusions. Deduplicate translated
mirrors, inherited datasets and repeated templates. Parse source conversations
into roles/tools before rendering the Gemma 4 native template. Existing
ChatML/Llama/Mistral delimiters are not target text. Supervise supported
assistant turns, not user or tool messages.

Supplement thin instruction supply with diverse audited synthetic
conversations: multi-turn dialogue, grounded instructions, rewriting and
summarization, reasoning/math/code and native tool dialogue. Historical
accepted goals were 35K or 70K depending on available instruction supply.
**Standing recipe, confirmed 2026-10-03:** target **35K accepted synthetic
instruction conversations** where existing instruction data has sufficient
amount and breadth, and **70K accepted conversations** where it is scarce or
narrow. Assess both volume and task/domain diversity per language, record the
chosen tier and rationale, and count accepted outputs rather than generation
attempts. These are synthetic additions, not caps on existing instruction data.
See
[joint production](dfm12-joint-synthetic-production.md).

### Four Text Transformations

Use high-quality, broadly sampled documents rather than only the first source
file. DynaWord is useful where available; other document-preserving corpora
can fill gaps. Non-Danish text is not automatically added as raw continuation.

| Family | Construction and verification |
|---|---|
| Error correction / denoising | Corrupt a clean passage; target the verified original. Keep mutation types and counts and distinguish spelling from grammatical corruption. |
| Prefix continuation | Present a genuine document prefix and supervise its actual continuation; do not invent adjacency between unrelated rows. |
| Span filling | Remove spans from a coherent passage and specify the expected reconstruction format unambiguously. |
| Paragraph reordering | Shuffle real contiguous paragraphs and reconstruct their order. If structure is absent, explicitly label grouped-sentence or sentence reordering rather than claiming original paragraphs. |

Audit language, answer coherence, recoverability and usefulness. Preserve
accepted-only outputs, stable IDs and document-level split/dedup keys.
Language-specific spelling conventions and scripts must survive normalization.

### Separately Curated DaLA

Language acceptability and grammatical error correction are supplied by the
parallel DaLA workstream. Integrate its released training partitions with
explicit language instructions; retain heldout evaluation partitions separately.
This page does not authorize recreating or changing that workstream. The
Baltic decision explicitly permits source articles/sittings underlying DaLA
heldouts, but not their heldout labels/pairs; report that source overlap rather
than claiming document-disjoint evaluation.

## Related Plans

- [European expansion](dfm12-european-expansion.md)
- [European source inventory](european-language-expansion-sources.md)
- [Baltic sources and decisions](dfm13-baltic-language-sources.md)
- [Fourth-wave source research](fourth-language-extension-wave.md)

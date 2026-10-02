---
type: Research
title: DFM12 Additional Instruction Candidates
description: Missing or deferred instruction resources in existing DFM12 languages, separated from duplicates and generation seeds.
status: draft
confidence: medium
last_updated: 2026-09-26
tags: [dfm12, multilingual, instruction, source-inventory]
---
# DFM12 Additional Instruction Candidates

## Scope and Evidence

Checked existing English, Danish, Dutch, Swedish, Polish, Bokmal, Nynorsk,
Icelandic and Faroese. Compared `dfm12/config.yaml`, downloader registrations,
DFM11 prefix allocation and current DFM12 wiki decisions against HF cards,
size/statistics endpoints and selected preview rows on 2026-09-26.
"Missing" means no direct source registration found in that scope, not proof
of zero inherited row overlap. No downloads in bulk, admissions, audits or
running-job changes were made. Existing source authorization remains intact.

## Ranked Candidates

| Priority | Source | Eligible languages / upstream rows | Recommendation |
|---|---|---|---|
| 1 | [openeurollm/EU-Instruct-Synthetic](https://huggingface.co/datasets/openeurollm/EU-Instruct-Synthetic) | Dutch 131,515; Polish 146,247 | Strongest straightforward missing SFT candidates: 277,762 single-turn instruction pairs. Card describes synthgen-if generation but little independent quality evidence. Audit before admission. Distinct from already included translated DOLCI. |
| 2 | [AnnikaSimonsen/TrustLLM-reformulation-prompts](https://huggingface.co/datasets/AnnikaSimonsen/TrustLLM-reformulation-prompts) | 6,937 total including 250 German; 6,687 in existing languages | Particularly useful native/culturally adapted prompt seeds for low-resource languages. Actual schema has no answer despite card wording about synthetic responses: generate and independently audit answers. |
| 3 | [utter-project/EuroBlocks-SFT-2512](https://huggingface.co/datasets/utter-project/EuroBlocks-SFT-2512) | Dutch 15,569; Swedish 6,664; Polish 6,550; Norwegian 2,513; Danish 164 | 31,460 exact monolingual-label rows before quality/overlap checks. Norwegian is not automatically Bokmal. Additional en_nb/en_nn labels are bilingual data, not native monolingual chat. |
| 4 | [CohereLabs/aya_dataset](https://huggingface.co/datasets/CohereLabs/aya_dataset) | Train: Dutch 1,733; Polish 1,483; Swedish 1,310; Danish 97; English 3,944 | Human-authored/edited diversity: 4,623 non-English rows, plus English if nonduplicated. This is not the enormous Aya Collection already represented through Scandi. Check actual overlaps nonetheless. |
| 5 | [HuggingFaceTB/smoltalk2](https://huggingface.co/datasets/HuggingFaceTB/smoltalk2) selected English tasks | Card: Multi-Turn IF 28,217; smolagents toolcalling traces 9,079; everyday-conversations no_think 2,260; systemchats no_think 33,997 | Targeted instruction persistence, chat and tools; not whole-mixture inclusion. Original Tulu/Nemotron/tool sources can overlap inherited DFM data. Exclude raw OpenHermes constituent per existing policy and protect LongAlign evaluation material. |
| 6 | [BramVanroy/dolly-15k-dutch](https://huggingface.co/datasets/BramVanroy/dolly-15k-dutch) | 12,911 train_sft; 1,428 test_sft | Smaller older translated source, lower priority than EU-Instruct. Train only; check prompt overlap with inherited Dolly and Dutch composites. |
| Hold | [liu-nlp/smol-smoltalk-icelandic](https://huggingface.co/datasets/liu-nlp/smol-smoltalk-icelandic) | 456,780 train rows | Potential scale, not established quality. Card is metadata-only; first preview contains apparent semantic/linguistic translation issues. Require substantial audit and provenance/terms review before recommending admission. |

All sizes are source rows, not accepted unique rows or token allocations.
EuroBlocks, Aya and Dolly counts were read from dataset-viewer metadata;
SmolTalk2 counts are card descriptions. Mixture overlap can be considerable.

## TrustLLM Details

Card counts: Danish 999, Dutch 697, Bokmal 999, Nynorsk 998, Swedish 999,
Icelandic 998, Faroese 997, German 250. HF size endpoint confirms 6,937 rows.
The [paper](https://aclanthology.org/2026.lrec-1.841/) reports a slightly different
total; use pinned released rows for preparation. Card per-language counts also
need reconciliation with actual row counts before allocating generation quotas.
Some languages have only one contributor; native authorship does not ensure
complete topic diversity. Inspect original-text prompts for required missing
context, benchmark reuse and answerability before generating responses.
Keep source prompt ID, language and attribution; do not render contributor
metadata into training messages.

## Icelandic Preview Caution

The first returned SmolTalk Icelandic record retains original English in
`messages[].source_text` and translated text in `content`. English describes
a trombonist; its translated user turn instead uses a trumpet-player term,
while the translated answer uses the trombone term. Other phrasing appears
unnatural. This is an agent spot-check, not a native review or corpus error-rate
estimate. The source text makes paired meaning-preservation auditing possible.
Keep `source_text`, generation parameters and timing out of rendered messages.

## Not New / Not Ready

- Dutch UltraChat, nl/pl/sv translated DOLCI, Scandi, DynaInstruct, PLLuMIC
  main and PLLuM-Align are already registered/prepared, not new discoveries.
- AI-Sweden's DOLCI release is a mirror, not additional unique Swedish supply.
- `pelcra/PLLuMIC-syn-ext` is a known deferred source, not newly missed. Do not
  silently reverse the owner deferral based on its 54K filename.
- Norwegian Magpie is already represented through DynaInstruct. New upstream
  rows would require a revision/content diff, not duplicate wholesale inclusion.
- `NbAiLab/aurora-sft` is named by the Borealis model card, but unauthenticated
  dataset access returned HTTP 401 and it was not in the public listing. Treat
  as an access inquiry, not a confirmed downloadable addition.
- No comparably strong new ready-made Faroese/Nynorsk SFT corpus was verified.
  TrustLLM-grounded response generation is the more concrete lead.
- Danish already has extensive inherited instruction coverage. Small Aya and
  EuroBlocks increments add diversity, not meaningful volume. The survey does
  not claim exhaustive coverage of every Danish/English HF release.

## Preparation Contract

Use source-specific adapters and the current Gemma template; preserve tool
schemas and separate reasoning from final targets. In SmolTalk2, system/tool
information can live in `chat_template_kwargs` and must not be discarded.
Freeze evaluation exclusions, deduplicate against inherited prompts and
conversations, audit each language separately and begin at repeat 1 if approved.
New audited native-data additions may replace matching synthetic targets as
specified in the [multilingual extension plan](dfm12-multilingual-extension-plan.md),
not silently increase the approved budget.

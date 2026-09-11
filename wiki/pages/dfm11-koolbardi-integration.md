---
type: Operational Record
title: DFM11 Koolbardi Integration
description: Final controlled Koolbardi inventory, publication contract, Hub revisions, and DFM11 admission state.
tags: [dfm11, koolbardi, synthetic-data, danish, english, huggingface]
status: stable
last_updated: 2026-09-08
confidence: high
sources:
  - id: koolbardi-da-hub
    resource: https://huggingface.co/datasets/schneiderkamplab/dfm11-koolbardi-da
    title: DFM11 Koolbardi Danish
    author: org:schneiderkamplab
  - id: koolbardi-en-hub
    resource: https://huggingface.co/datasets/schneiderkamplab/dfm11-koolbardi-en
    title: DFM11 Koolbardi English
    author: org:schneiderkamplab
---
# DFM11 Koolbardi Integration

## Final controlled release

The completed controlled campaign is
`data/koolbardi/dfm11-million-controlled-a4b`. Its immutable final source is
`final.jsonl`, with SHA-256
`07f461b7c9adc2c49cb7a8c77bb29060200218568e2684229bcc79128bdc15e1`.
Finalization retained every qualifying surplus row while enforcing the minimum
complexity-by-length quotas in both languages.

| Package | Rows | Native rendered tokens | Compressed shards | Hub revision |
|---|---:|---:|---:|---|
| `schneiderkamplab/dfm11-koolbardi-da` | 535,930 | 1,165,181,804 | 32 | `de2b92ba6684001fe2504d2b96520b394bc08897` |
| `schneiderkamplab/dfm11-koolbardi-en` | 528,926 | 1,147,687,693 | 32 | `81ad1affa1539006b04fb833664ea393fbab59c1` |
| **Total** | **1,064,856** | **2,312,869,497** | **64** | - |

The finalizer rejected 13,730 rows. Every admitted row has a positive
instruction audit, one positive turn audit per assistant exchange, a positive
aggregate conversation audit, and an exact native Gemma-4 rendered length no
greater than 4,096 tokens. All required complexity-by-length cells meet their
configured minimum. DFM11 admits all released rows at repeat one.

## Publication contract

The upload packages live under `exports_dfm11/dfm11-koolbardi-{da,en}` and are
built by `scripts/prepare_dfm11_koolbardi_exports.py`. Publication rows retain
the conversation, audit verdicts, diversity controls, and reproducible model
and persona provenance. They remove generation-only prompt scaffolding, local
model paths, local audit reasons, and persona join identifiers.

Both packages load through Hugging Face `datasets` streaming JSON and pass the
bundled exhaustive validator. The Hub inventories contain 32 data shards plus
the card, manifest, and validator. Upload verification receipts are in
`logs/dfm11_koolbardi_upload_receipts.json`. The packages use the conservative
CC-BY-4.0 declaration inherited from the persona inputs and attribute the
pinned public sources in their cards. Synthetic factual, safety, copyright,
and privacy errors remain residual risks and are disclosed there.

Do not upload the raw campaign `final.jsonl`: it intentionally retains local
generation metadata that is unnecessary for downstream users.

## DFM11 pipeline

The downloader manifest contains the two pinned source IDs, and
`data_io/prefix_config_dfm11.yaml` admits the tokenized prefixes at repeat one.
The production conversion uses the Gemma-4 native template and a strict 4,096
token limit:

```bash
python scripts/tokenize_chat_template.py \
  exports_dfm11/dfm11-koolbardi-da \
  exports_dfm11/dfm11-koolbardi-en \
  --tokenizer-path /work/mimir/brainsurgery/models/gemma4_31b/tokenizer.json \
  --chat-template data_io/chat_templates/gemma4_native_chat.jinja \
  --output-dir data/tokenized_dfm11_additions \
  --workers 16 --max-seq-len 4096 --skip-bad-json
```

Run this incrementally without `--force`; existing DFM11 additions must not be
retokenized. The completed 64 shards contain 3,366,675 assistant targets and
zero skipped rows. Repeated prompt context produces 2,704,118,142 Danish plus
2,611,428,918 English stored tokens; these storage/compute tokens must not be
confused with the unique-conversation token totals in the release table.
The independently recomputed inventory is retained in
`logs/dfm11_koolbardi_tokenization_receipt.json`.

Aggregate union construction and sampling remain blocked on this preparation
host because the inherited `data/tokenized_dfm10` base is absent.

## Manual quality spot-check, 2026-09-08

A reproducible uniform sample of ten complete conversations per language was
reviewed with `scripts/sample_koolbardi_review.py`. Full rows, transcripts and
per-conversation assessments are in
`logs/dfm11_post/koolbardi_review_20260908/{rows.jsonl,conversations.md,assessment.md}`.
Language and dialogue continuity were generally good, but positive stored
audits missed malformed names/punctuation, questionable factual references,
incorrect technical explanations, code/description mismatches and excessive
agreement. Audit acceptance must not be interpreted as factual verification.

The review recommends, but does not implement, a provisional 50% conversation
cap for both languages in DFM11-post, with stratified rotating coverage and a
larger independent review. Current combined exposure is 5.316B tokens per
epoch, 14.89% of the post mix (22.22% of behavior tokens). Twenty conversations
cannot establish a corpus defect rate or a reliable Danish/English ranking.
At review time, repeat-one admission remained unchanged pending a user decision.
Superseded later on 2026-09-08 for DFM11-post only: the user approved quality
undersampling. The rebuilt post pool retains 278,918 DA and 275,106 EN whole
conversations, stratified by topic/mode/complexity/length, at repeat one.
Combined post exposure is approximately 2.784B tokens per epoch. Full DFM11
still admits both complete releases unchanged. See
[the post plan](dfm11-post-plan.md) for the revised total and other source cuts.

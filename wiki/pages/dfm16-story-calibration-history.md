---
type: Report
title: Historical SimpleStories judge comparisons
description: Preserved 2026-10-28 multiview and prose judge studies preceding context-aware calibration.
tags: [dfm16, simplestories, audit]
status: draft
confidence: high
last_updated: 2026-10-28
---
# Historical judge studies

Preserved from [DFM16](dfm16-plan.md); these results do not qualify the
[new context-aware gate](dfm16-story-calibration.md).

## Independent SimpleStories judge calibration (2026-10-28)

Owner-requested follow-up: rerun the same frozen 200 parents with **one atomic
yes/no question per request** (grammar, clarity, consistency separately), on
Odin-2-Large API, existing Qwen-27B/Flash-Next servers and temporary Mimir v1.8
in spare VRAM. Expanded scope includes original seeds, every individual user
and assistant message, whole conversations, adjacent two-message windows,
and two-exchange windows for revisions. No JSON or explanations. There are
3390 checks/model: 600 seed, 1674 message, 400 conversation, 637 message-pair,
79 exchange-pair checks. Conversation/window checks ask consistency and, where
applicable, request compliance rather than prose style. No truncation: Mimir
over-4096 requests remain unresolved. Initially, blind manual labels covered only
the selected 200 assistant texts. **Superseded later on 2026-10-28:** all 200
complete seeds/conversations have now been read blind to the new model votes,
and all 3390 criterion-specific checks are labelled. Inputs/results:
`data/dfm16/expansion-v1/stories/quality-v3-qwen/multiview-judge-study`.
The durable driver is `scripts.run_dfm16_multiview_judges --detach`; API key is
kept in memory/passed through an anonymous pipe, not persisted. It waits for
the preceding 600-check atomic Odin run before using the same API quota.
Automatic report: `docs/reports/simplestories-atomic-multiview-20261028.md`.
This remains a diagnostic, not authorization to promote datasets.

Manual annotation source:
`docs/reports/dfm16-multiview-manual-labels.json`. Regenerate the per-check
`manual-labels.jsonl` and coverage/hash manifest `manual-progress.json` with
`python -m scripts.dfm16_manual_multiview`. Explicit exceptions are recorded
per view/index/criterion; clear defaults apply only to explicitly reviewed
parents, never unread parents. There are 2897 clear, 300 definite-defect and
193 borderline checks. These are assistant manual judgments, not independent
native-speaker certification. Counts repeat correlated content across views;
do not interpret them as a conversation-level or production rejection rate.
Completed four-model comparison: on the historical 200-message manual subset,
Odin+Qwen27B unanimity admits 2/40 definite defects and rejects 71/134 clean
texts; adding Flash still admits the same two defects but rejects 76 clean.
Flash alone admits 9 defects and rejects 32 clean, Odin alone 21 and 2.
Mimir alone admits 33 defects, with 19 unresolved units; it is not a reliable
acceptance gate in this setup. Expanded labels show weak whole-conversation
checking by Flash (28/32 defective checks accepted) and Odin (23/32), versus
Qwen27B (9/32, but 111/337 clear checks rejected). Recommended next policy
candidate is selective local checks plus deterministic edit/length checks,
not requiring all models on every overlapping view. Strict Odin+Qwen is a
precision-oriented candidate, not production-certified; validate on a fresh
sample before adoption. Borderlines and unresolved outputs remain separate.
The report preserves the old holistic 200-message labels separately and uses
the expanded labels for new per-view comparisons. Invalid/missing model votes
remain unresolved, not accepts. No dataset rows are promoted by this review.

Completed independent Odin/Qwen-27B/Flash-Next prose ensemble experiment:
20 prior Odin accepts plus 200 fresh texts (50 each DA/EN/HI/JA), manually
labelled before examining judge votes. Fresh labels: 40 clear defects,
134 clean, 26 borderline. Odin alone passed 25 defects and rejected one clean
text; Odin+Flash passed 17 and rejected 10; Odin+27B passed 16 and rejected
53; all three passed 10 and rejected 57. Thus unanimity improves defect recall
but does not qualify the pipeline as reliably clean. These counts are from
previously approved candidates, not an unbiased production sample; manual
labels are assistant judgments, not native-speaker adjudication. No production
admission policy changed. All checks returned valid decisions. Odin kept 64
concurrency but used 90 sends/61 seconds after quota errors, below the owner
cap of 180/minute. See [ensemble comparison](../../docs/reports/simplestories-ensemble-20261028.md)
and [all 200 manual assessments](../../docs/reports/odin-ensemble-manual-200-20261028.md).

Latest owner priority: false accepts matter more than tolerable false rejects.
A reproducible stratified spot-check of 20 texts accepted by Odin for both
prose criteria found two clear missed issues and one minor spelling error.
This is not a population false-accept rate. Continue defect-recall calibration;
source passages/fidelity remain outside the prose-only experiment. API policy
now fixes concurrency at 64 and gates actual HTTP sends (including retries and
preflights) to at most 180 per rolling minute; account-sharing can still cause
429s. This supersedes the adaptive policy below, not its historical results.
See [accepted-text review and policy](../../docs/reports/simplestories-odin-false-accepts-20261028.md).

Remote Odin comparison subsequently completed using API model `odin-2-large`:
the same 295 text units yielded 34 language rejects and three coherence
rejects, all previously accepted by Mimir. Several inspected catches are real;
some rejections remain questionable. This is diagnostic, not production
qualification. The endpoint reports substantial hidden reasoning tokens even
with an eight-token visible-output request. Concurrency doubled 8/16/32/64,
then backed off to 32 on HTTP 429; headers indicate request-quota exhaustion,
not proof of a concurrent-request limit. Preserve accepted judgments on resume
and verify provider rate-window semantics before scaling. See
[Odin results and operational caveats](../../docs/reports/simplestories-odin-judges-20261028.md).

Owner correction: Mimir must judge paragraphs/stories, not conversations.
The whole-conversation diagnostics below are superseded as a qualification
method for prose judging; they do not establish paragraph/story performance.
Use `scripts.run_dfm16_mimir_judge_comparison --text-units` for independent
language and internal-coherence checks on intact assistant texts with parent
and turn provenance. Do not infer source fidelity or conversation compliance
from these text-only verdicts. Short sentence controls are also not a substitute
for paragraph/story calibration. Preserve previous results separately.

The corrected prose-unit run is complete: 295 assistant texts, each checked
independently for language and coherence. Language: 285 accepts, one reject,
nine invalid responses; coherence: 295 accepts. A confirmed Danish story with
"i mørkt frakke" was still accepted. Thus this prompt/model combination is
not qualified as an admission gate even at the corrected granularity. These
checks exclude source passages in user prompts and do not establish fidelity.
See the report's corrected paragraph/story-level results and retained receipts
under `quality-v3-qwen/mimir-text-units/`. Own server cleaned up; other jobs
and training-data acceptance remained unchanged.

Mimir v1.8 independently judged 200 sampled conversations for language and
content. Language accepted all 200 despite known defects; content produced
188 invalid responses and 12 accepts. Short controls improved output validity,
but the Danish DaLA-style check accepted all four deliberately bad sentences.
Eight simple content controls were correct, not yet evidence of reliability
on real conversations. Qwen also missed three of nine known non-language
failures. Neither agreement nor invalid outputs justify admitting rows.
Keep production held pending targeted real-example calibration; retain both
judges' independent evidence. See [results and limitations](../../docs/reports/simplestories-mimir-judges-20261028.md).

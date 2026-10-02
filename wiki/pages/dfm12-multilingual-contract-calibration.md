---
type: Runbook
title: Multilingual Contract Repair and Recalibration
description: Isolated generation and reviewer contract fixes following the completed 700-row diagnostic pilot.
tags: [dfm12, multilingual, calibration, generation, review]
status: draft
last_updated: 2026-09-27
confidence: high
---
# Contract Repair and Recalibration

On 2026-09-27 the user authorized fixing both invalid reviews and non-tool
generation failures, followed by another calibration. This is not permission to
admit the old quarantined pilot or automatically start the full 35K pilot.

## Baseline

The [infrastructure retry](dfm12-multilingual-infrastructure-retry.md) completed
all 298 selected rows with no remaining transport failures. Combined diagnostic
outcomes are 521 reviewed, 81 invalid reviews and 98 invalid generations; 357
would pass both reviewers, but none is admitted. Counts below are first-failure
buckets, not exhaustive semantic judgments.

Review failures: 59 quote/pointer failures (41 oversized quotes), eight context
overflows, six inconsistent or missing issue findings, five oversized
explanations and three invalid back-translations. Of the 98 invalid generations,
60 are tool dialogue. Other failures are 13 empty fields, four malformed JSON
responses, 17 role-order violations, three length stops and one unexplained
abort. A stop finish reason did not guarantee valid JSON. An abort is not
automatically a transport failure.

## Isolated Changes

Use new versioned modules and new artifact roots. Preserve old requests,
responses, manifests and results; do not reinterpret frozen v2/v3 tool specs.

- Tool calls use the [native v4 contract](dfm12-multilingual-tool-dialogue.md),
  OpenAI-compatible definitions, deterministic structured calls/results and
  localized natural-language final responses. Claims about unexecuted actions
  remain semantic failures; JSON-only finals are not a substitute for dialogue.
- Reviewer evidence is selected from code-generated indexed assistant spans.
  Keep the complete candidate context, explicit per-dimension findings, bounded
  meaningful explanations and literal meaning without silently repairing text.
- Non-tool multi-turn output uses explicit user/assistant pairs, assembled into
  roles by code. Keep meaningful-text, JSON, repetition and source constraints.
  Do not blindly merge malformed messages or extend repetitive generations.
- Preflight complete rendered prompts plus reserved completions against the
  verified server context. No silent truncation or skipped review.

## Calibration Scope and Resources

Run new generation cases across all seven languages and tool subtypes, plus
the existing reviewer controls, explicitly labeled previously exposed rather
than fresh heldout data. Report operational validity, semantic discrimination
and deterministic checks separately. Existing controls are not native-language
gold and cannot establish broad linguistic quality by themselves.

Reuse healthy existing Gemma 4 26B-A4B endpoints on ports 8600-8607 as CPU
clients only. Verify the exact model and context before dispatch; port 8600
reported 16384 at planning time. Never stop or modify borrowed audit servers.
Keep inference bounded, preserve raw responses and use transport-only retries
with cooldowns. Do not allocate another model beside the identity continuation;
the thread retains its per-GPU 50% memory ceiling.

## Live Calibration and Recovery

Supersedes the initial not-yet-run status on 2026-09-27. The v6 calibration
launched in `data/dfm12/multilingual-calibration-v6-20260927`, with 242 exposed
reviewer controls and 112 new generation cases. It borrows all eight existing
teacher endpoints without allocating model memory or signalling their processes.

The initial client completed all controls (239 structurally valid reviews,
three invalid reviews) but generation endpoint timeouts opened circuit breakers,
leaving generation incomplete. A subsequent resume revealed an independent
reporting defect: `summarize()` added nullable validity fields with `sum`, raising
`TypeError` when a failed generation recorded `structure_valid: null`. The
exception aborted the client and cancelled outstanding requests. Do not mistake
these infrastructure outcomes for semantic rejection or a completed pilot.

Recovery must count explicit true validity flags, test null-valued failure
records, preserve completed outcomes and archive infrastructure-failed attempts
before authorized retry. Keep semantic invalid outputs unchanged. Longer bounded
request timeouts do not by themselves fix the reporting crash. Record the final
recovery outcome here after verification; the full 35K generation remains gated
on calibration assessment.

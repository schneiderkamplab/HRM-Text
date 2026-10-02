---
type: Report
title: Identity Versus Epoch 10 EuroEval Regression Review
description: Read-only comparison of four EuroEval losses and the tokenizer confound.
tags: [dfm12, identity, evaluation, tokenizer]
status: draft
last_updated: 2026-09-28
confidence: high
---
# Identity Versus Epoch 10 EuroEval

## Verdict

The four measured regressions are real under their respective evaluation
configurations, but this is not a controlled measurement of identity-training
damage. Epoch 10 uses `fix_mistral_regex=true`; identity uses `false`.
CPU reconstruction changes token IDs for every saved benchmark prompt.
The earlier same-weights 2750K experiment establishes that this flag alone can
substantially reduce these scores. It does not establish what fraction of the
current losses comes from tokenization, changed weights, or answer formatting.
Current raw responses and finish reasons are not retained in these task roots,
so a current per-example causal attribution is blocked.

| Task / capability | Epoch 10 | Identity | Change, percentage points |
|---|---:|---:|---:|
| Life in the UK / UK civic knowledge, accuracy | 68.046875 | 54.531250 | -13.515625 |
| ScaLA Danish / grammatical acceptability, macro F1 | 84.798257 | 75.225394 | -9.572863 |
| HellaSwag English / commonsense completion, accuracy | 78.750000 | 69.453125 | -9.296875 |
| AngryTweets / Danish sentiment, macro F1 | 70.795562 | 64.638921 | -6.156640 |

All four are lower in all ten corresponding passes. Accuracy totals over the
2,560 bootstrap sample occurrences are 1,742 versus 1,396 for UK (346 fewer
correct), and 2,016 versus 1,778 for HellaSwag (238 fewer). These are repeated
bootstrap occurrences, not 2,560 independent questions. Macro F1 cannot be
converted into a count of additional wrong answers.

## Matched Evaluation Inputs

Baseline root: `logs/euroeval/dfm11_XL_epoch10/epoch_10/epoch_2`.
Current root:
`logs/scheduler/dfm12_XL_identity_step2897261_ema_full_20260928/results/euroeval/step_2897261`.
The current task files are symlinks into scheduler jobs; inspection followed
those links. Evidence is each task's `proxy_payloads.jsonl`,
`euroeval_benchmark_results.jsonl`, and cached validation Arrow file.

Both runs use EuroEval 18.1.0, validation data, ten bootstrap passes, and
256 validation rows per task. Validation text/label tables are identical by
canonical JSON SHA256 for each task. Their hashes are:

| Task | Validation-table SHA256 |
|---|---|
| UK | `2d22479f96f87bfb4225ea26de5d0d841cc7e219ae1557f20a7d49917a012c79` |
| ScaLA | `f4ed8d9939ef704c6445f3863fc83f1e26d2886be8b3a8df05e288f57ccc486f` |
| HellaSwag | `dedc35db4909cbd2f8653e6cd4f859be55fb418f808f0c88fd30e8f39ac21086` |
| AngryTweets | `1b311024c8502da84b2130427e9266ed22174dde7bff17ae7a847b0006fd7b8c` |

Full outgoing message multisets match exactly, including few-shot examples,
question text, role structure, and answer instructions. Each is one user
message containing flattened demonstrations separated by `assistant:` text.
UK/HellaSwag have five demonstrations; ScaLA/AngryTweets have twelve.
There are 1,638 distinct actual UK request prompts and 1,624 for each other
task in both runs, plus eleven probe requests per task. Fewer requests than
bootstrap occurrences reflect cached duplicate inputs, not fewer scored rows.
The reported metric `num_samples=10` means ten passes, not ten questions.

Every actual outgoing task request has `temperature=0.0`, `max_tokens=10`.
Both proxies strip `logprobs`, `response_format`, `seed`, `stop`, and
`top_logprobs`. Neither uses constrained-label generation or answer-option
likelihood scoring in these captured requests. Both declare context 4,096.
Recorded Transformers 5.15.0, Torch 2.13.0 and xgrammar 0.2.3 match;
LiteLLM changes from 1.102.0 to 1.103.0. This version difference did not change
the captured outgoing prompts or explicit sampling settings.

## Tokenization And Truncation

Exports inspected:
`exports/dfm11_XL_epoch10_epoch_10_ema_hf` and
`exports/dfm12_XL_identity_step2897261_ema_hf_training_tokenizer`.
Their raw `tokenizer.json` SHA256 is identical:
`12bac982b793c44b03d52a250a9f0d0b666813da566b910c24a6da0695fd11e6`.
Their tokenizer configs explicitly differ in `fix_mistral_regex` (true/false).
The current scheduler's `export-validation.json` independently records false,
the raw hash, EMA export and ten tokenizer-parity probes.

CPU-only local tokenization used the two actual export loaders and
`evaluation/chat_templates/gemma4_native_chat.jinja`, with generation prompt,
no extra special tokens and no truncation. Both server command logs name this
same chat-template path and max model length 4,096. This reconstructs the
current on-disk template; it is not a historical template-byte attestation.

| Task | Old prompt tokens, min-max | New prompt tokens, min-max | Changed token-ID sequences |
|---|---:|---:|---:|
| UK | 447-572 | 383-510 | 1638/1638 |
| ScaLA | 912-1207 | 832-1098 | 1624/1624 |
| HellaSwag | 677-1081 | 588-965 | 1624/1624 |
| AngryTweets | 1012-1367 | 924-1257 | 1624/1624 |

Zero reconstructed prompts plus ten output tokens exceed 4,096. Input-context
overflow is therefore not supported as an explanation. Output truncation at
ten tokens is a different question and cannot be counted for the current run
without responses/finish reasons. Neither export has `generation_config.json`.
Server launch settings match bfloat16, eager execution, FLASH_ATTN and native
Gemma template/tool parser; recorded memory utilization differs (old .95,
current .45 in the inspected launches). No evidence attributes losses to that
resource-setting difference.

## Scoring And Missing Evidence

The two cached metric Python files per task are byte-identical between runs.
All raw pass results report empty `failed_instances`. This is not proof of
well-formed output: installed EuroEval
`task_group_utils/sequence_classification.py:193` accepts label prefixes,
then uses weighted edit-distance matching. For letter tasks, `assistant: b`
is interpreted as `a`; this was demonstrated in the older replay.

All eight inspected task `cache/model_cache` directories contain no files.
`euroeval/generation.py:100` removes model caches outside debug mode. Proxy
payloads preserve outgoing requests, not responses. Consequently there is no
current confusion matrix, per-example regression list, observed reasoning
rate, or output-truncation count in these artifacts. Aggregate scores cannot
distinguish these failure modes. Matching EuroEval versions and metric files
support scorer consistency; historical full package-source pins were not
found or reconstructed in this review.

## Earlier Controlled Evidence

The [2750K investigation](dfm11-xl-epoch10-resume.md) includes an isolated
same-weights tokenizer comparison and paired explicit-token-ID replay.
Full comparison receipt:
`logs/scheduler/dfm8_XXL_1epoch_steps50k_100k_persistent_vllm_20260725/tokenizer-comparison-2750k/comparison.md`.

| Task | 2750K fix on | 2750K fix off | Change, percentage points |
|---|---:|---:|---:|
| UK accuracy | 67.3828 | 49.8438 | -17.5391 |
| ScaLA macro F1 | 78.7852 | 77.7240 | -1.0613 |
| HellaSwag accuracy | 75.9375 | 68.0078 | -7.9297 |
| AngryTweets macro F1 | 73.9219 | 57.5616 | -16.3604 |

The 30-example/task paired replay is retained in
`logs/eval/xl_2750k_tokenizer_replay/{report.md,summary.json,generations.jsonl}`.
UK fix-off produced literal `<think>` text and ten-token length finishes in
15/30 cases versus zero with fix-on; correct counts were 14/30 versus 21/30.
AngryTweets always produced bare labels, but fix-off shifted toward neutral
(20 versus 14 predictions), with 18 versus 19 correct. HellaSwag gave two
`assistant:` prefixes fix-off and none fix-on, with 21 versus 24 correct;
the embedded letters in those two prefixed answers were themselves wrong,
so stripping prefixes would not explain the observed gap. ScaLA was not in
that response-level replay.

These are demonstrated mechanisms at 2750K, not observed current responses.
In particular, the large current ScaLA loss is not explained by the small
older tokenizer-only ScaLA delta. Nor can old deltas simply be subtracted
from current deltas: weights and tokenizer effects can interact.

To attribute the current losses requires a separately authorized same-checkpoint,
same-prompt tokenizer crossover with retained raw responses and finish reasons,
or at least an epoch-10 raw-tokenizer baseline. No such GPU run, process action,
configuration change, scorer modification or raw-result edit was performed.
This report is the only file written by this investigation.

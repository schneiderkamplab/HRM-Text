# Math Evaluation Invalids

Last updated: 2026-06-28

## Current Interpretation

Do not treat the current DFM6 `MATH` and MMLU-math invalids as pure capability failures.

- `MATH`: invalid mostly means the model did not produce a final `\boxed{...}` answer. Probes showed generations often continue reasoning until the token cap and are cut off before boxing.
- MMLU math subsets: invalid mostly means the model starts a learned reasoning trace such as `<think>` while the scorer permits only a one-token exact `A`, `B`, `C`, or `D`.

The exported tokenizer EOS is correct for current evals: `eos_token='<turn|>'`, `eos_token_id=106`, matching `stop_token_ids: [106]`. The Gemma-native eval template does not inject thinking markers when `enable_thinking=False`; the model emits plain `<think>` from learned behavior.

## Suggested Actions

1. Keep the current strict standard eval as the continuity/comparability line.

2. Add a parallel diagnostic/fair math eval variant:
   - `MATH`: prepend or wrap the task with an explicit instruction to end with `\boxed{...}`.
   - MCQ tasks, especially MMLU math/logical subsets: use constrained letter generation if possible, or allow a few tokens and extract the valid answer letter robustly.

3. Test constrained decoding for MMLU-style MCQ tasks.
   - Best: force output to one of `A/B/C/D`.
   - Fallback: `max_tokens=8-16` plus an extractor that handles `<think>`, `Answer:`, whitespace, and takes a valid option letter.

4. Test a MATH boxed-answer prompt on shards before changing full-suite evaluation:
   - Example instruction: `Solve the problem. End your response with the final answer in \\boxed{...}.`
   - Compare invalid rate and accuracy against the current strict prompt.

5. Add eval smoke tests for formatting contracts:
   - MATH generations contain boxed answers at an acceptable rate.
   - MMLU math direct mode does not start with `<think>`, or the extractor/constrained decoding handles it.
   - EOS/stop token remains id `106`.

6. Consider data-side cleanup for future checkpoints:
   - Keep reasoning traces where useful, but add direct-answer formatting examples for hard MCQ math.
   - For direct-mode hard MCQ examples, train responses to be exactly `A`, `B`, `C`, or `D`.

7. Do not rerun the whole suite until small probes pass:
   - MATH shard with boxed-answer prompt.
   - MMLU math subsets with constrained or relaxed extraction.
   - Compare against current strict scores, then decide which result line is official and which is diagnostic.

## Probe Artifacts

```text
logs/analysis/dfm6_step500000_math_invalid_probe/math_probe_512.yaml
logs/analysis/dfm6_step500000_math_invalid_probe/generations_512/MATH.generations.jsonl
logs/analysis/dfm6_step500000_math_invalid_probe/run_mmlu_probe.py
logs/analysis/dfm6_step500000_math_invalid_probe/mmlu_probe/mmlu_math_probe.jsonl
logs/analysis/dfm6_step500000_math_invalid_probe/run_mmlu_prompt_variant_probe.py
logs/analysis/dfm6_step500000_math_invalid_probe/mmlu_probe/mmlu_prompt_variant_probe.jsonl
```

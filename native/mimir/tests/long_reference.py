"""Build longer session cases with independent full-forward Transformers logits."""

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from transformers import HrmTextForCausalLM

__all__ = []


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    torch.set_num_threads(4)
    model = HrmTextForCausalLM.from_pretrained(args.model, dtype=torch.float32).eval()
    model.config._attn_implementation = "eager"
    prompt = [2] + [3 + i * 17 % 120 for i in range(95)]
    answer = [3 + i * 13 % 120 for i in range(32)]
    cases = [
        {"id": "long-single", "steps": [{"tokens": prompt, "attention": "prefix"}] + [
            {"tokens": [token], "attention": "causal"} for token in answer]},
        {"id": "long-chunk", "steps": [
            {"tokens": prompt, "attention": "prefix"}, {"tokens": answer, "attention": "causal"}]},
        {"id": "context-boundary", "steps": [
            {"tokens": prompt + answer[:-1], "attention": "prefix"},
            {"tokens": answer[-1:], "attention": "causal"}]},
    ]
    conversation = [2, 11, 23]
    turns = []
    for turn in range(12):
        turns.extend([
            {"tokens": list(conversation), "attention": "prefix"},
            {"tokens": [61, 73, 89], "attention": "causal"},
        ])
        conversation += [61, 73, 89, 3 + turn]
    cases.append({"id": "twelve-turns", "steps": turns})
    oracle = args.output / "oracle"
    oracle.mkdir(parents=True, exist_ok=True)
    report = {"cases": []}
    with torch.inference_mode():
        for case in cases:
            case.update(n_ctx=128, n_ubatch=127)
            history, types, past = [], [], None
            reference = {"id": case["id"], "steps": []}
            for index, step in enumerate(case["steps"]):
                prefix = step["attention"] == "prefix"
                if prefix:
                    history, types, past = [], [], None
                step["pos"] = len(history)
                history += step["tokens"]
                token_types = [int(prefix)] * len(step["tokens"])
                types += token_types
                full = model(torch.tensor([history]), token_type_ids=torch.tensor([types]), use_cache=False)
                expected = full.logits[0, -len(step["tokens"]):].numpy()
                cached = model(torch.tensor([step["tokens"]]), token_type_ids=torch.tensor([token_types]),
                               past_key_values=past, use_cache=True)
                past = cached.past_key_values
                np.testing.assert_allclose(expected, cached.logits[0].numpy(), atol=2e-5, rtol=2e-5)
                name = f"{case['id']}-{index}.f32"
                expected.astype(np.float32).tofile(oracle / name)
                reference["steps"].append({"file": name, "shape": list(expected.shape)})
            report["cases"].append(reference)
    (args.output / "cases.json").write_text(json.dumps(cases, indent=2) + "\n")
    (oracle / "result.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    _main()

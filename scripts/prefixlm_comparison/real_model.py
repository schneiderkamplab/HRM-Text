"""Prepare frozen Danish/English token streams for real Mimir logit comparisons."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from transformers import AutoTokenizer, HrmTextForCausalLM

from fixture import _write_gguf

__all__ = []


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    oracle = args.output / "oracle"
    oracle.mkdir(exist_ok=True)
    torch.set_num_threads(4)
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = HrmTextForCausalLM.from_pretrained(args.model, dtype=torch.float32,
                                             attn_implementation="eager").eval()
    _write_gguf(model, args.output / "mimir-f32.gguf", True)
    messages = [
        ("danish", [{"role": "user", "content": "Hvad er forskellen på vejr og klima? Svar kort på dansk."}]),
        ("english", [{"role": "user", "content": "Explain why the sky is blue in two short sentences."}]),
        ("multiturn", [{"role": "user", "content": "Hvad er fotosyntese?"},
                       {"role": "assistant", "content": "Planter bruger lys til at omdanne vand og kuldioxid til sukker og ilt."},
                       {"role": "user", "content": "Hvorfor er det vigtigt for mennesker?"}]),
    ]
    cases, references, prompts = [], [], []
    with torch.inference_mode():
        for name, conversation in messages:
            rendered = tokenizer.apply_chat_template(conversation, tokenize=False,
                                                       add_generation_prompt=True, enable_thinking=False)
            ids = tokenizer.apply_chat_template(conversation, tokenize=True,
                                                 add_generation_prompt=True, enable_thinking=False,
                                                 return_tensors="pt", return_dict=True)["input_ids"]
            prompts.append({"id": name, "messages": conversation, "rendered": rendered,
                            "token_ids": ids[0].tolist(),
                            "rendered_sha256": hashlib.sha256(rendered.encode()).hexdigest()})
            first = model(ids, token_type_ids=torch.ones_like(ids), use_cache=True, logits_to_keep=1)
            cache = first.past_key_values
            answer, single_logits = [], []
            logits = first.logits
            for _ in range(4):
                token = logits[:, -1].argmax(-1, keepdim=True)
                answer.append(token.item())
                output = model(token, past_key_values=cache, use_cache=True, logits_to_keep=1)
                cache, logits = output.past_key_values, output.logits
                single_logits.append(logits[0].numpy())
            # An independent full forward supplies a mixed prefix/causal-answer mask.
            full = torch.cat([ids, torch.tensor([answer])], dim=1)
            types = torch.cat([torch.ones_like(ids), torch.zeros((1, len(answer)), dtype=torch.long)], dim=1)
            direct = model(full, token_type_ids=types, use_cache=False,
                           logits_to_keep=len(answer) + 1).logits[0].numpy()
            expected = np.concatenate([first.logits[0].numpy(), *single_logits])
            np.testing.assert_allclose(expected, direct, atol=2e-3, rtol=2e-4)
            for chunked in [False, True]:
                case_id = name + ("-chunk" if chunked else "-single")
                steps = [{"tokens": ids[0].tolist(), "attention": "prefix", "pos": 0, "all_logits": False}]
                arrays = [first.logits[0].numpy()]
                if chunked:
                    steps.append({"tokens": answer, "attention": "causal", "pos": ids.shape[1]})
                    arrays.append(np.concatenate(single_logits))
                else:
                    for index, token in enumerate(answer):
                        steps.append({"tokens": [token], "attention": "causal", "pos": ids.shape[1] + index})
                        arrays.append(single_logits[index])
                cases.append({"id": case_id, "n_ctx": 256, "n_batch": 256, "n_ubatch": 256, "steps": steps})
                ref_steps = []
                for index, rows in enumerate(arrays):
                    filename = f"{case_id}-{index}.f32"
                    rows.astype(np.float32).tofile(oracle / filename)
                    ref_steps.append({"file": filename, "shape": list(rows.shape)})
                references.append({"id": case_id, "steps": ref_steps})
            prompts[-1]["reference_answer_ids"] = answer
            prompts[-1]["reference_answer_text"] = tokenizer.decode(answer)
            print(f"Prepared {name}: {ids.shape[1]} prompt tokens, {len(answer)} answer tokens", flush=True)
    (args.output / "cases.json").write_text(json.dumps(cases, indent=2) + "\n")
    (args.output / "prompts.json").write_text(json.dumps(prompts, indent=2, ensure_ascii=False) + "\n")
    (oracle / "result.json").write_text(json.dumps({"cases": references}, indent=2) + "\n")


if __name__ == "__main__":
    _main()

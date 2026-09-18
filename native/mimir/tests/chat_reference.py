"""Generate free-running HF references for an actual two-turn terminal conversation."""
import argparse
import json
from pathlib import Path
import torch
from transformers import AutoTokenizer, HrmTextForCausalLM

__all__ = []


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    torch.set_num_threads(4)
    model = HrmTextForCausalLM.from_pretrained(args.model, dtype=torch.float32, attn_implementation='eager').eval()
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    messages, cases = [], []
    with torch.inference_mode():
        for text in ['Svar med ét ord: Hvad er 2 + 2?', 'Og hvad er 3 + 3?']:
            messages.append({'role': 'user', 'content': text})
            ids = tokenizer.apply_chat_template(messages, tokenize=True, return_dict=False,
                                                add_generation_prompt=True, enable_thinking=False)
            inputs = torch.tensor([ids])
            output = model.generate(inputs, token_type_ids=torch.ones_like(inputs), max_new_tokens=32,
                                    do_sample=False, eos_token_id=tokenizer.eos_token_id,
                                    pad_token_id=tokenizer.pad_token_id)
            answer = output[0, len(ids):].tolist()
            eos = answer[-1] == tokenizer.eos_token_id
            tokens = answer[:-1] if eos else answer
            decoded = tokenizer.decode(tokens, skip_special_tokens=True, clean_up_tokenization_spaces=False)
            cases.append({'text': text, 'prompt_tokens': ids, 'tokens': tokens, 'answer': decoded,
                          'finish': 'eos' if eos else 'length', 'stop_token': tokenizer.eos_token_id if eos else -1})
            messages.append({'role': 'assistant', 'content': decoded})
    args.output.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    _main()

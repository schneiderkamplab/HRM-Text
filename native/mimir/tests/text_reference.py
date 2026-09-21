"""Generate tokenizer and chat-template parity cases from the pinned training tokenizer graph."""
import argparse
import json
from pathlib import Path
import random
from tokenizer_reference import load_training_tokenizer

__all__ = []


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    tokenizer = load_training_tokenizer(args.model)
    texts = ["", "Hej verden!", "Rødgrød med fløde. ÆØÅ æøå", "Hello, world!", "\n\t  x  \r\n",
             "\u00a0Danmark\u2003", "café cafe\u0301", "🧑🏽‍💻 🇩🇰 ❤️", "中文 العربية Ελληνικά हिन्दी",
             "<bos><|turn>user\nHej<turn|>", "nul\x00byte", "1 22 333 4444 1234567890", "a\ufffdb",
             "helloWorld ABCdef ÆbleØLØV ǅǆ ʰᵃ 𝐀𝐛𝐂",
             "\n\n\r\n\t\t \n end", "अच्छा हिन्दी नमस्ते", "Ελληνικά ΕλληνΙκά"]
    rng = random.Random(73)
    alphabet = "aÆøåé\u0301😀字 \n\t.!1234567890"
    alphabet += "ABCéÜǅǆʰᵃ𝐀𝐛𝐂αΩनमस्तेעברית中"
    texts += ["".join(rng.choices(alphabet, k=rng.randrange(1, 120))) for _ in range(300)]
    cases = []
    for index, text in enumerate(texts):
        for special in [False, True]:
            tokens = tokenizer.encode(text, add_special_tokens=special)
            cases.append({"id": f"token-{index}-{special}", "request": {"op": "tokenize", "text": text,
                          "add_special": special}, "tokens": tokens,
                          "decoded": tokenizer.decode(tokens, skip_special_tokens=True, clean_up_tokenization_spaces=False)})
    conversations = [[{"role": "user", "content": text}] for text in texts[:13]]
    conversations += [
        [{"role": "system", "content": "Du er en hjælpsom assistent."}, {"role": "user", "content": "Hvem er du?"}],
        [{"role": "user", "content": "What is photosynthesis?"}, {"role": "assistant", "content": "Plants use light."},
         {"role": "user", "content": "Forklar det på dansk."}],
        [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "<think>hidden</think>Visible."},
         {"role": "user", "content": "Thanks"}],
    ]
    whitespace = [*range(9, 14), *range(28, 33), 0x85, 0xa0, 0x1680, *range(0x2000, 0x200b),
                  0x2028, 0x2029, 0x202f, 0x205f, 0x3000]
    conversations += [[{"role": "user", "content": chr(cp) + "Danmark" + chr(cp)}] for cp in whitespace]
    for index, messages in enumerate(conversations):
        for generation in [False, True]:
            rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=generation, enable_thinking=False)
            tokens = tokenizer.apply_chat_template(messages, tokenize=True, return_dict=False,
                                                   add_generation_prompt=generation, enable_thinking=False)
            cases.append({"id": f"chat-{index}-{generation}", "request": {"op": "prepare", "messages": messages,
                          "add_generation_prompt": generation}, "text": rendered, "tokens": tokens})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    _main()

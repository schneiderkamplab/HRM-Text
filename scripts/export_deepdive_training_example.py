"""Export the first DeepDive trajectory, verifying against stored training tokens."""
import json
from pathlib import Path

import jinja2
import numpy as np
from tokenizers import Tokenizer

from scripts.tokenize_chat_template import examples_from_messages, tokenize_example


def main():
    source = Path('data/dfm10_deepdive_sources/zai_deepdive_trajectories_sft__train.jsonl')
    stored = Path('data/tokenized_dfm11') / source.name
    with source.open() as handle:
        row = json.loads(next(handle))
    info = json.loads(Path('data/sampled_dfm11/metadata.json').read_text())['tokenizer_info']
    policy = json.loads((stored / 'metadata.json').read_text())
    tokenizer = Tokenizer.from_file(info['tokenizer_path'])
    template = jinja2.Environment().from_string(Path(info['chat_template_path']).read_text())
    arrays = {name: np.load(stored / f'{name}.npy', mmap_mode='r') for name in
              ('tokens', 'inst_start', 'inst_len', 'resp_start', 'resp_len')}
    records = []
    index = 0
    for turn, example in enumerate(examples_from_messages(row['messages'], row['tools'])):
        encoded = tokenize_example(tokenizer, template, example, info['enable_thinking'],
                                  policy['max_seq_len'], policy['preserve_first_user'])
        if encoded is None:
            records.append(dict(source_row=0, assistant_turn=turn, status='excluded_by_tokenizer',
                                assistant_message=example.assistant_message))
            continue
        for prefix, ids in zip(('inst', 'resp'), encoded):
            start = int(arrays[f'{prefix}_start'][index])
            length = int(arrays[f'{prefix}_len'][index])
            assert ids == arrays['tokens'][start:start + length].tolist(), (turn, prefix)
        prompt, target = encoded
        records.append(dict(source_row=0, assistant_turn=turn, status='verified_against_training_tokens',
                            stored_example_index=index, prompt_tokens=len(prompt), target_tokens=len(target),
                            prompt=tokenizer.decode(prompt, skip_special_tokens=False),
                            target=tokenizer.decode(target, skip_special_tokens=False),
                            assistant_message=example.assistant_message))
        index += 1
    output = Path('docs/deepdive_first_trajectory_training_turns.jsonl')
    output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records))
    print(f'{output}: {len(records)} assistant turns, {index} verified training examples')


if __name__ == '__main__':
    main()

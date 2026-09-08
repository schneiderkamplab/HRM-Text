#!/usr/bin/env python3
"""Reproducibly inspect eligible training targets of large post-mix sources."""
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / 'logs/dfm11_post/manifest.json').read_text())
    groups = defaultdict(list)
    for task in manifest['tasks']:
        if task['selected_rows']:
            groups[task['family']].append(task)
    out = ROOT / 'logs/dfm11_post/large_source_review_20260908'
    out.mkdir(exist_ok=True)
    info = json.loads((ROOT / 'data/tokenized_dfm11/tokenizer_info.json').read_text())
    tokenizer = Tokenizer.from_file(info['tokenizer_path'])
    for family, tasks in groups.items():
        share = sum(t['expected_tokens'] for t in tasks) / manifest['summary']['total_tokens']
        if share < .02 or 'koolbardi' in family:
            continue
        rng = np.random.default_rng(int.from_bytes(family.encode(), 'little') % 2**64)
        weights = np.array([t['selected_rows'] * t['repeat'] for t in tasks], dtype=float)
        choices = rng.choice(len(tasks), size=10, p=weights / weights.sum())
        records = []
        for number, choice in enumerate(choices, 1):
            task = tasks[choice]
            path = ROOT / 'data/tokenized_dfm11' / task['name']
            arrays = {name: np.load(path / f'{name}.npy', mmap_mode='r')
                      for name in ('inst_start', 'inst_len', 'resp_start', 'resp_len', 'tokens')}
            il = arrays['inst_len']
            rl = arrays['resp_len']
            # Production sampler reserves one additional token for the AR shift.
            eligible = np.flatnonzero((rl >= 2) & (il < 4097) &
                                     ((il + rl <= 4097) if task['long_context'] != 'truncate' else True))
            idx = int(rng.choice(eligible))
            plen, rlen = int(il[idx]), min(int(rl[idx]), 4097 - int(il[idx]))
            ps, rs = int(arrays['inst_start'][idx]), int(arrays['resp_start'][idx])
            records.append(dict(number=number, family=family, task=task['name'], row=idx,
                                prompt_tokens=plen, response_tokens=rlen,
                                original_response_tokens=int(rl[idx]),
                                prompt=tokenizer.decode(arrays['tokens'][ps:ps+plen].tolist(), skip_special_tokens=False),
                                response=tokenizer.decode(arrays['tokens'][rs:rs+rlen].tolist(), skip_special_tokens=False)))
        (out / f'{family}.json').write_text(json.dumps(records, ensure_ascii=False, indent=2))
        lines = [f'# {family}', f'Original share: {share:.2%}', '']
        for r in records:
            lines += [f"## {r['number']}: {r['task']} row {r['row']}",
                      f"Tokens: prompt {r['prompt_tokens']}, response {r['response_tokens']}/{r['original_response_tokens']}",
                      '### Prompt', r['prompt'], '### Response', r['response'], '']
        (out / f'{family}.md').write_text('\n'.join(lines))
        print(family, f'{share:.2%}', flush=True)


if __name__ == '__main__':
    main()

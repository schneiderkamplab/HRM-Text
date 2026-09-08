#!/usr/bin/env python3
"""Uniform fixed-seed conversation sample from the pinned Koolbardi packages."""
import gzip
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[1]


def main():
    out = ROOT / 'logs/dfm11_post/koolbardi_review_20260908'
    out.mkdir(parents=True, exist_ok=True)
    selected = []
    for language in ('da', 'en'):
        package = ROOT / f'exports_dfm11/dfm11-koolbardi-{language}'
        manifest = json.loads((package / 'metadata/manifest.json').read_text())
        rng = random.Random(f'20260908:{language}')
        wanted = set(rng.sample(range(manifest['rows']), 10))
        offset = 0
        found = []
        for entry in sorted(manifest['data_files'], key=lambda x: x['file']):
            with gzip.open(package / entry['file'], 'rt') as handle:
                for line_index, line in enumerate(handle):
                    if offset in wanted:
                        found.append(dict(language=language, ordinal=offset,
                                          file=entry['file'], line=line_index + 1,
                                          row=json.loads(line)))
                    offset += 1
            if len(found) == 10:
                break
        assert len(found) == 10
        for index, item in enumerate(found, 1):
            item['review_id'] = f'{language.upper()}{index:02}'
        selected.extend(found)
        print(language, 'sampled', len(found), flush=True)
    (out / 'rows.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in selected))
    text = ['# Koolbardi DA/EN: Random Conversation Sample', '',
            'Seed: `20260908:<language>`. Ten unique uniform global row ordinals per language.',
            'Full source conversations, not individual expanded assistant targets.', '']
    for item in selected:
        row = item['row']
        text.extend([f"## {item['review_id']}: {row['id']}", '',
                     f"Source: `{item['file']}`, line {item['line']}; global ordinal {item['ordinal']}.",
                     f"Controls: {json.dumps(row.get('diversity', {}), ensure_ascii=False)}", ''])
        for turn, message in enumerate(row['messages'], 1):
            text.extend([f"### Message {turn}: {message['role']}", '', message['content'], ''])
    (out / 'conversations.md').write_text('\n'.join(text))
    print(out, flush=True)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Rebuild DFM11 additions from pinned public packages, without sampling."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import subprocess
import sys

import yaml
from huggingface_hub import snapshot_download

from prepare_dfm11_fineinstructions_english import balanced_quotas, rank_value

ROOT = Path(__file__).resolve().parents[1]


def rows(directory):
    for path in sorted(directory.glob('*.jsonl.gz')):
        with gzip.open(path, 'rt') as handle:
            for line in handle:
                yield json.loads(line)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=64)
    args = parser.parse_args()
    packages = ROOT / 'exports_dfm11'
    staging = ROOT / 'data/converted_dfm11_hub'
    staging.mkdir(parents=True, exist_ok=True)
    configs = {}
    for name in ('tool_replacements', 'mathagentic', 'koolbardi',
                 'fineinstructions_english', 'fineinstructions_danish'):
        config = yaml.safe_load((ROOT / f'config/data/dfm11_{name}.yaml').read_text())
        configs[name] = config
        sources = config.get('sources', {'source': config.get('source')})
        for source in sources.values():
            destination = packages / source['repo_id'].split('/')[-1]
            print('Downloading', source['repo_id'], source['revision'], flush=True)
            snapshot_download(repo_id=source['repo_id'], repo_type='dataset',
                              revision=source['revision'], local_dir=destination,
                              max_workers=16)
            if not name.startswith('fineinstructions'):
                link = staging / destination.name
                if not link.exists():
                    link.symlink_to(destination, target_is_directory=True)

    en = packages / 'dfm11-fineinstructions-en'
    styles = {str(r['pair_id']): r['continuation_style']
              for r in rows(en / 'metadata/chat_selection')}
    candidates = {}
    for pair in rows(en / 'pairs'):
        pid = str(pair['id'])
        if styles[pid] == 'legacy':
            source = pair['document_provenance']['source_id']
            candidates.setdefault(source, []).append(pid)
    quotas = balanced_quotas(Counter({s: len(v) for s, v in candidates.items()}), 100000)
    seed = configs['fineinstructions_english']['seed']
    selected = {pid for source, ids in candidates.items()
                for pid in sorted(ids, key=lambda p: rank_value(seed, source, p))[:quotas[source]]}
    assert len(selected) == 100000

    for language in ('en', 'da'):
        counts = Counter()
        handles = {}
        temporary = []
        try:
            for chat in rows(packages / f'dfm11-fineinstructions-{language}' / 'chats'):
                pid = str(chat['pair_id'])
                if language == 'en':
                    style = styles[pid]
                    if style == 'legacy' and pid not in selected:
                        continue
                    name = 'dfm11-fineinstructions-en-' + ('controlled' if style == 'controlled' else 'legacy-balanced')
                else:
                    name = 'dfm11-fineinstructions-da'
                shard = counts[name] // 50000
                key = (name, shard)
                if key not in handles:
                    directory = staging / name / 'data'
                    directory.mkdir(parents=True, exist_ok=True)
                    final = directory / f'train-{shard:05d}.jsonl.gz'
                    temp = final.with_suffix('.gz.tmp')
                    handles[key] = gzip.open(temp, 'wt')
                    temporary.append((temp, final))
                handles[key].write(json.dumps(chat, ensure_ascii=False) + '\n')
                counts[name] += 1
        finally:
            for handle in handles.values():
                handle.close()
        expected = 416022 if language == 'en' else 503740
        if sum(counts.values()) != expected:
            raise ValueError(f'{language}: {counts}, expected {expected}')
        for temp, final in temporary:
            temp.replace(final)
        print('Prepared', dict(counts), flush=True)

    info = json.loads((ROOT / 'data/tokenized_dfm10/tokenizer_info.json').read_text())
    command = [sys.executable, str(ROOT / 'scripts/tokenize_chat_template.py'), str(staging),
               '--tokenizer-path', info['tokenizer_path'], '--chat-template', info['chat_template_path'],
               '--output-dir', 'data/tokenized_dfm11_additions', '--max-seq-len', '4096',
               '--workers', str(args.workers)]
    print('Starting tokenizer:', command, flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


if __name__ == '__main__':
    main()

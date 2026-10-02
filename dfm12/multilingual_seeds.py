"""Bounded, deterministic seed reservoirs for the multilingual pilot."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import random

from .catalog import selected_source
from .io import digest, file_hash, rows, write_json

LANGUAGES = {'nb': 'Norwegian Bokmal', 'nn': 'Norwegian Nynorsk', 'is': 'Icelandic',
             'fo': 'Faroese', 'nl': 'Dutch', 'sv': 'Swedish', 'pl': 'Polish'}


def native(language, count=9000):
    import pyarrow.parquet as pq
    root = Path('data/dfm12')
    name = 'dynaword-' + ('no' if language in ('nb', 'nn') else language)
    source = selected_source(root, name)
    files = source['files']
    if language in ('nb', 'nn'):
        mapping = source['review_receipt']['language_by_file']
        files = [f for f in files if mapping.get(f) == language]
    rng = random.Random('dfm12-multilingual-v1/' + language)
    groups = []
    for relative in files:
        path = root / 'downloads' / name / relative
        if path.exists() and path.suffix == '.parquet':
            parquet = pq.ParquetFile(path)
            groups.extend((relative, i) for i in range(parquet.num_row_groups))
    rng.shuffle(groups)
    result, seen = [], set()
    # Read randomly ordered row groups, stratified with a cap per group. Never
    # use only a file prefix; report supply shortfalls instead of repetition.
    per_group = max(50, (count * 3 + len(groups) - 1) // max(1, len(groups)))
    for relative, group in groups:
        parquet = pq.ParquetFile(root / 'downloads' / name / relative)
        columns = [c for c in ('id', 'text', 'source') if c in parquet.schema_arrow.names]
        batch = parquet.read_row_group(group, columns=columns).to_pylist()
        indices = list(range(len(batch)))
        rng.shuffle(indices)
        kept = 0
        for index in indices:
            text = batch[index].get('text')
            if not isinstance(text, str) or len(text) < 600:
                continue
            # Preserve contiguous native text, with random windows in long docs.
            start = rng.randrange(max(1, len(text) - 2400))
            if start:
                boundary = text.find(' ', start)
                start = boundary + 1 if boundary >= 0 else start
            passage = text[start:start + 2400].rsplit(' ', 1)[0].strip()
            key = digest(passage)
            if key in seen or len(passage) < 500:
                continue
            seen.add(key)
            result.append({'text': passage, 'id': key, 'repo': source['repo'],
                'revision': source['revision'], 'file': relative, 'row_group': group,
                'row_in_group': index, 'source_id': batch[index].get('id'), 'offset': start})
            kept += 1
            if kept >= per_group or len(result) >= count:
                break
        if len(result) >= count:
            break
    if len(result) < 2500:
        raise ValueError(f'Insufficient native seed supply for {language}: {len(result)}')
    return language, result


def openhermes(count=12000):
    rng = random.Random('dfm12-multilingual-v1/openhermes')
    reservoir, eligible = [], 0
    paths = sorted(Path('data/dfm11_source_cache').glob('dfm8-openhermes-*/data/*.jsonl.gz'))
    if not paths:
        raise ValueError('Modernized OpenHermes source files missing')
    for path in paths:
        for ordinal, row in enumerate(rows(path)):
            messages = row.get('messages')
            if not isinstance(messages, list) or row.get('tools'):
                continue
            if any(m.get('role') not in ('user', 'assistant') for m in messages):
                continue
            text = json.dumps(messages, ensure_ascii=False)
            if not 100 < len(text) < 6500:
                continue
            eligible += 1
            index = rng.randrange(eligible)
            record = {'messages': messages, 'id': digest(messages),
                'repo': 'schneiderkamplab/' + path.parent.parent.name,
                'file': str(path), 'ordinal': ordinal}
            if len(reservoir) < count:
                reservoir.append(record)
            elif index < count:
                reservoir[index] = record
    if len(reservoir) < count:
        raise ValueError('Insufficient modernized OpenHermes seeds')
    return reservoir


def prepare(root):
    root.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        oh = pool.submit(openhermes)
        native_jobs = [pool.submit(native, lang) for lang in LANGUAGES]
        for job in native_jobs:
            lang, data = job.result()
            write_json(root / f'seeds-{lang}.json', data)
            print('Native seeds', lang, len(data), flush=True)
        write_json(root / 'seeds-openhermes.json', oh.result())
    write_json(root / 'seeds-ready.json', {p.name: file_hash(p) for p in root.glob('seeds-*.json')
               if p.name != 'seeds-ready.json'})


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--root', type=Path, required=True)
    prepare(parser.parse_args().root)

#!/usr/bin/env python3
"""Pinned Baltic downloads, original-text reuse and audit-gated SFT preparation."""
import argparse
from collections import Counter
import csv
import gzip
import json
from pathlib import Path
import shutil
import sqlite3

from dfm12.io import digest, file_hash, load, lock, write_json
from dfm12.multilingual_production_seeds import SCHEMA, insert, native_window
from dfm12.records import validate_messages

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config/dfm13_baltic_sources.json'


def records(path):
    if path.suffix == '.parquet':
        import pyarrow.parquet as pq
        for batch in pq.ParquetFile(path).iter_batches(batch_size=128):
            yield from batch.to_pylist()
    elif path.suffix == '.csv':
        with path.open(newline='', encoding='utf-8-sig') as f:
            yield from csv.DictReader(f)
    elif path.suffix == '.jsonl' or path.name.endswith('.jsonl.gz'):
        with (gzip.open(path, 'rt') if path.suffix == '.gz' else path.open()) as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)
    else:
        yield from load(path)


def messages(row, kind):
    if kind == 'aya':
        if row['language_code'] != 'lit':
            return None
        question, answer = row['inputs'], row['targets']
    elif kind == 'qa':
        question, answer = row['question'], row['answer']
    elif kind == 'chat':
        result = row['messages']
        if len(result) < 2 or len(result) % 2:
            raise ValueError('Incomplete conversation')
        for i, turn in enumerate(result):
            if turn.get('role') != ('user' if i % 2 == 0 else 'assistant'):
                raise ValueError('Unexpected conversation role')
            if not isinstance(turn.get('content'), str) or not turn['content'].strip():
                raise ValueError('Empty message')
        return result
    elif kind == 'summary':
        question = 'Pateikite šio teksto santrauką lietuvių kalba:\n\n' + row['text']
        answer = row['summary_abstract']
    else:
        raise ValueError(kind)
    if not all(isinstance(x, str) and x.strip() for x in (question, answer)):
        raise ValueError('Blank prompt/answer')
    return [dict(role='user', content=question), dict(role='assistant', content=answer)]


def local_sources(root, config):
    receipts = []
    for manifest_path in config['local_source_manifests']:
        for source in load(manifest_path)['sources']:
            original = Path(source['path'])
            expected = source['sha256']
            if file_hash(original) != expected:
                raise ValueError('DaLA original source changed: ' + str(original))
            destination = root / 'documents' / (source['name'] + '.jsonl')
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                temporary = destination.with_suffix('.partial')
                shutil.copyfile(original, temporary)
                if file_hash(temporary) != expected:
                    raise ValueError('Source copy hash mismatch')
                temporary.replace(destination)
            if file_hash(destination) != expected:
                raise ValueError('Existing source copy changed')
            n = chars = 0
            for row in records(destination):
                n += 1
                chars += len(row['text'])
            receipts.append(dict(source, path=str(destination), original_path=str(original),
                rows=n, text_characters=chars, dala_source_holdouts_included=True,
                source_manifest=manifest_path, source_manifest_sha256=file_hash(manifest_path)))
    write_json(root / 'local-sources.json', receipts)
    return receipts


def download(root, source):
    from huggingface_hub import snapshot_download
    folder = root / 'downloads' / source['name']
    snapshot_download(source['repo'], repo_type='dataset', revision=source['revision'],
        allow_patterns=source['patterns'], local_dir=folder, max_workers=2)
    files = [p for p in sorted(folder.rglob('*')) if p.is_file() and '.cache' not in p.parts]
    data = [p for p in files if p.suffix in {'.parquet', '.csv', '.json'}]
    if not data:
        raise ValueError('No downloaded data: ' + source['name'])
    receipt = dict(source, files=[dict(path=str(p), bytes=p.stat().st_size,
                                     sha256=file_hash(p)) for p in files])
    write_json(root / 'receipts' / (source['name'] + '.json'), receipt)
    return data


def convert(root, source, files):
    output = root / 'audit-candidates' / (source['name'] + '.jsonl')
    output.parent.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    seen = set()
    with output.with_suffix('.partial').open('w') as f, output.with_suffix('.rejected.jsonl').open('w') as rejected:
        for path in files:
            sha = file_hash(path)
            for index, row in enumerate(records(path)):
                provenance = dict(repo=source['repo'], revision=source['revision'],
                    file=str(path), file_sha256=sha, row=index)
                try:
                    turns = messages(row, source['kind'])
                    if turns is None:
                        counts['other_language'] += 1
                        continue
                    validate_messages(turns)
                    key = digest(turns)
                    if key in seen:
                        counts['duplicate'] += 1
                        continue
                    seen.add(key)
                    candidate = dict(id=key, language=source['language'], messages=turns,
                        provenance=provenance, source=source['name'], tools=[],
                        chat_template_kwargs={'enable_thinking': False},
                        audit_status='pending', admission_authorized=False)
                    f.write(json.dumps(candidate, ensure_ascii=False) + '\n')
                    counts['candidates'] += 1
                except (ValueError, KeyError, TypeError) as e:
                    counts['invalid'] += 1
                    rejected.write(json.dumps(dict(provenance=provenance, reason=str(e))) + '\n')
    output.with_suffix('.partial').replace(output)
    receipt = dict(source, output=str(output), output_sha256=file_hash(output), counts=dict(counts),
        repeat=1, status='pending_audit', training_ready=False)
    write_json(root / 'receipts' / (source['name'] + '-converted.json'), receipt)
    print(json.dumps(dict(source=source['name'], **counts)), flush=True)
    return receipt


def prepare_seeds(root, receipts, oh_root):
    """Build a fresh atomic seed database; keep all copied source documents intact."""
    from dfm12.european_synthetic_seeds import oh_payload
    seed_root = root / 'seeds'
    seed_root.mkdir(exist_ok=True)
    temporary = seed_root / 'seeds.building.sqlite'
    temporary.unlink(missing_ok=True)
    db = sqlite3.connect(temporary)
    db.executescript(SCHEMA)
    db.executemany('INSERT INTO languages VALUES (?)', [('lt',), ('lv',)])
    counts = Counter()
    try:
        for source in receipts:
            for row in records(Path(source['path'])):
                identity = [source['name'], row['source_document_id']]
                # Paragraph groups permit multiple windows from very long sittings.
                chunks = row['text'].split('\n') if source['name'].startswith('Europarl') else [row['text']]
                for index, text in enumerate(chunks):
                    selected = native_window(text, digest([identity, index]))
                    if selected is None:
                        continue
                    window, offset = selected
                    payload = dict(id=digest([identity, index, window]), text=window,
                        language=source['language'], source_document_id=row['source_document_id'],
                        source=source['name'], source_sha256=source['sha256'],
                        paragraph_index=index, offset=offset, document_url=row.get('url'),
                        dala_source_holdouts_included=True, generation_and_review_required=True)
                    if insert(db, source['language'], payload, digest([identity,index]), digest(window)):
                        counts[source['language']] += 1
            db.commit()
        for path in sorted([*oh_root.rglob('*.parquet'), *oh_root.rglob('*.jsonl.gz')]):
            sha = file_hash(path)
            for ordinal, row in enumerate(records(path)):
                payload, _ = oh_payload(row, path, ordinal, sha)
                if payload and insert(db, 'openhermes', payload, payload['id'], payload['id']):
                    counts['openhermes'] += 1
                if counts['openhermes'] >= 100000:
                    break
            db.commit()
            if counts['openhermes'] >= 100000:
                break
    finally:
        db.close()
    temporary.replace(seed_root / 'seeds.sqlite')
    write_json(seed_root / 'receipt.json', dict(counts=counts,
        sha256=file_hash(seed_root / 'seeds.sqlite'), policy='all_original_dala_source_documents_eligible',
        ready=all(counts[k] >= n for k,n in [('lt',30000),('lv',30000),('openhermes',15000)])))
    print('Seed inventory:', dict(counts), flush=True)


def shuffle_seeds(root):
    """Deterministic global hash order prevents the first source dominating slots."""
    selections = root/'synthetic/spec-selections.sqlite'
    if selections.exists():
        with sqlite3.connect(selections.as_uri()+'?mode=ro', uri=True) as db:
            if db.execute('SELECT 1 FROM selections LIMIT 1').fetchone():
                raise ValueError('Cannot reorder seeds after allocations')
    path = root/'seeds/seeds.sqlite'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TEMP TABLE ordering AS SELECT pool,source_id,ROW_NUMBER() OVER(PARTITION BY pool ORDER BY source_id) AS position FROM seeds')
        db.execute('CREATE UNIQUE INDEX ordering_key ON ordering(pool,source_id)')
        db.execute('UPDATE seeds SET seq=-seq')
        db.execute('UPDATE seeds SET seq=(SELECT position FROM ordering WHERE ordering.pool=seeds.pool AND ordering.source_id=seeds.source_id)')
    receipt = load(root/'seeds/receipt.json')
    receipt.update(sha256=file_hash(path), order='global_source_hash_within_pool')
    write_json(root/'seeds/receipt.json',receipt)


def register(root, config):
    registry = ROOT / 'config/dfm13_sources.json'
    with lock(registry.with_suffix('.lock')):
        data = load(registry)
        preparations = data.setdefault('preparations', {})
        preparations['baltic'] = dict(config=str(CONFIG), config_sha256=file_hash(CONFIG),
            root=str(root), status='audit_gated_preparation', training_ready=False,
            languages=['lt','lv'], synthetic_accepted_targets={'lt':70000,'lv':70000},
            dala_source_holdout_policy=config['dala_source_holdout_policy'])
        write_json(registry, data)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=ROOT/'data/dfm13/baltic')
    p.add_argument('--local-only', action='store_true')
    p.add_argument('--oh-root', type=Path, default=ROOT/'data/dfm11_source_cache/dfm8-openhermes-en')
    args = p.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    config = load(CONFIG)
    with lock(root/'prepare.lock'):
        receipts = local_sources(root, config)
        prepare_seeds(root, receipts, args.oh_root)
        shuffle_seeds(root)
        register(root, config)
        if not args.local_only:
            for source in config['sources']:
                print('Downloading', source['name'], flush=True)
                files = download(root, source)
                if source['kind'] != 'text':
                    convert(root, source, files)
        write_json(root/'preparation.json', dict(status='local_ready' if args.local_only else 'downloaded_and_prepared',
            training_ready=False, synthetic_generation_started=False, dala_modified=False))


if __name__ == '__main__':
    main()

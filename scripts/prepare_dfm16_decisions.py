"""Convert and tokenize DFM16 additions, without invoking any sampler."""
import argparse
from collections import Counter
from contextlib import ExitStack
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys

import ijson
import jinja2
import numpy as np
import pyarrow.parquet as pq
from tokenizers import Tokenizer

from scripts.dfm16_decision_adapters import Reject, adapt
from scripts.tokenize_chat_template import examples_from_messages, tokenize_example


def rows(path):
    if path.suffix == '.parquet':
        for batch in pq.ParquetFile(path).iter_batches(batch_size=64):
            yield from batch.to_pylist()
    elif path.suffix == '.jsonl':
        with path.open() as stream:
            for line in stream:
                if line.strip():
                    yield json.loads(line)
    elif path.suffix == '.json':
        with path.open('rb') as stream:
            yield from ijson.items(stream, 'item', use_float=True)
    else:
        raise ValueError(f'Unsupported file: {path}')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def semantic_key(repo, row, converted):
    if repo in ('nvidia/OpenScienceReasoning-2', 'nvidia/Nemotron-RL-knowledge-mcqa'):
        prompt = row['input'] if 'input' in row else row['responses_create_params']['input'][-1]['content']
        # Remove only the recognized instruction prefix, not problem text/options.
        if prompt.startswith(('Solve the following problem.', 'Answer the following multiple choice question.')):
            prompt = prompt.split('\n\n', 1)[-1]
        return 'science:' + fingerprint(' '.join(prompt.split()).casefold())
    return 'messages:' + fingerprint({k: converted[k] for k in ('messages', 'tools', 'target_message_index') if k in converted})


def validate(example):
    messages = example['messages']
    if not messages or messages[-1]['role'] != 'assistant':
        raise Reject('missing_assistant_target')
    names = {t['function']['name'] for t in example.get('tools', [])}
    calls = {}
    for message in messages:
        if message['role'] not in ('system', 'user', 'assistant', 'tool'):
            raise Reject('unknown_role')
        if not isinstance(message.get('content'), str):
            raise Reject('nontext_content')
        for call in message.get('tool_calls', []):
            if call['function']['name'] not in names or not isinstance(call['function']['arguments'], dict):
                raise Reject('invalid_native_call')
            calls[call['id']] = call['function']['name']
        if message['role'] == 'tool' and calls.get(message.get('tool_call_id')) != message.get('name'):
            raise Reject('unmatched_tool_response')
    target = messages[-1]
    if not target['content'].strip() and not target.get('tool_calls'):
        raise Reject('empty_target')


def convert_source(source, root, db, version, tok, template, workers):
    name, repo = source['name'], source['repo_id']
    out = root / name
    receipt_path = out / 'conversion.json'
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        if receipt['version'] != version:
            raise RuntimeError(f'{name}: changed converter; use a new --output to preserve provenance')
        return receipt
    stage = root / ('.' + name + '.partial')
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()
    counts, rejected = Counter(), Counter()
    outputs = {}
    demos = []
    db.execute('BEGIN')
    try:
        with ExitStack() as stack:
            reject_log = stack.enter_context((stage / 'rejected.jsonl').open('w'))
            for file in source['files']:
                path = Path(source['local_snapshot']) / file['path']
                if path.stat().st_size != file['bytes']:
                    raise RuntimeError(f'Source size changed: {path}')
                for index, row in enumerate(rows(path)):
                    counts['source_rows'] += 1
                    key = str(row.get('id', row.get('uuid', index)))
                    locator = dict(file=file['path'], row=index, id=key)
                    try:
                        examples = adapt(repo, row, key)
                    except Reject as exc:
                        rejected[str(exc)] += 1
                        reject_log.write(json.dumps(locator | {'reason': str(exc)}) + '\n')
                        continue
                    except (KeyError, TypeError, ValueError) as exc:
                        reason = 'schema:' + type(exc).__name__ + ':' + str(exc)[:200]
                        rejected[reason] += 1
                        reject_log.write(json.dumps(locator | {'reason': reason}) + '\n')
                        continue
                    for example in examples:
                        try:
                            validate(example)
                        except Reject as exc:
                            rejected[str(exc)] += 1
                            reject_log.write(json.dumps(locator | {'reason': str(exc)}) + '\n')
                            continue
                        thinking = any(m.get('reasoning_content') for m in example['messages'])
                        mode = 'thinking' if thinking else 'direct'
                        digest = semantic_key(repo, row, example)
                        if db.execute('INSERT OR IGNORE INTO seen VALUES (?,?)', (digest, name)).rowcount == 0:
                            rejected['duplicate_in_additions'] += 1
                            reject_log.write(json.dumps(locator | {'reason': 'duplicate_in_additions'}) + '\n')
                            continue
                        if len(demos) < 8:
                            parsed = list(examples_from_messages(example['messages'], example.get('tools'), example.get('target_message_index')))
                            if len(parsed) != 1 or tokenize_example(tok, template, parsed[0], thinking) is None:
                                raise RuntimeError(f'{name}: template prefix/target failure at {locator}')
                            demos.append(example)
                        example['provenance'] = dict(repo_id=repo, revision=source['revision'],
                            source_file=file['path'], source_file_sha256=file.get('sha256'),
                            source_row=index, source_id=key, original_split='unsplit' if repo=='bigcode/commitpackft' else 'train',
                            source_license=row.get('license', source.get('license_reported')),
                            group_id=row.get('group_id', row.get('annotation_id', row.get('item_id', key))))
                        shard = counts[mode] % workers
                        dest_key = (mode, shard)
                        if dest_key not in outputs:
                            directory = stage / 'input' / mode
                            directory.mkdir(parents=True, exist_ok=True)
                            outputs[dest_key] = stack.enter_context((directory / f'part-{shard:05d}.jsonl').open('w'))
                        outputs[dest_key].write(json.dumps(example, ensure_ascii=False) + '\n')
                        counts[mode] += 1
                    if counts['source_rows'] % 10000 == 0:
                        print(name, dict(counts), dict(rejected), flush=True)
        if not counts['direct'] and not counts['thinking']:
            raise RuntimeError(f'{name}: zero converted targets; inspect {stage}/rejected.jsonl')
        receipt = dict(name=name, repo_id=repo, version=version, revision=source['revision'],
                       counts=dict(counts), rejected=dict(rejected), sampled=False,
                       overlap_scope='exact converted messages plus normalized question for science/MCQA within new additions only',
                       inherited_corpus_overlap_checked=False)
        (stage / 'conversion.json').write_text(json.dumps(receipt, indent=2)+'\n')
        (stage / 'examples.json').write_text(json.dumps(demos, indent=2, ensure_ascii=False)+'\n')
        # Commit dedup state only with a complete source; recovery drops stale keys if no receipt exists.
        stage.rename(out)
        db.commit()
        return receipt
    except BaseException:
        db.rollback()
        raise


def tokenize_source(out, meta, workers):
    for mode in ['direct', 'thinking']:
        source, target = out / 'input' / mode, out / 'tokenized' / mode
        if not source.exists():
            continue
        if not (target / 'completion.json').exists():
            cmd = [sys.executable, '-m', 'scripts.tokenize_chat_template', str(source), '-o', str(target),
                   '--tokenizer-path', meta['tokenizer_path'], '--chat-template', meta['chat_template_path'],
                   '--workers', str(workers)]
            if mode == 'thinking':
                cmd.append('--enable-thinking')
            subprocess.run(cmd, check=True, env={**os.environ, 'TOKENIZERS_PARALLELISM': 'false',
                           'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'})
    total = Counter()
    for path in (out / 'tokenized').glob('*/*/resp_len.npy'):
        resp = np.load(path, mmap_mode='r')
        inst = np.load(path.parent / 'inst_len.npy', mmap_mode='r')
        tokens = np.load(path.parent / 'tokens.npy', mmap_mode='r')
        assert len(inst) == len(resp) and int(inst.sum()+resp.sum()) == len(tokens)
        lengths = inst + resp
        total.update(rows=len(resp), tokens=len(tokens), over_4096=int((lengths>4096).sum()),
                     over_8192=int((lengths>8192).sum()))
    conversion = json.loads((out / 'conversion.json').read_text())
    expected = sum(conversion['counts'].get(m, 0) for m in ['direct', 'thinking'])
    if total['rows'] != expected:
        raise RuntimeError(f'{out}: {total["rows"]} tokenized targets != {expected} converted targets')
    summary = dict(total) | dict(sampled=False, repeat=1,
        tokenized_path=str((out / 'tokenized').resolve()),
        tokenizer_sha256=hashlib.file_digest(open(meta['tokenizer_path'], 'rb'), 'sha256').hexdigest(),
        template_sha256=hashlib.file_digest(open(meta['chat_template_path'], 'rb'), 'sha256').hexdigest())
    (out / 'prepared.json').write_text(json.dumps(summary, indent=2)+'\n')
    print('PREPARED', out.name, summary, flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=Path('data/dfm16/decisions-v1'))
    p.add_argument('--workers', type=int, default=64)
    p.add_argument('--only', help='Comma-separated repo IDs (default all)')
    args = p.parse_args()
    if args.workers < 1:
        p.error('positive workers required')
    args.output.mkdir(parents=True, exist_ok=True)
    registry = json.loads(Path('config/dfm16_decision_sources.json').read_text())
    meta = json.loads(Path('data/dfm15/native-reasoning-v2/sampled_dfm15/metadata.json').read_text())['tokenizer_info']
    tok = Tokenizer.from_file(meta['tokenizer_path'])
    template = jinja2.Environment().from_string(Path(meta['chat_template_path']).read_text())
    version = fingerprint([Path(__file__).read_text(), Path('scripts/dfm16_decision_adapters.py').read_text(), registry])
    with (args.output / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        db = sqlite3.connect(args.output / 'dedup.sqlite')
        db.execute('CREATE TABLE IF NOT EXISTS seen (key TEXT PRIMARY KEY, source TEXT)')
        for source in registry['sources']:
            if not (args.output / source['name'] / 'conversion.json').exists():
                db.execute('DELETE FROM seen WHERE source=?', (source['name'],))
        db.commit()
        # Prefer full science reasoning over the same question with label-only supervision.
        sources = sorted(registry['sources'], key=lambda s: s['repo_id'] != 'nvidia/OpenScienceReasoning-2')
        for source in sources:
            if args.only and source['repo_id'] not in args.only.split(','):
                continue
            print('START', source['repo_id'], flush=True)
            convert_source(source, args.output, db, version, tok, template, args.workers)
            tokenize_source(args.output / source['name'], meta, args.workers)
        db.close()
        print('COMPLETE: conversion/tokenization only; no sampler invoked.', flush=True)


if __name__ == '__main__':
    main()

"""Acquire the original ATOMIC archive and compare triples with inherited seeds."""
import argparse
from collections import Counter
import csv
import io
import json
from pathlib import Path
import sqlite3
import tarfile
import unicodedata
import urllib.request

from dfm12.io import atomic, digest, file_hash, lock, rows, write_json

URL = 'https://homes.cs.washington.edu/~msap/atomic/data/atomic_data.tgz'
RELATIONS = ('oEffect', 'oReact', 'oWant', 'xAttr', 'xEffect', 'xIntent', 'xNeed', 'xReact', 'xWant')


def normalized(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split()).rstrip('.')


def key(event, relation, tail):
    return digest([normalized(event), relation, normalized(tail)])


def run(root, inherited):
    root.mkdir(parents=True, exist_ok=True)
    with lock(root/'.lock'):
        archive = root/'atomic_data.tgz'
        if not archive.exists():
            partial = root/'atomic_data.tgz.part'
            if not partial.exists():
                urllib.request.urlretrieve(URL, partial)
            with tarfile.open(partial) as bundle:
                assert 'v4_atomic_trn.csv' in bundle.getnames()
            partial.replace(archive)
        archive_hash = file_hash(archive)
        counts = Counter()
        db = sqlite3.connect(':memory:')
        db.execute('create table inherited (key text primary key)')
        db.execute('create table seen (key text primary key)')
        for row in rows(inherited):
            for tail in row['plausible_completions']:
                db.execute('insert or ignore into inherited values (?)', (key(row['event'], row['relation'], tail),))
        counts['inherited_unique_triples'] = db.execute('select count(*) from inherited').fetchone()[0]
        with tarfile.open(archive) as bundle, atomic(root/'unique-train-relations.jsonl') as out:
            # Do not extract arbitrary archive paths or silently admit evaluation splits.
            for split, filename in [('train', 'v4_atomic_trn.csv'), ('validation', 'v4_atomic_dev.csv'), ('test', 'v4_atomic_tst.csv')]:
                for ordinal, row in enumerate(csv.DictReader(io.TextIOWrapper(bundle.extractfile(filename), encoding='utf-8'))):
                    counts[split+'_events'] += 1
                    for relation in RELATIONS:
                        unique = []
                        for tail in json.loads(row[relation]):
                            if normalized(tail) in ('', 'none', 'nan'):
                                continue
                            k = key(row['event'], relation, tail)
                            counts[split+'_triples'] += 1
                            if db.execute('select 1 from inherited where key=?', (k,)).fetchone():
                                counts[split+'_overlap_triples'] += 1
                            elif split == 'train':
                                if db.execute('insert or ignore into seen values (?)', (k,)).rowcount:
                                    unique.append(tail)
                                    counts['train_unique_new_triples'] += 1
                                else:
                                    counts['train_duplicate_new_triples'] += 1
                        if unique:
                            record = dict(event=row['event'], relation=relation, plausible_completions=unique,
                                language='en', training_ready=False,
                                provenance=dict(repo='allenai/atomic', url=URL, archive_sha256=archive_hash,
                                                split='train', row=ordinal))
                            record['id'] = digest([record['event'], relation, unique])
                            out.write(json.dumps(record, ensure_ascii=False)+'\n')
                            counts['new_relation_seeds'] += 1
        write_json(root/'overlap.json', dict(counts=dict(counts), url=URL,
            archive_sha256=file_hash(archive), inherited=str(inherited), inherited_sha256=file_hash(inherited),
            comparison='NFKC, casefold, whitespace, terminal period normalized triples; not semantic paraphrase overlap',
            training_ready=False, note='Overlap is against prepared inherited seed evidence, not a claim that every seed was trained.'))
        db.close()
        print(json.dumps(dict(counts)), flush=True)
        prepare_candidates(root, inherited)


def prepare_candidates(root, inherited):
    from scripts.prepare_dfm16_dyna import publish_audit_manifest
    descriptions = {r['relation']: r['relation_description'] for r in rows(inherited)}
    out = root.parents[1]/'converted/allenai__atomic'
    if (out/'readiness.json').exists():
        return
    records = []
    for row in rows(root/'unique-train-relations.jsonl'):
        prompt = ('Consider this hypothetical event: '+row['event']+'\n'+descriptions[row['relation']]
                  +'\nGive plausible possibilities, not certain facts. Keep PersonX/PersonY as placeholders and do not invent missing details.')
        response = 'Plausible possibilities include:\n'+'\n'.join('- '+v for v in row['plausible_completions'])
        records.append(dict(id=row['id'], audit_id=row['id'], language='en', task='commonsense',
            messages=[dict(role='user', content=prompt), dict(role='assistant', content=response)],
            provenance=row['provenance'], training_ready=False))
    name = 'chunks/00000.jsonl'
    with atomic(out/name) as stream:
        for row in records:
            stream.write(json.dumps(row, ensure_ascii=False)+'\n')
    chunks = [dict(job_id='atomic-00000', input=name, rows=len(records), task='commonsense',
                   sha256=file_hash(out/name))] if records else []
    write_json(out/'conversion.json', dict(counts=dict(audit_candidates=len(records)),
        overlap_report=str(root/'overlap.json'), training_ready=False))
    publish_audit_manifest(out, chunks)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('data/dfm16/expansion-v1/downloads/allenai__atomic'))
    parser.add_argument('--inherited', type=Path, default=Path('data/dfm14/knowledge-pilot-v1/atomic-train-relations.jsonl'))
    args = parser.parse_args()
    run(args.root, args.inherited)

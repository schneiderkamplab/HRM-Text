"""Read-only accepted-ledger sample; writes only this review directory."""
import json
import sqlite3
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq

from dfm12.io import digest, file_hash, load, write_json
from dfm12.transform import window
from dfm12.wave4_transforms import transform

OUT = Path(__file__).resolve().parent
ROOT = Path('data/dfm13/wave4')
TASKS = ('denoising', 'paragraph-reordering', 'prefix-continuation', 'span-filling')


def main():
    assert not (OUT / 'evidence.json').exists(), 'Preserve frozen evidence'
    evidence, availability, pins = [], {}, {}
    for lang in ('sl', 'sq', 'sr'):
        ledger = ROOT / 'release' / f'wikipedia-{lang}' / 'ledger.sqlite'
        db = sqlite3.connect(ledger.resolve().as_uri() + '?mode=ro', uri=True)
        db.execute('BEGIN')
        availability[lang] = dict(db.execute('SELECT status,count(*) FROM rows GROUP BY status'))
        counts = Counter()
        for key, raw, review in db.execute("SELECT id,record,review FROM rows WHERE status='accepted' ORDER BY id"):
            row = json.loads(raw)
            task = row['task']
            if task not in TASKS or counts[task] >= 4:
                continue
            counts[task] += 1
            evidence.append(dict(case=len(evidence), language=lang, task=task,
                id=key, record=row, record_sha256=digest(row),
                acceptance_review=json.loads(review), ledger=str(ledger)))
            if all(counts[t] == 4 for t in TASKS):
                break
        db.rollback()
        db.close()
        availability[lang]['sample_counts'] = dict(counts)
        receipt = ROOT / 'transforms' / f'wikipedia-{lang}' / 'receipt.json'
        pins[str(receipt)] = file_hash(receipt)
        pins.update(load(receipt)['inputs'])
    wanted = {}
    for item in evidence:
        p = item['record']['provenance']
        path = ROOT / 'downloads' / f'wikipedia-{item["language"]}' / p['file']
        wanted.setdefault(str(path), set()).add(p['row'])
    docs = {}
    for path, indices in wanted.items():
        assert file_hash(path) == pins[path]
        offset = 0
        for batch in pq.ParquetFile(path).iter_batches(batch_size=256):
            for idx in indices:
                if offset <= idx < offset + len(batch):
                    docs[(path, idx)] = batch.slice(idx-offset, 1).to_pylist()[0]
            offset += len(batch)
            if offset > max(indices):
                break
    for item in evidence:
        row = item['record']; p = row['provenance']
        path = str(ROOT / 'downloads' / f'wikipedia-{item["language"]}' / p['file'])
        source = docs[(path, p['row'])]
        selected = window(source['text'], p['window_seed'], max_chars=4500)
        replay = transform(selected, item['language'], row['task'], p, row['audit_context']['seed'])
        checks = dict(source_identity=all(source[k] == p[k] for k in ('id','url','title')),
            window_matches=selected == row['audit_context']['original'],
            id_matches=replay['id'] == row['id'], messages_match=replay['messages'] == row['messages'])
        assert all(checks.values()), checks
        item.update(source_document=source, source_path=path, checks=checks)
    write_json(OUT / 'evidence.json', evidence)
    write_json(OUT / 'snapshot.json', dict(availability=availability, pins=pins,
        selection='First four accepted IDs lexicographically per task in each read transaction',
        evidence_sha256=file_hash(OUT / 'evidence.json')))
    for lang in ('sl', 'sq'):
        lines = []
        for item in evidence:
            if item['language'] != lang:
                continue
            row = item['record']
            lines.extend([f"## Case {item['case']} {item['task']}: {row['provenance']['title']}",
                f"ID: {item['id']}"])
            for message in row['messages']:
                lines.extend([f"### {message['role']}", message['content']])
        (OUT / f'{lang}-read.md').write_text('\n\n'.join(lines))
    print(json.dumps(availability))


if __name__ == '__main__':
    main()

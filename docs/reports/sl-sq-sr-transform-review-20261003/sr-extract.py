"""Add a separate immutable Serbian accepted-row snapshot after audits progress."""
import json
from pathlib import Path
import sqlite3
import pyarrow.parquet as pq
from dfm12.io import digest, file_hash, load, write_json
from dfm12.transform import window
from dfm12.wave4_transforms import transform


def main():
    out = Path(__file__).resolve().parent / 'sr-followup'
    assert not out.exists()
    root = Path('data/dfm13/wave4')
    ledger = root/'release/wikipedia-sr/ledger.sqlite'
    db = sqlite3.connect(ledger.resolve().as_uri()+'?mode=ro',uri=True)
    db.execute('BEGIN')
    counts = dict(db.execute('SELECT status,count(*) FROM rows GROUP BY status'))
    groups = {t:[] for t in ('denoising','paragraph-reordering','prefix-continuation','span-filling')}
    for key,raw,review in db.execute("SELECT id,record,review FROM rows WHERE status='accepted' ORDER BY id"):
        row=json.loads(raw)
        if row['task'] in groups and len(groups[row['task']]) < 4:
            groups[row['task']].append(dict(id=key,record=row,record_sha256=digest(row),acceptance_review=json.loads(review)))
        if all(len(v)==4 for v in groups.values()): break
    db.rollback();db.close()
    assert all(len(v)==4 for v in groups.values())
    evidence=[x for g in groups.values() for x in g]
    pins=load(root/'transforms/wikipedia-sr/receipt.json')['inputs']
    wanted={}
    for item in evidence:
        p=item['record']['provenance']; path=str(root/'downloads/wikipedia-sr'/p['file'])
        wanted.setdefault(path,set()).add(p['row'])
    docs={}
    for path,indices in wanted.items():
        assert file_hash(path)==pins[path]
        offset=0
        for batch in pq.ParquetFile(path).iter_batches(batch_size=256):
            for idx in indices:
                if offset<=idx<offset+len(batch): docs[(path,idx)]=batch.slice(idx-offset,1).to_pylist()[0]
            offset+=len(batch)
            if offset>max(indices): break
    for i,item in enumerate(evidence):
        row=item['record'];p=row['provenance']; path=str(root/'downloads/wikipedia-sr'/p['file'])
        source=docs[(path,p['row'])]; selected=window(source['text'],p['window_seed'],max_chars=4500)
        replay=transform(selected,'sr',row['task'],p,row['audit_context']['seed'])
        assert all(source[k]==p[k] for k in ('id','url','title'))
        assert selected==row['audit_context']['original'] and replay['id']==row['id'] and replay['messages']==row['messages']
        item.update(case=32+i,source_document=source,source_path=path,source_replay_exact=True)
    write_json(out/'evidence.json',evidence)
    write_json(out/'snapshot.json',dict(counts=counts,source_pins=pins,evidence_sha256=file_hash(out/'evidence.json'),
        selection='First four accepted IDs lexicographically per task in one read transaction'))
    for task,items in groups.items():
        lines=[]
        for item in items:
            row=item['record'];lines.extend([f"## Case {item['case']}: {row['provenance']['title']}",f"ID: {item['id']}"])
            for message in row['messages']: lines.extend([f"### {message['role']}",message['content']])
        (out/(task+'.md')).write_text('\n\n'.join(lines))
    print(counts)


if __name__ == '__main__': main()

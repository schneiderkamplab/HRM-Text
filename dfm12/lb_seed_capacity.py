"""Offline LB seed capacity study; never appends to production pools."""
from collections import Counter
import json
from pathlib import Path
import sqlite3
from .io import load, rows, digest, file_hash, write_json, atomic
from .multilingual_production_seeds import native_window

ROOT=Path('data/dfm13/wave4/lb-seed-capacity-20261003')


def nonoverlap(a,b):
    return a[1]<=b[0] or b[1]<=a[0]


def main():
    if ROOT.exists():raise ValueError('Immutable study exists')
    source=Path('data/dfm13/wave4/downloads/wikipedia-lb');pin=load(source/'wave4-download.json')
    seed_path=Path('data/dfm13/wave4/seeds/seeds.sqlite')
    seen=set();existing={}
    with sqlite3.connect(seed_path.resolve().as_uri()+'?mode=ro',uri=True) as db:
        for raw, in db.execute("SELECT payload FROM seeds WHERE pool='lb'"):
            r=json.loads(raw);seen.add(digest(r['text']))
            existing[str(r['source_document_id'])]=(r['offset'],r['offset']+len(r['text']))
    counts=Counter(existing_documents=len(existing));inputs={}
    with atomic(ROOT/'candidate-windows.jsonl') as out:
        for path in sorted(source.glob(pin['config']+'/*.parquet')):
            sha=file_hash(path);inputs[str(path)]=sha
            for row in rows(path):
                counts['documents_scanned']+=1;text=row['text'];doc=str(row['id'])
                if 300<=len(text)<500:counts['short_documents_300_499_not_admitted']+=1
                intervals=[existing[doc]] if doc in existing else []
                emitted=0
                for variant in range(12):
                    selected=native_window(text,digest(['lb-capacity-v1',doc,variant]))
                    if selected is None:break
                    window,offset=selected;interval=(offset,offset+len(window));key=digest(window)
                    if key in seen or not all(nonoverlap(interval,old) for old in intervals):continue
                    if sum(c.isalpha() for c in window)/len(window)<.6:continue
                    kind='additional_window_same_document' if doc in existing else 'new_document_candidate'
                    out.write(json.dumps(dict(id=key,text=window,language='lb',kind=kind,
                        parent_document_id=doc,offset=offset,end=interval[1],variant=variant,
                        source=pin['repo'],revision=pin['revision'],config=pin['config'],source_sha256=sha,
                        url=row.get('url'),license='cc-by-sa-3.0',
                        admission_authorized=False,production_pool_appended=False,
                        review_required=True),ensure_ascii=False)+'\n')
                    counts[kind]+=1;seen.add(key);intervals.append(interval);emitted+=1
                    if emitted>=2:break
    write_json(ROOT/'receipt.json',dict(counts=counts,input_pins=inputs,existing_pool_receipt_sha256=file_hash(seed_path.parent/'receipt.json'),
        candidates_sha256=file_hash(ROOT/'candidate-windows.jsonl'),max_additional_windows_per_document=2,
        exact_text_dedup=True,nonoverlap_with_existing_window=True,accepted_rows=0,
        no_target_cuts=True,source_scope='existing licensed downloaded Wikipedia only',
        limitation='Additional windows are NOT new unique documents; no independent corpus claim; semantic and near-duplicate screening still required'))
    print(dict(counts),flush=True)


if __name__=='__main__':main()

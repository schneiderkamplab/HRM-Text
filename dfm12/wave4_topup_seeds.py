"""CPU-only additive pinned, nonoverlapping source passages for LB/SQ/BS."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sqlite3

from .io import digest, file_hash, load, lock, rows, write_json


def passages(text, occupied, max_passages=4):
    """Select complete paragraph spans without rewriting or truncating text."""
    if not isinstance(text, str):
        return
    spans = []
    start = 0
    for match in re.finditer(r'\n\s*\n', text):
        if match.start() > start:
            spans.append((start, match.start()))
        start = match.end()
    if start < len(text):
        spans.append((start, len(text)))
    count = 0
    index = 0
    while index < len(spans) and count < max_passages:
        left, right = spans[index]
        index += 1
        if any(left < end and right > begin for begin, end in occupied):
            continue
        while right-left < 500 and index < len(spans):
            next_left, next_right = spans[index]
            if next_right-left > 2400 or any(next_left < end and next_right > begin for begin, end in occupied):
                break
            right = next_right
            index += 1
        if 500 <= right-left <= 2400 and text[left:right].strip():
            yield text[left:right], left
            occupied = [*occupied, (left, right)]
            count += 1


def prepare(output, source=Path('data/dfm13/wave4/seeds'), languages=('lb','sq','bs')):
    output, source = Path(output).resolve(), Path(source).resolve()
    output.mkdir(parents=True, exist_ok=False)
    with lock(output/'prepare.lock'):
        old = load(source/'receipt.json')
        original = source/'seeds.sqlite'
        if file_hash(original) != old['sha256']:
            raise ValueError('Original sealed seed inventory changed')
        building = output/'seeds.building.sqlite'
        with sqlite3.connect(original.as_uri()+'?mode=ro',uri=True) as src, sqlite3.connect(building) as db:
            src.backup(db)
            db.execute('CREATE TABLE topup_passages(source_id TEXT PRIMARY KEY,parent_source_id TEXT,document_id TEXT,offset INTEGER,length INTEGER,text_sha256 TEXT UNIQUE)')
            counts = Counter()
            pins = {}
            for lang in languages:
                parents = {}
                hashes = set()
                seq = db.execute('SELECT coalesce(max(seq),0) FROM seeds WHERE pool=?',(lang,)).fetchone()[0]
                for source_id, payload in db.execute('SELECT source_id,payload FROM seeds WHERE pool=?',(lang,)):
                    seed = json.loads(payload)
                    parents[str(seed['source_document_id'])] = (source_id,seed)
                    hashes.add(digest(seed['text']))
                folder = Path('data/dfm13/wave4/downloads')/('wikipedia-'+lang)
                pin = load(folder/'wave4-download.json')
                if pin['status'] != 'downloaded':
                    raise ValueError('Pinned source unavailable: '+lang)
                pins[str((folder/'wave4-download.json').resolve())] = file_hash(folder/'wave4-download.json')
                for path in sorted(folder.glob(pin['config']+'/*.parquet')):
                    sha = file_hash(path)
                    pins[str(path.resolve())] = sha
                    for row in rows(path):
                        parent = parents.get(str(row['id']))
                        if parent is None:
                            continue
                        parent_id, seed = parent
                        if seed['revision'] != pin['revision'] or seed['source_sha256'] != sha:
                            raise ValueError('Document lineage drift')
                        text = row['text']
                        offset = seed['offset']
                        if text[offset:offset+len(seed['text'])] != seed['text']:
                            raise ValueError('Original window not exact document substring')
                        for passage, start in passages(text, [(offset,offset+len(seed['text']))]):
                            text_hash = digest(passage)
                            if text_hash in hashes:
                                continue
                            hashes.add(text_hash)
                            key = digest(['wave4-topup-passage-v1',parent_id,start,passage])
                            payload = dict(seed,id=key,text=passage,offset=start,
                                parent_source_id=parent_id,source_variant='nonoverlapping-complete-paragraphs-v1',
                                source_passage_sha256=text_hash)
                            seq += 1
                            db.execute('INSERT INTO seeds VALUES(?,?,?,?)',(lang,seq,key,json.dumps(payload,ensure_ascii=False)))
                            db.execute('INSERT INTO topup_passages VALUES(?,?,?,?,?,?)',
                                (key,parent_id,str(row['id']),start,len(passage),text_hash))
                            counts[lang] += 1
                    db.commit()
                    write_json(output/'progress.json',dict(phase='preparing',added=dict(counts),source_pins=pins))
                print(lang, counts[lang], flush=True)
            db.commit()
        building.rename(output/'seeds.sqlite')
        result=dict(version='wave4-topup-passages-v1',ready=True,
            original_root=str(source),original_sha256=old['sha256'],source_pins=pins,
            added=dict(counts),sha256=file_hash(output/'seeds.sqlite'),
            max_additional_passages_per_document=4,no_text_rewriting=True,
            original_inventory_preserved=True,generation_and_review_required=True)
        write_json(output/'receipt.json',result)
        return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(args.output),indent=2))

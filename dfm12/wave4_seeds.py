"""Build the native and audited-English grounding inventory for wave four."""
from collections import Counter
import json
from pathlib import Path
import sqlite3

from .io import digest, file_hash, load, lock, rows, write_json
from .multilingual_production_seeds import SCHEMA, insert, native_window
from .wave4_cpu import LANGUAGES

ROOT = Path('data/dfm13/wave4')


def main():
    root = ROOT/'seeds'
    with lock(root/'.build.lock'):
        if (root/'receipt.json').exists():
            receipt = load(root/'receipt.json')
            if file_hash(root/'seeds.sqlite') != receipt['sha256']:
                raise ValueError('Sealed seeds changed')
            return
        temporary = root/'seeds.building.sqlite'
        temporary.unlink(missing_ok=True)
        counts = Counter()
        db = sqlite3.connect(temporary)
        try:
            db.executescript(SCHEMA)
            db.executemany('INSERT INTO languages VALUES (?)',[(lang,) for lang in LANGUAGES])
            for lang in LANGUAGES:
                folder = ROOT/'downloads'/('wikipedia-'+lang)
                pin = load(folder/'wave4-download.json')
                if pin['status'] != 'downloaded':
                    raise ValueError('Missing pinned native source: '+lang)
                for path in sorted(folder.glob(pin['config']+'/*.parquet')):
                    sha = file_hash(path)
                    for row in rows(path):
                        identity = [pin['repo'],pin['revision'],lang,row['id']]
                        selected = native_window(row['text'],digest(identity))
                        if selected is None:
                            continue
                        text,offset = selected
                        payload = dict(id=digest([identity,text]),text=text,language=lang,
                            source_document_id=row['id'],source=pin['repo'],revision=pin['revision'],
                            source_sha256=sha,document_url=row.get('url'),offset=offset,
                            generation_and_review_required=True)
                        if insert(db,lang,payload,digest(identity),digest(text)):
                            counts[lang] += 1
                    db.commit()
                print('SEEDS',lang,counts[lang],flush=True)
            # Reuse the already pinned, modernized English OH seed selection, not raw OH.
            origin = Path('data/dfm13/baltic/seeds/seeds.sqlite').resolve()
            pin = load(origin.parent/'receipt.json')
            if file_hash(origin) != pin['sha256']:
                raise ValueError('Baltic seed input changed')
            with sqlite3.connect(origin.as_uri()+'?mode=ro',uri=True) as source:
                for source_id,raw in source.execute("SELECT source_id,payload FROM seeds WHERE pool='openhermes' ORDER BY seq"):
                    payload=json.loads(raw)
                    if insert(db,'openhermes',payload,source_id,source_id):
                        counts['openhermes'] += 1
            db.commit()
            db.execute('CREATE TEMP TABLE ordering AS SELECT pool,source_id,ROW_NUMBER() OVER(PARTITION BY pool ORDER BY source_id) AS position FROM seeds')
            db.execute('CREATE UNIQUE INDEX ordering_key ON ordering(pool,source_id)')
            db.execute('UPDATE seeds SET seq=-seq')
            db.execute('UPDATE seeds SET seq=(SELECT position FROM ordering WHERE ordering.pool=seeds.pool AND ordering.source_id=seeds.source_id)')
            db.commit()
        finally:
            db.close()
        temporary.replace(root/'seeds.sqlite')
        write_json(root/'receipt.json',dict(counts=counts,sha256=file_hash(root/'seeds.sqlite'),
            ready=all(counts[lang]>0 for lang in LANGUAGES) and counts['openhermes']>=15000,
            sufficient_for_full_targets=False,policy='unique document windows; no implicit repeated sources',
            english_source_pin=pin['sha256']))


if __name__ == '__main__':
    main()

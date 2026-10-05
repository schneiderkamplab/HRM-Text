"""Bounded read-only selected-source gap research; no candidate/queue admission."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sqlite3
import time
import urllib.request

import yaml

from dfm12.io import file_hash, load, rows, write_json
from dfm12.baltic_pivots import texts


def crosscheck(root):
    """Independently stream pinned legs; do not trust mutable index contents."""
    root = Path(root)
    receipt = load(root/'receipt.json')
    maps = {language: defaultdict(set) for language in ('ca','fo','nn')}
    sk_path = None
    for name, sha in receipt['local_leg_pins'].items():
        if not name.endswith('/candidates.jsonl'):
            continue
        path = Path(name)
        if file_hash(path) != sha:
            raise ValueError('Pinned input drift')
        if path.parent.name == 'opus-en-sk':
            sk_path = path
            continue
        for row in rows(path):
            mapping = texts(row)
            language = next(k for k in mapping if k != 'en')
            maps[language][mapping['en']].add(mapping[language])
    wanted = set().union(*(set(mapping) for mapping in maps.values()))
    matches = defaultdict(set)
    scanned = 0
    if sk_path is None:
        raise ValueError('No pinned Slovak leg')
    for row in rows(sk_path):
        mapping = texts(row)
        scanned += 1
        if mapping['en'] in wanted:
            matches[mapping['en']].add(mapping['sk'])
    result = dict(input_pins=receipt['local_leg_pins'],sk_rows_scanned=scanned,
        pairs={language+'-sk':dict(
            raw_exact_anchor_intersections=len(set(mapping) & set(matches)),
            unambiguous_intersections=sum(len(values)==1 and len(matches.get(anchor,()))==1
                                         for anchor,values in mapping.items()))
            for language,mapping in maps.items()},
        matching='Exact strings only; no case folding, fuzzy matching or inferred translations',
        script_sha256=file_hash(__file__))
    write_json(root/'independent-stream-crosscheck.json',result)
    print(json.dumps(result['pairs'],indent=2))


def main(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    base = Path('data/dfm13/wave4')
    additive = base/'slovak-additive-20261003-v1'
    pins = {}
    legs = []
    for pair in ('ca-en', 'en-fo', 'en-nn', 'en-sk'):
        folder = (additive if pair == 'en-sk' else base)/'translations/candidates'/('opus-'+pair)
        receipt = load(folder/'receipt.json')
        actual = file_hash(folder/'candidates.jsonl')
        if actual != receipt['sha256']:
            raise ValueError('Changed English leg')
        pins[str(folder/'candidates.jsonl')] = actual
        pins[str(folder/'receipt.json')] = file_hash(folder/'receipt.json')
        legs.append(dict(pair=pair, counts=receipt['counts']))
    inventories = {}
    for family in ('translations', 'institutional-translations'):
        path = base/family/'opus/inventory.json'
        pins[str(path)] = file_hash(path)
        inv = load(path)
        inventories[family] = {p: inv['pairs'][p] for p in ('ca-sk','fo-sk','nn-sk')}
    # Existing indexed tables only: no rebuild, WAL change or write connection.
    dbpath = additive/'pivots/anchors.sqlite'
    results = []
    with sqlite3.connect(dbpath.resolve().as_uri()+'?mode=ro', uri=True) as db:
        for lang in ('ca', 'fo', 'nn'):
            deadline = time.monotonic()+60
            db.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
            total = db.execute('SELECT count(*) FROM unique_anchors WHERE language=?', (lang,)).fetchone()[0]
            matches = db.execute('SELECT count(*) FROM unique_anchors a JOIN unique_anchors b '
                'ON a.english=b.english WHERE a.language=? AND b.language=\'sk\'', (lang,)).fetchone()[0]
            results.append(dict(pair=lang+'-sk', unique_english_anchors=total,
                                exact_unambiguous_matches=matches))
        sk = db.execute("SELECT count(*) FROM unique_anchors WHERE language='sk'").fetchone()[0]
    path = additive/'pivots/manifest.json'
    pins[str(path)] = file_hash(path)
    remote = []
    revision = '42d4fbe382245487a68e853ca53bea832a41a02a'
    urls = [f'https://opus.nlpl.eu/opusapi/?source={a}&target={b}&corpus=Tatoeba&preprocessing=moses'
            for a,b in [('en','sk'),('ca','sk'),('fo','sk'),('nn','sk')]]
    urls += [f'https://raw.githubusercontent.com/Helsinki-NLP/OPUS/{revision}/corpus/{name}/{release}/info.yaml'
             for name,release in [('QED','v2.0a'),('TED2020','v1'),('EUbookshop','v2'),('ELRC-wikipedia_health','v1')]]
    for i,url in enumerate(urls):
        entry = dict(url=url, fetched_at=time.time())
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                raw = response.read(2_000_001)
            if len(raw)>2_000_000:
                raise ValueError('Metadata exceeds 2MB bound')
            entry['raw'] = raw.decode('utf-8')
            parsed = json.loads(entry['raw']) if 'opusapi' in url else yaml.safe_load(entry['raw'])
            entry['summary'] = parsed if 'opusapi' in url else {k:parsed.get(k) for k in ('name','release','license','copyright')}
        except Exception as exc:
            entry['error'] = str(exc)
        path = root/'evidence'/f'{i:02d}.json'
        write_json(path,entry)
        remote.append(dict(path=str(path),sha256=file_hash(path),url=url,
                           summary=entry.get('summary'),error=entry.get('error')))
    write_json(root/'receipt.json',dict(schema='slovak-selected-gap-research-v1',
        local_leg_pins=pins,legs=legs,joins=results,sk_unique_english_anchors=sk,
        inventory= inventories,remote_evidence=remote,
        database_read_only=str(dbpath),database_hash_not_claimed=True,
        join_basis='Existing exact unique_anchors indexed table; pinned input receipts and manifest retained',
        corpus_download_bytes=0,metadata_request_bound=8,metadata_bytes_per_request_bound=2000000,
        candidate_rows_created=0,queue_writes=0,gpu_calls=0,admission_authorized=False,
        scope='Selected sources and bounded metadata discovery only; not global unavailability'))
    print(json.dumps(dict(legs=legs,joins=results,sk_unique_english_anchors=sk,remote=remote),indent=2))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True)
    p.add_argument('--verify-local',action='store_true')
    args=p.parse_args()
    (crosscheck if args.verify_local else main)(args.root)

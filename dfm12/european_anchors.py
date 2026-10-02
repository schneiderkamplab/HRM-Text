"""CPU-only English-anchor supplements for missing direct European pairs."""
import json
import os
from pathlib import Path
import sqlite3
import time

from .european_expansion import ROOT
from .io import atomic, digest, file_hash, load, lock, rows, write_json
from .prepare import Renderer
from .opus import validate_license

CAP = 165_332_456


def matches(db, a, b):
    return db.execute('''WITH unique_anchors AS (
        SELECT lang,corpus,version,english,target,provenance FROM anchors
        WHERE lang IN (?,?) GROUP BY lang,corpus,version,english HAVING COUNT(*)=1)
        SELECT a.english,a.target,b.target,a.provenance,b.provenance
        FROM unique_anchors a JOIN unique_anchors b
        ON a.corpus=b.corpus AND a.version=b.version AND a.english=b.english
        WHERE a.lang=? AND b.lang=? ORDER BY a.corpus,a.version,a.english''', (a,b,a,b))


def run(root=ROOT):
    cfg = load(root / 'config.json')
    inventory = load(root / 'opus/inventory.json')['pairs']
    pairs = sorted(p for p, item in inventory.items()
                   if 'en' not in p.split('-') and not any(e.get('status') == 'approved' for e in item['corpora']))
    work = root / 'english-anchors'
    with lock(work / '.lock'):
        from . import opus
        from .european_opus import review
        bridge_root = work / 'bridge-sources'
        bridge_cfg = dict(cfg, opus_pairs=[['en','fo'], ['en','is']])
        opus.discover(bridge_root, bridge_cfg)
        review(bridge_root)
        renderer = Renderer(load('data/sampled_dfm11/metadata.json')['tokenizer_info'], cfg['max_seq_len'])
        for bridge in ('en-fo', 'en-is'):
            marker = bridge_root / 'candidates' / ('opus-' + bridge) / 'receipt.json'
            if not marker.exists():
                opus.prepare_pair(bridge_root, bridge, bridge_cfg, renderer)
        db = sqlite3.connect(work / 'anchors.sqlite')
        db.execute('PRAGMA cache_size=-65536')
        db.execute('CREATE TABLE IF NOT EXISTS anchors(lang, corpus, version, english, target, provenance, PRIMARY KEY(lang,corpus,version,english,target)) WITHOUT ROWID')
        db.execute('CREATE TABLE IF NOT EXISTS inputs(path PRIMARY KEY, sha256)')
        for lang in sorted({l for p in pairs for l in p.split('-')}):
            roots = [root, Path('data/dfm12'), bridge_root]
            en_pair = '-'.join(sorted(['en', lang]))
            source_root = next((r for r in roots if (r / 'candidates' / ('opus-' + en_pair) / 'receipt.json').exists()), None)
            if source_root is None:
                print('missing English source', lang, flush=True)
                continue
            directory = source_root / 'candidates' / ('opus-' + en_pair)
            path = directory / 'candidates.jsonl'
            with lock(directory / '.lock'):
                sha = file_hash(path)
                if sha != load(directory / 'receipt.json')['sha256']:
                    raise ValueError('Source checksum mismatch')
                previous = db.execute('SELECT sha256 FROM inputs WHERE path=?', (str(path),)).fetchone()
                if previous:
                    if previous[0] != sha:
                        raise ValueError('Pinned anchor source changed')
                    continue
                entries = load(source_root / 'opus/inventory.json')['pairs'][en_pair]['corpora']
                approved = {}
                for e in entries:
                    if e.get('status') == 'approved':
                        validate_license(e)
                        approved[(e['corpus'], e['version'], e['url'])] = e
                with db:
                    for row in rows(path):
                        prov = row['provenance']
                        if (prov['corpus'], prov['version'], prov['url']) not in approved:
                            continue
                        if {row['language'], row['reverse_language']} != {lang, 'en'}:
                            raise ValueError('Unexpected translation direction')
                        english = (row['messages'] if row['language'] == 'en' else row['reverse_messages'])[-1]['content']
                        target = (row['messages'] if row['language'] == lang else row['reverse_messages'])[-1]['content']
                        lineage = dict(prov, source_file=str(path.resolve()), source_sha256=sha, source_id=row['id'])
                        db.execute('INSERT OR IGNORE INTO anchors VALUES (?,?,?,?,?,?)',
                                   (lang, prov['corpus'], prov['version'], english, target, json.dumps(lineage)))
                    db.execute('INSERT INTO inputs VALUES (?,?)', (str(path), sha))
            print('indexed', lang, flush=True)
        renderer = Renderer(load('data/sampled_dfm11/metadata.json')['tokenizer_info'], cfg['max_seq_len'])
        components = []
        input_signature = digest(db.execute('SELECT path,sha256 FROM inputs ORDER BY path').fetchall())
        for pair in pairs:
            a, b = pair.split('-')
            component = 'opus-' + pair + '-english-anchor'
            directory = root / 'candidates' / component
            with lock(directory / '.lock'):
                receipt = directory / 'receipt.json'
                if receipt.exists():
                    result = load(receipt)
                    if result.get('input_signature') != input_signature:
                        raise ValueError('Anchor inputs changed; archive unscreened output explicitly before rebuilding')
                    if file_hash(directory / 'candidates.jsonl') != result['sha256']:
                        raise ValueError('Completed anchor candidates changed')
                else:
                    direct = root / 'candidates' / ('opus-' + pair) / 'candidates.jsonl'
                    if direct.exists():
                        raise ValueError('Direct supply appeared: review shared pair budget before supplementing')
                    count = tokens = 0
                    seen = set()
                    with atomic(directory / 'candidates.jsonl') as output:
                        for english, left, right, pa, pb in matches(db, a, b):
                            key = digest([pair,left,right])
                            if key in seen:
                                continue
                            seen.add(key)
                            def chat(src, dst, text, answer):
                                return [{'role':'user','content':f'Translate from {cfg["languages"][src]} into {cfg["languages"][dst]}. Output only the translation.\n\n{text}'}, {'role':'assistant','content':answer}]
                            messages, reverse = chat(a,b,left,right), chat(b,a,right,left)
                            try:
                                n = renderer.count(messages) + renderer.count(reverse)
                            except ValueError:
                                continue
                            if tokens + n > CAP:
                                continue
                            record = dict(id=key, messages=messages, reverse_messages=reverse,
                                language=b, reverse_language=a, task='translation', pair=pair, rendered_tokens=n,
                                provenance=dict(method='exact_english_anchor_join', machine_translated=False,
                                    english_anchor=english, sources=[json.loads(pa),json.loads(pb)]),
                                audit_context=dict(english_anchor=english, instruction='Audit both directions for equivalent meaning and correct language variants. Exact English equality does not establish shared sentence IDs or sense. pt_pt must be European Portuguese. Reject ambiguity.'))
                            output.write(json.dumps(record,ensure_ascii=False)+'\n')
                            count += 1
                            tokens += n
                    result = dict(component=component, pair=pair, input_signature=input_signature, counts=dict(candidate_pairs=count,rendered_tokens=tokens),
                        sha256=file_hash(directory/'candidates.jsonl'), pair_token_cap=CAP,
                        budget_scope='Shared direct plus anchor allowance, both directions, repeat 1', audit_status='pending', accepted=False)
                    write_json(receipt,result)
                components.append(component)
                print(pair, result['counts'], flush=True)
        write_json(work/'manifest.json',dict(components=components,pairs=pairs,pair_token_cap=CAP,accepted=False))
        db.close()


if __name__ == '__main__':
    os.environ.update(CUDA_VISIBLE_DEVICES='', TOKENIZERS_PARALLELISM='false')
    run()
    from .european_screen import run as screen
    while True:
        try:
            screen(ROOT, watch=True)
            break
        except BlockingIOError:
            time.sleep(60)

"""Recover Mandarin direct pairs and build conservative exact-English pivots."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import sqlite3

import typer
from dfm12.io import atomic, digest, file_hash, load, lock, rows, write_json
from dfm12.baltic_opus import prepare_one
from dfm12.prepare import Renderer
from dfm14.parallel import discover_one

app = typer.Typer()


def texts(row):
    return {row['language']: row['messages'][-1]['content'],
            row['reverse_language']: row['reverse_messages'][-1]['content']}


def eligible(anchor):
    return len(anchor) >= 40 and len(anchor.split()) >= 6 and sum(c.isalpha() for c in anchor) >= 25


def pivot(job):
    root, original, pair, cfg = job
    a, b = pair.split('-')
    folder = root / 'pivots' / pair
    with lock(folder / '.lock'):
        if (folder / 'receipt.json').exists():
            receipt = load(folder / 'receipt.json')
            if file_hash(folder / 'candidates.jsonl') != receipt['sha256']:
                raise ValueError('Changed pivot candidates')
            return receipt
        connection = sqlite3.connect(f'file:{root / "legs.sqlite"}?mode=ro', uri=True)
        connection.execute('PRAGMA cache_size=-8192')
        renderer = Renderer(load('data/sampled_dfm13/metadata.json')['tokenizer_info'], 4096)
        direct = original / 'candidates' / ('opus-' + pair) / 'candidates.jsonl'
        seen = {r['id'] for r in rows(direct)} if direct.exists() else set()
        count = Counter()
        sql = '''SELECT x.anchor,x.text,y.text,x.evidence,y.evidence FROM legs x JOIN legs y
                 ON x.anchor=y.anchor WHERE x.language=? AND y.language=?
                 AND x.ambiguous=0 AND y.ambiguous=0 ORDER BY x.anchor'''
        with atomic(folder / 'candidates.jsonl') as out:
            for anchor, ta, tb, ea, eb in connection.execute(sql, (a, b)):
                count['matched'] += 1
                key = digest({a: ta, b: tb})
                if key in seen or ta == tb:
                    count['duplicate_or_identical'] += 1
                    continue
                conversations = [[dict(role='user', content=f'Translate from {cfg["languages"][s]} into {cfg["languages"][d]}. Output only the translation.\n\n{t}'),
                                  dict(role='assistant', content=u)] for s,d,t,u in ((a,b,ta,tb),(b,a,tb,ta))]
                try:
                    tokens = sum(renderer.count(m) for m in conversations)
                except ValueError:
                    count['overlength'] += 1
                    continue
                record = dict(id=key, messages=conversations[0], reverse_messages=conversations[1],
                    language=b, reverse_language=a, pair=pair, task='translation', rendered_tokens=tokens,
                    training_ready=False, admission_authorized=False,
                    provenance=dict(route='exact_english_pivot', legs=[json.loads(ea),json.loads(eb)], english_anchor=anchor),
                    audit_context=dict(languages={l:cfg['languages'][l] for l in (a,b)}, english_anchor=anchor,
                        instruction='Audit BOTH directions and semantic equivalence to the anchor. Exact text joins do not guarantee equivalent senses.'))
                out.write(json.dumps(record, ensure_ascii=False) + '\n')
                count['candidate_pairs'] += 1
                count['rendered_tokens'] += tokens
                seen.add(key)
        connection.close()
        receipt = dict(pair=pair, counts=dict(count), sha256=file_hash(folder / 'candidates.jsonl'), training_ready=False)
        write_json(folder / 'receipt.json', receipt)
        print(json.dumps(receipt), flush=True)
        return receipt


@app.command()
def run(original: Path=Path('data/dfm14/parallel-v1'), root: Path=Path('data/dfm14/parallel-expansion-v2'), workers:int=16):
    if not 1 <= workers <= 32:
        raise ValueError('Workers must be 1..32')
    root = root.resolve()
    with lock(root / '.controller.lock'):
        cfg = load(original / 'config.json')
        cfg.setdefault('opus_codes', {})['zh'] = 'cmn'
        write_json(root / 'config.json', cfg)
        chinese = ['-'.join(p) for p in cfg['requested_pairs'] if 'zh' in p]
        inventory = {}
        for pair in chinese:
            _, item = discover_one(root, cfg, pair.split('-'))
            inventory[pair] = item
        write_json(root / 'opus/inventory.json', dict(pairs=inventory))
        with ProcessPoolExecutor(max_workers=workers) as pool:
            result = list(pool.map(prepare_one, [(root,pair,item,cfg) for pair,item in inventory.items()]))
        write_json(root / 'mandarin-direct.json', dict(zip(inventory,result)))
        database = root / 'legs.sqlite'
        if not (root / 'legs-ready.json').exists():
            connection = sqlite3.connect(database)
            connection.execute('DROP TABLE IF EXISTS legs')
            connection.execute('CREATE TABLE legs(language TEXT,anchor TEXT,text TEXT,evidence TEXT,ambiguous INTEGER DEFAULT 0,PRIMARY KEY(language,anchor)) WITHOUT ROWID')
            counts = Counter()
            for pair in cfg['opus_pairs']:
                if 'en' not in pair:
                    continue
                name = '-'.join(pair)
                base = root if 'zh' in pair else original
                path = base / 'candidates' / ('opus-' + name) / 'candidates.jsonl'
                if not path.exists():
                    continue
                for row in rows(path):
                    values = texts(row); anchor = values['en']; language = next(x for x in pair if x != 'en')
                    if not eligible(anchor):
                        counts['short_anchor'] += 1
                        continue
                    evidence = json.dumps(dict(id=row['id'], provenance=row['provenance'], input=str(path)), ensure_ascii=False)
                    connection.execute('''INSERT INTO legs(language,anchor,text,evidence) VALUES(?,?,?,?)
                        ON CONFLICT(language,anchor) DO UPDATE SET ambiguous=MAX(legs.ambiguous,legs.text != excluded.text)''',
                        (language, anchor, values[language], evidence))
                    counts['input_legs'] += 1
                connection.commit()
                write_json(root / 'progress.json', dict(phase='indexing', pair=name, counts=dict(counts)))
            counts['unique_legs'] = connection.execute('SELECT COUNT(*) FROM legs WHERE ambiguous=0').fetchone()[0]
            counts['ambiguous_legs'] = connection.execute('SELECT COUNT(*) FROM legs WHERE ambiguous=1').fetchone()[0]
            connection.close()
            write_json(root / 'legs-ready.json', dict(counts))
        requested = ['-'.join(p) for p in cfg['requested_pairs'] if 'en' not in p]
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = []
            for result in pool.map(pivot, [(root,original,p,cfg) for p in requested]):
                results.append(result)
                write_json(root / 'progress.json', dict(phase='pivots', done=len(results), total=len(requested)))
        write_json(root / 'summary.json', dict(pairs=results, training_ready=False,
            remaining=['both-direction semantic audit', 'inherited and benchmark decontamination', 'combined direct/pivot token cap']))


if __name__ == '__main__':
    app()

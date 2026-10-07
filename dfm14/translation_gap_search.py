"""CPU evidence search for remaining translation gaps; no training admission."""
from collections import defaultdict
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import urllib.request
import zipfile

from dfm12.io import file_hash, load, rows, write_json
from dfm14.parallel_expand import eligible, texts


def run():
    base = Path('data/dfm14/parallel-expansion-v3')
    original = Path('data/dfm14/parallel-v1')
    out = Path('data/dfm14/translation-gap-search-v1')
    out.mkdir(parents=True, exist_ok=True)
    url = 'https://www.manythings.org/anki/slk-eng.zip'
    archive = out / 'slk-eng.zip'
    if not archive.exists():
        request = urllib.request.Request(url, headers={'User-Agent': 'curl/8.5.0', 'Accept': '*/*'})
        with urllib.request.urlopen(request, timeout=90) as remote:
            payload = remote.read()
        fd, temporary = tempfile.mkstemp(dir=out)
        try:
            with os.fdopen(fd, 'wb') as handle:
                handle.write(payload)
            os.replace(temporary, archive)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    with zipfile.ZipFile(archive) as z:
        readme = z.read('_about.txt').decode('utf-8')
        if 'creativecommons.org/licenses/by/2.0' not in readme:
            raise ValueError('Unexpected license description')
        items = []
        for line in io.TextIOWrapper(z.open('slk.txt'), encoding='utf-8'):
            en, sk, attribution = line.rstrip('\n').split('\t')
            if 'CC-BY 2.0' not in attribution:
                raise ValueError('Missing row attribution')
            items.append((en, sk, attribution))
    connection = sqlite3.connect(f'file:{base / "legs.sqlite"}?mode=ro', uri=True)
    gaps = [r['pair'] for r in load(base / 'coverage.json')['per_pair'] if r['candidate_pairs'] == 0]
    mappings = defaultdict(set)
    for en, sk, attribution in items:
        if eligible(en):
            mappings[en].add(sk)
    findings = []
    for name in gaps:
        if 'sk' not in name.split('-'):
            continue
        other = next(x for x in name.split('-') if x != 'sk')
        matched = []
        for en, values in mappings.items():
            if len(values) != 1:
                continue
            entry = connection.execute('SELECT text FROM legs WHERE language=? AND anchor=? AND ambiguous=0', (other, en)).fetchone()
            if entry and entry[0] != next(iter(values)):
                matched.append(dict(anchor=en, sk=next(iter(values)), **{other: entry[0]}))
        findings.append(dict(pair=name, pivot='en', matches=len(matched), examples=matched[:3], route='manythings-slovak'))
    connection.close()

    def leg(language, pivot):
        name = '-'.join(sorted([language, pivot]))
        paths = [original / 'candidates' / ('opus-' + name) / 'candidates.jsonl',
                 base / 'candidates' / ('opus-' + name) / 'candidates.jsonl']
        mapping = defaultdict(set)
        for path in paths:
            if not path.exists():
                continue
            for row in rows(path):
                values = texts(row)
                if eligible(values[pivot]):
                    mapping[values[pivot]].add(values[language])
        return {k:next(iter(v)) for k,v in mapping.items() if len(v)==1}

    for name in gaps:
        if 'sk' in name.split('-'):
            continue
        a,b = name.split('-')
        for intermediate in ('fr','de','ru','es','pl','nl','cs'):
            x,y = leg(a,intermediate),leg(b,intermediate)
            keys = sorted(k for k in x.keys() & y.keys() if x[k] != y[k])
            findings.append(dict(pair=name, pivot=intermediate, matches=len(keys), route='existing-tatoeba',
                examples=[dict(anchor=k, **{a:x[k],b:y[k]}) for k in keys[:3]]))
    report = dict(training_ready=False, manythings=dict(url=url, rows=len(items), sha256=file_hash(archive), readme=readme),
        findings=findings, unresolved=[p for p in gaps if not any(f['pair']==p and f['matches'] for f in findings)],
        caveat='Exact pivot candidates only; counts precede native rendering, semantic audit and benchmark decontamination.')
    write_json(out / 'report.json',report)
    print(json.dumps(dict(manythings_rows=len(items), findings=[{k:v for k,v in f.items() if k!='examples'} for f in findings if f['matches']], unresolved=report['unresolved']),indent=2),flush=True)


if __name__ == '__main__':
    run()

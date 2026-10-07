"""Prepare an isolated institutional translation pilot; never alter active inputs."""
from collections import Counter
import io
import json
from itertools import zip_longest
from pathlib import Path
import random
import sqlite3
import os
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

from dfm12.io import atomic, digest, file_hash, load, lock, write_json
from dfm12.prepare import Renderer
from dfm14.parallel_expand import eligible

ROOT = Path('data/dfm14/institutional-parallel-v1').resolve()
BASE = Path('data/dfm14/parallel-expansion-v4').resolve()
DGT_TERMS = 'https://joint-research-centre.ec.europa.eu/language-technology-resources/dgt-translation-memory_en'


def dgt(pair):
    url = f'https://object.pouta.csc.fi/OPUS-DGT/v2021/moses/{pair}.txt.zip'
    path = ROOT / 'downloads' / (pair + '.zip')
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=path.parent)
        try:
            with urllib.request.urlopen(url, timeout=180) as response, os.fdopen(fd, 'wb') as out:
                while block := response.read(4 * 1024 * 1024):
                    out.write(block)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)
    proof = dict(corpus='DGT', version='v2021', url=url, archive_sha256=file_hash(path),
                 license='European Commission reuse Decision 2011/833/EU',
                 license_evidence=DGT_TERMS, ownership='European Commission')
    a, b = pair.split('-')
    with zipfile.ZipFile(path) as archive:
        write_json(path.with_suffix('.attribution.json'), dict(**proof, README=archive.read('README').decode()))
        names = [[n for n in archive.namelist() if n.endswith('.' + lang)] for lang in (a, b)]
        if any(len(n) != 1 for n in names):
            raise ValueError('Ambiguous Moses members')
        with archive.open(names[0][0]) as left, archive.open(names[1][0]) as right:
            for line, values in enumerate(zip_longest(io.TextIOWrapper(left), io.TextIOWrapper(right)), 1):
                if None in values:
                    raise ValueError('Unequal parallel files')
                yield dict(zip((a, b), (' '.join(v.split()) for v in values))), dict(**proof, line=line)


def clean(values):
    lengths = [len(v) for v in values.values()]
    return min(lengths) >= 20 and max(lengths) <= 12000 and max(lengths) <= 5 * min(lengths) and len(set(values.values())) == len(values)


def run():
    with lock(ROOT / '.controller.lock'):
        if (ROOT / 'coverage.json').exists():
            print('Preparation already complete', flush=True)
            return
        cfg = load(BASE / 'config.json')
        write_json(ROOT / 'config.json', cfg)
        candidates = {}
        stats = {}
        for pair in ('ga-sk', 'mt-sk'):
            sample = []; rng = random.Random(0); count = Counter()
            for values, proof in dgt(pair):
                count['raw'] += 1
                if not clean(values):
                    continue
                count['structurally_eligible'] += 1
                item = (values, proof)
                n = count['structurally_eligible']
                if len(sample) < 10000:
                    sample.append(item)
                else:
                    index = rng.randrange(n)
                    if index < len(sample): sample[index] = item
            candidates[pair] = sample; stats[pair] = dict(count)
            write_json(ROOT / 'progress.json', dict(phase='direct_sample', counts=stats))
            print(pair, dict(count), flush=True)

        discovery = Path('data/dfm14/alternate-pivots-v2')
        db = sqlite3.connect(f'file:{BASE / "legs.sqlite"}?mode=ro', uri=True)
        with zipfile.ZipFile(discovery / 'luxembourg.zip') as archive:
            n = 0
            for line in archive.open('LU-FR-DE-EN/LU-FR-DE-EN.jsonl'):
                row = json.loads(line); n += 1
                anchor = ' '.join(row['en'].split())
                if not eligible(anchor): continue
                for lang in ('eu', 'ga', 'mt'):
                    match = db.execute('SELECT text,evidence FROM legs WHERE language=? AND anchor=? AND ambiguous=0', (lang, anchor)).fetchone()
                    if match:
                        pair = '-'.join(sorted((lang, 'lb')))
                        candidates.setdefault(pair, []).append(({lang:match[0], 'lb':row['lb']},
                            dict(corpus='Tech-in-GOV 2025 exact English pivot', license='cc0-1.0',
                                 archive_sha256=file_hash(discovery/'luxembourg.zip'), source_id=row['id'],
                                 english_anchor=anchor, other_leg=json.loads(match[1]))))
            stats['luxembourg_source_rows'] = n
        db.close()
        anchors = {}; ambiguous = set(); total = 0
        with zipfile.ZipFile(discovery / 'efta.zip') as archive:
            with archive.open('2021_EFTA_eng_nno.tmx') as handle:
                for _, element in ET.iterparse(handle, events=('end',)):
                    if element.tag != 'tu': continue
                    values = {}
                    for tuv in element.findall('tuv'):
                        lang = tuv.attrib.get('{http://www.w3.org/XML/1998/namespace}lang', '')
                        seg = tuv.find('seg')
                        if seg is not None: values[lang] = ' '.join(''.join(seg.itertext()).split())
                    total += 1
                    en = next((v for k,v in values.items() if k.startswith('en')), None)
                    nn = next((v for k,v in values.items() if k.startswith(('nn','no-NN'))), None)
                    if en and nn and eligible(en):
                        if en in anchors and anchors[en][0] != nn: ambiguous.add(en)
                        anchors[en] = (nn, total)
                    element.clear()
        stats['efta'] = dict(raw=total, anchors=len(anchors), ambiguous=len(ambiguous))
        # Keep only unambiguous translations for the small EFTA anchor set.
        matches = {}; conflicts = set()
        for values, proof in dgt('en-mt'):
            anchor = values['en']
            if anchor not in anchors or anchor in ambiguous: continue
            if anchor in matches and matches[anchor][0] != values['mt']: conflicts.add(anchor)
            matches[anchor] = (values['mt'], proof)
        for anchor, (mt, proof) in matches.items():
            if anchor in conflicts: continue
            nn, index = anchors[anchor]
            candidates.setdefault('mt-nn', []).append((dict(mt=mt, nn=nn),
                dict(corpus='EFTA-DGT exact English pivot', english_anchor=anchor, dgt_leg=proof,
                     efta_leg=dict(license='cc0-1.0', archive_sha256=file_hash(discovery/'efta.zip'), unit=index))))
        stats['efta_dgt_matches'] = dict(matched=len(matches), ambiguous=len(conflicts))
        renderer = Renderer(load('data/sampled_dfm13/metadata.json')['tokenizer_info'], 4096)
        receipts = []
        for pair, items in candidates.items():
            a,b = pair.split('-'); seen=set(); count=Counter()
            path=ROOT/'novel'/(pair+'.jsonl')
            with atomic(path) as out:
                for values, proof in items:
                    key=digest(values)
                    if key in seen or not clean(values): continue
                    seen.add(key)
                    conversations=[[dict(role='user',content=f'Translate from {cfg["languages"][s]} into {cfg["languages"][d]}. Output only the translation.\n\n{values[s]}'),dict(role='assistant',content=values[d])] for s,d in ((a,b),(b,a))]
                    try: tokens=sum(renderer.count(m) for m in conversations)
                    except ValueError: count['overlength']+=1; continue
                    proof.setdefault('english_anchor', None)
                    row=dict(id=key,pair=pair,language=b,reverse_language=a,task='translation',
                        messages=conversations[0],reverse_messages=conversations[1],rendered_tokens=tokens,
                        provenance=proof,audit_context=dict(languages={l:cfg['languages'][l] for l in (a,b)}),
                        training_ready=False,admission_authorized=False)
                    out.write(json.dumps(row,ensure_ascii=False)+'\n'); count['candidate_pairs']+=1
            receipts.append(dict(pair=pair,**count,sha256=file_hash(path)))
        write_json(ROOT/'coverage.json',dict(per_pair=receipts,discovery=stats,training_ready=False,
            pilot_cap=10000,remaining=['semantic audit','inherited/benchmark decontamination','accepted-only integration']))
        print(json.dumps(receipts),flush=True)


if __name__ == '__main__': run()

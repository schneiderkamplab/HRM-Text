"""Fetch missing old-language Tatoeba legs and search exact non-English pivots."""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import json
from pathlib import Path

from dfm12.baltic_opus import prepare_one
from dfm12.io import load, lock, rows, write_json
from dfm14.parallel import discover_one
from dfm14.parallel_expand import eligible, texts


def run():
    root=Path('data/dfm14/alternate-pivots-v2').resolve()
    supplement=Path('data/dfm14/alternate-pivots-v1').resolve()
    base=Path('data/dfm14/parallel-expansion-v4').resolve()
    original=Path('data/dfm14/parallel-v1').resolve()
    with lock(root/'.controller.lock'):
        cfg=load(base/'config.json')
        cfg['languages']['eo']='Esperanto'
        gaps=[r['pair'] for r in load(base/'coverage.json')['per_pair'] if not r['candidate_pairs']]
        languages={l for p in gaps for l in p.split('-')}
        pivots=('fr','de','ru','es','pl','cs','nl','it','en','eo')
        pairs=set()
        for lang in languages:
            for middle in pivots:
                if lang==middle:continue
                pair='-'.join(sorted([lang,middle]))
                if not any((p/'candidates'/('opus-'+pair)/'candidates.jsonl').exists() for p in (original,base,supplement)):
                    pairs.add(pair)
        cfg['opus_pairs']=sorted({tuple(p) for p in cfg['opus_pairs']}|{tuple(p.split('-')) for p in pairs})
        write_json(root/'config.json',cfg)
        with ThreadPoolExecutor(max_workers=8) as pool:
            inventory=dict(pool.map(lambda p:discover_one(root,cfg,p.split('-')),sorted(pairs)))
        write_json(root/'opus/inventory.json',dict(pairs=inventory))
        with ProcessPoolExecutor(max_workers=8) as pool:
            prepared=list(pool.map(prepare_one,[(root,p,item,cfg) for p,item in inventory.items()]))
        write_json(root/'preparation.json',dict(results=prepared))
        cache={}
        def leg(lang,middle):
            key=lang,middle
            if key in cache:return cache[key]
            pair='-'.join(sorted(key));mapping=defaultdict(dict)
            for source in (original,base,supplement,root):
                path=source/'candidates'/('opus-'+pair)/'candidates.jsonl'
                if not path.exists():continue
                for row in rows(path):
                    value=texts(row);anchor=value[middle]
                    if eligible(anchor):
                        mapping[anchor][value[lang]]=dict(id=row['id'],provenance=row['provenance'],input=str(path))
            cache[key]={k:next(iter(v.items())) for k,v in mapping.items() if len(v)==1}
            return cache[key]
        findings=[]
        for pair in gaps:
            a,b=pair.split('-')
            for middle in sorted(set(cfg['languages'])-{a,b}):
                left,right=leg(a,middle),leg(b,middle)
                matches=[k for k in sorted(left.keys()&right.keys()) if left[k][0]!=right[k][0]]
                if not matches:continue
                findings.append(dict(pair=pair,pivot=middle,matches=len(matches),examples=[
                    dict(anchor=k,left=left[k],right=right[k]) for k in matches[:3]]))
            write_json(root/'progress.json',dict(phase='search',pair=pair,nonempty_routes=len(findings)))
        report=dict(findings=findings,unresolved=[p for p in gaps if not any(f['pair']==p for f in findings)],
            training_ready=False,note='Discovery only; native rendering, deduplication and bidirectional audit still required.')
        write_json(root/'report.json',report)
        print(json.dumps(dict(findings=[{k:v for k,v in f.items() if k!='examples'} for f in findings],unresolved=report['unresolved']),indent=2),flush=True)


if __name__=='__main__':run()

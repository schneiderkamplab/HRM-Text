"""Discover the complete new-language mesh and prepare reviewed direct pairs."""
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from itertools import combinations
import json
from pathlib import Path
import urllib.parse
import urllib.request
import typer

from dfm12.io import load, lock, write_json, file_hash
from dfm12.wave4_cpu import configuration as previous_configuration
from dfm12.token_accounting import inherited_budget
from dfm12 import opus
from dfm12.baltic_opus import prepare_one
from dfm12.opus_decisions import MINED, LOW_PRIORITY
from dfm14.catalog import LANGUAGES

app=typer.Typer()


def configuration():
    cfg=previous_configuration()
    old=set(cfg['languages'])
    assert not old & LANGUAGES.keys() and len(old)==34
    cfg['languages'].update(LANGUAGES)
    requested=[list(p) for p in combinations(sorted(cfg['languages']),2) if set(p)&LANGUAGES.keys()]
    legs=[sorted(['en',l]) for l in cfg['languages'] if l!='en']
    cfg.update(requested_pairs=requested,opus_pairs=sorted({tuple(p) for p in requested+legs}),sources={})
    assert len(requested)==664
    return cfg


def discover_one(root,cfg,pair):
    a,b=pair; key=a+'-'+b
    path=root/'discovery'/(key+'.json')
    if path.exists() and not load(path).get('error'): return key,load(path)
    codes=cfg.get('opus_codes',{})
    url='https://opus.nlpl.eu/opusapi/?'+urllib.parse.urlencode(dict(source=codes.get(a,a),target=codes.get(b,b),preprocessing='moses',version='latest'))
    try:
        with urllib.request.urlopen(url,timeout=90) as response: corpora=json.load(response)['corpora']
        for entry in corpora:
            entry['status']='license_review'
            if entry['corpus'] in MINED|LOW_PRIORITY:
                entry.update(status='excluded_quality',reason='No mined web, subtitles, software fragments or narrow religious backfill')
            elif entry['corpus']=='Tatoeba':
                entry.update(status='approved',license='cc-by-2.0',license_evidence='https://tatoeba.org/en/terms_of_use',
                    require_readme_license='creativecommons.org/licenses/by/2.0/fr/')
        result=dict(corpora=corpora,api=url)
    except Exception as exc: result=dict(corpora=[],api=url,error=str(exc))
    write_json(path,result)
    return key,result


@app.command()
def run(root: Path=Path('data/dfm14/parallel-v1'),workers: int=32):
    if not 1<=workers<=64: raise ValueError('Workers 1..64')
    with lock(root/'.controller.lock'):
        cfg=configuration()
        budget=inherited_budget(Path('logs/dfm11/sample_corrected.log'),Path('data/sampled_dfm11'))
        cfg['pair_budgets']={'-'.join(p):dict(tokens=budget['english_pair_cap' if 'en' in p else 'non_english_pair_cap'],
            directions='combined',routes='direct and pivot combined',shortfall='report; no low-quality quota filling') for p in cfg['requested_pairs']}
        write_json(root/'budget.json',budget); write_json(root/'config.json',cfg)
        inventory={}
        with ThreadPoolExecutor(max_workers=16) as pool:
            futures=[pool.submit(discover_one,root,cfg,p) for p in cfg['opus_pairs']]
            for future in as_completed(futures):
                key,item=future.result(); inventory[key]=item
                write_json(root/'progress.json',dict(phase='discovery',done=len(inventory),total=len(futures)))
        write_json(root/'opus/inventory.json',dict(pairs=inventory,policy='direct preferred; explicit source review; no web-mined pairs'))
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures={pool.submit(prepare_one,(root,p,item,cfg)):p for p,item in inventory.items()}
            results={}
            for future in as_completed(futures):
                results[futures[future]]=future.result()
                write_json(root/'progress.json',dict(phase='prepare_direct',done=len(results),total=len(futures)))
        requested={'-'.join(p) for p in cfg['requested_pairs']}
        write_json(root/'preparation.json',dict(pairs=results,requested_pairs=len(requested),
            english_new_pairs=16,non_english_new_pairs=648,training_ready=False,
            remaining=['Additional named institutional corpus-version reviews','Verified English-pivot matching for shortfalls',
                       'Both-direction semantic audit','Inherited/benchmark deduplication','Combined route token cap selection']))


if __name__=='__main__': app()

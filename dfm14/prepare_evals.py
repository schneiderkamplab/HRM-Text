"""Prepare pinned DFM14 heldouts without GPU calls or training-split fallback."""
from concurrent.futures import ProcessPoolExecutor
import gzip
import hashlib
import heapq
import json
from pathlib import Path
import yaml

from dfm12.io import file_hash, load, write_json

ROOT=Path(__file__).resolve().parents[1]
LANGUAGES='ga mt mk eu gl cy ru tr zh ar ja id ko hi vi he'.split()
PACKAGES=Path('/work/dfm/DaLA/export-upload/dfm14-audited-20261006')
OUT=ROOT/'data/dfm14/evaluation'
MANIFEST=ROOT/'config/dfm14_dala_heldout.json'
SUITE=ROOT/'config/dfm_evals_dfm14.yaml'


def heldout(language):
    package=PACKAGES/f'dfm14-dala-v2-{language}-compact'
    manifest=load(package/'manifest.json')
    release=load(package/'metadata/release.json')
    if not release['validation']['accepted_only'] or not release['tokenizer_inputs_train_only']:
        raise ValueError('Unverified heldout separation')
    selected={};pins=[]
    for kind in ('acceptability','correction'):
        heap=[]
        for relative,item in sorted(manifest['files'].items()):
            if not relative.startswith(f'data/{kind}/test_representative-'):continue
            path=package/relative
            if file_hash(path)!=item['sha256']:raise ValueError('Changed published heldout')
            pins.append(dict(path=str(path),sha256=item['sha256']))
            with gzip.open(path,'rt') as handle:
                for line in handle:
                    row=json.loads(line)
                    if row['variant']!='corrupted':continue
                    p=json.loads(row['provenance_json']);audit=json.loads(row['audit_json'])
                    d=audit['decision']
                    if (row['language']!=language or row['split']!='test' or row['view']!='representative'
                        or p['split']!='test' or p['view']!='representative' or d['decision']!='pass'
                        or any(d[k]!='yes' for k in ('clean_valid','noisy_has_error','correction_complete','meaning_preserved'))):
                        raise ValueError('Nonpassing/misbound heldout')
                    expected='no' if kind=='acceptability' else p['original']
                    if row['messages']!=[dict(role='user',content=release['prompts'][kind]+'\n\n'+p['corrupted']),
                                         dict(role='assistant',content=expected)]:
                        raise ValueError('Unexpected heldout prompt/target')
                    key=d['id'];rank=int(hashlib.sha256(('4242:'+key).encode()).hexdigest(),16)
                    value=(-rank,key,p,audit)
                    if len(heap)<1000:heapq.heappush(heap,value)
                    elif rank < -heap[0][0]:heapq.heapreplace(heap,value)
        selected[kind]={key:(p,a) for _,key,p,a in heap}
    if len(selected['acceptability'])!=1000 or set(selected['acceptability'])!=set(selected['correction']):
        raise ValueError('Insufficient or mismatched paired heldouts')
    rows=[]
    for key,(p,a) in sorted(selected['acceptability'].items()):
        if selected['correction'][key][0]!=p:raise ValueError('Paired provenance differs')
        rows.append(dict(id=key,original=p['original'],corrupted=p['corrupted'],provenance=p,compact_audit=a))
    target=OUT/language/'pairs.json';write_json(target,rows)
    return language,dict(status='ready',language=language,split='test',view='representative',pairs=1000,
        samples_per_task=2000,prompts=release['prompts'],selected=dict(path=str(target),sha256=file_hash(target)),
        input_pins=pins,quality='model-audited published paired heldouts; not native-human certification')


def main():
    with ProcessPoolExecutor(max_workers=8) as pool:held=dict(pool.map(heldout,LANGUAGES))
    # Reuse the existing validated paired-heldout reader/schema and scorers.
    write_json(MANIFEST,dict(schema='dfm13-accepted-dala-heldout-v1',release='dfm14',languages=held,seed=4242))
    sets={};tasks=[];metrics={}
    for language in LANGUAGES:
        metrics[language]={}
        for prefix,budget,batch in [('dala',32,512),('gec_dala',512,256)]:
            name=prefix+'_'+language
            sets[name]=dict(tasks=[dict(name=str(ROOT/'evaluation/dfm14_tasks.py')+'@'+prefix+'_dfm14',
                args=['-T','language='+language,'-T','manifest='+str(MANIFEST),'-T','max_gen_toks='+str(budget)])],
                args=['--model','{{target_model}}','--temperature','0'])
            tasks.append(dict(name=name,config=str(SUITE),language=language,shards=4,samples=2000,
                              max_tokens=budget,batch_size=batch))
            metrics[language][prefix]=dict(suite='dfm',scale='fraction',
                key=f'dfm_eval/{name}/'+('semantic_v1/macro_f1' if prefix=='dala' else 'exact_match/mean'))
    SUITE.write_text(yaml.safe_dump(dict(sets=sets),sort_keys=False))
    registry=dict(schema_version=1,populations=[dict(id='dfm14_new_languages_v1',kind='dfm14_new_languages',
        languages=LANGUAGES,required_tasks={l:list(metrics[l]) for l in LANGUAGES},metrics=metrics)])
    previous=next(p for p in load(ROOT/'config/multilingual_headline_populations_dfm13_dala_v2_20261006.json')['populations']
                  if p['kind']=='dfm13_all_languages')
    all_metrics={**previous['metrics'],**metrics}
    registry['populations'].append(dict(id='dfm14_all_languages_v1',kind='dfm14_all_languages',
        aggregation_policy='available_tasks_then_available_languages_v1',languages=list(all_metrics),
        required_tasks={l:list(v) for l,v in all_metrics.items()},metrics=all_metrics))
    from scripts.headline_population_registry import validate_registry
    validate_registry(registry)
    pop=ROOT/'config/multilingual_headline_populations_dfm14.json';write_json(pop,registry)
    write_json(OUT/'registry.json',dict(tasks=tasks,multilingual_manifest=str(pop),
        euroeval_gaps=LANGUAGES,reason='No native counterparts in installed EuroEval catalog',
        pins={str(p):file_hash(p) for p in (MANIFEST,SUITE,pop,ROOT/'evaluation/dfm14_tasks.py')}))
    print('Prepared 32 tasks, 128 shards per checkpoint',flush=True)


if __name__=='__main__':main()

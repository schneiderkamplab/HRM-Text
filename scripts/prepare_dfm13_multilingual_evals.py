"""CPU-only pinned DFM13 eval inventories; never edits a scheduler plan."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import gzip
import hashlib
import heapq
import json
import sys
from pathlib import Path
import yaml
from dfm12.io import file_hash, load, write_json, digest
from dfm12.dala_compact_finalize import accepted, canonical
from scripts import inspect_euroeval_dfm12 as inspect
from scripts.build_euroeval_dfm12_registry import METRICS, PYTHON

LANGUAGES='lt lv sq be bs bg hr hu lb sr sk sl fa'.split()
MODULES=dict(zip(LANGUAGES[:-1], 'lithuanian latvian albanian belarusian bosnian bulgarian croatian hungarian luxembourgish serbian slovak slovene'.split()))
ROOT=Path(__file__).resolve().parents[1]
CATALOG=Path('/work/mimir/.home/.cache/uv/archive-v0/20ddS3xsiCOjW0qI/euroeval')
OUT=ROOT/'data/dfm13/multilingual-evals-20261006-v1'
MANIFEST=ROOT/'config/dfm13_dala_heldout_20261006.json'
EURO=ROOT/'config/euroeval_dfm13_multilingual_20261006.yaml'
SUITE=ROOT/'config/dfm_evals_dfm13_multilingual_20261006.yaml'


def euro_registry():
    inspect.MODULES=list(MODULES.values())
    catalog=inspect.inspect(lambda p:(CATALOG/p).read_text(),str(CATALOG))
    entries=[]
    for language in LANGUAGES:
        for task,metric in METRICS.items():
            choices=[d for d in catalog['datasets'].values() if d['module']==MODULES.get(language)
                     and d['task_category']==task and language in d['language_codes'] and not d.get('unofficial')]
            e=dict(language=language,task=task,category=task,dataset=None,metric_key=None,
                   status='coverage_gap',include_in_average=False,metric_name=metric,
                   reason='No official registered native counterpart in pinned EuroEval18.1 catalog')
            if choices:
                d=choices[0];labels=d['language_codes'];name=d['name']
                e.update(dataset=name,datasets=[name],deduplication_key=name,group_id=language+'__'+name,
                    metric_key=f"euroeval/{'_'.join(labels)}/{task}/{name}/{metric}",
                    source_dataset=d['source'],source_url='https://huggingface.co/datasets/'+d['source'],
                    euroeval_result_languages=labels,status='supported',include_in_average=task!='european-values',
                    installed_18_1_supported=True,candidate_alternatives=[x['name'] for x in choices[1:]],
                    code_ref=d['code_ref'],catalog_code_sha256=catalog['file_sha256']['dataset_configs/'+d['module']+'.py'],
                    contamination_flags=['full_training_overlap_not_audited'],remote_access_status='not_preflighted')
                e.pop('reason')
            entries.append(e)
    old=yaml.safe_load((ROOT/'config/euroeval_dfm12_multilingual.yaml').read_text())
    return dict(schema='dfm13-euroeval-multilingual-v1',languages=LANGUAGES,categories=list(METRICS),entries=entries,
        execution=dict(old['execution'],requested_checkpoints=['step_3200000_and_future'],checkpoint_launch_authorized_here=False),
        source_evidence=dict(cached_18_1=dict(path=str(CATALOG),file_sha256=catalog['file_sha256'])),
        coverage={l:dict(supported=sum(e['dataset'] is not None for e in entries if e['language']==l),
                        gaps=[e['task'] for e in entries if e['language']==l and e['dataset'] is None]) for l in LANGUAGES},
        policy='Pinned runtime category parity; gaps explicit; no active plan or W&B edits; no benchmark-clean certification')


def checked_pin(path,sha=None):
    p=Path(path);actual=file_hash(p)
    if sha is not None and sha!=actual:raise ValueError('Input hash changed: '+str(p))
    return dict(path=str(p.resolve()),sha256=actual)


def heldout(language,output_root=None):
    source_language='pt-PT' if language=='pt_pt' else language
    package=ROOT/'exports_dfm13_dala_languages'/f'dfm13-dala-v2-{source_language}-compact'
    ready=load(package/'ready.json')
    if not ready['local_package_ready'] or not ready['one_dataset_per_language']:raise ValueError('Package not ready')
    pins=[checked_pin(package/'ready.json')]
    for item in ready['integration_pins'].values():
        pins.append(checked_pin(item['path'],item['sha256']))
        integration=load(item['path'])
        if integration['status']!='complete_train_only':raise ValueError('Heldout/train separation missing')
        for c in integration['components']:
            export=c['export_receipt'];pins.append(checked_pin(export['path'],export['sha256']))
    selected={};prompts={};counts={}
    for task in ('acceptability','correction'):
        relative='data/'+task+'/test_representative.jsonl.gz'
        path=package/relative;pins.append(checked_pin(path,ready['files'][relative]))
        heap=[];seen=set();count=eligible=0
        with gzip.open(path,'rt') as stream:
            for line in stream:
                row=json.loads(line);count+=1
                if row['language']!=source_language or row['split']!='test' or row['view']!='representative':
                    raise ValueError('Heldout split/language mismatch')
                if row['variant']!='corrupted':continue
                original=row['provenance'];audit=row['compact_audit']
                record=canonical(original,source_language,'pair')
                if not accepted(record,audit['decision'],'done') or audit['source_row_sha256']!=digest(original):
                    raise ValueError('Nonpassing or unbound heldout row')
                if original['split']!='test' or original['view']!='representative':raise ValueError('Provenance split mismatch')
                noisy=original['corrupted'];clean=original['original']
                if noisy==clean:raise ValueError('Unchanged corruption')
                if len(row['messages'])!=2 or row['messages'][0]['role']!='user' or row['messages'][1]['role']!='assistant':
                    raise ValueError('Unexpected heldout message schema')
                user=row['messages'][0]['content'];suffix='\n\n'+noisy
                if not user.endswith(suffix) or row['messages'][1]['content']!=('no' if task=='acceptability' else clean):
                    raise ValueError('Task source/target mismatch')
                prompt=user[:-len(suffix)]
                if task in prompts and prompts[task]!=prompt:raise ValueError('Mixed prompt definitions')
                prompts[task]=prompt
                key=record['id']
                if key in seen:raise ValueError('Duplicate accepted pair')
                seen.add(key);eligible+=1
                rank=int(hashlib.sha256(('4242:'+key).encode()).hexdigest(),16)
                item=(-rank,key,row)
                if len(heap)<1000:heapq.heappush(heap,item)
                elif rank < -heap[0][0]:heapq.heapreplace(heap,item)
        if count!=ready['counts'][task+':test_representative']:raise ValueError('Heldout count changed')
        selected[task]={key:row for _,key,row in heap};counts[task]=dict(total=count,eligible_pairs=eligible)
    if set(selected['acceptability'])!=set(selected['correction']):raise ValueError('LA/GEC pair selections differ')
    keys=sorted(selected['acceptability'],key=lambda k:hashlib.sha256(('4242:'+k).encode()).hexdigest())
    samples=[]
    for key in keys:
        row=selected['acceptability'][key];p=row['provenance']
        samples.append(dict(id=key,original=p['original'],corrupted=p['corrupted'],
            provenance=p,compact_audit=row['compact_audit'],publication_pool=row['publication_pool'],
            source_row_hashes={t:digest(selected[t][key]) for t in selected}))
    if len(samples)!=1000:raise ValueError('Insufficient accepted heldout pairs: '+language)
    target=(Path(output_root) if output_root is not None else OUT)/language/'pairs.json';write_json(target,samples)
    result=dict(status='ready',language=language,split='test',view='representative',pairs=len(samples),
                samples_per_task=2*len(samples),selection='seed4242 hash-ranked passing noisy pairs plus their audited clean controls',
                prompts=prompts,prompt_policy='Unchanged producer task prompts; English instructions where provided, native sentence targets',
                selected=checked_pin(target),input_pins=pins,counts=counts,
                quality='compact model-audited pairs; not native-speaker certification',
                overlap_scope='finalizer exact text/document heldout exclusion against its train pool and historical prior; not whole DFM13 semantic decontamination')
    print('HELDOUT',language,result['samples_per_task'],flush=True)
    return language,result


def definitions(euro,held):
    sets={};registry=[]
    taskfile=ROOT/'dfm-evals/dfm_evals/tasks/dala_dfm13_heldout.py'
    for language in LANGUAGES:
        for task,prefix,budget in [('acceptability','dala',32),('correction','gec_dala',512)]:
            name=prefix+'_'+language
            sets[name]=dict(description='DFM13 accepted test-representative paired controls; no train fallback',
                tasks=[dict(name=str(taskfile)+'@'+prefix+'_dfm13_heldout',args=['-T','language='+language,'-T','manifest='+str(MANIFEST),'-T','max_gen_toks='+str(budget)])],
                args=['--model','{{target_model}}','--temperature','0'])
            registry.append(dict(name=name,suite=name,config=str(SUITE),language=language,max_tokens=budget,shards=4,
                                 samples=held[language]['samples_per_task']))
    SUITE.write_text(yaml.safe_dump(dict(sets=sets),sort_keys=False))
    write_json(ROOT/'config/dfm13_dala_heldout_registry_20261006.json',registry)
    old=load(ROOT/'config/multilingual_headline_populations_semantic_v1.json')['populations'][0]
    metrics={}
    for language in LANGUAGES:
        bindings=dict(dfm_la=dict(suite='dfm',key=f'dfm_eval/dala_{language}/semantic_v1/macro_f1',scale='fraction'),
                      dfm_gec=dict(suite='dfm',key=f'dfm_eval/gec_dala_{language}/exact_match/mean',scale='fraction'))
        for e in euro['entries']:
            if e['language']==language and e['include_in_average']:
                bindings['euroeval_'+e['task']]=dict(suite='euroeval',key=e['metric_key'],scale='percent',
                                                   metric_language='_'.join(e['euroeval_result_languages']))
        metrics[language]=bindings
    pops=[]
    for kind,bindings in [('dfm13_new_languages',metrics),('dfm13_multilingual',dict(deepcopy(old['metrics']),**metrics))]:
        pops.append(dict(id=kind+'_v1',kind=kind,languages=list(bindings),
                         required_tasks={l:list(v) for l,v in bindings.items()},metrics=bindings))
    from scripts.log_dfm5_headline_averages import DANISH_KEYS, STRICT_DALA_KEY, SEMANTIC_DALA_KEY
    danish={}
    for i,key in enumerate(DANISH_KEYS):
        if key==STRICT_DALA_KEY:key=SEMANTIC_DALA_KEY
        key=key.replace('/generative-talemaader/model_graded_fact/','/generative-talemaader/model_graded_fact_v2/')
        danish['legacy_'+str(i+1)]=dict(suite='euroeval' if key.startswith('euroeval/') else 'dfm',
                                      key=key,scale='percent' if key.startswith('euroeval/') else 'fraction')
    english=next(p['metrics']['en'] for p in load(ROOT/'config/multilingual_headline_populations_semantic_v1.json')['populations'] if p['kind']=='english')
    bindings=dict(deepcopy(pops[-1]['metrics']),da=danish,en=deepcopy(english))
    pops.append(dict(id='dfm13_all_languages_v1',kind='dfm13_all_languages',languages=list(bindings),
                     required_tasks={l:list(v) for l,v in bindings.items()},metrics=bindings))
    from scripts.headline_population_registry import validate_registry
    output=validate_registry(dict(schema_version=1,populations=pops))
    write_json(ROOT/'config/multilingual_headline_populations_dfm13_20261006.json',output)


def main():
    p=argparse.ArgumentParser();p.add_argument('--preflight',action='store_true');args=p.parse_args()
    euro=euro_registry();EURO.write_text(yaml.safe_dump(euro,sort_keys=False))
    with ThreadPoolExecutor(max_workers=4) as pool:held=dict(pool.map(heldout,LANGUAGES))
    write_json(MANIFEST,dict(schema='dfm13-accepted-dala-heldout-v1',languages=held,seed=4242))
    definitions(euro,held)
    if args.preflight:
        from scripts import preflight_euroeval_dfm12 as probe
        sys.path.insert(0,str(ROOT/'scripts'))
        probe.ACCESS_TOKEN=probe.runtime_credential(euro)
        sources={}
        for e in euro['entries']:
            if e['dataset']:sources.setdefault(e['source_dataset'],set()).add(e['dataset'])
        with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(probe.check_source,sorted(sources.items())))
        probe.apply_results(euro,results)
        EURO.write_text(yaml.safe_dump(euro,sort_keys=False))
        write_json(ROOT/'config/euroeval_dfm13_multilingual_access_20261006.json',dict(sources=results,authentication='installed_framework_primary_credential',metadata_only=True))
    write_json(OUT/'completion.json',dict(complete=True,languages=LANGUAGES,dfm_tasks=26,
        euro_jobs=sum(e['dataset'] is not None for e in euro['entries']),
        files={str(p):file_hash(p) for p in [MANIFEST,EURO,SUITE,ROOT/'config/dfm13_dala_heldout_registry_20261006.json',ROOT/'config/multilingual_headline_populations_dfm13_20261006.json']},
        active_plan_modified=False,wandb_modified=False,gpu_calls=False))


if __name__=='__main__':main()

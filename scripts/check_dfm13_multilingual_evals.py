"""CPU task-construction and pin preflight; no models, W&B or plan writes."""
from pathlib import Path
import asyncio
from types import SimpleNamespace
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'dfm-evals'))
from dfm12.io import file_hash,load,write_json
from dfm_evals.tasks import dala_dfm13_heldout as tasks
from scripts.headline_population_registry import load_registry
from scripts.dala_semantic import NATIVE
from scripts.merge_dfm_eval_shards import task_metrics
from inspect_ai.scorer import Target


async def check_merge(language,samples,task_name=None):
    results={}
    for mode,labels in [('english',('yes','no')),('targets',('correct','incorrect')),
                        ('native',tuple(sorted(v)[0] if v else fallback
                                        for v,fallback in zip(NATIVE[language],('yes','no'))))]:
        records=[]
        scorer=tasks.multilingual_dala_scorer()
        for s in samples:
            completion=labels[0 if s.target=='correct' else 1]
            score=await scorer(SimpleNamespace(output=SimpleNamespace(completion=completion)),Target(s.target))
            records.append(dict(id=s.id,target=s.target,metadata=s.metadata,
                output=dict(completion=completion,choices=[]),
                scores={'linguistic-acceptability':score.model_dump()}))
        metrics=task_metrics(task_name or 'dala_'+language,records)
        if metrics['semantic_v1/macro_f1']!=1 or metrics['semantic_v1/invalid_rate']!=0:
            raise ValueError('Semantic scoring/merge failed: '+language+':'+mode)
        results[mode]=metrics
    return results


def main():
    manifest=ROOT/'config/dfm13_dala_heldout_20261006.json'
    checked=[]
    for language in tasks.LANGUAGES:
        for kind,budget in [('acceptability',32),('correction',512)]:
            task=tasks.make(language,kind,str(manifest),1,0,budget)
            samples=list(task.dataset)
            if len(samples)!=2000 or len({s.id for s in samples})!=2000:
                raise ValueError('Unexpected eval population')
            if any(s.metadata['split']!='test' for s in samples):raise ValueError('Non-test sample')
            if kind=='acceptability' and [s.target for s in samples]!=['correct','incorrect']*1000:
                raise ValueError('Paired labels changed')
            merged=asyncio.run(check_merge(language,samples)) if kind=='acceptability' else None
            checked.append(dict(language=language,task=kind,samples=len(samples),pair_count=1000,max_gen_toks=budget,
                                simulated_output_merge=merged))
        print('CONSTRUCTED',language,flush=True)
    registry=ROOT/'config/multilingual_headline_populations_dfm13_20261006.json'
    populations=load_registry(registry)
    for population in populations['populations']:
        for language in tasks.LANGUAGES:
            expected=f'dfm_eval/dala_{language}/semantic_v1/macro_f1'
            if population['metrics'][language]['dfm_la']['key']!=expected:
                raise ValueError('Average does not consume merged semantic metric')
    receipt=dict(valid=True,tasks=checked,no_generation=True,gpu_calls=False,
                 files={str(p):file_hash(p) for p in (manifest,registry,Path(tasks.__file__),Path(__file__),
                     ROOT/'scripts/dala_semantic.py',ROOT/'scripts/merge_dfm_eval_shards.py',
                     ROOT/'scripts/headline_population_registry.py')})
    write_json(ROOT/'config/dfm13_dala_heldout_preflight_20261006.json',receipt)
    complete=ROOT/'data/dfm13/multilingual-evals-20261006-v1/completion.json'
    result=load(complete)
    for p in result['files']:result['files'][p]=file_hash(p)
    result['task_preflight']=dict(path=str(ROOT/'config/dfm13_dala_heldout_preflight_20261006.json'),
                                 sha256=file_hash(ROOT/'config/dfm13_dala_heldout_preflight_20261006.json'))
    access=ROOT/'config/euroeval_dfm13_multilingual_access_20261006.json'
    result['euro_access']=dict(path=str(access),sha256=file_hash(access),
                             accessible=sum(s['status']=='accessible' for s in load(access)['sources']))
    write_json(complete,result)


if __name__=='__main__':main()

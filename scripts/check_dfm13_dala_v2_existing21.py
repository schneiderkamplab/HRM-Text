"""Real heldout construction -> simulated scoring -> merge -> average CPU check."""
import asyncio
import sys
from types import SimpleNamespace
from scripts.prepare_dfm13_dala_v2_existing21 import ROOT,OUT,MANIFEST,SUITE,REGISTRY,AVERAGES,LANGUAGES
sys.path.insert(0,str(ROOT/'dfm-evals'))
from dfm12.io import load,write_json,file_hash
from dfm_evals.tasks import dala_v2_heldout as tasks
from dfm_evals.tasks.gec_dala import gec_dala_scorer
from inspect_ai.scorer import Target
from scripts.check_dfm13_multilingual_evals import check_merge
from scripts.merge_dfm_eval_shards import task_metrics
from scripts.headline_population_registry import build_population_row,load_registry
from scripts.log_multilingual_headline_averages import PopulationItem


async def check_gec(samples,task_name):
    records=[];scorer=gec_dala_scorer()
    for sample in samples:
        score=await scorer(SimpleNamespace(output=SimpleNamespace(completion=sample.target)),Target(sample.target))
        records.append(dict(scores={'gec_dala_scorer':score.model_dump()}))
    result=task_metrics(task_name,records)
    if result.get('exact_match/mean')!=1:raise ValueError('Correction merge failed')
    return result


def main():
    evidence=[];merged={}
    for language in LANGUAGES:
        for prefix,constructor in [('dala_v2',tasks.dala_v2_heldout),('gec_dala_v2',tasks.gec_dala_v2_heldout)]:
            name=prefix+'_'+language
            task=constructor(language,manifest=str(MANIFEST));samples=list(task.dataset)
            if len(samples)!=2000 or len({s.id for s in samples})!=2000:raise ValueError('Count/identity mismatch')
            if any(s.metadata['split']!='test' for s in samples):raise ValueError('Non-test data')
            if prefix=='dala_v2':
                if [s.target for s in samples]!=['correct','incorrect']*1000:raise ValueError('Unbalanced')
                checks=asyncio.run(check_merge(language,samples,name));metrics=checks['native']
            else:
                checks=metrics=asyncio.run(check_gec(samples,name))
            merged.update({f'dfm_eval/{name}/{key}':value for key,value in metrics.items()})
            evidence.append(dict(task=name,samples=len(samples),simulated_scores=checks))
        print('SCORED_MERGED',language,flush=True)
    registry=load_registry(AVERAGES)
    # Other tasks are explicit synthetic controls, not claimed real eval results.
    for pop in registry['populations']:
        for bindings in pop['metrics'].values():
            for binding in bindings.values():
                merged.setdefault(binding['key'],100 if binding['scale']=='percent' else 1)
    probe=OUT/'simulated-average';write_json(probe/'merged_metrics.json',merged)
    row,_=build_population_row(PopulationItem(1,1,[probe],[probe],[probe]),registry)
    for pop in registry['populations']:
        if row.get('avg_population/'+pop['id']+'/score')!=1:raise ValueError('Average integration failed')
    write_json(OUT/'completion.json',dict(complete=True,no_model_calls=True,simulated_outputs=True,
        tasks=evidence,average_scores=row,
        files={str(p):file_hash(p) for p in (MANIFEST,SUITE,REGISTRY,AVERAGES,
            ROOT/'scripts/merge_dfm_eval_shards.py',ROOT/'scripts/dala_semantic.py',
            ROOT/'dfm-evals/dfm_evals/tasks/dala_v2_heldout.py',
            ROOT/'dfm-evals/dfm_evals/tasks/dala_dfm13_heldout.py')}))


if __name__=='__main__':main()

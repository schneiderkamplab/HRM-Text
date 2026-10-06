"""Prepare additional v2 heldouts and opt-in successor averages; no eval launch."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import yaml
from dfm12.io import load,write_json,file_hash
from scripts.prepare_dfm13_multilingual_evals import ROOT,heldout
from scripts.headline_population_registry import validate_registry

LANGUAGES=tuple('da en nb nn sv is fo nl pl de fr es it cs pt_pt fi et ca el ro uk'.split())
OUT=ROOT/'data/dfm13/dala-v2-existing21-evals-20261006-v1'
MANIFEST=ROOT/'config/dfm13_dala_v2_existing21_20261006.json'
SUITE=ROOT/'config/dfm_evals_dfm13_dala_v2_existing21_20261006.yaml'
REGISTRY=ROOT/'config/dfm13_dala_v2_existing21_registry_20261006.json'
AVERAGES=ROOT/'config/multilingual_headline_populations_dfm13_dala_v2_20261006.json'


def average_definitions(previous):
    result=deepcopy(previous)
    for pop in result['populations']:
        added=set(pop['languages']) & set(LANGUAGES)
        if not added:continue
        pop['id']=pop['id'].removesuffix('_v1')+'_v2'
        for language in sorted(added):
            for name,key in [('dfm_la_v2',f'dfm_eval/dala_v2_{language}/semantic_v1/macro_f1'),
                             ('dfm_gec_v2',f'dfm_eval/gec_dala_v2_{language}/exact_match/mean')]:
                pop['metrics'][language][name]=dict(suite='dfm',key=key,scale='fraction')
                pop['required_tasks'][language].append(name)
    return validate_registry(result)


def main():
    with ThreadPoolExecutor(max_workers=4) as pool:
        held=dict(pool.map(lambda language:heldout(language,OUT),LANGUAGES))
    write_json(MANIFEST,dict(schema='dfm13-accepted-dala-heldout-v1',languages=held,seed=4242))
    sets={};registry=[]
    module=ROOT/'dfm-evals/dfm_evals/tasks/dala_v2_heldout.py'
    for language in LANGUAGES:
        for prefix,budget in [('dala_v2',32),('gec_dala_v2',512)]:
            name=prefix+'_'+language
            sets[name]=dict(description='Additional accepted-v2 test representative; historical task unchanged',
                tasks=[dict(name=str(module)+'@'+prefix+'_heldout',args=['-T','language='+language,
                    '-T','manifest='+str(MANIFEST),'-T','max_gen_toks='+str(budget)])],
                args=['--model','{{target_model}}','--temperature','0'])
            registry.append(dict(name=name,suite=name,config=str(SUITE),language=language,
                max_tokens=budget,shards=4,samples=held[language]['samples_per_task']))
    SUITE.write_text(yaml.safe_dump(dict(sets=sets),sort_keys=False))
    write_json(REGISTRY,registry)
    write_json(AVERAGES,average_definitions(load(ROOT/'config/multilingual_headline_populations_dfm13_20261006.json')))
    write_json(OUT/'preparation.json',dict(prepared=True,preflight_required=True,languages=list(LANGUAGES),
        tasks=42,pairs=21000,samples=84000,gpu_calls=False,
        files={str(p):file_hash(p) for p in (MANIFEST,SUITE,REGISTRY,AVERAGES)}))


if __name__=='__main__':main()

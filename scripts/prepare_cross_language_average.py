"""Schedule the explicit 21-language comparison for epoch 10 and 2900K."""
import argparse
import json
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'eval_scheduler'))
from eval_scheduler.model import Action, JobStatus, read_plan, write_plan
from eval_scheduler.locking import PlanLock
from scripts.append_euroeval_language_additions import extend
from scripts.headline_population_registry import validate_registry

LANGUAGES = 'da en nb nn sv is fo nl pl de fr es it cs pt_pt fi et ca el ro uk'.split()
MANIFEST = ROOT/'config/cross_language_average_v1.json'
TASKS = ROOT/'config/cross_language_multiwikiqa.json'
TAGS = ('epoch_10', 'step_2900000')


def registry():
    population = dict(id='cross_language_v1', kind='cross_language', languages=LANGUAGES,
                      required_tasks={}, metrics={})
    for lang in LANGUAGES:
        suffix = 'pt' if lang == 'pt_pt' else lang
        ns = {'nb':'nb_no', 'nn':'nn_no', 'pt_pt':'pt_pt-pt'}.get(lang,lang)
        def euro(dataset, category, metric, namespace=ns):
            return dict(suite='euroeval', key=f'euroeval/{namespace}/{category}/{dataset}/{metric}',
                        scale='percent', metric_language=namespace)
        ds = '' if lang == 'da' else '_'+lang
        metrics = dict(
            scala=euro('scala-'+suffix,'linguistic-acceptability','macro_f1'),
            multiifeval=euro('multi-ifeval-'+suffix,'instruction-following','instruction_accuracy',
                            'pt' if lang=='pt_pt' else ns),
            dfm_la=dict(suite='dfm',key=f'dfm_eval/dala{ds}/linguistic-acceptability/dfm_evals_macro_f1',scale='fraction'),
            dfm_gec=dict(suite='dfm',key=f'dfm_eval/gec_dala{ds}/exact_match/mean',scale='fraction'))
        if lang != 'cs':
            metrics['multiwikiqa'] = euro('multi-wiki-qa-'+suffix,'reading-comprehension','f1')
        population['metrics'][lang] = metrics
        population['required_tasks'][lang] = list(metrics)
    return validate_registry(dict(schema_version=1,populations=[population]))


def tasks():
    return [dict(dataset='multi-wiki-qa-'+('pt' if l=='pt_pt' else l), language=l,
                 category='reading-comprehension', metric='f1',
                 source='EuroEval/multi-wiki-qa-'+{'nb':'no','pt_pt':'pt-pt'}.get(l,l)+'-mini')
            for l in LANGUAGES if l!='cs']


def add_average_jobs(jobs, manifest):
    result = list(jobs)
    population = manifest['populations'][0]
    euro_names = {b['key'].split('/')[3] for m in population['metrics'].values()
                  for b in m.values() if b['suite']=='euroeval'}
    dfm_names = {b['key'].split('/')[1] for m in population['metrics'].values()
                 for b in m.values() if b['suite']=='dfm'}
    for tag in TAGS:
        identifier = f'cross-language-{tag}-average'
        if any(j.job_id==identifier for j in result):
            continue
        template = next(j for j in jobs if j.action==Action.AVERAGE
                        and j.metadata.get('ckpt_tag')==tag
                        and j.metadata.get('multilingual_manifest'))
        candidates = [j for j in jobs if j.metadata.get('ckpt_tag')==tag]
        deps = [j.job_id for j in candidates if
                (j.action in (Action.EVAL_EUROEVAL, Action.EVAL_EUROEVAL_BATCHED_IFEVAL) and j.name in euro_names)
                or (j.action==Action.MERGE_DFM and j.name in dfm_names)]
        missing_euro = euro_names - {j.name for j in candidates if j.action in
                                    (Action.EVAL_EUROEVAL, Action.EVAL_EUROEVAL_BATCHED_IFEVAL)}
        if tag=='epoch_10':
            missing_euro -= {'scala-da','scala-en','multi-wiki-qa-da'}
        if missing_euro:
            raise ValueError('Missing eval dependencies: '+str(missing_euro))
        meta = {**template.metadata,'multilingual_manifest':str(MANIFEST),
                'population_require_complete':True}
        if tag=='epoch_10':
            meta['additional_euroeval_roots'] = [*meta['additional_euroeval_roots'],
                str(ROOT/'data/eval/dfm11-xl-epoch10-danish-comparison-20260930')]
        result.append(template.with_updates(job_id=identifier,name='cross_language_v1',
            deps=tuple(deps),status=JobStatus.PENDING,attempt=0,metadata=meta,
            log_dir=str(ROOT/'logs/scheduler/dfm12_XL_epoch11_noidentity/cross_language'/tag)))
    return result


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    manifest=registry()
    MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')
    TASKS.write_text(json.dumps(tasks(),indent=2)+'\n')
    if not args.apply:
        print(MANIFEST, TASKS)
        return
    plan=ROOT/'logs/scheduler/dfm12_XL_epoch11_noidentity'
    with PlanLock(plan):
        jobs=read_plan(plan/'plan.tsv')
        # Restrict new evaluations to the two requested checkpoints, then
        # merge back without touching other checkpoints or row ordering.
        subset=[j for j in jobs if j.metadata.get('ckpt_tag') in TAGS]
        # Danish baseline is already completed and provenance-bound below;
        # avoid creating a duplicate artifact for the same metric.
        expanded,ids=extend(subset,[t for t in tasks() if t['language']!='da'])
        old_ids={j.job_id for j in jobs}
        replacements={j.job_id:j for j in expanded}
        result=[replacements.get(j.job_id,j) for j in jobs]
        result.extend(j for j in expanded if j.job_id not in old_ids)
        result=add_average_jobs(result,manifest)
        stamp=datetime.now().strftime('%Y%m%d-%H%M%S')
        write_plan(plan/f'plan.before-cross-language-{stamp}.tsv',jobs)
        write_plan(plan/'plan.tsv',result)
        print(json.dumps({'new_evals':ids,'new_rows':len(result)-len(jobs)},indent=2))


if __name__=='__main__':
    main()

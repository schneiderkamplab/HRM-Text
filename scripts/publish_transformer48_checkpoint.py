"""Publish existing, completed task metrics in one W&B transaction; never rerun evals."""
import argparse
import json
import math
import sqlite3
from pathlib import Path
try:
    from wandb_writer_lock import wandb_writer_lock
except ModuleNotFoundError:
    from scripts.wandb_writer_lock import wandb_writer_lock


def collect(database, tag):
    c=sqlite3.connect(f'file:{database}?mode=ro',uri=True)
    metrics={};files=[];conflicts=[];metadata=None
    for raw,log,status in c.execute('select definition,log_dir,status from jobs where job_id like ?', (f'transformer48-{tag}-%',)):
        d=json.loads(raw);m=json.loads(d['metadata_json']);a=d['action']
        if a not in {'merge_standard','merge_dfm','merge_ifeval','merge_euroeval'}:continue
        if status!='done':raise ValueError(f"Incomplete publication input: {d['job_id']}: {status}")
        metadata=m
        if a=='merge_standard':p=Path(m['log_root'])/'standard_shards'/d['name']/'merged_metrics.json'
        elif a=='merge_dfm':p=Path(m['dfm_log_root'])/d['name']/'merged_metrics.json'
        elif a=='merge_ifeval':p=Path(m['dfm_log_root'])/'merged_ifeval_da_metrics.json'
        else:p=Path(log)/('wandb_metrics.json' if m.get('euroeval_inference_action')=='eval_euroeval_batched_ifeval' else 'merged_metrics.json')
        data=json.loads(p.read_text());values=data.get('metrics',data)
        recorded=data.get('step',data.get('euroeval/train_step'))
        if recorded is not None and recorded!=m['eval_step']:raise ValueError(f'Wrong checkpoint in {p}')
        for key,value in values.items():
            if '/' not in key or not isinstance(value,(int,float)) or not math.isfinite(value):continue
            if key in metrics and metrics[key]!=value:
                conflicts.append({'key':key,'previous':metrics[key],'value':value,'path':str(p)})
            metrics[key]=value
        files.append(str(p))
    if not files:raise ValueError('No metrics found')
    if conflicts:raise ValueError(f'Conflicting metric values: {conflicts[:5]}')
    for prefix in ('eval','dfm_eval','euroeval'):
        metrics[prefix+'/epoch']=metadata['eval_epoch'];metrics[prefix+'/train_step']=metadata['eval_step']
    return metrics,files,metadata


def main():
    p=argparse.ArgumentParser();p.add_argument('--database',required=True);p.add_argument('--tag',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--publish',action='store_true');a=p.parse_args()
    metrics,files,m=collect(a.database,a.tag)
    receipt={'tag':a.tag,'step':m['eval_step'],'files':files,'metrics':metrics,'synced':False}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(receipt,indent=2))
    print(f'Validated {len(files)} merged artifacts and {len(metrics)} metrics',flush=True)
    if a.publish:
        import wandb
        with wandb_writer_lock(m['wandb_run_id']):
            run=wandb.init(entity='peter-sk-sdu',project=m['wandb_project'],id=m['wandb_run_id'],resume='allow')
            for key in metrics:
                prefix=key.split('/')[0]
                if key.endswith(('/epoch','/train_step')):run.define_metric(key)
                else:run.define_metric(key,step_metric=prefix+'/train_step',summary='last')
            run.log(metrics,commit=True);run.summary.update(metrics);run.finish()
        receipt['synced']=True;a.output.write_text(json.dumps(receipt,indent=2));print('Bulk W&B sync completed',flush=True)

if __name__=='__main__':main()

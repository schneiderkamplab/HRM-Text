#!/home/ucloud/miniforge3/envs/hrm/bin/python
"""Publish completed v2 sidecars locally; deliberately no W&B sync."""
import fcntl
import json
from pathlib import Path
import runpy
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.rejudge_talemaader_v2 import digest, atomic, PREFIX


def publish(output):
    with (output/'local-publish.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        read=lambda p:json.loads(p.read_text())
        complete=read(output/'completed.json');manifest=read(output/'manifest.json');rows=read(output/'rows.json')
        if digest(manifest)!=complete['manifest_sha256'] or digest(rows)!=complete['rows_sha256']:
            raise ValueError('Completion binding mismatch')
        if len(rows)!=complete['points'] or len(manifest['points'])!=len(rows):
            raise ValueError('Incomplete points')
        artifacts=[]
        for point in manifest['points']:
            report=read(output/(point['id']+'.json'))
            row=report['row']
            if report['point']!=point or row not in rows:
                raise ValueError('Point/row mismatch')
            if row.get('dfm_eval/epoch')!=point['epoch'] or row.get('dfm_eval/train_step')!=point['train_step']:
                raise ValueError('Checkpoint mismatch')
            if row.get(PREFIX+'/n')!=point['expected_n']:
                raise ValueError('Sample count mismatch')
            if not point.get('merged_metrics'):continue
            path=Path(point['merged_metrics']).with_name('merged_metrics_v2.json')
            artifact=dict(epoch=point['epoch'],step=point['train_step'],num_samples=point['expected_n'],
                inputs=point['inputs'],metrics={k:v for k,v in row.items() if k.startswith(PREFIX+'/')})
            if path.exists() and read(path)!=artifact:raise ValueError('Existing sidecar differs: '+str(path))
            artifacts.append((path,artifact))
        for path,artifact in artifacts:atomic(path,artifact)
        receipt=dict(points=len(rows),sidecars=len(artifacts),rows_sha256=complete['rows_sha256'],
                     wandb_history_written=False,historical_sync_deferred=True)
        atomic(output/'local-published.json',receipt)
        return receipt


if __name__=='__main__':
    if sys.argv[1:]!=['scripts/generate_dfm5_l_eval_comparison_report.py']:
        raise SystemExit('Scheduler-only REPORT bridge')
    from scripts.schedule_dfm13_wave34_baseline import PLAN,PlanLock,read_plan
    validate=runpy.run_path(str(ROOT/'scripts/talemaader_v2_scheduler_sync'))['validate']
    with PlanLock(PLAN):validate(read_plan(PLAN/'plan.tsv'),sys.argv[1:])
    print(json.dumps(publish(ROOT/'logs/rejudge_talemaader_v2')))

"""Append causal target-only B and resumed causal all-token B; never replace live rows."""
import argparse, copy, hashlib, json, os, sqlite3, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from eval_scheduler.model import Job, JobStatus, write_plan
from eval_scheduler.store import _validate_graph, _definition
from eval_scheduler.preflight import check_job, check_artifact_isolation
from scripts.prepare_transformer48_eval_plan import replace
from training_suspend.supervisor import overrides
DB=Path('/var/tmp/dfm11-architecture-comparison/jobs.sqlite')
PLAN=ROOT/'logs/scheduler/dfm11_architecture_comparison_20261110'
OUT=PLAN/'objective-ablation-20261114'
PY='/home/ucloud/miniforge3/envs/hrm/bin/python'
BASE='B-dfm11-prefixlm-lrauto-bpwarmup-targetonly-epoch1'
NEW='B-dfm11-causal-lrauto-bpwarmup-targetonly-epoch1'
OLD='B-dfm11-causal-lrauto-bpwarmup-alltokens-epoch1'
NEWOUT=ROOT/'logs/training/B_dfm11_causal_targetonly_20261114'
OLDOUT=ROOT/'logs/training/B_dfm11_causal_lrauto_bpwarmup_20261110'
FINAL=393732

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--execute',action='store_true');args=ap.parse_args()
    c=sqlite3.connect(DB,timeout=60)
    rows=c.execute('select * from jobs order by position').fetchall()
    original={r[0]:Job.from_row(json.loads(r[2])).with_updates(status=JobStatus(r[5]),attempt=r[6],log_dir=r[7]) for r in rows}
    assert not any(k.startswith('btarget-dfm11-') for k in original),'Already installed'
    OUT.mkdir(exist_ok=True);NEWOUT.mkdir(exist_ok=True)
    newckpt=ROOT/'checkpoints/hrm'/NEW
    newckpt.mkdir(exist_ok=True);assert not any(newckpt.iterdir())
    settings=json.loads((OLDOUT/'launcher-settings.json').read_text());settings['allow_existing_peers']=False
    (NEWOUT/'launcher-settings.json').write_text(json.dumps(settings,indent=2))
    # A separate settings file preserves the historical run's launch receipt.
    (OUT/'alltoken-launcher-settings.json').write_text(json.dumps(settings,indent=2))
    template=original['bauto-dfm11-step_100000-train'].metadata['cooperative_training']['command']
    models={
      'target':dict(prefix='btarget-dfm11',run=NEW,out=NEWOUT,namespace='B_dfm11_causal_targetonly',settings=NEWOUT/'launcher-settings.json',target=True),
      'all':dict(prefix='bauto-dfm11',run=OLD,out=OLDOUT,namespace='B_dfm11_causal_lrauto_bpwarmup',settings=OUT/'alltoken-launcher-settings.json',target=False)}
    for spec in models.values():
        cmd=[x for x in template if not x.lstrip('+').startswith(('resume_', 'suspend_control_dir='))]
        spec['command']=overrides(cmd,{'data.target_only':str(spec['target']).lower(),'checkpoint_path':str(ROOT/'checkpoints/hrm'/spec['run']),'run_name':spec['run'],'wandb_run_id':spec['run'],'suspend_after_steps':'[50000,100000,150000,200000,250000,300000,350000]'})
        i=spec['command'].index('pretrain.py')
        resolved=subprocess.check_output([PY,'pretrain.py',*spec['command'][i+1:],'--cfg','job','--resolve'],cwd=ROOT,env={**os.environ,'TMPDIR':'/dev/shm/hrm-b-recovery','PATH':str(Path(PY).parent)+':'+os.environ['PATH']})
        (OUT/(spec['prefix']+'-resolved.yaml')).write_bytes(resolved)
        spec['config_sha256']=hashlib.sha256(resolved).hexdigest()
    stages=[('target',50000),('target',100000)]
    for step in [150000,200000,250000,300000,350000,FINAL]:stages += [('all',step),('target',step)]
    # Complete both currently scheduled final evaluation blocks first. Real work,
    # not vacuous barriers/teardowns, anchors the terminal gate.
    previous=[j.job_id for j in original.values() if any(j.job_id.startswith(p+'-epoch_1-eval') for p in ['transformer48','bprefix-dfm11']) and (j.action.startswith('eval_') or j.action in ('export_hf','wait_checkpoint','average','report'))]
    additions=[];prior=None;prior_step=None;order=[]
    for model,step in stages:
        spec=models[model];tag='epoch_1' if step==FINAL else f'step_{step}'
        source=[j for j in original.values() if j.job_id.startswith('bprefix-dfm11-'+tag+'-')]
        assert len(source)==2204,(tag,len(source))
        pairs=[('bprefix-dfm11',spec['prefix']),(BASE,spec['run']),('B_dfm11_prefixlm_lrauto_bpwarmup_20261111',spec['out'].name),('B_dfm11_prefixlm_lrauto_bpwarmup',spec['namespace']),('B-dfm11-prefixlm',spec['prefix'])]
        block=[]
        for j in source:
            m=replace(copy.deepcopy(j.metadata),pairs);jid=replace(j.job_id,pairs)
            assert jid not in original
            m.pop('transformer_single_pass',None);m['recurrent_causal']=True
            m['user_training_pause']=False
            m['eval_step']=step;m['eval_epoch']=1.0 if step==FINAL else step/FINAL;m['xl_boundary']=step
            log=replace(j.log_dir,pairs)
            if j.action=='train_until_step':
                co=m['cooperative_training'];co.update(command=spec['command'],control_root=str(spec['out']/'control'),launcher_settings=str(spec['settings']),allowed_existing_peer_identities=[],scheduled_disk_resume=True)
                co.pop('disk_handoff_from',None)
                if prior is not None and prior!=model and prior_step!=FINAL:co['disk_handoff_from']={'control_root':str(models[prior]['out']/'control'),'step':prior_step}
                if step==50000:m.pop('resume_from_tag',None);m.pop('resume_ckpt_path',None)
                else:m.update(resume_from_tag=f'step_{350000 if step==FINAL else step-50000}',resume_ckpt_path=m['ckpt_path'])
                if step==FINAL:co['finalize_command']=[PY,str(ROOT/'scripts/finalize_transformer48_epoch.py'),str(DB),m['ckpt_path']]
                deps=tuple(previous);log=str(PLAN/'runs'/jid)
            else:deps=tuple(replace(x,pairs) for x in j.deps)
            block.append(j.with_updates(job_id=jid,metadata=m,deps=deps,status=JobStatus.PENDING,attempt=0,log_dir=log))
        additions+=block
        previous=[j.job_id for j in block if j.action.startswith('eval_') or j.action in ('wait_checkpoint','export_hf')]
        order.append({'model':model,'boundary':tag});prior=model;prior_step=step
    candidates=list(original.values())+additions
    _validate_graph(candidates)
    errors={j.job_id:e for j in additions if (e:=check_job(j,ROOT))}
    collisions=check_artifact_isolation(candidates,ROOT)
    report={'jobs':len(additions),'order':order,'preflight_errors':errors,'artifact_collisions':collisions,'executed':False,'configs':{k:v['config_sha256'] for k,v in models.items()}}
    (OUT/'preflight.json').write_text(json.dumps(report,indent=2));assert not errors and not collisions
    write_plan(OUT/'additions.tsv',additions)
    if args.execute:
        backup=sqlite3.connect(OUT/f'before-{int(time.time())}.sqlite');c.backup(backup);backup.close()
        c.execute('begin immediate')
        assert c.execute("select count(*) from jobs where job_id like 'btarget-dfm11-%'").fetchone()[0]==0
        pos=c.execute('select max(position) from jobs').fetchone()[0]+1
        for i,j in enumerate(additions):
            d=json.loads(_definition(j))
            c.execute('insert into jobs values (?,?,?,?,?,?,?,?,?)',(j.job_id,pos+i,json.dumps(d),j.deps_mode,int(j.action == 'eval_euroeval' and j.name.startswith('valeu-')),'pending',0,j.log_dir,None))
            c.executemany('insert into dependencies values (?,?)',[(j.job_id,dep) for dep in j.deps])
        c.commit();report['executed']=True
    (OUT/('receipt.json' if args.execute else 'dry-run.json')).write_text(json.dumps(report,indent=2));print(json.dumps(report))

if __name__=='__main__':main()

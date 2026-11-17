"""Add PrefixLM Transformer rotation and a subsequent causal target-only Transformer."""
import argparse,copy,hashlib,json,os,sqlite3,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from eval_scheduler.model import Job,JobStatus,write_plan
from eval_scheduler.store import _validate_graph,_definition
from eval_scheduler.preflight import check_job,check_artifact_isolation
from scripts.prepare_transformer48_eval_plan import replace
from training_suspend.supervisor import overrides
DB=Path('/var/tmp/dfm11-architecture-comparison/jobs.sqlite');PLAN=ROOT/'logs/scheduler/dfm11_architecture_comparison_20261110'
OUT=PLAN/'objective-ablation-20261114';PY='/home/ucloud/miniforge3/envs/hrm/bin/python';FINAL=393732
STEPS=[50000,100000,150000,200000,250000,300000,350000,FINAL]
def tag(s):return 'epoch_1' if s==FINAL else f'step_{s}'
def work(j):return j.action.startswith('eval_') or j.action in ('wait_checkpoint','export_hf')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--execute',action='store_true');args=ap.parse_args()
    c=sqlite3.connect(DB,timeout=60);rows=c.execute('select * from jobs order by position').fetchall()
    snapshots={r[0]:r for r in rows}
    original={r[0]:Job.from_row(json.loads(r[2])).with_updates(status=JobStatus(r[5]),attempt=r[6],log_dir=r[7]) for r in rows}
    assert not any(k.startswith(('tprefix-dfm11-','ttarget-dfm11-')) for k in original)
    basecmd=original['transformer48-step_350000-train'].metadata['cooperative_training']['command']
    additions=[];specs={};configs={}
    for name,attn in [('tprefix','prefixlm'),('ttarget','causal')]:
        run=f'transformer48-dfm11-{attn}-targetonly-epoch1';out=ROOT/f'logs/training/transformer48_dfm11_{attn}_targetonly_20261114';ckpt=ROOT/'checkpoints/transformer'/run
        out.mkdir(exist_ok=True);ckpt.mkdir(exist_ok=True);assert not any(ckpt.iterdir())
        settings=json.loads((OUT/'alltoken-launcher-settings.json').read_text());(out/'launcher-settings.json').write_text(json.dumps(settings,indent=2))
        cmd=[x for x in basecmd if not x.lstrip('+').startswith(('resume_', 'suspend_control_dir='))]
        cmd=overrides(cmd,{'arch.attn_type':attn,'data.target_only':'true','checkpoint_path':str(ckpt),'run_name':run,'wandb_run_id':run,'suspend_after_steps':'[50000,100000,150000,200000,250000,300000,350000]'})
        cmd=[('+'+x) if x==f'arch.attn_type={attn}' else x for x in cmd]
        i=cmd.index('pretrain.py');cfg=subprocess.check_output([PY,'pretrain.py',*cmd[i+1:],'--cfg','job','--resolve'],cwd=ROOT,env={**os.environ,'TMPDIR':'/dev/shm/hrm-b-recovery','PATH':str(Path(PY).parent)+':'+os.environ['PATH']})
        (out/'resolved-config.yaml').write_bytes(cfg);configs[name]=hashlib.sha256(cfg).hexdigest()
        specs[name]={'prefix':name+'-dfm11','out':out,'cmd':cmd}
        pairs=[('bprefix-dfm11',name+'-dfm11'),('B-dfm11-prefixlm-lrauto-bpwarmup-targetonly-epoch1',run),('checkpoints/hrm/'+run,'checkpoints/transformer/'+run),('B_dfm11_prefixlm_lrauto_bpwarmup_20261111',out.name),('B_dfm11_prefixlm_lrauto_bpwarmup',f'transformer48_dfm11_{attn}_targetonly'),('B-dfm11-prefixlm',name+'-dfm11')]
        for step in STEPS:
            source=[j for j in original.values() if j.job_id.startswith('bprefix-dfm11-'+tag(step)+'-')];assert len(source)==2204
            for j in source:
                m=replace(copy.deepcopy(j.metadata),pairs);jid=replace(j.job_id,pairs);log=replace(j.log_dir,pairs)
                m.pop('recurrent_causal',None);m['transformer_single_pass']=True;m['user_training_pause']=False
                if j.action=='train_until_step':
                    co=m['cooperative_training'];co.update(command=cmd,control_root=str(out/'control'),launcher_settings=str(out/'launcher-settings.json'),allowed_existing_peer_identities=[],scheduled_disk_resume=True)
                    co.pop('disk_handoff_from',None)
                    if step==50000:m.pop('resume_from_tag',None);m.pop('resume_ckpt_path',None)
                    else:m.update(resume_from_tag=f'step_{350000 if step==FINAL else step-50000}',resume_ckpt_path=str(ckpt))
                    if step==FINAL:co['finalize_command']=[PY,str(ROOT/'scripts/finalize_transformer48_epoch.py'),str(DB),str(ckpt)]
                    log=str(PLAN/'runs'/jid)
                additions.append(j.with_updates(job_id=jid,metadata=m,deps=tuple(replace(d,pairs) for d in j.deps),status=JobStatus.PENDING,attempt=0,log_dir=log))
    byid={**original,**{j.job_id:j for j in additions}}
    stages=[('btarget',50000),('tprefix',50000),('btarget',100000),('tprefix',100000)]
    for step in STEPS[2:]:stages += [('bauto',step),('btarget',step),('tprefix',step)]
    stages += [('ttarget',step) for step in STEPS]
    controls={'btarget':ROOT/'logs/training/B_dfm11_causal_targetonly_20261114/control','bauto':ROOT/'logs/training/B_dfm11_causal_lrauto_bpwarmup_20261110/control',**{k:v['out']/'control' for k,v in specs.items()}}
    changes={};previous=None;prior=None;prior_step=None
    for model,step in stages:
        prefix=model+'-dfm11-'+tag(step);jid=prefix+'-train';j=byid[jid]
        assert j.status==JobStatus.PENDING
        m=copy.deepcopy(j.metadata);co=m['cooperative_training'];co.pop('disk_handoff_from',None)
        if prior and prior!=model and prior_step!=FINAL:co['disk_handoff_from']={'control_root':str(controls[prior]),'step':prior_step}
        deps=j.deps if previous is None else tuple(previous)
        if model=='ttarget' and step==50000:
            deps=tuple(k for k,v in byid.items() if any(k.startswith(p+'-dfm11-epoch_1-eval') for p in ('btarget','bauto','tprefix')) and (work(v) or v.action in ('average','report')))
        changed=j.with_updates(metadata=m,deps=deps,deps_mode='terminal');byid[jid]=changed
        if jid in original and changed!=original[jid]:changes[jid]=changed
        previous=[k for k,v in byid.items() if k.startswith(prefix+'-eval') and work(v)]
        assert previous
        prior=model;prior_step=step
    additions=[byid[j.job_id] for j in additions]
    candidates=list(byid.values());_validate_graph(candidates)
    check=additions+list(changes.values());errors={j.job_id:e for j in check if (e:=check_job(j,ROOT))};collisions=check_artifact_isolation(candidates,ROOT)
    report={'added_rows':len(additions),'changed_pending_train_rows':len(changes),'order':[(m,tag(s)) for m,s in stages],'errors':errors,'artifact_collisions':collisions,'config_sha256':configs,'executed':False}
    (OUT/'transformers-preflight.json').write_text(json.dumps(report,indent=2));assert not errors and not collisions
    write_plan(OUT/'transformer-additions.tsv',additions)
    if args.execute:
        backup=sqlite3.connect(OUT/f'before-transformers-{int(time.time())}.sqlite');c.backup(backup);backup.close()
        c.execute('begin immediate')
        assert c.execute("select count(*) from jobs where job_id like 'tprefix-dfm11-%' or job_id like 'ttarget-dfm11-%'").fetchone()[0]==0
        for jid in changes:assert c.execute('select * from jobs where job_id=?',(jid,)).fetchone()==snapshots[jid],jid
        for jid,j in changes.items():
            c.execute('update jobs set definition=?,deps_mode=? where job_id=?',(_definition(j),j.deps_mode,jid));c.execute('delete from dependencies where job_id=?',(jid,));c.executemany('insert into dependencies values (?,?)',[(jid,d) for d in j.deps])
        pos=c.execute('select max(position) from jobs').fetchone()[0]+1
        for i,j in enumerate(additions):
            c.execute('insert into jobs values (?,?,?,?,?,?,?,?,?)',(j.job_id,pos+i,_definition(j),j.deps_mode,int(j.action=='eval_euroeval' and j.name.startswith('valeu-')),'pending',0,j.log_dir,None));c.executemany('insert into dependencies values (?,?)',[(j.job_id,d) for d in j.deps])
        c.commit();report['executed']=True
    (OUT/('transformers-receipt.json' if args.execute else 'transformers-dry-run.json')).write_text(json.dumps(report,indent=2));print(json.dumps(report))

if __name__=='__main__':main()

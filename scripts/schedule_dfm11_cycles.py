"""Prepare qualified sampled-recurrence PrefixLM to the live SQLite plan and gate the existing successor after its final evaluation."""
import argparse,copy,hashlib,json,os,sqlite3,subprocess,sys,time,shlex
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from eval_scheduler.model import Job,JobStatus,write_plan
from eval_scheduler.store import _validate_graph,_definition
from eval_scheduler.preflight import check_job,check_artifact_isolation
from scripts.prepare_transformer48_eval_plan import replace
from training_suspend.supervisor import overrides
DB=Path('/var/tmp/dfm11-architecture-comparison/jobs.sqlite');PLAN=ROOT/'logs/scheduler/dfm11_architecture_comparison_20261110'
OUT=PLAN/'cycles-preparation-20261116';PY='/home/ucloud/miniforge3/envs/hrm/bin/python';FINAL=393732
STEPS=[50000,100000,150000,200000,250000,300000,350000,FINAL]
def tag(s):return 'epoch_1' if s==FINAL else f'step_{s}'
def work(j):return j.action.startswith('eval_') or j.action in ('wait_checkpoint','export_hf')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--execute',action='store_true');ap.add_argument('--qualification',type=Path,required=True);args=ap.parse_args();OUT.mkdir(exist_ok=True)
    qualified=json.loads(args.qualification.read_text());assert qualified['status']=='qualified'
    budget=qualified['selected_budget'];assert budget in (15,16)
    assert hashlib.sha256(Path(qualified['config']).read_bytes()).hexdigest()==qualified['config_sha256']
    for path,digest in qualified['software_hashes'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest, path
    ranks=[json.loads((args.qualification.parent/f'bp{budget}'/f'rank{i}.json').read_text()) for i in range(8)]
    assert all(r['passed'] and r['rank']==i and r['world_size']==8 and r['mixed_steps']>=100 for i,r in enumerate(ranks))
    import yaml
    recipe=copy.deepcopy(qualified['recipe']);recipe['arch']['bp_max_steps']=budget
    candidate='B-cycle-prefix-target'
    checkpoint=ROOT/'checkpoints/cycle-prefix-target'
    output=ROOT/'logs/training/B_cycle_prefix_target_dfm11'
    recipe.update(checkpoint_path=str(checkpoint),suspend_control_dir=str(output/'control'),suspend_after_steps=STEPS[:-1],run_name=candidate+'-dfm11-epoch1',wandb_run_id=candidate+'-dfm11-epoch1')
    candidate_path=OUT/(candidate+'.yaml');candidate_path.write_text(yaml.safe_dump(recipe,sort_keys=False))
    c=sqlite3.connect(DB,timeout=60);rows=c.execute('select * from jobs order by position').fetchall()
    original={r[0]:Job.from_row(json.loads(r[2])).with_updates(status=JobStatus(r[5]),attempt=r[6],log_dir=r[7]) for r in rows}
    assert not any(k.startswith(('bcycles-dfm11-',)) for k in original)
    additions=[];specs={};configs={}
    variants = [('bcycles','B-cycle-prefix-target')]
    for name,candidate in variants:
        source='bprefix'
        template=original[source+'-dfm11-step_50000-train'];old=template.metadata;oldco=old['cooperative_training'];oldrun=old['wandb_run_id'];oldout=Path(oldco['control_root']).parent
        run=candidate+'-dfm11-epoch1'
        out=output
        ckpt=checkpoint
        out.mkdir(exist_ok=True);ckpt.mkdir(parents=True,exist_ok=True);assert not any(ckpt.iterdir())
        settings=json.loads(Path(oldco['launcher_settings']).read_text())
        settings.update(allow_existing_peers=False,min_free_mib=178000)
        (out/'launcher-settings.json').write_text(json.dumps(settings,indent=2))
        pairs=[(str(Path(old['ckpt_path'])),str(ckpt)),(source+'-dfm11',name+'-dfm11'),(oldrun,run),(oldout.name,out.name),(oldout.name.rsplit('_',1)[0],out.name.rsplit('_',1)[0])]
        candidate_path=OUT/(candidate+'.yaml')
        cfg=candidate_path.read_bytes()
        import yaml
        recipe=yaml.safe_load(cfg)
        assert recipe['checkpoint_path']==str(ckpt)
        cmd=[str(Path(PY).parent/'torchrun'),'--standalone','--nproc_per_node=8','pretrain.py',
             '--config-path',str(candidate_path.parent),'--config-name',candidate]
        (out/'resolved-config.yaml').write_bytes(cfg)
        configs[name]=hashlib.sha256(cfg).hexdigest();specs[name]={'out':out,'run':run}
        for step in STEPS:
            block=[j for j in original.values() if j.job_id.startswith(source+'-dfm11-'+tag(step)+'-')];assert len(block)==2204,len(block)
            for j in block:
                m=replace(copy.deepcopy(j.metadata),pairs);jid=replace(j.job_id,pairs);log=replace(j.log_dir,pairs)
                m['cycle_sampling']='full_budget';m['qualified_bp_budget']=budget;m['user_training_pause']=False
                if j.action=='train_until_step':
                    m['min_gpu_free_mib']=178000
                    co=m['cooperative_training'];co.update(command=cmd,control_root=str(out/'control'),launcher_settings=str(out/'launcher-settings.json'),allowed_existing_peer_identities=[],scheduled_disk_resume=True)
                    co.pop('disk_handoff_from',None)
                    if step==50000:m.pop('resume_from_tag',None);m.pop('resume_ckpt_path',None)
                    else:m.update(resume_from_tag=f'step_{350000 if step==FINAL else step-50000}',resume_ckpt_path=str(ckpt))
                    if step==FINAL:co['finalize_command']=[PY,str(ROOT/'scripts/finalize_transformer48_epoch.py'),str(DB),str(ckpt)]
                    log=str(PLAN/'runs'/jid)
                additions.append(j.with_updates(job_id=jid,metadata=m,deps=tuple(replace(d,pairs) for d in j.deps),status=JobStatus.PENDING,attempt=0,log_dir=log))
    byid={**original,**{j.job_id:j for j in additions}}
    previous=[k for k,v in original.items() if k.startswith('embla-loop-dfm11-epoch_1-eval') and (work(v) or v.action in ('average','report'))];assert previous
    prior=None;prior_step=None;order=[]
    for model,_ in variants:
        for step in STEPS:
            prefix=model+'-dfm11-'+tag(step);jid=prefix+'-train';j=byid[jid];m=copy.deepcopy(j.metadata);co=m['cooperative_training']
            if prior and prior != model and prior_step!=FINAL:co['disk_handoff_from']={'control_root':str(specs[prior]['out']/'control'),'step':prior_step}
            byid[jid]=j.with_updates(metadata=m,deps=tuple(previous),deps_mode='terminal')
            previous=[k for k,v in byid.items() if k.startswith(prefix+'-eval') and work(v)];assert previous
            prior=model;prior_step=step;order.append(jid)
    # Insert after all Embla variants, before the remaining ablations.
    successors=[j for j in original.values() if j.action=='train_until_step' and
                any(d.startswith('embla-loop-dfm11-epoch_1-eval') for d in j.deps)]
    assert len(successors)==1
    successor=successors[0];assert successor.status==JobStatus.PENDING
    successor_before=next(r for r in rows if r[0]==successor.job_id)
    final_deps=tuple(k for k,v in byid.items() if k.startswith('bcycles-dfm11-epoch_1-eval') and (work(v) or v.action in ('average','report')))
    assert len(final_deps)==1057
    successor=successor.with_updates(deps=final_deps,deps_mode='terminal')
    byid[successor.job_id]=successor
    additions=[byid[j.job_id] for j in additions];candidates=list(byid.values());_validate_graph(candidates)
    errors={j.job_id:e for j in [*additions,successor] if (e:=check_job(j,ROOT))};collisions=check_artifact_isolation(candidates,ROOT)
    report={'added_rows':len(additions),'changed_existing_rows':1,'successor':successor.job_id,'order':order,'errors':errors,'artifact_collisions':collisions,'config_sha256':configs,'executed':False}
    (OUT/'preflight.json').write_text(json.dumps(report,indent=2));assert not errors and not collisions
    write_plan(OUT/'additions.tsv',additions)
    if args.execute:
        assert json.loads(args.qualification.read_text())==qualified, 'Qualification changed'
        backup=sqlite3.connect(OUT/f'before-{int(time.time())}.sqlite');c.backup(backup);backup.close()
        c.execute('begin immediate');assert c.execute("select count(*) from jobs where job_id like 'bcycles-dfm11-%'").fetchone()[0]==0
        assert c.execute('select definition,status,token from jobs where job_id=?',(successor.job_id,)).fetchone()==(successor_before[2],'pending',None)
        pos=c.execute('select max(position) from jobs').fetchone()[0]+1
        for i,j in enumerate(additions):
            c.execute('insert into jobs values (?,?,?,?,?,?,?,?,?)',(j.job_id,pos+i,_definition(j),j.deps_mode,int(j.action=='eval_euroeval' and j.name.startswith('valeu-')),'pending',0,j.log_dir,None));c.executemany('insert into dependencies values (?,?)',[(j.job_id,d) for d in j.deps])
        c.execute('update jobs set definition=?,deps_mode=? where job_id=?',(_definition(successor),'terminal',successor.job_id))
        c.execute('delete from dependencies where job_id=?',(successor.job_id,))
        c.executemany('insert into dependencies values (?,?)',[(successor.job_id,d) for d in successor.deps])
        c.commit()
        for j in [*additions,successor]:
            actual=c.execute('select definition,deps_mode from jobs where job_id=?',(j.job_id,)).fetchone()
            assert actual==(_definition(j),j.deps_mode),j.job_id
            actual_deps={r[0] for r in c.execute('select dependency from dependencies where job_id=?',(j.job_id,))}
            assert actual_deps==set(j.deps),j.job_id
        report['executed']=True;report['readback_verified']=True
    (OUT/('receipt.json' if args.execute else 'dry-run.json')).write_text(json.dumps(report,indent=2));print(json.dumps(report))
if __name__=='__main__':main()

"""Insert a fresh LR-auto/BP-warmup B run through 150K before Transformer200K."""
import json,sqlite3,time,subprocess,os,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from eval_scheduler.model import Job
from eval_scheduler.preflight import check_job
from training_suspend.supervisor import overrides
from scripts.prepare_transformer48_eval_plan import replace
DB=Path('/var/tmp/dfm11-architecture-comparison/jobs.sqlite')
PLAN=ROOT/'logs/scheduler/dfm11_architecture_comparison_20261110'
OUT=ROOT/'logs/training/B_dfm11_causal_lrauto_bpwarmup_20261110'
CONTROL=OUT/'control'
RUN='B-dfm11-causal-lrauto-bpwarmup-alltokens-epoch1'
CKPT=ROOT/'checkpoints/hrm'/RUN
PYTHON='/home/ucloud/miniforge3/envs/hrm/bin/python'


def main():
    c=sqlite3.connect(DB,timeout=60)
    assert c.execute("select count(*) from jobs where job_id like 'bauto-dfm11-%'").fetchone()[0]==0
    backup=sqlite3.connect(str(DB)+'.before-lrauto-insertion-'+str(int(time.time())));c.backup(backup);backup.close()
    OUT.mkdir(parents=True,exist_ok=True);CKPT.mkdir(parents=True,exist_ok=True);assert not any(CKPT.iterdir())
    settings=ROOT/'logs/training/B_dfm11_causal_fullbp_20261110/launcher-settings.json'
    (OUT/'launcher-settings.json').write_bytes(settings.read_bytes())
    rows=c.execute('select job_id,definition,log_dir from jobs').fetchall();original={jid:(json.loads(raw),log) for jid,raw,log in rows}
    pairs=[('bfull-dfm11','bauto-dfm11'),('B-dfm11-causal-fullbp-alltokens-epoch1',RUN),('B_dfm11_causal_fullbp','B_dfm11_causal_lrauto_bpwarmup')]
    additions=[];commands=[]
    for step in [50000,100000,150000]:
        source=[(jid,d,l) for jid,(d,l) in original.items() if jid.startswith(f'bfull-dfm11-step_{step}-')];assert len(source)==2204
        for jid,d,log in source:
            new=replace(d,pairs);m=json.loads(new['metadata_json']);newid=new['job_id'];newlog=replace(log,pairs)
            if new['action']=='train_until_step':
                coop=m['cooperative_training'];coop['control_root']=str(CONTROL);coop['launcher_settings']=str(OUT/'launcher-settings.json')
                coop['command']=overrides(coop['command'],{'lr_auto':'true','arch.bp_min_steps':'2','arch.bp_max_steps':'8','arch.bp_warmup_ratio':str(50000/393732),'checkpoint_path':str(CKPT),'run_name':RUN,'wandb_run_id':RUN})
                # bp_min_steps is absent from the Hydra preset, so retain add syntax.
                coop['command']=['+arch.bp_min_steps=2' if x=='arch.bp_min_steps=2' else x for x in coop['command']]
                coop['command']=overrides(coop['command'],{'suspend_after_steps':'[50000,100000,150000]'})
                if step==50000:
                    new['deps']=original['transformer48-step_200000-train'][0]['deps']
                    coop['disk_handoff_from']={'control_root':str(ROOT/'logs/training/B_dfm11_causal_fullbp_20261110/control'),'step':150000}
                    m.pop('resume_from_tag',None);m.pop('resume_ckpt_path',None)
                else:coop.pop('disk_handoff_from',None)
                m['ckpt_path']=str(CKPT);newlog=str(PLAN/'runs'/newid);commands.append(coop['command'])
            new['metadata_json']=json.dumps(m)
            j=Job.from_row(new).with_updates(log_dir=newlog)
            errors=check_job(j,ROOT);assert not errors,(newid,errors)
            additions.append((newid,new,newlog))
    command=commands[0];idx=command.index('pretrain.py')
    env={**os.environ,'TMPDIR':'/dev/shm/hrm-b-recovery','PATH':str(Path(PYTHON).parent)+':'+os.environ['PATH']}
    resolved=subprocess.check_output([PYTHON,'pretrain.py',*command[idx+1:],'--cfg','job','--resolve'],cwd=ROOT,env=env)
    (OUT/'resolved-config.yaml').write_bytes(resolved)
    c.execute('begin immediate')
    tid='transformer48-step_200000-train';raw,status=c.execute('select definition,status from jobs where job_id=?',(tid,)).fetchone();assert status=='pending'
    td=json.loads(raw);td['deps']=replace(td['deps'],pairs);tm=json.loads(td['metadata_json']);tm['cooperative_training']['disk_handoff_from']={'control_root':str(CONTROL),'step':150000};td['metadata_json']=json.dumps(tm)
    c.execute('update jobs set definition=? where job_id=?',(json.dumps(td),tid));c.execute('delete from dependencies where job_id=?',(tid,));c.executemany('insert into dependencies values (?,?)',[(tid,x) for x in td['deps'].split(',') if x])
    pos=c.execute('select max(position) from jobs').fetchone()[0]+1
    for i,(jid,d,log) in enumerate(additions):
        position=(-2000+int(json.loads(d['metadata_json'])['stop_after_step'])//50000) if d['action']=='train_until_step' else pos+i
        c.execute('insert into jobs values (?,?,?,?,?,?,?,?,?)',(jid,position,json.dumps(d),d.get('deps_mode','success'),0,'pending',0,log,None))
        c.executemany('insert into dependencies values (?,?)',[(jid,x) for x in d['deps'].split(',') if x])
    c.commit()
    (OUT/'preparation.json').write_text(json.dumps({'run':RUN,'jobs':len(additions),'config_sha256':hashlib.sha256(resolved).hexdigest(),'bp_warmup_steps':50000,'target':150000,'insert_before':tid},indent=2))
    print('Inserted',len(additions),'jobs for fresh B LR-auto/BP-warmup run')

if __name__=='__main__':main()

"""Stage and arm the explicitly authorized B DFM15 epoch-two schedule switch."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import signal
import sqlite3
import subprocess
import time
from dfm12.io import file_hash,load,lock,write_json
from training_suspend.protocol import validate_process,process_identity
from eval_scheduler.model import Job
from eval_scheduler.runtime import training_checkpoint_ready

LIVE=Path('/tmp/dfm15-B-production/jobs.sqlite')
STAGED=Path('/tmp/dfm15-B-production/jobs_epoch2_stage.sqlite')
PLAN=Path('/work/dfm/HRM-Text/logs/scheduler/B_dfm15_gemma4_epoch1_20261103')
OUT=PLAN/'epoch2-switch-900k-1m'
NEW_CONTROL=Path('/work/dfm/HRM-Text/logs/training/B-dfm15-gemma4-epoch1/cooperative_epoch2_from450k_20261104')
PYTHON='/home/ucloud/miniforge3/envs/hrm/bin/python'
END=1025846
BOUNDARIES=[500000,512923,*range(550000,1000001,50000)]


def command(value):
    items=shlex.split(value) if isinstance(value,str) else list(value)
    overrides=dict(epochs='2',training_total_steps=str(END),stop_after_step=str(END),
        lr='3e-4',lr_decay_start_step='900000',lr_decay_end_step='1000000',
        lr_min_ratio=str(1/30),suspend_after_steps='['+','.join(map(str,BOUNDARIES))+']')
    items=[x for x in items if x.lstrip('+').split('=',1)[0] not in overrides]
    items += [k+'='+v for k,v in overrides.items()]
    return shlex.join(items) if isinstance(value,str) else items


def patch_definition(definition):
    d=json.loads(json.dumps(definition));m=json.loads(d['metadata_json'])
    if d['action']=='train_until_step':
        target=int(m['stop_after_step'])
        m['command']=command(m['command'])
        coop=m['cooperative_training'];coop['command']=command(coop['command'])
        coop['control_root']=str(NEW_CONTROL)
        coop['final_boundary']=target==END
        if target!=END:m.pop('completion_checkpoint_tag',None)
        else:m['completion_checkpoint_tag']='epoch_2'
        if target==550000:
            m['resume_from_tag']='step_512923'
            d['deps']=re.sub(r'(?<!\d)500000(?!\d)','512923',d['deps'])
        m['eval_epoch']=target/512923
    else:
        match=re.match(r'b-dfm15-(\d+)-',d['job_id'])
        if match and int(match[1])>512923:
            step=int(match[1]);m['eval_step']=step;m['eval_epoch']=step/512923
            if step==550000:d['deps']=re.sub(r'(?<!\d)500000(?!\d)','512923',d['deps'])
    d['metadata_json']=json.dumps(m)
    return d


def backup(source,destination):
    destination.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(source) as src,sqlite3.connect(destination) as dst:src.backup(dst)


def stage():
    OUT.mkdir(parents=True,exist_ok=True)
    backup(STAGED,OUT/f'staged-before-{int(time.time())}.sqlite')
    with sqlite3.connect(STAGED) as db:
        db.execute('BEGIN IMMEDIATE')
        changed=[]
        for jid,text,status in db.execute('SELECT job_id,definition,status FROM jobs').fetchall():
            d=json.loads(text)
            match=re.match(r'b-dfm15-(\d+)-',jid)
            if not (d['action']=='train_until_step' and status=='pending' or match and int(match[1])>512923):continue
            if status=='running':raise ValueError('claimed staged row')
            d=patch_definition(d)
            db.execute('UPDATE jobs SET definition=? WHERE job_id=?',(json.dumps(d),jid))
            db.execute('DELETE FROM dependencies WHERE job_id=?',(jid,))
            db.executemany('INSERT INTO dependencies VALUES (?,?)',[(jid,k) for k in d.get('deps','').split(',') if k])
            # Preserve the working layout: inference/publication share directories,
            # and merges locate shard artifacts under the canonical task roots.
            if match and int(match[1])>512923:
                baseline_id = jid.replace(f'b-dfm15-{match[1]}-', 'b-dfm15-500000-', 1)
                baseline = db.execute('SELECT log_dir FROM jobs WHERE job_id=?', (baseline_id,)).fetchone()
                if not baseline:
                    raise ValueError(f'Missing canonical log layout for {jid}')
                log_dir = re.sub(r'(?<!\d)500000(?!\d)', match[1], baseline[0])
                db.execute('UPDATE jobs SET log_dir=? WHERE job_id=?',(log_dir,jid))
            changed.append(jid)
    write_json(OUT/'staged-repair.json',dict(rows=len(changed),staged=str(STAGED),schedule=[900000,1000000,END],floor=1e-5))


def state(dbpath,jid):
    with sqlite3.connect(f'file:{dbpath}?mode=ro',uri=True) as db:
        row=db.execute('SELECT definition,status FROM jobs WHERE job_id=?',(jid,)).fetchone()
    return (json.loads(row[0]),row[1]) if row else (None,None)


def apply_plan():
    """Only pending continuation rows and absent new rows are changed."""
    with sqlite3.connect(STAGED) as staged:
        staged.row_factory=sqlite3.Row
        source=[dict(r) for r in staged.execute('SELECT * FROM jobs ORDER BY position')]
    with sqlite3.connect(LIVE) as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT locked FROM administration WHERE singleton=1').fetchone()[0]!=1:raise ValueError('dispatch fence missing')
        existing=dict(db.execute('SELECT job_id,status FROM jobs'))
        cols=[r[1] for r in db.execute('PRAGMA table_info(jobs)')]
        n=0
        for row in source:
            jid=row['job_id']
            if jid in existing and jid not in ('b-dfm15-train-500000','b-dfm15-train-512923'):continue
            if jid in existing:
                if existing[jid]!='pending':raise ValueError('continuation already claimed')
                db.execute('UPDATE jobs SET definition=?,deps_mode=? WHERE job_id=?',(row['definition'],row['deps_mode'],jid))
            else:
                if row['status']!='pending' or row['token'] is not None:raise ValueError('new row is not pending')
                db.execute(f"INSERT INTO jobs ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",[row[k] for k in cols])
            db.execute('DELETE FROM dependencies WHERE job_id=?',(jid,))
            d=json.loads(row['definition'])
            db.executemany('INSERT INTO dependencies VALUES (?,?)',[(jid,k) for k in d.get('deps','').split(',') if k])
            n+=1
        if db.execute('SELECT count(*) FROM dependencies d LEFT JOIN jobs j ON d.dependency=j.job_id WHERE j.job_id IS NULL').fetchone()[0]:raise ValueError('missing dependencies')
    return n


def rollback_definitions():
    """Restore only edited definitions; preserve completions of active eval rows."""
    with sqlite3.connect(OUT/'live-before-switch.sqlite') as old:
        original={j:d for j,d in old.execute('SELECT job_id,definition FROM jobs')}
    with sqlite3.connect(LIVE) as db:
        db.execute('BEGIN IMMEDIATE')
        added=[j for (j,) in db.execute('SELECT job_id FROM jobs') if j not in original]
        for jid in added:
            if db.execute('SELECT status FROM jobs WHERE job_id=?',(jid,)).fetchone()[0]!='pending':
                raise RuntimeError('Cannot roll back a claimed extension row')
            db.execute('DELETE FROM dependencies WHERE job_id=?',(jid,))
        for jid in added:db.execute('DELETE FROM jobs WHERE job_id=?',(jid,))
        for jid in ('b-dfm15-train-500000','b-dfm15-train-512923'):
            d=json.loads(original[jid])
            db.execute('UPDATE jobs SET definition=?,deps_mode=? WHERE job_id=?',(original[jid],d['deps_mode'],jid))
            db.execute('DELETE FROM dependencies WHERE job_id=?',(jid,))
            db.executemany('INSERT INTO dependencies VALUES (?,?)',[(jid,k) for k in d.get('deps','').split(',') if k])


def alive(identity):
    try:validate_process(identity);return True
    except (OSError,RuntimeError):return False


def wait_switch():
    OUT.mkdir(parents=True,exist_ok=True)
    with lock(OUT/'.controller.lock'):
        if (OUT/'handoff-verified.json').exists():return
        while True:
            d,status=state(LIVE,'b-dfm15-train-450000')
            control=Path(json.loads(d['metadata_json'])['cooperative_training']['control_root'])
            active=load(control/'active.json') if (control/'active.json').exists() else {}
            active_dir=Path(active['control_dir']) if active else None
            ready=load(active_dir/'suspend_ready.json') if active_dir and (active_dir/'suspend_ready.json').exists() else {}
            if status=='done' and ready.get('step')==450000 and training_checkpoint_ready(Job.from_row(d),450000)[0]:break
            if status in ('failed','skipped'):raise RuntimeError('450K boundary failed; no schedule flip')
            write_json(OUT/'status.json',dict(phase='waiting_for_verified_450k_pause',boundary_status=status,last_checked=time.time()))
            time.sleep(15)
        pin=load(OUT/'armed.json')
        if file_hash(STAGED)!=pin['staged_sha256'] or file_hash(Path(__file__))!=pin['script_sha256']:
            raise RuntimeError('Armed schedule changed; refusing an unreviewed switch')
        # run_boundary has already completed the matching offload/fallback and set hold.
        if not (control/'hold').exists():raise RuntimeError('scheduler evaluation hold missing')
        launcher=load(control/'launcher.json')['identity']
        supervisor=load(control/'supervisor.json')['owner']
        validate_process(launcher);validate_process(supervisor)
        for who,needle in ((launcher,b'training_suspend.launcher'),(supervisor,b'training_suspend.supervisor')):
            if needle not in Path(f'/proc/{who["pid"]}/cmdline').read_bytes():raise RuntimeError('unexpected process identity')
        if state(LIVE,'b-dfm15-train-500000')[1]!='pending':raise RuntimeError('500K already started')
        with sqlite3.connect(LIVE) as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT locked FROM administration WHERE singleton=1').fetchone()[0]:raise RuntimeError('another administrator owns dispatch fence')
            db.execute('UPDATE administration SET locked=1 WHERE singleton=1')
        try:
            backup(LIVE,OUT/'live-before-switch.sqlite')
            count=apply_plan()
            with (OUT/'live-postflight.json').open('w') as report:
                subprocess.run([PYTHON,'-m','eval_scheduler','database','preflight','--database',str(LIVE)],stdout=report,check=True)
            # Exactly one checkpoint restart is needed because the loaded trainer
            # cannot reload epochs/LR settings. The launcher owns scoped cleanup.
            validate_process(launcher)
            os.kill(launcher['pid'],signal.SIGTERM)
            deadline=time.time()+180
            while alive(launcher) or alive(supervisor):
                if time.time()>deadline:raise RuntimeError('owned trainer cleanup did not finish')
                time.sleep(2)
            # New launch uses a separate control root, so the old held supervisor
            # cannot restore an obsolete in-memory schedule during evaluation.
            write_json(OUT/'applied.json',dict(rows_updated_or_added=count,time=time.time(),checkpoint=ready,
                old_launcher=launcher,new_control=str(NEW_CONTROL),schedule=[900000,1000000,END]))
        except BaseException:
            rollback_definitions()
            raise
        finally:
            with sqlite3.connect(LIVE) as db:db.execute('UPDATE administration SET locked=0 WHERE singleton=1')
        write_json(OUT/'status.json',dict(phase='applied_waiting_for_evaluations_and_resume',time=time.time()))
        while True:
            d,status=state(LIVE,'b-dfm15-train-500000')
            path=NEW_CONTROL/'supervisor.json'
            if path.exists():
                info=load(path)
                if alive(info['owner']):
                    argv=info['command'];needed=['epochs=2','lr_decay_start_step=900000','lr_decay_end_step=1000000',f'training_total_steps={END}','resume_checkpoint_tag=step_450000']
                    if not all(v in argv for v in needed):raise RuntimeError('resumed supervisor has wrong schedule')
                    active=load(NEW_CONTROL/'active.json') if (NEW_CONTROL/'active.json').exists() else {}
                    progress=False
                    ckpt=Path(json.loads(d['metadata_json'])['ckpt_path'])
                    for record in ckpt.glob('checkpoint_state_*step_*.json'):
                        try:
                            if int(load(record).get('step',0))>450000:progress=True;break
                        except (OSError,ValueError):pass
                    if active and (Path(active['control_dir'])/'launch.json').exists() and progress:
                        write_json(OUT/'handoff-verified.json',dict(time=time.time(),supervisor=info['owner'],command=argv,boundary_status=status))
                        write_json(OUT/'status.json',dict(phase='epoch2_schedule_resumed',time=time.time()));return
            if status in ('failed','skipped'):raise RuntimeError('500K continuation did not launch')
            time.sleep(15)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['stage','wait']);args=p.parse_args()
    if args.action=='stage':stage()
    else:
        try:wait_switch()
        except BaseException as exc:
            write_json(OUT/'failure.json',dict(error=type(exc).__name__,message=str(exc),time=time.time()))
            raise

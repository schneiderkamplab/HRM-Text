"""Apply the authorized staged B schedule at the verified 650K evaluation pause."""
import hashlib,json,os,re,shlex,signal,sqlite3,subprocess,time
from pathlib import Path
from dfm12.io import lock,load,write_json,file_hash
from training_suspend.protocol import validate_process
from eval_scheduler.model import Job
from eval_scheduler.runtime import training_checkpoint_ready
from scripts.stage_b_dfm15_epoch3 import LIVE,OUT,CONTROL,END,DECAY_START,definition_hash

PYTHON='/home/ucloud/miniforge3/envs/hrm/bin/python'
STAGED=Path('/tmp/dfm15-B-production/jobs_epoch3_stage.sqlite')
HANDOFF=OUT/'activation-650k'
OLD=Path('/work/dfm/HRM-Text/logs/training/B-dfm15-gemma4-epoch1/cooperative_recovered600k_20261105')


def state(jid):
    with sqlite3.connect(f'file:{LIVE}?mode=ro',uri=True) as db:
        row=db.execute('SELECT definition,status FROM jobs WHERE job_id=?',(jid,)).fetchone()
    return (json.loads(row[0]),row[1]) if row else (None,None)


def alive(identity):
    try:validate_process(identity);return True
    except (OSError,RuntimeError):return False


def trim_passed(d, boundary=650000):
    d=json.loads(json.dumps(d))
    if d['action']!='train_until_step':return d
    m=json.loads(d['metadata_json'])
    def trim(value):
        tokens=shlex.split(value) if isinstance(value,str) else list(value)
        result=[]
        for token in tokens:
            if token.startswith('suspend_after_steps='):
                steps=json.loads(token.split('=',1)[1]);token='suspend_after_steps='+json.dumps([s for s in steps if s>boundary],separators=(',',':'))
            result.append(token)
        return shlex.join(result) if isinstance(value,str) else result
    m['command']=trim(m['command']);m['cooperative_training']['command']=trim(m['cooperative_training']['command'])
    d['metadata_json']=json.dumps(m,sort_keys=True)
    return d


def apply_definitions():
    """Reconcile definitions only; never replay stale statuses or copied claim tokens."""
    with sqlite3.connect(STAGED) as source:
        source.row_factory=sqlite3.Row;rows=[dict(r) for r in source.execute('SELECT * FROM jobs ORDER BY position')]
    changed=[];added=[]
    with sqlite3.connect(LIVE) as db:
        db.execute('BEGIN IMMEDIATE')
        assert db.execute('SELECT locked FROM administration').fetchone()[0]==1
        existing=dict(db.execute('SELECT job_id,status FROM jobs'))
        assert existing['b-dfm15-train-700000']=='pending'
        position=db.execute('SELECT max(position) FROM jobs').fetchone()[0]
        for r in rows:
            jid=r['job_id'];d=trim_passed(json.loads(r['definition']))
            if jid in existing:
                if existing[jid]!='pending':continue
                old=db.execute('SELECT definition,deps_mode FROM jobs WHERE job_id=?',(jid,)).fetchone()
                if json.loads(old[0])==d:continue
                changed.append(dict(job_id=jid,definition=old[0],deps_mode=old[1]))
                db.execute('UPDATE jobs SET definition=?,deps_mode=? WHERE job_id=?',(json.dumps(d,sort_keys=True),d['deps_mode'],jid))
            else:
                assert r['status']=='pending' and r['token'] is None
                position+=1;r.update(position=position,definition=json.dumps(d,sort_keys=True))
                columns=list(r)
                db.execute(f"INSERT INTO jobs ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",[r[k] for k in columns]);added.append(jid)
            db.execute('DELETE FROM dependencies WHERE job_id=?',(jid,))
            db.executemany('INSERT INTO dependencies(job_id,dependency) VALUES (?,?)',[(jid,x) for x in filter(None,d.get('deps','').split(','))])
        assert not db.execute('SELECT 1 FROM dependencies d LEFT JOIN jobs j ON d.dependency=j.job_id WHERE j.job_id IS NULL LIMIT 1').fetchone()
        # Persist rollback information before the transaction commits.
        write_json(HANDOFF/'definition-changes.json',dict(changed=changed,added=added))
    return len(changed),len(added)


def rollback():
    r=load(HANDOFF/'definition-changes.json')
    with sqlite3.connect(LIVE) as db:
        db.execute('BEGIN IMMEDIATE')
        for jid in r['added']:
            assert db.execute('SELECT status FROM jobs WHERE job_id=?',(jid,)).fetchone()[0]=='pending'
            db.execute('DELETE FROM dependencies WHERE job_id=?',(jid,));db.execute('DELETE FROM jobs WHERE job_id=?',(jid,))
        for old in r['changed']:
            jid=old['job_id'];assert db.execute('SELECT status FROM jobs WHERE job_id=?',(jid,)).fetchone()[0]=='pending'
            db.execute('UPDATE jobs SET definition=?,deps_mode=? WHERE job_id=?',(old['definition'],old['deps_mode'],jid))
            db.execute('DELETE FROM dependencies WHERE job_id=?',(jid,))
            db.executemany('INSERT INTO dependencies VALUES (?,?)',[(jid,x) for x in filter(None,json.loads(old['definition']).get('deps','').split(','))])


def run():
    HANDOFF.mkdir(parents=True,exist_ok=True)
    with lock(HANDOFF/'.controller.lock'):
        if (HANDOFF/'handoff-verified.json').exists():return
        if not (HANDOFF/'applied.json').exists():
            pin=load(HANDOFF/'armed.json')
            assert file_hash(Path(__file__))==pin['script_sha256']
            with sqlite3.connect(STAGED) as staged:assert definition_hash(staged)==pin['staged_definition_sha256']
            while True:
                d,status=state('b-dfm15-train-650000')
                active=load(OLD/'active.json');ready_path=Path(active['control_dir'])/'suspend_ready.json'
                ready=load(ready_path) if ready_path.exists() else {}
                if status=='done' and ready.get('step')==650000 and training_checkpoint_ready(Job.from_row(d),650000)[0]:break
                if status in ('failed','skipped'):raise RuntimeError('650K boundary failed; no switch')
                write_json(HANDOFF/'status.json',dict(phase='waiting_for_verified_650k_pause',time=time.time()))
                time.sleep(10)
            assert (OLD/'hold').exists(),'Missing evaluation hold'
            launcher=load(OLD/'launcher.json')['identity'];supervisor=load(OLD/'supervisor.json')['owner']
            for who,needle in ((launcher,b'training_suspend.launcher'),(supervisor,b'training_suspend.supervisor')):
                validate_process(who);assert needle in Path(f'/proc/{who["pid"]}/cmdline').read_bytes()
            with sqlite3.connect(LIVE) as db:
                db.execute('BEGIN IMMEDIATE');assert db.execute('SELECT locked FROM administration').fetchone()[0]==0
                assert db.execute("SELECT status FROM jobs WHERE job_id='b-dfm15-train-700000'").fetchone()[0]=='pending'
                db.execute('UPDATE administration SET locked=1')
            applied=False;cleanup_started=False
            try:
                with sqlite3.connect(LIVE) as src,sqlite3.connect(HANDOFF/'live-before.sqlite') as dst:src.backup(dst)
                counts=apply_definitions();applied=True
                with (HANDOFF/'preflight.json').open('w') as log:
                    subprocess.run([PYTHON,'-m','eval_scheduler','database','preflight','--database',str(LIVE)],stdout=log,check=True)
                validate_process(launcher);cleanup_started=True;os.kill(launcher['pid'],signal.SIGTERM)
                deadline=time.monotonic()+180
                while alive(launcher) or alive(supervisor):
                    if time.monotonic()>deadline:raise RuntimeError('Old launcher/supervisor cleanup timed out')
                    time.sleep(2)
                write_json(HANDOFF/'applied.json',dict(time=time.time(),modified_existing=counts[0],added=counts[1],checkpoint=ready,
                           old_launcher=launcher,old_supervisor=supervisor,new_control=str(CONTROL),decay_start=DECAY_START,decay_end=END))
            except BaseException:
                if applied and not cleanup_started:rollback()
                raise
            finally:
                with sqlite3.connect(LIVE) as db:db.execute('UPDATE administration SET locked=0')
        write_json(HANDOFF/'status.json',dict(phase='applied_waiting_for_evals_and_resume',time=time.time()))
        while True:
            d,status=state('b-dfm15-train-700000')
            if status in ('failed','skipped'):raise RuntimeError('700K continuation failed')
            info_path=CONTROL/'supervisor.json';log=CONTROL/'training.log'
            if info_path.exists() and log.exists():
                info=load(info_path)
                if alive(info['owner']):
                    needed=['epochs=3',f'lr_decay_start_step={DECAY_START}',f'lr_decay_end_step={END}',f'training_total_steps={END}','resume_checkpoint_tag=step_650000']
                    assert all(x in info['command'] for x in needed),'Resumed schedule mismatch'
                    with log.open('rb') as f:f.seek(max(0,log.stat().st_size-16000));text=f.read().decode(errors='replace')
                    steps=[int(s) for s in re.findall(r'(\d+)/1538769',text)]
                    if steps and max(steps)>650000:
                        receipt=dict(time=time.time(),phase='epoch3_schedule_resumed',step=max(steps),supervisor=info['owner'],command=info['command'])
                        write_json(HANDOFF/'handoff-verified.json',receipt);write_json(HANDOFF/'status.json',receipt);return
            time.sleep(15)


if __name__=='__main__':
    try:run()
    except BaseException as exc:
        HANDOFF.mkdir(parents=True,exist_ok=True)
        write_json(HANDOFF/'failure.json',dict(time=time.time(),error=type(exc).__name__,message=str(exc)))
        raise

"""Read-only operational watcher for causal-auto100K -> fresh PrefixLM B handoff.

Writes a durable status/receipt and exits only after verified optimizer progress.
Does not kill processes, mutate scheduler rows, or silently restart training.
"""
import datetime,json,re,sqlite3,time,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from training_suspend.protocol import atomic_write,read_json,validate_process
DB='/var/tmp/dfm11-architecture-comparison/jobs.sqlite'
PLAN=ROOT/'logs/scheduler/dfm11_architecture_comparison_20261110'
OUT=PLAN/'prefixlm-transition-watch'
OLD=ROOT/'logs/training/B_dfm11_causal_lrauto_bpwarmup_20261110/control'
NEW=ROOT/'logs/training/B_dfm11_prefixlm_lrauto_bpwarmup_20261111/control'


def tail_step(root):
    path=root/'training.log'
    if not path.exists():return 0
    with path.open('rb') as f:
        f.seek(max(0,path.stat().st_size-50000));text=f.read().decode(errors='replace')
    values=re.findall(r'(\d+)/393732',text)
    return int(values[-1]) if values else 0


def alive(root):
    try:validate_process(read_json(root/'launcher.json')['identity']);return True
    except (OSError,RuntimeError):return False


def snapshot():
    with sqlite3.connect(f'file:{DB}?mode=ro',uri=True,timeout=30) as c:
        rows=c.execute("select job_id,definition,status from jobs where job_id like 'bauto-dfm11-step_100000-%' or job_id='bprefix-dfm11-step_50000-train'").fetchall()
        locked=c.execute('select locked from administration').fetchone()[0]
    inference={};new_status=None;failed=[]
    for jid,raw,status in rows:
        d=json.loads(raw)
        if jid=='bprefix-dfm11-step_50000-train':new_status=status
        elif d['action'].startswith('eval_'):inference[status]=inference.get(status,0)+1
        if status=='failed':failed.append(jid)
    return {'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'old_step':tail_step(OLD),'new_step':tail_step(NEW),'old_launcher_alive':alive(OLD),
            'new_launcher_alive':alive(NEW),'new_train_status':new_status,
            'inference':inference,'failed_jobs':failed,'dispatch_locked':bool(locked)}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    last=None;changed=time.monotonic()
    while True:
        try:
            s=snapshot();key=(s['old_step'],s['new_step'],tuple(sorted(s['inference'].items())),s['new_train_status'])
            if key!=last:last=key;changed=time.monotonic()
            s['seconds_without_stage_progress']=int(time.monotonic()-changed)
            # Aggregate row completion is coarse; alert requests inspection,
            # never asserts that a long inference shard is definitely stuck.
            if s['seconds_without_stage_progress']>=300:
                s['attention']='Inspect live inference/startup logs: no stage-level progress for five minutes'
                atomic_write(OUT/'attention.json',s)
            elif (OUT/'attention.json').exists():(OUT/'attention.json').unlink()
            atomic_write(OUT/'status.json',s)
            print(json.dumps(s),flush=True)
            if s['new_step']>=100 and s['new_launcher_alive'] and not s['old_launcher_alive']:
                command=read_json(NEW/'supervisor.json')['command']
                assert 'lr_auto=true' in command
                assert 'data.target_only=true' in command
                assert '+arch.attn_type=prefixlm' in command
                assert any(x.lstrip('+')=='arch.bp_min_steps=2' for x in command)
                assert 'arch.bp_max_steps=8' in command
                assert any(x.startswith('arch.bp_warmup_ratio=0.12698993223817215') for x in command)
                assert not any(x.startswith('resume_checkpoint_path=') for x in command),'Fresh run unexpectedly resumes a checkpoint'
                s['verified_configuration']='fresh PrefixLM target-only LR-auto B, BP2->8 by 50K'
                atomic_write(OUT/'completed.json',s)
                print('TRANSITION VERIFIED',flush=True);return
        except Exception as error:
            atomic_write(OUT/'attention.json',{'error':repr(error),'time':time.time()})
            print('WATCH_ERROR',repr(error),flush=True)
        time.sleep(30)

if __name__=='__main__':main()

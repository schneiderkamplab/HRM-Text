"""Persist the user's disk-stop request after the 150K evaluation block."""
import json,sqlite3,time
from pathlib import Path
from training_suspend.protocol import atomic_write, read_json
from eval_scheduler.model import Job
from eval_scheduler.runtime import checkpoint_ready
ROOT=Path(__file__).resolve().parents[1]
DB=Path('/var/tmp/dfm-transformer48-evals/jobs.sqlite')
CONTROL=ROOT/'logs/training/transformer48_dfm11_causal_20261109/control-shared-1'
OUT=ROOT/'logs/scheduler/transformer48_dfm11_causal_epoch1_20261109/stop-after-150k'

def main():
    OUT.mkdir(exist_ok=True)
    while True:
        with sqlite3.connect(f'file:{DB}?mode=ro',uri=True) as c:
            rows=c.execute("select definition,status from jobs where job_id like 'transformer48-step_150000-%'").fetchall()
        assert rows
        if all(s in ('done','failed','skipped') for _,s in rows):break
        time.sleep(10)
    d=next(json.loads(d) for d,s in rows if json.loads(d)['action']=='train_until_step')
    job=Job.from_row(d)
    valid,why=checkpoint_ready(job)
    if not valid:raise RuntimeError(why)
    active=Path(read_json(CONTROL/'active.json')['control_dir'])
    ready=read_json(active/'suspend_ready.json')
    assert ready['step']==150000,ready
    assert not (active/'resumed.json').exists() or read_json(active/'resumed.json').get('step')!=150000
    atomic_write(CONTROL/'hold','Explicit user stop after 150K eval; disk resume only\n')
    atomic_write(CONTROL/'stop.request','User requested disk stop after 150K eval\n')
    atomic_write(OUT/'receipt.json',{'step':150000,'checkpoint':ready['checkpoint'],
      'failed_jobs':sum(s=='failed' for _,s in rows),'time':time.time(),
      'status':'stop_requested','resume_from_tag':'step_150000'})
    print('150K evaluation terminal; verified checkpoint; requested supervisor shutdown',flush=True)

if __name__=='__main__':main()

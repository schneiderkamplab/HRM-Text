"""Observe recovered PrefixLM50K evaluation and verify in-place training continuation."""
import json,sqlite3,time,sys,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.watch_dfm11_b_transition import tail_step,alive
from training_suspend.protocol import atomic_write
CONTROL=ROOT/'logs/training/B_dfm11_prefixlm_lrauto_bpwarmup_20261111/control'
OUT=ROOT/'logs/scheduler/dfm11_architecture_comparison_20261110/prefixlm-resume-watch'
DB='/var/tmp/dfm11-architecture-comparison/jobs.sqlite'

def main():
    OUT.mkdir(exist_ok=True);last=None;changed=time.monotonic()
    while True:
        try:
            with sqlite3.connect(f'file:{DB}?mode=ro',uri=True) as c:
                counts=dict(c.execute("select status,count(*) from jobs where job_id like 'bprefix-dfm11-step_50000-%' and json_extract(definition,'$.action') like 'eval_%' group by status"))
                train=c.execute("select status from jobs where job_id='bprefix-dfm11-step_100000-train'").fetchone()[0]
                locked=bool(c.execute('select locked from administration').fetchone()[0])
            step=tail_step(CONTROL);key=(tuple(sorted(counts.items())),train,step)
            if key!=last:last=key;changed=time.monotonic()
            s={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'inference':counts,'train_status':train,'step':step,'launcher_alive':alive(CONTROL),'dispatch_locked':locked,'seconds_without_progress':int(time.monotonic()-changed)}
            atomic_write(OUT/'status.json',s)
            if s['seconds_without_progress']>=300 or counts.get('failed',0):atomic_write(OUT/'attention.json',s)
            elif (OUT/'attention.json').exists():(OUT/'attention.json').unlink()
            if step>=50100 and s['launcher_alive'] and train=='running':
                atomic_write(OUT/'completed.json',s);print('RESUME VERIFIED',json.dumps(s),flush=True);return
        except Exception as e:
            atomic_write(OUT/'attention.json',{'error':repr(e)});print(repr(e),flush=True)
        time.sleep(30)
if __name__=='__main__':main()

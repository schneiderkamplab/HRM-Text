"""Continue authorized alternating training when every GPU has100GiB headroom."""
import json,os,subprocess,sys,time,sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));os.chdir(ROOT)
from training_suspend.protocol import atomic_write,exclusive,process_identity
from eval_scheduler.store import SQLiteJobStore
PLAN=ROOT/'logs/scheduler/dfm11_architecture_comparison_20261110'
OUT=PLAN/'continue-100gib-20261113';DB='/var/tmp/dfm11-architecture-comparison/jobs.sqlite'
MINIMUM=102400

def free():
 r=subprocess.run(['nvidia-smi','--query-gpu=index,memory.free','--format=csv,noheader,nounits'],check=True,text=True,capture_output=True,timeout=15)
 return {int(i):int(m) for i,m in (l.split(',') for l in r.stdout.splitlines())}
def main():
 OUT.mkdir(exist_ok=True)
 with exclusive(OUT/'watcher.lock'):
  while True:
   if (OUT/'cancel.request').exists():return
   try:
    values=free();ok=set(values)==set(range(8)) and min(values.values())>=MINIMUM
    atomic_write(OUT/'status.json',{'stage':'waiting','free_mib':values,'required_mib_per_gpu':MINIMUM,'time':time.time()})
   except (OSError,ValueError,subprocess.SubprocessError):ok=False
   if ok:break
   time.sleep(10)
  s=SQLiteJobStore(DB);jobs=s.load_jobs()
  assert not any(j.status=='running' for j in jobs),'Active scheduler work; do not duplicate'
  rows=[j for j in jobs if j.action=='train_until_step' and j.status=='pending' and j.metadata.get('user_training_pause')]
  assert len(rows)==4,'Training schedule changed; inspect before overriding'
  raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True)
  peers=[process_identity(pid) for pid in sorted({int(l.strip()) for l in raw.splitlines() if l.strip()})]
  c=sqlite3.connect(DB);b=sqlite3.connect(OUT/'before.sqlite');c.backup(b);b.close();c.close()
  updates={}
  for j in rows:
   settings=Path(j.metadata['cooperative_training']['launcher_settings'])
   old=json.loads(settings.read_text());atomic_write(OUT/(settings.parent.name+'-'+settings.name+'.before.json'),old)
   atomic_write(settings,{**old,'min_free_mib':MINIMUM,'allow_existing_peers':True})
   md={**j.metadata,'user_training_pause':False,'min_gpu_free_mib':MINIMUM,'cooperative_training':{**j.metadata['cooperative_training'],'allowed_existing_peer_identities':peers}}
   updates[j.job_id]={'metadata':md}
  s.update_jobs(updates)
  atomic_write(OUT/'status.json',{'stage':'launching','jobs':list(updates),'peers':peers,'time':time.time()})
  env={**os.environ,'TMPDIR':'/dev/shm/hrm-b-recovery','PATH':'/home/ucloud/miniforge3/envs/hrm/bin:'+os.environ['PATH']}
  subprocess.run(['/home/ucloud/miniforge3/envs/hrm/bin/python','scripts/launch_dfm11_architecture_comparison.py','--execute'],check=True,env=env)
  atomic_write(OUT/'status.json',{'stage':'scheduler_launched','time':time.time(),'jobs':list(updates)})
if __name__=='__main__':main()

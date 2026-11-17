"""CAS-update only unclaimed pending Embla train rows after kernel qualification."""
import json,hashlib,sqlite3,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from eval_scheduler.model import Job
from eval_scheduler.store import _definition
from eval_scheduler.preflight import check_job

def main():
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');a=p.parse_args()
 proof=ROOT/'logs/diagnostics/embla/round2-qualification';campaign=json.loads((proof/'campaign.json').read_text())
 assert campaign['complete']
 assert campaign['passed'] and len(campaign['tasks'])==11
 restoration=json.loads((proof/'same-process-restore/result.json').read_text())
 assert restoration['passed'] and restoration['continued_after_restore']
 assert len(restoration['cycles'])==2 and all(c['exact'] for c in restoration['cycles'])
 assert restoration['optimizer']=='AdamATan2 with EMA'
 assert '71 passed' in (ROOT/'logs/diagnostics/embla/round2-all-tests.log').read_text()
 assert (proof/'trainer-resumed.json').exists()
 for path,sha in json.loads((proof/'software.json').read_text()).items():
  if path=='models/lm_head.py':continue # Shared head was tuned separately; Embla uses its native head.
  assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha,path
 configdir=ROOT/'logs/diagnostics/embla/candidate-configs-v8-gas2'
 for name in ('embla-causal-all','embla-prefix-target','embla-loop-prefix-target'):
  sha=hashlib.sha256((configdir/(name+'.yaml')).read_bytes()).hexdigest()
  for rank in range(8):
   evidence=json.loads((proof/(name+'-gas2')/f'rank{rank}.json').read_text())
   assert evidence['passed'] and evidence['rank']==rank and evidence['world_size']==8 and evidence['config_sha256']==sha
 epoch=json.loads((ROOT/'logs/diagnostics/embla/round2-epoch-gas2.json').read_text())
 assert epoch['gradient_accumulation_steps']==2 and 350000<epoch['complete_optimizer_steps']<400000
 db=Path('/var/tmp/dfm11-architecture-comparison/jobs.sqlite');c=sqlite3.connect(db,timeout=60)
 rows=c.execute("select job_id,definition,status,token from jobs where job_id like 'embla-%-dfm11-%-train'").fetchall();assert len(rows)==24,len(rows)
 changes=[]
 for jid,raw,status,token in rows:
  assert status=='pending' and token is None,(jid,status,token)
  j=Job.from_row(json.loads(raw));co=j.metadata['cooperative_training'];cmd=co['command'];i=cmd.index('--config-path')+1
  assert cmd[i]==str(ROOT/'logs/diagnostics/embla/candidate-configs-v6-kernels'),(jid,cmd)
  cmd[i]=str(configdir)
  j.metadata['embla_kernel_qualification']=str(proof)
  errors=check_job(j,ROOT);assert not errors,(jid,errors)
  changes.append((jid,raw,_definition(j)))
 receipt={'rows':len(changes),'qualification':str(proof),'exact_live_restore':str(proof/'same-process-restore/result.json'),'independent_trajectory_bitwise_parity':False,'changes':[dict(job_id=j,before=json.loads(b),after=json.loads(n)) for j,b,n in changes],'executed':False}
 destination=proof/('queue-activation.json' if a.execute else 'queue-dry-run.json');assert not destination.exists()
 if a.execute:
  backup=sqlite3.connect(proof/f'before-activation-{int(time.time())}.sqlite');c.backup(backup);backup.close()
  c.execute('begin immediate')
  try:
   for jid,before,after in changes:
    result=c.execute("update jobs set definition=? where job_id=? and definition=? and status='pending' and token is null",(after,jid,before));assert result.rowcount==1,jid
   c.commit()
  except BaseException:c.rollback();raise
  for jid,_,after in changes:
   assert c.execute('select definition,status,token from jobs where job_id=?',(jid,)).fetchone()==(after,'pending',None)
  receipt['executed']=True
 destination.write_text(json.dumps(receipt,indent=2));print(json.dumps({'rows':len(changes),'executed':a.execute,'receipt':str(destination)}))
if __name__=='__main__':main()

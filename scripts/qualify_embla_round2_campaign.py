"""Bounded kernel qualification, with guaranteed hand-back to managed trainer."""
import os,sys,json,time,re,signal,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from training_suspend.controller import Controller,CudaBackend
from training_suspend.protocol import read_json,atomic_write,submit
PYTHON='/home/ucloud/miniforge3/envs/hrm/bin/python'

def main():
 import argparse,hashlib
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 out=args.output.resolve();out.mkdir(exist_ok=False)
 atomic_write(out/'software.json',{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [*sorted((ROOT/'models/embla').glob('*.py')),ROOT/'models/baselines/embla.py',ROOT/'models/lm_head.py']})
 root=ROOT/'logs/training/transformer48_dfm11_prefixlm_targetonly_20261114/control'
 active=Path(read_json(root/'active.json')['control_dir']);hold=active/'hold';token='Embla kernel qualification '+str(os.getpid())
 assert not hold.exists() and not (root/'hold').exists(),'Respect existing hold'
 previous=read_json(active/'resumed.json');controller=Controller(active,CudaBackend('/home/ucloud/miniforge3/envs/cuda-checkpoint-test/bin/cuda-checkpoint'))
 log=root/'training.log'
 with log.open('rb') as f:f.seek(max(0,log.stat().st_size-20000));tail=f.read().decode(errors='replace')
 steps=[int(x) for x in re.findall(r'step=(\d+)',tail)];assert steps
 target=((max(steps)+99)//100+1)*100
 assert target%50000<49000 and target<390000,'Do not collide with next eval/final boundary'
 tasks=[];ready=None
 with hold.open('x') as f:f.write(token)
 try:
  submit(active,[target]);print(json.dumps({'requested_step':target,'active':str(active)}),flush=True)
  deadline=time.monotonic()+600
  while time.monotonic()<deadline:
   value=read_json(active/'suspend_ready.json')
   if value['generation']>previous['generation']:
    ready,_=controller.ready();break
   time.sleep(2)
  assert ready,'Trainer did not reach suspension'
  atomic_write(out/'trainer-before.json',ready)
  controller.offload(lease_seconds=1800);print('Trainer offloaded',flush=True)
  specs=[]
  for family in ('transformer','b'):
   for mode in ('full','selected'):
    name=f'{family}-{mode}'
    specs.append((name,[PYTHON,'-m','torch.distributed.run','--standalone','--nproc_per_node=8','scripts/qualify_queued_training.py','--config',str(ROOT/'logs/diagnostics/embla/round2-head-configs'/f'{name}.yaml'),'--output',str(out/name)]))
  for gas in (4,2):
   for variant in ('embla-causal-all','embla-prefix-target','embla-loop-prefix-target'):
    name=f'{variant}-gas{gas}';directory=out/name
    specs.append((name,[PYTHON,'-m','torch.distributed.run','--standalone','--nproc_per_node=8','scripts/qualify_queued_training.py','--config',str(ROOT/f'logs/diagnostics/embla/candidate-configs-v8-gas{gas}'/f'{variant}.yaml'),'--output',str(directory)]))
  specs.append(('restoration',[PYTHON,'scripts/test_embla_kernel_cuda_restore.py','--output',str(out/'same-process-restore')]))
  for name,command in specs:
   print('Starting '+name,flush=True);start=time.time()
   env=os.environ.copy();env['PATH']='/home/ucloud/miniforge3/envs/hrm/bin:'+env['PATH'];env.pop('CUDA_VISIBLE_DEVICES',None)
   with (out/(name+'.log')).open('x') as stream:
    proc=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    try:code=proc.wait(timeout=900)
    except BaseException:
     os.killpg(proc.pid,signal.SIGTERM)
     try:proc.wait(timeout=30)
     except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
     raise
   tasks.append(dict(name=name,returncode=code,seconds=time.time()-start));atomic_write(out/'campaign.json',{'tasks':tasks,'complete':False})
   print(json.dumps(tasks[-1]),flush=True)
   if code and name.endswith('gas4'):break
 finally:
  if hold.exists() and hold.read_text()==token:hold.unlink()
  if ready:
   atomic_write(active/f"generation_{ready['generation']:06d}"/'restore.request',ready)
   print('Released qualification hold; requesting managed in-memory restore',flush=True)
   deadline=time.monotonic()+1000
   while time.monotonic()<deadline:
    resumed=read_json(active/'resumed.json')
    if resumed['generation']==ready['generation']:
     atomic_write(out/'trainer-resumed.json',resumed);break
    time.sleep(2)
   else:raise RuntimeError('Managed trainer restore acknowledgement missing')
 atomic_write(out/'campaign.json',{'tasks':tasks,'complete':True,'passed':len(tasks)==11 and all(x['returncode']==0 for x in tasks if not x['name'].endswith('gas2'))})
 print('Qualification finished; trainer resumed',flush=True)
if __name__=='__main__':main()

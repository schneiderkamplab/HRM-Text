"""Verify exact live tensor restoration, independent of atomic-gradient ordering."""
import os,sys,time,json,signal,subprocess,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from training_suspend.protocol import atomic_write,read_json

def worker(out):
 import torch
 from models.baselines.embla import Embla, EmblaLMHead
 from training_suspend.runtime import SuspendHook
 torch.set_num_threads(4);torch.cuda.set_per_process_memory_fraction(.03);torch.manual_seed(83)
 spec=importlib.util.spec_from_file_location('embla_tests',ROOT/'tests/test_embla_model.py');tests=importlib.util.module_from_spec(spec);spec.loader.exec_module(tests)
 cfg=tests.tiny_config();cfg.hidden_size=128;cfg.head_dim=64;cfg.num_attention_heads=2;cfg.num_key_value_heads=1;cfg.sliding_num_attention_heads=2;cfg.sliding_num_key_value_heads=1;cfg.sliding_window=32
 spec={'embla_config':cfg.to_dict(),'vocab_size':64,'attn_type':'prefixlm','decoder_loops':4,'embla_fa4_window':True,'embla_fused_relu':True,'embla_fused_sparse':True,'embla_single_topk':True,'embla_batched_windows':True,'embla_relu_tile_m':32,'embla_target_head_only':True}
 model=EmblaLMHead(Embla(spec),spec).cuda()
 from models.adam_atan2 import AdamATan2
 optimizer=AdamATan2(model.parameters(),lr=1e-4,ema=.9999)
 hook=SuspendHook(out/'control',[1,2],torch.device('cuda'),poll_steps=1,wait_seconds=.1)
 ids=torch.randint(0,64,(1,137),device='cuda');positions=torch.arange(137,device='cuda')[None]%71;prompt=positions<33
 labels=ids.roll(-1,1).clone();labels[prompt]=-100
 batch={'inputs':ids[0],'labels':labels[0],'position_ids':positions[0],'prefix_lens':torch.tensor([33,33],device='cuda'),'cu_seqlens':torch.tensor([0,71,137],device='cuda'),'total_seqlen':torch.tensor(137)}
 def tensors():
  state={**{'model/'+k:v for k,v in model.state_dict().items()},**{'grad/'+k:p.grad for k,p in model.named_parameters() if p.grad is not None}}
  for i,p in enumerate(model.parameters()):
   for k,v in optimizer.state[p].items():
    if isinstance(v,torch.Tensor):state[f'optim/{i}/{k}']=v
  state['rng']=torch.cuda.get_rng_state();state['input']=ids
  return {k:v.detach().cpu().clone() for k,v in state.items()}
 checks=[]
 for step in (1,2,3):
  optimizer.zero_grad(set_to_none=True)
  with torch.autocast('cuda',dtype=torch.bfloat16):_,loss,_=model(None,batch)
  loss.backward();optimizer.step();torch.cuda.synchronize();assert torch.isfinite(loss)
  if step<3:
   before=tensors();path=out/f'checkpoint-{step}.pt'
   def save():torch.save(before,path);return path
   assert hook.after_step(step,save)
   after=tensors();assert before.keys()==after.keys()
   for key in before:assert torch.equal(before[key],after[key]),key
   checks.append({'step':step,'tensor_count':len(before),'exact':True})
 atomic_write(out/'result.json',{'passed':True,'cycles':checks,'continued_after_restore':True,'optimizer':'AdamATan2 with EMA', 'scope':'exact live model/optimizer/EMA/gradient/input/RNG tensors across two actual CUDA offload/restores; four-loop PrefixLM with all kernels; not equality of independent stochastic trajectories'})

def main():
 import argparse
 from training_suspend.controller import Controller,CudaBackend
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--worker',action='store_true');args=p.parse_args();out=args.output.resolve()
 if args.worker:return worker(out)
 manifest=out.parent/'followup-head-benchmarks.json'
 if manifest.exists():
  for task in read_json(manifest):
   destination=out.parent/task['name'];assert not destination.exists();destination.mkdir()
   command=[sys.executable,'-m','torch.distributed.run','--standalone','--nproc_per_node=8','scripts/qualify_queued_training.py','--config',task['config'],'--output',str(destination)]
   environment=os.environ.copy();environment.pop('CUDA_VISIBLE_DEVICES',None);environment['PATH']='/home/ucloud/miniforge3/envs/hrm/bin:'+environment['PATH']
   with (destination/'run.log').open('x') as log:
    followup=subprocess.Popen(command,cwd=ROOT,env=environment,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    try:code=followup.wait(timeout=600)
    except BaseException:
     os.killpg(followup.pid,signal.SIGTERM)
     try:followup.wait(timeout=20)
     except subprocess.TimeoutExpired:os.killpg(followup.pid,signal.SIGKILL);followup.wait()
     raise
   assert code==0,task['name']
 out.mkdir(exist_ok=False);(out/'control').mkdir()
 env=os.environ.copy();env['CUDA_VISIBLE_DEVICES']='7';env['OMP_NUM_THREADS']='4'
 command=[sys.executable,'-m','training_suspend.controller','launch','--control-root',str(out/'control'),'--',sys.executable,str(Path(__file__).resolve()),'--worker','--output',str(out)]
 backend=CudaBackend('/home/ucloud/miniforge3/envs/cuda-checkpoint-test/bin/cuda-checkpoint');seen=set();phases=[]
 with (out/'worker.log').open('x') as log:
  proc=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  deadline=time.monotonic()+240
  try:
   while proc.poll() is None:
    assert time.monotonic()<deadline,'Restore test timed out'
    for path in (out/'control').glob('*/suspend_ready.json'):
     ready=read_json(path);gen=ready['generation']
     if gen in seen:continue
     ctl=Controller(path.parent,backend);ctl.offload(lease_seconds=120)
     try:
      assert all(backend.state(r['pid'])=='checkpointed' for r in ready['ranks'])
      time.sleep(1)
     finally:ctl.restore()
     seen.add(gen);phases.append({'generation':gen,'offload_and_restore':True});atomic_write(out/'phases.json',phases)
    time.sleep(.1)
   assert proc.returncode==0,proc.returncode
  finally:
   if proc.poll() is None:
    os.killpg(proc.pid,signal.SIGTERM)
    try:proc.wait(timeout=20)
    except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
 assert len(seen)==2
 print(json.dumps(read_json(out/'result.json')),flush=True)
if __name__=='__main__':main()

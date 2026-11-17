"""Eight-rank full-recipe training check on real packed data; no W&B or queue writes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main():
    import faulthandler,signal
    faulthandler.register(signal.SIGUSR1,all_threads=True)
    faulthandler.dump_traceback_later(120,repeat=True)
    import torch
    import torch.distributed as dist
    import yaml
    from pretrain import (PretrainConfig,create_dataloader,create_model_and_carry,
        TrainState,move_batch_to_device,train_accumulated_batches,compute_train_extra_args,update_auto_module_rates)
    from models.accelerator import set_accelerator_type
    from models.common import prepare_prefixlm_batch,wrap_tensor
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--steps',type=int,default=3);args=p.parse_args();assert args.steps>=3
    rank=int(os.environ['RANK']);world=int(os.environ['WORLD_SIZE']);local=int(os.environ['LOCAL_RANK'])
    assert world==8,'Full-size qualification requires eight ranks'
    torch.set_num_threads(4);torch.cuda.set_device(local)
    if torch.cuda.mem_get_info()[0]<178000*1024**2:raise RuntimeError('Dedicated GPUs required')
    args.output.mkdir(parents=True,exist_ok=True)
    receipt=args.output/f'rank{rank}.json'
    assert not receipt.exists(),'Use a fresh output directory'
    data=yaml.safe_load(args.config.read_text())
    data.update(checkpoint_path=str(args.output),resume_checkpoint_path=None,resume_checkpoint_tag=None,
        suspend_after_steps=[],suspend_control_dir=None)
    cfg=PretrainConfig(**data)
    dist.init_process_group('nccl')
    try:
        device=torch.device('cuda',local);set_accelerator_type(cfg.accelerator_type);torch.manual_seed(cfg.seed)
        local_tokens=cfg.global_batch_size//(world*cfg.gradient_accumulation_steps)
        loader,metadata=create_dataloader(cfg,local_tokens,True,rank,world)
        iterator=iter(loader)
        model,carry,optim=create_model_and_carry(cfg,metadata,local_tokens,device)
        total=cfg.training_total_steps or metadata.total_length//cfg.global_batch_size
        state=TrainState(model,carry,optim,total,total,getattr(torch,cfg.fwd_bwd_dtype),False)
        for group in optim.param_groups:group['lr']=cfg.lr
        torch.cuda.reset_peak_memory_stats();seconds=[];losses=[]
        for i in range(args.steps):
            batches=[]
            for _ in range(cfg.gradient_accumulation_steps):
                raw,info=next(iterator);info.pop('resume_info',None)
                batches.append(prepare_prefixlm_batch(move_batch_to_device(raw,device)|{k:wrap_tensor(torch.tensor(v)) for k,v in info.items()}))
            torch.cuda.synchronize();start=time.monotonic()
            kwargs=compute_train_extra_args(model,state)
            update_auto_module_rates(cfg,model,optim,kwargs.get("bp_steps"))
            metrics,skipped=train_accumulated_batches(cfg,rank,state,batches,cfg.compile_train_batch,**kwargs)
            torch.cuda.synchronize();seconds.append(time.monotonic()-start)
            if skipped or not torch.isfinite(metrics['loss'][0]):raise RuntimeError('Nonfinite/skipped update')
            losses.append(float(metrics['loss'][0]));state.step+=1
            if rank == 0:print(json.dumps({'completed_updates':len(losses),'step_seconds':seconds[-1],'loss_sum':losses[-1]}),flush=True)
        result=dict(passed=True,rank=rank,world_size=world,config_sha256=hashlib.sha256(args.config.read_bytes()).hexdigest(),
            global_batch_size=cfg.global_batch_size,step_seconds=seconds,losses=losses,
            peak_allocated=torch.cuda.max_memory_allocated(),peak_reserved=torch.cuda.max_memory_reserved(),
            free_bytes=torch.cuda.mem_get_info()[0],scope=f'{args.steps} full-recipe real-data updates at maximum scheduled BP; no quality claim')
        receipt.write_text(json.dumps(result,indent=2));dist.barrier()
    finally:dist.destroy_process_group()
if __name__=='__main__':main()

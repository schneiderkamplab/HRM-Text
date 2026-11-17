"""Two-rank CPU/Gloo oracle for rank-aligned draws and weighted DDP updates."""
import copy
from pathlib import Path
import torch
import torch.distributed as dist
import torch.multiprocessing as mp
from torch.nn.parallel import DistributedDataParallel
from test_cycle_training import config,state,batch
from models.cycle_schedule import step_schemes,weighted_call_counts
from models.module_learning_rates import update_auto_module_rates
from pretrain import train_accumulated_batches


def worker(rank,root):
    torch.set_num_threads(1);torch.manual_seed(71)
    dist.init_process_group('gloo',init_method='file://'+root+'/rendezvous',rank=rank,world_size=2)
    c=config();s=state(c);r=state(c);r.model.load_state_dict(s.model.state_dict())
    s.model=DistributedDataParallel(s.model)
    batches=[batch(2+rank*2),batch(4-rank*2)]
    try:
        for step in (1,2,3):
            s.step=r.step=step
            schemes=step_schemes(c,step,2,5)
            draws=[None]*2;dist.all_gather_object(draws,schemes);assert draws[0]==draws[1]
            counts=weighted_call_counts(schemes,[3.,3.]);update_auto_module_rates(c,r.model,r.optim,5,counts)
            r.optim.zero_grad()
            for b,(h,l) in zip(batches,schemes):
                _,loss,_=r.model(None,b,H_cycles=h,L_cycles=l,bp_steps=h*(l+1))
                (loss*.5).backward()
            for p in r.model.parameters():dist.all_reduce(p.grad);p.grad/=2
            r.optim.step()
            train_accumulated_batches(c,rank,s,batches,False,bp_steps=5)
            for p,q in zip(s.model.module.parameters(),r.model.parameters()):torch.testing.assert_close(p,q,rtol=1e-6,atol=1e-8)
            if step==1:
                # Disk restore is separate for each rank; next draws derive only from step/config.
                path=Path(root)/f'rank{rank}.pt'
                torch.save(dict(model=s.model.module.state_dict(),optimizer=s.optim.state_dict()),path)
                saved=torch.load(path,weights_only=True)
                s.model.module.load_state_dict(saved['model']);s.optim.load_state_dict(saved['optimizer'])
        Path(root,f'passed{rank}').write_text('passed')
    finally:dist.destroy_process_group()


def test_two_rank_accumulation_and_resume(tmp_path):
    mp.spawn(worker,args=(str(tmp_path),),nprocs=2,join=True)
    assert all((tmp_path/f'passed{rank}').exists() for rank in range(2))

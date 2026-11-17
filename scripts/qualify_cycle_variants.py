"""Isolated full-recipe BP16/BP15 memory qualification; never changes the queue.

Run with the HRM Python: python scripts/qualify_cycle_variants.py --config
<resolved-training.yaml> --output <new-directory> --gpus 0,1,2,3,4,5,6,7.
The default dry run validates inputs and reports availability. --execute requires
all selected GPUs to be idle and runs fresh torchrun processes for each budget.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def gpu_snapshot(gpus):
    rows = subprocess.check_output(['nvidia-smi', '--query-gpu=index,uuid,memory.total,memory.used,utilization.gpu',
                                   '--format=csv,noheader,nounits'], text=True)
    selected = {}
    for row in rows.splitlines():
        index, uuid, total, used, util = [v.strip() for v in row.split(',')]
        if index in gpus:
            selected[index] = dict(uuid=uuid,total_mib=int(total),used_mib=int(used),util=int(util))
    if set(selected) != set(gpus):
        raise ValueError('Not all requested GPUs exist')
    jobs = subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True)
    for row in jobs.splitlines():
        uuid,pid=[s.strip() for s in row.split(',')]
        for gpu in selected.values():
            if gpu['uuid']==uuid:gpu.setdefault('pids',[]).append(int(pid))
    return selected


def belongs_to_worker(pid, parent):
    """torchrun rank workers have their own process groups; follow ancestry."""
    visited = set()
    while pid > 1 and pid not in visited:
        if pid == parent:
            return True
        visited.add(pid)
        try:
            pid = int(Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            return False
    return False


def idle(snapshot):
    return all(not g.get('pids') and g['util']==0 and g['used_mib']<2048 for g in snapshot.values())


def trial_passed(returncode, ranks, gpu_count, minimum, errors):
    return (returncode == 0 and len(ranks) == gpu_count
            and {r.get('rank') for r in ranks} == set(range(gpu_count))
            and all(r.get('passed') and r.get('mixed_steps', 0) >= 100 for r in ranks)
            and len(minimum) == gpu_count
            and all(2048 <= v < float('inf') for v in minimum.values()) and not errors)


def memory_failure(returncode, log, ranks, gpu_count, minimum):
    if returncode:
        return 'out of memory' in log.lower() or 'qualification_headroom' in log.lower()
    complete = (len(ranks) == gpu_count and {r.get('rank') for r in ranks} == set(range(gpu_count))
                and all(r.get('passed') and r.get('mixed_steps', 0) >= 100 for r in ranks))
    return complete and len(minimum) == gpu_count and any(v < 2048 for v in minimum.values())


def write_json(path,value):
    path=Path(path);temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,default=str)+'\n');temporary.replace(path)


def read_config(path, budget, output):
    import yaml
    from pretrain import PretrainConfig
    d=yaml.safe_load(Path(path).read_text())
    d['arch'].update(cycle_variants='full_budget',cycle_sampler_version=1,bp_max_steps=budget)
    d.update(checkpoint_path=str(output),resume_checkpoint_path=None,resume_checkpoint_tag=None,
             suspend_after_steps=[],suspend_control_dir=None,cycle_variants_prewarm=True)
    c=PretrainConfig(**d)
    if c.optimizer!='adam_atan2':raise ValueError('Initial memory qualification requires the B AdamATan2 recipe')
    if c.distributed_strategy!='fsdp' or not c.compile_train_batch:
        raise ValueError('Full qualification requires the intended compiled FSDP recipe')
    if not Path(c.data.path,'metadata.json').is_file():raise ValueError('Dataset metadata missing')
    return c


def worker(args):
    import numpy as np
    import torch
    import torch.distributed as dist
    from pretrain import (create_dataloader,create_model_and_carry,TrainState,move_batch_to_device,
                          train_accumulated_batches,prewarm_cycle_variants)
    from models.accelerator import set_accelerator_type
    from models.common import prepare_prefixlm_batch,wrap_tensor
    from models.cycle_schedule import scheme_pool
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    rank=int(os.environ['RANK']);world=int(os.environ['WORLD_SIZE']);local_rank=int(os.environ['LOCAL_RANK'])
    c=read_config(args.config,args.budget,out)
    torch.set_num_threads(4);torch.cuda.set_device(local_rank)
    dist.init_process_group('nccl');device=torch.device('cuda',local_rank)
    set_accelerator_type(c.accelerator_type);torch.manual_seed(c.seed)
    if c.global_batch_size%(world*c.gradient_accumulation_steps):raise ValueError('Nonintegral local batch')
    size=c.global_batch_size//(world*c.gradient_accumulation_steps)
    loader,metadata=create_dataloader(c,size,True,rank,world)
    iterator=iter(loader);raw,info=next(iterator);info.pop('resume_info',None)
    first=prepare_prefixlm_batch(move_batch_to_device(raw,device)|{k:wrap_tensor(torch.tensor(v)) for k,v in info.items()})
    tokens=raw['inputs'].cpu().numpy()
    def layout(length):
        lengths=[min(length,size-i) for i in range(0,size,length)]
        prefixes=[max(1,n//2) if n>1 else 0 for n in lengths]
        ids=np.resize(tokens,size);labels=np.roll(ids,-1).copy();positions=[];offset=0
        for n,prefix in zip(lengths,prefixes):
            positions.extend(range(n))
            if c.data.target_only:labels[offset:offset+prefix]=-100
            offset+=n
        b=dict(inputs=torch.tensor(ids,device=device),labels=torch.tensor(labels,device=device),
               position_ids=torch.tensor(positions,device=device),
               prefix_lens=torch.tensor(prefixes,device=device,dtype=torch.int32),
               causal_lens=torch.tensor([n-p for n,p in zip(lengths,prefixes)],device=device,dtype=torch.int32),
               cu_seqlens=torch.tensor([0]+list(np.cumsum(lengths)),device=device,dtype=torch.int32))
        if getattr(c.arch,'attn_type','prefixlm')=='mixedlm':
            from models.mixedlm import routing
            # Two reviewed assistant turns per long prompt exercise refresh routing.
            header=loader.dataset._mixed_header
            prompts=[];offset=0
            for n,p in zip(lengths,prefixes):
                prompt=ids[offset:offset+p].copy()
                if p>=2*len(header)+2:
                    prompt[:len(header)]=header;prompt[p//2:p//2+len(header)]=header
                prompts.append(prompt);offset+=n
            b.update({k:v.to(device) for k,v in routing(prompts,[n-p for n,p in zip(lengths,prefixes)],header).items()})
        scalars=dict(total_seqlen=size,numseqs=len(lengths),max_seqlen_prefix=max(prefixes),
                     max_seqlen_causal=max(n-p for n,p in zip(lengths,prefixes)),max_seqlen_all=max(lengths))
        return prepare_prefixlm_batch(b|{k:wrap_tensor(torch.tensor(v)) for k,v in scalars.items()})
    batches=[first,layout(min(metadata.max_seq_len-1,size)),layout(min(64,size))]
    model,carry,optim=create_model_and_carry(c,metadata,size,device)
    st=TrainState(model,carry,optim,0,c.training_total_steps or c.epochs*(metadata.total_length//c.global_batch_size),
                  getattr(torch,c.fwd_bwd_dtype),False)
    for group in optim.param_groups:group['lr']=c.lr
    torch.cuda.reset_peak_memory_stats();began=time.monotonic();times=[];lowest_free=torch.cuda.mem_get_info()[0]
    # Real prewarm covers all layouts, not just one synthetic shape.
    prewarm=prewarm_cycle_variants(c,st,batches)
    import pretrain
    original=pretrain.step_schemes
    observations=[]
    def step(b,forced=None):
        nonlocal lowest_free
        st.step+=1
        if forced is not None:
            pretrain.step_schemes=lambda config,step,microbatches,budget:tuple([forced]*microbatches)
        started=time.monotonic()
        try:
            metrics,skipped=train_accumulated_batches(c,rank,st,[b]*c.gradient_accumulation_steps,True,bp_steps=args.budget)
            torch.cuda.synchronize()
            if skipped or not torch.isfinite(metrics['loss'][0]):raise RuntimeError('Nonfinite or skipped qualification update')
        finally:pretrain.step_schemes=original
        times.append(time.monotonic()-started)
        free,total=torch.cuda.mem_get_info();lowest_free=min(lowest_free,free)
        observations.append(dict(step=st.step,scheme=forced,free_bytes=free,allocated=torch.cuda.memory_allocated(),reserved=torch.cuda.memory_reserved()))
        if free<2*1024**3:raise RuntimeError('QUALIFICATION_HEADROOM: less than 2 GiB remains')
    for scheme in scheme_pool(args.budget):
        for b in batches:step(b,scheme)
    times.clear()
    for i in range(100):step(batches[i%len(batches)])
    result=dict(passed=True,budget=args.budget,rank=rank,world_size=world,config=c.model_dump(),
                layouts=['real_sample','long_sequences','dense_64_tokens'],local_tokens=size,
                steps=st.step,mixed_steps=100,seconds=time.monotonic()-began,
                mixed_seconds=sum(times),steps_per_second=len(times)/sum(times),
                tokens_per_second=100*c.global_batch_size/sum(times),
                peak_allocated=torch.cuda.max_memory_allocated(),peak_reserved=torch.cuda.max_memory_reserved(),
                min_free_bytes=lowest_free,prewarm=prewarm,observations=observations)
    write_json(out/f'rank{rank}.json',result);dist.barrier();dist.destroy_process_group()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--gpus',default='0,1,2,3,4,5,6,7');parser.add_argument('--execute',action='store_true')
    parser.add_argument('--worker',action='store_true');parser.add_argument('--budget',type=int,choices=[15,16])
    args=parser.parse_args()
    if args.worker:
        try:worker(args)
        except Exception as exc:
            write_json(Path(args.output)/f"error-rank{os.environ.get('RANK','unknown')}.json",dict(error=repr(exc),oom='out of memory' in str(exc).lower()))
            raise
        return
    os.chdir(ROOT)
    output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=True)
    if (output/'report.json').exists():raise ValueError('Use a fresh output directory; prior reports are immutable')
    config=Path(args.config).resolve();gpus=args.gpus.split(',')
    if len(gpus)!=len(set(gpus)):raise ValueError('GPU list contains duplicates')
    c=read_config(config,16,output/'bp16');snapshot=gpu_snapshot(gpus)
    software={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [
        ROOT/'pretrain.py',ROOT/'models/cycle_schedule.py',ROOT/'models/module_learning_rates.py',
        ROOT/'models/baselines/hrm_nocarry_bp_warmup.py',Path(__file__).resolve()]}
    report=dict(software_hashes=software,metadata_sha256=hashlib.sha256(Path(c.data.path,'metadata.json').read_bytes()).hexdigest(),status='dry_run',config=str(config),config_sha256=hashlib.sha256(config.read_bytes()).hexdigest(),
                gpu_snapshot=snapshot,gpus=gpus,selected_budget=None,minimum_headroom_gib=2,
                recipe=c.model_dump(),trials=[])
    if not args.execute:
        write_json(output/'report.json',report);print(json.dumps({'status':'dry_run','idle':idle(snapshot),'report':str(output/'report.json')}));return
    if not idle(snapshot):
        report['status']='waiting_for_idle_gpus';write_json(output/'report.json',report)
        print('GPUs are occupied; no workers launched.');raise SystemExit(75)
    for budget in (16,15):
        trial=output/f'bp{budget}';trial.mkdir()
        if not idle(gpu_snapshot(gpus)):raise RuntimeError('GPU admission changed before launch')
        minimum={g:float('inf') for g in gpus};stop=threading.Event();errors=[]
        def monitor():
            while not stop.is_set():
                try:
                    for g,x in gpu_snapshot(gpus).items():minimum[g]=min(minimum[g],x['total_mib']-x['used_mib'])
                except Exception as exc:errors.append(repr(exc))
                stop.wait(.2)
        thread=threading.Thread(target=monitor);thread.start()
        env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES=','.join(gpus),OMP_NUM_THREADS='4')
        command=[sys.executable,'-m','torch.distributed.run','--standalone',f'--nproc_per_node={len(gpus)}',
                 str(Path(__file__).resolve()),'--worker','--budget',str(budget),'--config',str(config),'--output',str(trial)]
        with (trial/'torchrun.log').open('w') as log:
            process = subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                while process.poll() is None:
                    snapshot = gpu_snapshot(gpus)
                    foreign = []
                    for gpu in snapshot.values():
                        for pid in gpu.get('pids', []):
                            try:
                                if not belongs_to_worker(pid, process.pid):
                                    foreign.append(pid)
                            except ProcessLookupError:
                                pass
                    if foreign:
                        errors.append(f'Foreign GPU workload appeared: {foreign}')
                        os.killpg(process.pid, signal.SIGTERM)
                        break
                    time.sleep(.5)
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=30)
                result = process
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL);process.wait(timeout=30)
                stop.set();thread.join()
        ranks=[json.loads(p.read_text()) for p in trial.glob('rank*.json')]
        passed=trial_passed(result.returncode,ranks,len(gpus),minimum,errors)
        report['trials'].append(dict(budget=budget,returncode=result.returncode,passed=passed,min_device_free_mib={g:(None if v==float('inf') else v) for g,v in minimum.items()},monitor_errors=errors))
        if passed:
            report.update(status='qualified',selected_budget=budget);break
        text=(trial/'torchrun.log').read_text(errors='replace').lower()
        if errors:
            report.update(status='failed_monitor_or_gpu_admission');break
        if not memory_failure(result.returncode,text,ranks,len(gpus),minimum):
            report.update(status='failed_nonmemory');break
        report['status']='unqualified_memory'
    write_json(output/'report.json',report);print(json.dumps({'status':report['status'],'selected_budget':report['selected_budget']}))


if __name__=='__main__':main()

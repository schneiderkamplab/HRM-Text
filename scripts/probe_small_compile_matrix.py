"""Single-GPU, bounded numerical probes; no training state or W&B access."""
import argparse
import copy
import json
from pathlib import Path
import sys
import time
import os
import pickle
import io

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import torch
from torch.distributed._composable import checkpoint
from models.transformer import Transformer, TransformerConfig, TransformerBlock
from models.baselines.hrm_nocarry_bp_warmup import HierarchicalReasoningModel
from models.common import prepare_prefixlm_batch, wrap_tensor
from models.flash_attention_prefixlm_v2 import compute_aux_seq_tensors_scalars


def compare(a, b):
    x, y = a.double(), b.double()
    return {"relative_l2": ((x-y).norm()/x.norm().clamp_min(1e-30)).item(),
            "cosine": torch.nn.functional.cosine_similarity(x.flatten(), y.flatten(), dim=0).item(),
            "max_absolute": (x-y).abs().max().item()}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--mode', required=True)
    p.add_argument('--depth', type=int, default=1)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--hrm', action='store_true', help='Use actual H/L recurrence; depth means bp_steps')
    p.add_argument('--math-reference', choices=['float32','float64'])
    p.add_argument('--accum', type=int, choices=[1,2,8], default=1)
    p.add_argument('--fsdp', choices=['keep','reshard'])
    p.add_argument('--trained-level', choices=['H','L'])
    args = p.parse_args()
    device=int(os.environ.get('LOCAL_RANK',0))
    torch.cuda.set_device(device)
    torch.cuda.set_per_process_memory_fraction(6*2**30/torch.cuda.get_device_properties(device).total_memory)
    if args.fsdp:
        import torch.distributed as dist
        from torch.distributed.fsdp import fully_shard, MixedPrecisionPolicy
        dist.init_process_group('nccl')
    torch.set_num_threads(1)
    torch._inductor.config.compile_threads = 1
    torch.manual_seed(173)
    torch.backends.cuda.matmul.allow_tf32=False
    width=1792 if args.trained_level else 256
    cfg = TransformerConfig(max_seq_len=128, n_layers=3, hidden_size=width, num_heads=width//128,
                            expansion=4, init_type='lecun_normal', norm_type='pre',
                            norm_eps=1e-6, pos_emb_type='rope', rope_theta=10000)
    base = (HierarchicalReasoningModel(cfg.model_dump() | {'n_layers':6,'half_layers':True,
            'H_cycles':2,'L_cycles':3}) if args.hrm else Transformer(cfg)).cuda()
    if args.trained_level:
        assert not args.hrm
        source=Path('checkpoints/experiments/checkpoint_compile_xxl_619000/source/fsdp2_ephemeral_step_619000')
        metadata=pickle.load((source/'.metadata').open('rb'))
        with torch.no_grad():
            for name,param in base.named_parameters():
                fqn=f'model.model.{args.trained_level}_level.core.{name}'
                entries=sorted([(tuple(k.offset),v) for k,v in metadata.storage_data.items() if k.fqn==fqn])
                chunks=[]
                for _,entry in entries:
                    with (source/entry.relative_path).open('rb') as f:
                        f.seek(entry.offset)
                        chunks.append(torch.load(io.BytesIO(f.read(entry.length)),map_location='cpu',weights_only=True))
                weight=torch.cat(chunks,dim=0)
                assert weight.shape==param.shape
                param.copy_(weight)
    x = torch.randn(128, width, device='cuda', dtype=torch.bfloat16)
    upstream = torch.randn_like(x).float()/x.numel()
    if args.math_reference:
        import models.layers as layers
        def math_attention(q,k,v,is_causal,**kwargs):
            # This probe uses two 64-token sequences, each with a 16-token prefix.
            pos=torch.arange(128,device=q.device)
            local=pos%64
            mask=(pos[:,None]//64==pos[None,:]//64)&((local[None,:]<16)|(local[None,:]<=local[:,None]))
            scores=torch.einsum('ihd,jhd->hij',q,k)/(q.shape[-1]**.5)
            weights=scores.masked_fill(~mask,-float('inf')).softmax(-1)
            return torch.einsum('hij,jhd->ihd',weights,v)
        layers.flash_attn_varlen_prefixlm=math_attention
        dtype=getattr(torch,args.math_reference)
        base=base.to(dtype).cpu();x=x.to(dtype)
    if args.math_reference and args.accum != 1:
        raise ValueError('Math reference mask currently supports accum=1 only')
    tokens=128//args.accum
    # Accumulation controls use eight identical-length independent sequences.
    seq_len=16 if args.accum!=1 else 64
    tensors, scalars = compute_aux_seq_tensors_scalars(np.full(tokens//seq_len,seq_len//4,dtype=np.int32),
                                                      np.full(tokens//seq_len,3*seq_len//4,dtype=np.int32), tokens)
    info = {k:torch.from_numpy(v).cuda() for k,v in tensors.items()}
    info.update({k:wrap_tensor(torch.tensor(v)) for k,v in scalars.items()})
    info['position_ids'] = torch.arange(seq_len, device='cuda').repeat(tokens//seq_len)
    info = prepare_prefixlm_batch(info)
    snapshots = []
    for mode in ('eager', 'eager', args.mode):
        model = copy.deepcopy(base).cuda()
        blocks=[m for m in model.modules() if isinstance(m,TransformerBlock)]
        if mode in ('attn', 'mlp', 'norm'):
            for block in blocks:
                if mode == 'norm':
                    block.norm = torch.compile(block.norm, dynamic=False)
                else:
                    module = getattr(block, mode)
                    module.forward = torch.compile(module.forward, dynamic=False)
        if mode.startswith('block'):
            backend = 'aot_eager' if 'aot' in mode else 'inductor'
            for block in blocks:
                block.forward = torch.compile(block.forward, backend=backend, dynamic=False)
        if 'checkpoint' in mode:
            for block in blocks:
                checkpoint(block)
        if args.fsdp:
            for module in [*blocks,model]:
                fully_shard(module,mp_policy=MixedPrecisionPolicy(param_dtype=torch.bfloat16,reduce_dtype=torch.float32),
                            reshard_after_forward=args.fsdp=='reshard')
                if hasattr(module,'set_gradient_divide_factor'):module.set_gradient_divide_factor(1.)
                else:module.set_reduce_scatter_divide_factor(1.)
        def run(value, target):
            with torch.autocast('cuda', dtype=torch.bfloat16, enabled=not args.math_reference):
                if args.hrm:
                    _,value=model(None,value,bp_steps=args.depth,**info)
                else:
                    for _ in range(args.depth):
                        value = model(value, **info)
                loss = (value.float()*target).sum()
            loss.backward()
            return value.detach(), loss.detach()
        fn = torch.compile(run, backend='inductor', dynamic=False) if mode.startswith('outer') else run
        inputs = [v.detach().clone().requires_grad_(True) for v in x.chunk(args.accum)]
        start = time.monotonic()
        outputs=[];losses=[]
        for micro,(value,target) in enumerate(zip(inputs,upstream.chunk(args.accum))):
            if args.fsdp:model.set_requires_gradient_sync(micro==args.accum-1,recurse=True)
            output,loss=fn(value,target)
            outputs.append(output);losses.append(loss)
        output=torch.cat(outputs);loss=torch.stack(losses).sum()
        torch.cuda.synchronize()
        def local(g):return g.to_local() if hasattr(g,'to_local') else g
        assert all(p.grad is not None and torch.isfinite(local(p.grad)).all() for p in model.parameters())
        snapshots.append({'mode':mode, 'loss':loss.item(), 'seconds':time.monotonic()-start,
                          'output':output.float().cpu(), 'input_grad':torch.cat([(v.grad if v.grad is not None else torch.zeros_like(v)).float().cpu() for v in inputs]),
                          'grad':torch.cat([local(p.grad).flatten().float().cpu() for p in model.parameters()])})
        del model, fn, value, output, loss
        torch.cuda.empty_cache()
    result = {'mode':args.mode, 'depth':args.depth,
              'peak_allocated_gib':torch.cuda.max_memory_allocated()/2**30,
              'peak_reserved_gib':torch.cuda.max_memory_reserved()/2**30,
              'arms':[{k:v for k,v in s.items() if not isinstance(v,torch.Tensor)} for s in snapshots],
              'repeat':{k:compare(snapshots[0][k],snapshots[1][k]) for k in ('output','input_grad','grad')},
              'candidate':{k:compare(snapshots[0][k],snapshots[2][k]) for k in ('output','input_grad','grad')}}
    output=args.output if device==0 else args.output.with_name(args.output.stem+f'_rank{device}.json')
    output.write_text(json.dumps(result, indent=2))
    torch.save(snapshots,output.with_suffix('.pt'))
    print(json.dumps(result), flush=True)
    if args.fsdp:dist.destroy_process_group()


if __name__ == '__main__':
    main()

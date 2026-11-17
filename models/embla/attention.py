"""Bounded-score-memory exact squared-ReLU attention.

Tiles use device matmuls; custom backward recomputes scores instead of retaining
an N×N graph. Inputs are already QK-normalized, [B,T,H,D].
"""
import torch
from functools import wraps, lru_cache


def fp32_math(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        tensor = next(x for x in args if isinstance(x, torch.Tensor))
        with torch.autocast(tensor.device.type, enabled=False):
            return function(*args, **kwargs)
    return wrapped


def tile_mask(segments, positions, prompt, qa, qb, ka, kb, prefix):
    same = segments[:,qa:qb,None] == segments[:,None,ka:kb]
    causal = positions[:,qa:qb,None] >= positions[:,None,ka:kb]
    if prefix:
        causal = causal | (prompt[:,qa:qb,None] & prompt[:,None,ka:kb])
    return same & causal & (segments[:,qa:qb,None] >= 0) & (segments[:,None,ka:kb] >= 0)


class _ReluAttention(torch.autograd.Function):
    @staticmethod
    @fp32_math
    def forward(ctx,q,k,v,segments,positions,prompt,prefix,tile):
        b,t,h,d = q.shape
        groups = h // k.shape[2]
        output = torch.empty_like(q)
        denominator = torch.empty((b,h,t,1),device=q.device,dtype=torch.float32)
        for a in range(0,t,tile):
            z = min(a+tile,t)
            query = q[:,a:z].transpose(1,2).float()
            total = torch.full((b,h,z-a,1),d**.5,device=q.device)
            numerator = torch.zeros((b,h,z-a,d),device=q.device)
            for c in range(0,t,tile):
                e = min(c+tile,t)
                key = k[:,c:e].transpose(1,2).float().repeat_interleave(groups,1)
                value = v[:,c:e].transpose(1,2).float().repeat_interleave(groups,1)
                weights = (query @ key.transpose(-1,-2) / d**.5).relu().square()
                weights.masked_fill_(~tile_mask(segments,positions,prompt,a,z,c,e,prefix)[:,None],0)
                total += weights.sum(-1,keepdim=True)
                numerator += weights @ value
            output[:,a:z] = (numerator/total).transpose(1,2).to(q.dtype)
            denominator[:,:,a:z] = total
        ctx.save_for_backward(q,k,v,segments,positions,prompt,denominator)
        ctx.prefix,ctx.tile = prefix,tile
        return output

    @staticmethod
    @fp32_math
    def backward(ctx,gradient):
        q,k,v,segments,positions,prompt,denominator = ctx.saved_tensors
        b,t,h,d = q.shape
        kv = k.shape[2]
        groups = h//kv
        dq,dk,dv = (torch.zeros_like(x,dtype=torch.float32) for x in (q,k,v))
        # Reconstruct FP32 output (not rounded forward output) for exact derivative.
        for a in range(0,t,ctx.tile):
            z = min(a+ctx.tile,t)
            query = q[:,a:z].transpose(1,2).float()
            grad = gradient[:,a:z].transpose(1,2).float()
            denom = denominator[:,:,a:z]
            numerator = torch.zeros_like(query)
            for c in range(0,t,ctx.tile):
                e = min(c+ctx.tile,t)
                key = k[:,c:e].transpose(1,2).float().repeat_interleave(groups,1)
                value = v[:,c:e].transpose(1,2).float().repeat_interleave(groups,1)
                weights = (query @ key.transpose(-1,-2) / d**.5).relu().square()
                weights.masked_fill_(~tile_mask(segments,positions,prompt,a,z,c,e,ctx.prefix)[:,None],0)
                numerator += weights @ value
            dot = (grad * (numerator/denom)).sum(-1,keepdim=True)
            for c in range(0,t,ctx.tile):
                e = min(c+ctx.tile,t)
                key = k[:,c:e].transpose(1,2).float().repeat_interleave(groups,1)
                value = v[:,c:e].transpose(1,2).float().repeat_interleave(groups,1)
                positive = (query @ key.transpose(-1,-2) / d**.5).relu()
                positive.masked_fill_(~tile_mask(segments,positions,prompt,a,z,c,e,ctx.prefix)[:,None],0)
                ds = ((grad @ value.transpose(-1,-2))-dot)/denom * (2*positive/d**.5)
                dq[:,a:z] += (ds @ key).transpose(1,2)
                dk[:,c:e] += (ds.transpose(-1,-2) @ query).reshape(b,kv,groups,e-c,d).sum(2).transpose(1,2)
                dv[:,c:e] += ((positive.square()/denom).transpose(-1,-2) @ grad).reshape(b,kv,groups,e-c,d).sum(2).transpose(1,2)
        return dq.to(q.dtype),dk.to(k.dtype),dv.to(v.dtype),None,None,None,None,None


def relu_attention(q,k,v,segments,positions,prompt,*,prefix=False,tile=512):
    if tile < 1 or q.shape[2] % k.shape[2] or k.shape != v.shape:
        raise ValueError('Invalid tile or GQA dimensions')
    return _ReluAttention.apply(q,k,v,segments,positions,prompt,prefix,tile)


@torch.no_grad()
def local_indices(segments,positions,prompt,window,*,prefix=False):
    b,t = segments.shape
    offsets = torch.arange(-window+1,window if prefix else 1,device=segments.device)
    indices = torch.arange(t,device=segments.device)[:,None] + offsets
    safe = indices.clamp(0,t-1)[None].expand(b,-1,-1)
    keys_seg = segments[:,None,:].expand(-1,t,-1).gather(-1,safe)
    keys_pos = positions[:,None,:].expand(-1,t,-1).gather(-1,safe)
    keys_prompt = prompt[:,None,:].expand(-1,t,-1).gather(-1,safe)
    distance = positions[:,:,None] - keys_pos
    valid = (indices >= 0)[None] & (indices < t)[None] & (keys_seg == segments[:,:,None])
    visible = (distance >= 0) & (distance < window)
    if prefix:
        visible |= prompt[:,:,None] & keys_prompt & (distance.abs() < window)
    return safe.masked_fill(~(valid & visible),-1)[:,None].to(torch.int32)


@torch.no_grad()
@fp32_math
def select_keys_tiled(q,k,segments,positions,prompt,*,top_k,recent,prefix=False,tile=512):
    b,t,h,d = q.shape
    kv = k.shape[2]
    count = min(top_k,t)
    result = torch.full((b,kv,t,recent+count),-1,device=q.device,dtype=torch.int32)
    rec = local_indices(segments,positions,prompt,recent,prefix=False)
    result[...,:recent] = rec.expand(-1,kv,-1,-1)
    for a in range(0,t,tile):
        z = min(a+tile,t)
        query = q[:,a:z].float().reshape(b,z-a,kv,h//kv,d).permute(0,2,3,1,4)
        best = torch.full((b,kv,z-a,count),-torch.inf,device=q.device)
        best_idx = torch.full_like(best,-1,dtype=torch.long)
        for c in range(0,t,tile):
            e = min(c+tile,t)
            key = k[:,c:e].float().permute(0,2,1,3)[:,:,None]
            scores = (query @ key.transpose(-1,-2)).amax(2)
            distance = torch.arange(a,z,device=q.device)[:,None] - torch.arange(c,e,device=q.device)[None]
            valid = tile_mask(segments,positions,prompt,a,z,c,e,prefix) & ~((distance >= 0) & (distance < recent))[None]
            scores.masked_fill_(~valid[:,None],-torch.inf)
            candidates = torch.cat((best,scores),-1)
            ids = torch.cat((best_idx,torch.arange(c,e,device=q.device).expand(b,kv,z-a,-1)),-1)
            best, order = candidates.topk(count,dim=-1)
            best_idx = ids.gather(-1,order)
        result[...,a:z,recent:] = best_idx.masked_fill(~torch.isfinite(best),-1).to(torch.int32)
    return result


@lru_cache(maxsize=1)
def _compiled_selected_attention():
    from .reference import selected_softmax_attention
    return torch.compile(selected_softmax_attention,fullgraph=True,dynamic=True)


def gathered_attention(q,k,v,indices,*,chunk=256,compiled=False):
    """Checkpoint gathered tiles so backward never retains T×K×D values."""
    from torch.utils.checkpoint import checkpoint
    from .reference import selected_softmax_attention
    operation = _compiled_selected_attention() if compiled and q.is_cuda and torch.is_grad_enabled() else selected_softmax_attention
    outputs = []
    for a in range(0,q.shape[1],chunk):
        query, index = q[:,a:a+chunk], indices[:,:,a:a+chunk]
        if torch.is_grad_enabled() and any(x.requires_grad for x in (q,k,v)):
            outputs.append(checkpoint(operation,query,k,v,index,use_reentrant=False))
        else:
            outputs.append(operation(query,k,v,index))
    return torch.cat(outputs,dim=1)


def document_spans(positions):
    """Resolve packed boundaries once per forward; native adapter may supply them."""
    spans=[]
    for row in positions:
        starts=(row==0).nonzero().flatten().tolist()
        if not starts or starts[0]!=0:
            raise ValueError('Packed rows must start at position zero')
        spans.append(list(zip(starts,starts[1:]+[row.numel()])))
    return spans


def packed_relu_attention(q,k,v,segments,positions,prompt,*,prefix=False,spans=None,tile=512,fused=False,tile_m=16):
    operation=relu_attention
    kwargs={"tile":tile}
    if fused and q.is_cuda:
        from .relu_triton import relu_attention as operation
        kwargs={"tile_m":tile_m}
    spans=document_spans(positions) if spans is None else spans
    rows=[]
    for batch,documents in enumerate(spans):
        chunks=[]
        for a,z in documents:
            chunks.append(operation(q[batch:batch+1,a:z],k[batch:batch+1,a:z],v[batch:batch+1,a:z],
                segments[batch:batch+1,a:z],positions[batch:batch+1,a:z],prompt[batch:batch+1,a:z],prefix=prefix,**kwargs))
        rows.append(torch.cat(chunks,dim=1))
    return torch.cat(rows,dim=0)


@torch.no_grad()
def packed_select_keys(q,k,segments,positions,prompt,*,top_k,recent,prefix=False,spans=None,tile=512,single_topk=False):
    spans=document_spans(positions) if spans is None else spans
    result=torch.full((q.shape[0],k.shape[2],q.shape[1],recent+min(top_k,q.shape[1])),
                      -1,device=q.device,dtype=torch.int32)
    for batch,documents in enumerate(spans):
        for a,z in documents:
            selected=(select_keys_once if single_topk else select_keys_tiled)(q[batch:batch+1,a:z],k[batch:batch+1,a:z],segments[batch:batch+1,a:z],
                positions[batch:batch+1,a:z],prompt[batch:batch+1,a:z],top_k=top_k,recent=recent,prefix=prefix,tile=tile)
            selected=torch.where(selected>=0,selected+a,selected)
            result[batch:batch+1,:,a:z,:selected.shape[-1]]=selected
    return result


@torch.no_grad()
@fp32_math
def select_keys_once(q,k,segments,positions,prompt,*,top_k,recent,prefix=False,tile=512):
    """Bound query tiles, but rank all document keys once instead of merging top-k.

    Same FP32 score calculation and mask as the tiled reference. Score workspace
    is capped at roughly 32M elements by shrinking the query tile for long docs.
    """
    b,t,h,d=q.shape;kv=k.shape[2];count=min(top_k,t)
    tile=min(tile,max(1,32_000_000//(b*h*t)))
    result=torch.full((b,kv,t,recent+count),-1,device=q.device,dtype=torch.int32)
    result[...,:recent]=local_indices(segments,positions,prompt,recent,prefix=False).expand(-1,kv,-1,-1)
    key=k.float().permute(0,2,1,3)[:,:,None]
    for a in range(0,t,tile):
        z=min(a+tile,t)
        query=q[:,a:z].float().reshape(b,z-a,kv,h//kv,d).permute(0,2,3,1,4)
        scores=(query@key.transpose(-1,-2)).amax(2)
        distance=torch.arange(a,z,device=q.device)[:,None]-torch.arange(t,device=q.device)[None]
        valid=tile_mask(segments,positions,prompt,a,z,0,t,prefix)&~((distance>=0)&(distance<recent))[None]
        scores.masked_fill_(~valid[:,None],-torch.inf)
        values,ids=scores.topk(count,dim=-1)
        result[...,a:z,recent:]=ids.masked_fill(~torch.isfinite(values),-1).to(torch.int32)
    return result

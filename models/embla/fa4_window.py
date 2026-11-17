"""FA4 local attention with document isolation and bidirectional prompt windows."""
import torch


def packed_window_attention(q,k,v,positions,prompt,window,*,prefix=False,spans=None):
    from .attention import document_spans
    from flash_attn.cute import flash_attn_func
    if not q.is_cuda:
        raise ValueError('FA4 Embla attention requires CUDA')
    if spans is None:
        spans=document_spans(positions)
    def call(q,k,v,causal):
        out=flash_attn_func(q,k,v,causal=causal,
                           window_size=(window-1,0 if causal else window-1))
        return out[0] if isinstance(out,tuple) else out
    rows=[]
    # Resolve prompt lengths once, outside any attention kernels. All native
    # packed prompts are contiguous prefixes. Reject other layouts explicitly.
    prompt_cpu=prompt.detach().cpu() if prefix else None
    for row,documents in enumerate(spans):
        parts=[]
        for a,z in documents:
            query,key,value=(x[row:row+1,a:z] for x in (q,k,v))
            count=int(prompt_cpu[row,a:z].sum()) if prefix else 0
            if prefix and (not bool(prompt_cpu[row,a:a+count].all()) or bool(prompt_cpu[row,a+count:z].any())):
                raise ValueError('FA4 window requires contiguous prompt prefixes')
            if count==0:
                result=call(query,key,value,True)
            elif count==z-a:
                result=call(query,key,value,False)
            else:
                # FA4 aligns unequal-length Q/K at the right edge: suffix
                # queries retain their original positions in the full KV.
                front=call(query[:,:count],key[:,:count],value[:,:count],False)
                back=call(query[:,count:],key,value,True)
                result=torch.cat((front,back),1)
            parts.append(result)
        rows.append(torch.cat(parts,1))
    return torch.cat(rows,0)


def prepare_window_layout(spans,prompt,*,prefix=False):
    """One host metadata transfer per forward, reusable across all local layers."""
    b,t=prompt.shape
    host=prompt.detach().cpu() if prefix else None
    groups={False:[],True:[]}
    for row,docs in enumerate(spans):
        for a,z in docs:
            count=int(host[row,a:z].sum()) if prefix else 0
            if prefix and (not bool(host[row,a:a+count].all()) or bool(host[row,a+count:z].any())):
                raise ValueError('FA4 window requires contiguous prompt prefixes')
            base=row*t
            if count:groups[False].append((base+a,base+a+count,base+a,base+a+count))
            if a+count<z:groups[True].append((base+a+count,base+z,base+a,base+z))
    plans=[]
    for causal,parts in groups.items():
        if not parts:continue
        qi=[];ki=[];cq=[0];ck=[0];mq=mk=0
        for a,z,c,e in parts:
            qi.extend(range(a,z));ki.extend(range(c,e));cq.append(cq[-1]+z-a);ck.append(ck[-1]+e-c);mq=max(mq,z-a);mk=max(mk,e-c)
        identity=qi==list(range(b*t)) and ki==qi
        plans.append(dict(causal=causal,q=torch.tensor(qi,device=prompt.device,dtype=torch.long),k=torch.tensor(ki,device=prompt.device,dtype=torch.long),
                          cu_q=torch.tensor(cq,device=prompt.device,dtype=torch.int32),cu_k=torch.tensor(ck,device=prompt.device,dtype=torch.int32),max_q=mq,max_k=mk,identity=identity))
    return plans


def batched_window_attention(q,k,v,window,layout):
    from flash_attn.cute import flash_attn_varlen_func
    shape=q.shape;queries=q.reshape(-1,*q.shape[2:]);keys=k.reshape(-1,*k.shape[2:]);values=v.reshape(-1,*v.shape[2:])
    result=torch.zeros_like(queries)
    for plan in layout:
        identity=plan['identity']
        query=queries if identity else queries.index_select(0,plan['q'])
        key=keys if identity else keys.index_select(0,plan['k'])
        value=values if identity else values.index_select(0,plan['k'])
        out=flash_attn_varlen_func(query,key,value,cu_seqlens_q=plan['cu_q'],cu_seqlens_k=plan['cu_k'],max_seqlen_q=plan['max_q'],max_seqlen_k=plan['max_k'],
                                 causal=plan['causal'],window_size=(window-1,0 if plan['causal'] else window-1))
        out=out[0] if isinstance(out,tuple) else out
        result=out if identity else result.index_copy(0,plan['q'],out)
    return result.reshape(shape)

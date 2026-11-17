"""Frozen-prefix MixedLM: bidirectional prompt blocks, causal answer suffix.

Earlier blocks never attend to newer blocks. Full backpropagation through this
forward graph is independent of whether inference retains the earlier KV.
Tool-bearing prompts use an explicit full-refresh policy because flattened
training tokens do not retain every tool-continuation API boundary.
"""
import numpy as np
import torch
from torch import Tensor


def prompt_block_ends(tokens, header, tool_tokens=()):
    tokens=np.asarray(tokens)
    if not len(tokens):raise ValueError('MixedLM requires a nonempty prompt')
    if not header:raise ValueError('Missing assistant-header token pattern')
    if tool_tokens and np.isin(tokens,tool_tokens).any():return [len(tokens)]
    # Boundaries are the ends of complete assistant generation headers. The
    # preceding answer is therefore included in the following extension block.
    candidates=np.flatnonzero(tokens==header[0]);ends=[]
    for i in candidates:
        if i+len(header)<=len(tokens) and np.array_equal(tokens[i:i+len(header)],header):
            ends.append(int(i+len(header)))
    if not ends or ends[-1]!=len(tokens):ends.append(len(tokens))
    return sorted(set(ends))


def routing(prompts, answer_input_lengths, header, tool_tokens=()):
    """Build packed varlen gather routes without any dense attention mask."""
    result={};offset=0;groups={'prefix':([],[],[0],[0]),'answer':([],[],[0],[0])}
    for prompt,answer in zip(prompts,answer_input_lengths,strict=True):
        if answer < 0:
            raise ValueError('Answer input length must be nonnegative')
        n=len(prompt);prev=0
        for end in prompt_block_ends(prompt,header,tool_tokens):
            q,k,cq,ck=groups['prefix'];q.extend(range(offset+prev,offset+end));k.extend(range(offset,offset+end));cq.append(len(q));ck.append(len(k));prev=end
        if answer:
            q,k,cq,ck=groups['answer'];q.extend(range(offset+n,offset+n+answer));k.extend(range(offset,offset+n+answer));cq.append(len(q));ck.append(len(k))
        offset+=n+answer
    for group,(q,k,cq,ck) in groups.items():
        for key,values in [('q',q),('k',k),('cq',cq),('ck',ck)]:
            result[f'mixed_{group}_{key}']=torch.tensor(values,dtype=torch.int64 if key in ('q','k') else torch.int32)
    return result


@torch.compiler.disable
def mixed_attention(q:Tensor,k:Tensor,v:Tensor,**metadata):
    """Two FA4 varlen launches: noncausal prompt blocks and causal answers."""
    output=torch.zeros_like(q)
    for group,causal in [('prefix',False),('answer',True)]:
        qi=metadata[f'mixed_{group}_q'];ki=metadata[f'mixed_{group}_k']
        if qi.numel()==0:continue
        cq=metadata[f'mixed_{group}_cq'];ck=metadata[f'mixed_{group}_ck']
        qg=q[qi];kg=k[ki];vg=v[ki]
        if q.is_cuda:
            from models.flash_attention_prefixlm_fa4 import _fa4_varlen
            values=_fa4_varlen(qg,kg,vg,cu_seqlens_q=cq,cu_seqlens_k=ck,max_seqlen_q=4096,max_seqlen_k=4096,causal=causal)
        else:
            values=[]
            for a,b,c,d in zip(cq[:-1],cq[1:],ck[:-1],ck[1:]):
                qq=qg[a:b].transpose(0,1);kk=kg[c:d].transpose(0,1);vv=vg[c:d].transpose(0,1)
                mask=None
                if causal:
                    mask=torch.arange(d-c)[None,:]<=torch.arange(b-a)[:,None]+(d-c)-(b-a)
                values.append(torch.nn.functional.scaled_dot_product_attention(qq,kk,vv,attn_mask=mask,enable_gqa=True).transpose(0,1))
            values=torch.cat(values)
        output=output.index_copy(0,qi,values)
    return output

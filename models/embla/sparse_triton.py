"""Fused indexed GQA softmax with FP32 accumulation and valid-only KV atomics."""
import torch
import triton as tr
import triton.language as tl

@tr.jit(do_not_specialize=['T', 'S', 'C'])
def _sparse(Q,K,V,I,O,Y,L,T,S,H:tl.constexpr,G:tl.constexpr,D:tl.constexpr,C,BD:tl.constexpr,BH:tl.constexpr,N:tl.constexpr=32):
 t=tl.program_id(0);g=tl.program_id(1);b=tl.program_id(2);h=g*(H//G)+tl.arange(0,BH);d=tl.arange(0,BD)
 q=tl.load(Q+((b*T+t)*H+h[:,None])*D+d[None,:],(h[:,None]<(g+1)*(H//G))&(d[None,:]<D),0).to(tl.float32)
 mx=tl.full((BH,),-float('inf'),tl.float32);den=tl.full((BH,),0,tl.float32);acc=tl.full((BH,BD),0,tl.float32)
 for start in range(tl.cdiv(C,N)):
  c=start*N+tl.arange(0,N);ids=tl.load(I+((b*G+g)*T+t)*C+c,c<C,-1)
  valid=(c<C)&(ids>=0)&(ids<S)
  k=tl.load(K+((b*S+ids[:,None])*G+g)*D+d[None,:],valid[:,None]&(d[None,:]<D),0).to(tl.float32)
  v=tl.load(V+((b*S+ids[:,None])*G+g)*D+d[None,:],valid[:,None]&(d[None,:]<D),0).to(tl.float32)
  scores=tl.where(valid[None,:],tl.dot(q.to(Q.dtype.element_ty),tl.trans(k.to(K.dtype.element_ty)),input_precision='tf32x3')*D**-.5,-float('inf'))
  nextmx=tl.maximum(mx,tl.max(scores,1));safe=tl.where(nextmx==-float('inf'),0,nextmx)
  alpha=tl.exp(mx-safe);p=tl.exp(scores-safe[:,None])
  acc=acc*alpha[:,None]+tl.dot(p,v,input_precision='tf32x3');den=den*alpha+tl.sum(p,1);mx=nextmx
 out=acc/tl.where(den>0,den,1)[:,None];off=((b*T+t)*H+h[:,None])*D+d[None,:];mask=(h[:,None]<(g+1)*(H//G))&(d[None,:]<D)
 tl.store(O+off,out,mask);tl.store(Y+off,out,mask);tl.store(L+(b*T+t)*H+h,tl.where(den>0,mx+tl.log(den),0),h<(g+1)*(H//G))

@tr.jit(do_not_specialize=['T', 'S', 'C'])
def _back(Q,K,V,I,Y,L,DO,DQ,DK,DV,T,S,H:tl.constexpr,G:tl.constexpr,D:tl.constexpr,C,BD:tl.constexpr,BH:tl.constexpr,N:tl.constexpr=32):
 t=tl.program_id(0);g=tl.program_id(1);b=tl.program_id(2);h=g*(H//G)+tl.arange(0,BH);d=tl.arange(0,BD)
 off=((b*T+t)*H+h[:,None])*D+d[None,:];mask=(h[:,None]<(g+1)*(H//G))&(d[None,:]<D)
 q=tl.load(Q+off,mask,0).to(tl.float32);dy=tl.load(DO+off,mask,0).to(tl.float32);y=tl.load(Y+off,mask,0)
 lse=tl.load(L+(b*T+t)*H+h,h<(g+1)*(H//G),0);delta=tl.sum(dy*y,1);dq=tl.full((BH,BD),0,tl.float32)
 for start in range(tl.cdiv(C,N)):
  c=start*N+tl.arange(0,N);ids=tl.load(I+((b*G+g)*T+t)*C+c,c<C,-1);valid=(c<C)&(ids>=0)&(ids<S)
  ko=((b*S+ids[:,None])*G+g)*D+d[None,:];km=valid[:,None]&(d[None,:]<D)
  k=tl.load(K+ko,km,0).to(tl.float32);v=tl.load(V+ko,km,0).to(tl.float32)
  scores=tl.dot(q.to(Q.dtype.element_ty),tl.trans(k.to(K.dtype.element_ty)),input_precision='tf32x3')*D**-.5
  p=tl.where(valid[None,:]&(h[:,None]<(g+1)*(H//G)),tl.exp(scores-lse[:,None]),0)
  ds=p*(tl.dot(dy.to(DO.dtype.element_ty),tl.trans(v.to(V.dtype.element_ty)),input_precision='tf32x3')-delta[:,None])*D**-.5
  dq+=tl.dot(ds,k,input_precision='tf32x3')
  dk=tl.dot(tl.trans(ds),q,input_precision='tf32x3');dv=tl.dot(tl.trans(p),dy,input_precision='tf32x3')
  tl.atomic_add(DK+ko,dk,km,sem='relaxed');tl.atomic_add(DV+ko,dv,km,sem='relaxed')
 tl.store(DQ+off,dq,mask)

class _Sparse(torch.autograd.Function):
 @staticmethod
 def forward(ctx,q,k,v,indices,tile_n):
  q,k,v,indices=[x.contiguous() for x in (q,k,v,indices)]
  b,t,h,d=q.shape;s=k.shape[1];g=k.shape[2];c=indices.shape[-1]
  out=torch.empty_like(q);y=torch.empty_like(q,dtype=torch.float32);lse=torch.empty((b,t,h),device=q.device,dtype=torch.float32)
  _sparse[(t,g,b)](q,k,v,indices,out,y,lse,t,s,h,g,d,c,tr.next_power_of_2(d),max(16,tr.next_power_of_2(h//g)),N=tile_n,num_stages=1)
  ctx.save_for_backward(q,k,v,indices,y,lse);ctx.tile_n=tile_n;return out
 @staticmethod
 def backward(ctx,gradient):
  q,k,v,indices,y,lse=ctx.saved_tensors;b,t,h,d=q.shape;s=k.shape[1];g=k.shape[2];c=indices.shape[-1]
  tile_n=ctx.tile_n
  dq=torch.empty_like(q);dk=torch.zeros_like(k,dtype=torch.float32);dv=torch.zeros_like(v,dtype=torch.float32)
  _back[(t,g,b)](q,k,v,indices,y,lse,gradient.contiguous(),dq,dk,dv,t,s,h,g,d,c,tr.next_power_of_2(d),max(16,tr.next_power_of_2(h//g)),N=tile_n,num_stages=1)
  return dq,dk.to(k.dtype),dv.to(v.dtype),None,None

def sparse_attention(q,k,v,indices,*,tile_n=32):
 if (not q.is_cuda or q.shape[2]%k.shape[2] or k.shape!=v.shape
     or not 32<=q.shape[-1]<=128 or q.shape[2]//k.shape[2]>16):
  raise ValueError('Invalid fused sparse attention inputs')
 return _Sparse.apply(q,k,v,indices,tile_n)

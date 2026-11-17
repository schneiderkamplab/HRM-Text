"""Fused normalized squared-ReLU attention; FP32 accumulators and TF32x3 dots.

No softmax substitution, no repeated KV tensors, and no quadratic saved scores.
Backward owns query or KV tiles, avoiding gradient scatter atomics.
"""
import torch
import triton as tr
import triton.language as tl

@tr.jit(do_not_specialize=['T'])
def _forward(Q,K,V,S,P,R,O,Y,Z,T,H:tl.constexpr,G:tl.constexpr,D:tl.constexpr, PREFIX:tl.constexpr, BD:tl.constexpr, M:tl.constexpr=16,N:tl.constexpr=32):
 m=tl.program_id(0)*M+tl.arange(0,M); head=tl.program_id(1); batch=tl.program_id(2)
 d=tl.arange(0,BD); kv=head//(H//G)
 q=tl.load(Q+((batch*T+m[:,None])*H+head)*D+d[None,:],(m[:,None]<T)&(d[None,:]<D),0).to(tl.float32)
 ps=tl.load(P+batch*T+m,m<T,0); ss=tl.load(S+batch*T+m,m<T,-1); pr=tl.load(R+batch*T+m,m<T,0)
 num=tl.full((M,BD),0,tl.float32); den=tl.full((M,),D**.5,tl.float32)
 for start in range(tl.cdiv(T,N)):
  n=start*N+tl.arange(0,N)
  k=tl.load(K+((batch*T+n[:,None])*G+kv)*D+d[None,:],(n[:,None]<T)&(d[None,:]<D),0).to(tl.float32)
  v=tl.load(V+((batch*T+n[:,None])*G+kv)*D+d[None,:],(n[:,None]<T)&(d[None,:]<D),0).to(tl.float32)
  pn=tl.load(P+batch*T+n,n<T,0); sn=tl.load(S+batch*T+n,n<T,-2); rn=tl.load(R+batch*T+n,n<T,0)
  valid=(m[:,None]<T)&(n[None,:]<T)&(ss[:,None]==sn[None,:])&(ss[:,None]>=0)&((ps[:,None]>=pn[None,:])|(PREFIX&pr[:,None]&rn[None,:]))
  score=tl.maximum(tl.dot(q.to(Q.dtype.element_ty),tl.trans(k.to(K.dtype.element_ty)),input_precision='tf32x3')*(D**-.5),0)
  w=tl.where(valid,score*score,0)
  den+=tl.sum(w,1);num+=tl.dot(w,v,input_precision='tf32x3')
 y=num/den[:,None];offset=((batch*T+m[:,None])*H+head)*D+d[None,:]
 tl.store(O+offset,y,(m[:,None]<T)&(d[None,:]<D));tl.store(Y+offset,y,(m[:,None]<T)&(d[None,:]<D))
 tl.store(Z+(batch*H+head)*T+m,den,m<T)

@tr.jit(do_not_specialize=['T'])
def _dq(Q,K,V,S,P,R,Y,Z,DO,DQ,T,H:tl.constexpr,G:tl.constexpr,D:tl.constexpr,PREFIX:tl.constexpr,BD:tl.constexpr,M:tl.constexpr=16,N:tl.constexpr=32):
 m=tl.program_id(0)*M+tl.arange(0,M);head=tl.program_id(1);batch=tl.program_id(2);d=tl.arange(0,BD);kv=head//(H//G)
 off=((batch*T+m[:,None])*H+head)*D+d[None,:];mask=(m[:,None]<T)&(d[None,:]<D)
 q=tl.load(Q+off,mask,0).to(tl.float32);dy=tl.load(DO+off,mask,0).to(tl.float32);y=tl.load(Y+off,mask,0)
 den=tl.load(Z+(batch*H+head)*T+m,m<T,1);delta=tl.sum(dy*y,1)
 ps=tl.load(P+batch*T+m,m<T,0);ss=tl.load(S+batch*T+m,m<T,-1);pr=tl.load(R+batch*T+m,m<T,0)
 dq=tl.full((M,BD),0,tl.float32)
 for start in range(tl.cdiv(T,N)):
  n=start*N+tl.arange(0,N);offk=((batch*T+n[:,None])*G+kv)*D+d[None,:];maskk=(n[:,None]<T)&(d[None,:]<D)
  k=tl.load(K+offk,maskk,0).to(tl.float32);v=tl.load(V+offk,maskk,0).to(tl.float32)
  pn=tl.load(P+batch*T+n,n<T,0);sn=tl.load(S+batch*T+n,n<T,-2);rn=tl.load(R+batch*T+n,n<T,0)
  valid=(m[:,None]<T)&(n[None,:]<T)&(ss[:,None]==sn[None,:])&(ss[:,None]>=0)&((ps[:,None]>=pn[None,:])|(PREFIX&pr[:,None]&rn[None,:]))
  score=tl.where(valid,tl.maximum(tl.dot(q.to(Q.dtype.element_ty),tl.trans(k.to(K.dtype.element_ty)),input_precision='tf32x3')*(D**-.5),0),0)
  ds=(tl.dot(dy.to(DO.dtype.element_ty),tl.trans(v.to(V.dtype.element_ty)),input_precision='tf32x3')-delta[:,None])/den[:,None]*(2*D**-.5)*score
  dq+=tl.dot(ds,k,input_precision='tf32x3')
 tl.store(DQ+off,dq,mask)

@tr.jit(do_not_specialize=['T'])
def _dkv(Q,K,V,S,P,R,Y,Z,DO,DK,DV,T,H:tl.constexpr,G:tl.constexpr,D:tl.constexpr,PREFIX:tl.constexpr,BD:tl.constexpr,M:tl.constexpr=16,N:tl.constexpr=32):
 n=tl.program_id(0)*N+tl.arange(0,N);head=tl.program_id(1);kv=head//(H//G);batch=tl.program_id(2);d=tl.arange(0,BD)
 offk=((batch*T+n[:,None])*G+kv)*D+d[None,:];maskk=(n[:,None]<T)&(d[None,:]<D)
 k=tl.load(K+offk,maskk,0).to(tl.float32);v=tl.load(V+offk,maskk,0).to(tl.float32)
 pn=tl.load(P+batch*T+n,n<T,0);sn=tl.load(S+batch*T+n,n<T,-2);rn=tl.load(R+batch*T+n,n<T,0)
 dk=tl.full((N,BD),0,tl.float32);dv=tl.full((N,BD),0,tl.float32)
 for g in range(1):
  for start in range(tl.cdiv(T,M)):
   m=start*M+tl.arange(0,M);off=((batch*T+m[:,None])*H+head)*D+d[None,:];mask=(m[:,None]<T)&(d[None,:]<D)
   q=tl.load(Q+off,mask,0).to(tl.float32);dy=tl.load(DO+off,mask,0).to(tl.float32);y=tl.load(Y+off,mask,0)
   den=tl.load(Z+(batch*H+head)*T+m,m<T,1);delta=tl.sum(dy*y,1)
   ps=tl.load(P+batch*T+m,m<T,0);ss=tl.load(S+batch*T+m,m<T,-1);pr=tl.load(R+batch*T+m,m<T,0)
   valid=(m[:,None]<T)&(n[None,:]<T)&(ss[:,None]==sn[None,:])&(ss[:,None]>=0)&((ps[:,None]>=pn[None,:])|(PREFIX&pr[:,None]&rn[None,:]))
   score=tl.where(valid,tl.maximum(tl.dot(q.to(Q.dtype.element_ty),tl.trans(k.to(K.dtype.element_ty)),input_precision='tf32x3')*(D**-.5),0),0)
   ds=(tl.dot(dy.to(DO.dtype.element_ty),tl.trans(v.to(V.dtype.element_ty)),input_precision='tf32x3')-delta[:,None])/den[:,None]*(2*D**-.5)*score
   dk+=tl.dot(tl.trans(ds),q,input_precision='tf32x3');dv+=tl.dot(tl.trans(score*score/den[:,None]),dy,input_precision='tf32x3')
 outoff=((batch*T+n[:,None])*H+head)*D+d[None,:]
 tl.store(DK+outoff,dk,maskk);tl.store(DV+outoff,dv,maskk)

class _Attention(torch.autograd.Function):
 @staticmethod
 def forward(ctx,q,k,v,segments,positions,prompt,prefix,tile_m,tile_n):
  q,k,v,segments,positions,prompt=[x.contiguous() for x in (q,k,v,segments,positions,prompt)]
  b,t,h,d=q.shape;g=k.shape[2]
  out=torch.empty_like(q);y=torch.empty_like(q,dtype=torch.float32);z=torch.empty((b,h,t),device=q.device,dtype=torch.float32)
  _forward[(tr.cdiv(t,tile_m),h,b)](q,k,v,segments,positions,prompt,out,y,z,t,h,g,d,prefix,tr.next_power_of_2(d),M=tile_m,N=tile_n,num_stages=1)
  ctx.save_for_backward(q,k,v,segments,positions,prompt,y,z);ctx.prefix=prefix;ctx.tiles=(tile_m,tile_n)
  return out
 @staticmethod
 def backward(ctx,gradient):
  q,k,v,s,p,r,y,z=ctx.saved_tensors;b,t,h,d=q.shape;g=k.shape[2]
  dq=torch.empty_like(q);dk=torch.empty_like(q,dtype=torch.float32);dv=torch.empty_like(dk);gradient=gradient.contiguous()
  tile_m,tile_n=ctx.tiles
  args=(q,k,v,s,p,r,y,z,gradient)
  _dq[(tr.cdiv(t,tile_m),h,b)](*args,dq,t,h,g,d,ctx.prefix,tr.next_power_of_2(d),M=tile_m,N=tile_n,num_stages=1)
  _dkv[(tr.cdiv(t,tile_n),h,b)](*args,dk,dv,t,h,g,d,ctx.prefix,tr.next_power_of_2(d),M=tile_m,N=tile_n,num_stages=1)
  return dq,dk.reshape(b,t,g,h//g,d).sum(3).to(k.dtype),dv.reshape(b,t,g,h//g,d).sum(3).to(v.dtype),None,None,None,None,None,None

def relu_attention(q,k,v,segments,positions,prompt,*,prefix=False,tile_m=16,tile_n=32):
 if (not q.is_cuda or q.shape[2]%k.shape[2] or k.shape!=v.shape
     or not 32<=q.shape[-1]<=128 or q.shape[2]//k.shape[2]>16):
  raise ValueError('Invalid fused ReLU attention inputs')
 return _Attention.apply(q,k,v,segments,positions,prompt,prefix,tile_m,tile_n)

"""Stack-free residual mixing, preserving the reference matmul rounding points."""
from functools import lru_cache
import torch
from .upstream.modeling_embla import rms_norm


def streaming_residual_mix(lg,vals,queries,eps,x):
    logits=torch.stack(lg,dim=-1).float()
    probabilities=logits.softmax(-1);lse=logits.logsumexp(-1)
    dtype=vals[0].dtype
    for value in vals[1:]:dtype=torch.promote_types(dtype,value.dtype)
    if torch.is_autocast_enabled(vals[0].device.type):dtype=torch.get_autocast_dtype(vals[0].device.type)
    # Reference bmm casts probabilities/values to compute dtype, accumulates in
    # FP32 and rounds its output before the optional partial-block gate.
    weights=probabilities.to(dtype).float()
    mixes=[]
    for j in range(len(queries)):
        value=vals[0].to(dtype).float()*weights[...,j,0,None]
        for n in range(1,len(vals)):
            value=value+vals[n].to(dtype).float()*weights[...,j,n,None]
        mixes.append(value.to(dtype).float())
    if x is None:return mixes
    W=torch.stack(tuple(queries)).float()
    xn=rms_norm(x.float(),eps)
    w=torch.sigmoid(torch.einsum('btd,kd->kbt',xn,W)-lse.permute(2,0,1))
    return [m+w[j].unsqueeze(-1)*(x.float()-m) for j,m in enumerate(mixes)]


@lru_cache(maxsize=1)
def compiled_residual_mix():
    return torch.compile(streaming_residual_mix,fullgraph=True,dynamic=True)

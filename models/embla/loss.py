"""Chunked softcapped CE with bounded FP32 workspace and no head recomputation."""
import torch


class _SoftcappedCE(torch.autograd.Function):
    @staticmethod
    def forward(ctx, logits, labels, cap, chunk):
        ctx.save_for_backward(logits,labels)
        ctx.cap,ctx.chunk=cap,chunk
        loss=torch.zeros((),device=logits.device,dtype=torch.float32)
        predictions=torch.empty_like(labels)
        for start in range(0,labels.numel(),chunk):
            x=logits[start:start+chunk]
            capped=(x/cap).tanh()*cap if cap else x
            y=labels[start:start+chunk]
            loss+=torch.nn.functional.cross_entropy(capped.float(),y,ignore_index=-100,reduction='sum')
            predictions[start:start+chunk]=capped.argmax(-1)
        ctx.mark_non_differentiable(predictions)
        return loss,predictions

    @staticmethod
    def backward(ctx, loss_gradient, prediction_gradient):
        logits,labels=ctx.saved_tensors
        gradient=torch.empty_like(logits)
        for start in range(0,labels.numel(),ctx.chunk):
            x=logits[start:start+ctx.chunk];y=labels[start:start+ctx.chunk]
            tanh=(x/ctx.cap).tanh() if ctx.cap else None
            capped=tanh*ctx.cap if ctx.cap else x
            g=capped.float().softmax(-1)
            valid=y!=-100
            rows=torch.arange(y.numel(),device=y.device)
            g[rows,y.clamp_min(0)]-=valid.to(g.dtype)
            g*=valid[:,None]
            g=(g*loss_gradient).to(logits.dtype)
            if ctx.cap:
                g=torch.ops.aten.tanh_backward(g*ctx.cap,tanh)/ctx.cap
            gradient[start:start+ctx.chunk]=g
        return gradient,None,None,None


def softcapped_cross_entropy(logits,labels,cap,chunk=256):
    return _SoftcappedCE.apply(logits,labels,float(cap or 0),chunk)

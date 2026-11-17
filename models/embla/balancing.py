"""Exact global BF16 margin quantiles for Embla router balancing.

Two 256-bin histogram reductions per layer. No rank-local quantile averaging.
Margins from every microbatch and recurrent invocation share one update.
"""
import torch
import torch.distributed as dist


@torch.no_grad()
def radix_quantile(margins, quantile, *, group=None):
    if margins.ndim != 2 or not 0 <= quantile <= 1:
        raise ValueError('Expected [tokens,experts] margins and a quantile in [0,1]')
    distributed = dist.is_available() and dist.is_initialized()
    values = margins.to(torch.bfloat16).contiguous()
    invalid = (~torch.isfinite(values).all()).to(torch.int32)
    if distributed:
        dist.all_reduce(invalid, op=dist.ReduceOp.MAX, group=group)
    if invalid.item():
        raise ValueError('Router margins must be finite')
    experts = values.shape[1]
    bits = values.view(torch.int16).to(torch.int32) & 65535
    ordered = torch.where(bits & 32768 != 0, (~bits) & 65535, bits ^ 32768)
    high, low = ordered >> 8, ordered & 255
    offsets = torch.arange(experts,device=values.device) * 256
    histogram = torch.bincount((high + offsets).flatten(),minlength=experts*256).reshape(experts,256)
    if distributed:
        dist.all_reduce(histogram,group=group)
    counts = histogram.sum(-1)
    if (counts == 0).any():
        raise ValueError('No global routing tokens')
    rank = torch.floor((counts - 1).double() * quantile).long()
    cumulative = histogram.cumsum(-1)
    high_bin = (cumulative > rank[:,None]).long().argmax(-1)
    preceding = cumulative.gather(1,(high_bin-1).clamp_min(0)[:,None]).squeeze(1)
    preceding = torch.where(high_bin == 0,0,preceding)
    mask = high == high_bin[None]
    low_histogram = torch.bincount((low + offsets)[mask],minlength=experts*256).reshape(experts,256)
    if distributed:
        dist.all_reduce(low_histogram,group=group)
    low_bin = (low_histogram.cumsum(-1) > (rank-preceding)[:,None]).long().argmax(-1)
    selected = (high_bin << 8) | low_bin
    original = torch.where(selected & 32768 != 0,selected ^ 32768,(~selected) & 65535)
    return original.to(torch.int16).view(torch.bfloat16).float()


class RouterBalanceAccumulator:
    """Explicit optimizer-boundary lifecycle; install hooks only during training.

    Stored BF16 margins are transient and must be cleared at each step boundary.
    Checkpoint only after apply/discard; persistent bias belongs to the MoE module.
    """
    def __init__(self, moe):
        self.moe = moe
        self.margins = []
        self.handle = None

    def begin(self):
        if self.handle is not None or self.margins:
            raise RuntimeError('Unfinished router balancing step')
        self.handle = self.moe.register_forward_pre_hook(self._observe)

    @torch.no_grad()
    def _observe(self, module, args):
        if self.moe.top_k == self.moe.num_experts:
            return
        x = args[0].reshape(-1, args[0].shape[-1])
        with torch.autocast(x.device.type, enabled=False):
            scores = torch.nn.functional.linear(x.float(), self.moe.router.weight.float()).sigmoid()
        threshold = (scores + self.moe.expert_bias).topk(self.moe.top_k+1,dim=-1).values[:,-1:]
        self.margins.append((threshold-scores).to(torch.bfloat16))

    def discard(self):
        if self.handle is not None:
            self.handle.remove()
            self.handle = None
        self.margins.clear()

    @torch.no_grad()
    def apply(self, *, group=None):
        if self.handle is None:
            raise RuntimeError('No active router balancing step')
        if self.moe.top_k == self.moe.num_experts:
            self.discard()
            return
        values = torch.cat(self.margins) if self.margins else self.moe.expert_bias.new_empty((0,self.moe.num_experts))
        bias = radix_quantile(values,1-self.moe.top_k/self.moe.num_experts,group=group)
        self.moe.expert_bias.copy_(bias-bias.mean())
        self.discard()

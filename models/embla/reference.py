"""Small eager correctness oracles. Dense attention is not a production kernel."""
import torch
from .attention import fp32_math


def attention_mask(segment, position, prompt, *, prefix=False, window=None):
    """Return [batch, query, key] allowed edges, isolating packed examples."""
    same = segment[:, :, None] == segment[:, None, :]
    distance = position[:, :, None] - position[:, None, :]
    causal = distance >= 0
    prompt_pair = prompt[:, :, None] & prompt[:, None, :]
    allowed = causal | prompt_pair if prefix else causal
    if window is not None:
        local = (distance >= 0) & (distance < window)
        if prefix:
            local = local | (prompt_pair & (distance.abs() < window))
        allowed = allowed & local
    return same & allowed & (segment[:, :, None] >= 0) & (segment[:, None, :] >= 0)


def relu_squared_attention(q, k, v, allowed, *, norm_eps=torch.finfo(torch.float32).eps):
    """Full Embla attention oracle; tensors are [batch, heads, tokens, dim]."""
    def normalize(x):
        x = x.float()
        return x * torch.rsqrt(x.square().mean(-1, keepdim=True) + norm_eps)
    scale = q.shape[-1] ** 0.5
    scores = (normalize(q) @ normalize(k).transpose(-1, -2)) / scale
    weights = scores.relu().square().masked_fill(~allowed[:, None], 0)
    weights = weights / (scale + weights.sum(-1, keepdim=True))
    return (weights @ v.float()).to(v.dtype)


def exact_quantile_bias(scores, bias, top_k):
    """Gathered global-token EQB oracle; caller supplies unbiased routing scores.

    Production must reduce radix histograms, not average rank-local quantiles.
    Bias remains fixed during accumulation and is updated once per optimizer step.
    """
    if scores.ndim != 2 or not 0 < top_k < scores.shape[1]:
        raise ValueError('Expected token/expert scores and 0 < top_k < experts')
    if not scores.shape[0]:
        raise ValueError('No valid routing tokens')
    threshold = (scores.float() + bias.float()).topk(top_k + 1, dim=-1).values[:, -1:]
    margins = threshold - scores.float()
    updated = torch.quantile(margins, 1 - top_k / scores.shape[1], dim=0, interpolation='lower')
    return (updated - updated.mean()).detach()


@torch.no_grad()
def select_sparse_keys(q, k, allowed, *, top_k, recent):
    """Eager oracle on normalized [B,T,H,D]; mask before top-k.

    Recent means preceding positions including self. Bidirectional prompt keys
    outside that band compete in the top-k pool. No duplicate selected keys.
    """
    b, t, h, d = q.shape
    n, kv = k.shape[1:3]
    if h % kv or t != n or top_k < 0 or recent < 0:
        raise ValueError('Expected full-sequence GQA and nonnegative selection sizes')
    grouped = q.float().reshape(b, t, kv, h // kv, d)
    scores = torch.einsum('btghd,bsgd->bgths', grouped, k.float()).amax(3)
    distance = torch.arange(t, device=q.device)[:, None] - torch.arange(n, device=q.device)[None, :]
    recent_mask = (distance >= 0) & (distance < recent)
    candidates = allowed & ~recent_mask
    count = min(top_k, n)
    vals, indices = scores.masked_fill(~candidates[:, None], -torch.inf).topk(count, dim=-1)
    indices = indices.masked_fill(~torch.isfinite(vals), -1)
    rec = torch.arange(t, device=q.device)[:, None] - recent + 1 + torch.arange(recent, device=q.device)
    safe = rec.clamp(0, max(n - 1, 0))
    valid = (rec >= 0)[None] & allowed.gather(-1, safe[None].expand(b, -1, -1))
    rec = rec[None].expand(b, -1, -1).masked_fill(~valid, -1)
    return torch.cat((rec[:, None].expand(-1, kv, -1, -1), indices), -1).to(torch.int32)


@fp32_math
def selected_softmax_attention(q, k, v, indices):
    """Differentiable gathered attention, including zero output for masked rows."""
    b, t, h, d = q.shape
    kv = k.shape[2]
    valid = indices >= 0
    bi = torch.arange(b, device=q.device)[:, None, None, None]
    gi = torch.arange(kv, device=q.device)[None, :, None, None]
    # Masked slots contribute exactly zero, but their gather backward still
    # performs scatter adds. Sending every masked slot to key zero serializes
    # billions of zero-valued atomics on long/packed sequences. Spread those
    # harmless destinations across existing keys; masking semantics stay exact.
    fallback = torch.arange(indices.shape[-1],device=indices.device) % k.shape[1]
    index = torch.where(valid,indices,fallback).long()
    keys = k.float().permute(0, 2, 1, 3)[bi, gi, index]
    values = v.float().permute(0, 2, 1, 3)[bi, gi, index]
    query = q.float().reshape(b, t, kv, h // kv, d).permute(0, 2, 1, 3, 4)
    scores = torch.einsum('bgthd,bgtsd->bgths', query, keys) / d ** .5
    scores = scores.masked_fill(~valid[..., None, :], -torch.inf)
    any_valid = valid.any(-1)[..., None, None]
    probabilities = torch.softmax(torch.where(any_valid, scores, 0), -1)
    probabilities = probabilities.masked_fill(~valid[..., None, :], 0)
    out = torch.einsum('bgths,bgtsd->bgthd', probabilities, values)
    return out.permute(0, 2, 1, 3, 4).reshape(b, t, h, d).to(q.dtype)

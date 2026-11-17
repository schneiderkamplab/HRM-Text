"""Embla 1 as Hugging Face remote code: ``AutoModelForCausalLM.from_pretrained(dir, trust_remote_code=True)``
with nothing but torch, transformers and safetensors installed.

This is the eager torch path of the training code's model under the released config
(``configuration_embla.py``), transcribed into one file: the same math, the same logits (held to the training
code's by its export test). What training runs on GPU kernels (ReLU² attention and key
selection, FlashAttention-4's window, QuACK's grouped GEMMs, the fused AttnRes merge) runs here as the torch
reference ops those kernels are tested against. Training machinery is left out (no gradient checkpointing, no
context or expert parallelism, no MoE balancing statistics).

The model, briefly. Layers are ``sliding_attention`` (softmax GQA, partial RoPE, a left window), ``full_attention``
(ReLU² GQA, no position encoding, causal; its K/V projected from the normed input of layer ``kv_sources[i]``) or
``sparse_attention`` (no K/V of its own: its block's full layer's K/V, per query the ``sparse_topk`` keys that full
layer scores highest plus the ``sparse_recent`` latest, softmax). ReLU² attention is ``relu(q̂·k̂/√D)²`` over
``√D + Σ``. The MLP is a shared + routed ReLU² MoE (sigmoid router, top-k on score + bias, gates renormalised), or a
dense ReLU² MLP (``mlp_layer_types`` dense). An engram (hashed n-grams from a large row table, gated by the hidden
state, a dilated causal conv) reads after layer ``engram_layer``. The residual stream is Block Attention Residuals:
every sub-layer input is a softmax mix of the token embedding, the engram read and the completed blocks under its
own pseudo-query. Logits are softcapped.

Weights: the training code's names. The routed experts of a layer are two stacked parameters, ``mlp.experts_fc [E, f, d]`` and
``mlp.experts_proj [E, d, f]``, as training holds them (the training code registers a checkpoint conversion for this class name
that merges per-expert tensors into those stacks; keys that are stacks already pass through it unchanged). The engram table is ``engram_table.safetensors`` next to the weights, read in
bf16 and kept in host memory: ``model.to("cuda")`` leaves it there, and each forward gathers its rows.

With ``embla_q4`` in the config (a Q4 export packed with ``--packed-q4``) the tensors the
phone quantizes are stored as the phone stores them: 4-bit codes, two per byte (``<name>.q4``, uint8; the even
column in the low nibble), and a bf16 scale and bias per group of 64 along the input axis (``<name>.scales`` /
``<name>.biases``); the engram table's rows the same with fp16 scale / bias. They dequantize to
``bf16(q · scale + bias)`` (fp32 math, one rounding), the Q4 export's bf16 values bit for bit.

Generation keeps a cache (:class:`EmblaCache`): the sliding layers' last ``sliding_window - 1`` keys, the full
layers' K/V (the sparse layers read those), the engram's token and conv history. A prompt runs the prefill half for
every token and the decode half for the last one only (the decode half's K/V depend on prefill-half states alone),
which is also what any forward with ``logits_to_keep=1`` does. The attention is the torch reference (scores
``[heads, queries, keys]`` in fp32). No padding: one prompt per call, or rows of equal length.
"""
from __future__ import annotations

import math
import shutil
from pathlib import Path

import torch
import torch.nn.functional as F
from torch import nn
from transformers import GenerationMixin, PreTrainedModel
from transformers import initialization as init
from transformers.modeling_outputs import CausalLMOutputWithPast

from .configuration_embla import LAYER_FULL, LAYER_SLIDING, LAYER_SPARSE, MLP_SPARSE, EmblaConfig

TABLE_FILE = "engram_table.safetensors"
EPS32 = float(torch.finfo(torch.float32).eps)


# =============================================================================== helpers
def rms_norm(x: torch.Tensor, eps: float) -> torch.Tensor:
    return F.rms_norm(x, (x.size(-1),), eps=eps)


def rms_norm_fp32(x: torch.Tensor) -> torch.Tensor:
    """The parameter-free q / k norm (``use_qk_norm: false``): fp32 math, the input dtype out."""
    return F.rms_norm(x.float(), (x.shape[-1],), eps=EPS32).to(x.dtype)


def relu2(x: torch.Tensor) -> torch.Tensor:
    return F.relu(x).square()


def _compute_dtype(x: torch.Tensor) -> torch.dtype:
    if torch.is_autocast_enabled(x.device.type):
        return torch.get_autocast_dtype(x.device.type)
    return x.dtype


def _to_act(t: torch.Tensor, w: torch.Tensor) -> torch.Tensor:
    return t if torch.is_autocast_enabled(t.device.type) else t.to(w.dtype)


def _store_dtype(t: torch.Tensor, w: torch.Tensor) -> torch.dtype:
    dev = t.device.type
    return torch.get_autocast_dtype(dev) if torch.is_autocast_enabled(dev) else w.dtype


class Packing:
    """Document boundaries of a ``[B, T]`` batch from ``position_ids`` (0 at each document start)."""

    def __init__(self, position_ids: torch.Tensor) -> None:
        B, T = position_ids.shape
        starts = position_ids == 0
        self.starts = torch.cat([torch.ones_like(starts[:, :1]), starts[:, 1:]], dim=1)
        self.seq_idx = (self.starts.reshape(-1).to(torch.int32).cumsum(0) - 1).reshape(B, T)
        self.position_ids = position_ids


# =============================================================================== packed 4-bit weights (embla_q4)
def pack4(codes: torch.Tensor) -> torch.Tensor:
    """Integer codes 0..15 ``[..., n]`` -> ``[..., n / 2]`` uint8, column ``2j`` in the low nibble, ``2j + 1`` high."""
    c = codes.to(torch.uint8).reshape(*codes.shape[:-1], -1, 2)
    return c[..., 0] | (c[..., 1] << 4)


def unpack4(q4: torch.Tensor) -> torch.Tensor:
    """:func:`pack4`'s inverse: ``[..., n / 2]`` uint8 -> codes ``[..., n]`` uint8."""
    return torch.stack([q4 & 0x0F, q4 >> 4], dim=-1).reshape(*q4.shape[:-1], q4.shape[-1] * 2)


def dequant4(q4: torch.Tensor, scales: torch.Tensor, biases: torch.Tensor, group: int = 64) -> torch.Tensor:
    """``bf16(q · scale + bias)`` per group of ``group`` along the last axis, the products and sums in fp32:
    ``q4 [..., n / 2]``, ``scales`` / ``biases [..., n / group]`` -> ``[..., n]`` bf16."""
    codes = unpack4(q4).float()
    g = codes.reshape(*codes.shape[:-1], codes.shape[-1] // group, group)
    w = g * scales.float().unsqueeze(-1) + biases.float().unsqueeze(-1)
    return w.reshape(codes.shape).to(torch.bfloat16)


class _Q4(nn.Module):
    """A packed 4-bit weight ``[..., cols]``: ``q4`` (uint8) and per-group ``scales`` / ``biases`` (in the default
    dtype, so ``from_pretrained(dtype=...)`` moves them like any float tensor: bf16 / fp32 hold the stored bf16 values
    exactly; fp16 does not and is refused). ``weight``: the dequantized tensor, kept while no gradient is recorded."""

    def __init__(self, shape: tuple[int, ...], group: int) -> None:
        super().__init__()
        *lead, cols = shape
        if cols % group or cols % 2:
            raise ValueError(f"packed 4-bit weight: {cols} columns, not a multiple of the group {group}")
        self.group = int(group)
        self.register_buffer("q4", torch.zeros(*lead, cols // 2, dtype=torch.uint8))
        self.register_buffer("scales", torch.zeros(*lead, cols // group))
        self.register_buffer("biases", torch.zeros(*lead, cols // group))
        self._cache: torch.Tensor | None = None

    def _dtype(self) -> torch.dtype:
        dt = self.scales.dtype
        if dt not in (torch.bfloat16, torch.float32, torch.float64):
            raise ValueError(f"packed 4-bit weights need bf16 or fp32 scales, got {dt}: load the model with "
                             "dtype=torch.bfloat16 (or torch.float32)")
        return dt

    @property
    def weight(self) -> torch.Tensor:
        dt = self._dtype()
        c = self._cache
        if c is not None and c.device == self.q4.device and c.dtype == dt:
            return c
        w = dequant4(self.q4, self.scales, self.biases, self.group).to(dt)
        self._cache = None if torch.is_grad_enabled() else w
        return w

    def _apply(self, fn, *args, **kwargs):
        self._cache = None                       # .to() / .cuda(): rebuilt on the next use
        return super()._apply(fn, *args, **kwargs)


class Q4Linear(_Q4):
    """``nn.Linear`` over a packed 4-bit weight ``[out, in]``."""

    def __init__(self, in_features: int, out_features: int, bias: bool = False, group: int = 64) -> None:
        super().__init__((out_features, in_features), group)
        self.in_features, self.out_features = in_features, out_features
        self.bias = nn.Parameter(torch.zeros(out_features)) if bias else None

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.linear(x, self.weight, self.bias)


class Q4Embedding(_Q4):
    """``nn.Embedding`` over a packed 4-bit table ``[num, dim]``: a lookup dequantizes only the rows it reads."""

    def __init__(self, num_embeddings: int, embedding_dim: int, group: int = 64) -> None:
        super().__init__((num_embeddings, embedding_dim), group)
        self.num_embeddings, self.embedding_dim = num_embeddings, embedding_dim

    def forward(self, ids: torch.Tensor) -> torch.Tensor:
        return dequant4(self.q4[ids], self.scales[ids], self.biases[ids], self.group).to(self._dtype())


class Q4ExpertStack(_Q4):
    """The routed experts' packed 4-bit weights of one projection, ``[E, out, in]`` dequantized."""

    def __init__(self, E: int, out_features: int, in_features: int, group: int = 64) -> None:
        super().__init__((E, out_features, in_features), group)


def _q4_group(config) -> int | None:
    q = getattr(config, "embla_q4", None)
    return int(q.get("group_size", 64)) if q else None


def make_linear(config, in_features: int, out_features: int, bias: bool = False) -> nn.Module:
    """A projection the phone quantizes: packed under ``embla_q4``, else ``nn.Linear``."""
    g = _q4_group(config)
    return nn.Linear(in_features, out_features, bias=bias) if g is None else Q4Linear(in_features, out_features, bias, g)


def make_experts(config, E: int, out_features: int, in_features: int) -> nn.Parameter | nn.Module:
    """The routed experts' weights of one projection ``[E, out, in]``: a parameter, or packed under ``embla_q4``."""
    g = _q4_group(config)
    return (nn.Parameter(torch.empty(E, out_features, in_features)) if g is None
            else Q4ExpertStack(E, out_features, in_features, g))


def _stack(w: nn.Parameter | nn.Module) -> torch.Tensor:
    return w if isinstance(w, torch.Tensor) else w.weight


# =============================================================================== cache
class EmblaCache:
    """What generation keeps between forwards: per sliding layer its last ``sliding_window - 1`` keys (normed and
    rotated) and values; per full layer its raw K, its normed K and V at every position (the sparse layers of its
    block read them); the engram's last tokens and its conv's input history. Rows are the batch."""

    def __init__(self) -> None:
        self.seen = 0
        self.sliding: dict[int, tuple[torch.Tensor, torch.Tensor]] = {}
        self.full: dict[int, tuple[torch.Tensor, torch.Tensor, torch.Tensor]] = {}
        self.engram_ids: torch.Tensor | None = None
        self.engram_conv: torch.Tensor | None = None

    def get_seq_length(self, layer_idx: int = 0) -> int:
        return self.seen

    def _map(self, fn) -> None:
        self.sliding = {i: tuple(fn(t) for t in v) for i, v in self.sliding.items()}
        self.full = {i: tuple(fn(t) for t in v) for i, v in self.full.items()}
        self.engram_ids = None if self.engram_ids is None else fn(self.engram_ids)
        self.engram_conv = None if self.engram_conv is None else fn(self.engram_conv)

    def reorder_cache(self, beam_idx: torch.LongTensor) -> None:
        self._map(lambda t: t.index_select(0, beam_idx.to(t.device)))

    def batch_repeat_interleave(self, repeats: int) -> None:
        self._map(lambda t: t.repeat_interleave(repeats, dim=0))

    def batch_select_indices(self, indices: torch.Tensor) -> None:
        self._map(lambda t: t[indices])


def _cat(old: torch.Tensor | None, new: torch.Tensor) -> torch.Tensor:
    return new if old is None else torch.cat([old, new], dim=1)


# =============================================================================== attention ops (the training code's references)
# Queries are always the last Tq of the Tk keys (the keys before them come from the cache): query i sits at key
# position Tk - Tq + i.
def partial_rope(x: torch.Tensor, dims: int, theta: float, positions: torch.Tensor) -> torch.Tensor:
    """Half-split rotation of the first ``dims`` dims of ``x [B, T, H, D]`` at ``positions`` (``[T]`` or ``[B, T]``)."""
    if dims <= 0:
        return x
    inv_freq = 1.0 / (theta ** (torch.arange(0, dims, 2, dtype=torch.float32, device=x.device) / dims))
    freqs = positions.to(device=x.device, dtype=torch.float32)[..., None] * inv_freq
    if freqs.dim() == 2:
        freqs = freqs[None]
    cos, sin = freqs.cos().to(x.dtype)[:, :, None, :], freqs.sin().to(x.dtype)[:, :, None, :]
    r, rest = x[..., :dims], x[..., dims:]
    d = dims // 2
    x1, x2 = r[..., :d], r[..., d:]
    return torch.cat([x1 * cos + x2 * sin, x1 * (-sin) + x2 * cos, rest], dim=-1)


def relu2_attention(q: torch.Tensor, k: torch.Tensor, v: torch.Tensor, packing: Packing | None = None) -> torch.Tensor:
    """Causal ReLU² attention, ``q [B, Tq, H, D]``, ``k / v [B, Tk, Hkv, D]`` (q / k normed) -> ``[B, Tq, H·D]``:
    ``relu(q·k/√D)²`` over ``√D + Σ``, fp32 math."""
    B, Tq, H, D = q.shape
    Tk = k.shape[1]
    q, k, v_in = q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2)
    v = v_in
    n_rep = H // k.shape[1]
    if n_rep > 1:
        k = k.repeat_interleave(n_rep, dim=1)
        v = v.repeat_interleave(n_rep, dim=1)
    att = torch.clamp(torch.matmul(q.float(), k.float().transpose(-1, -2)) / math.sqrt(D), min=0.0).pow(2)
    allowed = (Tk - Tq + torch.arange(Tq, device=q.device))[:, None] >= torch.arange(Tk, device=q.device)[None, :]
    if packing is not None:
        seq_idx = packing.seq_idx
        allowed = allowed[None, None] & (seq_idx[:, None, :, None] == seq_idx[:, None, None, :])
    att = att * allowed.to(att.dtype)
    out = (torch.matmul(att, v.float()) / (math.sqrt(D) + att.sum(dim=-1, keepdim=True))).to(v_in.dtype)
    return out.transpose(1, 2).contiguous().reshape(B, Tq, -1)


def softmax_window(q: torch.Tensor, k: torch.Tensor, v: torch.Tensor, window: int,
                   position_ids: torch.Tensor | None = None) -> torch.Tensor:
    """Softmax at 1/√D over a left window of ``window`` keys (the query included), ``q [B, Tq, H, D]`` /
    ``k, v [B, Tk, Hkv, D]`` -> ``[B, Tq, H, D]``, fp32 math. ``position_ids``: packed documents (Tq = Tk)."""
    B, Tq, H, D = q.shape
    Tk = k.shape[1]
    G = H // k.shape[2]
    qf = q.float().transpose(1, 2)
    kf = k.float().transpose(1, 2).repeat_interleave(G, dim=1)
    vf = v.float().transpose(1, 2).repeat_interleave(G, dim=1)
    s = qf @ kf.transpose(-1, -2) / math.sqrt(D)
    j = torch.arange(Tk, device=q.device)
    dist = (Tk - Tq + torch.arange(Tq, device=q.device))[:, None] - j[None, :]
    keep = (dist >= 0) & (dist < window)
    if position_ids is not None:
        start = j[None, :] - position_ids.to(q.device)
        keep = (keep[None] & (j[None, None, :] >= start[:, :, None]))[:, None]
    s = s.masked_fill(~keep, float("-inf"))
    y = torch.softmax(s, -1) @ vf
    return y.transpose(1, 2).to(q.dtype)


@torch.no_grad()
def select_keys(qn: torch.Tensor, kn: torch.Tensor, topk: int, recent: int, chunk: int = 512,
                position_ids: torch.Tensor | None = None) -> torch.Tensor:
    """The sparse layers' key lists from the full layer's normed ``q [B, Tq, H, D]`` / ``k [B, Tk, Hkv, D]`` -> int32
    ``[B, Hkv, Tq, recent + min(topk, Tk)]``: the recent keys, then the top keys among the older ones by the
    max-over-heads score (``-1`` for an empty slot)."""
    B, Tq, H, D = qn.shape
    Tk, Hkv = kn.shape[1], kn.shape[2]
    G = H // Hkv
    kk = min(topk, Tk)
    qv = qn.view(B, Tq, Hkv, G, D).permute(0, 2, 3, 1, 4)
    kv = kn.permute(0, 2, 1, 3).unsqueeze(2)
    j = torch.arange(Tk, device=qn.device)
    tq = Tk - Tq + torch.arange(Tq, device=qn.device)
    start = None if position_ids is None else (tq[None, :] - position_ids.to(qn.device))[:, None, :, None]
    out = torch.empty(B, Hkv, Tq, recent + kk, dtype=torch.int32, device=qn.device)
    for c0 in range(0, Tq, chunk):
        c1 = min(Tq, c0 + chunk)
        t = tq[c0:c1]
        e = int(t[-1]) + 1                                  # the keys up to the chunk's last query
        s = torch.matmul(qv[:, :, :, c0:c1], kv[:, :, :, :e].transpose(-1, -2)).amax(dim=2)
        cand = j[None, :e] <= (t[:, None] - recent)
        if start is not None:
            cand = cand & (j[None, :e] >= start[:, :, c0:c1])
        s = s.masked_fill(~cand, float("-inf"))
        kc = min(kk, e)
        vals, ind = s.topk(kc, dim=-1, sorted=False)
        ind = torch.where(torch.isinf(vals), -1, ind)
        rec = t[:, None] - recent + 1 + torch.arange(recent, device=qn.device)[None, :]
        floor = 0 if start is None else start[:, :, c0:c1]
        rec = torch.where(rec >= floor, rec, -1).expand(B, Hkv, c1 - c0, recent)
        out[:, :, c0:c1, :recent] = rec.to(torch.int32)
        out[:, :, c0:c1, recent:recent + kc] = ind.to(torch.int32)
        out[:, :, c0:c1, recent + kc:] = -1
    return out


def sparse_attention(q: torch.Tensor, k: torch.Tensor, v: torch.Tensor, idx: torch.Tensor,
                     chunk: int = 1024) -> torch.Tensor:
    """Softmax attention over each query's listed keys: q ``[B, Tq, H, D]`` / k, v ``[B, Tk, Hkv, D]`` (q / k
    normed), ``idx [B, Hkv, Tq, KS]`` -> ``[B, Tq, H, D]`` in q's dtype, fp32 math, queries in chunks of ``chunk``."""
    Tq = q.shape[1]
    if Tq > chunk:
        return torch.cat([sparse_attention(q[:, a:a + chunk], k, v, idx[:, :, a:a + chunk], chunk)
                          for a in range(0, Tq, chunk)], dim=1)
    B, Tq, H, D = q.shape
    Hkv = k.shape[2]
    G = H // Hkv
    valid = idx >= 0
    ii = idx.clamp_min(0).long()
    bi = torch.arange(B, device=q.device)[:, None, None, None]
    gi = torch.arange(Hkv, device=q.device)[None, :, None, None]
    kg = k.permute(0, 2, 1, 3)[bi, gi, ii].float()
    vg = v.permute(0, 2, 1, 3)[bi, gi, ii].float()
    qg = q.view(B, Tq, Hkv, G, D).permute(0, 2, 1, 3, 4).float()
    s = torch.einsum("bgthd,bgtkd->bgthk", qg, kg) / math.sqrt(D)
    p = torch.softmax(s.masked_fill(~valid[:, :, :, None, :], float("-inf")), -1)
    y = torch.einsum("bgthk,bgtkd->bgthd", p, vg)
    return y.permute(0, 2, 1, 3, 4).reshape(B, Tq, H, D).to(q.dtype)


class QKRMSNorm(nn.Module):
    """``use_qk_norm``: RMS norm over head_dim with gains ``1 + weight``, fp32 math."""

    def __init__(self, dim: int) -> None:
        super().__init__()
        self.normalized_shape = (int(dim),)
        self.weight = nn.Parameter(torch.zeros(dim))

    def fp32(self, x: torch.Tensor) -> torch.Tensor:
        return F.rms_norm(x.float(), self.normalized_shape, 1.0 + self.weight.float(), EPS32)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fp32(x).to(x.dtype)


class _Attention(nn.Module):
    def __init__(self, config: EmblaConfig, layer_idx: int, kv: bool) -> None:
        super().__init__()
        self.layer_idx = layer_idx
        H, Hkv, self.rope_dims, self.rope_theta, self.window_size = config.attn_spec(layer_idx)
        self.num_heads, self.num_key_value_heads, self.head_dim = H, Hkv, config.head_dim
        C, D = config.hidden_size, config.head_dim
        self.c_q = make_linear(config, C, H * D)
        if kv:
            self.c_k = make_linear(config, C, Hkv * D)
            self.c_v = make_linear(config, C, Hkv * D)
        self.c_proj = make_linear(config, H * D, C)
        self.learned_norm = bool(config.use_qk_norm)
        if self.learned_norm:
            self.q_norm = QKRMSNorm(D)
            self.k_norm = QKRMSNorm(D)

    def _heads(self, lin: nn.Module, x: torch.Tensor, n: int) -> torch.Tensor:
        B, T, _ = x.shape
        return lin(x).view(B, T, n, self.head_dim)

    def norm_q(self, q: torch.Tensor) -> torch.Tensor:
        return self.q_norm(q) if self.learned_norm else rms_norm_fp32(q)

    def norm_k(self, k: torch.Tensor) -> torch.Tensor:
        return self.k_norm(k) if self.learned_norm else rms_norm_fp32(k)


class SlidingAttention(_Attention):
    """GQA, RoPE on the first ``rope_dims`` dims of q̂ / k̂ (normed first), softmax over a left window."""

    def __init__(self, config: EmblaConfig, layer_idx: int) -> None:
        super().__init__(config, layer_idx, kv=True)

    def _norm_rope(self, x: torch.Tensor, norm: QKRMSNorm | None, positions: torch.Tensor) -> torch.Tensor:
        xf = norm.fp32(x) if norm is not None else F.rms_norm(x.float(), (x.shape[-1],), eps=EPS32)
        return partial_rope(xf, self.rope_dims, self.rope_theta, positions).to(x.dtype)

    def forward(self, x: torch.Tensor, positions: torch.Tensor, packing: Packing | None = None,
                cache: EmblaCache | None = None) -> torch.Tensor:
        B, T, _ = x.shape
        q = self._heads(self.c_q, x, self.num_heads)
        k = self._heads(self.c_k, x, self.num_key_value_heads)
        v = self._heads(self.c_v, x, self.num_key_value_heads)
        qn, kn = (self.q_norm, self.k_norm) if self.learned_norm else (None, None)
        qr, kr = self._norm_rope(q, qn, positions), self._norm_rope(k, kn, positions)
        if cache is not None:
            old = cache.sliding.get(self.layer_idx)
            kr, v = (kr, v) if old is None else (torch.cat([old[0], kr], 1), torch.cat([old[1], v], 1))
            keep = self.window_size - 1
            cache.sliding[self.layer_idx] = (kr[:, -keep:], v[:, -keep:]) if keep > 0 else (kr[:, :0], v[:, :0])
        y = softmax_window(qr, kr, v, self.window_size, None if packing is None else packing.position_ids)
        return self.c_proj(y.reshape(B, T, -1))


class FullAttention(_Attention):
    """GQA, no position encoding, causal ReLU². q from ``x`` (this layer's input), K/V from ``src`` (the normed input
    of layer ``kv_sources[i]``; it may hold more positions than ``x``, the queries being its last ones). -> the
    output, and the raw K, normed K and V at every position (the cache's, with ``cache``) and q̂ for the key
    selection."""

    def __init__(self, config: EmblaConfig, layer_idx: int) -> None:
        super().__init__(config, layer_idx, kv=True)

    def forward(self, x: torch.Tensor, src: torch.Tensor, packing: Packing | None = None,
                cache: EmblaCache | None = None):
        q = self._heads(self.c_q, x, self.num_heads)
        k = self._heads(self.c_k, src, self.num_key_value_heads)
        v = self._heads(self.c_v, src, self.num_key_value_heads)
        qn, kn = self.norm_q(q), self.norm_k(k)
        if cache is not None:
            old = cache.full.get(self.layer_idx)
            if old is not None:
                k, kn, v = torch.cat([old[0], k], 1), torch.cat([old[1], kn], 1), torch.cat([old[2], v], 1)
            cache.full[self.layer_idx] = (k, kn, v)
        out = relu2_attention(qn, kn, v, packing)
        return self.c_proj(out), k, kn, v, qn


class SparseAttention(_Attention):
    """No K/V of its own: its block's full layer's (raw K normed by this layer's k norm), per query the keys that
    layer selected."""

    def __init__(self, config: EmblaConfig, layer_idx: int) -> None:
        super().__init__(config, layer_idx, kv=False)

    def forward(self, x: torch.Tensor, k: torch.Tensor, v: torch.Tensor, idx: torch.Tensor) -> torch.Tensor:
        B, T, _ = x.shape
        q = self._heads(self.c_q, x, self.num_heads)
        out = sparse_attention(self.norm_q(q), self.norm_k(k), v, idx)
        return self.c_proj(out.reshape(B, T, -1))


# =============================================================================== MLPs
class DenseMLP(nn.Module):
    def __init__(self, config: EmblaConfig) -> None:
        super().__init__()
        self.c_fc = make_linear(config, config.hidden_size, config.intermediate_size)
        self.c_proj = make_linear(config, config.intermediate_size, config.hidden_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.c_proj(relu2(self.c_fc(x)))


class MoE(nn.Module):
    """Shared ReLU² expert + ``E`` routed ReLU² experts (``proj(relu(fc(x))²)``), top-k on ``sigmoid(router) +
    expert_bias``, the chosen experts' sigmoid scores renormalised as gates."""

    def __init__(self, config: EmblaConfig) -> None:
        super().__init__()
        E, f, fs, d = config.num_experts, config.moe_intermediate_size, config.shared_expert_intermediate_size, \
            config.hidden_size
        self.num_experts, self.top_k = E, config.num_experts_per_tok
        self.shared_fc = make_linear(config, d, fs)
        self.shared_proj = make_linear(config, fs, d)
        self.router = nn.Linear(d, E, bias=False)
        self.register_buffer("expert_bias", torch.zeros(E), persistent=True)
        self.experts_fc = make_experts(config, E, f, d)
        self.experts_proj = make_experts(config, E, d, f)

    def route(self, x2: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        with torch.autocast(device_type=x2.device.type, enabled=False):
            scores = torch.sigmoid(F.linear(x2.float(), self.router.weight.float()))
        topk_idx = torch.topk(scores.detach() + self.expert_bias, self.top_k, dim=-1).indices
        gates = scores.gather(-1, topk_idx)
        return topk_idx, gates / gates.sum(-1, keepdim=True).clamp_min(1e-9)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, T, d = x.shape
        x2 = x.reshape(-1, d)
        N, k, E = x2.size(0), self.top_k, self.num_experts
        dtype = _compute_dtype(x2)
        shared = self.shared_proj(relu2(self.shared_fc(x2)))
        topk_idx, gates = self.route(x2)
        flat = topk_idx.reshape(-1)
        counts = torch.zeros(E, dtype=torch.int32, device=x.device).scatter_add_(
            0, flat, torch.ones_like(flat, dtype=torch.int32))
        order = torch.argsort(flat, stable=True)
        tok = order // k
        offs = counts.cumsum(0).to(torch.int32)
        xs = x2.to(dtype).index_select(0, tok)
        w1, w2 = _stack(self.experts_fc), _stack(self.experts_proj)          # [E, f, d], [E, d, f]
        if xs.is_cuda and dtype in (torch.bfloat16, torch.float16) and hasattr(torch, "_grouped_mm"):
            h = relu2(torch._grouped_mm(xs, w1.to(dtype).transpose(1, 2), offs=offs)).to(dtype)
            ys = torch._grouped_mm(h, w2.to(dtype).transpose(1, 2), offs=offs)
        else:
            ys = torch.empty(xs.size(0), d, dtype=xs.dtype, device=xs.device)
            start = 0
            for e, end in enumerate(offs.tolist()):
                if end > start:
                    ys[start:end] = relu2(xs[start:end] @ w1[e].to(dtype).t()) @ w2[e].to(dtype).t()
                start = end
        w = gates.reshape(-1).index_select(0, order).to(ys.dtype).unsqueeze(-1)
        if ys.is_cuda:
            # each token's k slots gathered back into routing order and summed: deterministic, where CUDA's
            # index_add_ adds them in an order that changes from run to run
            inv = torch.empty_like(order)
            inv[order] = torch.arange(order.numel(), device=order.device)
            routed = (ys * w).index_select(0, inv).view(N, k, d).sum(1)
        else:
            routed = torch.zeros(N, d, dtype=ys.dtype, device=x.device).index_add_(0, tok, ys * w)
        return (shared.to(routed.dtype) + routed).reshape(B, T, d)


# =============================================================================== engram
_MASK64 = (1 << 64) - 1


def _s64(x: int) -> int:
    x &= _MASK64
    return x - (1 << 64) if x >= 1 << 63 else x


K1, K2, K3 = _s64(0x9E3779B97F4A7C15), _s64(0xBF58476D1CE4E5B9), _s64(0x94D049BB133111EB)
SEED, SLOT_SALT = _s64(0x6A09E667F3BCC909), _s64(0xD6E8FEB86659FD93)


def _lsr(h: torch.Tensor, s: int) -> torch.Tensor:
    return (h >> s) & ((1 << (64 - s)) - 1)


def _finalize(h: torch.Tensor) -> torch.Tensor:
    h = (h ^ _lsr(h, 30)) * K2
    h = (h ^ _lsr(h, 27)) * K3
    return h ^ _lsr(h, 31)


def lagged_tokens(tok: torch.Tensor, max_lag: int, pad_id: int,
                  position_ids: torch.Tensor | None = None) -> list[torch.Tensor]:
    """``x_L[..., t] = tok[..., t - L]``, or ``pad_id`` before the row's (or the document's) start."""
    tok = tok.long()
    T = tok.shape[-1]
    padded = torch.cat([torch.full(tok.shape[:-1] + (max_lag,), int(pad_id), dtype=torch.long, device=tok.device),
                        tok], dim=-1)
    out = []
    for L in range(max_lag + 1):
        x = padded[..., max_lag - L: max_lag - L + T]
        if position_ids is not None and L:
            x = torch.where(position_ids >= L, x, int(pad_id))
        out.append(x)
    return out


def ngram_hashes(tok: torch.Tensor, max_order: int, pad_id: int,
                 position_ids: torch.Tensor | None = None) -> list[torch.Tensor]:
    """``H_n[..., t]``: the 64-bit hash of the n-gram ending at ``t`` (padded before the document start)."""
    lags = lagged_tokens(tok, max_order - 1, pad_id, position_ids)
    out = []
    for n in range(1, max_order + 1):
        r = torch.full_like(lags[0], SEED)
        for L in range(n - 1, -1, -1):
            r = (r ^ lags[L]) * K1
            r = r ^ _lsr(r, 29)
        out.append(_finalize(r ^ _s64(0x243F6A8885A308D3 * (n + 1))))
    return out


def page_rows(ids: torch.Tensor, orders: list[int], heads: int, page_heads: int, pages: int, S: int, pad_id: int,
              position_ids: torch.Tensor | None = None) -> torch.Tensor:
    """Page-local multi-head hashing: per order and group of ``page_heads`` heads, the group's slots on its n-gram's
    page -> table rows ``[..., len(orders) · heads]``."""
    hs = ngram_hashes(ids, max(orders), pad_id, position_ids)
    U = torch.tensor([s for s in range(1, S) if math.gcd(s, S) == 1], dtype=torch.long, device=ids.device)
    j = torch.arange(page_heads, device=ids.device)
    out = []
    for k, n in enumerate(orders):
        key = hs[n - 1]
        for g in range(heads // page_heads):
            hp = _finalize(key ^ _s64(0x9E3779B97F4A7C15 * (1 + 64 * n + g)))
            page = _lsr(hp, 1) % pages
            hsl = _finalize(hp ^ SLOT_SALT)
            a = _lsr(hsl, 1) % S
            s = U[_lsr(hsl, 40) % U.numel()]
            slot = (a[..., None] + j * s[..., None]) % S
            out.append(((k * pages + page) * S)[..., None] + slot)
    return torch.cat(out, dim=-1)


class Engram(nn.Module):
    """Hashed n-gram memory: ``x' = g·W_v e + silu(conv(rms(g·W_v e)))`` for the rows ``e`` of the n-grams ending at
    each position, ``g = σ(sign(z)·√|z|)``, ``z = <rms(W_k e), rms(x)> / √d``, a depthwise causal conv of
    ``engram_conv`` taps dilated by the longest order. The table (``[rows, head_dim]``, bf16, or under ``embla_q4``
    its packed ``(q4, scales, biases)``) is in host memory, loaded from ``engram_table.safetensors``."""

    def __init__(self, config: EmblaConfig) -> None:
        super().__init__()
        self.config = config
        self.orders = list(config.engram_orders)
        self.n_heads = len(self.orders) * config.engram_heads
        d, E = config.hidden_size, len(self.orders) * config.engram_heads * config.engram_head_dim
        self.host_table: torch.Tensor | tuple | None = None
        self.table_path: Path | None = None
        self.w_k = make_linear(config, E, d)
        self.w_v = make_linear(config, E, d)
        self.taps = int(config.engram_conv)
        self.dilation = max(self.orders)
        self.conv_weight = nn.Parameter(torch.zeros(d * self.taps))

    @property
    def history(self) -> int:
        """Positions of conv input a new token's conv reads before it."""
        return (self.taps - 1) * self.dilation

    def rows_of(self, ids: torch.Tensor, position_ids: torch.Tensor | None = None) -> torch.Tensor:
        cfg = self.config
        return page_rows(ids, self.orders, cfg.engram_heads, cfg.engram_page_heads, cfg.engram_pages,
                         cfg.engram_rows_per_page, int(cfg.vocab_size), position_ids)

    def load_table(self, path) -> None:
        from safetensors.torch import load_file
        f = load_file(str(path))
        want = (self.config.engram_table_rows, self.config.engram_head_dim)
        if "q4" in f:                            # packed: 4-bit codes, fp16 scale / bias per group of 64
            t = (f["q4"], f["scales"], f["biases"])
            shape = (t[0].shape[0], t[0].shape[1] * 2)
        else:
            t = f["weight"]
            shape = tuple(t.shape)
        if tuple(shape) != want:
            raise ValueError(f"{path}: an engram table of {tuple(shape)}, the config needs {want}")
        self.host_table, self.table_path = t, Path(path)

    def lookup(self, ids: torch.Tensor, dtype: torch.dtype, position_ids: torch.Tensor | None = None,
               cache: EmblaCache | None = None) -> torch.Tensor:
        """``ids [B, T]`` -> the rows of the n-grams ending at each of them ``[B, T, n_heads, head_dim]`` in
        ``dtype`` (with ``cache``: the tokens before them come from it, and it keeps the latest)."""
        B, T = ids.shape
        if cache is not None:
            full = _cat(cache.engram_ids, ids)
            cache.engram_ids = full[:, -(max(self.orders) - 1):] if max(self.orders) > 1 else full[:, :0]
            rows = self.rows_of(full)[:, -T:]
        else:
            rows = self.rows_of(ids, position_ids)
        if self.host_table is None:
            raise RuntimeError(f"the engram table is not loaded: load the model with from_pretrained from a "
                               f"directory holding {TABLE_FILE}")
        u, inv = torch.unique(rows.reshape(-1), return_inverse=True)
        if isinstance(self.host_table, tuple):
            q4, sc, bi = self.host_table
            uc = u.cpu()
            got = dequant4(q4[uc], sc[uc], bi[uc], _q4_group(self.config) or 64).to(ids.device)
        else:
            got = self.host_table[u.cpu()].to(ids.device)
        e = got[inv].reshape(*rows.shape, -1)
        return e.reshape(B, T, self.n_heads, -1).to(dtype)

    def read(self, x: torch.Tensor, e: torch.Tensor, position_ids: torch.Tensor | None = None,
             cache: EmblaCache | None = None) -> torch.Tensor:
        B, T, d = x.shape
        e = e.reshape(B, T, -1)
        key, val = self.w_k(e), self.w_v(e)
        z = (F.rms_norm(key.float(), (d,), eps=EPS32) * F.rms_norm(x.float(), (d,), eps=EPS32)).sum(-1, keepdim=True)
        z = z / math.sqrt(d)
        g = torch.sigmoid(torch.sign(z) * torch.sqrt(z.abs() + 1e-6)).to(val.dtype)
        gated = g * val
        normed = F.rms_norm(gated.float(), (d,), eps=EPS32).to(val.dtype)
        if position_ids is not None:              # the conv's taps stop at the document start
            w = self.conv_weight.view(d, self.taps).to(normed.dtype)
            conv = None
            for i in range(self.taps):
                L = (self.taps - 1 - i) * self.dilation
                term = normed if L == 0 else (
                    F.pad(normed, (0, 0, L, 0))[:, :T] * (position_ids >= L).unsqueeze(-1).to(normed.dtype))
                term = term * w[:, i]
                conv = term if conv is None else conv + term
            return gated + F.silu(conv)
        w = self.conv_weight.view(d, 1, self.taps).to(normed.dtype)
        pad = self.history
        if cache is not None:
            past = cache.engram_conv
            seq = normed if past is None else torch.cat([past.to(normed.dtype), normed], dim=1)
            cache.engram_conv = seq[:, -pad:] if pad > 0 else seq[:, :0]
            P = seq.shape[1] - T                                     # positions of history in front
            conv = F.conv1d(F.pad(seq.transpose(1, 2), (pad - min(P, pad), 0))[..., -(T + pad):], w,
                            dilation=self.dilation, groups=d)
            return gated + F.silu(conv.transpose(1, 2))
        conv = F.conv1d(F.pad(normed.transpose(1, 2), (pad, 0)), w, dilation=self.dilation, groups=d)
        return gated + F.silu(conv.transpose(1, 2))


# =============================================================================== Block AttnRes
def key_logits(b: torch.Tensor, w: torch.Tensor, eps: float) -> torch.Tensor:
    """``w_q · rms(b)`` for every pseudo-query row of ``w [Q, d]`` -> ``[B, T, Q]`` fp32."""
    with torch.autocast(b.device.type, enabled=False):
        bf = b.float()
        return (bf @ w.float().t()) * torch.rsqrt(bf.square().mean(-1, keepdim=True) + eps)


def attn_res_mix(lg: list[torch.Tensor], vals: list[torch.Tensor], queries, eps: float,
                 x: torch.Tensor | None) -> list[torch.Tensor]:
    """Block Attention Residuals (arXiv 2603.15031) for the pseudo-queries ``queries`` (``k`` of them): the softmax
    mix of the completed sources ``vals`` by the logits ``lg`` (one ``[B, T, k]`` per source), then merged with the
    current block's partial sum ``x`` at its own softmax weight ``σ(q · rms(x) − lse)`` -> one fp32 ``[B, T, d]``
    per query."""
    lgs = torch.stack(lg, dim=-1).float()                                         # [B, T, k, N]
    B, T, k, N = lgs.shape
    P = torch.softmax(lgs, dim=-1)
    lse = torch.logsumexp(lgs, dim=-1)                                            # [B, T, k]
    d = vals[0].shape[-1]
    V = torch.stack(list(vals), dim=2).reshape(B * T, N, d)
    mix = torch.bmm(P.reshape(B * T, k, N).to(V.dtype), V).view(B, T, k, d)
    mixes = [mix[:, :, j].contiguous() for j in range(k)]
    if x is None:
        return [m.float() for m in mixes]
    W = torch.stack(tuple(queries)).float()
    xn = rms_norm(x.float(), eps)
    w = torch.sigmoid(torch.einsum("btd,kd->kbt", xn, W) - lse.permute(2, 0, 1))
    return [m.float() + w[j].unsqueeze(-1) * (x.float() - m.float()) for j, m in enumerate(mixes)]


# =============================================================================== block
class Block(nn.Module):
    def __init__(self, config: EmblaConfig, layer_idx: int) -> None:
        super().__init__()
        self.layer_idx = layer_idx
        self.layer_type = config.layer_types[layer_idx]
        self.attn = {LAYER_SLIDING: SlidingAttention, LAYER_FULL: FullAttention,
                     LAYER_SPARSE: SparseAttention}[self.layer_type](config, layer_idx)
        self.mlp = MoE(config) if config.mlp_layer_types[layer_idx] == MLP_SPARSE else DenseMLP(config)
        d = config.hidden_size
        self.attn_res_query = nn.Parameter(torch.zeros(d))
        self.mlp_res_query = nn.Parameter(torch.zeros(d))
        if self.layer_type == LAYER_FULL and config.kv_sources[layer_idx] != layer_idx:
            self.kv_res_query = nn.Parameter(torch.zeros(d))

    def mlp_weight(self) -> torch.Tensor:
        return self.mlp.shared_fc.weight if isinstance(self.mlp, MoE) else self.mlp.c_fc.weight


class Transformer(nn.Module):
    def __init__(self, config: EmblaConfig) -> None:
        super().__init__()
        g = _q4_group(config)
        self.wte = (nn.Embedding(config.vocab_size, config.hidden_size) if g is None
                    else Q4Embedding(config.vocab_size, config.hidden_size, g))
        self.h = nn.ModuleList([Block(config, i) for i in range(config.num_hidden_layers)])


# =============================================================================== model
def unsupported(config) -> list[str]:
    """The released config's options this code does not implement."""
    bad = []
    if config.attn_res_block <= 0:
        bad.append(f"attn_res_block={config.attn_res_block} (the plain residual stream)")
    if config.engram_layer >= 0 and config.engram_table != "sparse":
        bad.append(f"engram_table={config.engram_table!r}")
    return bad


class EmblaPreTrainedModel(PreTrainedModel):
    config_class = EmblaConfig
    base_model_prefix = "transformer"
    supports_gradient_checkpointing = False
    _no_split_modules = ["Block"]
    _supports_flash_attn = False
    _supports_sdpa = False
    _supports_flex_attn = False

    def _init_weights(self, module: nn.Module) -> None:
        # Every weight comes from the checkpoint; a fresh model is not this code's use. transformers runs this after
        # loading too, so it goes through transformers' guarded initializers, which leave a loaded tensor alone
        # (writing .data directly would overwrite the checkpoint's weights).
        std = float(self.config.initializer_range)
        if isinstance(module, (nn.Linear, nn.Embedding)):
            init.normal_(module.weight, mean=0.0, std=std)
            if getattr(module, "bias", None) is not None:
                init.zeros_(module.bias)
        elif isinstance(module, MoE) and isinstance(module.experts_fc, torch.Tensor):
            init.normal_(module.experts_fc, mean=0.0, std=std)
            init.normal_(module.experts_proj, mean=0.0, std=std)


class EmblaForCausalLM(EmblaPreTrainedModel, GenerationMixin):
    def __init__(self, config: EmblaConfig) -> None:
        bad = unsupported(config)
        if bad:
            raise ValueError("this Embla config uses options this modeling code does not implement: "
                             + ", ".join(bad))
        super().__init__(config)
        C, V = config.hidden_size, config.vocab_size
        self.transformer = Transformer(config)
        self.lm_head = make_linear(config, C, V)
        self.engram = Engram(config) if config.engram_layer >= 0 else None
        self.final_res_query = nn.Parameter(torch.zeros(C))
        if self.engram is not None:
            self.engram_res_query = nn.Parameter(torch.zeros(C))
        self._sources = sorted(set(config.kv_sources.values()))
        # K/V source layer -> the full layers whose K/V project its (mixed) input
        self._bridges = {s: [j for j in sorted(config.kv_sources) if config.kv_sources[j] == s and j != s]
                         for s in self._sources}
        P = config.num_prefill_layers
        # the decode half runs for the last position only when every K/V it reads is a function of prefill-half
        # states: each decode-half full layer's K/V source is layer P's input or earlier
        self._early_exit = 0 < P < config.num_hidden_layers and all(
            config.kv_sources[j] <= P for j, t in enumerate(config.layer_types) if t == LAYER_FULL and j >= P)
        self.post_init()

    # ---- loading -----------------------------------------------------------------------------------------------
    @classmethod
    def from_pretrained(cls, pretrained_model_name_or_path, *args, **kwargs):
        """transformers' loader, plus the engram table (``engram_table.safetensors``, not a parameter)."""
        out = super().from_pretrained(pretrained_model_name_or_path, *args, **kwargs)
        model = out[0] if isinstance(out, tuple) else out          # output_loading_info=True: (model, info)
        if model.engram is not None:
            local = Path(str(pretrained_model_name_or_path)) / TABLE_FILE
            if local.is_file():
                path = local
            else:
                from transformers.utils import cached_file
                path = cached_file(str(pretrained_model_name_or_path), TABLE_FILE,
                                   **{k: kwargs[k] for k in ("revision", "token", "cache_dir") if k in kwargs})
            model.engram.load_table(path)
        return out

    def save_pretrained(self, save_directory, *args, **kwargs):
        out = super().save_pretrained(save_directory, *args, **kwargs)
        e = self.engram
        if e is not None and e.host_table is not None:
            dst = Path(save_directory) / TABLE_FILE
            if e.table_path is not None and e.table_path.is_file():
                if e.table_path.resolve() != dst.resolve():
                    shutil.copyfile(e.table_path, dst)
            else:
                from safetensors.torch import save_file
                t = e.host_table
                save_file(dict(zip(("q4", "scales", "biases"), t)) if isinstance(t, tuple)
                          else {"weight": t.contiguous()}, str(dst))
        return out

    def get_input_embeddings(self) -> nn.Module:
        return self.transformer.wte

    def set_input_embeddings(self, value: nn.Module) -> None:
        self.transformer.wte = value

    def get_output_embeddings(self) -> nn.Module:
        return self.lm_head

    # ---- generation --------------------------------------------------------------------------------------------
    @classmethod
    def _supports_default_dynamic_cache(cls) -> bool:
        return False                             # the cache is EmblaCache, made in prepare_inputs_for_generation

    def prepare_inputs_for_generation(self, input_ids, past_key_values=None, attention_mask=None, use_cache=None,
                                      logits_to_keep=None, **kwargs):
        # One row has no padding, whatever generate() inferred: when the tokenizer's pad token is its BOS,
        # transformers masks a prompt's leading BOS as padding.
        if input_ids.shape[0] == 1:
            attention_mask = None
        use_cache = self.config.use_cache if use_cache is None else use_cache
        if use_cache and past_key_values is None:
            past_key_values = EmblaCache()
        if past_key_values is not None:
            input_ids = input_ids[:, past_key_values.seen:]
            if attention_mask is not None:
                attention_mask = attention_mask[:, -input_ids.shape[1]:]
        out = {"input_ids": input_ids, "attention_mask": attention_mask, "past_key_values": past_key_values,
               "use_cache": use_cache}
        if logits_to_keep is not None:
            out["logits_to_keep"] = logits_to_keep
        return out

    # ---- forward -----------------------------------------------------------------------------------------------
    def forward(self, input_ids: torch.LongTensor | None = None, attention_mask: torch.Tensor | None = None,
                position_ids: torch.LongTensor | None = None, past_key_values: EmblaCache | None = None,
                inputs_embeds: torch.FloatTensor | None = None, labels: torch.LongTensor | None = None,
                use_cache: bool | None = None, logits_to_keep: int | torch.Tensor = 0,
                **kwargs) -> CausalLMOutputWithPast:
        """``input_ids [B, T]`` (the engram hashes them). No padding: ``attention_mask`` must be all ones (rows of
        unequal length: one row per call, or pack them with ``position_ids`` restarting at 0 per document, without a
        cache). ``past_key_values``: a :class:`EmblaCache` (``use_cache`` makes one), ``input_ids`` then the
        tokens after the ones it has seen. ``logits_to_keep=1`` runs the decode half for the last position only."""
        if input_ids is None:
            raise ValueError("embla needs input_ids (the engram hashes them)")
        if attention_mask is not None and not bool(attention_mask.all()):
            raise ValueError("embla has no padding mask: pass unpadded rows (one sequence per call, or "
                             "documents packed into a row with position_ids restarting at 0)")
        cache = past_key_values
        if position_ids is not None:
            if cache is not None:
                raise ValueError("embla: packed documents (position_ids) take no cache")
        elif cache is None and (self.config.use_cache if use_cache is None else use_cache) and labels is None:
            cache = EmblaCache()
        if cache is not None and not isinstance(cache, EmblaCache):
            raise TypeError(f"embla's cache is a EmblaCache, got {type(cache).__name__}")
        packing = None if position_ids is None else Packing(position_ids.to(input_ids.device))
        early = (self._early_exit and packing is None and labels is None and isinstance(logits_to_keep, int)
                 and logits_to_keep == 1 and input_ids.shape[1] > 1)
        x = self._stack(input_ids, inputs_embeds, packing, cache, early)
        cfg = self.config
        x = rms_norm(x, cfg.rms_norm_eps)
        sl = slice(-logits_to_keep, None) if isinstance(logits_to_keep, int) else logits_to_keep
        logits = self.lm_head(x[:, sl, :])
        cap = cfg.final_logit_softcapping
        if cap:
            logits = torch.tanh(logits / cap) * cap
        loss = None
        if labels is not None:
            loss = self.loss_function(logits=logits, labels=labels, vocab_size=cfg.vocab_size, **kwargs)
        if cache is not None:
            cache.seen += input_ids.shape[1]
        return CausalLMOutputWithPast(loss=loss, logits=logits, past_key_values=cache)

    def _select(self, qn: torch.Tensor, kn: torch.Tensor, packing: Packing | None) -> torch.Tensor:
        cfg = self.config
        return select_keys(qn.detach(), kn.detach(), cfg.sparse_topk, cfg.sparse_recent,
                           position_ids=None if packing is None else packing.position_ids)

    def _res_queries(self) -> tuple[list[nn.Parameter], dict]:
        """Every AttnRes pseudo-query in the training code's order, and each mix's columns: ``("attn", i)`` the layer's query
        then the queries of the layers bridged to it, ``("mlp", i)``, ``"engram"``, ``"final"``."""
        qs, cols = [], {}
        for i, b in enumerate(self.transformer.h):
            bridged = [self.transformer.h[j].kv_res_query for j in self._bridges.get(i, ())]
            cols[("attn", i)] = (len(qs), len(qs) + 1 + len(bridged))
            qs += [b.attn_res_query, *bridged]
            cols[("mlp", i)] = (len(qs), len(qs) + 1)
            qs.append(b.mlp_res_query)
        if self.engram is not None:
            cols["engram"] = (len(qs), len(qs) + 1)
            qs.append(self.engram_res_query)
        cols["final"] = (len(qs), len(qs) + 1)
        qs.append(self.final_res_query)
        return qs, cols

    def _stack(self, input_ids, inputs_embeds, packing: Packing | None, cache: EmblaCache | None,
               early: bool) -> torch.Tensor:
        """Block AttnRes: ``blocks`` the completed sources (the normed embedding, the engram read's output, each
        completed block's sum), ``x`` the current block's partial sum (fp32; None at a block's start). Every
        sub-layer reads its own mix of them (:func:`attn_res_mix`) and adds its output to ``x``. A K/V source layer
        also mixes the inputs of the layers bridged to it (their K/V sources), held until they run. ``early``: at
        layer ``num_prefill_layers`` the K/V sources are kept at every position and everything else is cut to the
        last one."""
        cfg = self.config
        eps = cfg.rms_norm_eps
        pos = None if packing is None else packing.position_ids
        B, T = input_ids.shape
        p0 = 0 if cache is None else cache.seen
        positions = pos if pos is not None else torch.arange(p0, p0 + T, device=input_ids.device)
        starts = set(cfg.res_block_starts())
        b0 = rms_norm(self.transformer.wte(input_ids) if inputs_embeds is None else inputs_embeds, eps)
        dt = _store_dtype(b0, self.transformer.wte.weight)
        qs, cols = self._res_queries()
        W = torch.stack(qs)
        blocks, x = [b0.to(dt)], None
        logits = [key_logits(blocks[0], W, eps)]

        def mixes(key, x):
            a, b = cols[key]
            return attn_res_mix([lg[..., a:b] for lg in logits], blocks, qs[a:b], eps, x)

        taps: dict[int, torch.Tensor] = {}
        k = kn = v = idx = None
        for i, block in enumerate(self.transformer.h):
            t = block.layer_type
            if i in starts:
                blocks.append(x.to(dt))
                logits.append(key_logits(blocks[-1], W, eps))
                x = None
            hs = mixes(("attn", i), x)
            h = _to_act(rms_norm(hs[0], eps), block.attn.c_q.weight)
            if early and i == cfg.num_prefill_layers:
                # the decode half for the last position: its K/V sources (this input, the taps) stay whole
                taps.update(zip(self._bridges.get(i, ()), (rms_norm(m, eps).to(dt) for m in hs[1:])))
                src_here = h
                h = h[:, -1:]
                blocks = [b[:, -1:] for b in blocks]
                logits = [lg[:, -1:] for lg in logits]
                x = None if x is None else x[:, -1:]
            else:
                src_here = h
                if t == LAYER_FULL:
                    taps.update(zip(self._bridges.get(i, ()), (rms_norm(m, eps).to(dt) for m in hs[1:])))
            if t == LAYER_FULL:
                src = src_here if cfg.kv_sources[i] == i else taps.pop(i)
                a, k, kn, v, qn = block.attn(h, src, packing, cache)
                if cfg.selects_keys(i):
                    idx = self._select(qn, kn, packing)
            elif t == LAYER_SPARSE:
                a = block.attn(h, k, v, idx)
            else:
                a = block.attn(h, positions, packing, cache)
            x = a.float() if x is None else x + a
            hm = mixes(("mlp", i), x)
            x = x + block.mlp(_to_act(rms_norm(hm[0], eps), block.mlp_weight()))
            if self.engram is not None and i == cfg.engram_layer:
                w_k = self.engram.w_k.weight
                e_eng = self.engram.lookup(input_ids, _to_act(x, w_k).dtype, pos, cache)
                he = _to_act(mixes("engram", x)[0], w_k)
                e = self.engram.read(he, e_eng, pos, cache)
                blocks.append(e.to(dt))
                logits.append(key_logits(blocks[-1], W, eps))
        return _to_act(mixes("final", x)[0], self.lm_head.weight)


__all__ = ["EmblaForCausalLM", "EmblaPreTrainedModel", "EmblaCache"]

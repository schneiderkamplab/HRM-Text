"""Trainable Embla with packed PrefixLM and fixed decoder recurrence.

Reference and bounded-memory training paths with optional qualified GPU kernels.
Keep eager operations available as numerical oracles for every optimized path.
"""
import torch
from torch import nn
from torch.nn import functional as F
from .upstream.modeling_embla import (
    Transformer, key_logits, attn_res_mix, rms_norm, EmblaForCausalLM,
    LAYER_FULL, LAYER_SPARSE, relu2_attention, select_keys, softmax_window,
)
from .engram import TrainableEngram
from .attention import packed_relu_attention, packed_select_keys, document_spans, local_indices, gathered_attention
from .reference import attention_mask, select_sparse_keys, selected_softmax_attention


class EmblaTrainingModel(nn.Module):
    _res_queries = EmblaForCausalLM._res_queries

    def __init__(self, config, *, decoder_loops=1, prefix_lm=False, attention_backend="tiled", compile_attention=False, fa4_window=False, fused_relu=False, single_topk=False, fused_sparse=False, batched_windows=False, fused_residual=False, relu_tile_m=16):
        if attention_backend not in ("eager", "tiled"):
            raise ValueError("Unknown Embla attention backend")
        self.attention_backend = attention_backend
        self.compile_attention = compile_attention
        self.fa4_window = fa4_window
        self.fused_relu = fused_relu
        self.single_topk = single_topk
        self.fused_sparse = fused_sparse
        self.batched_windows = batched_windows
        self.fused_residual = fused_residual
        self.relu_tile_m = relu_tile_m
        super().__init__()
        if type(decoder_loops) is not int or decoder_loops < 1:
            raise ValueError('decoder_loops must be a positive integer')
        if not config.attn_res_block:
            raise ValueError('Embla experiments require attention residuals')
        if decoder_loops > 1 and (config.num_prefill_layers not in config.res_block_starts() or
                any(s > config.num_prefill_layers for s in config.kv_sources.values())):
            raise ValueError('Loop boundary must start a residual block and all KV sources must precede it')
        self.config, self.decoder_loops, self.prefix_lm = config, decoder_loops, prefix_lm
        self.transformer = Transformer(config)
        self.lm_head = nn.Linear(config.hidden_size, config.vocab_size, bias=False)
        self.engram = TrainableEngram(config) if config.engram_layer >= 0 else None
        self.final_res_query = nn.Parameter(torch.zeros(config.hidden_size))
        if self.engram is not None:
            self.engram_res_query = nn.Parameter(torch.zeros(config.hidden_size))
        sources = sorted(set(config.kv_sources.values()))
        self._bridges = {s: [j for j in sorted(config.kv_sources) if config.kv_sources[j] == s and j != s]
                         for s in sources}
        # Upstream expert stacks are bare parameters, not nn.Linear children.
        with torch.no_grad():
            for name, parameter in self.named_parameters():
                if name == 'engram.table':
                    continue
                if parameter.ndim >= 2:
                    nn.init.normal_(parameter, std=config.initializer_range)
                else:
                    parameter.zero_()

    def forward(self, input_ids, *, position_ids=None, prompt_mask=None, inputs_embeds=None,
                return_hidden=False, cache=None, last_token_only=False):
        cfg = self.config
        b, t = input_ids.shape
        input_length = t
        decoding = cache is not None and cache.seen > 0
        early = last_token_only and cache is not None and not decoding and t > 1
        if early and (cfg.num_prefill_layers not in cfg.res_block_starts() or
                      any(source > cfg.num_prefill_layers for source in cfg.kv_sources.values())):
            raise ValueError('Early prefill requires decoder KV derived entirely from the encoder')
        if cache is not None and position_ids is not None:
            raise ValueError('Packed explicit positions cannot use an incremental cache')
        if cache is not None and torch.is_grad_enabled():
            raise ValueError('Incremental caching is inference-only; use torch.no_grad()')
        if position_ids is None:
            position_ids = (torch.arange(t, device=input_ids.device) + (cache.seen if cache is not None else 0))[None].expand(b, -1)
        if prompt_mask is None:
            if self.prefix_lm:
                raise ValueError('PrefixLM requires an explicit prompt mask')
            prompt_mask = torch.zeros_like(input_ids, dtype=torch.bool)
        segments = (position_ids == 0).cumsum(-1)
        spans = None if decoding else document_spans(position_ids)
        allowed = attention_mask(segments, position_ids, prompt_mask, prefix=self.prefix_lm) if self.attention_backend == "eager" else None
        local = None if self.fa4_window and input_ids.is_cuda else local_indices(segments,position_ids,prompt_mask,cfg.sliding_window,prefix=self.prefix_lm)
        window_layout = None
        if self.fa4_window and self.batched_windows and input_ids.is_cuda and not decoding:
            from .fa4_window import prepare_window_layout
            window_layout = prepare_window_layout(spans,prompt_mask,prefix=self.prefix_lm)
        b0 = rms_norm(self.transformer.wte(input_ids) if inputs_embeds is None else inputs_embeds, cfg.rms_norm_eps)
        dtype = b0.dtype
        qs, cols = self._res_queries()
        W = torch.stack(qs)
        blocks, x = [b0], None
        logits = [key_logits(b0, W, cfg.rms_norm_eps)]
        taps, full_kv = {}, {}
        starts = set(cfg.res_block_starts())
        encoder_blocks = encoder_logits = None

        residual_operation = attn_res_mix
        if self.fused_residual and input_ids.is_cuda:
            from .residual import compiled_residual_mix
            residual_operation = compiled_residual_mix()
        def mix(key):
            a, z = cols[key]
            arguments = ([lg[..., a:z] for lg in logits], list(blocks), qs[a:z], cfg.rms_norm_eps, x)
            # Recompute residual mixing instead of retaining a stacked copy of
            # every completed source at every layer. Snapshot the source list:
            # the outer forward appends/reset sources before backward runs.
            if torch.is_grad_enabled():
                from torch.utils.checkpoint import checkpoint
                return checkpoint(residual_operation, *arguments, use_reentrant=False)
            return residual_operation(*arguments)

        def normalized(value):
            return rms_norm(value, cfg.rms_norm_eps).to(dtype)

        order = list(range(cfg.num_hidden_layers)) + list(range(cfg.num_prefill_layers, cfg.num_hidden_layers)) * (self.decoder_loops - 1)
        for execution, i in enumerate(order):
            repeated = execution >= cfg.num_hidden_layers
            block = self.transformer.h[i]
            attn = block.attn
            if i == cfg.num_prefill_layers and repeated:
                previous = mix('final')[0].to(dtype)
                blocks = list(encoder_blocks) + [previous]
                logits = list(encoder_logits) + [key_logits(previous, W, cfg.rms_norm_eps)]
                x = None
            elif i in starts:
                blocks.append(x.to(dtype))
                logits.append(key_logits(blocks[-1], W, cfg.rms_norm_eps))
                x = None
            if i == cfg.num_prefill_layers and not repeated:
                encoder_blocks, encoder_logits = list(blocks), list(logits)
            hs = mix(('attn', i))
            h = normalized(hs[0])
            if block.layer_type == LAYER_FULL:
                if not repeated:
                    taps.update(zip(self._bridges.get(i, ()), (normalized(m) for m in hs[1:])))
                    src = h if cfg.kv_sources[i] == i else taps.pop(i)
                    k = attn._heads(attn.c_k, src, attn.num_key_value_heads)
                    v = attn._heads(attn.c_v, src, attn.num_key_value_heads)
                    kn = attn.norm_k(k)
                    if cache is not None:
                        if i in cache.full:
                            old = cache.full[i]
                            k,kn,v = (torch.cat((old[0],k),1),torch.cat((old[1],kn),1),torch.cat((old[2],v),1))
                        cache.full[i] = k,kn,v
                    full_kv[i] = k, kn, v
                k, kn, v = full_kv[i]
                if early and i == cfg.num_prefill_layers and not repeated:
                    h = h[:,-1:]
                    blocks = [source[:,-1:] for source in blocks]
                    logits = [source[:,-1:] for source in logits]
                    encoder_blocks = [source[:,-1:] for source in encoder_blocks]
                    encoder_logits = [source[:,-1:] for source in encoder_logits]
                    x = None if x is None else x[:,-1:]
                    t = 1
                    decoding = True
                q = attn.norm_q(attn._heads(attn.c_q, h, attn.num_heads))
                if decoding:
                    a = attn.c_proj(relu2_attention(q,kn,v))
                elif self.attention_backend == "tiled":
                    a = packed_relu_attention(q,kn,v,segments,position_ids,prompt_mask,prefix=self.prefix_lm,spans=spans,fused=self.fused_relu,tile_m=self.relu_tile_m)
                    a = attn.c_proj(a.reshape(b,t,-1))
                else:
                    repeat = attn.num_heads // attn.num_key_value_heads
                    scores = q.float().transpose(1,2) @ kn.float().transpose(1,2).repeat_interleave(repeat,1).transpose(-1,-2)
                    weights = (scores / cfg.head_dim ** .5).relu().square().masked_fill(~allowed[:,None],0)
                    a = (weights @ v.float().transpose(1,2).repeat_interleave(repeat,1)) / (cfg.head_dim ** .5 + weights.sum(-1,keepdim=True))
                    a = attn.c_proj(a.transpose(1,2).reshape(b,t,-1).to(dtype))
                if cfg.selects_keys(i):
                    if decoding:
                        idx = select_keys(q,kn,cfg.sparse_topk,cfg.sparse_recent)
                    elif self.attention_backend == "tiled":
                        idx = packed_select_keys(q,kn,segments,position_ids,prompt_mask,top_k=cfg.sparse_topk,recent=cfg.sparse_recent,prefix=self.prefix_lm,spans=spans,single_topk=self.single_topk)
                    else:
                        idx = select_sparse_keys(q,kn,allowed,top_k=cfg.sparse_topk,recent=cfg.sparse_recent)
            elif block.layer_type == LAYER_SPARSE:
                q = attn.norm_q(attn._heads(attn.c_q,h,attn.num_heads))
                if self.fused_sparse and q.is_cuda:
                    from .sparse_triton import sparse_attention
                    a = sparse_attention(q,attn.norm_k(k),v,idx)
                else:
                    a = gathered_attention(q,attn.norm_k(k),v,idx,compiled=self.compile_attention)
                a = attn.c_proj(a.reshape(b,t,-1))
            else:
                q = attn._norm_rope(attn._heads(attn.c_q,h,attn.num_heads),attn.q_norm if attn.learned_norm else None,position_ids)
                key = attn._norm_rope(attn._heads(attn.c_k,h,attn.num_key_value_heads),attn.k_norm if attn.learned_norm else None,position_ids)
                value = attn._heads(attn.c_v,h,attn.num_key_value_heads)
                repeat = attn.num_heads // attn.num_key_value_heads
                if cache is not None:
                    old = cache.sliding.get(i)
                    if old is not None:
                        key,value = torch.cat((old[0],key),1),torch.cat((old[1],value),1)
                    keep = cfg.sliding_window-1
                    cache.sliding[i] = (key[:,-keep:],value[:,-keep:]) if keep else (key[:,:0],value[:,:0])
                if decoding:
                    a = softmax_window(q,key,value,cfg.sliding_window)
                elif window_layout is not None:
                    from .fa4_window import batched_window_attention
                    a = batched_window_attention(q,key,value,cfg.sliding_window,window_layout)
                elif self.fa4_window and q.is_cuda:
                    from .fa4_window import packed_window_attention
                    a = packed_window_attention(q,key,value,position_ids,prompt_mask,cfg.sliding_window,prefix=self.prefix_lm,spans=spans)
                else:
                    a = gathered_attention(q,key,value,local.expand(-1,attn.num_key_value_heads,-1,-1),compiled=self.compile_attention)
                a = attn.c_proj(a.reshape(b,t,-1))
            x = a.float() if x is None else x + a
            x = x + block.mlp(normalized(mix(('mlp',i))[0]))
            if self.engram is not None and i == cfg.engram_layer:
                emb = self.engram.lookup(input_ids,dtype,position_ids if cache is None else None,cache)
                eng = self.engram.read(mix('engram')[0].to(dtype),emb,position_ids if cache is None else None,cache).to(dtype)
                blocks.append(eng)
                logits.append(key_logits(eng,W,cfg.rms_norm_eps))
        if cache is not None:
            cache.seen += input_length
        hidden = normalized(mix('final')[0])
        if return_hidden:
            return hidden
        out = self.lm_head(hidden)
        cap = cfg.final_logit_softcapping
        return out if not cap else torch.tanh(out / cap) * cap

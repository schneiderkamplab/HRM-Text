"""Configuration of an Embla 1 checkpoint as Hugging Face remote code (``trust_remote_code=True``).

The released model's schema, standalone: the fields, defaults and checks of the training
code's config without its kernel choices, training plan, experimental options or old-name migration, so a
packaged checkpoint loads with nothing but transformers installed. The training code's export test holds the two to
the same fields and defaults.

A 32-layer stack in two halves. The **prefill half** (layers ``[0, num_prefill_layers)``) is ``sliding_attention``
layers (softmax GQA, RoPE on ``partial_rotary_factor`` of each head, a left window of ``sliding_window`` keys, the
query included) with one ``full_attention`` layer (ReLU², no position encoding, full causal). The **decode half** is
blocks of one ``full_attention`` layer followed by ``sparse_attention`` layers. A full layer projects its K/V from the
normed input of layer ``kv_sources[l]`` (its own, or an earlier one: a "bridged" cache), so every K/V the decode
half reads is a function of prefill-half states. A sparse layer has no K/V of its own: it reads the nearest full
layer before it, per query that layer's ``sparse_topk`` highest-scoring keys (max over the query heads of a kv head)
plus the ``sparse_recent`` most recent, with softmax. ``mlp_layer_types``: a dense ReLU² MLP or the MoE (shared +
routed ReLU² experts). An engram (hashed n-gram rows, gated by the hidden state) is read after ``engram_layer``. The
residual stream is Block Attention Residuals in blocks of ``attn_res_block`` layers. Logits are softcapped.

``layer_types`` uses transformers' ``sliding_attention`` / ``full_attention`` and this architecture's
``sparse_attention``, which is not in transformers' allowed list: :meth:`EmblaConfig.validate` checks it here.
"""
from __future__ import annotations

from transformers.configuration_utils import PreTrainedConfig

LAYER_SLIDING = "sliding_attention"
LAYER_FULL = "full_attention"
LAYER_SPARSE = "sparse_attention"
LAYER_TYPES = (LAYER_SLIDING, LAYER_FULL, LAYER_SPARSE)
MLP_DENSE = "dense"
MLP_SPARSE = "sparse"
MLP_LAYER_TYPES = (MLP_DENSE, MLP_SPARSE)

# Field names of the training code's config.json before 2026-11-10 (this code does not rewrite them)
_OLD_NAMES = frozenset({"block_types", "attention_types", "prefill_layers", "local_window", "local_rope_dims",
                        "local_rope_theta", "local_num_attention_heads", "local_num_key_value_heads", "moe_num_experts",
                        "moe_expert_hidden", "moe_top_k", "moe_shared_hidden", "moe_dense_layers", "mlp_hidden",
                        "gate_threshold", "qk_norm_learned", "logit_softcap"})


def two_half_layer_types(num_hidden_layers: int, num_prefill_layers: int, prefill_full_layers=(7,),
                         decode_block: int = 4) -> list[str]:
    """The two-half schedule: sliding layers in the prefill half but for ``prefill_full_layers`` (full), then
    blocks of ``decode_block`` layers, one full layer and sparse layers after it."""
    return [(LAYER_FULL if i in prefill_full_layers else LAYER_SLIDING) if i < num_prefill_layers else
            (LAYER_FULL if (i - num_prefill_layers) % decode_block == 0 else LAYER_SPARSE)
            for i in range(num_hidden_layers)]


def rows_per_page(dim: int, bits: int = 4, group: int = 64, page: int = 4096) -> int:
    """Rows of the phone's 4-bit engram table per flash page of ``page`` bytes (56 at width 128 in 4 KiB)."""
    return page // (dim * bits // 8 + 2 * 2 * (dim // group))


class EmblaConfig(PreTrainedConfig):
    model_type = "embla"
    keys_to_ignore_at_inference = ["past_key_values"]
    ignore_keys_at_rope_validation = {"partial_rotary_factor"}

    # ---- stack ---------------------------------------------------------------
    vocab_size: int = 65536
    hidden_size: int = 2048
    num_hidden_layers: int = 32
    num_prefill_layers: int = 16                # layers [0, num_prefill_layers) run for every prompt token
    layer_types: list[str] | None = None        # None: two_half_layer_types (layer 7 full, decode blocks of 4)
    mlp_layer_types: list[str] | None = None    # None: layer 0 dense, the rest sparse (the MoE)
    kv_sources: dict | None = None              # full layer -> the layer whose normed input its K/V project
    rms_norm_eps: float = 2.0 ** -7
    max_position_embeddings: int = 2 ** 18
    initializer_range: float = 0.02
    tie_word_embeddings: bool = False
    use_cache: bool = True
    pad_token_id: int | None = None
    bos_token_id: int | None = None
    eos_token_id: int | list[int] | None = None

    # ---- attention -------------------------------------------------------------
    head_dim: int = 128
    # True: learned q / k RMS-norm gains (1 + weight) per layer; False: the parameter-free norm (q and k are normed
    # either way)
    use_qk_norm: bool = True
    num_attention_heads: int = 16               # full and sparse layers
    num_key_value_heads: int = 2
    sparse_topk: int = 1024
    sparse_recent: int = 128
    sliding_num_attention_heads: int = 16
    sliding_num_key_value_heads: int = 4
    sliding_window: int = 128
    rope_parameters: dict | None = None         # None: default RoPE, theta 10000, partial_rotary_factor 0.5

    # ---- MLP -------------------------------------------------------------------
    intermediate_size: int = 2048               # the dense MLP's width
    num_experts: int = 96
    num_experts_per_tok: int = 8
    moe_intermediate_size: int = 512
    shared_expert_intermediate_size: int = 1024

    # ---- engram ----------------------------------------------------------------
    engram_layer: int = 0                       # -1 = no engram
    engram_orders: list[int] | None = None      # default [2, 3]
    engram_heads: int = 8
    engram_head_dim: int = 128
    engram_conv: int = 4
    engram_pages: int = 209716
    engram_page_heads: int = 4
    engram_page_bytes: int = 4096
    # sparse: the table is engram_table.safetensors beside the weights (host memory); dense: a parameter
    engram_table: str = "sparse"
    engram_init_std: float = 1.0

    # ---- residual stream and output ---------------------------------------------
    attn_res_block: int = 4                     # Block Attention Residuals in blocks of this many layers; 0 = plain
    final_logit_softcapping: float | None = 15.0

    def __post_init__(self, **kwargs):
        old = sorted(_OLD_NAMES.intersection(kwargs))
        if old:
            raise ValueError(f"{self.model_type}: {old} are names of the training code's config.json from before "
                             "2026-11-10; re-export the checkpoint")
        n = self.num_hidden_layers
        if self.layer_types is None:
            self.layer_types = two_half_layer_types(n, self.num_prefill_layers)
        self.layer_types = list(self.layer_types)
        self._check_layer_types()
        if self.layer_types[0] == LAYER_SPARSE:
            raise ValueError("a sparse_attention layer needs a full_attention layer before it")
        if self.mlp_layer_types is None:
            self.mlp_layer_types = [MLP_DENSE if i == 0 else MLP_SPARSE for i in range(n)]
        self.mlp_layer_types = list(self.mlp_layer_types)
        if sorted(set(self.mlp_layer_types) - set(MLP_LAYER_TYPES)) or len(self.mlp_layer_types) != n:
            raise ValueError(f"mlp_layer_types must be {n} entries from {MLP_LAYER_TYPES}, got {self.mlp_layer_types}")
        if self.kv_sources is None:
            full = [i for i, t in enumerate(self.layer_types) if t == LAYER_FULL]
            self.kv_sources = {i: i for i in full}
            pre = [i for i in full if i < self.num_prefill_layers]
            dec = [i for i in full if i >= self.num_prefill_layers]
            if pre and dec:
                for j, i in enumerate(dec):
                    self.kv_sources[i] = dec[0] if j < (len(dec) + 1) // 2 else pre[-1]
        self.kv_sources = {int(k): int(v) for k, v in self.kv_sources.items()}
        for i, t in enumerate(self.layer_types):
            src = self.kv_sources.get(i)
            if t == LAYER_FULL and (src is None or not 0 <= src <= i):
                raise ValueError(f"full layer {i} needs kv_sources[{i}] in [0, {i}], got {src}")
        if any(self.layer_types[k] != LAYER_FULL for k in self.kv_sources):
            raise ValueError(f"kv_sources names a layer that is not a full layer: {self.kv_sources}")
        if self.sliding_num_attention_heads % self.sliding_num_key_value_heads:
            raise ValueError("sliding_num_attention_heads must be divisible by sliding_num_key_value_heads")
        if self.num_attention_heads % self.num_key_value_heads:
            raise ValueError("num_attention_heads must be divisible by num_key_value_heads")
        if self.rope_parameters is None:
            self.rope_parameters = {"rope_type": "default", "rope_theta": 10000.0, "partial_rotary_factor": 0.5}
        self.rope_parameters = dict(self.rope_parameters)
        self.rope_parameters.setdefault("partial_rotary_factor", 1.0)
        dims = self.rope_parameters["partial_rotary_factor"] * self.head_dim
        if not (0 <= dims <= self.head_dim and abs(dims - round(dims)) < 1e-6 and round(dims) % 2 == 0):
            raise ValueError(f"rope_parameters' partial_rotary_factor must rotate an even number of the "
                             f"{self.head_dim} dims of a head")
        if not 0 < self.num_experts_per_tok <= self.num_experts:
            raise ValueError("num_experts_per_tok must be in (0, num_experts]")
        if self.engram_orders is None:
            self.engram_orders = [2, 3]
        self.engram_orders = sorted(int(o) for o in self.engram_orders)
        if self.engram_table not in ("dense", "sparse"):
            raise ValueError(f"engram_table must be dense or sparse, got {self.engram_table!r}")
        if self.engram_layer >= 0:
            S = self.engram_rows_per_page
            if self.engram_heads % self.engram_page_heads or not 1 <= self.engram_page_heads <= S:
                raise ValueError(f"engram_heads ({self.engram_heads}) must be a multiple of engram_page_heads "
                                 f"({self.engram_page_heads}), at most {S}")
        if self.attn_res_block > 0:
            starts = self.res_block_starts()
            if not self.engram_layer < (starts[0] if starts else n):
                raise ValueError("attn_res_block: engram_layer must be in the first block")
            for s in sorted(set(self.kv_sources.values())):
                if self.kv_sources.get(s) != s:
                    raise ValueError(f"attn_res_block: the K/V source layer {s} must be a full layer that is its own "
                                     "K/V source")
        super().__post_init__(**kwargs)

    def validate(self) -> None:
        """transformers' validators, with ``layer_types`` checked against this architecture's types
        (``sparse_attention`` is not in transformers' ``ALLOWED_LAYER_TYPES``)."""
        for validator in PreTrainedConfig.__class_validators__:
            if validator.__name__ != "validate_layer_type":
                validator(self)
        self._check_layer_types()

    def _check_layer_types(self) -> None:
        if self.layer_types is None:
            return
        bad = sorted(set(self.layer_types) - set(LAYER_TYPES))
        if bad:
            raise ValueError(f"unknown layer types {bad}; choose from {LAYER_TYPES}")
        if len(self.layer_types) != self.num_hidden_layers:
            raise ValueError(f"layer_types has {len(self.layer_types)} entries for {self.num_hidden_layers} layers")

    # ------------------------------------------------------------------ what the modeling code asks
    @property
    def rope_dims(self) -> int:
        return round(self.rope_parameters["partial_rotary_factor"] * self.head_dim)

    def attn_spec(self, i: int) -> tuple[int, int, int, float, int]:
        """``(n_head, n_kv_head, rope_dims, rope_theta, window)`` of layer ``i`` (window -1 = full)."""
        if self.layer_types[i] == LAYER_SLIDING:
            return (self.sliding_num_attention_heads, self.sliding_num_key_value_heads, self.rope_dims,
                    float(self.rope_parameters["rope_theta"]), int(self.sliding_window))
        return (self.num_attention_heads, self.num_key_value_heads, 0, 0.0, -1)

    def res_block_starts(self) -> list[int]:
        """The layers after layer 0 that open an AttnRes block ([] without AttnRes)."""
        S = self.attn_res_block
        return list(range(S, self.num_hidden_layers, S)) if S > 0 else []

    def block_full(self, i: int) -> int:
        """The full layer whose cache and key selection sparse layer ``i`` uses."""
        return max(j for j in range(i) if self.layer_types[j] == LAYER_FULL)

    def selects_keys(self, i: int) -> bool:
        """True for a full layer that at least one sparse layer reads."""
        return any(t == LAYER_SPARSE and self.block_full(j) == i for j, t in enumerate(self.layer_types) if j > i)

    @property
    def engram_rows_per_page(self) -> int:
        return rows_per_page(self.engram_head_dim, page=self.engram_page_bytes)

    @property
    def engram_table_rows(self) -> int:
        """Rows of the whole engram table (every order and head)."""
        return len(self.engram_orders) * self.engram_pages * self.engram_rows_per_page


__all__ = ["EmblaConfig", "LAYER_TYPES", "LAYER_SLIDING", "LAYER_FULL", "LAYER_SPARSE", "MLP_LAYER_TYPES",
           "MLP_DENSE", "MLP_SPARSE", "rows_per_page", "two_half_layer_types"]

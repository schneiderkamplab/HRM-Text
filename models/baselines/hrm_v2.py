"""Opt-in HRM v2: invocation gates and reference k-of-n expert mixtures."""

import copy
import math
from typing import Literal

import torch
from torch import nn
from torch.nn import functional as F
from pydantic import Field, model_validator

from models.baselines.hrm_nocarry_bp_warmup import (
    HierarchicalReasoningModel as Baseline,
    HierarchicalReasoningModelConfig as BaselineConfig,
)
from models.module_learning_rates import backward_call_counts
from models.expert_mixtures import TopKRouter, install_mlp_mixtures
from models.residual_branches import BranchedTransformer
from models.recurrent_memory import RecurrentMemory
from models.ngram_memory import NGramMemory


class GateConfig(BaselineConfig):
    gates_enabled: bool = False
    gate_alpha_max: float = Field(default=1.0, ge=0, le=1)
    gate_warmup_start_step: int = Field(default=0, ge=0)
    gate_warmup_steps: int = Field(default=2000, ge=0)
    gate_initialize_from_v1: bool = False
    moe_num_experts: int = Field(default=1, ge=1)
    moe_top_k: int = Field(default=1, ge=1)
    moe_levels: Literal["L", "H", "both"] = "L"
    mos_num_experts: int = Field(default=1, ge=1)
    mos_top_k: int = Field(default=1, ge=1)
    mos_state_mode: Literal["shared", "separate"] = "shared"
    expert_freeze_base: bool = False
    router_top1_straight_through: bool = True
    residual_branches: int = Field(default=1, ge=1)
    residual_levels: Literal["L", "H", "both"] = "both"
    residual_alpha_max: float = Field(default=1.0, ge=0, le=1)
    residual_warmup_start_step: int = Field(default=0, ge=0)
    residual_warmup_steps: int = Field(default=0, ge=0)
    residual_write_init_scale: float = Field(default=0.1, ge=0)
    residual_input_dependent: bool = False
    upcycle_from_dense: bool = False
    moe_sparse: bool = False
    mos_sparse: bool = False
    mos_sparse_routing: Literal['first_token', 'prefix_mean'] = 'first_token'
    h_memory_branches: int = Field(default=1, ge=1)
    l_memory_branches: int = Field(default=1, ge=1)
    memory_warmup_steps: int = Field(default=2000, ge=0)
    memory_warmup_start_step: int = Field(default=0, ge=0)
    ngram_orders: list[int] = Field(default_factory=list)
    ngram_buckets: int = Field(default=4096, ge=2)
    ngram_warmup_steps: int = Field(default=2000, ge=0)
    ngram_warmup_start_step: int = Field(default=0, ge=0)
    moe_metadata_bias: list[list[float]] = Field(default_factory=list)
    mos_metadata_bias: list[list[float]] = Field(default_factory=list)
    routing_bias_decay_start: int = Field(default=0, ge=0)
    routing_bias_decay_end: int = Field(default=0, ge=0)
    specialist_training: bool = False
    specialist_router_calibration: bool = False

    @model_validator(mode="after")
    def validate_experts(self):
        if self.mos_sparse and self.mos_sparse_routing == 'prefix_mean' and self.attn_type != 'prefixlm':
            raise ValueError('Prefix-mean routing requires PrefixLM prompt visibility')
        for field, count in ((self.moe_metadata_bias, self.moe_num_experts),
                             (self.mos_metadata_bias, self.mos_num_experts)):
            if any(len(row) != count or not all(math.isfinite(v) for v in row) for row in field):
                raise ValueError('Metadata bias rows must contain one finite logit per expert')
        if self.routing_bias_decay_end and self.routing_bias_decay_end <= self.routing_bias_decay_start:
            raise ValueError('Routing bias decay end must follow start')
        if self.specialist_training and not self.expert_freeze_base:
            raise ValueError('Specialist training requires a frozen reference expert')
        if self.mos_state_mode == 'separate' and self.l_memory_branches > 1:
            raise ValueError('Choose expert-specific L states or general L memory branches, not both')
        if self.upcycle_from_dense and self.gate_initialize_from_v1:
            raise ValueError('Use only one migration mode')
        if self.gate_initialize_from_v1 and not self.gates_enabled:
            raise ValueError("gate_initialize_from_v1 requires gates_enabled=true")
        if self.moe_top_k > self.moe_num_experts or self.mos_top_k > self.mos_num_experts:
            raise ValueError("Expert top_k must not exceed num_experts")
        if self.gate_initialize_from_v1 and (self.moe_num_experts > 1 or self.mos_num_experts > 1
                                           or self.residual_branches > 1):
            raise ValueError("Expert/branch upcycling requires upcycle_from_dense; "
                             "gate_initialize_from_v1 only migrates gates")
        if self.residual_branches > 1:
            for level in ("L", "H"):
                norm = self.H_override.get('norm_type', self.norm_type) if level == "H" else self.norm_type
                if self.residual_levels in (level, "both") and norm != "pre":
                    raise ValueError("Multiple residual branches currently require pre-norm")
        if self.expert_freeze_base and self.moe_num_experts == self.mos_num_experts == 1:
            raise ValueError("expert_freeze_base requires an expert mixture")
        return self


class InvocationGate(nn.Module):
    def __init__(self, hidden_size):
        super().__init__()
        # Direct allocation avoids consuming RNG before baseline head initialization.
        self.weight = nn.Parameter(torch.zeros(hidden_size, 2 * hidden_size))
        self.bias = nn.Parameter(torch.zeros(hidden_size))

    def forward(self, hidden, injection, alpha):
        hidden, injection = torch.broadcast_tensors(hidden, injection)
        inputs = torch.cat((hidden, injection), dim=-1)
        gate = F.linear(inputs, self.weight.to(inputs.dtype), self.bias.to(inputs.dtype))
        return injection * (1 + alpha.to(inputs.dtype) * torch.tanh(gate))


class HierarchicalReasoningModel(Baseline):
    def __init__(self, config_dict):
        config = GateConfig(**config_dict)
        if config.H_cycles < 1 or config.L_cycles < 1:
            raise ValueError("HRM v2 requires positive H/L cycles")
        super().__init__(config_dict)
        self.gate_config = config
        options = dict(freeze_base=config.expert_freeze_base,
                       top1_straight_through=config.router_top1_straight_through)
        for name in ("L", "H"):
            level = getattr(self, f"{name}_level")
            if config.moe_levels in (name, "both"):
                install_mlp_mixtures(level.core, self.hidden_size,
                                     config.moe_num_experts, config.moe_top_k, sparse=config.moe_sparse, **options)
                if config.moe_num_experts > 1:
                    from models.routed_block import RoutedBlock
                    norm = config.H_override.get('norm_type', config.norm_type) if name == 'H' else config.norm_type
                    level.core.layers = nn.ModuleList(RoutedBlock(block, norm) for block in level.core.layers)
            if config.residual_branches > 1 and config.residual_levels in (name, "both"):
                level.core = BranchedTransformer(level.core, config.residual_branches,
                                                 config.residual_write_init_scale, config.residual_input_dependent)
                level.create_cache = level.core.create_cache
        if config.mos_num_experts > 1:
            self.L_level.stack_experts = nn.ModuleList(
                copy.deepcopy(self.L_level.core) for _ in range(config.mos_num_experts - 1)
            )
            self.L_level.stack_router = TopKRouter(self.hidden_size, config.mos_num_experts,
                                                  config.mos_top_k, **options)
            if config.expert_freeze_base:
                self.L_level.core.requires_grad_(False)
            self.create_cache = self._create_expert_cache
        if config.gates_enabled:
            self.H_level.invocation_gates = nn.ModuleList(
                InvocationGate(self.hidden_size) for _ in range(self.H_cycles)
            )
            self.L_level.invocation_gates = nn.ModuleList(
                InvocationGate(self.hidden_size) for _ in range(self.H_cycles * self.L_cycles)
            )
            # Persist effective alpha so inference uses the checkpoint's strength.
            self.register_buffer("gate_alpha", torch.tensor(0.0))
        for name, branches in (('H', config.h_memory_branches), ('L', config.l_memory_branches)):
            if branches > 1:
                getattr(self, f'{name}_level').memory = RecurrentMemory(branches, self.hidden_size)
        if config.moe_metadata_bias or config.mos_metadata_bias:
            self.register_buffer('routing_bias_scale', torch.tensor(1.0))
        self.ngram_enabled = bool(config.ngram_orders)
        if self.ngram_enabled:
            self.ngram = NGramMemory(self.hidden_size, config.ngram_orders, config.ngram_buckets)
            self._attention_create_cache = self.create_cache
            self.create_cache = self._create_ngram_cache
        if (config.ngram_orders or config.h_memory_branches > 1 or config.l_memory_branches > 1
                or config.moe_sparse or config.mos_sparse or config.residual_input_dependent):
            from models.transformer import TransformerBlock
            for module in self.modules():
                if isinstance(module, TransformerBlock):
                    module._v2_explicit_checkpoint = True

    def _create_ngram_cache(self, **kwargs):
        return self._attention_create_cache(**kwargs) | {'ngram_history': {}}

    def _metadata_bias(self, category, kind):
        values = getattr(self.gate_config, f'{kind}_metadata_bias')
        if not self.training or self.gate_config.specialist_router_calibration or category is None or not values:
            return None
        table = torch.tensor(values, device=category.device, dtype=torch.float32)
        return table[category.long()] * self.routing_bias_scale

    def _create_expert_cache(self, **kwargs):
        cores = [self.L_level.core, *self.L_level.stack_experts]
        result = dict(H=[self.H_level.create_cache(**kwargs) for _ in range(self.H_cycles)],
                    L=[[core.create_cache(**kwargs) for core in cores]
                       for _ in range(self.H_cycles * self.L_cycles)])
        if self.gate_config.mos_sparse:
            result['mos_routes'] = torch.zeros(kwargs['max_batch_size'], len(cores),
                                               device=kwargs.get('device'), dtype=torch.float32)
        return result

    def _inject(self, level, invocation, hidden, other):
        if not self.gate_config.gates_enabled:
            return other
        return level.invocation_gates[invocation](hidden, other, self.gate_alpha)

    def _stack_step(self, z_L, z_H, states, invocation, cache, diagnostics, seq_info, bias=None):
        # Route token-locally, but run each attention stack on complete sequences.
        # This mixes full-context outputs; it never prunes tokens from attention.
        weights = self.L_level.stack_router(z_L + z_H, bias)
        output = torch.zeros_like(z_H)
        next_states = []
        for index, core in enumerate([self.L_level.core, *self.L_level.stack_experts]):
            previous = states[index] if states is not None else z_L
            injection = self._inject(self.L_level, invocation, previous, z_H)
            y = core(previous + injection, **seq_info,
                     cache=cache[index] if cache is not None else None,
                     stability_diagnostics=diagnostics,
                     stability_scope=f"L/cycle_{invocation:03d}/expert_{index}" if diagnostics is not None else None)
            weight = weights[..., index:index + 1]
            output = output + weight.to(y.dtype) * y
            if states is not None:
                # Inactive states are held, even though their candidate outputs
                # are computed to keep caches and distributed execution coherent.
                next_states.append(torch.where(weight > 0, y, previous))
        return output, next_states if states is not None else None

    def forward(self, carry, x, cache=None, bp_steps=2, stability_diagnostics=None, **seq_info):
        category = seq_info.pop('routing_category', None)
        if self.ngram_enabled:
            x = self.ngram(x, seq_info.pop('token_ids'), seq_info.get('position_ids'),
                           cache['ngram_history'] if cache is not None else None)
        if (not self.gate_config.gates_enabled and self.gate_config.moe_num_experts == 1
                and self.gate_config.mos_num_experts == 1 and self.gate_config.residual_branches == 1
                and self.gate_config.h_memory_branches == self.gate_config.l_memory_branches == 1):
            return super().forward(carry, x, cache=cache, bp_steps=bp_steps,
                                   stability_diagnostics=stability_diagnostics, **seq_info)
        z_H, z_L = x, self.zL_init
        memories = {}
        for name, value in (('H', z_H), ('L', z_L)):
            memory = getattr(getattr(self, f'{name}_level'), 'memory', None)
            if memory is not None:
                memories[name] = memory.initialize(value.expand_as(x))
        moe_bias, mos_bias = self._metadata_bias(category, 'moe'), self._metadata_bias(category, 'mos')
        level_info = {name: dict(seq_info) for name in ('L', 'H')}
        for name in ('L', 'H'):
            if moe_bias is not None and self.gate_config.moe_levels in (name, 'both'):
                level_info[name]['routing_bias'] = moe_bias
        mixture = self.gate_config.mos_num_experts > 1
        if mixture and self.gate_config.mos_sparse:
            from models.sparse_stacks import sequence_routes, sparse_stack_step, cached_sequence_routes, batched_sparse_stack_step
            if cache is not None:
                routes = cached_sequence_routes(self, x, cache, seq_info, mos_bias)
            else:
                routes = sequence_routes(self.L_level.stack_router, x, seq_info, mos_bias,
                                         self.gate_config.mos_sparse_routing)
        states = ([self.zL_init] * self.gate_config.mos_num_experts
                  if mixture and self.gate_config.mos_state_mode == "separate" else None)
        h_bp, l_bp = backward_call_counts(self.H_cycles, self.L_cycles, bp_steps)
        for i in range(self.H_cycles):
            for k in range(i * self.L_cycles, (i + 1) * self.L_cycles):
                with torch.set_grad_enabled(torch.is_grad_enabled() and k >= self.H_cycles * self.L_cycles - l_bp):
                    if 'L' in memories:
                        z_L = self.L_level.memory.read_state(memories['L'])
                    if mixture:
                        if self.gate_config.mos_sparse:
                            if cache is not None or x.ndim == 3:
                                z_L, states = batched_sparse_stack_step(
                                    self, z_L, z_H, states, k, stability_diagnostics, level_info['L'], routes,
                                    cache['L'][k] if cache is not None else None)
                            else:
                                z_L, states = sparse_stack_step(self, z_L, z_H, states, k,
                                                               stability_diagnostics, level_info['L'], routes)
                        else:
                            z_L, states = self._stack_step(
                                z_L, z_H, states, k, cache['L'][k] if cache is not None else None,
                                stability_diagnostics, level_info['L'], mos_bias)
                    else:
                        injection = self._inject(self.L_level, k, z_L, z_H)
                        z_L = self.L_level(
                            z_L, injection, **level_info['L'],
                            cache=cache["L"][k] if cache is not None else None,
                            stability_diagnostics=stability_diagnostics,
                            stability_scope=f"L/cycle_{k:03d}" if stability_diagnostics is not None else None,
                        )
                    if 'L' in memories:
                        memories['L'] = self.L_level.memory.update(memories['L'], z_L)
                        z_L = self.L_level.memory.read_state(memories['L'])
            with torch.set_grad_enabled(torch.is_grad_enabled() and i >= self.H_cycles - h_bp):
                if 'H' in memories:
                    z_H = self.H_level.memory.read_state(memories['H'])
                injection = self._inject(self.H_level, i, z_H, z_L)
                z_H = self.H_level(
                    z_H, injection, **level_info['H'],
                    cache=cache["H"][i] if cache is not None else None,
                    stability_diagnostics=stability_diagnostics,
                    stability_scope=f"H/cycle_{i:03d}" if stability_diagnostics is not None else None,
                )
                if 'H' in memories:
                    memories['H'] = self.H_level.memory.update(memories['H'], z_H)
                    z_H = self.H_level.memory.read_state(memories['H'])
        return None, z_H

    def compute_train_extra_args(self, train_state):
        config = self.gate_config
        if hasattr(self, 'routing_bias_scale'):
            start, end = config.routing_bias_decay_start, config.routing_bias_decay_end
            self.routing_bias_scale.fill_(max(0., min(1., (end - train_state.step) / (end - start))) if end else 1.)
        for name in ('H', 'L'):
            memory = getattr(getattr(self, f'{name}_level'), 'memory', None)
            if memory is not None:
                elapsed = max(0, train_state.step - config.memory_warmup_start_step)
                memory.alpha.fill_(min(1., elapsed / config.memory_warmup_steps) if config.memory_warmup_steps else 1.)
        if self.ngram_enabled:
            elapsed = max(0, train_state.step - config.ngram_warmup_start_step)
            self.ngram.alpha.fill_(min(1., elapsed / config.ngram_warmup_steps) if config.ngram_warmup_steps else 1.)
        elapsed = max(0, train_state.step - config.gate_warmup_start_step)
        fraction = min(1.0, elapsed / config.gate_warmup_steps) if config.gate_warmup_steps else 1.0
        if config.gates_enabled:
            self.gate_alpha.fill_(config.gate_alpha_max * fraction)
        if config.residual_branches > 1:
            elapsed = max(0, train_state.step - config.residual_warmup_start_step)
            fraction = min(1.0, elapsed / config.residual_warmup_steps) if config.residual_warmup_steps else 1.0
            for module in self.modules():
                if isinstance(module, BranchedTransformer):
                    module.residual_alpha.fill_(config.residual_alpha_max * fraction)
        return super().compute_train_extra_args(train_state)

    def configure_gate_updates(self, optimizer, bp_steps):
        """Rebuild runtime-only donor mapping; optimizer state itself is checkpointed."""
        h_bp, l_bp = backward_call_counts(self.H_cycles, self.L_cycles, bp_steps)
        pairs = {}
        if not self.gate_config.gates_enabled:
            optimizer.shared_parameter_updates = pairs
            return
        for level, active_count in ((self.H_level, h_bp), (self.L_level, l_bp)):
            first_active = len(level.invocation_gates) - active_count
            donor = level.invocation_gates[first_active]
            if not any(p.requires_grad for p in donor.parameters()):
                continue
            for gate in level.invocation_gates[:first_active]:
                pairs.update(zip(gate.parameters(), donor.parameters()))
        optimizer.shared_parameter_updates = pairs

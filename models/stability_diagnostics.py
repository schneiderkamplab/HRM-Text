from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import fcntl
import json
import math
import os
from pathlib import Path
from typing import Iterable, Optional

import torch
import torch.distributed as dist
from torch import Tensor, nn

from models.common import WrappedTensor, prepare_prefixlm_batch, unwrap_tensor, wrap_tensor
from models.flash_attention_prefixlm_common import PREFIXLM_PREPARED_KEYS


@dataclass
class _Moments:
    total: Tensor
    total_sq: Tensor
    count: Tensor
    nonfinite: Tensor
    max_abs: Tensor


@dataclass
class _PairMoments:
    dot: Tensor
    left_sq: Tensor
    right_sq: Tensor
    count: Tensor


def _local_tensor(value: Tensor) -> Tensor:
    to_local = getattr(value, "to_local", None)
    if callable(to_local):
        value = to_local()
    return value


def _parameter_group(name: str) -> str:
    parts = name.split(".")
    try:
        layer_pos = parts.index("layers")
        return "/".join(parts[:layer_pos] + ["layers", parts[layer_pos + 1]])
    except (ValueError, IndexError):
        return "/".join(parts[:-1] or parts)


def diagnostic_prefixlm_batch(
    batch: dict[str, Tensor | WrappedTensor], *, max_tokens: int
) -> dict[str, Tensor | WrappedTensor]:
    """Keep complete leading packed sequences within a diagnostic token budget."""
    if max_tokens < 1:
        raise ValueError("Diagnostic token budget must be positive")

    numseqs = int(unwrap_tensor(batch["numseqs"]).item())
    cu_seqlens = unwrap_tensor(batch["cu_seqlens"])
    sequence_ends = cu_seqlens[1 : numseqs + 1]
    within_budget = int((sequence_ends <= max_tokens).sum().item())
    selected_sequences = max(1, within_budget)
    token_count = int(sequence_ends[selected_sequences - 1].item())

    active_prefix_lens = unwrap_tensor(batch["prefix_lens"])[:selected_sequences]
    prefix_lens = torch.nn.functional.pad(active_prefix_lens, (0, 1))
    causal_lens = unwrap_tensor(batch["causal_lens"])[:selected_sequences]
    total_lens = active_prefix_lens + causal_lens
    sliced = {
        key: value
        for key, value in batch.items()
        if key not in PREFIXLM_PREPARED_KEYS
    }
    for key in ("inputs", "labels", "position_ids"):
        sliced[key] = unwrap_tensor(batch[key])[:token_count]
    sliced["prefix_lens"] = prefix_lens
    sliced["causal_lens"] = causal_lens
    sliced["cu_seqlens"] = cu_seqlens[: selected_sequences + 1]
    sliced.update(
        {
            "total_seqlen": wrap_tensor(torch.tensor(token_count, device="cpu")),
            "numseqs": wrap_tensor(torch.tensor(selected_sequences, device="cpu")),
            "max_seqlen_prefix": wrap_tensor(active_prefix_lens.max().detach().cpu()),
            "max_seqlen_causal": wrap_tensor(causal_lens.max().detach().cpu()),
            "max_seqlen_all": wrap_tensor(total_lens.max().detach().cpu()),
        }
    )
    return prepare_prefixlm_batch(sliced)


class StabilityDiagnostics:
    """Collect expensive stability diagnostics for explicitly selected steps.

    The object stores only scalar reductions, not activation tensors. It must
    never be constructed or passed through the model on ordinary training
    steps; this keeps the disabled path free of hooks and diagnostic kernels.
    """

    _MAX_STAT_ELEMENTS = 1 << 20

    def __init__(
        self,
        *,
        step: int,
        rank: int,
        output_path: str,
        context: Optional[dict[str, object]] = None,
    ) -> None:
        self.step = step
        self.rank = rank
        self.output_path = output_path
        self.context = context or {}
        self._moments: dict[str, list[_Moments]] = defaultdict(list)
        self._pairs: dict[str, list[_PairMoments]] = defaultdict(list)
        self.wandb_summary: dict[str, float] = {}
        self.wandb_detailed: dict[str, float] = {}

    @classmethod
    def _bounded_sample(cls, value: Tensor) -> Tensor:
        """Return a deterministic strided view bounded before any dtype conversion."""
        value = _local_tensor(value.detach())
        if value.numel() <= cls._MAX_STAT_ELEMENTS:
            return value

        sample = value
        for dim in range(sample.ndim):
            if sample.numel() <= cls._MAX_STAT_ELEMENTS:
                break
            other_elements = sample.numel() // sample.shape[dim]
            keep = max(1, cls._MAX_STAT_ELEMENTS // max(other_elements, 1))
            stride = max(1, math.ceil(sample.shape[dim] / keep))
            slices = [slice(None)] * sample.ndim
            slices[dim] = slice(None, None, stride)
            sample = sample[tuple(slices)]

        if sample.numel() > cls._MAX_STAT_ELEMENTS:
            sample = sample.reshape(-1)[: cls._MAX_STAT_ELEMENTS]
        return sample

    @classmethod
    def _finite_values(cls, value: Tensor) -> tuple[Tensor, Tensor, Tensor]:
        value = cls._bounded_sample(value).to(torch.float32)
        finite = torch.isfinite(value)
        safe = torch.where(finite, value, torch.zeros_like(value))
        return safe, finite, value

    def record_tensor(self, name: str, value: Tensor, *, record_gradient: bool = False) -> None:
        with torch.no_grad():
            safe, finite, original = self._finite_values(value)
            count = finite.sum(dtype=torch.float32)
            finite_abs = torch.where(finite, original.abs(), torch.zeros_like(original))
            self._moments[name].append(
                _Moments(
                    total=safe.sum(dtype=torch.float32),
                    total_sq=(safe * safe).sum(dtype=torch.float32),
                    count=count,
                    nonfinite=(~finite).sum(dtype=torch.float32),
                    max_abs=(finite_abs.amax() if finite_abs.numel() else safe.new_zeros(())),
                )
            )

        if record_gradient and value.requires_grad:
            value.register_hook(
                lambda gradient, metric_name=f"gradient/{name}": self._record_gradient(
                    metric_name, gradient
                )
            )

    def _record_gradient(self, name: str, gradient: Tensor) -> Tensor:
        self.record_tensor(name, gradient)
        return gradient

    def record_pair(self, name: str, left: Tensor, right: Tensor) -> None:
        with torch.no_grad():
            left, right = torch.broadcast_tensors(
                _local_tensor(left.detach()), _local_tensor(right.detach())
            )
            left = self._bounded_sample(left).to(torch.float32)
            right = self._bounded_sample(right).to(torch.float32)
            finite = torch.isfinite(left) & torch.isfinite(right)
            left = torch.where(finite, left, torch.zeros_like(left))
            right = torch.where(finite, right, torch.zeros_like(right))
            self._pairs[name].append(
                _PairMoments(
                    dot=(left * right).sum(dtype=torch.float32),
                    left_sq=(left * left).sum(dtype=torch.float32),
                    right_sq=(right * right).sum(dtype=torch.float32),
                    count=finite.sum(dtype=torch.float32),
                )
            )

    def record_last_dim_rms(self, name: str, value: Tensor) -> None:
        with torch.no_grad():
            value = _local_tensor(value.detach()).to(torch.float32)
            rms = torch.linalg.vector_norm(value, dim=-1) / math.sqrt(value.shape[-1])
        self.record_tensor(name, rms)

    def record_fraction(self, name: str, condition: Tensor) -> None:
        self.record_tensor(name, condition.detach().to(torch.float32))

    def record_model_state(self, model: nn.Module, optimizer: torch.optim.Optimizer) -> None:
        parameter_names = {id(parameter): name for name, parameter in model.named_parameters()}
        for name, parameter in model.named_parameters():
            group = _parameter_group(name)
            self.record_tensor(f"parameter/{group}/value", parameter)
            if parameter.grad is not None:
                self.record_tensor(f"parameter/{group}/grad", parameter.grad)

        for parameter, state in optimizer.state.items():
            name = parameter_names.get(id(parameter))
            if name is None:
                continue
            group = _parameter_group(name)
            for state_name in ("exp_avg", "exp_avg_sq", "param_ema"):
                value = state.get(state_name)
                if torch.is_tensor(value) and value.is_floating_point():
                    self.record_tensor(f"optimizer/{group}/{state_name}", value)

    @staticmethod
    def _sum_moments(values: Iterable[_Moments]) -> _Moments:
        values = list(values)
        return _Moments(
            total=torch.stack([value.total for value in values]).sum(),
            total_sq=torch.stack([value.total_sq for value in values]).sum(),
            count=torch.stack([value.count for value in values]).sum(),
            nonfinite=torch.stack([value.nonfinite for value in values]).sum(),
            max_abs=torch.stack([value.max_abs for value in values]).amax(),
        )

    @staticmethod
    def _sum_pairs(values: Iterable[_PairMoments]) -> _PairMoments:
        values = list(values)
        return _PairMoments(
            dot=torch.stack([value.dot for value in values]).sum(),
            left_sq=torch.stack([value.left_sq for value in values]).sum(),
            right_sq=torch.stack([value.right_sq for value in values]).sum(),
            count=torch.stack([value.count for value in values]).sum(),
        )

    @staticmethod
    def _check_distributed_keys(keys: list[str]) -> None:
        if not (dist.is_available() and dist.is_initialized()):
            return
        gathered: list[Optional[list[str]]] = [None] * dist.get_world_size()
        dist.all_gather_object(gathered, keys)
        if any(rank_keys != keys for rank_keys in gathered):
            raise RuntimeError("Stability diagnostic keys differ across distributed ranks")

    def finalize(self, *, detailed_wandb: bool = False) -> dict[str, object]:
        moment_keys = sorted(self._moments)
        pair_keys = sorted(self._pairs)
        self._check_distributed_keys(moment_keys + [f"pair:{key}" for key in pair_keys])

        detailed: dict[str, float] = {}
        if moment_keys:
            local_moments = [self._sum_moments(self._moments[name]) for name in moment_keys]
            sums = torch.stack(
                [
                    torch.stack([value.total, value.total_sq, value.count, value.nonfinite])
                    for value in local_moments
                ]
            )
            maxima = torch.stack([value.max_abs for value in local_moments])
            if dist.is_available() and dist.is_initialized():
                dist.all_reduce(sums, op=dist.ReduceOp.SUM)
                dist.all_reduce(maxima, op=dist.ReduceOp.MAX)
            host_sums = sums.cpu().tolist()
            host_maxima = maxima.cpu().tolist()
        else:
            host_sums = []
            host_maxima = []

        for name, values, maximum_value in zip(moment_keys, host_sums, host_maxima):
            total, total_sq, count, nonfinite = (float(item) for item in values)
            denominator = max(count, 1.0)
            mean = total / denominator
            rms = math.sqrt(max(total_sq / denominator, 0.0))
            variance = max(total_sq / denominator - mean * mean, 0.0)
            all_count = count + nonfinite
            detailed[f"{name}/mean"] = mean
            detailed[f"{name}/rms"] = rms
            detailed[f"{name}/std"] = math.sqrt(variance)
            detailed[f"{name}/max_abs"] = maximum_value
            detailed[f"{name}/nonfinite_fraction"] = nonfinite / max(all_count, 1.0)

        if pair_keys:
            local_pairs = [self._sum_pairs(self._pairs[name]) for name in pair_keys]
            pair_sums = torch.stack(
                [
                    torch.stack([value.dot, value.left_sq, value.right_sq, value.count])
                    for value in local_pairs
                ]
            )
            if dist.is_available() and dist.is_initialized():
                dist.all_reduce(pair_sums, op=dist.ReduceOp.SUM)
            host_pair_sums = pair_sums.cpu().tolist()
        else:
            host_pair_sums = []

        for name, values in zip(pair_keys, host_pair_sums):
            dot, left_sq, right_sq, _count = (float(item) for item in values)
            detailed[f"pair/{name}/cosine"] = dot / max(math.sqrt(left_sq * right_sq), 1e-30)

        self._add_derived_metrics(detailed)
        summary = self._summarize(detailed)
        record: dict[str, object] = {
            "schema_version": 1,
            "step": self.step,
            "world_size": dist.get_world_size() if dist.is_available() and dist.is_initialized() else 1,
            "context": self.context,
            "summary": summary,
            "metrics": detailed,
        }
        if self.rank == 0:
            self._append_locked(record)

        self.wandb_summary = {f"stability/{key}": value for key, value in summary.items()}
        if detailed_wandb:
            self.wandb_detailed = {
                f"stability_detail/{key}": value for key, value in detailed.items()
            }
        self._moments.clear()
        self._pairs.clear()
        return record

    @staticmethod
    def _add_derived_metrics(metrics: dict[str, float]) -> None:
        suffix_pairs = {
            "gradient_gain": ("gradient/activation/{base}/input/rms", "gradient/activation/{base}/output/rms"),
            "attn_residual_ratio": ("activation/{base}/attn_residual/rms", "activation/{base}/input/rms"),
            "mlp_residual_ratio": ("activation/{base}/mlp_residual/rms", "activation/{base}/post_attn/rms"),
        }
        block_bases = {
            key.removeprefix("activation/").removesuffix("/input/rms")
            for key in metrics
            if key.startswith("activation/") and key.endswith("/input/rms") and "/layer_" in key
        }
        for base in block_bases:
            for derived_name, (numerator_pattern, denominator_pattern) in suffix_pairs.items():
                numerator = metrics.get(numerator_pattern.format(base=base))
                denominator = metrics.get(denominator_pattern.format(base=base))
                if numerator is not None and denominator is not None:
                    metrics[f"derived/{base}/{derived_name}"] = numerator / max(denominator, 1e-30)

        recurrent_bases = {
            key.removeprefix("recurrent/").removesuffix("/hidden/rms")
            for key in metrics
            if key.startswith("recurrent/") and key.endswith("/hidden/rms")
        }
        for base in recurrent_bases:
            hidden = metrics[f"recurrent/{base}/hidden/rms"]
            injection = metrics.get(f"recurrent/{base}/injection/rms")
            if injection is not None:
                metrics[f"derived/recurrent/{base}/injection_ratio"] = injection / max(hidden, 1e-30)
            gradient_input = metrics.get(f"gradient/recurrent/{base}/combined/rms")
            gradient_output = metrics.get(f"gradient/recurrent/{base}/output/rms")
            if gradient_input is not None and gradient_output is not None:
                metrics[f"derived/recurrent/{base}/gradient_gain"] = gradient_input / max(
                    gradient_output, 1e-30
                )

    @staticmethod
    def _summarize(metrics: dict[str, float]) -> dict[str, float]:
        def maximum(fragment: str, *, default: float = 0.0) -> float:
            values = [value for key, value in metrics.items() if fragment in key]
            return max(values, default=default)

        alignment_values = [
            value
            for key, value in metrics.items()
            if key.startswith("pair/") and key.endswith("_input_residual/cosine")
        ]

        return {
            "activation_max_abs": max(
                (
                    value
                    for key, value in metrics.items()
                    if key.startswith(("activation/", "recurrent/")) and key.endswith("max_abs")
                ),
                default=0.0,
            ),
            "activation_nonfinite_fraction_max": max(
                (
                    value
                    for key, value in metrics.items()
                    if key.startswith(("activation/", "recurrent/"))
                    and key.endswith("nonfinite_fraction")
                ),
                default=0.0,
            ),
            "gradient_max_abs": max(
                (value for key, value in metrics.items() if key.startswith("gradient/") and key.endswith("max_abs")),
                default=0.0,
            ),
            "gradient_nonfinite_fraction_max": max(
                (value for key, value in metrics.items() if key.startswith("gradient/") and key.endswith("nonfinite_fraction")),
                default=0.0,
            ),
            "block_gradient_gain_max": max(
                (
                    value
                    for key, value in metrics.items()
                    if key.startswith(("derived/H/", "derived/L/"))
                    and key.endswith("gradient_gain")
                ),
                default=0.0,
            ),
            "h_block_gradient_gain_max": max(
                (
                    value
                    for key, value in metrics.items()
                    if key.startswith("derived/H/") and key.endswith("gradient_gain")
                ),
                default=0.0,
            ),
            "l_block_gradient_gain_max": max(
                (
                    value
                    for key, value in metrics.items()
                    if key.startswith("derived/L/") and key.endswith("gradient_gain")
                ),
                default=0.0,
            ),
            "recurrent_gradient_gain_max": max(
                (
                    value
                    for key, value in metrics.items()
                    if key.startswith("derived/recurrent/") and key.endswith("gradient_gain")
                ),
                default=0.0,
            ),
            "residual_ratio_max": max(
                (value for key, value in metrics.items() if key.endswith("residual_ratio")),
                default=0.0,
            ),
            "recurrent_injection_ratio_max": maximum("injection_ratio", default=0.0),
            "residual_alignment_min": min(alignment_values, default=0.0),
            "residual_alignment_max": max(alignment_values, default=0.0),
            "attention_gate_near_zero_fraction_max": max(
                (
                    value
                    for key, value in metrics.items()
                    if key.endswith("attention/gate_near_zero/mean")
                ),
                default=0.0,
            ),
            "attention_gate_near_one_fraction_max": max(
                (
                    value
                    for key, value in metrics.items()
                    if key.endswith("attention/gate_near_one/mean")
                ),
                default=0.0,
            ),
            "parameter_grad_max_abs": max(
                (
                    value
                    for key, value in metrics.items()
                    if key.startswith("parameter/") and "/grad/max_abs" in key
                ),
                default=0.0,
            ),
        }

    def _append_locked(self, record: dict[str, object]) -> None:
        path = Path(self.output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        with path.open("a", encoding="utf-8") as output:
            fcntl.flock(output.fileno(), fcntl.LOCK_EX)
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
            fcntl.flock(output.fileno(), fcntl.LOCK_UN)

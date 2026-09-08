from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest
import torch
from torch.distributed._composable import checkpoint
from torch import nn

from models.layers import Attention, Cache, SwiGLU
from models.adam_atan2 import AdamATan2
from models.common import unwrap_tensor, wrap_tensor
from models.stability_diagnostics import StabilityDiagnostics, diagnostic_prefixlm_batch
from models.transformer import TransformerBlock, TransformerConfig
from pretrain import TrainState, train_accumulated_batches


class DiagnosticLinear(nn.Linear):
    def forward(self, value, **_kwargs):
        return super().forward(value)


def make_block() -> TransformerBlock:
    config = TransformerConfig(
        max_seq_len=8,
        n_layers=1,
        hidden_size=8,
        num_heads=1,
        expansion=1,
        attn_type="causal",
        init_type="lecun_normal",
        norm_type="pre",
        norm_eps=1e-6,
        pos_emb_type="none",
    )
    block = TransformerBlock(config)
    block.attn = DiagnosticLinear(8, 8, bias=False)
    block.mlp = DiagnosticLinear(8, 8, bias=False)
    return block


def test_diagnostics_preserve_block_outputs_and_gradients(tmp_path) -> None:
    baseline = make_block()
    instrumented = copy.deepcopy(baseline)
    baseline_input = torch.randn(3, 8, requires_grad=True)
    instrumented_input = baseline_input.detach().clone().requires_grad_(True)

    baseline_output = baseline(baseline_input)
    recorder = StabilityDiagnostics(step=10, rank=0, output_path=str(tmp_path / "stats.jsonl"))
    instrumented_output = instrumented(
        instrumented_input,
        stability_diagnostics=recorder,
        stability_scope="H/cycle_000/layer_000",
    )
    baseline_output.square().sum().backward()
    instrumented_output.square().sum().backward()
    recorder.finalize()

    torch.testing.assert_close(instrumented_output, baseline_output)
    torch.testing.assert_close(instrumented_input.grad, baseline_input.grad)
    for baseline_parameter, instrumented_parameter in zip(
        baseline.parameters(), instrumented.parameters()
    ):
        torch.testing.assert_close(instrumented_parameter.grad, baseline_parameter.grad)

    record = json.loads((tmp_path / "stats.jsonl").read_text().strip())
    assert record["step"] == 10
    assert "activation/H/cycle_000/layer_000/attn_residual/rms" in record["metrics"]
    assert "gradient/activation/H/cycle_000/layer_000/input/rms" in record["metrics"]
    assert "derived/H/cycle_000/layer_000/gradient_gain" in record["metrics"]


def test_model_and_optimizer_state_are_grouped_by_physical_layer(tmp_path) -> None:
    model = nn.Sequential(nn.Linear(4, 4, bias=False), nn.Linear(4, 2, bias=False))
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    model(torch.ones(2, 4)).sum().backward()
    optimizer.step()

    recorder = StabilityDiagnostics(step=1, rank=0, output_path=str(tmp_path / "stats.jsonl"))
    recorder.record_model_state(model, optimizer)
    record = recorder.finalize()

    metrics = record["metrics"]
    assert metrics["parameter/0/value/rms"] > 0
    assert metrics["parameter/1/grad/rms"] > 0
    assert metrics["optimizer/0/exp_avg/rms"] > 0
    assert metrics["optimizer/1/exp_avg_sq/rms"] > 0


def test_gradient_hook_is_identity(tmp_path) -> None:
    value = torch.tensor([2.0, -3.0], requires_grad=True)
    recorder = StabilityDiagnostics(step=1, rank=0, output_path=str(tmp_path / "stats.jsonl"))
    recorder.record_tensor("activation/test", value, record_gradient=True)
    (value.square().sum()).backward()
    recorder.finalize()

    assert value.grad is not None
    assert value.grad.tolist() == pytest.approx([4.0, -6.0])


def test_large_tensor_statistics_are_bounded_before_conversion(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(StabilityDiagnostics, "_MAX_STAT_ELEMENTS", 16)
    recorder = StabilityDiagnostics(step=1, rank=0, output_path=str(tmp_path / "stats.jsonl"))
    value = torch.arange(100, dtype=torch.bfloat16).reshape(10, 10)

    sample = recorder._bounded_sample(value)
    recorder.record_tensor("activation/large", value)
    record = recorder.finalize()

    assert sample.numel() <= 16
    assert record["metrics"]["activation/large/rms"] > 0


def test_pair_statistics_support_broadcasted_inputs(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(StabilityDiagnostics, "_MAX_STAT_ELEMENTS", 16)
    recorder = StabilityDiagnostics(step=1, rank=0, output_path=str(tmp_path / "stats.jsonl"))
    recorder.record_pair("broadcast", torch.ones(3), torch.ones(10, 3))
    record = recorder.finalize()

    assert record["metrics"]["pair/broadcast/cosine"] == pytest.approx(1.0)


def test_diagnostic_prefixlm_batch_keeps_complete_sequences() -> None:
    batch = {
        "inputs": torch.arange(12),
        "labels": torch.arange(12),
        "position_ids": torch.arange(12),
        "prefix_lens": torch.tensor([2, 1]),
        "causal_lens": torch.tensor([4, 5]),
        "cu_seqlens": torch.tensor([0, 6, 12], dtype=torch.int32),
        "total_seqlen": wrap_tensor(torch.tensor(12)),
        "numseqs": wrap_tensor(torch.tensor(2)),
        "max_seqlen_prefix": wrap_tensor(torch.tensor(2)),
        "max_seqlen_causal": wrap_tensor(torch.tensor(5)),
        "max_seqlen_all": wrap_tensor(torch.tensor(6)),
    }

    sliced = diagnostic_prefixlm_batch(batch, max_tokens=7)

    assert sliced["inputs"].tolist() == list(range(6))
    assert int(unwrap_tensor(sliced["numseqs"]).item()) == 1
    assert int(unwrap_tensor(sliced["total_seqlen"]).item()) == 6
    assert sliced["cu_seqlens"].tolist() == [0, 6]
    assert sliced["prefix_lens"].tolist() == [2, 0]


def test_diagnostics_preserve_activation_checkpointing(tmp_path) -> None:
    baseline = make_block()
    checkpointed = copy.deepcopy(baseline)
    checkpoint(checkpointed)
    baseline_input = torch.randn(3, 8, requires_grad=True)
    checkpointed_input = baseline_input.detach().clone().requires_grad_(True)
    recorder = StabilityDiagnostics(step=2, rank=0, output_path=str(tmp_path / "stats.jsonl"))

    baseline_output = baseline(baseline_input)
    checkpointed_output = checkpointed(
        checkpointed_input,
        stability_diagnostics=recorder,
        stability_scope="L/cycle_005/layer_000",
    )
    baseline_output.sum().backward()
    checkpointed_output.sum().backward()
    recorder.finalize()

    torch.testing.assert_close(checkpointed_output, baseline_output)
    torch.testing.assert_close(checkpointed_input.grad, baseline_input.grad)
    for baseline_parameter, checkpointed_parameter in zip(
        baseline.parameters(), checkpointed.parameters()
    ):
        torch.testing.assert_close(checkpointed_parameter.grad, baseline_parameter.grad)


def test_attention_and_mlp_internal_probes(tmp_path) -> None:
    recorder = StabilityDiagnostics(step=3, rank=0, output_path=str(tmp_path / "stats.jsonl"))
    attention = Attention(
        hidden_size=8,
        head_dim=8,
        num_heads=1,
        num_key_value_heads=1,
        attn_type="causal",
        init_std_in=0.1,
        init_std_out=0.1,
    )
    hidden = torch.randn(2, 3, 8, requires_grad=True)
    cache = Cache.create(max_batch_size=2, max_seq_len=3, num_heads=1, head_dim=8)
    attention_output = attention(
        hidden,
        None,
        cache=cache,
        cache_lengths=torch.zeros(2, dtype=torch.long),
        stability_diagnostics=recorder,
        stability_scope="H/cycle_000/layer_000/attention",
    )
    mlp = SwiGLU(hidden_size=8, intermediate_size=16, init_std_in=0.1, init_std_out=0.1)
    output = mlp(
        attention_output,
        stability_diagnostics=recorder,
        stability_scope="H/cycle_000/layer_000/mlp",
    )
    output.sum().backward()
    record = recorder.finalize()

    metrics = record["metrics"]
    assert "activation/H/cycle_000/layer_000/attention/query/rms" in metrics
    assert "activation/H/cycle_000/layer_000/attention/aligned_qk_score/rms" in metrics
    assert "gradient/activation/H/cycle_000/layer_000/mlp/product/rms" in metrics


def test_shadow_replay_does_not_update_training_state(tmp_path) -> None:
    model = DiagnosticLinear(1, 1, bias=False)
    optimizer = AdamATan2(model.parameters(), lr=0.1, ema=0.9)
    state = TrainState(
        model=model,
        carry=None,
        optim=optimizer,
        step=7,
        total_steps=10,
        fwd_bwd_dtype=torch.float32,
        use_cuda_autocast=False,
    )
    parameter = next(model.parameters())
    optimizer_state = optimizer.state[parameter]
    before_parameter = parameter.detach().clone()
    before_optimizer = {
        key: value.clone() for key, value in optimizer_state.items() if torch.is_tensor(value)
    }
    config = SimpleNamespace(
        compile_train_batch_mode="default",
        fsdp_accumulation_sync_mode="no_sync",
        fsdp_shard_degree=None,
        gradient_clip_norm=None,
        gradient_skip_norm=None,
        resume_trace=False,
        stability_diagnostics_wandb_detailed=False,
    )
    recorder = StabilityDiagnostics(step=7, rank=0, output_path=str(tmp_path / "stats.jsonl"))
    batch = {
        "inputs": torch.ones(1, 1),
        "labels": torch.zeros(1, dtype=torch.long),
    }

    class LossWrapper(nn.Module):
        def __init__(self, inner):
            super().__init__()
            self.inner = inner

        def forward(self, *, batch, carry, **_kwargs):
            loss = self.inner(batch["inputs"]).sum()
            one = loss.detach().new_ones(())
            return carry, loss, {"loss": (loss.detach(), one)}

    state.model = LossWrapper(model)
    train_accumulated_batches(
        config,
        rank=0,
        train_state=state,
        batches=[batch],
        use_compiled=False,
        optimizer_step_enabled=False,
        stability_diagnostics=recorder,
    )

    assert parameter.grad is None
    assert torch.equal(parameter, before_parameter)
    for key, value in before_optimizer.items():
        assert torch.equal(optimizer_state[key], value)

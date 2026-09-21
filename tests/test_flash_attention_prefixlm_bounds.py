from importlib import import_module
from inspect import signature

import pytest
import torch

from models.common import prepare_prefixlm_batch, wrap_tensor
from models.flash_attention_prefixlm_common import (
    PREFIXLM_PREPARED_KEYS,
    PREFIXLM_ROUTING_KEYS,
    prefixlm_prepared_from_tensors,
    prefixlm_routing_from_tensors,
)
from models.layers import Attention
from models.transformer import TransformerConfig


def test_fa4_optimized_path_is_the_consistent_default() -> None:
    assert TransformerConfig.model_fields["prefixlm_fa4_impl"].default == "seqused"
    assert TransformerConfig.model_fields["prefixlm_fa4_grad_mask_impl"].default == "triton"
    assert TransformerConfig.model_fields["prefixlm_fa4_output_combine_impl"].default == "triton"
    assert signature(Attention).parameters["prefixlm_fa4_impl"].default == "seqused"
    assert signature(Attention).parameters["prefixlm_fa4_grad_mask_impl"].default == "triton"
    assert signature(Attention).parameters["prefixlm_fa4_output_combine_impl"].default == "triton"

    wrappers = (
        import_module("models.flash_attention_prefixlm_dispatch").flash_attn_varlen_prefixlm,
        import_module("models.flash_attention_prefixlm_v2").flash_attn_varlen_prefixlm,
    )
    for wrapper in wrappers:
        parameters = signature(wrapper).parameters
        assert parameters["fa4_impl"].default == "seqused"
        assert parameters["fa4_grad_mask_impl"].default == "triton"
        assert parameters["fa4_output_combine_impl"].default == "triton"

    fa4_parameters = signature(
        import_module("models.flash_attention_prefixlm_fa4").flash_attn_varlen_prefixlm
    ).parameters
    assert fa4_parameters["impl"].default == "seqused"
    assert fa4_parameters["grad_mask_impl"].default == "triton"
    assert fa4_parameters["output_combine_impl"].default == "triton"


def packed_inputs() -> tuple[torch.Tensor, ...]:
    return (
        torch.tensor([3, 7, 0], dtype=torch.int32),
        torch.tensor([2, 0, 0], dtype=torch.int32),
        torch.tensor([0, 5, 12], dtype=torch.int32),
        torch.tensor(12),
        torch.tensor(2),
        torch.tensor(7),
        torch.tensor(2),
        torch.tensor(7),
    )


@pytest.mark.parametrize("padding", [0, 1, 8])
def test_prepared_metadata_accepts_exact_and_padded_prefix_lengths(padding: int) -> None:
    prefix_lens, causal_lens, cu_seqlens, *scalars = packed_inputs()
    prefix_lens = torch.nn.functional.pad(prefix_lens[:2], (0, padding))

    prepared = prefixlm_prepared_from_tensors(
        prefix_lens, causal_lens[:2], cu_seqlens, *scalars
    )
    padded = prefixlm_prepared_from_tensors(*packed_inputs())

    assert prepared.keys() == padded.keys()
    for name in prepared:
        assert torch.equal(prepared[name], padded[name]), name
    assert prepared["cu_seqlens_shifted"].dtype == torch.int32
    assert prepared["cu_seqlens_shifted"].tolist() == [3, 12, 12]


@pytest.mark.parametrize(
    ("module_name", "kernel_name"),
    [
        ("models.flash_attention_prefixlm_fa4", "_fa4_varlen"),
        ("models.flash_attention_prefixlm_rocm", "_rocm_varlen"),
    ],
)
def test_causal_launch_reuses_batch_sequence_bounds(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    kernel_name: str,
) -> None:
    module = import_module(module_name)
    launches: list[dict[str, object]] = []

    def fake_varlen(q: torch.Tensor, _k: torch.Tensor, _v: torch.Tensor, **kwargs: object) -> torch.Tensor:
        launches.append(kwargs)
        return torch.zeros_like(q)

    monkeypatch.setattr(module, kernel_name, fake_varlen)

    # The prefix-only sequence makes max_seqlen_all a conservative upper bound
    # for the active causal launch (7 versus an exact active maximum of 5).
    prefix_lens, causal_lens, cu_seqlens, *scalars = packed_inputs()
    q = torch.randn(12, 2, 8)

    output = module.flash_attn_varlen_prefixlm(
        q,
        q,
        q,
        False,
        prefix_lens,
        causal_lens,
        cu_seqlens,
        *scalars,
    )

    assert output.shape == q.shape
    assert len(launches) == 2
    assert launches[1]["max_seqlen_q"] == 2
    assert launches[1]["max_seqlen_k"] == 7


def test_prepare_prefixlm_batch_is_complete_and_idempotent() -> None:
    prefix_lens, causal_lens, cu_seqlens, *scalars = packed_inputs()
    scalar_names = (
        "total_seqlen",
        "numseqs",
        "max_seqlen_prefix",
        "max_seqlen_causal",
        "max_seqlen_all",
    )
    batch = {
        "prefix_lens": prefix_lens,
        "causal_lens": causal_lens,
        "cu_seqlens": cu_seqlens,
        **{name: wrap_tensor(value) for name, value in zip(scalar_names, scalars, strict=True)},
    }

    prepared = prepare_prefixlm_batch(batch)

    assert all(name in prepared for name in PREFIXLM_PREPARED_KEYS)
    assert prepare_prefixlm_batch(prepared) is prepared
    assert torch.equal(prepared["prefix_idx"], torch.tensor([0, 1, 2, 5, 6, 7, 8, 9, 10, 11]))
    assert torch.equal(prepared["causal_idx"], torch.tensor([3, 4]))
    assert torch.equal(prepared["active_key_idx"], torch.tensor([0, 1, 2, 3, 4]))
    assert torch.equal(prepared["cu_seqlens_shifted"], torch.tensor([3, 12, 12]))
    assert torch.equal(
        prepared["prefix_mask"],
        torch.tensor([True, True, True, False, False, True, True, True, True, True, True, True]),
    )
    assert torch.equal(
        prepared["causal_mask"],
        torch.tensor([False, False, False, True, True, False, False, False, False, False, False, False]),
    )


def test_prepare_prefixlm_batch_leaves_other_backends_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("models.accelerator.get_accelerator_type", lambda: "sm90")
    batch = {"inputs": torch.tensor([1])}

    assert prepare_prefixlm_batch(batch) is batch


@pytest.mark.parametrize(
    ("module_name", "kernel_name"),
    [
        ("models.flash_attention_prefixlm_fa4", "_fa4_varlen"),
        ("models.flash_attention_prefixlm_rocm", "_rocm_varlen"),
    ],
)
def test_precomputed_routing_matches_backend_fallback(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    kernel_name: str,
) -> None:
    module = import_module(module_name)
    launches: list[tuple[torch.Tensor, dict[str, object]]] = []

    def fake_varlen(q: torch.Tensor, _k: torch.Tensor, _v: torch.Tensor, **kwargs: object) -> torch.Tensor:
        launches.append((q.clone(), kwargs))
        return q.clone()

    monkeypatch.setattr(module, kernel_name, fake_varlen)
    packed = packed_inputs()
    q = torch.randn(12, 2, 8)

    fallback_output = module.flash_attn_varlen_prefixlm(q, q, q, False, *packed)
    fallback_launches = launches.copy()
    launches.clear()

    routing = prefixlm_routing_from_tensors(*packed)
    monkeypatch.setattr(
        module,
        "prefixlm_routing_from_tensors",
        lambda *_args, **_kwargs: pytest.fail("backend recomputed pre-supplied PrefixLM routing"),
    )
    prepared_output = module.flash_attn_varlen_prefixlm(q, q, q, False, *packed, **routing)

    assert torch.equal(prepared_output, fallback_output)
    assert len(launches) == len(fallback_launches)
    for (prepared_q, prepared_kwargs), (fallback_q, fallback_kwargs) in zip(
        launches, fallback_launches, strict=True
    ):
        assert torch.equal(prepared_q, fallback_q)
        assert prepared_kwargs.keys() == fallback_kwargs.keys()
        for name in prepared_kwargs:
            prepared_value = prepared_kwargs[name]
            fallback_value = fallback_kwargs[name]
            if isinstance(prepared_value, torch.Tensor):
                assert torch.equal(prepared_value, fallback_value)
            else:
                assert prepared_value == fallback_value


def test_seqused_launches_use_original_packed_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = import_module("models.flash_attention_prefixlm_fa4")
    launches: list[tuple[torch.Tensor, dict[str, object]]] = []

    def fake_varlen(q: torch.Tensor, _k: torch.Tensor, _v: torch.Tensor, **kwargs: object) -> torch.Tensor:
        launches.append((q, kwargs))
        return q.clone()

    monkeypatch.setattr(module, "_fa4_varlen", fake_varlen)
    packed = packed_inputs()
    prepared = prefixlm_prepared_from_tensors(*packed)
    q = torch.randn(16, 2, 8)

    output = module.flash_attn_varlen_prefixlm(
        q,
        q,
        q,
        False,
        *packed,
        **prepared,
        impl="seqused",
    )

    assert torch.equal(output[:12], q[:12])
    assert torch.equal(output[12:], torch.zeros_like(output[12:]))
    assert len(launches) == 2
    assert launches[0][0].shape == q.shape
    assert launches[1][0].shape == q.shape
    assert torch.equal(launches[0][1]["seqused_q"], packed[0][:2])
    assert torch.equal(launches[0][1]["seqused_k"], packed[0][:2])
    assert torch.equal(launches[1][1]["seqused_q"], packed[1][:2])
    assert launches[1][1].get("seqused_k") is None


@pytest.mark.parametrize("impl", ["eager", "triton"])
def test_seqused_gradient_mask_zeros_only_unused_rows(impl: str) -> None:
    module = import_module("models.flash_attention_prefixlm_fa4")
    q = torch.randn(4, 2, 3, requires_grad=True)
    k = torch.randn(4, 1, 3, requires_grad=True)
    v = torch.randn(4, 1, 3, requires_grad=True)
    q_used = torch.tensor([True, False, True, False])
    kv_used = torch.tensor([True, True, True, False])

    masked = module._mask_undefined_seqused_grads(
        q, k, v, q_used, kv_used, impl
    )
    sum(tensor.sum() for tensor in masked).backward()

    assert torch.equal(q.grad[q_used], torch.ones_like(q.grad[q_used]))
    assert torch.equal(q.grad[~q_used], torch.zeros_like(q.grad[~q_used]))
    for tensor in (k, v):
        assert torch.equal(tensor.grad[kv_used], torch.ones_like(tensor.grad[kv_used]))
        assert torch.equal(tensor.grad[~kv_used], torch.zeros_like(tensor.grad[~kv_used]))


@pytest.mark.skipif(not torch.cuda.is_available(), reason="requires CUDA and Triton")
def test_triton_seqused_gradient_mask_matches_eager_on_cuda() -> None:
    module = import_module("models.flash_attention_prefixlm_fa4")
    q = torch.randn(17, 4, 8, device="cuda", dtype=torch.bfloat16)
    k = torch.randn(17, 2, 8, device="cuda", dtype=torch.bfloat16)
    v = torch.randn_like(k)
    q_used = torch.arange(17, device="cuda") % 3 != 0
    kv_used = torch.arange(17, device="cuda") % 4 != 0
    q[~q_used] = torch.nan
    k[~kv_used] = torch.nan
    v[~kv_used] = torch.nan

    actual = module._mask_undefined_seqused_grads_triton(
        q, k, v, q_used, kv_used
    )
    expected = (
        q.masked_fill(~q_used[:, None, None], 0),
        k.masked_fill(~kv_used[:, None, None], 0),
        v.masked_fill(~kv_used[:, None, None], 0),
    )

    assert all(torch.equal(left, right) for left, right in zip(actual, expected))


@pytest.mark.parametrize("impl", ["eager", "triton"])
def test_seqused_output_combine_routes_forward_and_backward(impl: str) -> None:
    module = import_module("models.flash_attention_prefixlm_fa4")
    prefix = torch.randn(5, 2, 3, requires_grad=True)
    causal = torch.randn(5, 2, 3, requires_grad=True)
    prefix_mask = torch.tensor([True, True, False, False, False])
    causal_mask = torch.tensor([False, False, True, True, False])

    output = module._combine_seqused_outputs(
        prefix, causal, prefix_mask, causal_mask, impl
    )
    output.sum().backward()

    assert torch.equal(output[:2], prefix[:2])
    assert torch.equal(output[2:4], causal[2:4])
    assert torch.equal(output[4], torch.zeros_like(output[4]))
    assert torch.equal(
        prefix.grad, prefix_mask[:, None, None].expand_as(prefix).to(prefix.dtype)
    )
    assert torch.equal(
        causal.grad, causal_mask[:, None, None].expand_as(causal).to(causal.dtype)
    )


@pytest.mark.skipif(not torch.cuda.is_available(), reason="requires CUDA and Triton")
def test_triton_seqused_output_combine_matches_eager_on_cuda() -> None:
    module = import_module("models.flash_attention_prefixlm_fa4")
    prefix_mask = torch.tensor(
        [True, True, False, False, False, True, False], device="cuda"
    )
    causal_mask = torch.tensor(
        [False, False, True, True, False, False, True], device="cuda"
    )
    prefix = torch.randn(7, 4, 8, device="cuda", dtype=torch.bfloat16)
    causal = torch.randn_like(prefix)
    prefix[~prefix_mask] = torch.nan
    causal[~causal_mask] = torch.nan

    expected_prefix = prefix.clone().requires_grad_()
    expected_causal = causal.clone().requires_grad_()
    actual_prefix = prefix.clone().requires_grad_()
    actual_causal = causal.clone().requires_grad_()
    grad = torch.randn_like(prefix)

    expected = module._combine_seqused_outputs(
        expected_prefix, expected_causal, prefix_mask, causal_mask, "eager"
    )
    actual = module._combine_seqused_outputs(
        actual_prefix, actual_causal, prefix_mask, causal_mask, "triton"
    )
    expected.backward(grad)
    actual.backward(grad)

    assert torch.equal(actual, expected)
    assert torch.equal(actual_prefix.grad, expected_prefix.grad)
    assert torch.equal(actual_causal.grad, expected_causal.grad)

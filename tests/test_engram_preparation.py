import copy
import json
from types import SimpleNamespace

import pytest
import torch

from test_hrm_experts import config, cpu_attention
from models.adam_atan2 import AdamATan2
from models.baselines.hrm_nocarry_bp_warmup import HierarchicalReasoningModel as V1
from models.baselines.hrm_v2 import HierarchicalReasoningModel as V2
from models.expert_mixtures import dense_source_key
from models.lm_head import LMHead
from models.ngram_memory import NGramMemory
from models.v2_checkpoint import load_upcycled_checkpoint
from scripts.measure_ngram_occupancy import measure


@pytest.mark.parametrize("dtype", [torch.float32, torch.bfloat16])
def test_engram_dcp_upcycle_and_optimizer_ema_resume(tmp_path, dtype):
    import torch.distributed.checkpoint as dcp
    from torch.distributed.checkpoint.state_dict import get_optimizer_state_dict

    torch.manual_seed(18)
    source = LMHead(V1(config()), config()).to(dtype)
    optimizer = AdamATan2(source.parameters(), lr=.001, ema=.9, ema_dtype=torch.float32)
    for parameter in source.parameters():
        parameter.grad = torch.randn_like(parameter)
    optimizer.step()
    dcp.save({"model": source.state_dict(),
              "optim": get_optimizer_state_dict(source, optimizer)},
             checkpoint_id=tmp_path / "dense")
    cfg = config(ngram_orders=[2, 3], ngram_buckets=31, ngram_heads=4,
                 ngram_contextual_gate=True, ngram_warmup_start_step=3800000,
                 ngram_warmup_steps=2000)
    target = LMHead(V2(cfg), cfg).to(dtype)
    dest = AdamATan2(target.parameters(), lr=.001, ema=.9, ema_dtype=torch.float32)
    load_upcycled_checkpoint(target, dest, str(tmp_path / "dense"))
    original = dict(source.named_parameters())
    for name, parameter in target.named_parameters():
        key = dense_source_key(name)
        if key in original:
            torch.testing.assert_close(parameter, original[key], rtol=0, atol=0)
            for slot, value in optimizer.state[original[key]].items():
                torch.testing.assert_close(dest.state[parameter][slot], value, rtol=0, atol=0)
        else:
            assert "ngram." in name
            assert dest.state[parameter]["step"] == 0
            assert not dest.state[parameter]["exp_avg"].count_nonzero()
            assert not dest.state[parameter]["exp_avg_sq"].count_nonzero()
            torch.testing.assert_close(dest.state[parameter]["param_ema"],
                                       parameter.float(), rtol=0, atol=0)
    batch = dict(inputs=torch.tensor([[1, 2, 3, 4]]), position_ids=torch.arange(4)[None])
    torch.testing.assert_close(target(None, batch, bp_steps=8)[1],
                               source(None, batch, bp_steps=8)[1], rtol=0, atol=0)
    for step_value, expected_alpha in ((3800000, 0.), (3801000, .5), (3802000, 1.)):
        target.model.compute_train_extra_args(SimpleNamespace(step=step_value))
        assert target.model.ngram.alpha.item() == expected_alpha
    target.model.ngram.alpha.fill_(1)

    def step(model, opt):
        opt.zero_grad()
        model(None, batch, bp_steps=8)[1].float().square().mean().backward()
        opt.step()

    # Two steps activate both the tables and the gate's gradients.
    step(target, dest)
    step(target, dest)
    torch.save({"model": target.state_dict(), "optim": dest.state_dict()}, tmp_path / "resume.pt")
    restored = LMHead(V2(cfg), cfg).to(dtype)
    resumed = AdamATan2(restored.parameters(), lr=.001, ema=.9, ema_dtype=torch.float32)
    state = torch.load(tmp_path / "resume.pt", weights_only=True)
    restored.load_state_dict(state["model"], strict=True)
    resumed.load_state_dict(state["optim"])
    step(target, dest)
    step(restored, resumed)
    for (name, parameter), (_, other) in zip(target.named_parameters(), restored.named_parameters()):
        torch.testing.assert_close(parameter, other, rtol=0, atol=0)
        for slot, value in dest.state[parameter].items():
            torch.testing.assert_close(value, resumed.state[other][slot], rtol=0, atol=0)
        assert resumed.state[other]["param_ema"].dtype == torch.float32


def test_diagnostics_are_opt_in_detached_and_function_preserving(tmp_path):
    memory = NGramMemory(16, (2, 3), 31, 4, True)
    memory.alpha.fill_(.7)
    with torch.no_grad():
        for table in memory.tables:
            table.normal_(std=.1)
    state = copy.deepcopy(memory.state_dict())
    x = torch.randn(2, 8, 16, requires_grad=True)
    tokens = torch.randint(0, 32, (2, 8))
    stats = {}
    expected = memory(x, tokens)
    actual = memory(x, tokens, diagnostics=stats)
    torch.testing.assert_close(actual, expected, rtol=0, atol=0)
    assert 0 <= stats["gate_min"] <= stats["gate_mean"] <= stats["gate_max"] <= 1
    assert stats["contribution_rms"] > 0
    assert all(not value.requires_grad for value in stats.values())
    for key, value in state.items():
        torch.testing.assert_close(value, memory.state_dict()[key], rtol=0, atol=0)
    (tmp_path / "diagnostics.json").write_text(json.dumps({k: float(v) for k, v in stats.items()}))


def test_exact_collisions_separate_repeats_and_boundaries():
    # With two buckets, these two distinct bigrams collide for each odd base.
    report = measure([[1, 2, 1, 2], [3, 4]], orders=(2,), heads=4, buckets=2, max_tokens=6)
    for result in report["results"]:
        assert result["observations"] == 4
        assert result["distinct_ngrams"] == 3
        assert result["repeated_observations"] == 1
        assert result["excess_distinct_collisions"] == 2
        assert result["colliding_distinct_pairs"] == 3
    bounded = measure([[1, 2, 3, 4], [5, 6]], max_tokens=3)
    assert bounded["tokens"] == 3
    assert bounded["rows"] == 1


def _distributed_engram_resume(rank, rendezvous):
    import torch.distributed as dist
    import torch.distributed.checkpoint as dcp
    from torch.distributed.checkpoint.state_dict import get_state_dict, set_state_dict
    from torch.distributed.device_mesh import init_device_mesh
    from torch.distributed.fsdp import fully_shard
    from models.transformer import TransformerBlock
    import models.layers

    def attention(q, k, v, causal, **kwargs):
        return torch.nn.functional.scaled_dot_product_attention(
            q.transpose(-3, -2), k.transpose(-3, -2), v.transpose(-3, -2),
            is_causal=causal).transpose(-3, -2)

    models.layers.flash_attn_varlen_prefixlm = attention
    dist.init_process_group("gloo", init_method=f"file://{rendezvous}", rank=rank, world_size=2)
    try:
        mesh = init_device_mesh("cpu", (2,))
        cfg = config(ngram_orders=[2, 3], ngram_buckets=32, ngram_heads=4,
                     ngram_contextual_gate=True, ngram_warmup_start_step=3800000)

        def create():
            model = LMHead(V2(cfg), cfg)
            model.model.ngram.alpha.fill_(.7)
            for block in model.modules():
                if isinstance(block, TransformerBlock):
                    fully_shard(block, mesh=mesh, reshard_after_forward=False)
            fully_shard(model, mesh=mesh, reshard_after_forward=False)
            return model, AdamATan2(model.parameters(), lr=.001, ema=.9, ema_dtype=torch.float32)

        torch.manual_seed(17)
        model, optimizer = create()
        batch = dict(inputs=torch.tensor([[1, 2 + rank, 3, 4]]), position_ids=torch.arange(4)[None])

        def step(model, optimizer):
            optimizer.zero_grad()
            model(None, batch, bp_steps=8)[1].square().mean().backward()
            optimizer.step()

        step(model, optimizer)
        step(model, optimizer)
        weights, slots = get_state_dict(model, optimizer)
        path = rendezvous + "-checkpoint"
        dcp.save(dict(model=weights, optim=slots), checkpoint_id=path)
        clone, resumed = create()
        weights, slots = get_state_dict(clone, resumed)
        state = dict(model=weights, optim=slots)
        dcp.load(state, checkpoint_id=path)
        set_state_dict(clone, resumed, model_state_dict=state["model"], optim_state_dict=state["optim"])
        step(model, optimizer)
        step(clone, resumed)
        for p, q in zip(model.parameters(), clone.parameters()):
            torch.testing.assert_close(p.full_tensor(), q.full_tensor(), rtol=0, atol=0)
            for key, value in optimizer.state[p].items():
                other = resumed.state[q][key]
                if hasattr(value, "full_tensor"):
                    value, other = value.full_tensor(), other.full_tensor()
                torch.testing.assert_close(value, other, rtol=0, atol=0)
    finally:
        dist.destroy_process_group()


def test_two_rank_fsdp_engram_save_resume(tmp_path):
    torch.multiprocessing.spawn(_distributed_engram_resume,
                                args=(str(tmp_path / "engram-rendezvous"),),
                                nprocs=2, join=True)

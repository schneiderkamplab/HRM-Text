import copy
from types import SimpleNamespace

import pytest
import torch
import torch.distributed.checkpoint as dcp
from torch import nn
from torch.nn import functional as F
from torch.distributed.checkpoint.state_dict import get_optimizer_state_dict, set_state_dict

from models.adam_atan2 import AdamATan2
from models.baselines.hrm_nocarry_bp_warmup import HierarchicalReasoningModel as V1
from models.baselines.hrm_v2 import HierarchicalReasoningModel as V2, InvocationGate
from models.lm_head import LMHead
from models.module_learning_rates import module_lr_scales, configured_module_rates
from models.v2_checkpoint import load_v1_checkpoint, is_gate_key


def config(**changes):
    return dict(hidden_size=16, num_heads=2, n_layers=2, half_layers=True,
                expansion=1, norm_type="pre", norm_eps=1e-6, init_type="lecun_normal",
                pos_emb_type="rope", rope_theta=10000, max_seq_len=16,
                H_cycles=2, L_cycles=3, bp_max_steps=8, bp_warmup_ratio=0,
                fwd_bwd_dtype="float32", vocab_size=32, gates_enabled=True, **changes)


@pytest.fixture(autouse=True)
def cpu_attention(monkeypatch):
    # Exercise real transformer layers with a CPU reference attention kernel.
    def attention(q, k, v, causal, **kwargs):
        return F.scaled_dot_product_attention(q.transpose(-3, -2), k.transpose(-3, -2),
                                            v.transpose(-3, -2), is_causal=causal).transpose(-3, -2)
    monkeypatch.setattr("models.layers.flash_attn_varlen_prefixlm", attention)


def pair():
    torch.manual_seed(123)
    baseline = LMHead(V1(config()), config())
    torch.manual_seed(123)
    gated = LMHead(V2(config()), config())
    return baseline, gated


@pytest.mark.parametrize("bp", [2, 5, 8])
def test_zero_gates_preserve_logits_and_backbone_gradients(bp):
    baseline, gated = pair()
    for key, value in baseline.state_dict().items():
        torch.testing.assert_close(value, gated.state_dict()[key], rtol=0, atol=0)
    batch = {"inputs": torch.tensor([1, 2, 3, 4]), "position_ids": torch.arange(4)}
    a = baseline(None, batch, bp_steps=bp)[1]
    gated.model.gate_alpha.fill_(1)
    b = gated(None, batch, bp_steps=bp)[1]
    torch.testing.assert_close(a, b, rtol=0, atol=0)
    a.square().mean().backward()
    b.square().mean().backward()
    for name, param in baseline.named_parameters():
        torch.testing.assert_close(param.grad, dict(gated.named_parameters())[name].grad, rtol=0, atol=0)
    h_bp = min(2, bp - 1)
    for level, count in ((gated.model.H_level, h_bp), (gated.model.L_level, bp - h_bp)):
        for i, gate in enumerate(level.invocation_gates):
            assert (gate.weight.grad is not None) == (i >= len(level.invocation_gates) - count)
            if gate.weight.grad is not None:
                assert gate.weight.grad.abs().sum() > 0


def test_alpha_zero_and_schedule_is_absolute_and_persisted():
    baseline, gated = pair()
    for name, param in gated.named_parameters():
        if is_gate_key(name):
            nn.init.normal_(param)
    batch = {"inputs": torch.tensor([1, 2, 3, 4]), "position_ids": torch.arange(4)}
    torch.testing.assert_close(baseline(None, batch)[1], gated(None, batch)[1], rtol=0, atol=0)
    gate_model = V2(config(gate_warmup_start_step=3800000, gate_warmup_steps=2000))
    for step, alpha in [(3799999, 0), (3800000, 0), (3800001, .0005), (3801000, .5), (3802000, 1), (3810000, 1)]:
        gate_model.compute_train_extra_args(SimpleNamespace(step=step))
        assert gate_model.gate_alpha.item() == pytest.approx(alpha)
    restored = V2(config())
    restored.load_state_dict(gate_model.state_dict())
    assert restored.gate_alpha.item() == 1


def test_gate_is_token_local_and_bounded():
    gate = InvocationGate(16)
    nn.init.normal_(gate.weight)
    x, y = torch.randn(4, 16), torch.ones(4, 16)
    a = gate(x, y, torch.tensor(.5))
    x[3] += 10
    b = gate(x, y, torch.tensor(.5))
    torch.testing.assert_close(a[:3], b[:3])
    assert (a >= .5).all() and (a <= 1.5).all()


def test_delta_sharing_moments_ema_and_bp_transition():
    model = V2(config())
    model.gate_alpha.fill_(1)
    optimizer = AdamATan2(model.parameters(), lr=.001, ema=.9)
    for bp in (2, 5, 8):
        optimizer.zero_grad(set_to_none=True)
        model.configure_gate_updates(optimizer, bp)
        model(None, torch.randn(4, 16), bp_steps=bp, position_ids=torch.arange(4))[1].square().mean().backward()
        pairs = optimizer.shared_parameter_updates
        before = {p: p.detach().clone() for p in pairs}
        donors = {p: p.detach().clone() for p in set(pairs.values())}
        emas = {p: optimizer.state[p]["param_ema"].clone() for p in pairs}
        # Simulate FSDP materialized zero gradients on unused parameters.
        for p in pairs:
            p.grad = torch.zeros_like(p)
        optimizer.step()
        for p, donor in pairs.items():
            torch.testing.assert_close(p - before[p], donor - donors[donor])
            for key in ("step", "exp_avg", "exp_avg_sq"):
                torch.testing.assert_close(optimizer.state[p][key], optimizer.state[donor][key])
            torch.testing.assert_close(optimizer.state[p]["param_ema"], emas[p].lerp(p, .1))
    assert not optimizer.shared_parameter_updates
    assert not torch.equal(model.L_level.invocation_gates[0].weight, model.L_level.invocation_gates[-1].weight)


def test_migration_and_roundtrip_preserve_original_state(tmp_path):
    baseline, gated = pair()
    opt1 = AdamATan2(baseline.parameters(), lr=.003, ema=.9)
    for p in baseline.parameters():
        p.grad = torch.ones_like(p)
    opt1.step()
    opt2 = AdamATan2(gated.parameters(), lr=.001, ema=.9)
    dcp.save({"model": baseline.state_dict(), "optim": get_optimizer_state_dict(baseline, opt1)},
             checkpoint_id=tmp_path / "v1")
    assert load_v1_checkpoint(gated, opt2, tmp_path / "v1")
    for name, p in baseline.named_parameters():
        q = dict(gated.named_parameters())[name]
        torch.testing.assert_close(p, q, rtol=0, atol=0)
        for key, value in opt1.state[p].items():
            torch.testing.assert_close(value, opt2.state[q][key], rtol=0, atol=0)
    for name, p in gated.named_parameters():
        if is_gate_key(name):
            assert not torch.count_nonzero(p)
            assert opt2.state[p]["step"] == 0
    gated.model.gate_alpha.fill_(.4)
    saved = {"model": gated.state_dict(), "optim": get_optimizer_state_dict(gated, opt2)}
    dcp.save(saved, checkpoint_id=tmp_path / "v2")
    assert not load_v1_checkpoint(gated, opt2, tmp_path / "v2")
    restored = LMHead(V2(config()), config())
    opt3 = AdamATan2(restored.parameters(), lr=.001, ema=.9)
    state = {"model": restored.state_dict(), "optim": get_optimizer_state_dict(restored, opt3)}
    dcp.load(state, checkpoint_id=tmp_path / "v2")
    set_state_dict(restored, opt3, model_state_dict=state["model"], optim_state_dict=state["optim"])
    for key, value in gated.state_dict().items():
        torch.testing.assert_close(value, restored.state_dict()[key], rtol=0, atol=0)
    broken = dict(baseline.state_dict())
    broken.pop(next(iter(broken)))
    dcp.save({"model": broken, "optim": get_optimizer_state_dict(baseline, opt1)}, checkpoint_id=tmp_path / "broken")
    with pytest.raises(ValueError, match="backbone mismatch"):
        load_v1_checkpoint(gated, opt2, tmp_path / "broken")


def test_gate_lr_is_not_divided_by_recurrence():
    _, model = pair()
    cfg = SimpleNamespace(lr=1e-5, lr_auto=True, lr_embeddings=None, lr_head=None, lr_h=None, lr_l=None,
                          arch=dict(name="baselines.hrm_v2@HierarchicalReasoningModel", H_cycles=2, L_cycles=3))
    scales = module_lr_scales(model, cfg.lr, configured_module_rates(cfg, 8))
    for name, param in model.named_parameters():
        if is_gate_key(name):
            assert scales[param] == 1
        elif "L_level" in name:
            assert scales[param] == pytest.approx(1 / 6)


def test_native_cache_parity_with_nonzero_gates():
    model = V2(config()).eval()
    model.gate_alpha.fill_(.5)
    for name, param in model.named_parameters():
        if is_gate_key(name):
            nn.init.normal_(param, std=.02)
    x = torch.randn(1, 5, 16)
    # Full-prefix prefill through the production cache path versus CPU attention.
    with torch.no_grad():
        full = model(None, x, position_ids=torch.arange(5))[1]
        cache = model.create_cache(max_batch_size=1, max_seq_len=16, dtype=torch.float32, device="cpu")
        cached = model(None, x, cache=cache, cache_lengths=torch.tensor([0]), position_ids=torch.arange(5))[1]
    torch.testing.assert_close(full, cached)


def test_compile_alpha_change_does_not_specialize(monkeypatch):
    gate = InvocationGate(16)
    count = []
    def backend(gm, inputs):
        count.append(1)
        return gm.forward
    compiled = torch.compile(gate, backend=backend, fullgraph=True)
    x, y, alpha = torch.randn(4, 16), torch.randn(4, 16), torch.tensor(0.)
    for value in (0., .1, .5, 1.):
        alpha.fill_(value)
        torch.testing.assert_close(compiled(x, y, alpha), gate(x, y, alpha))
    assert len(count) == 1


def test_shared_delta_preserves_offsets_and_own_ema():
    donor = nn.Parameter(torch.ones(4, 4))
    target = nn.Parameter(torch.full((4, 4), 2.))
    optimizer = AdamATan2([target, donor], lr=.1, weight_decay=.1, ema=.9)
    optimizer.shared_parameter_updates = {target: donor}
    donor.grad = torch.ones_like(donor)
    optimizer.step()
    torch.testing.assert_close(target - donor, torch.ones_like(target))
    torch.testing.assert_close(optimizer.state[target]["param_ema"], 2 * .9 + target * .1)


def test_v2_resume_continues_updates_exactly():
    _, model = pair()
    optimizer = AdamATan2(model.parameters(), lr=.001, ema=.9)
    model.model.gate_alpha.fill_(.7)
    batch = {"inputs": torch.tensor([1, 2, 3, 4]), "position_ids": torch.arange(4)}
    def step(m, opt, bp):
        opt.zero_grad(set_to_none=True)
        m.model.configure_gate_updates(opt, bp)
        m(None, batch, bp_steps=bp)[1].square().mean().backward()
        opt.step()
    step(model, optimizer, 2)
    clone = copy.deepcopy(model)
    opt2 = AdamATan2(clone.parameters(), lr=.001, ema=.9)
    opt2.load_state_dict(copy.deepcopy(optimizer.state_dict()))
    for bp in (2, 5, 8):
        step(model, optimizer, bp)
        step(clone, opt2, bp)
    for p, q in zip(model.parameters(), clone.parameters()):
        torch.testing.assert_close(p, q, rtol=0, atol=0)
        for key in optimizer.state[p]:
            torch.testing.assert_close(optimizer.state[p][key], opt2.state[q][key], rtol=0, atol=0)


def _fsdp_worker(rank, world_size, path, mixed_precision):
    import torch.distributed as dist
    from torch.distributed.device_mesh import init_device_mesh
    from torch.distributed.fsdp import fully_shard, MixedPrecisionPolicy
    dist.init_process_group("gloo", init_method=f"file://{path}", rank=rank, world_size=world_size)
    try:
        # Use real FSDP root-owned gate tensors without any CUDA allocation.
        class GateBank(nn.Module):
            def __init__(self):
                super().__init__()
                self.gates = nn.ModuleList([InvocationGate(16) for _ in range(3)])
            def forward(self, x):
                with torch.no_grad():
                    y = self.gates[0](x, x, torch.tensor(.5))
                    y = self.gates[1](y, x, torch.tensor(.5))
                return self.gates[2](y, x, torch.tensor(.5))
        torch.manual_seed(456)
        model = GateBank()
        reference = copy.deepcopy(model)
        mesh = init_device_mesh("cpu", (world_size,))
        fully_shard(model, mesh=mesh, reshard_after_forward=False)
        opt = AdamATan2(model.parameters(), lr=.001, ema=.9)
        refopt = AdamATan2(reference.parameters(), lr=.001, ema=.9)
        def configure(m, o):
            o.shared_parameter_updates = dict(
                pair for gate in m.gates[:2] for pair in zip(gate.parameters(), m.gates[2].parameters()))
        for _ in range(3):
            x = torch.randn(4, 16)
            for m, o in ((model, opt), (reference, refopt)):
                o.zero_grad(set_to_none=True)
                configure(m, o)
                m(x).square().sum().backward()
                o.step()
            for p, q in zip(model.parameters(), reference.parameters()):
                torch.testing.assert_close(p.full_tensor(), q, rtol=1e-5, atol=1e-7)
                torch.testing.assert_close(opt.state[p]["param_ema"].full_tensor(), refopt.state[q]["param_ema"])

        import models.layers
        from models.transformer import TransformerBlock
        def attention(q, k, v, causal, **kwargs):
            return F.scaled_dot_product_attention(q.transpose(-3, -2), k.transpose(-3, -2),
                                                v.transpose(-3, -2), is_causal=causal).transpose(-3, -2)
        models.layers.flash_attn_varlen_prefixlm = attention
        baseline, gated = pair()
        policy = MixedPrecisionPolicy(param_dtype=torch.bfloat16, reduce_dtype=torch.float32) if mixed_precision else MixedPrecisionPolicy()
        for m in (baseline, gated):
            for block in m.modules():
                if isinstance(block, TransformerBlock):
                    fully_shard(block, mesh=mesh, reshard_after_forward=False, mp_policy=policy)
            fully_shard(m, mesh=mesh, reshard_after_forward=False, mp_policy=policy)
        oldopt = AdamATan2(baseline.parameters(), lr=.001, ema=.9)
        newopt = AdamATan2(gated.parameters(), lr=.001, ema=.9)
        batch = {"inputs": torch.tensor([1, 2, 3, 4]), "position_ids": torch.arange(4)}
        baseline(None, batch, bp_steps=8)[1].square().mean().backward()
        oldopt.step()
        checkpoint = path + "-checkpoint"
        dcp.save({"model": baseline.state_dict(), "optim": get_optimizer_state_dict(baseline, oldopt)},
                 checkpoint_id=checkpoint)
        assert load_v1_checkpoint(gated, newopt, checkpoint)
        for name, p in baseline.named_parameters():
            q = dict(gated.named_parameters())[name]
            torch.testing.assert_close(p.full_tensor(), q.full_tensor(), rtol=0, atol=0)
            for key in ("exp_avg", "exp_avg_sq", "param_ema"):
                torch.testing.assert_close(oldopt.state[p][key].full_tensor(), newopt.state[q][key].full_tensor(), rtol=0, atol=0)
        gated.model.gate_alpha.fill_(.5)
        for bp in (2, 5, 8):
            newopt.zero_grad(set_to_none=True)
            gated.model.configure_gate_updates(newopt, bp)
            for microbatch in range(2):
                gated.set_requires_gradient_sync(microbatch == 1, recurse=True)
                loss = gated(None, batch, bp_steps=bp)[1].float().square().mean() / 2
                loss.backward()
            newopt.step()
            assert torch.isfinite(loss)
            for p, donor in newopt.shared_parameter_updates.items():
                torch.testing.assert_close(newopt.state[p]["exp_avg"].full_tensor(), newopt.state[donor]["exp_avg"].full_tensor())
    finally:
        dist.destroy_process_group()


@pytest.mark.parametrize("mixed_precision", [False, True])
def test_two_rank_fsdp_gate_updates(tmp_path, mixed_precision):
    torch.multiprocessing.spawn(_fsdp_worker, args=(2, str(tmp_path / "rendezvous"), mixed_precision), nprocs=2, join=True)


def test_prepared_command_is_isolated_and_matches_baseline():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("prepare_v2", Path(__file__).parents[1] / "scripts/prepare_hrm_v2_xl.py")
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
    spec.loader.exec_module(module)
    v2 = dict(arg.split("=", 1) for arg in module.command()[3:])
    control = dict(arg.split("=", 1) for arg in module.command("control")[3:])
    for key in ("lr", "data.path", "resume_checkpoint_path", "resume_checkpoint_tag", "epochs",
                "global_batch_size", "gradient_accumulation_steps", "stop_after_step", "arch.bp_max_steps"):
        assert v2[key] == control[key]
    assert v2["checkpoint_path"] != control["checkpoint_path"]
    assert v2["wandb_run_id"] != control["wandb_run_id"]
    assert v2["wandb_resume"] == "never"
    assert v2["arch.gate_warmup_start_step"] == "3800000"
    assert not {"resume_step", "resume_epoch", "resume_batch_in_epoch"} & v2.keys()


def test_compile_full_model_backward_and_gas():
    model = V2(config())
    model.gate_alpha.fill_(.5)
    reference = copy.deepcopy(model)
    compiled = torch.compile(model, backend="aot_eager", dynamic=False)
    for _ in range(2):
        x = torch.randn(4, 16)
        a = compiled(None, x, position_ids=torch.arange(4), bp_steps=5)[1]
        b = reference(None, x, position_ids=torch.arange(4), bp_steps=5)[1]
        a.square().mean().backward()
        b.square().mean().backward()
        torch.testing.assert_close(a, b)
    for p, q in zip(model.parameters(), reference.parameters()):
        torch.testing.assert_close(p.grad, q.grad)


def test_cached_decode_with_nonzero_gates():
    model = V2(config(attn_type="causal")).eval()
    model.gate_alpha.fill_(.7)
    for name, param in model.named_parameters():
        if is_gate_key(name):
            nn.init.normal_(param, std=.02)
    x = torch.randn(1, 5, 16)
    cache = model.create_cache(max_batch_size=1, max_seq_len=16, dtype=torch.float32, device="cpu")
    with torch.no_grad():
        full = model(None, x, position_ids=torch.arange(5))[1]
        parts = [model(None, x[:, i:i + 1], cache=cache, cache_lengths=torch.tensor([i]),
                       position_ids=torch.tensor([i]))[1] for i in range(5)]
    torch.testing.assert_close(full, torch.cat(parts, dim=1), rtol=1e-4, atol=1e-5)


def test_hf_export_rejects_gate_loss():
    from conversion.convert_to_hf import build_hf_config, convert_state_dict
    with pytest.raises(ValueError, match="HRM v2"):
        build_hf_config(dict(name="baselines.hrm_v2@HierarchicalReasoningModel"), None)
    with pytest.raises(ValueError, match="HRM v2"):
        convert_state_dict({"model.H_level.invocation_gates.0.weight": torch.zeros(16, 32)}, {})


def test_pretrain_v1_migration_and_strict_v2_resume(tmp_path):
    import yaml
    from pretrain import ArchConfig, load_sharded_train_state
    baseline, gated = pair()
    opt1 = AdamATan2(baseline.parameters(), lr=.001, ema=.9)
    opt2 = AdamATan2(gated.parameters(), lr=.001, ema=.9)
    dcp.save({"model": baseline.state_dict(), "optim": get_optimizer_state_dict(baseline, opt1)},
             checkpoint_id=tmp_path / "fsdp2_step_1")
    (tmp_path / "all_config.yaml").write_text(yaml.safe_dump(dict(arch=dict(
        name="baselines.hrm_nocarry_bp_warmup@HierarchicalReasoningModel", H_cycles=2, L_cycles=3))))
    cfg = SimpleNamespace(resume_checkpoint_path=str(tmp_path), distributed_strategy="none", arch=ArchConfig(
        name="baselines.hrm_v2@HierarchicalReasoningModel", head="lm_head@LMHead",
        H_cycles=2, L_cycles=3, gate_initialize_from_v1=True))
    state = SimpleNamespace(model=gated, optim=opt2)
    load_sharded_train_state(cfg, state, "step_1")
    cfg.arch.L_cycles = 4
    with pytest.raises(ValueError, match="preserve L_cycles"):
        load_sharded_train_state(cfg, state, "step_1")
    cfg.arch.L_cycles = 3
    # A corrupt v2 checkpoint missing all gate state is NOT mistaken for v1.
    (tmp_path / "all_config.yaml").write_text(yaml.safe_dump(dict(arch=cfg.arch.model_dump())))
    with pytest.raises(dcp.CheckpointException):
        load_sharded_train_state(cfg, state, "step_1")


def test_resume_cannot_silently_disable_gates(tmp_path):
    from pretrain import ArchConfig, load_sharded_train_state
    _, gated = pair()
    gated_opt = AdamATan2(gated.parameters(), lr=.001, ema=.9)
    dcp.save({'model': gated.state_dict(), 'optim': get_optimizer_state_dict(gated, gated_opt)},
             checkpoint_id=tmp_path / 'fsdp2_step_1')
    plain_cfg = config()
    plain_cfg.pop('gates_enabled')
    plain = LMHead(V2(plain_cfg), plain_cfg)
    plain_opt = AdamATan2(plain.parameters(), lr=.001, ema=.9)
    cfg = SimpleNamespace(resume_checkpoint_path=str(tmp_path), distributed_strategy='none',
                          arch=ArchConfig(name='baselines.hrm_v2@HierarchicalReasoningModel',
                                          head='lm_head@LMHead'))
    with pytest.raises(ValueError, match='disabled or mismatched v2 features'):
        load_sharded_train_state(cfg, SimpleNamespace(model=plain, optim=plain_opt), 'step_1')

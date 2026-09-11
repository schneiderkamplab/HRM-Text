import copy

import pytest
import torch

from models.adam_atan2 import AdamATan2
from models.experiment_diagnostics import ParameterUpdateProbe


def test_probe_preserves_updates_optimizer_ema_and_rng():
    torch.manual_seed(17)
    reference = torch.nn.Linear(5, 3)
    measured = copy.deepcopy(reference)
    optimizers = [AdamATan2(model.parameters(), lr=1e-3, ema=0.99)
                  for model in (reference, measured)]
    inputs = torch.randn(7, 5)
    for _ in range(3):
        for model, optimizer in zip((reference, measured), optimizers):
            optimizer.zero_grad()
            model(inputs).square().mean().backward()
        rng = torch.get_rng_state().clone()
        before = {name: p.detach().clone() for name, p in measured.named_parameters()}
        gradients = [p.grad.clone() for p in measured.parameters()]
        probe = ParameterUpdateProbe(measured)
        for optimizer in optimizers:
            optimizer.step()
        records = probe.finish(torch.device("cpu"))
        assert torch.equal(rng, torch.get_rng_state())
        for (name, a), b, grad, record in zip(reference.named_parameters(), measured.parameters(), gradients, records):
            assert torch.equal(a, b)
            assert torch.equal(b.grad, grad)
            for key, value in optimizers[0].state[a].items():
                assert torch.equal(value, optimizers[1].state[b][key])
            delta = b.detach().double() - before[name].double()
            assert record["update_rms"] == pytest.approx(delta.square().mean().sqrt().item())
            assert record["update_to_weight"] == pytest.approx(
                delta.norm().item() / before[name].double().norm().item())


def test_no_update_has_zero_delta():
    model = torch.nn.Linear(2, 2)
    probe = ParameterUpdateProbe(model)
    assert all(row["update_rms"] == 0 for row in probe.finish(torch.device("cpu")))


def test_training_diagnostics_default_off():
    from pretrain import PretrainConfig
    fields = PretrainConfig.model_fields
    assert fields['experiment_update_probe_interval'].default == 0
    assert fields['experiment_metrics_output'].default is None
    assert fields['stability_diagnostics_interval'].default == 0
    assert fields['stability_diagnostics_wandb_detailed'].default is False
    assert 'experiment_gradient_probe_steps' not in fields
    from models.lm_head import LMHeadConfig
    assert 'mlp_relative_energy_weight' not in LMHeadConfig.model_fields

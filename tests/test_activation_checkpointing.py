import copy
import unittest

import torch
from torch import nn

from models.activation_checkpointing import apply_activation_checkpointing
from models.baselines.hrm_nocarry_bp_warmup import HierarchicalReasoningModel
from models.transformer import TransformerBlock


class CountingBlock(TransformerBlock):
    def __init__(self, weight: float) -> None:
        nn.Module.__init__(self)
        self.weight = nn.Parameter(torch.tensor(weight))
        self.calls = 0

    def forward(self, hidden_states, **_kwargs):
        self.calls += 1
        return torch.tanh(hidden_states * self.weight)


def make_model(activation_checkpointing: str) -> HierarchicalReasoningModel:
    model = HierarchicalReasoningModel({
        "max_seq_len": 8,
        "n_layers": 2,
        "hidden_size": 8,
        "num_heads": 1,
        "expansion": 1,
        "init_type": "lecun_normal",
        "norm_type": "pre",
        "norm_eps": 1e-6,
        "pos_emb_type": "none",
        "half_layers": True,
        "H_cycles": 2,
        "L_cycles": 3,
        "bp_min_steps": 2,
        "bp_max_steps": 5,
        "fwd_bwd_dtype": "float32",
        "activation_checkpointing": activation_checkpointing,
    })
    model.H_level.core.layers = nn.ModuleList([CountingBlock(0.7)])
    model.L_level.core.layers = nn.ModuleList([CountingBlock(0.6)])
    if activation_checkpointing != "none":
        apply_activation_checkpointing(model, activation_checkpointing)
    model.train()
    return model


class ActivationCheckpointingTest(unittest.TestCase):
    def test_full_matches_outputs_and_gradients_with_five_recomputations(self):
        baseline = make_model("none")
        checkpointed = make_model("full")
        checkpointed.load_state_dict(copy.deepcopy(baseline.state_dict()))

        baseline_input = torch.randn(4, 8, requires_grad=True)
        checkpointed_input = baseline_input.detach().clone().requires_grad_(True)

        _, baseline_output = baseline(None, baseline_input, bp_steps=5)
        _, checkpointed_output = checkpointed(None, checkpointed_input, bp_steps=5)
        baseline_output.sum().backward()
        checkpointed_output.sum().backward()

        torch.testing.assert_close(checkpointed_output, baseline_output)
        torch.testing.assert_close(checkpointed_input.grad, baseline_input.grad)
        checkpointed_h = checkpointed.H_level.core.layers[0]
        checkpointed_l = checkpointed.L_level.core.layers[0]
        baseline_h = baseline.H_level.core.layers[0]
        baseline_l = baseline.L_level.core.layers[0]
        torch.testing.assert_close(checkpointed_h.weight.grad, baseline_h.weight.grad)
        torch.testing.assert_close(checkpointed_l.weight.grad, baseline_l.weight.grad)

        self.assertEqual((baseline_l.calls, baseline_h.calls), (6, 2))
        self.assertEqual((checkpointed_l.calls, checkpointed_h.calls), (9, 4))

    def test_full_is_inactive_during_evaluation(self):
        model = make_model("full")
        model.eval()

        with torch.no_grad():
            model(None, torch.randn(4, 8), bp_steps=5)

        self.assertEqual((model.L_level.core.layers[0].calls, model.H_level.core.layers[0].calls), (6, 2))

    def test_l_only_recomputes_only_differentiable_l_calls(self):
        model = make_model("l_only")
        model_input = torch.randn(4, 8, requires_grad=True)

        model(None, model_input, bp_steps=5)[1].sum().backward()

        self.assertEqual(model.L_level.core.layers[0].calls, 9)
        self.assertEqual(model.H_level.core.layers[0].calls, 2)

    def test_full_runs_under_torch_compile(self):
        model = make_model("full")

        def forward(model_input):
            return model(None, model_input, bp_steps=5)[1]

        compiled_forward = torch.compile(forward, backend="eager", dynamic=False)
        model_input = torch.randn(4, 8, requires_grad=True)
        output = compiled_forward(model_input)
        output.sum().backward()

        self.assertIsNotNone(model_input.grad)

    def test_h_only_matches_bp8_gradients_and_only_recomputes_h(self):
        baseline = make_model("none")
        model = make_model("h_only")
        model.load_state_dict(copy.deepcopy(baseline.state_dict()))
        x = torch.randn(4, 8, requires_grad=True)
        y = x.detach().clone().requires_grad_(True)
        a = baseline(None, x, bp_steps=8)[1]
        b = model(None, y, bp_steps=8)[1]
        a.sum().backward()
        b.sum().backward()
        torch.testing.assert_close(a, b)
        torch.testing.assert_close(x.grad, y.grad)
        for (name, p), (other_name, q) in zip(baseline.named_parameters(), model.named_parameters()):
            self.assertEqual(name, other_name)
            torch.testing.assert_close(p.grad, q.grad)
        self.assertEqual(model.L_level.core.layers[0].calls, 6)
        self.assertEqual(model.H_level.core.layers[0].calls, 4)


if __name__ == "__main__":
    unittest.main()

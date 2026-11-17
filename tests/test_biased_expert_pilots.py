from types import SimpleNamespace

import numpy as np
import pytest
import torch

from dataset_new import V1Dataset, V1DatasetIndices
from models.baselines.hrm_nocarry_bp_warmup import HierarchicalReasoningModel as V1
from models.baselines.hrm_v2 import HierarchicalReasoningModel as V2
from models.expert_mixtures import TopKRouter, upcycle_dense_weights
from models.lm_head import LMHead
from test_hrm_experts import config, cpu_attention

BIAS = [[0., 0.], [.69314718056, -.69314718056], [-.69314718056, .69314718056]]


def test_source_categories_preserve_packed_batch():
    data = V1Dataset.__new__(V1Dataset)
    data.config = SimpleNamespace(target_only=True, batch_max_length=12,
                                  homogeneous_categories=False, routing_categories=False, mixed_lm=False)
    data._data = np.arange(20, dtype=np.uint32)
    data._data_indices = V1DatasetIndices(
        inst_start=np.array([0, 10]), inst_len=np.array([2, 3]),
        resp_start=np.array([2, 13]), resp_len=np.array([3, 2]))
    data._categories = np.array([1, 2], dtype=np.uint8)
    original, scalars = data._load_batch(np.array([0, 1]))
    data.config.routing_categories = True
    routed, routed_scalars = data._load_batch(np.array([0, 1]))
    for key in original:
        torch.testing.assert_close(original[key], routed[key], rtol=0, atol=0)
    assert scalars == routed_scalars
    assert routed["routing_category"].tolist() == [1]*4 + [2]*4 + [0]*4


@pytest.mark.parametrize("kind", ["moe", "mos"])
def test_bias_parity_specialization_and_eval_removal(kind):
    torch.manual_seed(42)
    extra = {f"{kind}_num_experts": 2, f"{kind}_top_k": 2,
             f"{kind}_metadata_bias": BIAS,
             "routing_bias_decay_start": 3810000, "routing_bias_decay_end": 3820000}
    if kind == "moe":
        extra["moe_levels"] = "both"
    cfg = config(**extra)
    baseline = LMHead(V1(config()), config())
    target = LMHead(V2(cfg), cfg)
    upcycle_dense_weights(target, baseline.state_dict())
    batch = dict(inputs=torch.tensor([1, 2, 3, 4]), position_ids=torch.arange(4),
                 routing_category=torch.ones(4, dtype=torch.long))
    expected = baseline(None, {k: v for k, v in batch.items() if k != "routing_category"}, bp_steps=8)[1]
    actual = target(None, batch, bp_steps=8)[1]
    torch.testing.assert_close(expected, actual, rtol=1e-5, atol=1e-5)
    router = next(m for m in target.modules() if isinstance(m, TopKRouter))
    logits_bias = target.model._metadata_bias(batch["routing_category"], kind)
    torch.testing.assert_close(router(torch.zeros(4, 16), logits_bias),
                               torch.tensor([[.8, .2]]).expand(4, -1))
    opt = torch.optim.SGD(target.parameters(), lr=.03)
    for _ in range(3):
        opt.zero_grad()
        target(None, batch, bp_steps=8)[1].square().mean().backward()
        opt.step()
    assert any(p.grad is not None and p.grad.abs().max() > 0 for p in router.rows)
    target.model.compute_train_extra_args(SimpleNamespace(step=3815000))
    assert target.model.routing_bias_scale.item() == .5
    target.model.compute_train_extra_args(SimpleNamespace(step=3820000))
    assert target.model.routing_bias_scale.item() == 0
    target.eval()
    assert target.model._metadata_bias(batch["routing_category"], kind) is None

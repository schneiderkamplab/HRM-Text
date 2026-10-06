from types import SimpleNamespace

from models.baselines.hrm_nocarry_bp_warmup import HierarchicalReasoningModel


def test_disabled_bp_warmup_uses_maximum():
    model = SimpleNamespace(bp_min_steps=2, bp_max_steps=8, bp_warmup_ratio=0)
    for step in (0, 3150000):
        state = SimpleNamespace(step=step, total_steps=3641017)
        assert HierarchicalReasoningModel.compute_train_extra_args(model, state) == {'bp_steps': 8}


def test_positive_bp_warmup_unchanged():
    model = SimpleNamespace(bp_min_steps=2, bp_max_steps=8, bp_warmup_ratio=0.5)
    for step, expected in ((0, 2), (25, 5), (50, 8), (100, 8)):
        state = SimpleNamespace(step=step, total_steps=100)
        assert HierarchicalReasoningModel.compute_train_extra_args(model, state) == {'bp_steps': expected}

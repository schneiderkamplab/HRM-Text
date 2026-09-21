import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "backfill_external", Path(__file__).resolve().parents[1] / "scripts/backfill_external_eval_to_wandb.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_duplicate_checkpoint_root(tmp_path):
    root = tmp_path / "step_2750000"
    task = root / "epoch_2" / "hellaswag"
    task.mkdir(parents=True)
    (task / "merged_metrics.json").write_text(json.dumps({"euroeval/train_step": 2750000}))
    assert module.resolve_euroeval_root(root / root.name, 2750000) == root
    assert module.resolve_euroeval_root(root, 2750000) == root
    with pytest.raises(ValueError, match="checkpoint mismatch"):
        module.resolve_euroeval_root(root, 2700000)


def test_no_campaign_fallback(tmp_path):
    root = tmp_path / "step_2750000"
    assert module.resolve_euroeval_root(root, 2750000) == root

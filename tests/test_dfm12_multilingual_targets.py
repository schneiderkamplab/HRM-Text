import yaml

from dfm12.multilingual_targets import CONFIG, targets


def test_cumulative_milestones():
    config = yaml.safe_load(CONFIG.read_text())
    quarter, half, full = [targets(config, stage) for stage in ("quarter", "half", "full")]
    assert len(quarter) == 42
    assert sum(row["accepted_target"] for row in quarter) == 962500
    assert sum(row["estimated_training_tokens"] for row in quarter) == 1527625000
    for q, h, f in zip(quarter, half, full):
        assert q["id_namespace"] == h["id_namespace"] == f["id_namespace"]
        assert q["repo_id"] == h["repo_id"] == f["repo_id"]
        assert q["accepted_target"] * 2 == h["accepted_target"]
        assert q["accepted_target"] * 4 == f["accepted_target"]
    assert config["require_pilot_review_before_bulk"]

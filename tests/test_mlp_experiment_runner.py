import json
import pickle
import shutil
from types import SimpleNamespace

from scripts.run_mlp_shared_prefix_experiment import complete, override, preserve, experiment_stages


def fixture_checkpoint(root, tag="step_1"):
    root.mkdir()
    directory = root / f"fsdp2_{tag}"
    directory.mkdir()
    (root / f"checkpoint_state_{tag}.json").write_text(json.dumps({"step": 1}))
    (directory / "rank.distcp").write_bytes(b"checkpoint")
    with (directory / ".metadata").open("wb") as handle:
        pickle.dump(SimpleNamespace(storage_data={"weight": SimpleNamespace(
            relative_path="rank.distcp", offset=0, length=10)}), handle)


def test_completion_checks_payload_ranges(tmp_path):
    root = tmp_path / "source"
    assert not complete(root, "step_1")
    fixture_checkpoint(root)
    assert complete(root, "step_1")
    (root / "fsdp2_step_1" / "rank.distcp").write_bytes(b"short")
    assert not complete(root, "step_1")


def test_preserved_links_survive_source_pruning(tmp_path):
    source, target = tmp_path / "source", tmp_path / "archive"
    fixture_checkpoint(source)
    preserve(source, target, "step_1")
    assert (target / "fsdp2_step_1" / "rank.distcp").stat().st_nlink == 2
    shutil.rmtree(source)
    assert complete(target, "step_1")


def test_overrides_replace_instead_of_append_duplicates():
    assert override(["torchrun", "lr=0.1", "+max_steps=10", "data=dfm10"], lr=0.2, max_steps="null") == [
        "torchrun", "data=dfm10", "lr=0.2", "max_steps=null"]


def test_reused_prefix_only_runs_requested_new_coefficient():
    assert experiment_stages(1e-3, True) == [
        ("regularized", "prefix", "step_453000", 454000, 1e-3)]
    assert [stage[0] for stage in experiment_stages()] == [
        "prefix", "diagnostics_preflight", "baseline", "regularized"]


def test_update_calibration_uses_matched_short_branches():
    stages = experiment_stages(update_calibration=True)
    assert [stage[0] for stage in stages] == ["update_control", "update_baseline", "update_regularized"]
    assert all(stage[2:4] == ("step_453000", 453010) for stage in stages)
    assert [stage[4] for stage in stages] == [0, 0, 1e-4]


def test_three_way_report_leaves_reference_results_untouched(tmp_path, monkeypatch):
    from scripts.summarize_mlp_shared_prefix_experiment import main
    old, new = tmp_path / "old", tmp_path / "new"
    for path, weight in ((old / "baseline", 0), (old / "regularized", 1e-4), (new / "regularized", 1e-3)):
        path.mkdir(parents=True)
        (path / "command.json").write_text(json.dumps([f"+arch.mlp_relative_energy_weight={weight}"]))
        (path / "metrics.json").write_text(json.dumps({
            "median_step_seconds": 3,
            "metric_history": [{"step": 453450, "train/loss": 1.0}, {"step": 454000, "train/loss": 2.0}]}))
    (old / "comparison.md").write_text("preserved report")
    monkeypatch.setattr("sys.argv", ["report", str(new), "--reference-root", str(old)])
    main()
    result = json.loads((new / "comparison.json").read_text())
    assert result["new_regularized"]["coefficient"] == 1e-3
    assert result["previous_regularized"]["coefficient"] == 1e-4
    assert result["baseline"]["coefficient"] == 0
    assert (old / "comparison.md").read_text() == "preserved report"

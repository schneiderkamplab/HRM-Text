from scripts.clone_wandb_run_to_step import clean_history_row, metric_axis


def test_cutoff_and_axes():
    assert clean_history_row({"_step": 520001, "train/loss": 1.0}, 520000) is None
    row = clean_history_row({"_step": 520000, "train/loss": 1.0, "_runtime": 10}, 520000)
    assert row == {"_step": 520000, "train/loss": 1.0, "train/step": 520000}
    assert metric_axis("headline_avg_v3/danish") == "headline_avg_v3/epoch"
    assert metric_axis("suite_avg_v3/dfm") == "suite_avg_v3/epoch"
    assert metric_axis("train/accuracy") == "train/step"


def test_preserves_eval_epoch_and_rejects_nonfinite():
    assert clean_history_row({"_step": 500020, "dfm_eval/epoch": 1.5, "dfm_eval/a": 0.8,
                              "bad": float("nan")}, 520000) == {
                                  "_step": 500020, "dfm_eval/epoch": 1.5, "dfm_eval/a": 0.8}

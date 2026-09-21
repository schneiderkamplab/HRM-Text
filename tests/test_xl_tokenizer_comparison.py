import json
from scripts import schedule_xl_2750k_tokenizer_comparison as campaign


def test_collect_nested_and_flat_metrics(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign, "ROOT", tmp_path)
    for family, payload in (
        ("eval", {"metrics": {"eval/MATH/acc": .5}, "num_samples": 5000}),
        ("dfm_evals", {"metrics": {"dfm_eval/piqa/accuracy": .6}}),
        ("euroeval", {"euroeval/da/angry-tweets/macro_f1": 75.}),
    ):
        path = tmp_path / "logs" / family / "comparison" / "merged_metrics.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(payload))
    assert campaign.metrics("comparison") == {
        "eval/MATH/acc": .5, "dfm_eval/piqa/accuracy": .6,
        "euroeval/da/angry-tweets/macro_f1": 75.,
    }

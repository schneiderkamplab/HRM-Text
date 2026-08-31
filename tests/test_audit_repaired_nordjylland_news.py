from scripts.audit_repaired_nordjylland_news import stable_priority, summarize_rows


def test_stable_priority_is_deterministic() -> None:
    assert stable_priority(1, 7) == stable_priority(1, 7)
    assert stable_priority(1, 7) != stable_priority(2, 7)


def test_summary_tracks_strict_acceptance(tmp_path) -> None:
    rows = [
        {
            "judgment": {
                "usable_for_training": True,
                "complete": True,
                "language_quality": 5,
                "instruction_answer_coherence": 4,
                "grounding": 4,
                "training_value": 3,
                "primary_problem": "none",
            }
        },
        {
            "judgment": {
                "usable_for_training": True,
                "complete": True,
                "language_quality": 5,
                "instruction_answer_coherence": 4,
                "grounding": 3,
                "training_value": 4,
                "primary_problem": "unsupported_claim",
            }
        },
    ]
    output = tmp_path / "summary.json"
    summarize_rows(rows, output, "judge")
    import json
    summary = json.loads(output.read_text())
    assert summary["counts"]["usable"] == 2
    assert summary["counts"]["strict_accepted"] == 1

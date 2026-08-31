import json

from scripts.classify_mimir_mmlu_failure_ontology import migrate_retryable_errors, parse_labels


def test_parse_labels_recovers_complete_fields_from_truncated_json() -> None:
    content = """{
      "broad_domain": "science",
      "discipline": "physics",
      "subdiscipline": "mechanics",
      "concept": "momentum",
      "cognitive_operation": "conceptual_application",
      "knowledge_form": "law_or_rule",
      "prerequisites": ["vectors", "forces"],
      "recommended_grounding": "open_textbook",
    """
    labels, recovered = parse_labels(content)
    assert recovered is True
    assert labels["concept"] == "momentum"
    assert labels["prerequisites"] == ["vectors", "forces"]


def test_migrate_retryable_errors(tmp_path) -> None:
    path = tmp_path / "partition.jsonl"
    path.write_text(
        json.dumps({"sample_id": "bad", "classification_error": "bad json"})
        + "\n"
        + json.dumps({"sample_id": "good", "labels": {}})
        + "\n"
    )
    migrate_retryable_errors(path)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows[0]["generation_error"] == "bad json"
    assert "classification_error" not in rows[0]
    assert rows[1]["labels"] == {}

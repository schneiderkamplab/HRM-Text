import json
from pathlib import Path

from scripts.prepare_mimir_grounding_passages import sample_openstax_cc_by


def test_verified_openstax_sampling_preserves_provenance(tmp_path: Path) -> None:
    path = tmp_path / "passages.jsonl"
    row = {
        "dataset": "OpenStax/official-cc-by-4.0",
        "book_slug": "chemistry-2e",
        "document_id": "m1",
        "passage_index": 0,
        "category": "natural_health_sciences",
        "license": "CC-BY-4.0",
        "immutable_ref": "a" * 40,
        "passage": "A grounded chemistry passage.",
    }
    path.write_text(json.dumps(row) + "\n")
    sampled = sample_openstax_cc_by(
        {"technical_stem": 10, "professional_domains": 10}, path
    )
    assert sampled["technical_stem"][0]["book_slug"] == "chemistry-2e"
    assert sampled["professional_domains"][0]["immutable_ref"] == "a" * 40


def test_unverified_openstax_row_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "passages.jsonl"
    path.write_text(json.dumps({
        "book_slug": "chemistry-2e", "document_id": "1", "passage_index": 0,
        "category": "natural_health_sciences", "license": "provisional",
        "immutable_ref": "", "passage": "text",
    }) + "\n")
    try:
        sample_openstax_cc_by({"technical_stem": 1}, path)
    except ValueError as error:
        assert "verified license" in str(error)
    else:
        raise AssertionError("unverified OpenStax row was accepted")

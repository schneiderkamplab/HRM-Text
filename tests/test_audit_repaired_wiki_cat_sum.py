import json
from pathlib import Path

import pytest

from scripts.audit_repaired_wiki_cat_sum import (
    domain_for,
    strict_usable,
    validate_full_audit,
)


def test_domain_for_sharded_file() -> None:
    from pathlib import Path

    assert domain_for(Path("train-film.part-003-of-016.parquet")) == "film"


def test_strict_usable_requires_all_substantive_fields() -> None:
    judgment = {
        "usable_for_training": True,
        "complete": True,
        "language_quality": 5,
        "instruction_answer_coherence": 5,
        "grounding": 4,
        "training_value": 4,
        "primary_problem": "none",
    }
    assert strict_usable(judgment)
    judgment["grounding"] = 2
    assert not strict_usable(judgment)
    judgment["grounding"] = 4
    judgment["primary_problem"] = "incomplete"
    assert not strict_usable(judgment)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def test_validate_full_audit_rejects_pilot(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    audit_dir = tmp_path / "audit"
    write_json(input_dir / "repair_summary.json", {"counts": {"written": 2}})
    write_json(
        audit_dir / "inventory.json",
        {"all_rows": False, "sample_count": 2, "available_by_domain": {"film": 2}},
    )
    write_json(
        audit_dir / "summary.json",
        {"rows": 2, "strict_usable": 2, "strict_usable_rate": 1.0},
    )
    (audit_dir / "wiki_cat_sum_repaired_quality_audit.jsonl").write_text(
        '{"sample_id":"a"}\n{"sample_id":"b"}\n', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="sampled pilot"):
        validate_full_audit(input_dir, audit_dir, 0.9)


def test_validate_full_audit_accepts_exact_coverage(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    audit_dir = tmp_path / "audit"
    write_json(input_dir / "repair_summary.json", {"counts": {"written": 2}})
    write_json(
        audit_dir / "inventory.json",
        {"all_rows": True, "sample_count": 2, "available_by_domain": {"film": 2}},
    )
    write_json(
        audit_dir / "summary.json",
        {"rows": 2, "strict_usable": 2, "strict_usable_rate": 1.0},
    )
    (audit_dir / "wiki_cat_sum_repaired_quality_audit.jsonl").write_text(
        '{"sample_id":"a"}\n{"sample_id":"b"}\n', encoding="utf-8"
    )
    assert validate_full_audit(input_dir, audit_dir, 0.9)["audited_rows"] == 2

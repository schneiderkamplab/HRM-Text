from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import scripts.audit_wiki_cat_sum_recovery as audit
import scripts.generate_wiki_cat_sum_recovery as generator
import scripts.prepare_wiki_cat_sum_recovery as recovery


def test_selected_evidence_prioritizes_title_mentions() -> None:
    row = {
        "title": "Example Company",
        "paragraphs": [
            "A long unrelated sentence about an unrelated market and its participants.",
            "Example Company develops testing equipment for research laboratories.",
        ],
    }
    selected = recovery.selected_evidence(row, max_chars=500)
    assert selected[0].startswith("Example Company")


def test_generation_parser_recovers_complete_fields() -> None:
    content = (
        '{"usable": true, "summary": "A grounded summary.", '
        '"reason": "Supported"'
    )
    parsed, recovered = generator.parse_content(content)
    assert recovered
    assert parsed == {
        "usable": True,
        "summary": "A grounded summary.",
        "reason": "Supported",
    }


def test_generation_parser_accepts_valid_json() -> None:
    payload = {"usable": False, "summary": "", "reason": "No useful evidence"}
    parsed, recovered = generator.parse_content(json.dumps(payload))
    assert not recovered
    assert parsed == payload


def test_terminal_judge_failures_are_explicitly_rejected(tmp_path: Path) -> None:
    audit_dir = tmp_path / "audit"
    (audit_dir / "partitions").mkdir(parents=True)
    (audit_dir / "results").mkdir()
    samples = [
        {"sample_id": "a", "sample_ordinal": 0, "domain": "animal"},
        {"sample_id": "b", "sample_ordinal": 1, "domain": "animal"},
    ]
    (audit_dir / "partitions/partition_0.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in samples), encoding="utf-8"
    )
    accepted = {
        **samples[0],
        "judge_model": "judge",
        "judgment": {
            "language_quality": 5,
            "instruction_answer_coherence": 5,
            "grounding": 5,
            "training_value": 5,
            "complete": True,
            "usable_for_training": True,
            "primary_problem": "none",
        },
    }
    (audit_dir / "results/partition_0.audit.jsonl.partial").write_text(
        json.dumps(accepted) + "\n", encoding="utf-8"
    )

    audit.fail_close(Namespace(audit_dir=audit_dir, partitions=1, model="judge"))

    rows = [
        json.loads(line)
        for line in (audit_dir / "results/partition_0.audit.jsonl").read_text().splitlines()
    ]
    assert [row["sample_id"] for row in rows] == ["a", "b"]
    assert rows[1]["terminal_judge_failure"] is True
    assert rows[1]["judgment"]["usable_for_training"] is False
    assert not (audit_dir / "results/partition_0.audit.jsonl.partial").exists()

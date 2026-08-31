import json
from argparse import Namespace

from scripts.audit_dfm10_tidsskrift_summaries import candidate_fingerprint, cmd_filter


def test_filter_requires_audit_and_removes_duplicate_targets(tmp_path) -> None:
    candidates = tmp_path / "candidates.jsonl"
    audit = tmp_path / "audit.jsonl"
    output = tmp_path / "accepted.jsonl"
    rows = [
        {"source_id": "a", "messages": [{"content": "p"}, {"content": "duplicate"}]},
        {"source_id": "b", "messages": [{"content": "q"}, {"content": "duplicate"}]},
        {"source_id": "c", "messages": [{"content": "r"}, {"content": "unique"}]},
    ]
    candidates.write_text("".join(json.dumps(row) + "\n" for row in rows))
    audit.write_text(
        json.dumps(
            {
                "source_id": "c",
                "candidate_fingerprint": candidate_fingerprint(rows[2]),
                "audit_complete": True,
                "keep": True,
                "grounding": 5,
            }
        )
        + "\n"
    )
    cmd_filter(Namespace(input=candidates, audit=audit, output=output))
    accepted = [json.loads(line) for line in output.read_text().splitlines()]
    assert [row["source_id"] for row in accepted] == ["c"]
